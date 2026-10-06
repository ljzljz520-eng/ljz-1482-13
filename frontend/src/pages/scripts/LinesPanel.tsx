import { useState } from "react";
import toast from "react-hot-toast";
import { scriptApi } from "@/api";
import type { Character, Line, Script } from "@/types";
import { Badge, Button, Select, Textarea } from "@/components/ui";

const LinesPanel = ({
  script,
  characters,
  lines,
  canEdit,
  onChanged,
}: {
  script: Script;
  characters: Character[];
  lines: Line[];
  canEdit: boolean;
  onChanged: () => void;
}) => {
  const referencedIds = new Set(script.characters.map((c) => c.character_id));
  const [sceneId, setSceneId] = useState(script.scenes[0]?.id ?? "");
  const [characterId, setCharacterId] = useState(script.characters[0]?.character_id ?? "");
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const grouped = script.scenes.map((scene) => ({
    scene,
    lines: lines.filter((l) => l.scene_id === scene.id),
  }));

  const create = async () => {
    if (!sceneId || !characterId || !content.trim()) {
      toast.error("请选择场次、角色并填写台词");
      return;
    }
    setBusy("create");
    try {
      await scriptApi.createLine({ scene_id: sceneId, character_id: characterId, content: content.trim() });
      setContent("");
      toast.success("台词已创建（解析到该角色引用的当前版本）");
      onChanged();
    } catch {
      /* toasted */
    } finally {
      setBusy(null);
    }
  };

  const approve = async (line: Line) => {
    setBusy(line.id);
    try {
      await scriptApi.approve(line.id);
      toast.success("已批准：当前角色解释已冻结为快照");
      onChanged();
    } catch {
      /* 409 => recheck needed */
    } finally {
      setBusy(null);
    }
  };

  const reapprove = async (line: Line) => {
    setBusy(line.id);
    try {
      await scriptApi.reapprove(line.id);
      toast.success("已按最新版本重新批准，复核项已清除");
      onChanged();
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-4">
      {grouped.map(({ scene, lines: sceneLines }) => (
        <div key={scene.id} className="overflow-hidden rounded-2xl ring-1 ring-slate-100">
          <div className="flex items-center justify-between bg-slate-50 px-4 py-2.5">
            <p className="text-sm font-semibold text-slate-700">
              {scene.code} · {scene.title}
            </p>
            <span className="text-[11px] text-slate-400">{sceneLines.length} 句台词</span>
          </div>
          <div className="divide-y divide-slate-100">
            {sceneLines.length === 0 && (
              <p className="px-4 py-6 text-center text-xs text-slate-400">本场暂无台词</p>
            )}
            {sceneLines.map((line) => (
              <div key={line.id} className="flex flex-wrap gap-3 px-4 py-3">
                {line.cover_url && (
                  <img src={line.cover_url} alt="cover" className="h-14 w-14 rounded-lg object-cover ring-1 ring-slate-200" />
                )}
                <div className="min-w-0 flex-1">
                  <div className="mb-1 flex flex-wrap items-center gap-1.5">
                    <span className="text-xs font-semibold text-slate-800">
                      {line.character_name}
                    </span>
                    <Badge tone="slate">v{line.version_no}</Badge>
                    {line.approved ? (
                      <Badge tone="green">✓ 已批准</Badge>
                    ) : (
                      <Badge tone="amber">待批准</Badge>
                    )}
                    {line.needs_recheck && <Badge tone="red">待复核</Badge>}
                  </div>
                  <p className="text-sm leading-relaxed text-slate-700">{line.content}</p>
                  {line.interpretation_snapshot && (
                    <p className="mt-1 text-[11px] text-slate-400">
                      冻结解释 @ v{(line.interpretation_snapshot as any).version_no} ·
                      {" " + String((line.interpretation_snapshot as any).tone || "").slice(0, 40)}
                    </p>
                  )}
                  {line.needs_recheck && line.recheck_reason && (
                    <p className="mt-1 rounded-lg bg-red-50 px-2 py-1 text-[11px] text-red-600 ring-1 ring-red-100">
                      {line.recheck_reason}
                    </p>
                  )}
                </div>
                {canEdit && (
                  <div className="flex items-start gap-1.5">
                    {!line.approved && (
                      <Button size="sm" variant="secondary" loading={busy === line.id} onClick={() => approve(line)}>
                        批准并冻结
                      </Button>
                    )}
                    {line.needs_recheck && (
                      <Button size="sm" loading={busy === line.id} onClick={() => reapprove(line)}>
                        按最新版重新批准
                      </Button>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}

      {canEdit && script.scenes.length > 0 && referencedIds.size > 0 && (
        <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-100">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">新增台词</p>
          <div className="grid gap-2 sm:grid-cols-2">
            <Select value={sceneId} onChange={(e) => setSceneId(e.target.value)}>
              {script.scenes.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.code} · {s.title}
                </option>
              ))}
            </Select>
            <Select value={characterId} onChange={(e) => setCharacterId(e.target.value)}>
              {script.characters.map((c) => (
                <option key={c.id} value={c.character_id}>
                  {c.character_name}（{c.pin_mode === "pinned" ? "固定" : "跟随最新"} v{c.resolved_version_no}）
                </option>
              ))}
            </Select>
          </div>
          <Textarea
            className="mt-2"
            placeholder="输入台词内容…"
            value={content}
            onChange={(e) => setContent(e.target.value)}
          />
          <div className="mt-2 flex justify-end">
            <Button size="sm" loading={busy === "create"} onClick={create}>
              添加台词
            </Button>
          </div>
          <p className="mt-2 text-[11px] text-slate-400">
            已退役角色不能被新增引用；批准时会冻结当时版本的外观/语气/限制词快照，之后发布新版本不会改写它。
          </p>
        </div>
      )}
    </div>
  );
};

export default LinesPanel;
