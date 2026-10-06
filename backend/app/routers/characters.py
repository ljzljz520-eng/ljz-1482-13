"""Character + immutable version endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import current_user, require_roles
from app.models import Character, CharacterVersion, ReferenceImage, User, VersionImage
from app.schemas import (
    CharacterCreate,
    CharacterOut,
    CharacterUpdate,
    VersionCreate,
    VersionOut,
)
from app.serializers import character_out, version_out
from app.services.characters import (
    create_version,
    ensure_editable,
    get_active_character,
)

router = APIRouter(prefix="/characters", tags=["characters"])


@router.get("", response_model=list[CharacterOut])
def list_characters(db: Session = Depends(get_db), _: User = Depends(current_user)):
    rows = db.query(Character).order_by(Character.created_at.desc()).all()
    return [character_out(db, ch) for ch in rows]


@router.post("", response_model=CharacterOut, status_code=status.HTTP_201_CREATED)
def create_character(
    payload: CharacterCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "editor")),
):
    if db.query(Character).filter(Character.slug == payload.slug).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "角色标识已存在")
    character = Character(
        name=payload.name,
        slug=payload.slug,
        summary=payload.summary,
        created_by=user.id,
    )
    db.add(character)
    db.flush()
    version = create_version(
        db,
        character,
        appearance=payload.appearance,
        tone=payload.tone,
        restrictions=payload.restrictions,
        change_note="初始版本",
        image_ids=payload.image_ids,
        user_id=user.id,
    )
    db.refresh(character)
    return character_out(db, character, include_versions=True)


@router.get("/{character_id}", response_model=CharacterOut)
def get_character(character_id: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    ch = get_active_character(db, character_id)
    return character_out(db, ch, include_versions=True)


@router.patch("/{character_id}", response_model=CharacterOut)
def update_character(
    character_id: str,
    payload: CharacterUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "editor")),
):
    # IMMEDIATE transaction + revision check makes same-field concurrent edits
    # fail fast for the second writer instead of silently losing an update.
    from app.services.tx import immediate_transaction

    with immediate_transaction(db):
        ch = (
            db.query(Character)
            .filter(Character.id == character_id)
            .with_for_update()
            .first()
        )
        if ch is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "角色不存在")
        ensure_editable(ch)
        if ch.revision != payload.expected_revision:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"字段已被他人修改（服务器版本号 {ch.revision}，你基于 {payload.expected_revision}），请刷新后合并修改",
            )
        if payload.name is not None:
            ch.name = payload.name
        if payload.summary is not None:
            ch.summary = payload.summary
        ch.revision += 1
    db.refresh(ch)
    return character_out(db, ch, include_versions=True)


@router.post("/{character_id}/versions", response_model=VersionOut, status_code=status.HTTP_201_CREATED)
def publish_version(
    character_id: str,
    payload: VersionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "editor")),
):
    ch = get_active_character(db, character_id, for_update=True)
    ensure_editable(ch)
    version = create_version(
        db,
        ch,
        appearance=payload.appearance,
        tone=payload.tone,
        restrictions=payload.restrictions,
        change_note=payload.change_note,
        image_ids=payload.image_ids,
        user_id=user.id,
    )
    return version_out(db, version)


@router.get("/{character_id}/versions/{version_id}", response_model=VersionOut)
def get_version(
    character_id: str,
    version_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
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
    return version_out(db, version)
