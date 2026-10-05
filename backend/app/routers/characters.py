import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.deps import require_admin, require_editor, require_viewer
from app.models import (
    Character,
    CharacterStatus,
    CharacterVersion,
    CoverJob,
    User,
)
from app.services import characters as svc
from app.services.serializers import character_out, cover_job_out, version_out

router = APIRouter(prefix="/characters", tags=["characters"])


def _get_or_404(db: Session, character_id: uuid.UUID) -> Character:
    c = db.get(Character, character_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "角色不存在")
    return c


@router.get("", response_model=list[schemas.CharacterOut])
def list_characters(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    q = db.query(Character)
    if not include_inactive:
        q = q.filter(Character.status == CharacterStatus.active)
    return [character_out(db, c) for c in q.order_by(Character.code.asc()).all()]


@router.post("", response_model=schemas.CharacterOut, status_code=status.HTTP_201_CREATED)
def create_character(
    payload: schemas.CharacterCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    c = svc.create_character(db, payload, user)
    return character_out(db, c, with_latest=True)


@router.get("/{character_id}", response_model=schemas.CharacterDetailOut)
def get_character(
    character_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    c = _get_or_404(db, character_id)
    base = character_out(db, c, with_latest=True)
    versions = (
        db.query(CharacterVersion)
        .filter_by(character_id=c.id)
        .order_by(CharacterVersion.version.desc())
        .all()
    )
    detail = schemas.CharacterDetailOut(**base.model_dump(), versions=[version_out(db, v) for v in versions])
    return detail


@router.post("/{character_id}/versions", response_model=schemas.VersionOut, status_code=201)
def append_version(
    character_id: uuid.UUID,
    payload: schemas.VersionCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    c = _get_or_404(db, character_id)
    v = svc.append_version(db, c, payload, user)
    return version_out(db, v)


@router.get("/{character_id}/references", response_model=schemas.RetireDryRunOut)
def reverse_references(
    character_id: uuid.UUID,
    mode: str = Query("retire", pattern="^(retire|soft_delete)$"),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    c = _get_or_404(db, character_id)
    return svc.retire_dry_run(db, c, mode)


@router.post("/{character_id}/retire", response_model=schemas.CharacterOut)
def retire_character(
    character_id: uuid.UUID,
    payload: schemas.RetireIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    c = _get_or_404(db, character_id)
    c = svc.retire(db, c, payload, user)
    return character_out(db, c, with_latest=True)


@router.post("/{character_id}/restore", response_model=schemas.CharacterOut)
def restore_character(
    character_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    c = _get_or_404(db, character_id)
    c = svc.restore(db, c, user)
    return character_out(db, c, with_latest=True)


@router.get("/{character_id}/cover-jobs", response_model=list[schemas.CoverJobOut])
def list_cover_jobs(
    character_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    c = _get_or_404(db, character_id)
    version_ids = [
        r[0]
        for r in db.query(CharacterVersion.id).filter_by(character_id=c.id).all()
    ]
    jobs = (
        db.query(CoverJob)
        .filter(CoverJob.character_version_id.in_(version_ids))
        .order_by(CoverJob.created_at.desc())
        .all()
    )
    return [cover_job_out(db, j) for j in jobs]
