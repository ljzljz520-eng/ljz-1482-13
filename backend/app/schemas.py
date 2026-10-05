"""Pydantic DTO：严格校验入参，拒绝非法 Payload。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models import JobState, RefMode, ReviewKind, ReviewState, RoleName


# ---------- auth ----------
class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str
    role: RoleName

    model_config = {"from_attributes": True}


# ---------- characters / versions ----------
class CharacterCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$")
    appearance: str = Field(default="", max_length=8000)
    tone: str = Field(default="", max_length=8000)
    restrictions: str = Field(default="", max_length=8000)


class VersionCreateIn(BaseModel):
    appearance: str = Field(max_length=8000)
    tone: str = Field(max_length=8000)
    restrictions: str = Field(max_length=8000)
    change_note: str = Field(default="", max_length=512)
    image_asset_ids: list[uuid.UUID] = Field(default_factory=list)
    expected_lock_version: int = Field(ge=1)


class VersionOut(BaseModel):
    id: uuid.UUID
    version: int
    appearance: str
    tone: str
    restrictions: str
    change_note: str
    created_by_name: str | None = None
    created_at: datetime
    images: list["ReferenceImageOut"] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ReferenceImageOut(BaseModel):
    id: uuid.UUID
    image_asset_id: uuid.UUID
    caption: str
    url: str
    license_granted: bool
    license_note: str
    width: int
    height: int


class CharacterOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    status: str
    latest_version: int
    lock_version: int
    created_at: datetime
    updated_at: datetime
    latest: VersionOut | None = None
    pinned_count: int = 0
    floating_count: int = 0


class CharacterDetailOut(CharacterOut):
    versions: list[VersionOut] = Field(default_factory=list)


class RetireIn(BaseModel):
    expected_lock_version: int = Field(ge=1)
    replacement_character_id: uuid.UUID | None = None
    mode: Literal["soft_delete", "retire"] = "retire"


class RetireDryRunOut(BaseModel):
    mode: str
    blocking_scripts: list["ScriptRefOut"] = Field(default_factory=list)
    generated_assets: int = 0
    export_snapshots: int = 0
    floating_links: int = 0
    pinned_links: int = 0
    recommendation: str = ""


# ---------- images ----------
class ImageOut(BaseModel):
    id: uuid.UUID
    url: str
    original_filename: str
    width: int
    height: int
    license_granted: bool
    license_note: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LicenseIn(BaseModel):
    license_granted: bool
    license_note: str = Field(default="", max_length=512)


class LicenseImpactOut(BaseModel):
    image: ImageOut
    affected_versions: list["VersionBriefOut"]
    affected_scenes: list["ScriptRefOut"]
    pending_cover_jobs: int
    export_snapshots: int
    generated_covers: int


class VersionBriefOut(BaseModel):
    character_id: uuid.UUID
    character_name: str
    version_id: uuid.UUID
    version: int


class GcCandidateOut(BaseModel):
    asset: ImageOut
    referenced_by_reference: bool
    referenced_by_generated_source: bool
    referenced_by_generated_output: bool
    referenced_by_pending_job: bool
    referenced_by_export: bool
    deletable: bool


# ---------- scripts ----------
class ScriptLinkIn(BaseModel):
    character_id: uuid.UUID
    ref_mode: RefMode
    pinned_version_id: uuid.UUID | None = None
    approved_text: str | None = Field(default=None, max_length=8000)

    @field_validator("pinned_version_id")
    @classmethod
    def _check_pin(cls, v, info):
        mode = info.data.get("ref_mode")
        if mode == RefMode.pinned and v is None:
            raise ValueError("固定版本引用必须提供 pinned_version_id")
        if mode == RefMode.floating and v is not None:
            raise ValueError("跟随最新版引用不能携带 pinned_version_id")
        return v


class ScriptCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    scene_code: str = Field(min_length=1, max_length=64)
    content: str = Field(default="", max_length=20000)
    links: list[ScriptLinkIn] = Field(default_factory=list)


class ScriptUpdateIn(BaseModel):
    title: str | None = Field(default=None, max_length=256)
    scene_code: str | None = Field(default=None, max_length=64)
    content: str | None = Field(default=None, max_length=20000)


class ScriptRefOut(BaseModel):
    link_id: uuid.UUID | None = None
    script_id: uuid.UUID
    character_id: uuid.UUID | None = None
    title: str
    scene_code: str
    ref_mode: RefMode
    pinned_version: int | None
    effective_version: int | None
    latest_version: int
    approved_text: str | None
    approved_version: int | None
    needs_review: bool


class ScriptOut(BaseModel):
    id: uuid.UUID
    title: str
    scene_code: str
    content: str
    created_at: datetime
    updated_at: datetime
    links: list[ScriptRefOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ApproveIn(BaseModel):
    link_id: uuid.UUID
    approved_text: str = Field(min_length=1, max_length=8000)


# ---------- cover jobs ----------
class CoverJobIn(BaseModel):
    character_version_id: uuid.UUID
    source_asset_id: uuid.UUID
    crop_x: float = Field(ge=0, le=1)
    crop_y: float = Field(ge=0, le=1)
    crop_w: float = Field(gt=0, le=1)
    crop_h: float = Field(gt=0, le=1)
    target_width: int = Field(default=640, ge=64, le=2048)
    target_height: int = Field(default=360, ge=64, le=2048)
    force_fail: bool = False

    @field_validator("crop_w", "crop_h")
    @classmethod
    def _bounds(cls, v, info):
        x = info.data.get("crop_x", 0)
        y = info.data.get("crop_y", 0)
        axis = "crop_x" if info.field_name == "crop_w" else "crop_y"
        start = x if axis == "crop_x" else y
        if start + v > 1 + 1e-9:
            raise ValueError("裁切区域超出原图范围")
        return v


class CoverJobOut(BaseModel):
    id: uuid.UUID
    character_version_id: uuid.UUID
    source_asset_id: uuid.UUID
    output_asset_id: uuid.UUID | None
    output_url: str | None = None
    state: JobState
    crop_x: float
    crop_y: float
    crop_w: float
    crop_h: float
    target_width: int
    target_height: int
    params_fingerprint: str
    attempts: int
    last_error: str | None
    created_at: datetime
    updated_at: datetime


# ---------- exports ----------
class ExportIn(BaseModel):
    label: str = Field(min_length=1, max_length=256)
    script_id: uuid.UUID | None = None


class ExportOut(BaseModel):
    id: uuid.UUID
    label: str
    script_id: uuid.UUID | None
    created_by_name: str | None
    created_at: datetime
    character_refs: list[VersionBriefOut] = Field(default_factory=list)
    image_count: int = 0


# ---------- review ----------
class ReviewOut(BaseModel):
    id: uuid.UUID
    kind: ReviewKind
    state: ReviewState
    title: str
    detail: str
    character_id: uuid.UUID | None
    script_id: uuid.UUID | None
    job_id: uuid.UUID | None
    created_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class DashboardOut(BaseModel):
    affected_scenes: list[ScriptRefOut]
    review_items: list[ReviewOut]
    failed_jobs: list[CoverJobOut]
    soft_deleted_characters: list[CharacterOut]


TokenOut.model_rebuild()
VersionOut.model_rebuild()
RetireDryRunOut.model_rebuild()
LicenseImpactOut.model_rebuild()
