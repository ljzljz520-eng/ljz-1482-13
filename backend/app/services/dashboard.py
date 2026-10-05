"""复核工作台：受影响场次 + 待复核项 + 失败任务 + 软删除角色。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app import schemas
from app.models import (
    Character,
    CharacterStatus,
    CoverJob,
    JobState,
    ReviewItem,
    ReviewState,
    Script,
)
from app.services.serializers import character_out, cover_job_out, script_ref_out


def affected_scenes(db: Session) -> list[schemas.ScriptRefOut]:
    """所有处于“需要复核”状态的场次引用（floating 漂移 / 已退役引用等）。"""
    out: list[schemas.ScriptRefOut] = []
    scripts = db.query(Script).order_by(Script.scene_code.asc()).all()
    for script in scripts:
        for link in script.links:
            ref = script_ref_out(db, link)
            ref.title = script.title
            ref.scene_code = script.scene_code
            if ref.needs_review:
                out.append(ref)
    return out


def dashboard(db: Session) -> schemas.DashboardOut:
    scenes = affected_scenes(db)
    reviews = (
        db.query(ReviewItem)
        .filter(ReviewItem.state == ReviewState.open)
        .order_by(ReviewItem.created_at.desc())
        .all()
    )
    failed_jobs = (
        db.query(CoverJob)
        .filter(CoverJob.state.in_([JobState.failed, JobState.stale]))
        .order_by(CoverJob.updated_at.desc())
        .all()
    )
    soft_deleted = (
        db.query(Character).filter(Character.status == CharacterStatus.soft_deleted).all()
    )
    return schemas.DashboardOut(
        affected_scenes=scenes,
        review_items=[schemas.ReviewOut.model_validate(r) for r in reviews],
        failed_jobs=[cover_job_out(db, j) for j in failed_jobs],
        soft_deleted_characters=[character_out(db, c) for c in soft_deleted],
    )


def resolve_review(db: Session, item_id) -> None:
    from datetime import datetime, timezone

    item = db.get(ReviewItem, item_id)
    if item is None:
        return
    item.state = ReviewState.resolved
    item.resolved_at = datetime.now(timezone.utc)
    db.commit()
