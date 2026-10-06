import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import toast from "react-hot-toast";
import { characterApi, reviewApi, scriptApi } from "@/api";
import type { Character, ReviewItem, Script } from "@/types";
import AnimatedCover from "@/components/AnimatedCover";
import { Badge, Button, Card, Field, Input, Textarea } from "@/components/ui";
import { useAuthStore } from "@/store/authStore";
import { PublishVersionCard, VersionContent } from "./VersionPanel";
import CoverJobsPanel from "./CoverJobsPanel";
import RetireDialog from "./RetireDialog";

const CharacterDetailPage = () => {
  const { id = "" } = useParams();
  const { user } = useAuthStore();
  const canEdit = user?.role === "admin" || user?.role === "editor";
  const isAdmin = user?.role === "admin";
  const [character, setCharacter] = useState<Character | null>(null);
  const [allCharacters, setAllCharacters] = useState<Character[]>([]);
  const [scripts, setScripts] = useState<Script[]>([]);
  const [reviews, setReviews] = useState<ReviewItem[]>([]);
  const [activeVersion, setActiveVersion] = useState<string>("");
  const [editingMeta, setEditingMeta] = useState(false);
  const [metaForm, setMetaForm] = useState({ name: "", summary: "" });
  const [savingMeta, setSavingMeta] = useState(false);
  const [showRetire, setShowRetire] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [ch, chs, ss, rvs] = await Promise.all([
        characterApi.get(id),
        characterApi.list(),
        scriptApi.list(),
        reviewApi.list("open"),
      ]);
      setCharacter(ch);
      setAllCharacters(chs);
      setScripts(ss);
      setReviews(rvs.filter((r) => r.character_id === id));
      setActiveVersion((prev) => prev || ch.current_version_id || "");
      setMetaForm({ name: ch.name, summary: ch.summary });
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading || !character) {
    return <div className="h-72 animate-pulse rounded-3xl bg-slate-200/60" />;
  }

  const version =
    character.versions.find((v) => v.id === activeVersion) ??
    character.versions.find((v) => v.id === character.current_version_id);

  const saveMeta = async () => {
    setSavingMeta(true);
    try {
      const updated = await characterApi.update(character.id, {
        name: metaForm.name,
        summary: metaForm.summary,
        expected_revision: character.revision,
      });
      toast.success("角色信息已更新");
      setCharacter(updated);
      setEditingMeta(false);
    } catch (err: any) {
      if (err?.response?.status === 409) {
        toast.error("有人刚刚也改了这个字段，已为你刷新，请重新合并修改");
      }
      load();
    } finally {
      setSavingMeta(false);
    }
  };

  // Which scripts reference this character, and how (pinned/latest visible)
  const refsInScripts = scripts.flatMap((s) =>
    s.characters
      .filter((c) => c.character_id === character.id)
      .map((c) => ({ script: s, ref: c })),
  );

  return (
    <div className="space-y-6">
      <Link to="/characters" className="text-xs font-medium text-primary hover:underline">
        ← 返回角色列表
      </Link>

      <Card className="overflow-hidden p-0">
        <div className="grid gap-0 md:grid-cols-[280px_1fr]">
          <AnimatedCover
            src={character.active_cover_url}
            alt={character.name}
            className="h-60 w-full rounded-none md:h-full"
          />
          <div className="p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-2xl font-bold text-slate-900">{character.name}</h2>
                  <Badge tone={character.status === "retired" ? "slate" : "green"}>
                    {character.status === "retired" ? "已退役（只读）" : "启用中"}
                  </Badge>
                  <Badge tone="blue">当前 v{character.current_version_no}</Badge>
                  <span className="text-[11px] text-slate-400">revision #{character.revision}（乐观锁）</span>
                </div>
                <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-500">
                  {character.summary}
                </p>
              </div>
              <div className="flex gap-2">
                {canEdit && character.status === "active" && (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => setEditingMeta((v) => !v)}
                  >
                    {editingMeta ? "取消编辑" : "编辑名称/简介"}
                  </Button>
                )}
                {isAdmin && character.status === "active" && (
                  <Button size="sm" variant="danger" onClick={() => setShowRetire(true)}>
                    退役…
                  </Button>
                )}
              </div>
            </div>

            {editingMeta && canEdit && (
              <div className="mt-4 space-y-3 rounded-2xl bg-amber-50/60 p-4 ring-1 ring-amber-100">
                <p className="text-xs text-amber-700">
                  ⚠ 你正在基于 revision #{character.revision} 编辑；若他人已先提交，保存会收到
                  409 冲突提示而不是静默覆盖。
                </p>
                <Field label="名称">
                  <Input
                    value={metaForm.name}
                    onChange={(e) => setMetaForm({ ...metaForm, name: e.target.value })}
                  />
                </Field>
                <Field label="简介">
                  <Textarea
                    value={metaForm.summary}
                    onChange={(e) => setMetaForm({ ...metaForm, summary: e.target.value })}
                  />
                </Field>
                <div className="flex justify-end">
                  <Button size="sm" loading={savingMeta} onClick={saveMeta}>
                    保存（带版本号校验）
                  </Button>
                </div>
              </div>
            )}

            <div className="mt-5">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                被脚本引用方式
              </p>
              {refsInScripts.length === 0 ? (
                <p className="text-xs text-slate-400">暂无脚本引用该角色。</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {refsInScripts.map(({ script: s, ref }) => (
                    <Link
                      key={ref.id}
                      to={`/scripts/${s.id}`}
                      className="group inline-flex items-center gap-2 rounded-full bg-slate-50 py-1.5 pl-3 pr-2 text-xs ring-1 ring-slate-200 transition hover:ring-primary"
                    >
                      <span className="font-medium text-slate-700 group-hover:text-primary">
                        {s.title}
                      </span>
                      {ref.pin_mode === "pinned" ? (
                        <Badge tone="violet">
                          📌 固定 v{ref.resolved_version_no}
                        </Badge>
                      ) : (
                        <Badge tone="blue">🌀 跟随最新 v{ref.resolved_version_no}</Badge>
                      )}
                    </Link>
                  ))}
                </div>
              )}
            </div>

            {reviews.length > 0 && (
              <div className="mt-4 rounded-2xl bg-red-50/70 p-3 ring-1 ring-red-100">
                <p className="text-xs font-semibold text-red-700">该角色有 {reviews.length} 个待复核项</p>
                <ul className="mt-1 space-y-1 text-[11px] text-red-600">
                  {reviews.slice(0, 3).map((r) => (
                    <li key={r.id}>
                      {r.scene_code ? `场次 ${r.scene_code}：` : ""}
                      {r.message}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
        <Card>
          <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
            版本历史（不可变）
          </p>
          <div className="space-y-1.5">
            {character.versions
              .slice()
              .sort((a, b) => b.version_no - a.version_no)
              .map((v) => (
                <button
                  key={v.id}
                  onClick={() => setActiveVersion(v.id)}
                  className={
                    "flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-sm transition " +
                    (activeVersion === v.id
                      ? "bg-primary/10 font-semibold text-primary"
                      : "text-slate-600 hover:bg-slate-100")
                  }
                >
                  <span>v{v.version_no}</span>
                  {v.id === character.current_version_id && <Badge tone="green">最新</Badge>}
                </button>
              ))}
          </div>
          <div className="mt-4 border-t border-slate-100 pt-4">
            {canEdit && character.status === "active" && (
              <PublishVersionCard
                character={character}
                onPublished={async () => {
                  await load();
                }}
              />
            )}
          </div>
        </Card>

        <div className="space-y-6">
          {version && (
            <Card>
              <VersionContent version={version} current={version.id === character.current_version_id} character={character} />
            </Card>
          )}
          <CoverJobsPanel character={character} />
        </div>
      </div>

      {showRetire && (
        <RetireDialog
          character={character}
          alternatives={allCharacters}
          onClose={() => setShowRetire(false)}
        />
      )}
    </div>
  );
};

export default CharacterDetailPage;
