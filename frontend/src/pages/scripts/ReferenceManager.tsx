import { useState } from "react";
import toast from "react-hot-toast";
import { scriptApi } from "@/api";
import type { Character, Script } from "@/types";
import { Badge, Button, Select } from "@/components/ui";

interface Props {
  script: Script;
  characters: Character[];
  canEdit: boolean;
  onChanged: (s: Script) => void;
}

const ReferenceManager = ({ script, characters, canEdit, onChanged }: Props) => {
  const activeChars = characters.filter((c) => c.status === "active");
  const existingIds = new Set(script.characters.map((c) => c.character_id));
  const [characterId, setCharacterId] = useState("");
  const [pinMode, setPinMode] = useState<"pinned" | "latest">("latest");
  const [versionId, setVersionId] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  const picked = characters.find((c) => c.id === characterId);

  const add = async () => {
    if (!characterId) {
      toast.error("请先选择角色");
      return;
    }
    if (pinMode === "pinned" && !versionId) {
      toast.error("固定模式必须选择具体版本");
      return;
    }
    setBusyId("add");
    try {
      const updated = await scriptApi.addCharacter(script.id, {
        character_id: characterId,
        pin_mode: pinMode,
        pinned_version_id: pinMode === "pinned" ? versionId : null,
      });
      toast.success(pinMode === "pinned" ? "已固定到所选版本" : "已设置为跟随最新版");
      onChanged(updated);
      setCharacterId("");
      setVersionId("");
    } catch {
      /* toasted */
    } finally {
      setBusyId(null);
    }
  };

  const changeMode = async (
    refId: string,
    charId: string,
    mode: "pinned" | "latest",
    pinned: string | null,
  ) => {
    setBusyId(refId);
    try {
      onChanged(await scriptApi.updateCharacter(script.id, refId, {
        character_id: charId,
        pin_mode: mode,
        pinned_version_id: mode === "pinned" ? pinned : null,
      }));
      toast.success("引用方式已更新");
    } catch {
      /* toasted */
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (refId: string) => {
    setBusyId(refId);
    try {
      onChanged(await scriptApi.removeCharacter(script.id, refId));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        {script.characters.length === 0 && (
          <p className="rounded-xl bg-slate-50 px-3 py-4 text-center text-xs text-slate-400">
            剧本尚未引用任何角色
          </p>
        )}
        {script.characters.map((ref) => {
          const ch = characters.find((c) => c.id === ref.character_id);
          const versions = (ch?.versions ?? []).slice().sort((a, b) => b.version_no - a.version_no);
          return (
            <div
              key={ref.id}
              className={
                "flex flex-wrap items-center gap-3 rounded-xl p-3 ring-1 " +
                (ref.pin_mode === "pinned" ? "bg-violet-50/60 ring-violet-100" : "bg-blue-50/50 ring-blue-100")
              }
            >
              <div className="min-w-[120px] flex-1">
                <p className="text-sm font-semibold text-slate-800">
                  {ref.character_name}
                  {ch?.status === "retired" && <Badge tone="slate" className="ml-2">角色已退役</Badge>}
                </p>
                <p className="text-[11px] text-slate-400">
                  当前解析到 v{ref.resolved_version_no}
                </p>
              </div>
              <Badge tone={ref.pin_mode === "pinned" ? "violet" : "blue"}>
                {ref.pin_mode === "pinned" ? "📌 固定版本" : "🌀 跟随最新"}
              </Badge>
              {canEdit && (
                <>
                  <Select
                    className="w-32 py-1.5 text-xs"
                    value={ref.pin_mode}
                    disabled={busyId === ref.id}
                    onChange={(e) => {
                      const mode = e.target.value as "pinned" | "latest";
                      changeMode(
                        ref.id,
                        ref.character_id,
                        mode,
                        mode === "pinned"
                          ? ref.pinned_version_id ?? ch?.current_version_id ?? null
                          : null,
                      );
                    }}
                  >
                    <option value="latest">跟随最新</option>
                    <option value="pinned">固定版本</option>
                  </Select>
                  {ref.pin_mode === "pinned" && (
                    <Select
                      className="w-28 py-1.5 text-xs"
                      value={ref.pinned_version_id ?? ""}
                      disabled={busyId === ref.id}
                      onChange={(e) =>
                        changeMode(ref.id, ref.character_id, "pinned", e.target.value)
                      }
                    >
                      {versions.map((v) => (
                        <option key={v.id} value={v.id}>
                          v{v.version_no}
                        </option>
                      ))}
                    </Select>
                  )}
                  <Button size="sm" variant="ghost" disabled={busyId === ref.id} onClick={() => remove(ref.id)}>
                    移除
                  </Button>
                </>
              )}
            </div>
          );
        })}
      </div>

      {canEdit && (
        <div className="flex flex-wrap items-end gap-2 rounded-xl bg-slate-50 p-3 ring-1 ring-slate-100">
          <Select
            className="w-44 text-xs"
            value={characterId}
            onChange={(e) => {
              setCharacterId(e.target.value);
              const c = characters.find((x) => x.id === e.target.value);
              setVersionId(c?.current_version_id ?? "");
            }}
          >
            <option value="">选择角色…</option>
            {activeChars.filter((c) => !existingIds.has(c.id)).map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
          <Select
            className="w-32 text-xs"
            value={pinMode}
            onChange={(e) => setPinMode(e.target.value as "pinned" | "latest")}
          >
            <option value="latest">跟随最新版</option>
            <option value="pinned">固定某版本</option>
          </Select>
          {pinMode === "pinned" && (
            <Select className="w-28 text-xs" value={versionId} onChange={(e) => setVersionId(e.target.value)}>
              {(picked?.versions ?? [])
                .slice()
                .sort((a, b) => b.version_no - a.version_no)
                .map((v) => (
                  <option key={v.id} value={v.id}>
                    v{v.version_no}
                  </option>
                ))}
            </Select>
          )}
          <Button size="sm" loading={busyId === "add"} onClick={add} disabled={!characterId}>
            添加引用
          </Button>
        </div>
      )}
    </div>
  );
};

export default ReferenceManager;
