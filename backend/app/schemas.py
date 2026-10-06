"""Pydantic request/response schemas with strict validation."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


# ---------- auth ----------
class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: str
    username: str
    display_name: str
    role: str


class LoginResponse(BaseModel):
    token: str
    user: UserOut


# ---------- images ----------
class ImageOut(BaseModel):
    id: str
    filename: str
    url: str
    mime_type: str
    width: int
    height: int
    license_status: str
    created_at: datetime


class LicenseRevokeResponse(BaseModel):
    image: ImageOut
    affected_versions: list[str]
    affected_jobs: list[str]
    flagged_lines: int
    deactivated_assets: int
    review_id: str


# ---------- versions / characters ----------
class VersionCreate(BaseModel):
    appearance: str = Field(default="", max_length=20000)
    tone: str = Field(default="", max_length=20000)
    restrictions: str = Field(default="", max_length=20000)
    change_note: str = Field(default="", max_length=512)
    image_ids: list[str] = Field(default_factory=list, max_length=20)


class VersionOut(BaseModel):
    id: str
    character_id: str
    version_no: int
    appearance: str
    tone: str
    restrictions: str
    change_note: str
    created_by: str
    created_at: datetime
    images: list[ImageOut] = Field(default_factory=list)


class CharacterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    slug: str = Field(min_length=1, max_length=128, pattern=r"^[a-z0-9\-_]+$")
    summary: str = Field(default="", max_length=4000)
    appearance: str = Field(default="", max_length=20000)
    tone: str = Field(default="", max_length=20000)
    restrictions: str = Field(default="", max_length=20000)
    image_ids: list[str] = Field(default_factory=list, max_length=20)


class CharacterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    summary: str | None = Field(default=None, max_length=4000)
    expected_revision: int = Field(ge=1)


class CharacterOut(BaseModel):
    id: str
    name: str
    slug: str
    summary: str
    status: str
    revision: int
    current_version_id: str | None
    current_version_no: int | None = None
    active_cover_url: str | None = None
    created_by: str
    updated_at: datetime
    created_at: datetime
    versions: list[VersionOut] = Field(default_factory=list)


class PinInfo(BaseModel):
    pin_mode: Literal["pinned", "latest"]
    pinned_version_id: str | None = None


class ScriptCharacterRequest(BaseModel):
    character_id: str
    pin_mode: Literal["pinned", "latest"] = "latest"
    pinned_version_id: str | None = None

    @field_validator("pinned_version_id")
    @classmethod
    def _pin_requires_version(cls, v, info):
        values = info.data
        if values.get("pin_mode") == "pinned" and not v:
            raise ValueError("固定版本模式必须提供 pinned_version_id")
        return v


# ---------- scripts / scenes / lines ----------
class ScriptCreate(BaseModel):
    title: str = Field(min_length=1, max_length=128)
    synopsis: str = Field(default="", max_length=4000)


class SceneOut(BaseModel):
    id: str
    code: str
    title: str
    sort_order: int


class ScriptCharacterOut(BaseModel):
    id: str
    character_id: str
    character_name: str
    pin_mode: str
    pinned_version_id: str | None
    resolved_version_id: str
    resolved_version_no: int
    floating: bool


class ScriptOut(BaseModel):
    id: str
    title: str
    synopsis: str
    created_at: datetime
    scenes: list[SceneOut] = Field(default_factory=list)
    characters: list[ScriptCharacterOut] = Field(default_factory=list)


class SceneCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    title: str = Field(min_length=1, max_length=128)
    sort_order: int = 0


class LineCreate(BaseModel):
    scene_id: str
    character_id: str
    content: str = Field(min_length=1, max_length=20000)


class LineOut(BaseModel):
    id: str
    scene_id: str
    scene_code: str | None = None
    scene_title: str | None = None
    script_id: str | None = None
    character_id: str
    character_name: str | None = None
    version_id: str
    version_no: int | None = None
    content: str
    approved: bool
    approved_at: datetime | None = None
    needs_recheck: bool
    recheck_reason: str | None = None
    interpretation_snapshot: dict[str, Any] | None = None
    cover_url: str | None = None
    created_at: datetime


# ---------- cover jobs ----------
class CropParams(BaseModel):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    width: float = Field(gt=0.0, le=1.0)
    height: float = Field(gt=0.0, le=1.0)
    target_width: int = Field(default=1024, ge=64, le=4096)
    target_height: int = Field(default=1024, ge=64, le=4096)
    force_fail: bool = False  # demo hook to simulate material generation failure

    @field_validator("height")
    @classmethod
    def _bounds(cls, v, info):
        data = info.data
        if "y" in data and data["y"] + v > 1.0 + 1e-9:
            raise ValueError("裁切区域超出图片下边界")
        return v

    @field_validator("width")
    @classmethod
    def _bounds_w(cls, v, info):
        data = info.data
        if "x" in data and data["x"] + v > 1.0 + 1e-9:
            raise ValueError("裁切区域超出图片右边界")
        return v


class CoverJobCreate(BaseModel):
    source_image_id: str
    crop: CropParams


class CoverJobOut(BaseModel):
    id: str
    character_id: str
    version_id: str
    source_image_id: str
    crop_params: dict[str, Any]
    status: str
    attempts: int
    error_message: str | None
    result_asset_id: str | None
    result_url: str | None = None
    created_at: datetime
    processed_at: datetime | None = None


# ---------- exports ----------
class ExportCreate(BaseModel):
    label: str = Field(default="", max_length=256)


class ExportOut(BaseModel):
    id: str
    script_id: str
    label: str
    payload: dict[str, Any]
    asset_ids: list[str]
    image_ids: list[str]
    created_at: datetime


# ---------- review ----------
class ReviewOut(BaseModel):
    id: str
    kind: str
    severity: str
    message: str
    status: str
    character_id: str | None
    character_name: str | None = None
    version_id: str | None
    line_id: str | None
    scene_id: str | None
    scene_code: str | None = None
    scene_title: str | None = None
    job_id: str | None
    image_id: str | None
    created_at: datetime
    resolved_at: datetime | None = None


# ---------- references / retire / cleanup ----------
class RefGroup(BaseModel):
    count: int
    items: list[dict[str, Any]]


class ReferencesOut(BaseModel):
    character_id: str
    character_status: str
    total: int
    pinned_script_refs: RefGroup
    floating_script_refs: int
    approved_lines: RefGroup
    pending_lines: RefGroup
    cover_jobs: RefGroup
    generated_assets: RefGroup
    export_snapshots: RefGroup


class RetireRequest(BaseModel):
    strategy: Literal["soft_delete", "replace"]
    expected_ref_count: int = Field(ge=0)
    replacement_character_id: str | None = None


class RetireResponse(BaseModel):
    character_id: str
    status: str
    strategy: str
    migrated_script_refs: int
    migrated_pins: int
    preserved_approved_lines: int
    review_ids: list[str]


class CleanupReport(BaseModel):
    deleted_images: list[dict[str, Any]]
    deleted_assets: list[dict[str, Any]]
    protected_by_exports: list[dict[str, Any]]
    kept_in_use: list[dict[str, Any]]
    bytes_freed: int
