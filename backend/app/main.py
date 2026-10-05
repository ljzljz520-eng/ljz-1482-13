"""FastAPI 入口：生命周期内等待数据库并执行种子，挂载媒体目录与全部路由。"""
from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import engine
from app.logging_conf import get_logger
from app.routers import auth, characters, covers, exports, images, review, scripts
from app.seed import run_seed

logger = get_logger("api")


def _wait_for_db(max_attempts: int = 60) -> None:
    from sqlalchemy import exc as sa_exc

    for attempt in range(1, max_attempts + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except (sa_exc.OperationalError, OSError) as exc:
            logger.warning("waiting for database (attempt %s/%s): %s", attempt, max_attempts, exc)
            time.sleep(2)
    raise RuntimeError("数据库连接超时")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _wait_for_db()
    run_seed()
    os.makedirs(settings.media_dir, exist_ok=True)
    logger.info("api started")
    yield


app = FastAPI(
    title="角色工作室 · 版本与依赖管理 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(settings.media_dir, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")


@app.exception_handler(StarletteHTTPException)
async def http_exc_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": str(exc.detail), "code": exc.status_code},
    )


@app.exception_handler(RequestValidationError)
async def validation_exc_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(
            {"message": "入参校验失败", "errors": exc.errors()}
        ),
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "character-studio-api"}


for r in (auth.router, characters.router, scripts.router, images.router,
          covers.router, exports.router, review.router):
    app.include_router(r)
