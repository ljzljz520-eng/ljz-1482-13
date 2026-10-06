"""Export snapshots."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import current_user, require_roles
from app.models import ExportSnapshot, Script, User
from app.schemas import ExportCreate, ExportOut
from app.services.exports import build_export

router = APIRouter(tags=["exports"])


@router.get("/exports", response_model=list[ExportOut])
def list_exports(db: Session = Depends(get_db), _: User = Depends(current_user)):
    rows = db.query(ExportSnapshot).order_by(ExportSnapshot.created_at.desc()).all()
    return [
        {
            "id": e.id,
            "script_id": e.script_id,
            "label": e.label,
            "payload": e.payload,
            "asset_ids": [a.asset_id for a in e.assets],
            "image_ids": [i.image_id for i in e.images],
            "created_at": e.created_at,
        }
        for e in rows
    ]


@router.post("/scripts/{script_id}/exports", response_model=ExportOut, status_code=status.HTTP_201_CREATED)
def create_export(
    script_id: str,
    payload: ExportCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "editor")),
):
    script = db.query(Script).get(script_id)
    if script is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "脚本不存在")
    export = build_export(db, script, user.id, payload.label)
    return {
        "id": export.id,
        "script_id": export.script_id,
        "label": export.label,
        "payload": export.payload,
        "asset_ids": [a.asset_id for a in export.assets],
        "image_ids": [i.image_id for i in export.images],
        "created_at": export.created_at,
    }
