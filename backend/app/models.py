"""SQLAlchemy ORM models for the character design workbench.

The schema captures four domains:
* identity & access (users)
* character content + immutable versions + source images
* production dependencies (scripts, scenes, approved lines, generated assets)
* lifecycle/operations (cover jobs, exports, review items, soft delete/retire)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def gen_uuid() -> str:
    return uuid.uuid4().hex


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    # For demo simplicity passwords are stored with a pbkdf2 hash; login also
    # returns a stable API token so the SPA can be used by QA without storage.
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # admin | editor | viewer
    api_token: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)


class Character(TimestampMixin, Base):
    __tablename__ = "characters"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)  # active | retired
    current_version_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("character_versions.id", ondelete="SET NULL"), nullable=True
    )
    # Monotonic revision used for optimistic concurrency control on edits.
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)

    versions: Mapped[list[CharacterVersion]] = relationship(
        "CharacterVersion",
        back_populates="character",
        foreign_keys="CharacterVersion.character_id",
    )
    current_version: Mapped[CharacterVersion | None] = relationship(
        "CharacterVersion", foreign_keys=[current_version_id], post_update=True
    )


class CharacterVersion(TimestampMixin, Base):
    __tablename__ = "character_versions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    character_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("characters.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    appearance: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tone: Mapped[str] = mapped_column(Text, default="", nullable=False)
    restrictions: Mapped[str] = mapped_column(Text, default="", nullable=False)
    change_note: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)

    character: Mapped[Character] = relationship(
        "Character", back_populates="versions", foreign_keys=[character_id]
    )
    images: Mapped[list[VersionImage]] = relationship(
        "VersionImage", back_populates="version", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("character_id", "version_no", name="uq_version_character_no"),
    )


class ReferenceImage(TimestampMixin, Base):
    """Original source artwork whose license/authorization can be revoked."""
    __tablename__ = "reference_images"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), default="image/png", nullable=False)
    width: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    height: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    license_status: Mapped[str] = mapped_column(
        String(16), default="licensed", nullable=False
    )  # licensed | revoked
    uploaded_by: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)

    version_images: Mapped[list[VersionImage]] = relationship(back_populates="image")


class VersionImage(TimestampMixin, Base):
    """Association of a source image to a specific immutable version."""
    __tablename__ = "version_images"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    version_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("character_versions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    image_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("reference_images.id", ondelete="RESTRICT"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), default="reference", nullable=False)

    version: Mapped[CharacterVersion] = relationship(back_populates="images")
    image: Mapped[ReferenceImage] = relationship(back_populates="version_images")


class Script(TimestampMixin, Base):
    __tablename__ = "scripts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    synopsis: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)

    characters: Mapped[list[ScriptCharacter]] = relationship(
        back_populates="script", cascade="all, delete-orphan"
    )
    scenes: Mapped[list[Scene]] = relationship(back_populates="script", cascade="all, delete-orphan")


class ScriptCharacter(TimestampMixin, Base):
    """A script's dependency on a character version.

    pin_mode = pinned  -> depends on exact version_id (frozen interpretation)
    pin_mode = latest  -> floats to character.current_version_id
    """
    __tablename__ = "script_characters"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    script_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("scripts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    character_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("characters.id", ondelete="RESTRICT"), nullable=False
    )
    pin_mode: Mapped[str] = mapped_column(String(16), default="latest", nullable=False)
    pinned_version_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("character_versions.id", ondelete="SET NULL"), nullable=True
    )

    script: Mapped[Script] = relationship(back_populates="characters")

    __table_args__ = (
        UniqueConstraint("script_id", "character_id", name="uq_script_character"),
    )


class Scene(TimestampMixin, Base):
    __tablename__ = "scenes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    script_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("scripts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    script: Mapped[Script] = relationship(back_populates="scenes")
    lines: Mapped[list[Line]] = relationship(back_populates="scene", cascade="all, delete-orphan")


class Line(TimestampMixin, Base):
    __tablename__ = "lines"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    scene_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("scenes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    character_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("characters.id", ondelete="RESTRICT"), nullable=False
    )
    # Exact version the line was written/approved against (snapshot source).
    version_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("character_versions.id", ondelete="RESTRICT"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Frozen interpretation taken at approval time; never silently mutated.
    interpretation_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    needs_recheck: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    recheck_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)

    scene: Mapped[Scene] = relationship(back_populates="lines")


class CoverJob(TimestampMixin, Base):
    """Asynchronous task deriving a cover image from a source + crop params."""
    __tablename__ = "cover_jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    character_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("characters.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("character_versions.id", ondelete="CASCADE"), nullable=False
    )
    source_image_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("reference_images.id", ondelete="RESTRICT"), nullable=False
    )
    crop_params: Mapped[dict] = mapped_column(JSON, nullable=False)
    crop_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default="pending", index=True, nullable=False
    )  # pending | processing | succeeded | failed | stale
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    result_asset_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("generated_assets.id", ondelete="SET NULL"), nullable=True
    )
    requested_by: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    result_asset: Mapped[GeneratedAsset | None] = relationship("GeneratedAsset", foreign_keys=[result_asset_id])

    __table_args__ = (
        UniqueConstraint("character_id", "version_id", "crop_hash", name="uq_cover_job_dedup"),
    )


class GeneratedAsset(TimestampMixin, Base):
    __tablename__ = "generated_assets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    kind: Mapped[str] = mapped_column(String(32), default="cover", nullable=False)
    character_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("characters.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("character_versions.id", ondelete="CASCADE"), nullable=False
    )
    source_image_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("reference_images.id", ondelete="SET NULL"), nullable=True
    )
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    crop_params: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # True while attached as the current cover of a character card.
    is_active_cover: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    job_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("cover_jobs.id"), nullable=True)
    created_by: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)


class ExportSnapshot(TimestampMixin, Base):
    """Immutable export bundle; keeps historical referenced objects alive."""
    __tablename__ = "export_snapshots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    script_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("scripts.id", ondelete="RESTRICT"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)

    assets: Mapped[list[ExportAsset]] = relationship(
        back_populates="export", cascade="all, delete-orphan"
    )
    images: Mapped[list[ExportImage]] = relationship(
        back_populates="export", cascade="all, delete-orphan"
    )


class ExportAsset(TimestampMixin, Base):
    __tablename__ = "export_assets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    export_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("export_snapshots.id", ondelete="CASCADE"), index=True, nullable=False
    )
    asset_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("generated_assets.id", ondelete="RESTRICT"), nullable=False
    )

    export: Mapped[ExportSnapshot] = relationship(back_populates="assets")


class ExportImage(TimestampMixin, Base):
    __tablename__ = "export_images"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    export_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("export_snapshots.id", ondelete="CASCADE"), index=True, nullable=False
    )
    image_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("reference_images.id", ondelete="RESTRICT"), nullable=False
    )

    export: Mapped[ExportSnapshot] = relationship(back_populates="images")


class ReviewItem(TimestampMixin, Base):
    __tablename__ = "review_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    # line_recheck | cover_failed | license_revoked | stale_cover
    severity: Mapped[str] = mapped_column(String(16), default="warning", nullable=False)
    character_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("characters.id", ondelete="CASCADE"), nullable=True
    )
    version_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    line_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("lines.id", ondelete="CASCADE"), nullable=True
    )
    scene_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("scenes.id", ondelete="CASCADE"), nullable=True
    )
    job_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    image_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    message: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="open", index=True, nullable=False)
    # open | resolved
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("kind", "line_id", "job_id", "image_id", name="uq_review_dedup"),
    )
