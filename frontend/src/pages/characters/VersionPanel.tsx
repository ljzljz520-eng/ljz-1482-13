import { useState } from "react";
import toast from "react-hot-toast";
import { characterApi } from "@/api";
import type { Character, CharacterVersion } from "@/types";
import { Badge, Button, Card, Textarea } from "@/components/ui";

interface Props {
  version: CharacterVersion;
  current: boolean;
  character: Character;
}

export const VersionContent = ({ version, current }: Props) => (
  <div className="space-y-4">
    <div className="flex flex-wrap items-center gap-2">
      <Badge tone={current ? "green" : "slate"}>
        {current ? "当前最新版" : "历史版本"}
      </Badge>
      <span className="text-sm font-semibold text-slate-800">v{version.version_no}</span>
      {version.change_note && <span className="text-xs text-slate-400">· {version.change_note}</span>}
    </div>
    <div className="grid gap-3 md:grid-cols-3">
      <InfoBlock label="外观" value={version.appearance} />
      <InfoBlock label="语气" value={version.tone} />
      <InfoBlock label="限制词" value={version.restrictions} danger />
    </div>
    {version.images.length > 0 && (
      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
          绑定参考图
        </p>
        <div className="flex flex-wrap gap-2">
          {version.images.map((img) => (
            <div key={img.id} className="relative">
              <img
                src={img.url}
                alt={img.filename}
                title={img.filename}
                className="h-24 w-20 rounded-lg object-cover ring-1 ring-slate-200"
              />
              {img.license_status === "revoked" && (
                <span className="absolute inset-0 flex items-end justify-center rounded-lg bg-red-900/60 pb-1 text-[10px] font-bold text-white">
                  授权撤销
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
    )}
    <p className="text-[11px] text-slate-400">
      版本一经发布不可修改；已批准台词按批准时的版本冻结解释，切换版本不会改动历史记录。
    </p>
  </div>
);

const InfoBlock = ({ label, value, danger }: { label: string; value: string; danger?: boolean }) => (
  <div className="rounded-xl bg-slate-50 p-3 ring-1 ring-slate-100">
    <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">{label}</p>
    <p className={"whitespace-pre-wrap text-sm leading-relaxed " + (danger ? "text-red-700" : "text-slate-700")}>
      {value || <span className="text-slate-300">未填写</span>}
    </p>
  </div>
);

export const PublishVersionCard = ({
  character,
  onPublished,
}: {
  character: Character;
  onPublished: (v: CharacterVersion) => void;
}) => {
  const current = character.versions.find((v) => v.id === character.current_version_id);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ appearance: "", tone: "", restrictions: "", change_note: "" });
  const [saving, setSaving] = useState(false);

  const publish = async () => {
    if (!form.appearance && !form.tone && !form.restrictions) {
      toast.error("至少修改外观 / 语气 / 限制词中的一项再发布新版本");
      return;
    }
    setSaving(true);
    try {
      const v = await characterApi.publishVersion(character.id, {
        appearance: form.appearance || current?.appearance || "",
        tone: form.tone || current?.tone || "",
        restrictions: form.restrictions || current?.restrictions || "",
        change_note: form.change_note || "未填写变更说明",
        image_ids: current?.images.map((i) => i.id) ?? [],
      });
      toast.success(`v${v.version_no} 已发布，跟随最新版的已批准台词已进入待复核`);
      setOpen(false);
      setForm({ appearance: "", tone: "", restrictions: "", change_note: "" });
      onPublished(v);
    } catch {
      /* toasted */
    } finally {
      setSaving(false);
    }
  };

  if (!open)
    return (
      <Button variant="secondary" className="w-full" onClick={() => setOpen(true)}>
        ＋ 基于 v{current?.version_no} 发布新版本
      </Button>
    );

  return (
    <Card className="border-2 border-dashed border-primary/30 bg-primary/[0.02]">
      <p className="mb-3 text-sm font-semibold text-slate-800">
        发布 v{(current?.version_no ?? 0) + 1}
      </p>
      <div className="grid gap-3 md:grid-cols-3">
        <Textarea
          placeholder="外观（留空沿用上一版）"
          value={form.appearance}
          onChange={(e) => setForm({ ...form, appearance: e.target.value })}
        />
        <Textarea
          placeholder="语气（留空沿用上一版）"
          value={form.tone}
          onChange={(e) => setForm({ ...form, tone: e.target.value })}
        />
        <Textarea
          placeholder="限制词（留空沿用上一版）"
          value={form.restrictions}
          onChange={(e) => setForm({ ...form, restrictions: e.target.value })}
        />
      </div>
      <div className="mt-3">
        <Textarea
          className="min-h-[56px]"
          placeholder="变更说明，例如：第 3 幕造型升级"
          value={form.change_note}
          onChange={(e) => setForm({ ...form, change_note: e.target.value })}
        />
      </div>
      <div className="mt-3 flex justify-end gap-2">
        <Button variant="ghost" onClick={() => setOpen(false)}>
          取消
        </Button>
        <Button loading={saving} onClick={publish}>
          确认发布
        </Button>
      </div>
    </Card>
  );
};
