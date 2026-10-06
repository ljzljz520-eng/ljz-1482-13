import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { imageApi } from "@/api";
import type { RefImage } from "@/types";
import { Badge, Button, Card, EmptyState } from "@/components/ui";
import { useAuthStore } from "@/store/authStore";

const ImageLibraryPage = () => {
  const { user } = useAuthStore();
  const canEdit = user?.role === "admin" || user?.role === "editor";
  const isAdmin = user?.role === "admin";
  const [images, setImages] = useState<RefImage[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = async () => {
    setLoading(true);
    try {
      setImages(await imageApi.list());
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load();
  }, []);

  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    setUploading(true);
    try {
      for (const file of Array.from(files)) {
        await imageApi.upload(file);
      }
      toast.success(`已上传 ${files.length} 张参考图`);
      load();
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const revoke = async (img: RefImage) => {
    if (!window.confirm(`确认撤销「${img.filename}」的授权？相关任务、封面与台词将立即级联标记。`)) return;
    try {
      await imageApi.revoke(img.id);
      toast.success("授权已撤销，受影响场次已进入待复核");
      load();
    } catch {
      /* admin only */
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900">参考图库</h2>
          <p className="mt-1 text-sm text-slate-500">
            授权撤销会级联终止封面任务、下架封面并标记相关场次；仅管理员可执行。
          </p>
        </div>
        {canEdit && (
          <>
            <input
              ref={fileRef}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              multiple
              className="hidden"
              onChange={(e) => upload(e.target.files)}
            />
            <Button loading={uploading} onClick={() => fileRef.current?.click()}>
              上传参考图
            </Button>
          </>
        )}
      </div>

      {loading ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-48 animate-pulse rounded-2xl bg-slate-200/60" />
          ))}
        </div>
      ) : images.length === 0 ? (
        <EmptyState icon="🖼" title="图库为空" />
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {images.map((img) => (
            <Card key={img.id} className="group p-0 overflow-hidden">
              <div className="relative h-44">
                <img
                  src={img.url}
                  alt={img.filename}
                  className={
                    "h-full w-full object-cover transition " +
                    (img.license_status === "revoked" ? "grayscale" : "")
                  }
                />
                <div className="absolute left-2 top-2">
                  {img.license_status === "revoked" ? (
                    <Badge tone="red">授权已撤销</Badge>
                  ) : (
                    <Badge tone="green">已授权</Badge>
                  )}
                </div>
              </div>
              <div className="p-2.5">
                <p className="truncate text-xs font-medium text-slate-700" title={img.filename}>
                  {img.filename}
                </p>
                <p className="text-[10px] text-slate-400">
                  {img.width}×{img.height}
                </p>
                {isAdmin && img.license_status === "licensed" && (
                  <Button size="sm" variant="danger" className="mt-2 w-full" onClick={() => revoke(img)}>
                    撤销授权
                  </Button>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default ImageLibraryPage;
