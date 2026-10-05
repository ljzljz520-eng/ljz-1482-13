"""反向引用查询：删除/退役/GC 前必须查清脚本、素材、历史导出三类真实引用。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Character,
    CharacterVersion,
    CoverJob,
    ExportImageRef,
    ExportSnapshot,
    ExportVersionRef,
    GeneratedAsset,
    ImageAsset,
    JobState,
    RefMode,
    ReferenceImage,
    Script,
    ScriptCharacterLink,
)


def script_links_for_character(db: Session, character_id) -> list[ScriptCharacterLink]:
    return db.query(ScriptCharacterLink).filter_by(character_id=character_id).all()


def scripts_for_character(db: Session, character_id) -> list[tuple[Script, ScriptCharacterLink]]:
    rows = (
        db.query(Script, ScriptCharacterLink)
        .join(ScriptCharacterLink, ScriptCharacterLink.script_id == Script.id)
        .filter(ScriptCharacterLink.character_id == character_id)
        .order_by(Script.scene_code.asc())
        .all()
    )
    return rows


def generated_assets_for_character(db: Session, character_id) -> list[GeneratedAsset]:
    version_ids = [
        v.id
        for v in db.query(CharacterVersion.id).filter_by(character_id=character_id).all()
    ]
    if not version_ids:
        return []
    return (
        db.query(GeneratedAsset)
        .filter(GeneratedAsset.character_version_id.in_(version_ids))
        .all()
    )


def export_snapshots_for_character(db: Session, character_id) -> list[ExportSnapshot]:
    rows = (
        db.query(ExportSnapshot)
        .join(ExportVersionRef, ExportVersionRef.snapshot_id == ExportSnapshot.id)
        .filter(ExportVersionRef.character_id == character_id)
        .distinct()
        .all()
    )
    return rows


def pending_cover_jobs_for_character(db: Session, character_id) -> int:
    version_ids = [
        r[0]
        for r in db.query(CharacterVersion.id)
        .join(CoverJob, CoverJob.character_version_id == CharacterVersion.id)
        .filter(CharacterVersion.character_id == character_id)
        .distinct()
        .all()
    ]
    if not version_ids:
        return 0
    return (
        db.query(CoverJob)
        .filter(
            CoverJob.character_version_id.in_(version_ids),
            CoverJob.state.in_([JobState.pending, JobState.processing]),
        )
        .count()
    )


# ---------- 图片资产反向引用（GC / 授权撤销共用） ----------

def image_reference_usages(db: Session, asset_id) -> dict:
    """汇总一个图片对象的全部真实引用方。历史导出也算引用。"""
    referenced_by_reference = (
        db.query(ReferenceImage).filter_by(image_asset_id=asset_id).count() > 0
    )
    referenced_by_generated_source = (
        db.query(GeneratedAsset).filter_by(source_asset_id=asset_id).count() > 0
    )
    referenced_by_generated_output = (
        db.query(GeneratedAsset).filter_by(output_asset_id=asset_id).count() > 0
    )
    referenced_by_pending_job = (
        db.query(CoverJob)
        .filter(
            CoverJob.source_asset_id == asset_id,
            CoverJob.state.in_([JobState.pending, JobState.processing]),
        )
        .count()
        > 0
    )
    referenced_by_export = (
        db.query(ExportImageRef).filter_by(image_asset_id=asset_id).count() > 0
    )
    return {
        "referenced_by_reference": referenced_by_reference,
        "referenced_by_generated_source": referenced_by_generated_source,
        "referenced_by_generated_output": referenced_by_generated_output,
        "referenced_by_pending_job": referenced_by_pending_job,
        "referenced_by_export": referenced_by_export,
    }


def asset_is_deletable(usages: dict) -> bool:
    return not any(usages.values())


def versions_using_image(db: Session, asset_id):
    rows = (
        db.query(ReferenceImage, CharacterVersion, Character)
        .join(CharacterVersion, CharacterVersion.id == ReferenceImage.version_id)
        .join(Character, Character.id == CharacterVersion.character_id)
        .filter(ReferenceImage.image_asset_id == asset_id)
        .all()
    )
    return rows


def exports_using_image(db: Session, asset_id) -> int:
    return db.query(ExportImageRef).filter_by(image_asset_id=asset_id).count()


def generated_covers_for_image(db: Session, asset_id) -> int:
    return (
        db.query(GeneratedAsset)
        .filter(
            (GeneratedAsset.source_asset_id == asset_id)
            | (GeneratedAsset.output_asset_id == asset_id)
        )
        .count()
    )
