import api from "./client";
import type {
  Character,
  CoverJob,
  Dashboard,
  ExportRecord,
  GcCandidate,
  ImageAsset,
  LicenseImpact,
  RefMode,
  RetireDryRun,
  Script,
  User,
} from "../types";

// ---------- auth ----------
export const login = (username: string, password: string) =>
  api.post<{ access_token: string; user: User }>("/auth/login", { username, password }).then((r) => r.data);
export const me = () => api.get<User>("/auth/me").then((r) => r.data);

// ---------- characters ----------
export const listCharacters = (includeInactive = false) =>
  api
    .get<Character[]>("/characters", { params: { include_inactive: includeInactive } })
    .then((r) => r.data);
export const getCharacter = (id: string) =>
  api.get<Character>(`/characters/${id}`).then((r) => r.data);
export const createCharacter = (body: {
  name: string;
  code: string;
  appearance: string;
  tone: string;
  restrictions: string;
}) => api.post<Character>("/characters", body).then((r) => r.data);

export const appendVersion = (
  id: string,
  body: {
    appearance: string;
    tone: string;
    restrictions: string;
    change_note: string;
    image_asset_ids: string[];
    expected_lock_version: number;
  }
) => api.post<Character>(`/characters/${id}/versions`, body).then((r) => r.data);

export const dryRunRetire = (id: string, mode: "retire" | "soft_delete") =>
  api
    .get<RetireDryRun>(`/characters/${id}/references`, { params: { mode } })
    .then((r) => r.data);

export const retireCharacter = (
  id: string,
  body: {
    expected_lock_version: number;
    replacement_character_id?: string | null;
    mode: "soft_delete" | "retire";
  }
) => api.post<Character>(`/characters/${id}/retire`, body).then((r) => r.data);

export const restoreCharacter = (id: string) =>
  api.post<Character>(`/characters/${id}/restore`).then((r) => r.data);

export const listCharacterCoverJobs = (id: string) =>
  api.get<CoverJob[]>(`/characters/${id}/cover-jobs`).then((r) => r.data);

// ---------- scripts ----------
export const listScripts = () => api.get<Script[]>("/scripts").then((r) => r.data);
export const createScript = (body: {
  title: string;
  scene_code: string;
  content: string;
  links: {
    character_id: string;
    ref_mode: RefMode;
    pinned_version_id?: string | null;
    approved_text?: string | null;
  }[];
}) => api.post<Script>("/scripts", body).then((r) => r.data);
export const updateScript = (
  id: string,
  body: Partial<Pick<Script, "title" | "scene_code" | "content">>
) => api.patch<Script>(`/scripts/${id}`, body).then((r) => r.data);
export const addScriptLink = (
  scriptId: string,
  body: { character_id: string; ref_mode: RefMode; pinned_version_id?: string | null }
) => api.post<Script>(`/scripts/${scriptId}/links`, body).then((r) => r.data);
export const removeScriptLink = (linkId: string) =>
  api.delete(`/scripts/links/${linkId}`).then((r) => r.data);
export const approveLine = (
  linkId: string,
  approved_text: string
) =>
  api
    .post<Script>(`/scripts/links/${linkId}/approve`, { link_id: linkId, approved_text })
    .then((r) => r.data);
export const reconfirmLine = (linkId: string) =>
  api.post<Script>(`/scripts/links/${linkId}/reconfirm`).then((r) => r.data);
export const switchLinkMode = (
  linkId: string,
  ref_mode: RefMode,
  pinned_version_id?: string | null
) =>
  api
    .post<Script>(`/scripts/links/${linkId}/mode`, { ref_mode, pinned_version_id })
    .then((r) => r.data);

// ---------- images ----------
export const uploadImage = (file: File, license_note: string) => {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("license_note", license_note);
  return api
    .post<ImageAsset>("/images", fd, { headers: { "Content-Type": "multipart/form-data" } })
    .then((r) => r.data);
};
export const setLicense = (
  imageId: string,
  license_granted: boolean,
  license_note: string
) =>
  api
    .post<LicenseImpact>(`/images/${imageId}/license`, { license_granted, license_note })
    .then((r) => r.data);
export const gcCandidates = () =>
  api.get<GcCandidate[]>("/images/gc-candidates").then((r) => r.data);
export const runGc = () => api.delete<{ deleted: string[]; kept: string[] }>("/images/gc-run").then((r) => r.data);

// ---------- cover jobs ----------
export const createCoverJob = (body: {
  character_version_id: string;
  source_asset_id: string;
  crop_x: number;
  crop_y: number;
  crop_w: number;
  crop_h: number;
  target_width: number;
  target_height: number;
  force_fail?: boolean;
}) => api.post<CoverJob>("/cover-jobs", body).then((r) => r.data);
export const getCoverJob = (id: string) =>
  api.get<CoverJob>(`/cover-jobs/${id}`).then((r) => r.data);
export const retryCoverJob = (id: string) =>
  api.post<CoverJob>(`/cover-jobs/${id}/retry`).then((r) => r.data);

// ---------- exports ----------
export const listExports = () => api.get<ExportRecord[]>("/exports").then((r) => r.data);
export const createExport = (body: { label: string; script_id?: string | null }) =>
  api.post<ExportRecord>("/exports", body).then((r) => r.data);

// ---------- dashboard ----------
export const getDashboard = () => api.get<Dashboard>("/dashboard").then((r) => r.data);
export const resolveReview = (id: string) =>
  api.post(`/review-items/${id}/resolve`).then((r) => r.data);
