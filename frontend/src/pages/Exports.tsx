import { useCallback, useEffect, useState } from "react";
import toast from "react-hot-toast";
import { createExport, listExports, listScripts } from "../api/endpoints";
import type { ExportRecord, Script as ScriptType } from "../types";
import { canEdit, useAuth } from "../store/auth";
import { Badge, Button, Card, Empty, Field, Modal, PageHeader, SkeletonRows, inputCls } from "../components/ui";

export default function Exports() {
  const { user } = useAuth();
  const [items, setItems] = useState<ExportRecord[]>([]);
  const [scripts, setScripts] = useState<ScriptType[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [ex, ss] = await Promise.all([listExports(), listScripts()]);
      setItems(ex);
      setScripts(ss);
    } catch (e) {
      toast.error((e as { friendlyMessage?: string }).friendlyMessage ?? "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div>
      <PageHeader
        title="导出快照"
        subtitle="导出时冻结角色版本与图片集合；只要历史导出存在，被引用图片就不会被物理清理"
        actions={canEdit(user) ? <Button onClick={() => setOpen(true)}>＋ 新建导出</Button> : undefined}
      />

      {loading ? (
        <Card>
          <SkeletonRows rows={3} />
        </Card>
      ) : items.length === 0 ? (
        <Card>
          <Empty text="暂无导出快照" />
        </Card>
      ) : (
        <div className="space-y-3">
          {items.map((ex) => (
            <Card key={ex.id} className="p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-slate-900">{ex.label}</h3>
                    <Badge tone="violet">📦 {ex.image_count} 张图片被锁定</Badge>
                  </div>
                  <p className="mt-1 text-xs text-slate-400">
                    {ex.created_by_name} · {new Date(ex.created_at).toLocaleString("zh-CN")}
                  </p>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {ex.character_refs.map((r) => (
                  <span
                    key={r.version_id}
                    className="rounded-lg bg-slate-50 px-2.5 py-1 text-xs text-slate-600 ring-1 ring-slate-200"
                  >
                    {r.character_name} <b className="text-slate-800">v{r.version}</b>
                  </span>
                ))}
              </div>
            </Card>
          ))}
        </div>
      )}

      {open && (
        <CreateExportModal
          scripts={scripts}
          onClose={() => setOpen(false)}
          onDone={() => {
            setOpen(false);
            load();
          }}
        />
      )}
    </div>
  );
}

function CreateExportModal({
  scripts,
  onClose,
  onDone,
}: {
  scripts: ScriptType[];
  onClose: () => void;
  onDone: () => void;
}) {
  const [label, setLabel] = useState(`导出 ${new Date().toISOString().slice(0, 10)}`);
  const [scope, setScope] = useState<"all" | "script">("script");
  const [scriptId, setScriptId] = useState(scripts[0]?.id ?? "");
  const [busy, setBusy] = useState(false);

  return (
    <Modal
      open
      onClose={onClose}
      title="新建导出快照"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>取消</Button>
          <Button
            loading={busy}
            onClick={async () => {
              if (!label.trim()) return toast.error("请填写导出名称");
              setBusy(true);
              try {
                await createExport({
                  label,
                  script_id: scope === "script" ? scriptId : null,
                });
                toast.success("快照已创建：版本与图片引用已冻结");
                onDone();
              } catch (e) {
                toast.error((e as { friendlyMessage?: string }).friendlyMessage ?? "导出失败");
              } finally {
                setBusy(false);
              }
            }}
          >
            创建快照
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="快照名称">
          <input className={inputCls} value={label} onChange={(e) => setLabel(e.target.value)} />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={() => setScope("script")}
            className={`rounded-xl border p-3 text-sm ${scope === "script" ? "border-blue-400 bg-blue-50" : "border-slate-200"}`}
          >
            按场次导出
            <span className="mt-1 block text-xs text-slate-500">固定引用保留版本，跟随引用冻结为当时最新版</span>
          </button>
          <button
            type="button"
            onClick={() => setScope("all")}
            className={`rounded-xl border p-3 text-sm ${scope === "all" ? "border-blue-400 bg-blue-50" : "border-slate-200"}`}
          >
            全量导出
            <span className="mt-1 block text-xs text-slate-500">冻结全部角色最新版与其图片</span>
          </button>
        </div>
        {scope === "script" && (
          <Field label="选择场次">
            <select className={inputCls} value={scriptId} onChange={(e) => setScriptId(e.target.value)}>
              {scripts.map((s) => (
                <option key={s.id} value={s.id}>{s.scene_code} · {s.title}</option>
              ))}
            </select>
          </Field>
        )}
      </div>
    </Modal>
  );
}
