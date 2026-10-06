import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { reviewApi } from "@/api";
import type { ReviewItem } from "@/types";
import { Badge, Button, Card, EmptyState } from "@/components/ui";
import { useAuthStore } from "@/store/authStore";

const kindMeta: Record<ReviewItem["kind"], { label: string; icon: string }> = {
  line_recheck: { label: "台词复核", icon: "📝" },
  cover_failed: { label: "封面生成失败", icon: "🎞" },
  license_revoked: { label: "授权撤销", icon: "⛔" },
  stale_cover: { label: "旧封面晚到", icon: "🕓" },
};

const sevTone = { critical: "red", warning: "amber", info: "slate" } as const;

const ReviewPage = () => {
  const { user } = useAuthStore();
  const canEdit = user?.role === "admin" || user?.role === "editor";
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [filter, setFilter] = useState<"open" | "resolved" | "all">("open");
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      setItems(await reviewApi.list(filter));
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load();
  }, [filter]);

  const grouped = useMemo(() => {
    const byScene = new Map<string, { label: string; rows: ReviewItem[] }>();
    for (const item of items) {
      const key = item.scene_code ?? item.kind;
      const label = item.scene_code
        ? `场次 ${item.scene_code}${item.scene_title ? " · " + item.scene_title : ""}`
        : kindMeta[item.kind].label;
      if (!byScene.has(key)) byScene.set(key, { label, rows: [] });
      byScene.get(key)!.rows.push(item);
    }
    return Array.from(byScene.entries());
  }, [items]);

  const resolve = async (id: string) => {
    await reviewApi.resolve(id);
    setItems((list) => list.filter((x) => x.id !== id));
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900">待复核队列</h2>
          <p className="mt-1 text-sm text-slate-500">
            汇总角色改版、封面失败、授权撤销、旧任务晚到 —— 按受影响场次呈现。
          </p>
        </div>
        <div className="flex gap-1 rounded-full bg-slate-100 p-1">
          {(["open", "all", "resolved"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={
                "rounded-full px-3 py-1.5 text-xs font-medium transition " +
                (filter === f ? "bg-white text-primary shadow-sm" : "text-slate-500 hover:text-slate-700")
              }
            >
              {f === "open" ? "待处理" : f === "resolved" ? "已处理" : "全部"}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="h-40 animate-pulse rounded-2xl bg-slate-200/60" />
      ) : items.length === 0 ? (
        <EmptyState icon="✅" title="没有待处理的复核项" hint="角色改版或素材失败时会自动在这里生成任务。" />
      ) : (
        <div className="grid gap-4">
          {grouped.map(([key, group]) => (
            <Card key={key}>
              <p className="mb-3 text-sm font-semibold text-slate-800">
                🎬 {group.label}
              </p>
              <div className="space-y-2">
                {group.rows.map((item) => (
                  <div
                    key={item.id}
                    className="flex flex-wrap items-center gap-3 rounded-xl bg-slate-50 px-3 py-2.5 ring-1 ring-slate-100"
                  >
                    <span className="text-lg">{kindMeta[item.kind].icon}</span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <Badge tone={sevTone[item.severity]}>{kindMeta[item.kind].label}</Badge>
                        {item.character_name && (
                          <span className="text-xs font-medium text-slate-600">
                            {item.character_name}
                          </span>
                        )}
                        {item.status === "resolved" && <Badge tone="green">已处理</Badge>}
                      </div>
                      <p className="mt-0.5 text-xs text-slate-600">{item.message}</p>
                    </div>
                    <div className="flex gap-1.5">
                      {item.character_id && (
                        <Link to={`/characters/${item.character_id}`}>
                          <Button size="sm" variant="ghost">
                            查看角色
                          </Button>
                        </Link>
                      )}
                      {canEdit && item.status === "open" && (
                        <Button size="sm" onClick={() => resolve(item.id)}>
                          标记已处理
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default ReviewPage;
