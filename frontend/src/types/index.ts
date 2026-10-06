export type Role = "admin" | "editor" | "viewer";

export interface User {
  id: string;
  username: string;
  display_name: string;
  role: Role;
}

export interface RefImage {
  id: string;
  filename: string;
  url: string;
  mime_type: string;
  width: number;
  height: number;
  license_status: "licensed" | "revoked";
  created_at: string;
}

export interface CharacterVersion {
  id: string;
  character_id: string;
  version_no: number;
  appearance: string;
  tone: string;
  restrictions: string;
  change_note: string;
  created_at: string;
  images: RefImage[];
}

export interface Character {
  id: string;
  name: string;
  slug: string;
  summary: string;
  status: "active" | "retired";
  revision: number;
  current_version_id: string | null;
  current_version_no: number | null;
  active_cover_url: string | null;
  updated_at: string;
  created_at: string;
  versions: CharacterVersion[];
}

export interface ScriptCharacterRef {
  id: string;
  character_id: string;
  character_name: string;
  pin_mode: "pinned" | "latest";
  pinned_version_id: string | null;
  resolved_version_id: string;
  resolved_version_no: number;
  floating: boolean;
}

export interface Scene {
  id: string;
  code: string;
  title: string;
  sort_order: number;
}

export interface Script {
  id: string;
  title: string;
  synopsis: string;
  created_at: string;
  scenes: Scene[];
  characters: ScriptCharacterRef[];
}

export interface Line {
  id: string;
  scene_id: string;
  scene_code?: string | null;
  scene_title?: string | null;
  script_id?: string | null;
  character_id: string;
  character_name?: string | null;
  version_id: string;
  version_no?: number | null;
  content: string;
  approved: boolean;
  approved_at?: string | null;
  needs_recheck: boolean;
  recheck_reason?: string | null;
  interpretation_snapshot?: Record<string, unknown> | null;
  cover_url?: string | null;
  created_at: string;
}

export interface CropParams {
  x: number;
  y: number;
  width: number;
  height: number;
  target_width: number;
  target_height: number;
  force_fail?: boolean;
}

export interface CoverJob {
  id: string;
  character_id: string;
  version_id: string;
  source_image_id: string;
  crop_params: CropParams;
  status: "pending" | "processing" | "succeeded" | "failed" | "stale";
  attempts: number;
  error_message?: string | null;
  result_asset_id?: string | null;
  result_url?: string | null;
  created_at: string;
  processed_at?: string | null;
}

export interface ReviewItem {
  id: string;
  kind: "line_recheck" | "cover_failed" | "license_revoked" | "stale_cover";
  severity: "info" | "warning" | "critical";
  message: string;
  status: "open" | "resolved";
  character_id?: string | null;
  character_name?: string | null;
  version_id?: string | null;
  line_id?: string | null;
  scene_id?: string | null;
  scene_code?: string | null;
  scene_title?: string | null;
  job_id?: string | null;
  image_id?: string | null;
  created_at: string;
  resolved_at?: string | null;
}

export interface RefGroup {
  count: number;
  items: Array<Record<string, any>>;
}

export interface References {
  character_id: string;
  character_status: string;
  total: number;
  pinned_script_refs: RefGroup;
  floating_script_refs: number;
  approved_lines: RefGroup;
  pending_lines: RefGroup;
  cover_jobs: RefGroup;
  generated_assets: RefGroup;
  export_snapshots: RefGroup;
}

export interface ExportSnapshot {
  id: string;
  script_id: string;
  label: string;
  payload: Record<string, any>;
  asset_ids: string[];
  image_ids: string[];
  created_at: string;
}
