import { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import {
  createCoverJob,
  listCharacterCoverJobs,
  retryCoverJob,
  uploadImage,
} from "../api/endpoints";
import type { Character, CoverJob, ImageAsset } from "../types";
import { usePolling } from "../hooks/usePolling";
import { useMotionAllowed } from "../hooks/useMotionAllowed";
import { useRef } from "react";
import { Badge, Button, Field, inputCls } from "./ui";

const stateMeta: Record<CoverJob["state"], { label: string; tone: "slate" | "blue" | "amber" | "green" | "red" | "violet" }> = {
  pending: { label: "排队中", tone: "slate" },
  processing: { label: "处理中", tone: "blue" },
  succeeded: { label: "已完成", tone: "green" },
  failed: { label: "失败", tone: "red" },
  stale: { label: "旧任务·已归档", tone: "violet" },
  cancelled: { label: "已取消", tone: "slate" },
};

export default function CoverJobPanel({ character }: { character: Character }) {
  const version = character.versions?.[0];
  const [jobs, setJobs] = useState<CoverJob[]>([]);
  const [source, setSource] = useState<ImageAsset | null>(null);
  const [uploading, setUploading] = useState(false);
  const [crop, setCrop] = useState({ x: 0.08, y: 0.1, w: 0.84, h: 0.78 });
  const [size, setSize] = useState({ w: 640, h: 360 });
  const [forceFail, setForceFail] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const latestVersionImages = version?.images ?? [];

  const load = async () => {
    if (!character.id) return;
    try {
      setJobs(await listCharacterCoverJobs(character.id));
    } catch {
      /* 列表静默，操作类报错提示 */
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [character.id]);

  const active = jobs.some((j) => j.state === "pending" || j.state === "processing");
  usePolling(load, 2500, active);

  const onUpload = async (file: File | undefined) => {
    if (!file) return;
    setUploading(true);
    try {
      const asset = await uploadImage(file, "封面来源图（页面上传）");
      setSource(asset);
      toast.success("来源图已上传");
    } catch (e) {
      toast.error((e as { friendlyMessage?: string }).friendlyMessage ?? "上传失败");
    } finally {
      setUploading(false);
    }
  };

  const submit = async () => {
    if (!version) return;
    if (!source) {
      toast.error("请先选择或上传来源图");
      return;
    }
    setSubmitting(true);
    try {
      await createCoverJob({
        character_version_id: version.id,
        source_asset_id: source.id,
        crop_x: crop.x,
        crop_y: crop.y,
        crop_w: crop.w,
        crop_h: crop.h,
        target_width: size.w,
        target_height: size.h,
        force_fail: forceFail,
      });
      toast.success("封面派生任务已入队（异步执行）");
      await load();
    } catch (e) {
      toast.error((e as { friendlyMessage?: string }).friendlyMessage ?? "创建任务失败");
    } finally {
      setSubmitting(false);
    }
  };

  const previewSrc = source?.url ?? latestVersionImages[0]?.url;

  return (
    <div className="space-y-5">
      <div className="grid gap-5 lg:grid-cols-2">
        {/* 左：裁切参数 */}
        <div className="space-y-4">
          <Field label="来源图（任务绑定该原图，授权撤销后任务中止）">
            <div className="flex flex-wrap items-center gap-2">
              {latestVersionImages.map((img) => (
                <button
                  key={img.image_asset_id}
                  onClick={() =>
                    setSource({
                      id: img.image_asset_id,
                      url: img.url,
                      original_filename: img.caption,
                      width: img.width,
                      height: img.height,
                      license_granted: img.license_granted,
                      license_note: img.license_note,
                      created_at: "",
                    })
                  }
                  className={`h-14 w-14 overflow-hidden rounded-lg ring-2 transition ${
                    source?.id === img.image_asset_id ? "ring-blue-500" : "ring-transparent hover:ring-slate-300"
                  } ${!img.license_granted ? "opacity-40 grayscale" : ""}`}
                  title={img.license_granted ? img.caption : "授权已撤销"}
                >
                  <img src={img.url} alt={img.caption} className="h-full w-full object-cover" />
                </button>
              ))}
              <label className="flex h-14 cursor-pointer items-center gap-1 rounded-lg border border-dashed border-slate-300 px-3 text-xs text-slate-500 transition hover:border-blue-400 hover:text-blue-600">
                {uploading ? "上传中…" : "＋ 上传新图"}
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  className="hidden"
                  onChange={(e) => onUpload(e.target.files?.[0])}
                />
              </label>
            </div>
          </Field>

          <div className="relative overflow-hidden rounded-xl border border-slate-200 bg-slate-100">
            {previewSrc ? (
              <div className="relative">
                <img src={previewSrc} alt="裁切预览" className="w-full" />
                <div
                  className="pointer-events-none absolute border-2 border-white/90 shadow-[0_0_0_9999px_rgba(15,23,42,0.35)]"
                  style={{
                    left: `${crop.x * 100}%`,
                    top: `${crop.y * 100}%`,
                    width: `${crop.w * 100}%`,
                    height: `${crop.h * 100}%`,
                  }}
                />
              </div>
            ) : (
              <p className="py-10 text-center text-sm text-slate-400">请选择来源图</p>
            )}
          </div>

          <div className="grid grid-cols-4 gap-3">
            {(
              [
                ["x", "起点 X"],
                ["y", "起点 Y"],
                ["w", "宽度 W"],
                ["h", "高度 H"],
              ] as const
            ).map(([key, label]) => (
              <Field key={key} label={label}>
                <input
                  type="number"
                  step={0.01}
                  min={0}
                  max={1}
                  className={inputCls}
                  value={crop[key]}
                  onChange={(e) => {
                    const v = Number(e.target.value);
                    setCrop((c) => ({
                      ...c,
                      [key]: Math.max(0, Math.min(1, v)),
                    }));
                  }}
                />
              </Field>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="目标宽 px">
              <input
                type="number"
                className={inputCls}
                value={size.w}
                onChange={(e) => setSize((s) => ({ ...s, w: Number(e.target.value) }))}
              />
            </Field>
            <Field label="目标高 px">
              <input
                type="number"
                className={inputCls}
                value={size.h}
                onChange={(e) => setSize((s) => ({ ...s, h: Number(e.target.value) }))}
              />
            </Field>
          </div>
          <label className="flex items-center gap-2 rounded-xl bg-rose-50 px-3 py-2 text-sm text-rose-700">
            <input type="checkbox" checked={forceFail} onChange={(e) => setForceFail(e.target.checked)} />
            模拟素材生成失败（验收用：失败会进入复核队列）
          </label>
          <Button onClick={submit} loading={submitting} disabled={!version}>
            为 v{version?.version} 创建封面派生任务
          </Button>
        </div>

        {/* 右：任务列表 */}
        <div>
          <p className="mb-2 text-sm font-semibold text-slate-700">任务队列（绑定版本 / 原图 / 裁切指纹）</p>
          <div className="space-y-2">
            {jobs.length === 0 && <p className="rounded-xl bg-slate-50 px-3 py-6 text-center text-sm text-slate-400">暂无任务</p>}
            {jobs.map((j) => (
              <JobRow key={j.id} job={j} onChanged={load} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function JobRow({ job, onChanged }: { job: CoverJob; onChanged: () => void }) {
  const meta = stateMeta[job.state];
  const imgRef = useRef<HTMLDivElement>(null);
  const animate = useMotionAllowed(imgRef);
  const busy = job.state === "processing" || job.state === "pending";

  const fingerprintShort = useMemo(() => job.params_fingerprint.slice(0, 10), [job.params_fingerprint]);

  return (
    <div className="rounded-xl border border-slate-200 p-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Badge tone={meta.tone}>{busy && animate ? <span className="h-2 w-2 animate-pulse rounded-full bg-current" /> : null}{meta.label}</Badge>
          <span className="font-mono text-xs text-slate-400">fp:{fingerprintShort}</span>
        </div>
        {(job.state === "failed" || job.state === "stale") && (
          <Button size="sm" variant="secondary" onClick={() => retryCoverJob(job.id).then(onChanged)}>
            重试
          </Button>
        )}
      </div>
      <p className="mt-1.5 font-mono text-[11px] leading-4 text-slate-400">
        crop=({job.crop_x},{job.crop_y},{job.crop_w},{job.crop_h}) · {job.target_width}×{job.target_height}
      </p>
      <div className="mt-2 flex items-center gap-3">
        <div ref={imgRef} className="h-14 w-24 shrink-0 overflow-hidden rounded-lg bg-slate-100">
          {job.output_url ? (
            <img
              src={job.output_url}
              alt="封面结果"
              className={`h-full w-full object-cover ${busy && animate ? "cs-pulse-cover" : ""} ${
                job.state === "stale" ? "opacity-50 saturate-50" : ""
              }`}
            />
          ) : busy ? (
            <div className={`flex h-full w-full items-center justify-center text-xs text-slate-400 ${animate ? "cs-shimmer" : ""}`}>
              渲染中…
            </div>
          ) : (
            <div className="flex h-full w-full items-center justify-center text-xs text-slate-300">无产物</div>
          )}
        </div>
        <div className="min-w-0 flex-1">
          {job.last_error && (
            <p className="rounded-lg bg-rose-50 px-2 py-1 text-xs leading-5 text-rose-600">{job.last_error}</p>
          )}
          {job.state === "stale" && (
            <p className="text-xs leading-5 text-violet-600">
              旧任务晚到：结果仅归档，不会覆盖当前角色卡封面。
            </p>
          )}
          <p className="mt-0.5 text-[11px] text-slate-400">尝试 {job.attempts} 次</p>
        </div>
      </div>
    </div>
  );
}
