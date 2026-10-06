import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { characterApi } from "@/api";
import type { Character, References } from "@/types";
import { Badge, Button } from "@/components/ui";

const RefRow = ({
  label,
  group,
  tone,
}: {
  label: string;
  group: { count: number; items: any[] };
  tone: "blue" | "violet" | "green" | "amber" | "red" | "slate";
}) => (
  <div className="rounded-xl bg-slate-50 p-3 ring-1 ring-slate-100">
    <div className="flex items-center justify-between">
      <span className="text-xs font-medium text-slate-600">{label}</span>
      <Badge tone={group.count > 0 ? tone : "slate"}>{group.count}</Badge>
    </div>
    {group.items.length > 0 && (
      <ul className="mt-2 space-y-1 text-[11px] text-slate-500">
        {group.items.slice(0, 4).map((it, i) => (
          <li key={i} className="truncate">
            {it.script_title || it.scene_code || it.job_id?.slice(0, 8) || it.export_id?.slice(0, 8) ||
              it.asset_id?.slice(0, 8) || JSON.stringify(it).slice(0, 60)}
          </li>
        ))}
        {group.items.length > 4 && <li>… 其余 {group.items.length - 4} 项</li>}
      </ul>
    )}
  </div>
);

const RetireDialog = ({
  character,
  alternatives,
  onClose,
}: {
  character: Character;
  alternatives: Character[];
  onClose: () => void;
}) => {
  const navigate = useNavigate();
  const [refs, setRefs] = useState<References | null>(null);
  const [loading, setLoading] = useState(true);
  const [strategy, setStrategy] = useState<"soft_delete" | "replace">("soft_delete");
  const [replacementId, setReplacementId] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      setRefs(await characterApi.references(character.id));
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load();
  }, [character.id]);

  const confirm = async () => {
    if (!refs) return;
    if (strategy === "replace" && !replacementId) {
      toast.error("请选择替换角色");
      return;
    }
    setSubmitting(true);
    try {
      const r = await characterApi.retire(character.id, {
        strategy,
        expected_ref_count: refs.total,
        replacement_character_id: strategy === "replace" ? replacementId : null,
      });
      toast.success(
        strategy === "soft_delete"
          ? "角色已软删除退役，全部历史引用保留，已生成复核项"
          : `退役完成：迁移 ${r.migrated_script_refs} 个脚本引用，受影响台词已标记复核`,
      );
      onClose();
      if (strategy === "replace" && replacementId) navigate(`/characters/${replacementId}`);
      else navigate("/characters");
    } catch {
      /* 409 etc toasted; refresh precheck for the conflict case */
      load();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-sm">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-3xl bg-white p-6 shadow-xl animate-fade-up">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h3 className="text-lg font-bold text-slate-900">退役角色 · {character.name}</h3>
            <p className="mt-1 text-xs text-slate-500">
              系统已查询脚本、生成素材、导出快照的实际反向引用；提交时服务端会重新加锁校验，
              防止退役期间他人新增引用。
            </p>
          </div>
          <button onClick={onClose} className="rounded-full p-2 text-slate-400 hover:bg-slate-100">
            ✕
          </button>
        </div>

        {loading || !refs ? (
          <div className="h-48 animate-pulse rounded-2xl bg-slate-100" />
        ) : (
          <>
            <div className="mb-4 flex items-center gap-2 rounded-xl bg-blue-50 px-3 py-2 text-xs text-blue-700 ring-1 ring-blue-100">
              <span>🔎 当前实际反向引用总数</span>
              <strong>{refs.total}</strong>
              <span className="text-blue-400">（提交时再次校验，不一致将拒绝）</span>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <RefRow label="脚本固定引用（pinned）" group={refs.pinned_script_refs} tone="violet" />
              <div className="rounded-xl bg-slate-50 p-3 ring-1 ring-slate-100">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-slate-600">脚本跟随最新引用</span>
                  <Badge tone={refs.floating_script_refs > 0 ? "blue" : "slate"}>
                    {refs.floating_script_refs}
                  </Badge>
                </div>
              </div>
              <RefRow label="已批准台词（冻结解释）" group={refs.approved_lines} tone="amber" />
              <RefRow label="待批准台词" group={refs.pending_lines} tone="slate" />
              <RefRow label="封面任务" group={refs.cover_jobs} tone="blue" />
              <RefRow label="生成素材" group={refs.generated_assets} tone="slate" />
              <div className="sm:col-span-2">
                <RefRow label="历史导出快照（对象必须保留）" group={refs.export_snapshots} tone="red" />
              </div>
            </div>

            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              <StrategyCard
                active={strategy === "soft_delete"}
                title="软删除保留引用"
                desc="角色标记退役、只读；脚本与历史导出继续可读，相关场次进入待复核。任何新增引用都会被拒绝。"
                onClick={() => setStrategy("soft_delete")}
              />
              <StrategyCard
                active={strategy === "replace"}
                title="替换后退役"
                desc="脚本引用迁移到替换角色的最新版（固定引用重新固定到该版本），台词保留并强制复核。"
                onClick={() => setStrategy("replace")}
              />
            </div>

            {strategy === "replace" && (
              <select
                value={replacementId}
                onChange={(e) => setReplacementId(e.target.value)}
                className="mt-3 w-full rounded-xl bg-slate-50 px-3 py-2 text-sm ring-1 ring-slate-200 focus:ring-primary"
              >
                <option value="">选择替换角色…</option>
                {alternatives
                  .filter((c) => c.id !== character.id && c.status === "active")
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}（v{c.current_version_no}）
                    </option>
                  ))}
              </select>
            )}

            <div className="mt-6 flex justify-end gap-2">
              <Button variant="ghost" onClick={onClose}>
                取消
              </Button>
              <Button variant="danger" loading={submitting} onClick={confirm}>
                {strategy === "soft_delete" ? "确认软删除退役" : "确认替换并退役"}
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

const StrategyCard = ({
  active,
  title,
  desc,
  onClick,
}: {
  active: boolean;
  title: string;
  desc: string;
  onClick: () => void;
}) => (
  <button
    type="button"
    onClick={onClick}
    className={
      "rounded-2xl p-4 text-left ring-2 transition " +
      (active ? "bg-primary/5 ring-primary" : "bg-white ring-slate-200 hover:ring-slate-300")
    }
  >
    <p className="text-sm font-semibold text-slate-800">{title}</p>
    <p className="mt-1 text-xs leading-relaxed text-slate-500">{desc}</p>
  </button>
);

export default RetireDialog;
