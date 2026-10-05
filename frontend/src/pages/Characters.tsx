import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import toast from "react-hot-toast";
import { createCharacter, listCharacters } from "../api/endpoints";
import type { Character } from "../types";
import { useAuth, canEdit } from "../store/auth";
import {
  Badge,
  Button,
  Card,
  Empty,
  Field,
  Modal,
  PageHeader,
  SkeletonRows,
  inputCls,
} from "../components/ui";
import { useMotionAllowed } from "../hooks/useMotionAllowed";
import { useRef } from "react";

const statusMeta: Record<string, { label: string; tone: "green" | "amber" | "slate" }> = {
  active: { label: "活跃", tone: "green" },
  soft_deleted: { label: "软删除", tone: "amber" },
  retired: { label: "已退役", tone: "slate" },
};

export default function Characters() {
  const { user } = useAuth();
  const [items, setItems] = useState<Character[]>([]);
  const [loading, setLoading] = useState(true);
  const [includeInactive, setIncludeInactive] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await listCharacters(includeInactive));
    } catch (e) {
      toast.error((e as { friendlyMessage?: string }).friendlyMessage ?? "加载失败");
    } finally {
      setLoading(false);
    }
  }, [includeInactive]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div>
      <PageHeader
        title="角色设计"
        subtitle="外观 · 语气 · 参考图 · 限制词 —— 每次修改都生成不可变新版本"
        actions={
          <>
            <label className="flex items-center gap-2 rounded-xl bg-white px-3 py-2 text-sm text-slate-600 ring-1 ring-slate-200">
              <input
                type="checkbox"
                checked={includeInactive}
                onChange={(e) => setIncludeInactive(e.target.checked)}
              />
              显示已下线角色
            </label>
            {canEdit(user) && (
              <Button onClick={() => setCreateOpen(true)}>＋ 新建角色</Button>
            )}
          </>
        }
      />

      {loading ? (
        <Card>
          <SkeletonRows rows={4} />
        </Card>
      ) : items.length === 0 ? (
        <Card>
          <Empty text="还没有角色，点击右上角新建" />
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {items.map((c) => (
            <CharacterCard key={c.id} character={c} />
          ))}
        </div>
      )}

      {createOpen && (
        <CreateCharacterModal
          onClose={() => setCreateOpen(false)}
          onCreated={() => {
            setCreateOpen(false);
            load();
          }}
        />
      )}
    </div>
  );
}

function CharacterCard({ character }: { character: Character }) {
  const imgRef = useRef<HTMLDivElement>(null);
  const animate = useMotionAllowed(imgRef);
  const meta = statusMeta[character.status];
  const cover = character.latest?.images.find((i) => i.license_granted) ?? character.latest?.images[0];

  return (
    <Link
      to={`/characters/${character.id}`}
      className="group block overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-card transition hover:-translate-y-0.5 hover:border-blue-300"
    >
      <div
        ref={imgRef}
        className={`relative h-36 overflow-hidden bg-gradient-to-br from-slate-100 to-slate-200 ${
          animate ? "cs-kenburns" : ""
        }`}
      >
        {cover ? (
          <img
            src={cover.url}
            alt={cover.caption || character.name}
            className={`h-full w-full object-cover ${animate ? "cs-kenburns-img" : ""}`}
          />
        ) : (
          <div className="flex h-full items-center justify-center text-4xl">🎭</div>
        )}
        <div className="absolute left-3 top-3 flex gap-1.5">
          <Badge tone={meta.tone}>{meta.label}</Badge>
          <Badge tone="blue">v{character.latest_version}</Badge>
        </div>
      </div>
      <div className="p-4">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-slate-900 group-hover:text-blue-700">
            {character.name}
          </h3>
          <span className="font-mono text-xs text-slate-400">{character.code}</span>
        </div>
        <p className="mt-1.5 line-clamp-2 text-sm leading-6 text-slate-500">
          {character.latest?.appearance || "暂无外观描述"}
        </p>
        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          <span className="rounded-lg bg-slate-50 px-2 py-1 text-slate-500 ring-1 ring-slate-200">
            📌 固定引用 <b className="text-slate-700">{character.pinned_count}</b>
          </span>
          <span className="rounded-lg bg-slate-50 px-2 py-1 text-slate-500 ring-1 ring-slate-200">
            🔄 跟随最新 <b className="text-slate-700">{character.floating_count}</b>
          </span>
          {character.latest?.images.some((i) => !i.license_granted) && (
            <Badge tone="red">含授权撤销图</Badge>
          )}
        </div>
      </div>
    </Link>
  );
}

function CreateCharacterModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [form, setForm] = useState({ name: "", code: "", appearance: "", tone: "", restrictions: "" });
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    if (!form.name.trim() || !form.code.trim()) {
      toast.error("名称与编码必填");
      return;
    }
    setSaving(true);
    try {
      await createCharacter(form);
      toast.success("角色已创建（v1 不可变版本）");
      onCreated();
    } catch (e) {
      toast.error((e as { friendlyMessage?: string }).friendlyMessage ?? "创建失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      title="新建角色"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            取消
          </Button>
          <Button loading={saving} onClick={submit}>
            创建 v1
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <Field label="角色名称">
            <input
              className={inputCls}
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="如：瑶光"
            />
          </Field>
          <Field label="角色编码" hint="字母数字 - _">
            <input
              className={inputCls}
              value={form.code}
              onChange={(e) => setForm({ ...form, code: e.target.value })}
              placeholder="YG-03"
            />
          </Field>
        </div>
        <Field label="外观设定">
          <textarea
            className={inputCls}
            rows={3}
            value={form.appearance}
            onChange={(e) => setForm({ ...form, appearance: e.target.value })}
          />
        </Field>
        <Field label="语气风格">
          <textarea
            className={inputCls}
            rows={2}
            value={form.tone}
            onChange={(e) => setForm({ ...form, tone: e.target.value })}
          />
        </Field>
        <Field label="限制词 / 红线">
          <textarea
            className={inputCls}
            rows={2}
            value={form.restrictions}
            onChange={(e) => setForm({ ...form, restrictions: e.target.value })}
          />
        </Field>
      </div>
    </Modal>
  );
}
