import { useCallback, useEffect, useState } from "react";
import toast from "react-hot-toast";
import {
  addScriptLink,
  approveLine,
  listCharacters,
  listScripts,
  reconfirmLine,
  removeScriptLink,
  switchLinkMode,
} from "../api/endpoints";
import type { Character, RefMode, Script as ScriptType, ScriptRef } from "../types";
import { useAuth, canEdit } from "../store/auth";
import { Badge, Button, Card, Empty, Field, Modal, PageHeader, SkeletonRows, inputCls } from "../components/ui";

export default function Scripts() {
  const { user } = useAuth();
  const [scripts, setScripts] = useState<ScriptType[]>([]);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeId, setActiveId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [ss, cs] = await Promise.all([listScripts(), listCharacters(true)]);
      setScripts(ss);
      setCharacters(cs);
      setActiveId((cur) => cur ?? ss[0]?.id ?? null);
    } catch (e) {
      toast.error((e as { friendlyMessage?: string }).friendlyMessage ?? "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const active = scripts.find((s) => s.id === activeId) ?? null;

  return (
    <div>
      <PageHeader
        title="脚本场次"
        subtitle="每个角色引用都显式标注：📌 固定版本 / 🔄 跟随最新版；已批准台词改版后必须人工复核"
      />
      {loading ? (
        <Card>
          <SkeletonRows rows={4} />
        </Card>
      ) : scripts.length === 0 ? (
        <Card>
          <Empty text="暂无脚本（种子数据应已生成 3 个场次）" />
        </Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
          <Card className="h-fit overflow-hidden">
            <ul className="divide-y divide-slate-100">
              {scripts.map((s) => {
                const needsReview = s.links.some((l) => l.needs_review);
                return (
                  <li key={s.id}>
                    <button
                      onClick={() => setActiveId(s.id)}
                      className={`flex w-full items-center justify-between px-4 py-3 text-left transition ${
                        activeId === s.id ? "bg-blue-50" : "hover:bg-slate-50"
                      }`}
                    >
                      <span>
                        <span className="font-mono text-xs text-slate-400">{s.scene_code}</span>
                        <span className="ml-2 text-sm font-medium text-slate-800">{s.title}</span>
                      </span>
                      {needsReview && <Badge tone="amber">待复核</Badge>}
                    </button>
                  </li>
                );
              })}
            </ul>
          </Card>

          {active && (
            <ScriptDetail
              key={active.id}
              script={active}
              characters={characters}
              editable={canEdit(user)}
              onChanged={load}
            />
          )}
        </div>
      )}
    </div>
  );
}

function ScriptDetail({
  script,
  characters,
  editable,
  onChanged,
}: {
  script: ScriptType;
  characters: Character[];
  editable: boolean;
  onChanged: () => void;
}) {
  const [addOpen, setAddOpen] = useState(false);

  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">
            <span className="mr-2 font-mono text-sm text-slate-400">{script.scene_code}</span>
            {script.title}
          </h3>
          <p className="mt-2 whitespace-pre-wrap rounded-xl bg-slate-50 p-3 text-sm leading-7 text-slate-600">
            {script.content}
          </p>
        </div>
        {editable && <Button size="sm" onClick={() => setAddOpen(true)}>＋ 引用角色</Button>}
      </div>

      <div className="mt-5 space-y-3">
        <h4 className="text-sm font-semibold text-slate-700">角色引用（{script.links.length}）</h4>
        {script.links.map((link) => (
          <LinkRow key={link.link_id} link={link} characters={characters} editable={editable} onChanged={onChanged} />
        ))}
      </div>

      {addOpen && (
        <AddLinkModal
          scriptId={script.id}
          characters={characters.filter((c) => c.status === "active")}
          onClose={() => setAddOpen(false)}
          onDone={() => {
            setAddOpen(false);
            onChanged();
          }}
        />
      )}
    </Card>
  );
}

function LinkRow({
  link,
  characters,
  editable,
  onChanged,
}: {
  link: ScriptRef;
  characters: Character[];
  editable: boolean;
  onChanged: () => void;
}) {
  const resolvedCharacter = characters.find((c) => c.id === link.character_id);
  const [approveOpen, setApproveOpen] = useState(false);
  const [text, setText] = useState(link.approved_text ?? "");
  const [busy, setBusy] = useState(false);
  const versions = resolvedCharacter?.versions ?? [];

  const pinned = link.ref_mode === "pinned";
  const drift = link.needs_review;

  const act = async (fn: () => Promise<unknown>, ok: string) => {
    setBusy(true);
    try {
      await fn();
      toast.success(ok);
      onChanged();
    } catch (e) {
      toast.error((e as { friendlyMessage?: string }).friendlyMessage ?? "操作失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className={`rounded-2xl border p-4 ${
        drift ? "border-amber-300 bg-amber-50/50" : "border-slate-200 bg-white"
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-slate-800">
          {resolvedCharacter?.name ?? "角色"}
        </span>
        {pinned ? (
          <Badge tone="blue">📌 固定 v{link.pinned_version}</Badge>
        ) : (
          <Badge tone="violet">🔄 跟随最新 v{link.latest_version}</Badge>
        )}
        {link.approved_text && (
          <Badge tone="slate">已批准基线 v{link.approved_version}</Badge>
        )}
        {drift && <Badge tone="amber">⚠️ 改版后待复核（解释未改变）</Badge>}
      </div>

      {link.approved_text && (
        <div className="mt-2 rounded-xl bg-slate-50 px-3 py-2">
          <p className="text-xs font-medium text-slate-500">已批准台词（冻结于批准时版本）</p>
          <p className="mt-1 text-sm leading-6 text-slate-700">{link.approved_text}</p>
        </div>
      )}
      {drift && (
        <p className="mt-2 text-xs leading-5 text-amber-700">
          角色已发布 v{link.latest_version}，但本台词仍按 v{link.approved_version} 解释，系统没有自动改写。
          请核对新版本后显式“确认复核”。
        </p>
      )}

      {editable && (
        <div className="mt-3 flex flex-wrap gap-2">
          {!link.approved_text && (
            <Button size="sm" variant="secondary" onClick={() => setApproveOpen(true)}>
              批准台词
            </Button>
          )}
          {drift && (
            <Button
              size="sm"
              loading={busy}
              onClick={() =>
                link.link_id &&
                act(() => reconfirmLine(link.link_id!), "已以当前最新版重新冻结基线")
              }
            >
              确认复核（重新冻结到 v{link.latest_version}）
            </Button>
          )}
          <ModeSwitcher link={link} versions={versions} onChanged={onChanged} />
        </div>
      )}

      {approveOpen && (
        <Modal
          open
          onClose={() => setApproveOpen(false)}
          title={pinned ? `批准台词（将固定在 v${link.pinned_version}）` : `批准台词（冻结到当前最新 v${link.latest_version}）`}
          footer={
            <>
              <Button variant="secondary" onClick={() => setApproveOpen(false)}>取消</Button>
              <Button
                loading={busy}
                onClick={() =>
                  link.link_id &&
                  act(async () => {
                    await approveLine(link.link_id!, text);
                    setApproveOpen(false);
                  }, "台词已批准")
                }
              >
                确认批准
              </Button>
            </>
          }
        >
          <Field label="台词文本">
            <textarea className={inputCls} rows={4} value={text} onChange={(e) => setText(e.target.value)} />
          </Field>
        </Modal>
      )}
    </div>
  );
}

function ModeSwitcher({
  link,
  versions,
  onChanged,
}: {
  link: ScriptRef;
  versions: NonNullable<Character["versions"]>;
  onChanged: () => void;
}) {
  const linkId = link.link_id;
  const [mode, setMode] = useState<RefMode>(link.ref_mode);
  const [pinnedVersionId, setPinnedVersionId] = useState<string>("");
  if (!linkId) return null;

  return (
    <span className="inline-flex items-center gap-1.5">
      <select
        className="rounded-lg border border-slate-300 px-2 py-1.5 text-xs"
        value={mode}
        onChange={(e) => setMode(e.target.value as RefMode)}
      >
        <option value="pinned">📌 固定版本</option>
        <option value="floating">🔄 跟随最新</option>
      </select>
      {mode === "pinned" && (
        <select
          className="rounded-lg border border-slate-300 px-2 py-1.5 text-xs"
          value={pinnedVersionId}
          onChange={(e) => setPinnedVersionId(e.target.value)}
        >
          <option value="">选择版本</option>
          {[...versions].reverse().map((v) => (
            <option key={v.id} value={v.id}>v{v.version}</option>
          ))}
        </select>
      )}
      <Button
        size="sm"
        variant="ghost"
        onClick={async () => {
          try {
            await switchLinkMode(linkId, mode, mode === "pinned" ? pinnedVersionId || undefined : null);
            toast.success("引用模式已切换");
            onChanged();
          } catch (e) {
            toast.error((e as { friendlyMessage?: string }).friendlyMessage ?? "切换失败");
          }
        }}
      >
        应用
      </Button>
    </span>
  );
}

function AddLinkModal({
  scriptId,
  characters,
  onClose,
  onDone,
}: {
  scriptId: string;
  characters: Character[];
  onClose: () => void;
  onDone: () => void;
}) {
  const [characterId, setCharacterId] = useState(characters[0]?.id ?? "");
  const [mode, setMode] = useState<RefMode>("floating");
  const [versionId, setVersionId] = useState("");
  const [busy, setBusy] = useState(false);
  const chosen = characters.find((c) => c.id === characterId);

  return (
    <Modal
      open
      onClose={onClose}
      title="新增角色引用"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>取消</Button>
          <Button
            loading={busy}
            onClick={async () => {
              if (!characterId) return toast.error("请选择角色");
              if (mode === "pinned" && !versionId) return toast.error("固定模式必须选择版本");
              setBusy(true);
              try {
                await addScriptLink(scriptId, {
                  character_id: characterId,
                  ref_mode: mode,
                  pinned_version_id: mode === "pinned" ? versionId : null,
                });
                toast.success("引用已新增（退役进行中时服务端会拒绝新增）");
                onDone();
              } catch (e) {
                toast.error((e as { friendlyMessage?: string }).friendlyMessage ?? "新增失败");
              } finally {
                setBusy(false);
              }
            }}
          >
            新增
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="选择角色">
          <select className={inputCls} value={characterId} onChange={(e) => setCharacterId(e.target.value)}>
            {characters.map((c) => (
              <option key={c.id} value={c.id}>{c.name}（{c.code}）</option>
            ))}
          </select>
        </Field>
        <div className="grid grid-cols-2 gap-3">
          {(["pinned", "floating"] as RefMode[]).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={`rounded-xl border p-3 text-left text-sm ${
                mode === m ? "border-blue-400 bg-blue-50" : "border-slate-200"
              }`}
            >
              {m === "pinned" ? "📌 固定某版" : "🔄 跟随最新版"}
              <span className="mt-1 block text-xs text-slate-500">
                {m === "pinned" ? "角色改版不影响已批准台词" : "改版后已批准台词进入待复核"}
              </span>
            </button>
          ))}
        </div>
        {mode === "pinned" && (
          <Field label="固定到版本">
            <select className={inputCls} value={versionId} onChange={(e) => setVersionId(e.target.value)}>
              <option value="">选择版本</option>
              {[...(chosen?.versions ?? [])].reverse().map((v) => (
                <option key={v.id} value={v.id}>
                  v{v.version} — {v.change_note}
                </option>
              ))}
            </select>
          </Field>
        )}
      </div>
    </Modal>
  );
}
