"""Test fixtures: isolated SQLite database, temp media dir and API client."""
import os
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///./test_workbench.db"
os.environ["ENABLE_WORKER"] = "false"
os.environ["MEDIA_ROOT"] = tempfile.mkdtemp(prefix="wb-media-")
os.environ["TOKEN_SECRET"] = "test-secret"

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import User
from app.security import hash_password, make_token
from app.services import media


@pytest.fixture(autouse=True)
def clean_db():
    # Import models so metadata is populated, then reset everything per test.
    # Delete rows instead of dropping tables: SQLite keeps PRAGMA state per
    # connection (the pool hands out different ones), and drop_all otherwise
    # trips foreign-key checks depending on reflection order.
    import app.models  # noqa: F401

    from sqlalchemy import inspect, text

    media.ensure_dirs()
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        existing = set(inspect(conn).get_table_names())
        for table in reversed(Base.metadata.sorted_tables):
            if table.name in existing:
                conn.execute(table.delete())
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    for username, display, role in (
        ("admin", "管理员", "admin"),
        ("editor", "编剧", "editor"),
        ("viewer", "观众", "viewer"),
    ):
        db.add(User(
            username=username, display_name=display, role=role,
            password_hash=hash_password("123456"), api_token=make_token(username),
        ))
    db.commit()
    db.close()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def tokens():
    return {
        "admin": make_token("admin"),
        "editor": make_token("editor"),
        "viewer": make_token("viewer"),
    }


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def h(tokens):
    return {role: auth(t) for role, t in tokens.items()}


def make_png(path, size=(200, 260), color=(40, 120, 220)):
    Image.new("RGB", size, color).save(path, format="PNG")


def upload_image(client, headers, name="ref.png", color=(40, 120, 220)):
    import io

    buf = io.BytesIO()
    Image.new("RGB", (300, 400), color).save(buf, format="PNG")
    buf.seek(0)
    resp = client.post(
        "/images",
        headers=headers,
        files={"file": (name, buf, "image/png")},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def create_character(client, headers, slug="hero", name="主角", image_id=None):
    body = {
        "name": name, "slug": slug, "summary": "测试角色",
        "appearance": "黑风衣", "tone": "冷静", "restrictions": "禁粗口",
    }
    if image_id:
        body["image_ids"] = [image_id]
    r = client.post("/characters", headers=headers, json=body)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def helpers():
    class Helper:
        upload_image = staticmethod(upload_image)
        create_character = staticmethod(create_character)
    return Helper
