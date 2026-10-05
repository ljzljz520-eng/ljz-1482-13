"""封面异步 worker：轮询 pending 任务，行级锁认领，调用渲染服务。

独立容器进程，与 API 共享同一 PostgreSQL 与 /data/media 卷。
"""
from __future__ import annotations

import time

from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.database import SessionLocal
from app.logging_conf import get_logger
from app.models import CoverJob, JobState
from app.services.covers import render_cover

logger = get_logger("cover-worker")
POLL_INTERVAL = 1.5


def claim_next_job(db) -> CoverJob | None:
    """FOR UPDATE SKIP LOCKED：多 worker 实例也不会重复认领。"""
    job = db.execute(
        select(CoverJob)
        .where(CoverJob.state == JobState.pending)
        .order_by(CoverJob.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    ).scalar_one_or_none()
    return job


def main() -> None:
    logger.info("cover worker started, polling every %.1fs", POLL_INTERVAL)
    while True:
        try:
            db = SessionLocal()
            try:
                job = claim_next_job(db)
                if job is None:
                    db.rollback()
                else:
                    job_id = job.id
                    db.commit()  # 释放认领锁
                    logger.info("claimed cover job %s", job_id)
                    state = _render(job_id)
                    logger.info("cover job %s finished -> %s", job_id, state)
            finally:
                db.close()
        except OperationalError as exc:
            logger.warning("database not ready: %s; retrying", exc.orig)
            time.sleep(3)
        except Exception:  # noqa: BLE001
            logger.exception("worker loop error")
            time.sleep(2)
        time.sleep(POLL_INTERVAL)


def _render(job_id):
    db = SessionLocal()
    try:
        return render_cover(db, job_id)
    finally:
        db.close()


if __name__ == "__main__":
    main()
