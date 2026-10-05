export type Role = "admin" | "editor" | "viewer";
export type RefMode = "pinned" | "floating";
export type JobState = "pending" | "processing" | "succeeded" | "failed" | "stale" | "cancelled";
export type CharacterStatus = "active" | "soft_deleted" | "retired";

export interface User {
  id: string;
  username: string;
  display_name: string;
  role: Role;
}

export interface ReferenceImage {
  id: string;
  image_asset_id: string;
  caption: string;
  url: string;
  license_granted: boolean;
  license_note: string;
  width: number;
  height: number;
}

export interface CharacterVersion {
  id: string;
  version: number;
  appearance: string;
  tone: string;
  restrictions: string;
  change_note: string;
  created_by_name?: string | null;
  created_at: string;
  images: ReferenceImage[];
}

export interface Character {
  id: string;
  name: string;
  code: string;
  status: CharacterStatus;
  latest_version: number;
  lock_version: number;
  created_at: string;
  updated_at: string;
  latest?: CharacterVersion | null;
  pinned_count: number;
  floating_count: number;
  versions?: CharacterVersion[];
}

export interface ScriptRef {
  link_id?: string;
  script_id: string;
  character_id?: string;
  title: string;
  scene_code: string;
  ref_mode: RefMode;
  pinned_version: number | null;
  effective_version: number | null;
  latest_version: number;
  approved_text: string | null;
  approved_version: number | null;
  needs_review: boolean;
}

export interface Script {
  id: string;
  title: string;
  scene_code: string;
  content: string;
  created_at: string;
  updated_at: string;
  links: ScriptRef[];
}

export interface RetireDryRun {
  mode: "retire" | "soft_delete";
  blocking_scripts: ScriptRef[];
  generated_assets: number;
  export_snapshots: number;
  floating_links: number;
  pinned_links: number;
  recommendation: string;
}

export interface ImageAsset {
  id: string;
  url: string;
  original_filename: string;
  width: number;
  height: number;
  license_granted: boolean;
  license_note: string;
  created_at: string;
}

export interface GcCandidate {
  asset: ImageAsset;
  referenced_by_reference: boolean;
  referenced_by_generated_source: boolean;
  referenced_by_generated_output: boolean;
  referenced_by_pending_job: boolean;
  referenced_by_export: boolean;
  deletable: boolean;
}

export interface CoverJob {
  id: string;
  character_version_id: string;
  source_asset_id: string;
  output_asset_id: string | null;
  output_url: string | null;
  state: JobState;
  crop_x: number;
  crop_y: number;
  crop_w: number;
  crop_h: number;
  target_width: number;
  target_height: number;
  params_fingerprint: string;
  attempts: number;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface LicenseImpact {
  image: ImageAsset;
  affected_versions: {
    character_id: string;
    character_name: string;
    version_id: string;
    version: number;
  }[];
  affected_scenes: ScriptRef[];
  pending_cover_jobs: number;
  export_snapshots: number;
  generated_covers: number;
}

export interface ExportRecord {
  id: string;
  label: string;
  script_id: string | null;
  created_by_name?: string | null;
  created_at: string;
  character_refs: {
    character_id: string;
    character_name: string;
    version_id: string;
    version: number;
  }[];
  image_count: number;
}

export type ReviewKind =
  | "edit_conflict"
  | "license_revoked"
  | "generation_failed"
  | "retired_referenced"
  | "approved_drift";

export interface ReviewItem {
  id: string;
  kind: ReviewKind;
  state: "open" | "resolved";
  title: string;
  detail: string;
  character_id: string | null;
  script_id: string | null;
  job_id: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface Dashboard {
  affected_scenes: ScriptRef[];
  review_items: ReviewItem[];
  failed_jobs: CoverJob[];
  soft_deleted_characters: Character[];
}
