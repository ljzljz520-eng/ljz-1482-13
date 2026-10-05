import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import toast from "react-hot-toast";
import {
  getCharacter,
  restoreCharacter,
} from "../api/endpoints";
import type { Character } from "../types";
import { useAuth, canEdit, isAdmin } from "../store/auth";
import { Badge, Button, Card, Modal, PageHeader, SkeletonRows } from "../components/ui";
import NewVersionModal from "../components/NewVersionModal";
import RetireFlow from "../components/RetireFlow";
import CoverJobPanel from "../components/CoverJobPanel";
import { useMotionAllowed } from "../hooks/useMotionAllowed";

type Tab = "versions" | "cover";

export default function CharacterDetail() {
  const { id = "" } = useParams();
  const { user } = useAuth();
  const [character, setCharacter] = useState<Character | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("versions");
  const [newVersionOpen, setNewVersionOpen] = useState(false);
  const [retireOpen, setRetireOpen] = useState(false);
  const [restoring, setRestoring] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setCharacter(await getCharacter(id));
    } catch (e) {
      toast.error((e as { friendlyMessage?: string }).friendlyMessage ?? "角色加载失败");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading || !character) {
    return (
      <Card>
        <SkeletonRows rows={5} />
      </Card>
    );
  }

  const inactive = character.status !== "active";

  return (
    <div>
      <PageHeader
        title={
          <span className="flex items-center gap-2">
            {character.name}
            <span className="font-mono text-sm font-normal text-slate-400">{character.code}</span>
            {character.status === "soft_deleted" && <Badge tone="amber">软删除</Badge>}
            {character.status === "retired" && <Badge tone="slate">已退役</Badge>}
            <Badge tone="blue">最新 v{character.latest_version}</Badge>
            <span className="text-xs font-normal text-slate-400">lock_version={character.lock_version}</span>
          </span>
        }
        subtitle="版本不可变：历史版本永久保留，脚本可固定任意一版或跟随最新"
        actions={
          <>
            <Link to="/" className="text-sm text-slate-500 hover:text-blue-600">
              ← 返回列表
            </Link>
            {canEdit(user) && !inactive && (
              <Button onClick={() => setNewVersionOpen(true)}>＋ 发布新版本</Button>
            )}
            {isAdmin(user) && character.status === "soft_deleted" && (
              <Button
                variant="secondary"
                loading={restoring}
                onClick={async () => {
                  setRestoring(true);
                  try {
                    setCharacter(await restoreCharacter(character.id));
                    toast.success("角色已恢复");
                  } catch (e) {
                    toast.error((e as { friendlyMessage?: string }).friendlyMessage ?? "恢复失败");
                  } finally {
                    setRestoring(false);
                  }
                }}
              >
                恢复角色
              </Button>
            )}
            {isAdmin(user) && !inactive && (
              <Button variant="danger" onClick={() => setRetireOpen(true)}>
                退役 / 软删除
              </Button>
            )}
          </>
        }
      />

      <div className="mb-4 flex gap-1 rounded-2xl bg-white p-1 ring-1 ring-slate-200">
        {([
          ["versions", "版本时间线"],
          ["cover", "封面派生任务"],
        ] as const).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex-1 rounded-xl px-4 py-2 text-sm font-medium transition ${
              tab === key ? "bg-blue-600 text-white shadow-sm" : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "versions" ? (
        <div className="relative">
          <div className="absolute bottom-4 left-[19px] top-4 w-px bg-gradient-to-b from-blue-200 via-slate-200 to-transparent" />
          <div className="space-y-4">
            {character.versions?.map((v, idx) => (
              <VersionCard key={v.id} version={v} isLatest={idx === 0} character={character} />
            ))}
          </div>
        </div>
      ) : (
        <Card className="p-5">
          <CoverJobPanel character={character} />
        </Card>
      )}

      {newVersionOpen && (
        <NewVersionModal
          character={character}
          onClose={() => setNewVersionOpen(false)}
          onCreated={() => {
            setNewVersionOpen(false);
            load();
          }}
        />
      )}

      <Modal open={retireOpen} onClose={() => setRetireOpen(false)} title="退役前反向引用核查" wide>
        <RetireFlow
          character={character}
          onClose={() => setRetireOpen(false)}
          onDone={(c) => {
            setRetireOpen(false);
            setCharacter(c);
          }}
        />
      </Modal>
    </div>
  );
}

function VersionCard({
  version,
  isLatest,
  character,
}: {
  version: Character["versions"] extends (infer V)[] | undefined ? V : never;
  isLatest: boolean;
  character: Character;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const animate = useMotionAllowed(ref);

  return (
    <div
      ref={ref}
      className={`relative ml-10 rounded-2xl border bg-white p-5 shadow-card transition ${
        isLatest ? "border-blue-200 ring-1 ring-blue-100" : "border-slate-200"
      } ${animate && isLatest ? "cs-card-in" : ""}`}
    >
      <span
        className={`absolute -left-[29px] top-6 flex h-5 w-5 items-center justify-center rounded-full ring-4 ring-white ${
          isLatest ? "bg-blue-600" : "bg-slate-300"
        }`}
      >
        <span className="h-1.5 w-1.5 rounded-full bg-white" />
      </span>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h3 className="text-base font-semibold text-slate-900">v{version.version}</h3>
        {isLatest && <Badge tone="green">当前最新</Badge>}
        <span className="text-xs text-slate-400">
          {version.created_by_name} · {new Date(version.created_at).toLocaleString("zh-CN")}
        </span>
        {version.change_note && <Badge tone="slate">{version.change_note}</Badge>}
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <InfoBlock label="外观" value={version.appearance} />
        <InfoBlock label="语气" value={version.tone} />
        <InfoBlock label="限制词" value={version.restrictions} danger />
      </div>

      {version.images.length > 0 && (
        <div className="mt-4">
          <p className="mb-2 text-xs font-semibold text-slate-500">
            参考图（{version.images.length}）· 属于此不可变版本
          </p>
          <div className="flex flex-wrap gap-3">
            {version.images.map((img) => (
              <div key={img.id} className="group relative w-28">
                <div
                  className={`h-28 overflow-hidden rounded-xl ring-1 ring-slate-200 ${
                    !img.license_granted ? "grayscale" : ""
                  }`}
                >
                  <img src={img.url} alt={img.caption} className="h-full w-full object-cover transition group-hover:scale-105" />
                </div>
                <p className="mt-1 truncate text-[11px] text-slate-500">{img.caption || "参考图"}</p>
                {!img.license_granted && (
                  <span className="absolute left-1 top-1">
                    <Badge tone="red">授权撤销</Badge>
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {!isLatest && (
        <p className="mt-3 text-xs text-slate-400">
          该版本内容已冻结；固定引用此版本（v{version.version}）的场次不会受到 v{character.latest_version} 影响。
        </p>
      )}
    </div>
  );
}

function InfoBlock({ label, value, danger }: { label: string; value: string; danger?: boolean }) {
  return (
    <div className={`rounded-xl px-3 py-2.5 ${danger ? "bg-rose-50/60" : "bg-slate-50"}`}>
      <p className={`text-xs font-semibold ${danger ? "text-rose-600" : "text-slate-500"}`}>{label}</p>
      <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-slate-700">{value || "—"}</p>
    </div>
  );
}
