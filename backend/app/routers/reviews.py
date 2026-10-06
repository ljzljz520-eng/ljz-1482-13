"""Review queue surfaced by the UI ('affected scenes / items to re-check')."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import current_user, require_roles
from app.models import ReviewItem, User
from app.schemas import ReviewOut
from app.services import reviews as review_service
from app.services.reviews import serialise

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("", response_model=list[ReviewOut])
def list_reviews(
    status_filter: str = "open",
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    q = db.query(ReviewItem).order_by(ReviewItem.created_at.desc())
    if status_filter != "all":
        q = q.filter(ReviewItem.status == status_filter)
    return [serialise(db, r) for r in q.all()]


@router.post("/{review_id}/resolve", response_model=ReviewOut)
def resolve_review(
    review_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "editor")),
):
    review = db.query(ReviewItem).get(review_id)
    from fastapi import HTTPException, status

    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "复核项不存在")
    review.status = "resolved"
    from app.models import utcnow

    review.resolved_at = utcnow()
    db.commit()
    return serialise(db, review)
