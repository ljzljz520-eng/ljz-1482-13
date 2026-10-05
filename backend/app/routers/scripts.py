import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.deps import require_editor, require_viewer
from app.models import Script, ScriptCharacterLink, User
from app.services import scripts as svc
from app.services.serializers import script_out

router = APIRouter(prefix="/scripts", tags=["scripts"])


@router.get("", response_model=list[schemas.ScriptOut])
def list_scripts(db: Session = Depends(get_db), _: User = Depends(require_viewer)):
    scripts = db.query(Script).order_by(Script.scene_code.asc()).all()
    return [script_out(db, s) for s in scripts]


@router.post("", response_model=schemas.ScriptOut, status_code=status.HTTP_201_CREATED)
def create_script(
    payload: schemas.ScriptCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    s = svc.create_script(db, payload, user)
    return script_out(db, s)


@router.get("/{script_id}", response_model=schemas.ScriptOut)
def get_script(script_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_viewer)):
    s = db.get(Script, script_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "脚本不存在")
    return script_out(db, s)


@router.patch("/{script_id}", response_model=schemas.ScriptOut)
def update_script(
    script_id: uuid.UUID,
    payload: schemas.ScriptUpdateIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_editor),
):
    s = db.get(Script, script_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "脚本不存在")
    s = svc.update_script(db, s, payload)
    return script_out(db, s)


@router.post("/{script_id}/links", response_model=schemas.ScriptOut, status_code=201)
def add_link(
    script_id: uuid.UUID,
    payload: schemas.ScriptLinkIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    svc.add_link(db, script_id, payload, user)
    s = db.get(Script, script_id)
    return script_out(db, s)


@router.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_link(link_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_editor)):
    svc.remove_link(db, link_id)


@router.post("/links/{link_id}/approve", response_model=schemas.ScriptOut)
def approve_line(
    link_id: uuid.UUID,
    payload: schemas.ApproveIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    if str(payload.link_id) != str(link_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "link_id 不一致")
    link = svc.approve_line(db, payload, user)
    s = db.get(Script, link.script_id)
    return script_out(db, s)


@router.post("/links/{link_id}/reconfirm", response_model=schemas.ScriptOut)
def reconfirm(link_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_editor)):
    link = svc.reconfirm_drift(db, link_id, user)
    s = db.get(Script, link.script_id)
    return script_out(db, s)


from app.models import RefMode  # noqa: E402
from pydantic import BaseModel  # noqa: E402


class SwitchBody(BaseModel):
    ref_mode: RefMode
    pinned_version_id: str | None = None


@router.post("/links/{link_id}/mode", response_model=schemas.ScriptOut)
def switch_mode(
    link_id: uuid.UUID,
    body: SwitchBody,
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    import uuid
    pinned = uuid.UUID(body.pinned_version_id) if body.pinned_version_id else None
    link = svc.switch_ref_mode(db, link_id, body.ref_mode, pinned, user)
    s = db.get(Script, link.script_id)
    return script_out(db, s)
