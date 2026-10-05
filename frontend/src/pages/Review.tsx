import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import toast from "react-hot-toast";
import {
  getDashboard,
  resolveReview,
  retryCoverJob,
  restoreCharacter,
} from "../api/endpoints";
import type { Dashboard, ReviewKind } from "../types";
import { useAuth, isAdmin } from "../store/auth";
import { Badge, Button, Card, Empty, PageHeader, SkeletonRows } from "../components/ui";
import { usePolling } from "../hooks/usePolling";

const kindMeta: Record<ReviewKind, { label: string; tone: "red" | "amber" | "blue" | "violet" | "green"; icon: string }> = {
  edit_conflict: { label: "并发编辑冲突", tone: "red", icon: "⚔️" },
  license_revoked: { label: "来源图授权撤销", tone: "amber", icon: "⚠️" },
  generation_failed: { label: "素材生成失败", tone: "red", icon: "🧩" },
  retired_referenced: { label: "退役引用问题", tone: "violet", icon: "🔁" },
  approved_drift: { label: "已批准台词漂移", tone: "amber", icon: "📝" },
};

export default function Review() {
  const { user } = useAuth();
  const [data, setData] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setData(await getDashboard());
    } catch (e) {
      toast.error((e as { friendlyMessage?: string }).friendlyMessage ?? "工作台加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);
  usePolling(load, 8000, !!data && data.failed_jobs.some((j) => j.state === "pending" || j.state === "processing"));

  if (loading || !data) {
    return (
      <Card>
        <SkeletonRows rows={5} />
      </Card>
    );
  }

  const totalOpen = data.review_items.length;

  return (
    <div>
      <PageHeader
        title="复核工作台"
        subtitle="受影响场次 · 待复核项 · 失败/过期任务 · 软删除角色 —— 全部需要显式人工处理"
        actions={<Button variant="secondary" onClick={load}>刷新</Button>}
      />

      <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="待复核项" value={totalOpen} tone="rose" />
        <Metric label="受影响场次" value={data.affected_scenes.length} tone="amber" />
        <Metric label="失败/过期任务" value={data.failed_jobs.length} tone="blue" />
        <Metric label="软删除角色" value={data.soft_deleted_characters.length} tone="slate" />
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card>
          <div className="border-b border-slate-100 px-5 py-3">
            <h3 className="text-sm font-semibold text-slate-800">受影响场次（已批准台词 vs 角色最新版）</h3>
          </div>
          {data.affected_scenes.length === 0 ? (
            <Empty text="没有待复核场次" />
          ) : (
            <ul className="divide-y divide-slate-100">
              {data.affected_scenes.map((s) => (
                <li key={s.link_id} className="flex items-center justify-between gap-3 px-5 py-3">
                  <div className="min-w-0">
                    <p className="text-sm text-slate-800">
                      <span className="mr-2 font-mono text-xs text-slate-400">{s.scene_code}</span>
                      {s.title}
                    </p>
                    <p className="mt-0.5 text-xs text-amber-700">
                      跟随最新引用：批准基线 v{s.approved_version} → 最新 v{s.latest_version}
                    </p>
                  </div>
                  <Link to="/scripts">
                    <Button size="sm" variant="secondary">去复核</Button>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <div className="border-b border-slate-100 px-5 py-3">
            <h3 className="text-sm font-semibold text-slate-800">待复核项</h3>
          </div>
          {data.review_items.length === 0 ? (
            <Empty text="一切正常 ✅" />
          ) : (
            <ul className="divide-y divide-slate-100">
              {data.review_items.map((item) => {
                const meta = kindMeta[item.kind];
                return (
                  <li key={item.id} className="px-5 py-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium text-slate-800">
                        <span className="mr-1.5">{meta.icon}</span>
                        {item.title}
                      </p>
                      <Badge tone={meta.tone}>{meta.label}</Badge>
                    </div>
                    <p className="mt-1 text-xs leading-5 text-slate-500">{item.detail}</p>
                    <div className="mt-2 flex items-center gap-2">
                      {item.character_id && (
                        <Link to={`/characters/${item.character_id}`}>
                          <Button size="sm" variant="ghost">查看角色</Button>
                        </Link>
                      )}
                      {item.script_id && <Link to="/scripts"><Button size="sm" variant="ghost">查看场次</Button></Link>}
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={async () => {
                          await resolveReview(item.id);
                          toast.success("已标记为处理完成");
                          load();
                        }}
                      >
                        标记已处理
                      </Button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        <Card>
          <div className="border-b border-slate-100 px-5 py-3">
            <h3 className="text-sm font-semibold text-slate-800">失败 / 过期封面任务</h3>
          </div>
          {data.failed_jobs.length === 0 ? (
            <Empty text="没有失败任务" />
          ) : (
            <ul className="divide-y divide-slate-100">
              {data.failed_jobs.map((j) => (
                <li key={j.id} className="flex items-center justify-between gap-3 px-5 py-3">
                  <div className="min-w-0">
                    <Badge tone={j.state === "stale" ? "violet" : "red"}>
                      {j.state === "stale" ? "旧任务·已归档" : "生成失败"}
                    </Badge>
                    <p className="mt-1 truncate font-mono text-[11px] text-slate-400">
                      {j.params_fingerprint} · {j.target_width}×{j.target_height}
                    </p>
                    {j.last_error && <p className="mt-0.5 truncate text-xs text-rose-600">{j.last_error}</p>}
                  </div>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={async () => {
                      await retryCoverJob(j.id);
                      toast.success("已重新入队");
                      setTimeout(load, 500);
                    }}
                  >
                    重新入队
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <div className="border-b border-slate-100 px-5 py-3">
            <h3 className="text-sm font-semibold text-slate-800">软删除角色（引用仍保留）</h3>
          </div>
          {data.soft_deleted_characters.length === 0 ? (
            <Empty text="无软删除角色" />
          ) : (
            <ul className="divide-y divide-slate-100">
              {data.soft_deleted_characters.map((c) => (
                <li key={c.id} className="flex items-center justify-between px-5 py-3">
                  <Link to={`/characters/${c.id}`} className="text-sm text-slate-800 hover:text-blue-600">
                    {c.name} <span className="font-mono text-xs text-slate-400">{c.code}</span>
                  </Link>
                  {isAdmin(user) && (
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={async () => {
                        await restoreCharacter(c.id);
                        toast.success("角色已恢复");
                        load();
                      }}
                    >
                      恢复
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: number; tone: "rose" | "amber" | "blue" | "slate" }) {
  const map = {
    rose: "from-rose-500 to-red-500",
    amber: "from-amber-500 to-orange-500",
    blue: "from-blue-500 to-indigo-500",
    slate: "from-slate-500 to-slate-600",
  } as const;
  return (
    <div className={`rounded-2xl bg-gradient-to-br ${map[tone]} p-4 text-white shadow-card`}>
      <p className="text-3xl font-bold">{value}</p>
      <p className="mt-1 text-xs text-white/85">{label}</p>
    </div>
  );
}
