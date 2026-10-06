"""Asynchronous cover-image derivation worker.

A job is bound to (character, version, source image, crop parameters). Two
stale-result rules apply:

* jobs whose source image loses authorization fail instead of producing art;
* a job that finishes after a newer cover has been produced for the same
  character card is marked ``staled`` and never overwrites the active cover.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import time

from fastapi import HTTPException, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.config import get_settings
from app.models import (
    Character,
    CharacterVersion,
    CoverJob,
    GeneratedAsset,
    ReferenceImage,
)
from app.services import media, reviews as review_service

logger = logging.getLogger("workbench.cover_worker")
settings = get_settings()


def crop_hash(source_image_id: str, crop: dict) -> str:
    canonical = json.dumps(
        {"src": source_image_id, "crop": crop}, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def get_or_create_job(
    db: Session,
    *,
    character: Character,
    version: CharacterVersion,
    source: ReferenceImage,
    crop: dict,
    user_id: str,
) -> tuple[CoverJob, bool]:
    """Idempotent creation keyed by (character, version, crop hash)."""
    digest = crop_hash(source.id, crop)
    existing = (
        db.query(CoverJob)
        .filter(
            CoverJob.character_id == character.id,
            CoverJob.version_id == version.id,
            CoverJob.crop_hash == digest,
        )
        .first()
    )
    if existing:
        return existing, False
    job = CoverJob(
        character_id=character.id,
        version_id=version.id,
        source_image_id=source.id,
        crop_params=crop,
        crop_hash=digest,
        status="pending",
        requested_by=user_id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job, True


def _render(source: ReferenceImage, crop: dict) -> bytes:
    img = Image.open(source.storage_path).convert("RGB")
    w, h = img.size
    left = int(round(crop["x"] * w))
    upper = int(round(crop["y"] * h))
    right = int(round((crop["x"] + crop["width"]) * w))
    lower = int(round((crop["y"] + crop["height"]) * h))
    left, upper = max(0, left), max(0, upper)
    right, lower = min(w, right), min(h, lower)
    if right - left < 8 or lower - upper < 8:
        raise ValueError("裁切区域过小，至少需要 8×8 像素")
    cropped = img.crop((left, upper, right, lower))
    cropped = cropped.resize(
        (int(crop["target_width"]), int(crop["target_height"])), Image.LANCZOS
    )
    buf = io.BytesIO()
    cropped.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


def process_job(db: Session, job: CoverJob) -> CoverJob:
    from app.models import utcnow

    job.status = "processing"
    job.attempts += 1
    db.commit()

    source = db.query(ReferenceImage).get(job.source_image_id)
    version = db.query(CharacterVersion).get(job.version_id)
    character = db.query(Character).get(job.character_id)
    failure: str | None = None

    if source is None:
        failure = "来源图不存在"
    elif source.license_status != "licensed":
        failure = f"来源图 {source.filename} 授权已撤销，不能生成派生素材"
    elif version is None or character is None:
        failure = "绑定的角色版本已不存在"
    elif job.crop_params.get("force_fail"):
        failure = "素材生成失败：渲染服务返回错误（模拟失败）"

    asset: GeneratedAsset | None = None
    if failure is None:
        try:
            data = _render(source, job.crop_params)
            path, _name = media.save_asset_image(data, ".jpg")
            asset = GeneratedAsset(
                kind="cover",
                character_id=character.id,
                version_id=version.id,
                source_image_id=source.id,
                storage_path=path,
                crop_params=job.crop_params,
                is_active_cover=False,
                job_id=job.id,
                created_by=job.requested_by,
            )
            db.add(asset)
            db.flush()
        except (OSError, UnidentifiedImageError, ValueError) as exc:  # pragma: no cover - defensive
            failure = f"素材生成失败：{exc}"
            logger.warning("cover_job %s failed: %s", job.id, exc)

    if failure is not None:
        job.status = "failed"
        job.error_message = failure
        job.processed_at = utcnow()
        review_service.open_review(
            db,
            kind="cover_failed",
            severity="warning",
            message=failure,
            character_id=job.character_id,
            version_id=job.version_id,
            job_id=job.id,
            image_id=job.source_image_id,
        )
        db.commit()
        return job

    # ---- stale guard -----------------------------------------------------
    # A newer cover already attached to this character card wins. Old results
    # arriving late are recorded but never overwrite the card. Compare the
    # *jobs'* request timestamps so a late older request cannot clobber a cover
    # produced by a newer one.
    active = (
        db.query(GeneratedAsset)
        .filter(
            GeneratedAsset.character_id == character.id,
            GeneratedAsset.is_active_cover.is_(True),
        )
        .with_for_update()
        .first()
    )
    active_is_newer = False
    if active is not None:
        active_job = db.query(CoverJob).get(active.job_id) if active.job_id else None
        if active_job is None:
            # Manually attached cover without a job — treat as authoritative.
            active_is_newer = True
        else:
            active_is_newer = (active_job.created_at, active_job.id) >= (
                job.created_at,
                job.id,
            )

    if active_is_newer:
        job.status = "stale"
        job.error_message = "旧任务晚到：角色卡已使用更新的封面，结果不覆盖"
        job.result_asset_id = asset.id
        job.processed_at = utcnow()
        review_service.open_review(
            db,
            kind="stale_cover",
            severity="info",
            message="旧封面任务晚到，已保留为历史素材，未覆盖当前角色卡",
            character_id=character.id,
            version_id=version.id,
            job_id=job.id,
        )
        db.commit()
        return job

    asset.is_active_cover = True
    job.status = "succeeded"
    job.result_asset_id = asset.id
    job.processed_at = utcnow()
    db.commit()
    return job


def tick(db: Session | None = None, limit: int = 5) -> int:
    """Process up to ``limit`` pending jobs. Returns number processed."""
    own_session = db is None
    if own_session:
        db = SessionLocal()
    try:
        jobs = (
            db.query(CoverJob)
            .filter(CoverJob.status == "pending")
            .order_by(CoverJob.created_at.asc())
            .limit(limit)
            .all()
        )
        for job in jobs:
            process_job(db, job)
        return len(jobs)
    finally:
        if own_session:
            db.close()


_worker_started = False


def start_background_worker() -> None:
    global _worker_started
    if _worker_started or not settings.enable_worker:
        return
    _worker_started = True

    import threading

    def _loop() -> None:
        # Wait for the web process/DB to be ready.
        time.sleep(2.0)
        while True:
            try:
                tick()
            except Exception:  # pragma: no cover - defensive loop
                logger.exception("cover worker iteration failed")
            time.sleep(settings.worker_interval_seconds)

    thread = threading.Thread(target=_loop, name="cover-worker", daemon=True)
    thread.start()
    logger.info("cover derivation worker started")
