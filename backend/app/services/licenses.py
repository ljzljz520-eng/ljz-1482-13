"""Source image license/authorization revocation cascade."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import (
    CharacterVersion,
    CoverJob,
    GeneratedAsset,
    Line,
    ReferenceImage,
    Scene,
    VersionImage,
)
from app.services import reviews as review_service


def revoke(db: Session, image: ReferenceImage) -> dict:
    image.license_status = "revoked"

    affected_versions = {
        row[0]
        for row in db.query(VersionImage.version_id)
        .filter(VersionImage.image_id == image.id)
        .all()
    }

    affected_jobs = []
    for job in (
        db.query(CoverJob)
        .filter(
            CoverJob.source_image_id == image.id,
            CoverJob.status.in_(["pending", "processing"]),
        )
        .all()
    ):
        job.status = "failed"
        job.error_message = "来源图授权已撤销，任务终止"
        affected_jobs.append(job.id)
        review_service.open_review(
            db,
            kind="cover_failed",
            severity="warning",
            message=f"封面任务因来源图 {image.filename} 授权撤销而失败",
            character_id=job.character_id,
            version_id=job.version_id,
            job_id=job.id,
            image_id=image.id,
        )

    deactivated_assets = 0
    for asset in (
        db.query(GeneratedAsset)
        .filter(
            GeneratedAsset.source_image_id == image.id,
            GeneratedAsset.is_active_cover.is_(True),
        )
        .all()
    ):
        asset.is_active_cover = False
        deactivated_assets += 1
        review_service.open_review(
            db,
            kind="license_revoked",
            severity="critical",
            message=f"角色封面因来源图 {image.filename} 授权撤销而下架，需重新授权或替换",
            character_id=asset.character_id,
            version_id=asset.version_id,
            image_id=image.id,
        )

    flagged_lines = 0
    if affected_versions:
        rows = (
            db.query(Line, Scene)
            .join(Scene, Line.scene_id == Scene.id)
            .filter(Line.version_id.in_(list(affected_versions)))
            .all()
        )
        affected_chars = set()
        for line, scene in rows:
            line.needs_recheck = True
            line.recheck_reason = f"参考图 {image.filename} 授权已撤销，相关场次需复核"
            flagged_lines += 1
            affected_chars.add(line.character_id)
            review_service.open_review(
                db,
                kind="license_revoked",
                severity="critical",
                message=f"场次 {scene.code} 使用了授权撤销的参考图 {image.filename}",
                character_id=line.character_id,
                version_id=line.version_id,
                line_id=line.id,
                scene_id=scene.id,
                image_id=image.id,
            )

    review = review_service.open_review(
        db,
        kind="license_revoked",
        severity="critical",
        message=f"来源图 {image.filename} 的授权已撤销，所有派生用途已标记",
        image_id=image.id,
    )
    db.commit()
    return {
        "affected_versions": sorted(affected_versions),
        "affected_jobs": affected_jobs,
        "flagged_lines": flagged_lines,
        "deactivated_assets": deactivated_assets,
        "review_id": review.id,
    }
