import api from "./client";
import type {
  Character,
  CoverJob,
  CropParams,
  ExportSnapshot,
  Line,
  References,
  RefImage,
  ReviewItem,
  Script,
  User,
} from "@/types";

export const authApi = {
  login: (username: string, password: string) =>
    api.post<{ token: string; user: User }>("/auth/login", { username, password }),
  me: () => api.get<User>("/auth/me"),
};

export const characterApi = {
  list: () => api.get<Character[]>("/characters").then((r) => r.data),
  get: (id: string) => api.get<Character>(`/characters/${id}`).then((r) => r.data),
  create: (body: Record<string, unknown>) =>
    api.post<Character>("/characters", body).then((r) => r.data),
  update: (id: string, body: { name?: string; summary?: string; expected_revision: number }) =>
    api.patch<Character>(`/characters/${id}`, body).then((r) => r.data),
  publishVersion: (id: string, body: Record<string, unknown>) =>
    api.post<Character["versions"][number]>(`/characters/${id}/versions`, body).then((r) => r.data),
  references: (id: string) =>
    api.get<References>(`/characters/${id}/references`).then((r) => r.data),
  retire: (
    id: string,
    body: { strategy: "soft_delete" | "replace"; expected_ref_count: number; replacement_character_id?: string | null },
  ) => api.post(`/characters/${id}/retire`, body).then((r) => r.data),
};

export const imageApi = {
  list: () => api.get<RefImage[]>("/images").then((r) => r.data),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.post<RefImage>("/images", form).then((r) => r.data);
  },
  revoke: (id: string) => api.post(`/images/${id}/revoke`).then((r) => r.data),
};

export const scriptApi = {
  list: () => api.get<Script[]>("/scripts").then((r) => r.data),
  get: (id: string) => api.get<Script>(`/scripts/${id}`).then((r) => r.data),
  create: (title: string, synopsis: string) =>
    api.post<Script>("/scripts", { title, synopsis }).then((r) => r.data),
  addScene: (id: string, body: { code: string; title: string; sort_order: number }) =>
    api.post<Script>(`/scripts/${id}/scenes`, body).then((r) => r.data),
  addCharacter: (
    id: string,
    body: { character_id: string; pin_mode: "pinned" | "latest"; pinned_version_id?: string | null },
  ) => api.post<Script>(`/scripts/${id}/characters`, body).then((r) => r.data),
  updateCharacter: (
    scriptId: string,
    refId: string,
    body: { character_id: string; pin_mode: "pinned" | "latest"; pinned_version_id?: string | null },
  ) => api.patch<Script>(`/scripts/${scriptId}/characters/${refId}`, body).then((r) => r.data),
  removeCharacter: (scriptId: string, refId: string) =>
    api.delete<Script>(`/scripts/${scriptId}/characters/${refId}`).then((r) => r.data),
  lines: (scriptId: string) =>
    api.get<Line[]>(`/scripts/${scriptId}/lines`).then((r) => r.data),
  createLine: (body: { scene_id: string; character_id: string; content: string }) =>
    api.post<Line>("/lines", body).then((r) => r.data),
  approve: (lineId: string) => api.post<Line>(`/lines/${lineId}/approve`).then((r) => r.data),
  reapprove: (lineId: string) => api.post<Line>(`/lines/${lineId}/reapprove`).then((r) => r.data),
  export: (scriptId: string, label: string) =>
    api.post<ExportSnapshot>(`/scripts/${scriptId}/exports`, { label }).then((r) => r.data),
  exports: () => api.get<ExportSnapshot[]>("/exports").then((r) => r.data),
};

export const coverApi = {
  list: (characterId: string) =>
    api.get<CoverJob[]>(`/characters/${characterId}/jobs`).then((r) => r.data),
  enqueue: (characterId: string, versionId: string, sourceImageId: string, crop: CropParams) =>
    api
      .post<CoverJob>(`/characters/${characterId}/versions/${versionId}/cover-jobs`, {
        source_image_id: sourceImageId,
        crop,
      })
      .then((r) => r.data),
  process: () => api.post<{ processed: number }>("/cover-jobs/process").then((r) => r.data),
};

export const reviewApi = {
  list: (statusFilter = "open") =>
    api.get<ReviewItem[]>(`/reviews?status_filter=${statusFilter}`).then((r) => r.data),
  resolve: (id: string) => api.post<ReviewItem>(`/reviews/${id}/resolve`).then((r) => r.data),
};

export const adminApi = {
  cleanup: (dryRun: boolean) =>
    api
      .post<{
        deleted_images: any[];
        deleted_assets: any[];
        protected_by_exports: any[];
        kept_in_use: any[];
        bytes_freed: number;
      }>(`/admin/cleanup?dry_run=${dryRun}`)
      .then((r) => r.data),
};
