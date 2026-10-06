import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { scriptApi } from "@/api";
import type { Script } from "@/types";
import { Badge, Button, Card, EmptyState, Field, Input, Textarea } from "@/components/ui";
import { useAuthStore } from "@/store/authStore";

const ScriptListPage = () => {
  const { user } = useAuthStore();
  const canEdit = user?.role === "admin" || user?.role === "editor";
  const [scripts, setScripts] = useState<Script[]>([]);
  const [loading, setLoading] = useState(true);
  const [title, setTitle] = useState("");
  const [synopsis, setSynopsis] = useState("");
  const [creating, setCreating] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      setScripts(await scriptApi.list());
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load();
  }, []);

  const create = async (e: FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    setCreating(true);
    try {
      const s = await scriptApi.create(title.trim(), synopsis);
      setTitle("");
      setSynopsis("");
      window.location.assign(`/scripts/${s.id}`);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900">脚本与场次</h2>
        <p className="mt-1 text-sm text-slate-500">
          每个角色引用都明确显示「📌 固定版本」或「🌀 跟随最新」两种模式。
        </p>
      </div>

      {canEdit && (
        <Card>
          <form onSubmit={create} className="grid gap-3 md:grid-cols-[1fr_1.6fr_auto] md:items-end">
            <Field label="剧本标题">
              <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="例如：《雨夜画廊》第 8 集" />
            </Field>
            <Field label="剧情概述">
              <Input value={synopsis} onChange={(e) => setSynopsis(e.target.value)} placeholder="一句话梗概" />
            </Field>
            <Button loading={creating}>新建剧本</Button>
          </form>
        </Card>
      )}

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 2 }).map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-2xl bg-slate-200/60" />
          ))}
        </div>
      ) : scripts.length === 0 ? (
        <EmptyState title="暂无剧本" />
      ) : (
        <div className="grid gap-3">
          {scripts.map((s) => (
            <Link key={s.id} to={`/scripts/${s.id}`} className="block">
              <Card className="flex flex-wrap items-center justify-between gap-3 transition hover:-translate-y-0.5 hover:shadow-lg">
                <div>
                  <h3 className="font-semibold text-slate-900">{s.title}</h3>
                  <p className="mt-0.5 text-xs text-slate-500">{s.synopsis || "暂无梗概"}</p>
                </div>
                <div className="flex flex-wrap items-center gap-1.5">
                  <Badge tone="slate">{s.scenes.length} 场</Badge>
                  {s.characters.map((c) => (
                    <Badge key={c.id} tone={c.pin_mode === "pinned" ? "violet" : "blue"}>
                      {c.pin_mode === "pinned" ? "📌" : "🌀"} {c.character_name} v{c.resolved_version_no}
                    </Badge>
                  ))}
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
};

export default ScriptListPage;
