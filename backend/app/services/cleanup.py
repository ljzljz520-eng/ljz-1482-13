"""Garbage collection of unreferenced binary objects.

Deletion safety rules:
* a reference image is a deletion candidate only when no version references it
  and no live/pending/succeeded cover job uses it;
* a generated asset is a candidate only when it is not the current cover and no
  cover job still points at it;
* anything still linked by a historical export snapshot is reported as
  "protected by exports" and kept on disk — even if every other reference is
  gone (this is the explicit historical-export requirement).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import (
    CoverJob,
    ExportAsset,
    ExportImage,
    GeneratedAsset,
    ReferenceImage,
    VersionImage,
)
from app.services import media


def cleanup(db: Session, *, dry_run: bool = True) -> dict:
    used_image_ids = {row[0] for row in db.query(VersionImage.image_id).all()}
    for row in db.query(CoverJob.source_image_id).filter(
        CoverJob.status.in_(["pending", "processing", "succeeded", "stale"])
    ).all():
        used_image_ids.add(row[0])

    protected_image_ids = {row[0] for row in db.query(ExportImage.image_id).all()}
    protected_asset_ids = {row[0] for row in db.query(ExportAsset.asset_id).all()}

    job_asset_ids = {
        row[0]
        for row in db.query(CoverJob.result_asset_id)
        .filter(CoverJob.result_asset_id.isnot(None))
        .all()
    }
    active_cover_ids = {
        row[0]
        for row in db.query(GeneratedAsset.id)
        .filter(GeneratedAsset.is_active_cover.is_(True))
        .all()
    }

    deleted_images, deleted_assets = [], []
    protected, kept = [], []
    bytes_freed = 0

    for img in db.query(ReferenceImage).all():
        if img.id in used_image_ids:
            kept.append(
                {"id": img.id, "filename": img.filename, "reason": "仍被角色版本或任务引用"}
            )
            continue
        entry = {"id": img.id, "filename": img.filename, "license_status": img.license_status}
        if img.id in protected_image_ids:
            entry["reason"] = "仍被历史导出快照引用"
            protected.append(entry)
            continue
        bytes_freed += media.remove_file(img.storage_path)
        deleted_images.append(entry)
        if not dry_run:
            db.delete(img)

    for asset in db.query(GeneratedAsset).all():
        entry = {"id": asset.id, "kind": asset.kind, "character_id": asset.character_id}
        # Export protection wins: even assets still attached to succeeded jobs
        # are reported as export-protected when a snapshot cites them.
        if asset.id in protected_asset_ids:
            entry["reason"] = "仍被历史导出快照引用"
            protected.append(entry)
            continue
        if asset.id in job_asset_ids or asset.id in active_cover_ids:
            kept.append(
                {"id": asset.id, "kind": asset.kind,
                 "reason": "当前封面或仍被任务引用"}
            )
            continue
        bytes_freed += media.remove_file(asset.storage_path)
        deleted_assets.append(entry)
        if not dry_run:
            db.delete(asset)

    if not dry_run:
        db.commit()

    return {
        "deleted_images": deleted_images,
        "deleted_assets": deleted_assets,
        "protected_by_exports": protected,
        "kept_in_use": kept,
        "bytes_freed": bytes_freed,
    }
