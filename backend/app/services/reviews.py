"""Review item bookkeeping with dedup so repeated events do not spam queues."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import CoverJob, Line, ReferenceImage, ReviewItem, Scene, utcnow


def open_review(
    db: Session,
    *,
    kind: str,
    message: str,
    severity: str = "warning",
    character_id: str | None = None,
    version_id: str | None = None,
    line_id: str | None = None,
    scene_id: str | None = None,
    job_id: str | None = None,
    image_id: str | None = None,
) -> ReviewItem:
    existing = (
        db.query(ReviewItem)
        .filter(
            ReviewItem.kind == kind,
            ReviewItem.line_id.is_(line_id) if line_id is None else ReviewItem.line_id == line_id,
            ReviewItem.job_id.is_(job_id) if job_id is None else ReviewItem.job_id == job_id,
            ReviewItem.image_id.is_(image_id) if image_id is None else ReviewItem.image_id == image_id,
            ReviewItem.status == "open",
        )
        .first()
    )
    if existing:
        return existing
    review = ReviewItem(
        kind=kind,
        severity=severity,
        message=message,
        character_id=character_id,
        version_id=version_id,
        line_id=line_id,
        scene_id=scene_id,
        job_id=job_id,
        image_id=image_id,
    )
    db.add(review)
    db.flush()
    return review


def resolve_reviews(
    db: Session,
    *,
    kind: str | None = None,
    line_id: str | None = None,
    job_id: str | None = None,
    image_id: str | None = None,
) -> int:
    q = db.query(ReviewItem).filter(ReviewItem.status == "open")
    if kind:
        q = q.filter(ReviewItem.kind == kind)
    if line_id is not None:
        q = q.filter(ReviewItem.line_id == line_id)
    if job_id is not None:
        q = q.filter(ReviewItem.job_id == job_id)
    if image_id is not None:
        q = q.filter(ReviewItem.image_id == image_id)
    count = 0
    for item in q.all():
        item.status = "resolved"
        item.resolved_at = utcnow()
        count += 1
    return count


def serialise(db: Session, review: ReviewItem) -> dict:
    scene_code = scene_title = None
    if review.scene_id:
        scene = db.query(Scene).get(review.scene_id)
        if scene:
            scene_code, scene_title = scene.code, scene.title
    character_name = None
    if review.character_id:
        from app.models import Character

        ch = db.query(Character).get(review.character_id)
        character_name = ch.name if ch else None
    return {
        "id": review.id,
        "kind": review.kind,
        "severity": review.severity,
        "message": review.message,
        "status": review.status,
        "character_id": review.character_id,
        "character_name": character_name,
        "version_id": review.version_id,
        "line_id": review.line_id,
        "scene_id": review.scene_id,
        "scene_code": scene_code,
        "scene_title": scene_title,
        "job_id": review.job_id,
        "image_id": review.image_id,
        "created_at": review.created_at,
        "resolved_at": review.resolved_at,
    }
