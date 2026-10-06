import { useState } from "react";
import toast from "react-hot-toast";
import { adminApi } from "@/api";
import { Badge, Button, Card } from "@/components/ui";
import { useAuthStore } from "@/store/authStore";

interface Report {
  deleted_images: any[];
  deleted_assets: any[];
  protected_by_exports: any[];
  kept_in_use: any[];
  bytes_freed: number;
}

const empty: Report = {
  deleted_images: [],
  deleted_assets: [],
  protected_by_exports: [],
  kept_in_use: [],
  bytes_freed: 0,
};

const AdminPage = () => {
  const { user } = useAuthStore();
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);

  if (user?.role !== "admin") {
    return (
      <Card>
        <p className="text-sm text-slate-600">⛔ 仅管理员可访问存储清理功能。服务端会独立校验权限。</p>
      </Card>
    );
  }

  const run = async (dryRun: boolean) => {
    setLoading(true);
    try {
      const r = await adminApi.cleanup(dryRun);
      setReport(r);
      if (dryRun) toast.success("已生成清理预览，尚未删除任何文件");
      else toast.success(`清理完成，释放 ${(r.bytes_freed / 1024).toFixed(1)} KB`);
    } finally {
      setLoading(false);
    }
  };

  const r = report ?? empty;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900">存储清理（管理员）</h2>
        <p className="mt-1 text-sm text-slate-500">
          清理无引用对象时，会始终保留仍被历史导出快照使用的图片与素材。建议先预览再执行。
        </p>
      </div>

      <div className="flex gap-2">
        <Button variant="secondary" loading={loading} onClick={() => run(true)}>
          生成清理预览（dry-run）
        </Button>
        <Button
          variant="danger"
          loading={loading}
          onClick={() => {
            if (window.confirm("确认物理删除未引用对象？被历史导出保护的对象不会删除。")) run(false);
          }}
        >
          执行物理清理
        </Button>
      </div>

      {report && (
        <div className="grid gap-4 lg:grid-cols-2">
          <ReportCard
            title="将删除的来源图"
            tone="red"
            rows={r.deleted_images.map((x) => x.filename ?? x.id)}
            emptyHint="无"
          />
          <ReportCard
            title="将删除的派生素材"
            tone="red"
            rows={r.deleted_assets.map((x) => `${x.id?.slice(0, 8)} · ${x.kind}`)}
            emptyHint="无"
          />
          <ReportCard
            title="被历史导出保护（保留）"
            tone="green"
            rows={r.protected_by_exports.map((x) => `${x.filename ?? x.id?.slice?.(0, 12) ?? x.id} · ${x.reason}`)}
            emptyHint="无"
          />
          <ReportCard
            title="仍被版本/任务使用（保留）"
            tone="blue"
            rows={r.kept_in_use.map((x) => `${x.filename ?? x.id?.slice?.(0, 12) ?? x.id} · ${x.reason}`)}
            emptyHint="无"
          />
        </div>
      )}
    </div>
  );
};

const ReportCard = ({
  title,
  rows,
  emptyHint,
  tone,
}: {
  title: string;
  rows: string[];
  emptyHint: string;
  tone: "red" | "green" | "blue";
}) => (
  <Card>
    <div className="mb-2 flex items-center justify-between">
      <h3 className="text-sm font-bold text-slate-800">{title}</h3>
      <Badge tone={tone}>{rows.length}</Badge>
    </div>
    {rows.length === 0 ? (
      <p className="text-xs text-slate-400">{emptyHint}</p>
    ) : (
      <ul className="max-h-56 space-y-1 overflow-y-auto text-xs text-slate-600">
        {rows.map((row, i) => (
          <li key={i} className="truncate rounded bg-slate-50 px-2 py-1">
            {row}
          </li>
        ))}
      </ul>
    )}
  </Card>
);

export default AdminPage;
