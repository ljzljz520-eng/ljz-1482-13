import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { dryRunRetire, listCharacters, retireCharacter } from "../api/endpoints";
import type { Character, RetireDryRun } from "../types";
import { Badge, Button, inputCls } from "./ui";

export default function RetireFlow({
  character,
  onDone,
  onClose,
}: {
  character: Character;
  onDone: (c: Character) => void;
  onClose: () => void;
}) {
  const [mode, setMode] = useState<"soft_delete" | "retire">("soft_delete");
  const [dry, setDry] = useState<RetireDryRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [replacements, setReplacements] = useState<Character[]>([]);
  const [replacementId, setReplacementId] = useState<string>("");

  const loadDry = async (m: "soft_delete" | "retire") => {
    setLoading(true);
    try {
      setDry(await dryRunRetire(character.id, m));
    } catch (e) {
      toast.error((e as { friendlyMessage?: string }).friendlyMessage ?? "引用查询失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDry(mode);
    listCharacters(false).then(setReplacements).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  const submit = async () => {
    setSubmitting(true);
    try {
      const updated = await retireCharacter(character.id, {
        expected_lock_version: character.lock_version,
        replacement_character_id: mode === "retire" && replacementId ? replacementId : null,
        mode,
      });
      toast.success(
        mode === "soft_delete"
          ? "已软删除：全部反向引用与历史版本保留"
          : replacementId
            ? "引用已迁移到替代角色，角色已退役"
            : "角色已退役"
      );
      onDone(updated);
    } catch (e) {
      toast.error((e as { friendlyMessage?: string }).friendlyMessage ?? "退役失败");
      loadDry(mode);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <button
          onClick={() => setMode("soft_delete")}
          className={`rounded-2xl border p-4 text-left transition ${
            mode === "soft_delete"
              ? "border-amber-400 bg-amber-50 ring-2 ring-amber-100"
              : "border-slate-200 hover:border-slate-300"
          }`}
        >
          <p className="font-semibold text-slate-800">软删除（保留引用）</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            角色从默认列表隐藏，但脚本引用、素材、历史导出全部可解析，可随时恢复。
          </p>
        </button>
        <button
          onClick={() => setMode("retire")}
          className={`rounded-2xl border p-4 text-left transition ${
            mode === "retire"
              ? "border-rose-400 bg-rose-50 ring-2 ring-rose-100"
              : "border-slate-200 hover:border-slate-300"
          }`}
        >
          <p className="font-semibold text-slate-800">替换后退役</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            先把脚本引用迁移到替代角色（已批准台词需重新确认），再将本角色退役。
          </p>
        </button>
      </div>

      {loading ? (
        <div className="py-6 text-center text-sm text-slate-400">正在查询真实反向引用…</div>
      ) : dry ? (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="脚本引用" value={dry.blocking_scripts.length} tone="blue" />
            <Stat label="固定 / 跟随" value={`${dry.pinned_links} / ${dry.floating_links}`} />
            <Stat label="生成素材" value={dry.generated_assets} />
            <Stat label="历史导出" value={dry.export_snapshots} tone="violet" />
          </div>

          {dry.blocking_scripts.length > 0 && (
            <div className="rounded-xl border border-slate-200">
              <p className="border-b border-slate-100 px-3 py-2 text-xs font-semibold text-slate-500">
                被引用的场次
              </p>
              <ul className="divide-y divide-slate-100">
                {dry.blocking_scripts.map((s) => (
                  <li key={s.script_id + s.ref_mode} className="flex items-center justify-between px-3 py-2 text-sm">
                    <span className="text-slate-700">
                      <span className="mr-2 font-mono text-xs text-slate-400">{s.scene_code}</span>
                      {s.title}
                    </span>
                    {s.ref_mode === "pinned" ? (
                      <Badge tone="blue">📌 固定 v{s.pinned_version}</Badge>
                    ) : (
                      <Badge tone="violet">🔄 跟随最新 v{s.latest_version}</Badge>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <p className="rounded-xl bg-slate-50 px-3 py-2.5 text-xs leading-6 text-slate-500">
            {dry.recommendation}
          </p>

          {mode === "retire" && dry.blocking_scripts.length > 0 && (
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-slate-700">
                替代角色（有引用时必选）
              </span>
              <select
                className={inputCls}
                value={replacementId}
                onChange={(e) => setReplacementId(e.target.value)}
              >
                <option value="">— 请选择替代角色 —</option>
                {replacements
                  .filter((c) => c.id !== character.id)
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}（{c.code} · 最新 v{c.latest_version}）
                    </option>
                  ))}
              </select>
            </label>
          )}
        </div>
      ) : null}

      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>
          取消
        </Button>
        <Button
          variant={mode === "soft_delete" ? "secondary" : "danger"}
          loading={submitting}
          disabled={mode === "retire" && (dry?.blocking_scripts.length ?? 0) > 0 && !replacementId}
          onClick={submit}
        >
          {mode === "soft_delete" ? "确认软删除" : "迁移引用并退役"}
        </Button>
      </div>
    </div>
  );
}

function Stat({ label, value, tone = "slate" }: { label: string; value: string | number; tone?: "slate" | "blue" | "violet" }) {
  const bg = {
    slate: "bg-slate-50 text-slate-700",
    blue: "bg-blue-50 text-blue-700",
    violet: "bg-violet-50 text-violet-700",
  }[tone];
  return (
    <div className={`rounded-xl px-3 py-2.5 ${bg}`}>
      <p className="text-lg font-bold leading-tight">{value}</p>
      <p className="text-xs opacity-70">{label}</p>
    </div>
  );
}
