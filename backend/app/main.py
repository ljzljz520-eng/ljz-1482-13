"""FastAPI application entry point for the Character Design Workbench."""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.routers import (
    admin,
    auth,
    characters,
    covers,
    exports,
    images,
    lifecycle,
    lines,
    media,
    reviews,
    scripts,
)
from app.services import media as media_service
from app.services.covers import start_background_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("workbench")
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    media_service.ensure_dirs()
    # Seed on first boot when the database is empty.
    db = SessionLocal()
    try:
        from app.models import User

        if db.query(User).count() == 0:
            from app.seed import seed_all

            seed_all(db)
            logger.info("demo data seeded")
    finally:
        db.close()
    start_background_worker()
    logger.info("character design workbench API started")
    yield


app = FastAPI(
    title="角色设计工作台 API",
    version="1.0.0",
    description="角色版本、引用依赖、封面异步任务与退役流程管理",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")] if settings.cors_origins != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (
    auth,
    characters,
    lifecycle,
    scripts,
    lines,
    images,
    covers,
    exports,
    reviews,
    admin,
    media,
):
    app.include_router(module.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "service": "character-workbench"}
