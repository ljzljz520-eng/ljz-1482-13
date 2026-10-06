"""Static media serving for uploaded images and generated assets."""
import os

from fastapi import APIRouter, HTTPException, status
from app.models import User
from fastapi.responses import FileResponse

from app.config import get_settings
from app.deps import current_user
from fastapi import Depends

settings = get_settings()
router = APIRouter(prefix="/api/media", tags=["media"])


def _serve(directory: str, name: str):
    # Prevent path traversal: only basename is ever used.
    safe = os.path.basename(name)
    path = os.path.join(directory, safe)
    if not os.path.isfile(path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "文件不存在")
    media_type = "image/webp" if safe.endswith(".webp") else (
        "image/png" if safe.endswith(".png") else "image/jpeg"
    )
    return FileResponse(path, media_type=media_type)


@router.get("/images/{name}")
def get_image_file(name: str, _: User = Depends(current_user)):
    return _serve(os.path.join(settings.media_root, "images"), name)


@router.get("/assets/{name}")
def get_asset_file(name: str, _: User = Depends(current_user)):
    return _serve(os.path.join(settings.media_root, "assets"), name)
