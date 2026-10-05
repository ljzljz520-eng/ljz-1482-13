"""关系库模型：角色不可变版本化、引用、素材任务、导出快照与复核队列。"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class RoleName(str, enum.Enum):
    admin = "admin"
    editor = "editor"
    viewer = "viewer"


class RefMode(str, enum.Enum):
    """脚本引用角色的两种方式：固定版本 / 跟随最新。"""
    pinned = "pinned"
    floating = "floating"


class CharacterStatus(str, enum.Enum):
    active = "active"
    soft_deleted = "soft_deleted"
    retired = "retired"


class JobState(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    succeeded = "succeeded"
    failed = "failed"
    stale = "stale"  # 旧任务晚到，结果被策略性丢弃
    cancelled = "cancelled"


class ReviewKind(str, enum.Enum):
    edit_conflict = "edit_conflict"
    license_revoked = "license_revoked"
    generation_failed = "generation_failed"
    retired_referenced = "retired_referenced"
    approved_drift = "approved_drift"


class ReviewState(str, enum.Enum):
    open = "open"
    resolved = "resolved"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[RoleName] = mapped_column(Enum(RoleName), nullable=False, default=RoleName.editor)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[CharacterStatus] = mapped_column(
        Enum(CharacterStatus), nullable=False, default=CharacterStatus.active
    )
    latest_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # 乐观锁：每次更新角色元数据/退役时版本号递增，前端必须回传
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    versions: Mapped[list["CharacterVersion"]] = relationship(
        back_populates="character", order_by="CharacterVersion.version.desc()"
    )


class CharacterVersion(Base):
    """角色的不可变版本。修改角色 = 追加新版本，绝不原地改。"""
    __tablename__ = "character_versions"
    __table_args__ = (
        UniqueConstraint("character_id", "version", name="uq_character_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    character_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("characters.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    appearance: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tone: Mapped[str] = mapped_column(Text, nullable=False, default="")
    restrictions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    change_note: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    character: Mapped[Character] = relationship(back_populates="versions")
    images: Mapped[list["ReferenceImage"]] = relationship(back_populates="version")


class ImageAsset(Base):
    """物理图片对象。被参考图绑定 / 派生封面 / 历史导出快照引用，GC 前必须全部查清。"""
    __tablename__ = "image_assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False, default="image/png")
    width: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    height: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    license_granted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    license_note: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReferenceImage(Base):
    """参考图绑定到【具体不可变版本】，授权撤销时按资产维度排查影响。"""
    __tablename__ = "reference_images"
    __table_args__ = (
        UniqueConstraint("version_id", "image_asset_id", name="uq_version_image"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("character_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    image_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("image_assets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    caption: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    version: Mapped[CharacterVersion] = relationship(back_populates="images")
    asset: Mapped[ImageAsset] = relationship()


class Script(Base):
    """剧本/脚本：可固定角色某版 (pinned) 或跟随最新版 (floating)。"""
    __tablename__ = "scripts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    scene_code: Mapped[str] = mapped_column(String(64), nullable=False)  # 场次号
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    links: Mapped[list["ScriptCharacterLink"]] = relationship(
        back_populates="script", cascade="all, delete-orphan"
    )


class ScriptCharacterLink(Base):
    __tablename__ = "script_character_links"
    __table_args__ = (
        UniqueConstraint("script_id", "character_id", name="uq_script_character"),
        CheckConstraint(
            "(ref_mode = 'floating' AND pinned_version_id IS NULL) "
            "OR (ref_mode = 'pinned' AND pinned_version_id IS NOT NULL)",
            name="ck_ref_mode_consistency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    script_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scripts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    character_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("characters.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    ref_mode: Mapped[RefMode] = mapped_column(Enum(RefMode), nullable=False)
    pinned_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("character_versions.id", ondelete="RESTRICT"), nullable=True
    )
    # 已批准台词快照。floating 引用在角色改版后，effective_version 会落后于最新版，
    # 系统必须提示“待复核”，且不得悄悄改变解释。
    approved_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    effective_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    script: Mapped[Script] = relationship(back_populates="links")


class CoverJob(Base):
    """封面图异步派生任务：绑定原图与裁切参数（不可变指纹）。"""
    __tablename__ = "cover_jobs"
    __table_args__ = (
        Index("ix_cover_jobs_character_version", "character_version_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    character_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("character_versions.id", ondelete="CASCADE"), nullable=False
    )
    source_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("image_assets.id", ondelete="RESTRICT"), nullable=False
    )
    output_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("image_assets.id", ondelete="SET NULL"), nullable=True
    )
    state: Mapped[JobState] = mapped_column(Enum(JobState), nullable=False, default=JobState.pending, index=True)
    # 裁切参数
    crop_x: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    crop_y: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    crop_w: Mapped[float] = mapped_column(Float, nullable=False, default=1)
    crop_h: Mapped[float] = mapped_column(Float, nullable=False, default=1)
    target_width: Mapped[int] = mapped_column(Integer, nullable=False, default=640)
    target_height: Mapped[int] = mapped_column(Integer, nullable=False, default=360)
    params_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    force_fail: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class GeneratedAsset(Base):
    """已生成的素材（封面等），属于某个角色版本并溯源任务与来源图。"""
    __tablename__ = "generated_assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    character_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("character_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("image_assets.id", ondelete="RESTRICT"), nullable=False
    )
    output_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("image_assets.id", ondelete="RESTRICT"), nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cover_jobs.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="cover")
    params_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExportSnapshot(Base):
    """导出快照：导出时刻把引用的角色版本与图片冻结，历史导出会阻止图片 GC。"""
    __tablename__ = "export_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    label: Mapped[str] = mapped_column(String(256), nullable=False)
    script_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("scripts.id", ondelete="SET NULL"), nullable=True
    )
    payload: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    images: Mapped[list["ExportImageRef"]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan"
    )
    version_refs: Mapped[list["ExportVersionRef"]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan"
    )


class ExportImageRef(Base):
    __tablename__ = "export_image_refs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("export_snapshots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    image_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("image_assets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    snapshot: Mapped[ExportSnapshot] = relationship(back_populates="images")


class ExportVersionRef(Base):
    __tablename__ = "export_version_refs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("export_snapshots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    character_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("characters.id"), nullable=False)
    character_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("character_versions.id", ondelete="RESTRICT"), nullable=False
    )
    ref_mode_at_export: Mapped[RefMode] = mapped_column(Enum(RefMode), nullable=False)
    snapshot: Mapped[ExportSnapshot] = relationship(back_populates="version_refs")


class ReviewItem(Base):
    """待复核队列：冲突、授权撤销、生成失败、退役受阻、已批准台词漂移。"""
    __tablename__ = "review_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    kind: Mapped[ReviewKind] = mapped_column(Enum(ReviewKind), nullable=False, index=True)
    state: Mapped[ReviewState] = mapped_column(
        Enum(ReviewState), nullable=False, default=ReviewState.open, index=True
    )
    character_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), nullable=True
    )
    script_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("scripts.id", ondelete="CASCADE"), nullable=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cover_jobs.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
