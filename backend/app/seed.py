"""演示数据种子：容器启动时幂等执行（advisory lock 保证多进程只跑一次）。"""
from __future__ import annotations

import io
import os
import uuid

from PIL import Image, ImageDraw
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.logging_conf import get_logger
from app.models import (
    Character,
    CharacterStatus,
    CharacterVersion,
    ExportImageRef,
    ExportSnapshot,
    ExportVersionRef,
    ImageAsset,
    RefMode,
    ReferenceImage,
    ReviewItem,
    ReviewKind,
    ReviewState,
    RoleName,
    Script,
    ScriptCharacterLink,
    User,
)
from app.security import hash_password

logger = get_logger("seed")


def _make_source_image(path: str, color: tuple[int, int, int], label: str, size=(960, 720)) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(im)
    draw.rectangle([40, 40, size[0] - 40, size[1] - 40], outline=(255, 255, 255), width=6)
    draw.text((size[0] // 2 - 60, size[1] // 2), label, fill=(255, 255, 255))
    im.save(path, format="PNG")


def run_seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # 事务级 advisory lock：api 多 worker / worker 容器同时启动时只执行一次
        if engine.dialect.name == "postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(836271)"))
        if db.query(User).count() > 0:
            logger.info("seed skipped: data already present")
            return

        os.makedirs(os.path.join(settings.media_dir, "sources"), exist_ok=True)

        admin = User(
            username="admin",
            display_name="管理员·林溪",
            password_hash=hash_password("123456"),
            role=RoleName.admin,
        )
        editor_a = User(
            username="editor_a",
            display_name="编剧·阿禾",
            password_hash=hash_password("123456"),
            role=RoleName.editor,
        )
        editor_b = User(
            username="editor_b",
            display_name="美术·半夏",
            password_hash=hash_password("123456"),
            role=RoleName.editor,
        )
        viewer = User(
            username="viewer",
            display_name="访客·观察员",
            password_hash=hash_password("123456"),
            role=RoleName.viewer,
        )
        db.add_all([admin, editor_a, editor_b, viewer])
        db.flush()

        # —— 角色 1：瑶光（两版） ——
        yaoguang = Character(
            name="瑶光", code="YG-01", status=CharacterStatus.active,
            latest_version=2, lock_version=2, created_by=admin.id,
        )
        # —— 角色 2：玄矶 ——
        xuanji = Character(
            name="玄矶", code="XJ-02", status=CharacterStatus.active,
            latest_version=1, lock_version=1, created_by=admin.id,
        )
        db.add_all([yaoguang, xuanji])
        db.flush()

        yg_v1 = CharacterVersion(
            character_id=yaoguang.id, version=1,
            appearance="月白长袍，银色发饰，身佩琉璃灯。",
            tone="温和、克制，语速平缓，常用比喻。",
            restrictions="不得使用粗口；不得出现战斗血腥描写。",
            change_note="初始版本", created_by=admin.id,
        )
        yg_v2 = CharacterVersion(
            character_id=yaoguang.id, version=2,
            appearance="月白长袍改为浅青渐变，银饰替换为青玉，琉璃灯保留。",
            tone="温和之外增加坚定感，关键抉择处语气更果断。",
            restrictions="不得使用粗口；不得出现战斗血腥描写；避免现代网络用语。",
            change_note="第二幕造型升级", created_by=editor_b.id,
        )
        xj_v1 = CharacterVersion(
            character_id=xuanji.id, version=1,
            appearance="玄色短打，皮质护腕，背负机械弩。",
            tone="简练、直接，偶尔嘲讽。",
            restrictions="不得渲染残忍机关细节。",
            change_note="初始版本", created_by=admin.id,
        )
        db.add_all([yg_v1, yg_v2, xj_v1])
        db.flush()

        # 参考图
        yg_img_path = os.path.join(settings.media_dir, "sources", f"seed_yg_{uuid.uuid4().hex}.png")
        xj_img_path = os.path.join(settings.media_dir, "sources", f"seed_xj_{uuid.uuid4().hex}.png")
        _make_source_image(yg_img_path, (94, 136, 174), "YAOGUANG REF")
        _make_source_image(xj_img_path, (66, 78, 96), "XUANJI REF")
        yg_asset = ImageAsset(
            storage_key=os.path.relpath(yg_img_path, settings.media_dir),
            original_filename="yaoguang_ref.png", width=960, height=720,
            license_granted=True, license_note="画师已授权（可商用）", uploaded_by=editor_b.id,
        )
        xj_asset = ImageAsset(
            storage_key=os.path.relpath(xj_img_path, settings.media_dir),
            original_filename="xuanji_ref.png", width=960, height=720,
            license_granted=True, license_note="画师已授权（内部演示）", uploaded_by=editor_b.id,
        )
        db.add_all([yg_asset, xj_asset])
        db.flush()
        db.add_all([
            ReferenceImage(version_id=yg_v1.id, image_asset_id=yg_asset.id, caption="v1 设定稿"),
            ReferenceImage(version_id=yg_v2.id, image_asset_id=yg_asset.id, caption="沿用设定稿"),
            ReferenceImage(version_id=xj_v1.id, image_asset_id=xj_asset.id, caption="玄矶立绘"),
        ])

        # —— 脚本：一个固定引用 v1，一个跟随最新（制造“改版后待复核”） ——
        s1 = Script(
            title="第一幕·灯影初遇", scene_code="S01",
            content="瑶光提灯登场，与玄矶在渡口相遇。",
            created_by=editor_a.id,
        )
        s2 = Script(
            title="第二幕·风雨抉择", scene_code="S02",
            content="瑶光必须决定是否点亮璃灯。",
            created_by=editor_a.id,
        )
        s3 = Script(
            title="第三幕·机关小径", scene_code="S03",
            content="玄玑开路，瑶光随行。",
            created_by=editor_a.id,
        )
        db.add_all([s1, s2, s3])
        db.flush()
        link_pinned = ScriptCharacterLink(
            script_id=s1.id, character_id=yaoguang.id, ref_mode=RefMode.pinned,
            pinned_version_id=yg_v1.id,
            approved_text="（温和地）夜深了，渡口的风比灯还凉。",
            approved_version=1, effective_version=1,
        )
        link_floating = ScriptCharacterLink(
            script_id=s2.id, character_id=yaoguang.id, ref_mode=RefMode.floating,
            pinned_version_id=None,
            approved_text="这盏灯，我会自己决定何时点亮。",
            approved_version=1, effective_version=1,  # 最新已是 v2 -> 漂移待复核
        )
        link_xj = ScriptCharacterLink(
            script_id=s3.id, character_id=xuanji.id, ref_mode=RefMode.floating,
            pinned_version_id=None,
            approved_text=None, approved_version=None, effective_version=1,
        )
        link_s1_xj = ScriptCharacterLink(
            script_id=s1.id, character_id=xuanji.id, ref_mode=RefMode.pinned,
            pinned_version_id=xj_v1.id,
            approved_text="让开，或者跟我走。", approved_version=1, effective_version=1,
        )
        db.add_all([link_pinned, link_floating, link_xj, link_s1_xj])

        # 已批准台词漂移待复核（与 seed 数据一致）
        db.add(
            ReviewItem(
                kind=ReviewKind.approved_drift,
                state=ReviewState.open,
                character_id=yaoguang.id,
                script_id=s2.id,
                title="场次 S02 已批准台词待复核",
                detail=(
                    "角色「瑶光」已发布 v2，该场次为“跟随最新版”引用，"
                    "已批准台词基于 v1。系统保留原解释不变，请人工确认。"
                ),
                created_by=editor_b.id,
            )
        )

        # 一个历史导出快照（引用图片，阻止 GC）
        snap = ExportSnapshot(
            label="2026-09 月报导出",
            script_id=s1.id,
            payload='{"type":"script","scene_code":"S01"}',
            created_by=admin.id,
        )
        db.add(snap)
        db.flush()
        db.add_all([
            ExportVersionRef(
                snapshot_id=snap.id, character_id=yaoguang.id,
                character_version_id=yg_v1.id, ref_mode_at_export=RefMode.pinned
            ),
            ExportVersionRef(
                snapshot_id=snap.id, character_id=xuanji.id,
                character_version_id=xj_v1.id, ref_mode_at_export=RefMode.pinned
            ),
            ExportImageRef(snapshot_id=snap.id, image_asset_id=yg_asset.id),
            ExportImageRef(snapshot_id=snap.id, image_asset_id=xj_asset.id),
        ])

        db.commit()
        logger.info("seed complete: users, 2 characters (3 versions), 3 scenes, 1 export snapshot")
    except Exception:
        db.rollback()
        logger.exception("seed failed")
        raise
    finally:
        db.close()
