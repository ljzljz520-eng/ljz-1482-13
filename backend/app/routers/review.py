import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.deps import require_viewer
from app.models import User
from app.services import dashboard as svc

router = APIRouter(tags=["review"])


@router.get("/dashboard", response_model=schemas.DashboardOut)
def get_dashboard(db: Session = Depends(get_db), _: User = Depends(require_viewer)):
    return svc.dashboard(db)


@router.post("/review-items/{item_id}/resolve")
def resolve_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    svc.resolve_review(db, item_id)
    return {"ok": True}
