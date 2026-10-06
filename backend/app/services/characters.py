"""Character versioning and approved-line interpretation protection.

Core rule: publishing a new version must never silently change how an already
approved line is interpreted. Pinned references stay untouched; floating
("follow latest") approved lines keep their frozen snapshot and are flagged for
human re-review.
"""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import (
    Character,
    CharacterVersion,
    Line,
    ReferenceImage,
    ScriptCharacter,
    VersionImage,
)
from app.services import reviews as review_service


def get_active_character(db: Session, character_id: str, for_update: bool = False) -> Character:
    q = db.query(Character).filter(Character.id == character_id)
    if for_update:
        q = q.with_for_update()
    character = q.first()
    if character is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "角色不存在")
    return character


def ensure_editable(character: Character) -> None:
    if character.status != "active":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"角色已退役（{character.status}），不能再新增引用或修改",
        )


def snapshot_version(version: CharacterVersion) -> dict:
    return {
        "version_id": version.id,
        "version_no": version.version_no,
        "appearance": version.appearance,
        "tone": version.tone,
        "restrictions": version.restrictions,
    }


def create_version(
    db: Session,
    character: Character,
    *,
    appearance: str,
    tone: str,
    restrictions: str,
    change_note: str,
    image_ids: list[str],
    user_id: str,
) -> CharacterVersion:
    """Append an immutable version, point latest at it, protect approved lines."""
    # Validate image ids and licenses up-front.
    images: list[ReferenceImage] = []
    for image_id in image_ids:
        img = db.query(ReferenceImage).filter(ReferenceImage.id == image_id).first()
        if img is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"参考图 {image_id} 不存在")
        if img.license_status != "licensed":
            raise HTTPException(status.HTTP_409_CONFLICT, f"参考图 {img.filename} 授权已撤销")
        images.append(img)

    last = (
        db.query(CharacterVersion)
        .filter(CharacterVersion.character_id == character.id)
        .order_by(CharacterVersion.version_no.desc())
        .with_for_update()
        .first()
    )
    next_no = (last.version_no + 1) if last else 1
    version = CharacterVersion(
        character_id=character.id,
        version_no=next_no,
        appearance=appearance,
        tone=tone,
        restrictions=restrictions,
        change_note=change_note,
        created_by=user_id,
    )
    db.add(version)
    db.flush()
    for img in images:
        db.add(VersionImage(version_id=version.id, image_id=img.id))

    previous_latest_id = character.current_version_id
    character.current_version_id = version.id
    character.revision += 1
    db.flush()

    # Approved lines belonging to "follow latest" script refs are the only ones
    # that semantically float. Freeze is already in place; we flag instead of
    # mutating interpretation.
    floating_script_ids = [
        sc.id
        for sc in db.query(ScriptCharacter)
        .filter(
            ScriptCharacter.character_id == character.id,
            ScriptCharacter.pin_mode == "latest",
        )
        .all()
    ]
    flagged = 0
    if floating_script_ids and previous_latest_id:
        from app.models import Scene

        rows = (
            db.query(Line, Scene)
            .join(Scene, Line.scene_id == Scene.id)
            .join(ScriptCharacter, ScriptCharacter.script_id == Scene.script_id)
            .filter(
                Line.character_id == character.id,
                Line.version_id == previous_latest_id,
                Line.approved.is_(True),
                ScriptCharacter.pin_mode == "latest",
            )
            .all()
        )
        for line, scene in rows:
            line.needs_recheck = True
            line.recheck_reason = (
                f"角色已发布 v{next_no}，该台词按“跟随最新版”引用，"
                "已冻结旧解释，等待人工复核"
            )
            flagged += 1
            review_service.open_review(
                db,
                kind="line_recheck",
                severity="warning",
                message=f"场次 {scene.code} 的已批准台词需按 v{next_no} 复核",
                character_id=character.id,
                version_id=version.id,
                line_id=line.id,
                scene_id=scene.id,
            )
    db.commit()
    db.refresh(version)
    return version
