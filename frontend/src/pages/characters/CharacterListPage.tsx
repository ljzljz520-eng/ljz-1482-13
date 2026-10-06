import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import toast from "react-hot-toast";
import { characterApi, imageApi } from "@/api";
import type { Character, RefImage } from "@/types";
import AnimatedCover from "@/components/AnimatedCover";
import { Badge, Button, Card, EmptyState, Field, Input, Textarea } from "@/components/ui";
import { useAuthStore } from "@/store/authStore";

const CharacterListPage = () => {
  const { user } = useAuthStore();
  const canEdit = user?.role === "admin" || user?.role === "editor";
  const [characters, setCharacters] = useState<Character[]>([]);
  const [images, setImages] = useState<RefImage[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [chs, imgs] = await Promise.all([characterApi.list(), imageApi.list()]);
      setCharacters(chs);
      setImages(imgs.filter((i) => i.license_status === "licensed"));
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900">角色设计</h2>
          <p className="mt-1 text-sm text-slate-500">
            外观 · 语气 · 参考图 · 限制词 —— 每次修改生成不可变版本，脚本引用方式清晰可见。
          </p>
        </div>
        {canEdit && (
          <Button onClick={() => setShowCreate((v) => !v)}>
            {showCreate ? "收起表单" : "＋ 新建角色"}
          </Button>
        )}
      </div>

      {showCreate && canEdit && (
        <CreateCharacterCard
          images={images}
          onCreated={() => {
            setShowCreate(false);
            load();
          }}
        />
      )}

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-64 animate-pulse rounded-2xl bg-slate-200/60" />
          ))}
        </div>
      ) : characters.length === 0 ? (
        <EmptyState title="还没有角色" hint="点击右上角“新建角色”开始维护第一张角色卡。" />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {characters.map((ch, idx) => (
            <Link
              key={ch.id}
              to={`/characters/${ch.id}`}
              className="animate-fade-up block"
              style={{ animationDelay: `${idx * 60}ms` }}
            >
              <Card className="group h-full cursor-pointer p-0 overflow-hidden hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200">
                <div className="relative">
                  <AnimatedCover src={ch.active_cover_url} alt={ch.name} className="h-44 w-full rounded-none" />
                  <div className="absolute left-3 top-3 flex gap-1.5">
                    {ch.status === "retired" ? (
                      <Badge tone="slate">已退役</Badge>
                    ) : (
                      <Badge tone="green">启用中</Badge>
                    )}
                    <Badge tone="blue">v{ch.current_version_no ?? "-"}</Badge>
                  </div>
                </div>
                <div className="p-4">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-slate-900 group-hover:text-primary transition">
                      {ch.name}
                    </h3>
                    <span className="text-[11px] text-slate-400">{ch.versions.length || ""} 个版本</span>
                  </div>
                  <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-slate-500">
                    {ch.summary || "暂无简介"}
                  </p>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
};

const CreateCharacterCard = ({
  images,
  onCreated,
}: {
  images: RefImage[];
  onCreated: (ch: Character) => void;
}) => {
  const [form, setForm] = useState({
    name: "",
    slug: "",
    summary: "",
    appearance: "",
    tone: "",
    restrictions: "",
  });
  const [imageIds, setImageIds] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || !form.slug.trim()) {
      toast.error("请填写角色名称与标识");
      return;
    }
    setSaving(true);
    try {
      const ch = await characterApi.create({ ...form, image_ids: imageIds });
      toast.success(`角色「${ch.name}」已创建并发布 v1`);
      onCreated(ch);
    } catch {
      /* toasted */
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="animate-fade-up">
      <form onSubmit={submit} className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="角色名称">
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="例如：林晚"
            />
          </Field>
          <Field label="英文标识" hint="仅小写字母、数字、中划线">
            <Input
              value={form.slug}
              onChange={(e) => setForm({ ...form, slug: e.target.value.toLowerCase() })}
              placeholder="例如：lin-wan"
            />
          </Field>
        </div>
        <Field label="一句话简介">
          <Textarea
            value={form.summary}
            onChange={(e) => setForm({ ...form, summary: e.target.value })}
            placeholder="人物定位与背景"
          />
        </Field>
        <div className="grid gap-4 md:grid-cols-3">
          <Field label="外观设定">
            <Textarea
              value={form.appearance}
              onChange={(e) => setForm({ ...form, appearance: e.target.value })}
              placeholder="发型、服装、标志物"
            />
          </Field>
          <Field label="语气 / 说话方式">
            <Textarea
              value={form.tone}
              onChange={(e) => setForm({ ...form, tone: e.target.value })}
              placeholder="语速、口头禅、情绪"
            />
          </Field>
          <Field label="限制词 / 禁忌">
            <Textarea
              value={form.restrictions}
              onChange={(e) => setForm({ ...form, restrictions: e.target.value })}
              placeholder="禁止使用的表达与设定"
            />
          </Field>
        </div>
        <Field label="参考图（可多选）">
          <div className="flex flex-wrap gap-2">
            {images.length === 0 && (
              <span className="text-xs text-slate-400">图库暂无已授权图片，可先创建后再补图。</span>
            )}
            {images.map((img) => {
              const active = imageIds.includes(img.id);
              return (
                <button
                  type="button"
                  key={img.id}
                  onClick={() =>
                    setImageIds((ids) => (active ? ids.filter((x) => x !== img.id) : [...ids, img.id]))
                  }
                  className={
                    "relative h-20 w-16 overflow-hidden rounded-lg ring-2 transition " +
                    (active ? "ring-primary" : "ring-transparent hover:ring-slate-300")
                  }
                >
                  <img src={img.url} alt={img.filename} className="h-full w-full object-cover" />
                  {active && (
                    <span className="absolute inset-0 flex items-center justify-center bg-primary/30 text-xs text-white">
                      ✓
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </Field>
        <div className="flex justify-end gap-2">
          <Button type="submit" loading={saving}>
            发布 v1
          </Button>
        </div>
      </form>
    </Card>
  );
};

export default CharacterListPage;
