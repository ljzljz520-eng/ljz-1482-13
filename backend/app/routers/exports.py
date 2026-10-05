import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.deps import require_editor, require_viewer
from app.models import CharacterVersion, ExportSnapshot, User
from app.services import exports as svc

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("", response_model=list[schemas.ExportOut])
def list_exports(db: Session = Depends(get_db), _: User = Depends(require_viewer)):
    snaps = db.query(ExportSnapshot).order_by(ExportSnapshot.created_at.desc()).all()
    out = []
    for snap in snaps:
        creator = db.get(User, snap.created_by)
        refs = []
        for vr in snap.version_refs:
            v = db.get(CharacterVersion, vr.character_version_id)
            character = v.character
            refs.append(
                schemas.VersionBriefOut(
                    character_id=vr.character_id,
                    character_name=character.name,
                    version_id=v.id,
                    version=v.version,
                )
            )
        out.append(
            schemas.ExportOut(
                id=snap.id,
                label=snap.label,
                script_id=snap.script_id,
                created_by_name=creator.display_name if creator else None,
                created_at=snap.created_at,
                character_refs=refs,
                image_count=len(snap.images),
            )
        )
    return out


@router.post("", response_model=schemas.ExportOut, status_code=status.HTTP_201_CREATED)
def create_export(
    payload: schemas.ExportIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    snap = svc.create_export(db, payload, user)
    created = list_exports(db, user)  # reuse serialization
    return next(x for x in created if x.id == snap.id)
