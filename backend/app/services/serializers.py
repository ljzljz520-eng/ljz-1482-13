"""模型 -> DTO 序列化，集中处理引用解析（固定/跟随）与待复核判定。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import (
    Character,
    CharacterVersion,
    CoverJob,
    ExportImageRef,
    GeneratedAsset,
    ImageAsset,
    RefMode,
    ReferenceImage,
    Script,
    ScriptCharacterLink,
)
from app import schemas

MEDIA_PREFIX = "/media"


def image_url(asset: ImageAsset) -> str:
    return f"{MEDIA_PREFIX}/{asset.storage_key}"


def reference_image_out(db: Session, ri: ReferenceImage) -> schemas.ReferenceImageOut:
    asset = db.get(ImageAsset, ri.image_asset_id)
    return schemas.ReferenceImageOut(
        id=ri.id,
        image_asset_id=ri.image_asset_id,
        caption=ri.caption,
        url=image_url(asset) if asset else "",
        license_granted=asset.license_granted if asset else False,
        license_note=asset.license_note if asset else "",
        width=asset.width if asset else 0,
        height=asset.height if asset else 0,
    )


def version_out(db: Session, v: CharacterVersion, *, with_images: bool = True) -> schemas.VersionOut:
    from app.models import User
    creator = db.get(User, v.created_by)
    images = []
    if with_images:
        ris = db.query(ReferenceImage).filter_by(version_id=v.id).all()
        images = [reference_image_out(db, ri) for ri in ris]
    return schemas.VersionOut(
        id=v.id,
        version=v.version,
        appearance=v.appearance,
        tone=v.tone,
        restrictions=v.restrictions,
        change_note=v.change_note,
        created_by_name=creator.display_name if creator else None,
        created_at=v.created_at,
        images=images,
    )


def link_needs_review(link: ScriptCharacterLink, character: Character) -> bool:
    """已批准台词在角色改版后是否需要复核。

    - pinned：effective_version 固定，不受改版影响，无需复核。
    - floating：最新版高于已批准/生效版本时，解释可能漂移，必须人工复核，
      且系统绝不自动改写 approved_text 的解释。
    """
    if link.approved_text is None:
        return False
    if link.ref_mode == RefMode.pinned:
        return False
    baseline = link.approved_version or link.effective_version
    if baseline is None:
        return False
    return character.latest_version > baseline


def script_ref_out(db: Session, link: ScriptCharacterLink) -> schemas.ScriptRefOut:
    character = db.get(Character, link.character_id)
    pinned_version: int | None = None
    if link.pinned_version_id is not None:
        pv = db.get(CharacterVersion, link.pinned_version_id)
        pinned_version = pv.version if pv else None
    return schemas.ScriptRefOut(
        link_id=link.id,
        script_id=link.script_id,
        character_id=link.character_id,
        title="",  # 由 script_out 补
        scene_code="",
        ref_mode=link.ref_mode,
        pinned_version=pinned_version,
        effective_version=link.effective_version,
        latest_version=character.latest_version if character else 0,
        approved_text=link.approved_text,
        approved_version=link.approved_version,
        needs_review=bool(character and link_needs_review(link, character)),
    )


def script_out(db: Session, script: Script) -> schemas.ScriptOut:
    refs: list[schemas.ScriptRefOut] = []
    for link in script.links:
        ref = script_ref_out(db, link)
        ref.title = script.title
        ref.scene_code = script.scene_code
        refs.append(ref)
    return schemas.ScriptOut(
        id=script.id,
        title=script.title,
        scene_code=script.scene_code,
        content=script.content,
        created_at=script.created_at,
        updated_at=script.updated_at,
        links=refs,
    )


def cover_job_out(db: Session, job: CoverJob) -> schemas.CoverJobOut:
    output_url = None
    if job.output_asset_id is not None:
        asset = db.get(ImageAsset, job.output_asset_id)
        output_url = image_url(asset) if asset else None
    return schemas.CoverJobOut(
        id=job.id,
        character_version_id=job.character_version_id,
        source_asset_id=job.source_asset_id,
        output_asset_id=job.output_asset_id,
        output_url=output_url,
        state=job.state,
        crop_x=job.crop_x,
        crop_y=job.crop_y,
        crop_w=job.crop_w,
        crop_h=job.crop_h,
        target_width=job.target_width,
        target_height=job.target_height,
        params_fingerprint=job.params_fingerprint,
        attempts=job.attempts,
        last_error=job.last_error,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def character_out(
    db: Session,
    character: Character,
    *,
    with_latest: bool = False,
    counts: bool = True,
) -> schemas.CharacterOut:
    pinned = floating = 0
    if counts:
        links = db.query(ScriptCharacterLink).filter_by(character_id=character.id).all()
        pinned = sum(1 for l in links if l.ref_mode == RefMode.pinned)
        floating = sum(1 for l in links if l.ref_mode == RefMode.floating)
    latest = None
    if with_latest:
        v = (
            db.query(CharacterVersion)
            .filter_by(character_id=character.id, version=character.latest_version)
            .one_or_none()
        )
        if v:
            latest = version_out(db, v)
    return schemas.CharacterOut(
        id=character.id,
        name=character.name,
        code=character.code,
        status=character.status.value,
        latest_version=character.latest_version,
        lock_version=character.lock_version,
        created_at=character.created_at,
        updated_at=character.updated_at,
        latest=latest,
        pinned_count=pinned,
        floating_count=floating,
    )
