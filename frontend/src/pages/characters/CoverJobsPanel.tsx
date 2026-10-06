import { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { coverApi, imageApi } from "@/api";
import type { Character, CoverJob, CropParams, RefImage } from "@/types";
import { Badge, Button, Card, Field, Select } from "@/components/ui";
import { useAuthStore } from "@/store/authStore";

const statusTone: Record<CoverJob["status"], "slate" | "blue" | "amber" | "red" | "green"> = {
  pending: "amber",
  processing: "blue",
  succeeded: "green",
  failed: "red",
  stale: "slate",
};
const statusLabel: Record<CoverJob["status"], string> = {
  pending: "排队中",
  processing: "生成中",
  succeeded: "成功",
  failed: "失败",
  stale: "旧任务晚到",
};

const CoverJobsPanel = ({ character }: { character: Character }) => {
  const { user } = useAuthStore();
  const canEdit = user?.role === "admin" || user?.role === "editor";
  const isAdmin = user?.role === "admin";
  const [jobs, setJobs] = useState<CoverJob[]>([]);
  const [images, setImages] = useState<RefImage[]>([]);
  const [versionId, setVersionId] = useState(character.current_version_id ?? "");
  const [sourceId, setSourceId] = useState("");
  const [crop, setCrop] = useState({ x: 0.05, y: 0.05, width: 0.9, height: 0.9 });
  const [size, setSize] = useState(1024);
  const [forceFail, setForceFail] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    const [js, imgs] = await Promise.all([coverApi.list(character.id), imageApi.list()]);
    setJobs(js);
    setImages(imgs);
  };
  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [character.id]);

  const selectedSource = useMemo(
    () => images.find((i) => i.id === sourceId),
    [images, sourceId],
  );

  const enqueue = async () => {
    if (!sourceId) {
      toast.error("请选择已授权的来源原图");
      return;
    }
    if (crop.x + crop.width > 1 || crop.y + crop.height > 1) {
      toast.error("裁切框超出图片边界");
      return;
    }
    const payload: CropParams = {
      x: crop.x,
      y: crop.y,
      width: crop.width,
      height: crop.height,
      target_width: size,
      target_height: size,
      force_fail: forceFail,
    };
    setSubmitting(true);
    try {
      const job = await coverApi.enqueue(character.id, versionId, sourceId, payload);
      toast.success("封面任务已入队，参数与原图已绑定");
      setJobs((list) => (list.some((j) => j.id === job.id) ? list : [job, ...list]));
      setTimeout(load, 500);
    } catch {
      /* toasted */
    } finally {
      setSubmitting(false);
    }
  };

  const runNow = async () => {
    try {
      const r = await coverApi.process();
      toast.success(`已同步处理 ${r.processed} 个任务`);
      load();
    } catch {
      /* admin only */
    }
  };

  return (
    <Card>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-bold text-slate-800">封面派生任务</h3>
          <p className="mt-0.5 text-xs text-slate-400">
            任务绑定「原图 + 裁切参数」；重复请求幂等去重，旧任务晚到不会覆盖新角色卡。
          </p>
        </div>
        {isAdmin && (
          <Button size="sm" variant="secondary" onClick={runNow}>
            立即执行队列（管理员）
          </Button>
        )}
      </div>

      {canEdit && (
        <div className="mb-5 grid gap-4 rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-100 lg:grid-cols-[1fr_1.4fr_auto]">
          <div className="space-y-3">
            <Field label="目标版本">
              <Select value={versionId} onChange={(e) => setVersionId(e.target.value)}>
                {character.versions
                  .slice()
                  .sort((a, b) => b.version_no - a.version_no)
                  .map((v) => (
                    <option key={v.id} value={v.id}>
                      v{v.version_no}
                      {v.id === character.current_version_id ? "（最新）" : ""}
                    </option>
                  ))}
              </Select>
            </Field>
            <Field label="来源原图（必须已授权）">
              <Select value={sourceId} onChange={(e) => setSourceId(e.target.value)}>
                <option value="">请选择…</option>
                {images.map((img) => (
                  <option key={img.id} value={img.id} disabled={img.license_status === "revoked"}>
                    {img.filename}
                    {img.license_status === "revoked" ? "（授权已撤销）" : ` · ${img.width}×${img.height}`}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="输出尺寸">
              <Select value={size} onChange={(e) => setSize(Number(e.target.value))}>
                {[512, 768, 1024, 2048].map((s) => (
                  <option key={s} value={s}>
                    {s} × {s}
                  </option>
                ))}
              </Select>
            </Field>
            <label className="flex items-center gap-2 text-xs text-slate-500">
              <input
                type="checkbox"
                checked={forceFail}
                onChange={(e) => setForceFail(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-primary"
              />
              模拟素材生成失败（验收用）
            </label>
          </div>

          <div>
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
              裁切区域（相对比例 0–1）
            </p>
            {selectedSource ? (
              <div className="relative overflow-hidden rounded-xl bg-slate-200 ring-1 ring-slate-200">
                <img
                  src={selectedSource.url}
                  alt={selectedSource.filename}
                  className="block max-h-56 w-full object-contain"
                />
                <div
                  className="absolute border-2 border-white bg-primary/25 shadow-[0_0_0_9999px_rgba(15,23,42,0.25)]"
                  style={{
                    left: `${crop.x * 100}%`,
                    top: `${crop.y * 100}%`,
                    width: `${crop.width * 100}%`,
                    height: `${crop.height * 100}%`,
                  }}
                />
              </div>
            ) : (
              <div className="flex h-40 items-center justify-center rounded-xl border-2 border-dashed border-slate-200 text-xs text-slate-400">
                选择来源图后可预览裁切框
              </div>
            )}
            <div className="mt-2 grid grid-cols-4 gap-2">
              {(
                [
                  ["x", "起点X"],
                  ["y", "起点Y"],
                  ["width", "宽"],
                  ["height", "高"],
                ] as const
              ).map(([key, label]) => (
                <label key={key} className="text-[11px] text-slate-500">
                  {label}
                  <input
                    type="number"
                    step={0.05}
                    min={0}
                    max={1}
                    value={crop[key]}
                    onChange={(e) => setCrop({ ...crop, [key]: Number(e.target.value) })}
                    className="mt-1 w-full rounded-lg border-0 bg-white px-2 py-1 text-xs ring-1 ring-slate-200 focus:ring-primary"
                  />
                </label>
              ))}
            </div>
          </div>

          <div className="flex items-end">
            <Button loading={submitting} onClick={enqueue} className="w-full lg:w-auto">
              入队生成
            </Button>
          </div>
        </div>
      )}

      <div className="space-y-2">
        {jobs.length === 0 && <p className="py-4 text-center text-xs text-slate-400">暂无任务记录</p>}
        {jobs.map((job) => (
          <div
            key={job.id}
            className="flex flex-wrap items-center gap-3 rounded-xl bg-white p-3 ring-1 ring-slate-100"
          >
            {job.result_url ? (
              <img src={job.result_url} alt="cover" className="h-12 w-12 rounded-lg object-cover ring-1 ring-slate-200" />
            ) : (
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-slate-100 text-lg">
                {job.status === "failed" ? "⚠️" : job.status === "stale" ? "🕓" : "🎞"}
              </div>
            )}
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <Badge tone={statusTone[job.status]}>{statusLabel[job.status]}</Badge>
                <span className="text-[11px] text-slate-400">尝试 {job.attempts} 次</span>
              </div>
              <p className="mt-1 truncate font-mono text-[11px] text-slate-400">
                x{cropFmt(job)}-s{job.source_image_id.slice(0, 6)}
              </p>
              {job.error_message && (
                <p className="mt-0.5 text-[11px] text-red-600">{job.error_message}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
};

function cropFmt(job: CoverJob) {
  const c = job.crop_params;
  return `${c.x},${c.y} ${c.width}×${c.height} ${c.target_width}px`;
}

export default CoverJobsPanel;
