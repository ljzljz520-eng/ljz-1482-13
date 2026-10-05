import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.deps import require_editor, require_viewer
from app.models import CoverJob, User
from app.services import covers as svc
from app.services.serializers import cover_job_out

router = APIRouter(prefix="/cover-jobs", tags=["covers"])


@router.post("", response_model=schemas.CoverJobOut, status_code=status.HTTP_202_ACCEPTED)
def create_job(
    payload: schemas.CoverJobIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    job = svc.create_cover_job(db, payload, user)
    return cover_job_out(db, job)


@router.get("/{job_id}", response_model=schemas.CoverJobOut)
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_viewer)):
    job = db.get(CoverJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    return cover_job_out(db, job)


@router.post("/{job_id}/retry", response_model=schemas.CoverJobOut)
def retry_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_editor),
):
    job = svc.retry_job(db, job_id)
    return cover_job_out(db, job)
