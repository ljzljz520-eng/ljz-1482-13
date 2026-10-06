"""Transaction helpers for concurrency-critical write paths.

``immediate_transaction`` emits ``BEGIN IMMEDIATE`` on SQLite (acquiring the
writer lock up front, equivalent to taking a table-level serialization point;
on PostgreSQL it is a normal transaction that still benefits from explicit
``SELECT ... FOR UPDATE`` row locks). Lock-busy responses are retried briefly.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.config import get_settings

logger = logging.getLogger("workbench.tx")


@contextmanager
def immediate_transaction(db: Session, *, retries: int = 8, delay: float = 0.05) -> Iterator[Session]:
    is_sqlite = get_settings().database_url.startswith("sqlite")
    attempt = 0
    while True:
        try:
            if is_sqlite:
                db.execute(text("BEGIN IMMEDIATE"))
            yield db
            db.commit()
            return
        except OperationalError as exc:  # database is locked (SQLITE_BUSY)
            db.rollback()
            msg = str(exc).lower()
            if is_sqlite and ("locked" in msg or "busy" in msg) and attempt < retries:
                attempt += 1
                logger.debug("database locked, retrying (%s/%s)", attempt, retries)
                time.sleep(delay * attempt)
                continue
            raise
