"""Dialogue lines with frozen approved interpretation."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import current_user, require_roles
from app.models import (
    Character,
    Line,
    Scene,
    ScriptCharacter,
    User,
    utcnow,
)
from app.schemas import LineCreate, LineOut
from app.serializers import line_out
from app.services.characters import ensure_editable, get_active_character, snapshot_version
from app.services import reviews as review_service

router = APIRouter(tags=["lines"])


def _get_scene(db: Session, scene_id: str) -> Scene:
    scene = db.query(Scene).get(scene_id)
    if scene is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "场次不存在")
    return scene


@router.get("/scripts/{script_id}/lines", response_model=list[LineOut])
def list_lines(script_id: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    scenes = db.query(Scene).filter(Scene.script_id == script_id).all()
    rows = []
    for scene in sorted(scenes, key=lambda s: s.sort_order):
        for line in sorted(scene.lines, key=lambda l: l.created_at):
            rows.append(line_out(db, line))
    return rows


@router.post("/lines", response_model=LineOut, status_code=status.HTTP_201_CREATED)
def create_line(
    payload: LineCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "editor")),
):
    scene = _get_scene(db, payload.scene_id)
    character = get_active_character(db, payload.character_id, for_update=True)
    ensure_editable(character)
    # A line requires the script to actually depend on the character.
    ref = (
        db.query(ScriptCharacter)
        .filter(
            ScriptCharacter.script_id == scene.script_id,
            ScriptCharacter.character_id == character.id,
        )
        .first()
    )
    if ref is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "该脚本尚未引用此角色，请先建立引用")
    line = Line(
        scene_id=scene.id,
        character_id=character.id,
        version_id=character.current_version_id,
        content=payload.content,
    )
    db.add(line)
    db.commit()
    db.refresh(line)
    return line_out(db, line)


@router.post("/lines/{line_id}/approve", response_model=LineOut)
def approve_line(
    line_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "editor")),
):
    line = db.query(Line).filter(Line.id == line_id).with_for_update().first()
    if line is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "台词不存在")
    if line.needs_recheck:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "该台词有待复核项，请先完成复核（或显式重新批准）",
        )
    from app.models import CharacterVersion

    version = db.query(CharacterVersion).get(line.version_id)
    line.approved = True
    line.approved_by = user.id
    line.approved_at = utcnow()
    line.interpretation_snapshot = snapshot_version(version)
    line.needs_recheck = False
    line.recheck_reason = None
    db.commit()
    db.refresh(line)
    return line_out(db, line)


@router.post("/lines/{line_id}/reapprove", response_model=LineOut)
def reapprove_line(
    line_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "editor")),
):
    """Explicit human re-approval against the resolved latest version."""
    line = db.query(Line).filter(Line.id == line_id).with_for_update().first()
    if line is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "台词不存在")
    character = db.query(Character).get(line.character_id)
    if character is None or character.current_version_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "角色无可用版本，无法重新批准")
    from app.models import CharacterVersion

    version = db.query(CharacterVersion).get(character.current_version_id)
    line.version_id = version.id
    line.approved = True
    line.approved_by = user.id
    line.approved_at = utcnow()
    line.interpretation_snapshot = snapshot_version(version)
    line.needs_recheck = False
    line.recheck_reason = None
    review_service.resolve_reviews(db, kind="line_recheck", line_id=line.id)
    db.commit()
    db.refresh(line)
    return line_out(db, line)
