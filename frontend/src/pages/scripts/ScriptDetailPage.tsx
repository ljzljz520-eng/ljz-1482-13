import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import toast from "react-hot-toast";
import { characterApi, scriptApi } from "@/api";
import type { Character, ExportSnapshot, Line, Script } from "@/types";
import { Badge, Button, Card, Field, Input } from "@/components/ui";
import { useAuthStore } from "@/store/authStore";
import ReferenceManager from "./ReferenceManager";
import LinesPanel from "./LinesPanel";

const ScriptDetailPage = () => {
  const { id = "" } = useParams();
  const { user } = useAuthStore();
  const canEdit = user?.role === "admin" || user?.role === "editor";
  const [script, setScript] = useState<Script | null>(null);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [lines, setLines] = useState<Line[]>([]);
  const [exports, setExports] = useState<ExportSnapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [sceneForm, setSceneForm] = useState({ code: "", title: "" });
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, cs, ls, es] = await Promise.all([
        scriptApi.get(id),
        characterApi.list(),
        scriptApi.lines(id),
        scriptApi.exports(),
      ]);
      setScript(s);
      setCharacters(cs);
      setLines(ls);
      setExports(es.filter((e) => e.script_id === id));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
    const t = setInterval(load, 6000);
    return () => clearInterval(t);
  }, [load]);

  if (loading || !script) return <div className="h-72 animate-pulse rounded-3xl bg-slate-200/60" />;

  const addScene = async () => {
    if (!sceneForm.code.trim() || !sceneForm.title.trim()) {
      toast.error("请填写场次编号与标题");
      return;
    }
    const updated = await scriptApi.addScene(script.id, {
      code: sceneForm.code.trim(),
      title: sceneForm.title.trim(),
      sort_order: script.scenes.length + 1,
    });
    setScript(updated);
    setSceneForm({ code: "", title: "" });
    toast.success("场次已添加");
  };

  const createExport = async () => {
    setExporting(true);
    try {
      const label = `导出 ${new Date().toLocaleString("zh-CN", { hour12: false })}`;
      const e = await scriptApi.export(script.id, label);
      toast.success(`导出快照 ${e.id.slice(0, 8)} 已生成，将永久保护其中图片与素材`);
      load();
    } finally {
      setExporting(false);
    }
  };

  // affected scenes = scenes with any flagged line
  const affectedScenes = new Set(
    lines.filter((l) => l.needs_recheck).map((l) => l.scene_code),
  );

  return (
    <div className="space-y-6">
      <Link to="/scripts" className="text-xs font-medium text-primary hover:underline">
        ← 返回剧本列表
      </Link>

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold text-slate-900">{script.title}</h2>
            <p className="mt-1 max-w-2xl text-sm text-slate-500">{script.synopsis || "暂无梗概"}</p>
          </div>
          {canEdit && (
            <Button variant="secondary" loading={exporting} onClick={createExport}>
              📦 生成导出快照
            </Button>
          )}
        </div>
        {affectedScenes.size > 0 && (
          <div className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-xs text-red-700 ring-1 ring-red-100">
            受影响场次：
            {Array.from(affectedScenes).map((code) => (
              <Badge key={code} tone="red" className="mx-1">
                {code}
              </Badge>
            ))}
            内有台词因角色改版 / 授权撤销等待复核。
          </div>
        )}
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <h3 className="mb-3 text-sm font-bold text-slate-800">角色引用</h3>
          <ReferenceManager
            script={script}
            characters={characters}
            canEdit={canEdit}
            onChanged={(s) => {
              setScript(s);
              load();
            }}
          />
        </Card>

        <Card>
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-800">场次结构</h3>
            <span className="text-[11px] text-slate-400">{script.scenes.length} 场</span>
          </div>
          <div className="space-y-2">
            {script.scenes
              .slice()
              .sort((a, b) => a.sort_order - b.sort_order)
              .map((scene) => {
                const affected = lines.some(
                  (l) => l.scene_id === scene.id && l.needs_recheck,
                );
                return (
                  <div
                    key={scene.id}
                    className={
                      "flex items-center justify-between rounded-xl px-3 py-2 text-sm ring-1 " +
                      (affected ? "bg-red-50/70 ring-red-100" : "bg-slate-50 ring-slate-100")
                    }
                  >
                    <span className="font-medium text-slate-700">
                      {scene.code} · {scene.title}
                    </span>
                    {affected && <Badge tone="red">有待复核台词</Badge>}
                  </div>
                );
              })}
          </div>
          {canEdit && (
            <div className="mt-3 grid grid-cols-[120px_1fr_auto] gap-2">
              <Input
                className="text-xs"
                placeholder="EP08-04"
                value={sceneForm.code}
                onChange={(e) => setSceneForm({ ...sceneForm, code: e.target.value })}
              />
              <Input
                className="text-xs"
                placeholder="场次标题"
                value={sceneForm.title}
                onChange={(e) => setSceneForm({ ...sceneForm, title: e.target.value })}
              />
              <Button size="sm" onClick={addScene}>
                添加
              </Button>
            </div>
          )}
        </Card>
      </div>

      <Card>
        <h3 className="mb-4 text-sm font-bold text-slate-800">台词与解释快照</h3>
        <LinesPanel
          script={script}
          characters={characters}
          lines={lines}
          canEdit={canEdit}
          onChanged={load}
        />
      </Card>

      <Card>
        <h3 className="mb-3 text-sm font-bold text-slate-800">历史导出快照</h3>
        {exports.length === 0 ? (
          <p className="text-xs text-slate-400">还没有导出。导出对象会阻止清理任务删除其引用的图片/素材。</p>
        ) : (
          <div className="space-y-2">
            {exports.map((e) => (
              <div key={e.id} className="flex flex-wrap items-center gap-2 rounded-xl bg-slate-50 px-3 py-2 text-xs ring-1 ring-slate-100">
                <span className="font-medium text-slate-700">{e.label || e.id.slice(0, 8)}</span>
                <Badge tone="blue">{e.payload?.version_ids?.length ?? 0} 个角色版本</Badge>
                <Badge tone="green">{e.asset_ids.length} 个封面素材</Badge>
                <Badge tone="violet">{e.image_ids.length} 张来源图</Badge>
                <span className="ml-auto text-slate-400">
                  {new Date(e.created_at).toLocaleString("zh-CN", { hour12: false })}
                </span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
};

export default ScriptDetailPage;
