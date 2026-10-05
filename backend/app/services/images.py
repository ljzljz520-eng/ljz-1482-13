"""图片资产：上传、授权撤销影响分析、安全 GC（历史导出仍算引用）。"""
from __future__ import annotations

import os
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app import schemas
from app.config import settings
from app.models import (
    Character,
    CharacterVersion,
    CoverJob,
    GeneratedAsset,
    ImageAsset,
    JobState,
    ReferenceImage,
    ReviewItem,
    ReviewKind,
    ReviewState,
    Script,
    ScriptCharacterLink,
    User,
)
from app.services import references
from app.services.serializers import image_url, script_ref_out

_ALLOWED = {"image/png", "image/jpeg", "image/webp"}


def upload_image(db: Session, file: UploadFile, license_note: str, user: User) -> ImageAsset:
    if file.content_type not in _ALLOWED:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"仅支持 {sorted(_ALLOWED)}，收到 {file.content_type}"
        )
    data = file.file.read()
    if not data or len(data) > 10 * 1024 * 1024:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "文件为空或超过 10MB")

    from PIL import Image
    import io
    try:
        im = Image.open(io.BytesIO(data))
        im.verify()
        width, height = im.size
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "无法解析的图片文件") from exc

    ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[file.content_type]
    key = f"sources/{uuid.uuid4().hex}.{ext}"
    os.makedirs(os.path.join(settings.media_dir, "sources"), exist_ok=True)
    with open(os.path.join(settings.media_dir, key), "wb") as fh:
        fh.write(data)

    asset = ImageAsset(
        storage_key=key,
        original_filename=file.filename or key,
        mime_type=file.content_type,
        width=width,
        height=height,
        license_granted=True,
        license_note=license_note,
        uploaded_by=user.id,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def revoke_or_grant_license(
    db: Session, asset: ImageAsset, payload: schemas.LicenseIn, user: User
) -> schemas.LicenseImpactOut:
    was_granted = asset.license_granted
    asset.license_granted = payload.license_granted
    asset.license_note = payload.license_note

    # 影响面分析：哪些角色版本、哪些场次、哪些待处理任务、哪些历史导出
    rows = references.versions_using_image(db, asset.id)
    version_briefs: list[schemas.VersionBriefOut] = []
    affected_script_ids: set = set()
    for ri, version, character in rows:
        version_briefs.append(
            schemas.VersionBriefOut(
                character_id=character.id,
                character_name=character.name,
                version_id=version.id,
                version=version.version,
            )
        )
        for pair in references.scripts_for_character(db, character.id):
            script, link = pair
            affected_script_ids.add(script.id)

    scenes: list[schemas.ScriptRefOut] = []
    for sid in affected_script_ids:
        script = db.get(Script, sid)
        for link in script.links:
            ref = script_ref_out(db, link)
            ref.title = script.title
            ref.scene_code = script.scene_code
            scenes.append(ref)

    pending_jobs = (
        db.query(CoverJob)
        .filter(
            CoverJob.source_asset_id == asset.id,
            CoverJob.state.in_([JobState.pending, JobState.processing]),
        )
        .count()
    )
    export_count = references.exports_using_image(db, asset.id)
    cover_count = references.generated_covers_for_image(db, asset.id)

    # 撤销时登记待复核并阻止待处理任务继续（worker 会二次校验授权）
    if was_granted and not payload.license_granted and (rows or pending_jobs):
        db.add(
            ReviewItem(
                kind=ReviewKind.license_revoked,
                state=ReviewState.open,
                title=f"来源图授权已撤销：{asset.original_filename}",
                detail=(
                    f"影响 {len(version_briefs)} 个角色版本、{len(scenes)} 个场次、"
                    f"{pending_jobs} 个待处理封面任务；历史导出 {export_count} 份仍引用该图，"
                    "对象不会被物理删除。"
                ),
                created_by=user.id,
            )
        )

    db.commit()
    return schemas.LicenseImpactOut(
        image=schemas.ImageOut(
            id=asset.id,
            url=image_url(asset),
            original_filename=asset.original_filename,
            width=asset.width,
            height=asset.height,
            license_granted=asset.license_granted,
            license_note=asset.license_note,
            created_at=asset.created_at,
        ),
        affected_versions=version_briefs,
        affected_scenes=scenes,
        pending_cover_jobs=pending_jobs,
        export_snapshots=export_count,
        generated_covers=cover_count,
    )


def list_gc_candidates(db: Session) -> list[schemas.GcCandidateOut]:
    assets = db.query(ImageAsset).order_by(ImageAsset.created_at.desc()).all()
    result = []
    for asset in assets:
        usages = references.image_reference_usages(db, asset.id)
        result.append(
            schemas.GcCandidateOut(
                asset=schemas.ImageOut(
                    id=asset.id,
                    url=image_url(asset),
                    original_filename=asset.original_filename,
                    width=asset.width,
                    height=asset.height,
                    license_granted=asset.license_granted,
                    license_note=asset.license_note,
                    created_at=asset.created_at,
                ),
                **usages,
                deletable=references.asset_is_deletable(usages),
            )
        )
    return result


def delete_unreferenced(db: Session) -> dict:
    """物理清理：五类引用（参考图/派生来源/派生产物/在途任务/历史导出）全部为空才删除。"""
    deleted: list[str] = []
    blocked: list[str] = []
    assets = db.query(ImageAsset).all()
    for asset in assets:
        usages = references.image_reference_usages(db, asset.id)
        if references.asset_is_deletable(usages):
            full = os.path.join(settings.media_dir, asset.storage_key)
            try:
                if os.path.exists(full):
                    os.remove(full)
            except OSError:
                blocked.append(str(asset.id))
                continue
            db.delete(asset)
            deleted.append(str(asset.id))
        else:
            blocked.append(str(asset.id))
    db.commit()
    return {"deleted": deleted, "kept": blocked}
