"""Scripts, scenes and script->character references (pin/follow latest)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import current_user, require_roles
from app.models import (
    Character,
    CharacterVersion,
    Scene,
    Script,
    ScriptCharacter,
    User,
)
from app.schemas import (
    SceneCreate,
    ScriptCharacterRequest,
    ScriptCreate,
    ScriptOut,
)
from app.serializers import script_out
from app.services.characters import ensure_editable, get_active_character

router = APIRouter(prefix="/scripts", tags=["scripts"])


@router.get("", response_model=list[ScriptOut])
def list_scripts(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return [script_out(db, s) for s in db.query(Script).order_by(Script.created_at.desc()).all()]


@router.post("", response_model=ScriptOut, status_code=status.HTTP_201_CREATED)
def create_script(
    payload: ScriptCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "editor")),
):
    script = Script(title=payload.title, synopsis=payload.synopsis, created_by=user.id)
    db.add(script)
    db.commit()
    db.refresh(script)
    return script_out(db, script)


@router.get("/{script_id}", response_model=ScriptOut)
def get_script(script_id: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    script = db.query(Script).get(script_id)
    if script is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "脚本不存在")
    return script_out(db, script)


@router.post("/{script_id}/scenes", response_model=ScriptOut, status_code=status.HTTP_201_CREATED)
def add_scene(
    script_id: str,
    payload: SceneCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "editor")),
):
    script = db.query(Script).get(script_id)
    if script is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "脚本不存在")
    db.add(Scene(
        script_id=script.id,
        code=payload.code,
        title=payload.title,
        sort_order=payload.sort_order,
    ))
    db.commit()
    return script_out(db, script)


@router.post("/{script_id}/characters", response_model=ScriptOut, status_code=status.HTTP_201_CREATED)
def add_character_reference(
    script_id: str,
    payload: ScriptCharacterRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "editor")),
):
    script = db.query(Script).get(script_id)
    if script is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "脚本不存在")

    # BEGIN IMMEDIATE (SQLite) / normal tx (Postgres + FOR UPDATE): this is
    # what blocks adding references while a retirement transaction is running.
    from app.services.tx import immediate_transaction

    with immediate_transaction(db):
        character = get_active_character(db, payload.character_id, for_update=True)
        ensure_editable(character)

        if payload.pin_mode == "pinned":
            version = (
                db.query(CharacterVersion)
                .filter(
                    CharacterVersion.id == payload.pinned_version_id,
                    CharacterVersion.character_id == character.id,
                )
                .first()
            )
            if version is None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "固定版本不属于该角色")
        exists = (
            db.query(ScriptCharacter)
            .filter(
                ScriptCharacter.script_id == script.id,
                ScriptCharacter.character_id == character.id,
            )
            .first()
        )
        if exists:
            raise HTTPException(status.HTTP_409_CONFLICT, "该脚本已引用此角色")
        db.add(ScriptCharacter(
            script_id=script.id,
            character_id=character.id,
            pin_mode=payload.pin_mode,
            pinned_version_id=payload.pinned_version_id if payload.pin_mode == "pinned" else None,
        ))
    return script_out(db, script)


@router.patch(
    "/{script_id}/characters/{ref_id}",
    response_model=ScriptOut,
)
def update_reference(
    script_id: str,
    ref_id: str,
    payload: ScriptCharacterRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "editor")),
):
    ref = (
        db.query(ScriptCharacter)
        .filter(ScriptCharacter.id == ref_id, ScriptCharacter.script_id == script_id)
        .with_for_update()
        .first()
    )
    if ref is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "引用不存在")
    character = get_active_character(db, payload.character_id, for_update=True)
    ensure_editable(character)
    ref.character_id = character.id
    ref.pin_mode = payload.pin_mode
    ref.pinned_version_id = (
        payload.pinned_version_id if payload.pin_mode == "pinned" else None
    )
    if payload.pin_mode == "pinned":
        version = (
            db.query(CharacterVersion)
            .filter(
                CharacterVersion.id == payload.pinned_version_id,
                CharacterVersion.character_id == character.id,
            )
            .first()
        )
        if version is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "固定版本不属于该角色")
    db.commit()
    return script_out(db, db.query(Script).get(script_id))


@router.delete("/{script_id}/characters/{ref_id}", response_model=ScriptOut)
def remove_reference(
    script_id: str,
    ref_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "editor")),
):
    ref = (
        db.query(ScriptCharacter)
        .filter(ScriptCharacter.id == ref_id, ScriptCharacter.script_id == script_id)
        .first()
    )
    if ref is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "引用不存在")
    db.delete(ref)
    db.commit()
    return script_out(db, db.query(Script).get(script_id))
