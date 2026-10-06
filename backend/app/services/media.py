"""Filesystem helpers for source images and generated assets."""
from __future__ import annotations

import os
import uuid

from app.config import get_settings

settings = get_settings()

IMAGES_DIR = os.path.join(settings.media_root, "images")
ASSETS_DIR = os.path.join(settings.media_root, "assets")


def ensure_dirs() -> None:
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(ASSETS_DIR, exist_ok=True)


def _extension(filename: str, mime: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext in {".png", ".jpg", ".jpeg", ".webp"}:
        return ext
    return {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
    }.get(mime, ".png")


def save_source_image(data: bytes, filename: str, mime: str) -> tuple[str, str]:
    ensure_dirs()
    name = f"{uuid.uuid4().hex}{_extension(filename, mime)}"
    path = os.path.join(IMAGES_DIR, name)
    with open(path, "wb") as fh:
        fh.write(data)
    return path, name


def save_asset_image(data: bytes, ext: str = ".jpg") -> tuple[str, str]:
    ensure_dirs()
    name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(ASSETS_DIR, name)
    with open(path, "wb") as fh:
        fh.write(data)
    return path, name


def remove_file(path: str) -> int:
    try:
        size = os.path.getsize(path)
        os.remove(path)
        return size
    except FileNotFoundError:
        return 0


def image_url(name_or_path: str) -> str:
    name = os.path.basename(name_or_path)
    if name_or_path.startswith(ASSETS_DIR) or f"{os.sep}assets{os.sep}" in name_or_path or "/assets/" in name_or_path:
        return f"/api/media/assets/{name}"
    return f"/api/media/images/{name}"
