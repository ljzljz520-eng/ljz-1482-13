import { useCallback, useEffect, useState } from "react";
import toast from "react-hot-toast";
import { gcCandidates, runGc, setLicense, uploadImage } from "../api/endpoints";
import type { GcCandidate, LicenseImpact } from "../types";
import { useAuth, isAdmin } from "../store/auth";
import { Badge, Button, Card, Empty, Modal, PageHeader, SkeletonRows } from "../components/ui";

export default function Assets() {
  const { user } = useAuth();
  const [items, setItems] = useState<GcCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [impact, setImpact] = useState<LicenseImpact | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await gcCandidates());
    } catch (e) {
      toast.error((e as { friendlyMessage?: string }).friendlyMessage ?? "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const deletable = items.filter((i) => i.deletable);

  return (
    <div>
      <PageHeader
        title="图片与清理"
        subtitle="授权撤销会给出受影响角色版本与场次；物理清理前检查参考图/派生/在途任务/历史导出五类引用"
        actions={
          <>
            <label className="cursor-pointer rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-500">
              {uploading ? "上传中…" : "＋ 上传图片"}
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                className="hidden"
                onChange={async (e) => {
                  const f = e.target.files?.[0];
                  if (!f) return;
                  setUploading(true);
                  try {
                    const a = await uploadImage(f, "图片库上传");
                    toast.success(`已上传 ${a.original_filename}`);
                    load();
                  } catch (err) {
                    toast.error((err as { friendlyMessage?: string }).friendlyMessage ?? "上传失败");
                  } finally {
                    setUploading(false);
                  }
                }}
              />
            </label>
            {isAdmin(user) && (
              <Button
                variant="secondary"
                disabled={deletable.length === 0}
                onClick={async () => {
                  const res = await runGc();
                  toast.success(`已物理删除 ${res.deleted.length} 个；保留 ${res.kept.length} 个（仍有引用）`);
                  load();
                }}
              >
                清理未引用图片（{deletable.length}）
              </Button>
            )}
          </>
        }
      />

      <Card className="mb-4 overflow-hidden">
        <div className="border-b border-slate-100 bg-slate-50/60 px-4 py-2 text-xs text-slate-500">
          图例：
          <span className="ml-2">📖 参考图</span>
          <span className="ml-2">↗ 派生来源</span>
          <span className="ml-2">🖼 派生产物</span>
          <span className="ml-2">⏳ 在途任务</span>
          <span className="ml-2 text-violet-600">📦 历史导出（即使其它引用都没了也保留）</span>
        </div>
      </Card>

      {loading ? (
        <Card>
          <SkeletonRows rows={5} />
        </Card>
      ) : items.length === 0 ? (
        <Card>
          <Empty text="图片库为空" />
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {items.map((item) => (
            <AssetCard key={item.asset.id} item={item} isAdmin={isAdmin(user)} onChanged={load} onImpact={setImpact} />
          ))}
        </div>
      )}

      {impact && <ImpactModal impact={impact} onClose={() => setImpact(null)} />}
    </div>
  );
}

function AssetCard({
  item,
  isAdmin,
  onChanged,
  onImpact,
}: {
  item: GcCandidate;
  isAdmin: boolean;
  onChanged: () => void;
  onImpact: (i: LicenseImpact) => void;
}) {
  const [busy, setBusy] = useState(false);
  const a = item.asset;
  const tags: { text: string; show: boolean; violet?: boolean }[] = [
    { text: "📖 参考图", show: item.referenced_by_reference },
    { text: "↗ 派生来源", show: item.referenced_by_generated_source },
    { text: "🖼 派生产物", show: item.referenced_by_generated_output },
    { text: "⏳ 在途任务", show: item.referenced_by_pending_job },
    { text: "📦 历史导出", show: item.referenced_by_export, violet: true },
  ];

  const toggleLicense = async () => {
    setBusy(true);
    try {
      const next = !a.license_granted;
      const result = await setLicense(a.id, next, next ? "授权恢复" : "授权撤销（复核中）");
      toast.success(next ? "授权已恢复" : "授权已撤销，请查看影响面");
      onImpact(result);
      onChanged();
    } catch (e) {
      toast.error((e as { friendlyMessage?: string }).friendlyMessage ?? "操作失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="overflow-hidden">
      <div className={`relative h-36 bg-slate-100 ${!a.license_granted ? "grayscale" : ""}`}>
        <img src={a.url} alt={a.original_filename} className="h-full w-full object-cover" />
        <div className="absolute left-2 top-2">
          {a.license_granted ? <Badge tone="green">已授权</Badge> : <Badge tone="red">授权撤销</Badge>}
          {item.deletable && <Badge tone="slate" className="ml-1">可清理</Badge>}
        </div>
      </div>
      <div className="p-3">
        <p className="truncate text-sm font-medium text-slate-800">{a.original_filename}</p>
        <p className="mt-0.5 text-xs text-slate-400">{a.width}×{a.height} · {a.license_note || "无授权备注"}</p>
        <div className="mt-2 flex flex-wrap gap-1">
          {tags.filter((t) => t.show).map((t) => (
            <span
              key={t.text}
              className={`rounded-md px-1.5 py-0.5 text-[11px] ${
                t.violet ? "bg-violet-50 text-violet-700" : "bg-slate-100 text-slate-500"
              }`}
            >
              {t.text}
            </span>
          ))}
          {!tags.some((t) => t.show) && (
            <span className="text-[11px] text-slate-400">无任何引用 —— 可安全物理删除</span>
          )}
        </div>
        <div className="mt-3 flex justify-end">
          <Button size="sm" variant={a.license_granted ? "danger" : "primary"} loading={busy} onClick={toggleLicense}>
            {a.license_granted ? "撤销授权" : "恢复授权"}
          </Button>
        </div>
      </div>
    </Card>
  );
}

function ImpactModal({ impact, onClose }: { impact: LicenseImpact; onClose: () => void }) {
  return (
    <Modal open onClose={onClose} title="授权变更影响面" wide footer={<Button onClick={onClose}>知道了</Button>}>
      <div className="space-y-4 text-sm">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Box label="影响版本" value={impact.affected_versions.length} />
          <Box label="影响场次" value={impact.affected_scenes.length} />
          <Box label="在途任务" value={impact.pending_cover_jobs} />
          <Box label="历史导出" value={impact.export_snapshots} highlight />
        </div>
        {impact.affected_versions.length > 0 && (
          <div>
            <p className="mb-1 text-xs font-semibold text-slate-500">角色版本</p>
            <ul className="space-y-1">
              {impact.affected_versions.map((v) => (
                <li key={v.version_id} className="text-slate-700">
                  {v.character_name} <Badge tone="blue">v{v.version}</Badge>
                </li>
              ))}
            </ul>
          </div>
        )}
        {impact.affected_scenes.length > 0 && (
          <div>
            <p className="mb-1 text-xs font-semibold text-slate-500">受影响场次</p>
            <ul className="space-y-1">
              {impact.affected_scenes.map((s) => (
                <li key={s.link_id} className="flex items-center justify-between text-slate-700">
                  <span>
                    <span className="mr-2 font-mono text-xs text-slate-400">{s.scene_code}</span>
                    {s.title}
                  </span>
                  {s.ref_mode === "pinned" ? (
                    <Badge tone="blue">固定 v{s.pinned_version}</Badge>
                  ) : (
                    <Badge tone="violet">跟随 v{s.latest_version}</Badge>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
        <p className="rounded-xl bg-slate-50 px-3 py-2 text-xs leading-6 text-slate-500">
          在途封面任务将在 worker 处理时二次校验授权并中止；已生成的历史导出仍保留该图片，
          因此物理清理不会删除它。
        </p>
      </div>
    </Modal>
  );
}

function Box({ label, value, highlight }: { label: string; value: number; highlight?: boolean }) {
  return (
    <div className={`rounded-xl px-3 py-2.5 ${highlight ? "bg-violet-50 text-violet-700" : "bg-slate-50 text-slate-700"}`}>
      <p className="text-lg font-bold leading-tight">{value}</p>
      <p className="text-xs opacity-70">{label}</p>
    </div>
  );
}
