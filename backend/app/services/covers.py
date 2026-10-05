"""封面派生：创建不可变指纹任务；worker 完成时防止旧任务晚到覆盖新角色卡。"""
from __future__ import annotations

import hashlib
import os
import uuid

from fastapi import HTTPException, status
from PIL import Image
from sqlalchemy.orm import Session

from app import schemas
from app.config import settings
from app.models import (
    Character,
    CharacterStatus,
    CharacterVersion,
    CoverJob,
    GeneratedAsset,
    ImageAsset,
    JobState,
    ReviewItem,
    ReviewKind,
    ReviewState,
    User,
)


def _fingerprint(payload: schemas.CoverJobIn) -> str:
    raw = "|".join(
        [
            str(payload.source_asset_id),
            f"{payload.crop_x:.4f}",
            f"{payload.crop_y:.4f}",
            f"{payload.crop_w:.4f}",
            f"{payload.crop_h:.4f}",
            str(payload.target_width),
            str(payload.target_height),
        ]
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def create_cover_job(
    db: Session, payload: schemas.CoverJobIn, user: User
) -> CoverJob:
    version = db.get(CharacterVersion, payload.character_version_id)
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "角色版本不存在")
    source = db.get(ImageAsset, payload.source_asset_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "来源图不存在")
    if not source.license_granted:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "来源图授权已撤销，不能派生封面")

    job = CoverJob(
        character_version_id=version.id,
        source_asset_id=source.id,
        state=JobState.pending,
        crop_x=payload.crop_x,
        crop_y=payload.crop_y,
        crop_w=payload.crop_w,
        crop_h=payload.crop_h,
        target_width=payload.target_width,
        target_height=payload.target_height,
        params_fingerprint=_fingerprint(payload),
        force_fail=payload.force_fail,
        created_by=user.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _asset_path(asset: ImageAsset) -> str:
    return os.path.join(settings.media_dir, asset.storage_key)


def render_cover(db: Session, job_id) -> JobState:
    """由 worker 调用。包含失败注入与“旧任务晚到”守卫。

    守卫：任务完成时检查该（版本, 指纹）是否已被后续任务的结果占用，
    且当前角色卡是否已推进到更新版本——旧结果写入为 stale，不覆盖任何展示。
    """
    job = db.get(CoverJob, job_id)
    if job is None or job.state not in (JobState.pending, JobState.failed):
        return job.state if job else JobState.cancelled

    job.state = JobState.processing
    job.attempts += 1
    db.commit()

    # 模拟处理耗时（在 worker 进程中 sleep，不阻塞 API）
    import time
    time.sleep(settings.cover_job_delay_seconds)

    # 失败注入：用于验收“素材生成失败”
    if settings.enable_failure_injection and job.force_fail:
        job.state = JobState.failed
        job.last_error = "素材生成失败（注入）：渲染管线返回 5xx"
        db.add(
            ReviewItem(
                kind=ReviewKind.generation_failed,
                state=ReviewState.open,
                job_id=job.id,
                title="封面素材生成失败",
                detail=(
                    f"任务 {job.id} 绑定来源图 {job.source_asset_id} 与裁切参数 "
                    f"{job.params_fingerprint}，请检查后重试。"
                ),
                created_by=job.created_by,
            )
        )
        db.commit()
        return JobState.failed

    source = db.get(ImageAsset, job.source_asset_id)
    if source is None or not source.license_granted:
        job.state = JobState.failed
        job.last_error = "来源图缺失或授权已撤销"
        db.add(
            ReviewItem(
                kind=ReviewKind.generation_failed,
                state=ReviewState.open,
                job_id=job.id,
                title="封面任务中止：来源图授权撤销",
                detail=f"任务 {job.id} 的来源图 {job.source_asset_id} 授权已撤销。",
                created_by=job.created_by,
            )
        )
        db.commit()
        return JobState.failed

    try:
        out_path, width, height = _do_crop(job, source)
    except Exception as exc:  # noqa: BLE001 - 真实管线失败兜底
        job.state = JobState.failed
        job.last_error = f"渲染异常: {type(exc).__name__}: {exc}"[:500]
        db.add(
            ReviewItem(
                kind=ReviewKind.generation_failed,
                state=ReviewState.open,
                job_id=job.id,
                title="封面素材生成失败",
                detail=job.last_error,
                created_by=job.created_by,
            )
        )
        db.commit()
        return JobState.failed

    # —— 旧任务晚到守卫 ——
    # 同版本下：若已存在更晚创建、同指纹且已成功的任务，本次结果标记 stale，不挂到角色卡。
    # 同版本下：只要存在更晚创建且已成功的任务，角色卡封面已被更新的结果占用，
    # 本次晚到结果一律 stale（不区分裁切指纹：卡片只展示最新一张）。
    newer_success = (
        db.query(CoverJob)
        .filter(
            CoverJob.character_version_id == job.character_version_id,
            CoverJob.id != job.id,
            CoverJob.state == JobState.succeeded,
            CoverJob.created_at > job.created_at,
        )
        .count()
    )
    version = db.get(CharacterVersion, job.character_version_id)
    character = db.get(Character, version.character_id)
    stale_by_version = character is not None and version.version < character.latest_version
    # 注：封面绑定具体不可变版本，历史版本封面仍可保留；但“角色卡封面”只指向最新结果。
    # 因此晚到任务输出仍然落盘（审计），但不生成 GeneratedAsset、不参与最新卡片展示。

    output_asset = ImageAsset(
        storage_key=out_path,
        original_filename=f"cover_{job.params_fingerprint}.png",
        mime_type="image/png",
        width=width,
        height=height,
        license_granted=source.license_granted,
        license_note=f"derived from {source.id}",
        uploaded_by=job.created_by,
    )
    db.add(output_asset)
    db.flush()

    if newer_success or stale_by_version:
        job.output_asset_id = output_asset.id
        job.state = JobState.stale
        job.last_error = (
            "旧任务晚到：更新的封面已占用角色卡" if newer_success
            else f"旧任务晚到：角色卡已升级到 v{character.latest_version}，结果仅归档"
        )
        db.commit()
        return JobState.stale

    job.output_asset_id = output_asset.id
    job.state = JobState.succeeded
    job.last_error = None
    db.add(
        GeneratedAsset(
            character_version_id=job.character_version_id,
            source_asset_id=job.source_asset_id,
            output_asset_id=output_asset.id,
            job_id=job.id,
            kind="cover",
            params_fingerprint=job.params_fingerprint,
        )
    )
    db.commit()
    return JobState.succeeded


def _do_crop(job: CoverJob, source: ImageAsset) -> tuple[str, int, int]:
    os.makedirs(settings.media_dir, exist_ok=True)
    src_path = _asset_path(source)
    with Image.open(src_path) as im:
        im = im.convert("RGB")
        W, H = im.size
        left = int(job.crop_x * W)
        top = int(job.crop_y * H)
        right = int(min(W, (job.crop_x + job.crop_w) * W))
        bottom = int(min(H, (job.crop_y + job.crop_h) * H))
        cropped = im.crop((left, top, right, bottom))
        cropped = cropped.resize((job.target_width, job.target_height), Image.LANCZOS)
        key = f"generated/{uuid.uuid4().hex}.png"
        full = os.path.join(settings.media_dir, key)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        cropped.save(full, format="PNG")
    return key, job.target_width, job.target_height


def retry_job(db: Session, job_id) -> CoverJob:
    job = db.get(CoverJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    if job.state not in (JobState.failed, JobState.stale):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "仅失败/过期任务可重试")
    job.state = JobState.pending
    job.last_error = None
    db.commit()
    db.refresh(job)
    return job
