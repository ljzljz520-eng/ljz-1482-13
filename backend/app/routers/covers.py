"""Cover derivation task endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import current_user, require_roles
from app.models import CharacterVersion, CoverJob, ReferenceImage, User
from app.schemas import CoverJobCreate, CoverJobOut
from app.serializers import job_out
from app.services.covers import get_or_create_job, tick
from app.services.characters import ensure_editable, get_active_character

router = APIRouter(tags=["covers"])


@router.get("/characters/{character_id}/jobs", response_model=list[CoverJobOut])
def list_jobs(character_id: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    rows = (
        db.query(CoverJob)
        .filter(CoverJob.character_id == character_id)
        .order_by(CoverJob.created_at.desc())
        .all()
    )
    return [job_out(db, j) for j in rows]


@router.post(
    "/characters/{character_id}/versions/{version_id}/cover-jobs",
    response_model=CoverJobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_cover(
    character_id: str,
    version_id: str,
    payload: CoverJobCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "editor")),
):
    character = get_active_character(db, character_id, for_update=True)
    ensure_editable(character)
    version = (
        db.query(CharacterVersion)
        .filter(
            CharacterVersion.id == version_id,
            CharacterVersion.character_id == character_id,
        )
        .first()
    )
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "版本不存在")
    source = db.query(ReferenceImage).get(payload.source_image_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "来源图不存在")
    if source.license_status != "licensed":
        raise HTTPException(status.HTTP_409_CONFLICT, "来源图授权已撤销，不能派生封面")
    job, _created = get_or_create_job(
        db,
        character=character,
        version=version,
        source=source,
        crop=payload.crop.model_dump(),
        user_id=user.id,
    )
    db.refresh(job)
    return job_out(db, job)


@router.post("/cover-jobs/process", include_in_schema=False)
def process_pending(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    """Synchronous processing hook used by QA/tests and an admin 'run now' UI."""
    processed = tick(db)
    return {"processed": processed}
