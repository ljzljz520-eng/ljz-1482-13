"""脚本服务：显式两种引用模式；批准冻结；退役期间新增引用的并发处理。"""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.models import (
    Character,
    CharacterStatus,
    CharacterVersion,
    RefMode,
    ReviewItem,
    ReviewKind,
    ReviewState,
    Script,
    ScriptCharacterLink,
    User,
)


def create_script(db: Session, payload: schemas.ScriptCreateIn, user: User) -> Script:
    script = Script(
        title=payload.title,
        scene_code=payload.scene_code,
        content=payload.content,
        created_by=user.id,
    )
    db.add(script)
    db.flush()
    for link_in in payload.links:
        _add_link(db, script, link_in, user)
    db.commit()
    db.refresh(script)
    return script


def _add_link(
    db: Session, script: Script, link_in: schemas.ScriptLinkIn, user: User
) -> ScriptCharacterLink:
    # 锁角色行：与退役流程互斥，杜绝“退役时另一人新增引用”造成悬挂引用
    character = db.execute(
        select(Character).where(Character.id == link_in.character_id).with_for_update()
    ).scalar_one_or_none()
    if character is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "角色不存在")
    if character.status != CharacterStatus.active:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"角色「{character.name}」当前状态为 {character.status.value}，不能新增引用",
        )

    dup = (
        db.query(ScriptCharacterLink)
        .filter_by(script_id=script.id, character_id=character.id)
        .one_or_none()
    )
    if dup:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "同一脚本不能重复引用同一角色")

    pinned_version: CharacterVersion | None = None
    effective: int
    if link_in.ref_mode == RefMode.pinned:
        pinned_version = db.get(CharacterVersion, link_in.pinned_version_id)
        if pinned_version is None or pinned_version.character_id != character.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "固定版本不属于该角色")
        effective = pinned_version.version
    else:
        effective = character.latest_version

    link = ScriptCharacterLink(
        script_id=script.id,
        character_id=character.id,
        ref_mode=link_in.ref_mode,
        pinned_version_id=pinned_version.id if pinned_version else None,
        approved_text=link_in.approved_text,
        approved_version=effective if link_in.approved_text else None,
        effective_version=effective,
    )
    db.add(link)
    return link


def add_link(
    db: Session, script_id, link_in: schemas.ScriptLinkIn, user: User
) -> ScriptCharacterLink:
    script = db.get(Script, script_id)
    if script is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "脚本不存在")
    link = _add_link(db, script, link_in, user)
    db.commit()
    db.refresh(link)
    return link


def update_script(
    db: Session, script: Script, payload: schemas.ScriptUpdateIn
) -> Script:
    if payload.title is not None:
        script.title = payload.title
    if payload.scene_code is not None:
        script.scene_code = payload.scene_code
    if payload.content is not None:
        script.content = payload.content
    db.commit()
    db.refresh(script)
    return script


def remove_link(db: Session, link_id) -> None:
    link = db.get(ScriptCharacterLink, link_id)
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "引用不存在")
    db.delete(link)
    db.commit()


def approve_line(db: Session, payload: schemas.ApproveIn, user: User) -> ScriptCharacterLink:
    """批准台词：把解释冻结在“当前生效版本”，后续改版不会悄悄改变它。"""
    link = db.get(ScriptCharacterLink, payload.link_id)
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "引用不存在")
    character = db.get(Character, link.character_id)
    baseline_version = (
        db.get(CharacterVersion, link.pinned_version_id).version
        if link.ref_mode == RefMode.pinned and link.pinned_version_id
        else character.latest_version
    )
    link.approved_text = payload.approved_text
    link.approved_version = baseline_version
    link.effective_version = baseline_version
    db.commit()
    db.refresh(link)
    return link


def reconfirm_drift(db: Session, link_id, user: User) -> ScriptCharacterLink:
    """人工复核漂移：以当前最新版重新冻结基线（必须显式点击，不自动发生）。"""
    link = db.get(ScriptCharacterLink, link_id)
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "引用不存在")
    character = db.get(Character, link.character_id)
    link.approved_version = character.latest_version
    link.effective_version = character.latest_version
    # 关闭对应的待复核项
    items = (
        db.query(ReviewItem)
        .filter(
            ReviewItem.kind == ReviewKind.approved_drift,
            ReviewItem.script_id == link.script_id,
            ReviewItem.character_id == link.character_id,
            ReviewItem.state == ReviewState.open,
        )
        .all()
    )
    from datetime import datetime, timezone
    for item in items:
        item.state = ReviewState.resolved
        item.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(link)
    return link


def switch_ref_mode(db: Session, link_id, mode: schemas.RefMode, pinned_version_id, user):
    """在 固定版本 / 跟随最新 之间显式切换。"""
    link = db.get(ScriptCharacterLink, link_id)
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "引用不存在")
    character = db.get(Character, link.character_id)
    if mode == RefMode.pinned:
        if pinned_version_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "固定版本必须指定版本")
        v = db.get(CharacterVersion, pinned_version_id)
        if v is None or v.character_id != character.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "版本不属于该角色")
        link.pinned_version_id = v.id
    else:
        link.pinned_version_id = None
    link.ref_mode = mode
    db.commit()
    db.refresh(link)
    return link
