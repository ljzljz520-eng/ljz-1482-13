"""Actual reverse-reference inspection used before retiring a character.

Counts come from the relational database (scripts, generated materials, export
snapshots) rather than from in-memory guesses.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import (
    Character,
    CharacterVersion,
    CoverJob,
    ExportAsset,
    ExportImage,
    ExportSnapshot,
    GeneratedAsset,
    Line,
    Scene,
    Script,
    ScriptCharacter,
    VersionImage,
)


def _version_ids(db: Session, character_id: str) -> list[str]:
    return [
        row[0]
        for row in db.query(CharacterVersion.id)
        .filter(CharacterVersion.character_id == character_id)
        .all()
    ]


def script_references(db: Session, character_id: str) -> list[ScriptCharacter]:
    return (
        db.query(ScriptCharacter)
        .filter(ScriptCharacter.character_id == character_id)
        .all()
    )


def collect_references(db: Session, character: Character) -> dict:
    cid = character.id
    version_ids = set(_version_ids(db, cid))

    pinned = []
    floating = 0
    for sc in script_references(db, cid):
        script = db.query(Script).get(sc.script_id)
        entry = {
            "script_character_id": sc.id,
            "script_id": sc.script_id,
            "script_title": script.title if script else None,
            "pin_mode": sc.pin_mode,
            "pinned_version_id": sc.pinned_version_id,
        }
        if sc.pin_mode == "pinned":
            pinned.append(entry)
        else:
            floating += 1

    lines_q = (
        db.query(Line, Scene)
        .join(Scene, Line.scene_id == Scene.id)
        .filter(Line.character_id == cid)
        .order_by(Scene.sort_order, Scene.code)
    )
    approved_lines, pending_lines = [], []
    for line, scene in lines_q.all():
        entry = {
            "line_id": line.id,
            "scene_id": scene.id,
            "scene_code": scene.code,
            "scene_title": scene.title,
            "script_id": scene.script_id,
            "version_id": line.version_id,
            "approved": line.approved,
            "needs_recheck": line.needs_recheck,
            "content": line.content[:80],
        }
        (approved_lines if line.approved else pending_lines).append(entry)

    jobs = []
    for job in db.query(CoverJob).filter(CoverJob.character_id == cid).all():
        jobs.append(
            {
                "job_id": job.id,
                "status": job.status,
                "version_id": job.version_id,
                "source_image_id": job.source_image_id,
            }
        )

    assets = []
    for asset in db.query(GeneratedAsset).filter(GeneratedAsset.character_id == cid).all():
        assets.append(
            {
                "asset_id": asset.id,
                "version_id": asset.version_id,
                "is_active_cover": asset.is_active_cover,
                "storage_path": asset.storage_path,
            }
        )

    # Exports touch characters through included generated assets or source
    # images embedded in a version used by the export payload.
    export_rows = (
        db.query(ExportSnapshot)
        .order_by(ExportSnapshot.created_at.desc())
    )
    exports = []
    asset_id_set = {a["asset_id"] for a in assets}
    version_image_ids = {
        row[0]
        for row in db.query(VersionImage.image_id)
        .filter(VersionImage.version_id.in_(version_ids or ["__none__"]))
        .all()
    }
    for export in export_rows.all():
        linked_assets = [ea.asset_id for ea in export.assets if ea.asset_id in asset_id_set]
        linked_images = [ei.image_id for ei in export.images if ei.image_id in version_image_ids]
        payload_versions = set((export.payload or {}).get("version_ids", []))
        if linked_assets or linked_images or (payload_versions & version_ids):
            exports.append(
                {
                    "export_id": export.id,
                    "label": export.label,
                    "asset_ids": linked_assets,
                    "image_ids": linked_images,
                    "created_at": export.created_at.isoformat(),
                }
            )

    return {
        "pinned_script_refs": {"count": len(pinned), "items": pinned},
        "floating_script_refs": floating,
        "approved_lines": {"count": len(approved_lines), "items": approved_lines},
        "pending_lines": {"count": len(pending_lines), "items": pending_lines},
        "cover_jobs": {"count": len(jobs), "items": jobs},
        "generated_assets": {"count": len(assets), "items": assets},
        "export_snapshots": {"count": len(exports), "items": exports},
    }


def total_reference_count(refs: dict) -> int:
    return (
        refs["pinned_script_refs"]["count"]
        + refs["floating_script_refs"]
        + refs["approved_lines"]["count"]
        + refs["pending_lines"]["count"]
        + refs["cover_jobs"]["count"]
        + refs["generated_assets"]["count"]
        + refs["export_snapshots"]["count"]
    )
