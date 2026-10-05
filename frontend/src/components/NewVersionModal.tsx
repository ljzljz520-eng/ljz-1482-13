import { useState } from "react";
import toast from "react-hot-toast";
import { appendVersion, uploadImage } from "../api/endpoints";
import type { Character } from "../types";
import { Badge, Button, Field, Modal, inputCls } from "./ui";

export default function NewVersionModal({
  character,
  onClose,
  onCreated,
}: {
  character: Character;
  onClose: () => void;
  onCreated: () => void;
}) {
  const latest = character.versions?.[0] ?? character.latest;
  const [appearance, setAppearance] = useState(latest?.appearance ?? "");
  const [tone, setTone] = useState(latest?.tone ?? "");
  const [restrictions, setRestrictions] = useState(latest?.restrictions ?? "");
  const [note, setNote] = useState("");
  const [picked, setPicked] = useState<string[]>(
    latest?.images.map((i) => i.image_asset_id) ?? []
  );
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);

  // 候选图：当前版本参考图
  const candidates = latest?.images ?? [];
  const candidateMap = new Map(candidates.map((i) => [i.image_asset_id, i]));

  const toggle = (id: string) =>
    setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));

  const onUpload = async (file: File | undefined) => {
    if (!file) return;
    setUploading(true);
    try {
      const asset = await uploadImage(file, "新版本参考图");
      // 上传后刷新父数据拿不到 asset 的图片关联，直接让用户在上传成功后提示；
      // 该新图可在图片库授权，随后在再次打开弹窗时由版本数据携带。这里直接把新图加入 picked，
      // 后端按 asset id 绑定，无需 ReferenceImage 预存在。
      toast.success(`已上传 ${asset.original_filename}，已自动勾选绑定到新版本`);
      setPicked((p) => [...p, asset.id]);
      onUploadedAsset(asset);
    } catch (e) {
      toast.error((e as { friendlyMessage?: string }).friendlyMessage ?? "上传失败");
    } finally {
      setUploading(false);
    }
  };

  const [extraAssets, setExtraAssets] = useState<
    { id: string; url: string; name: string }[]
  >([]);
  const onUploadedAsset = (a: { id: string; url: string; original_filename: string }) => {
    setExtraAssets((list) => [...list, { id: a.id, url: a.url, name: a.original_filename }]);
  };

  const submit = async () => {
    setSaving(true);
    try {
      await appendVersion(character.id, {
        appearance,
        tone,
        restrictions,
        change_note: note || `第 ${character.latest_version + 1} 版`,
        image_asset_ids: picked,
        expected_lock_version: character.lock_version,
      });
      toast.success(`v${character.latest_version + 1} 已发布（旧版本不可变）`);
      onCreated();
    } catch (e) {
      toast.error((e as { friendlyMessage?: string }).friendlyMessage ?? "提交失败，请处理冲突后重试");
      onClose();
      onCreated();
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open
      wide
      onClose={onClose}
      title={`发布新版本（当前 v${character.latest_version} → v${character.latest_version + 1}）`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            取消
          </Button>
          <Button loading={saving} onClick={submit}>
            追加新版本
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="rounded-xl bg-blue-50 px-3 py-2 text-xs leading-5 text-blue-700">
          乐观锁校验：基于 lock_version={character.lock_version} 提交。若期间他人已修改，服务端会拒绝并生成冲突复核项。
        </div>
        <Field label="外观设定">
          <textarea className={inputCls} rows={3} value={appearance} onChange={(e) => setAppearance(e.target.value)} />
        </Field>
        <Field label="语气风格">
          <textarea className={inputCls} rows={2} value={tone} onChange={(e) => setTone(e.target.value)} />
        </Field>
        <Field label="限制词 / 红线">
          <textarea className={inputCls} rows={2} value={restrictions} onChange={(e) => setRestrictions(e.target.value)} />
        </Field>
        <Field label="版本变更说明">
          <input className={inputCls} value={note} onChange={(e) => setNote(e.target.value)} placeholder="如：第二幕造型升级" />
        </Field>

        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-medium text-slate-700">参考图（绑定到这个不可变版本）</span>
            <label className="cursor-pointer rounded-lg border border-dashed border-slate-300 px-3 py-1.5 text-xs text-slate-500 transition hover:border-blue-400 hover:text-blue-600">
              {uploading ? "上传中…" : "＋ 上传新参考图"}
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                className="hidden"
                onChange={(e) => onUpload(e.target.files?.[0])}
              />
            </label>
          </div>
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
            {candidates.map((img) => {
              const active = picked.includes(img.image_asset_id);
              return (
                <button
                  key={img.image_asset_id}
                  type="button"
                  onClick={() => !img.license_granted ? toast.error("该图授权已撤销，不能绑定") : toggle(img.image_asset_id)}
                  className={`relative aspect-square overflow-hidden rounded-xl ring-2 transition ${
                    active ? "ring-blue-500" : "ring-transparent hover:ring-slate-300"
                  } ${!img.license_granted ? "opacity-40 grayscale" : ""}`}
                >
                  <img src={img.url} alt={img.caption} className="h-full w-full object-cover" />
                  {active && (
                    <span className="absolute right-1 top-1 rounded-full bg-blue-600 px-1.5 text-[10px] text-white">
                      ✓
                    </span>
                  )}
                  {!img.license_granted && <Badge tone="red" className="absolute bottom-1 left-1">授权撤销</Badge>}
                </button>
              );
            })}
            {extraAssets.map((a) => {
              const active = picked.includes(a.id);
              return (
                <button
                  key={a.id}
                  type="button"
                  onClick={() => toggle(a.id)}
                  className={`relative aspect-square overflow-hidden rounded-xl ring-2 ${
                    active ? "ring-blue-500" : "ring-slate-300"
                  }`}
                  title={a.name}
                >
                  <img src={a.url} alt={a.name} className="h-full w-full object-cover" />
                  <span className="absolute right-1 top-1 rounded-full bg-emerald-600 px-1.5 text-[10px] text-white">新</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </Modal>
  );
}
