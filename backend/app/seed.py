"""Idempotent demo seed: users, characters with versions, a full script."""
from __future__ import annotations

import io
import logging

from PIL import Image, ImageDraw
from sqlalchemy.orm import Session

from app.models import (
    Character,
    CharacterVersion,
    CoverJob,
    ExportAsset,
    ExportImage,
    ExportSnapshot,
    GeneratedAsset,
    Line,
    ReferenceImage,
    Scene,
    Script,
    ScriptCharacter,
    User,
    utcnow,
)
from app.security import hash_password, make_token
from app.services import media
from app.services.characters import snapshot_version
from app.services.exports import build_export

logger = logging.getLogger("workbench.seed")

USERS = [
    ("admin", "平台管理员", "admin", "123456"),
    ("editor", "编剧小林", "editor", "123456"),
    ("viewer", "审片老王", "viewer", "123456"),
]


def _gradient_image(path: str, c1: tuple, c2: tuple, w: int = 900, h: int = 1200) -> None:
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        color = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
        draw.line([(0, y), (w, y)], fill=color)
    # decorative circles suggesting character concept art
    for i, (cx, cy, r, fill) in enumerate(
        [(w // 2, h // 3, 160, (255, 255, 255)), (w // 3, int(h * 0.7), 110, (0, 0, 0))]
    ):
        alpha = int(70 + 40 * i)
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(overlay).ellipse(
            (cx - r, cy - r, cx + r, cy + r), fill=(*fill, alpha)
        )
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)
    img.save(path, format="PNG")


def _cover_asset(path: str, color: tuple, w: int = 1024, h: int = 1024) -> None:
    img = Image.new("RGB", (w, h), color)
    draw = ImageDraw.Draw(img)
    draw.rectangle((40, 40, w - 40, h - 40), outline=(255, 255, 255), width=8)
    draw.ellipse((w // 2 - 220, 220, w // 2 + 220, 660), fill=(255, 255, 255))
    draw.rectangle((w // 2 - 260, 660, w // 2 + 260, 900), fill=(30, 41, 59))
    img.save(path, format="JPEG", quality=88)


def seed_all(db: Session) -> None:
    media.ensure_dirs()
    users: dict[str, User] = {}
    for username, display, role, password in USERS:
        user = User(
            username=username,
            display_name=display,
            role=role,
            password_hash=hash_password(password),
            api_token=make_token(username),
        )
        db.add(user)
        users[username] = user
    db.flush()
    admin = users["admin"]
    editor = users["editor"]

    # ---- source images ----
    img_specs = [
        ("linwan-concept-v1.png", (22, 93, 255), (124, 196, 255)),
        ("linwan-costume-v2.png", (124, 58, 237), (224, 170, 255)),
        ("guhe-concept.png", (255, 125, 0), (255, 205, 140)),
        ("xiaoman-concept.png", (16, 185, 129), (167, 243, 208)),
    ]
    images: dict[str, ReferenceImage] = {}
    for filename, c1, c2 in img_specs:
        import os

        path = os.path.join(media.IMAGES_DIR, filename)
        _gradient_image(path, c1, c2)
        ref = ReferenceImage(
            filename=filename,
            storage_path=path,
            mime_type="image/png",
            width=900,
            height=1200,
            uploaded_by=editor.id,
        )
        db.add(ref)
        images[filename] = ref
    db.flush()

    def make_character(slug: str, name: str, summary: str) -> Character:
        ch = Character(name=name, slug=slug, summary=summary, created_by=editor.id)
        db.add(ch)
        db.flush()
        return ch

    def add_version(ch: Character, no: int, appearance: str, tone: str, restrictions: str,
                    note: str, imgs: list[ReferenceImage]) -> CharacterVersion:
        v = CharacterVersion(
            character_id=ch.id, version_no=no, appearance=appearance, tone=tone,
            restrictions=restrictions, change_note=note, created_by=editor.id,
        )
        db.add(v)
        db.flush()
        from app.models import VersionImage

        for img in imgs:
            db.add(VersionImage(version_id=v.id, image_id=img.id))
        ch.current_version_id = v.id
        ch.revision = no
        return v

    linwan = make_character("lin-wan", "林晚", "雨夜独行的年轻侦探，冷静外表下藏着对真相的执拗。")
    v1 = add_version(
        linwan, 1,
        appearance="齐肩黑发，深灰色风衣，银色怀表；雨夜常戴黑色皮手套。",
        tone="克制、低声、句尾短促；只在推理时语速加快。",
        restrictions="禁止卖萌语气；不使用网络流行语；不提及品牌名称。",
        note="初始角色设定",
        imgs=[images["linwan-concept-v1.png"]],
    )
    v2 = add_version(
        linwan, 2,
        appearance="齐肩黑发（新增一缕蓝挑染），藏蓝色收腰风衣，银色怀表；雨夜常戴黑色皮手套。",
        tone="克制、低声、句尾短促；面对妹妹时会停顿半秒，情绪更柔软。",
        restrictions="禁止卖萌语气；不使用网络流行语；不提及品牌名称；感情戏不直白说“爱”。",
        note="第 3 幕造型升级，补充亲情线语气",
        imgs=[images["linwan-concept-v1.png"], images["linwan-costume-v2.png"]],
    )

    guhe = make_character("gu-he", "顾珩", "表面温润的画廊主，实际是横跨双城的伪画中间商。")
    gv1 = add_version(
        guhe, 1,
        appearance="金丝眼镜，驼色大衣，左手戴黑色玛瑙戒指；永远拄一把黑伞。",
        tone="优雅、缓慢、引经据典；撒谎时音量不变但会先微笑。",
        restrictions="不出现粗口；不直接承认犯罪事实；对话中不评价真实画家。",
        note="初始角色设定",
        imgs=[images["guhe-concept.png"]],
    )

    xiaoman = make_character("xiao-man", "小满", "林晚的妹妹，大学生，镜头感强的 vlogger。")
    xv1 = add_version(
        xiaoman, 1,
        appearance="双马尾，明黄色冲锋衣，挂着复古胶片相机。",
        tone="活泼、跳脱、爱用比喻；害怕时会反向说冷笑话。",
        restrictions="不出现成人向表达；不植入真实 App。",
        note="初始角色设定",
        imgs=[images["xiaoman-concept.png"]],
    )
    db.flush()

    # ---- active covers for linwan v2 and guhe ----
    import os

    for ch, version, color in [
        (linwan, v2, (22, 93, 255)),
        (guhe, gv1, (255, 125, 0)),
    ]:
        name = f"cover-{ch.slug}-v{version.version_no}.jpg"
        path = os.path.join(media.ASSETS_DIR, name)
        _cover_asset(path, color)
        job = CoverJob(
            character_id=ch.id, version_id=version.id,
            source_image_id=images["linwan-concept-v1.png"].id if ch is linwan else images["guhe-concept.png"].id,
            crop_params={"x": 0.05, "y": 0.05, "width": 0.9, "height": 0.9,
                         "target_width": 1024, "target_height": 1024},
            crop_hash=f"seed-{ch.id}",
            status="succeeded", attempts=1, requested_by=editor.id,
            processed_at=utcnow(),
        )
        db.add(job)
        db.flush()
        asset = GeneratedAsset(
            kind="cover", character_id=ch.id, version_id=version.id,
            source_image_id=job.source_image_id, storage_path=path,
            crop_params=job.crop_params, is_active_cover=True, job_id=job.id,
            created_by=editor.id,
        )
        db.add(asset)
        db.flush()
        job.result_asset_id = asset.id

    # ---- script + scenes ----
    script = Script(title="《雨夜画廊》第 7 集", synopsis="林晚追查伪画链条，与顾珩在雨夜画廊正面对峙。",
                    created_by=editor.id)
    db.add(script)
    db.flush()
    s1 = Scene(script_id=script.id, code="EP07-01", title="雨夜巷口", sort_order=1)
    s2 = Scene(script_id=script.id, code="EP07-02", title="画廊密室", sort_order=2)
    s3 = Scene(script_id=script.id, code="EP07-03", title="天台追问", sort_order=3)
    db.add_all([s1, s2, s3])
    db.flush()

    db.add_all([
        # 林晚：固定 v1（导演要求这一集维持旧造型语气）
        ScriptCharacter(script_id=script.id, character_id=linwan.id,
                        pin_mode="pinned", pinned_version_id=v1.id),
        # 顾珩：跟随最新版
        ScriptCharacter(script_id=script.id, character_id=guhe.id, pin_mode="latest"),
        ScriptCharacter(script_id=script.id, character_id=xiaoman.id, pin_mode="latest"),
    ])
    db.flush()

    lines_spec = [
        (s1, linwan, v1, "雨再大一点，监控就只剩三个死角。", True),
        (s1, xiaoman, xv1, "姐你听我解释，我只是来拍雨景的……好吧还有画廊的瓜。", False),
        (s2, guhe, gv1, "林小姐懂画吗？懂画的人，从不问画是真是假。", True),
        (s2, linwan, v1, "我不问画。我问的是，画上这枚指纹的主人去了哪里。", True),
        (s3, linwan, v1, "你撑伞的样子，和监控里逃跑的人一模一样。", False),
    ]
    for scene, ch, ver, text, approved in lines_spec:
        line = Line(
            scene_id=scene.id, character_id=ch.id, version_id=ver.id, content=text,
            approved=approved,
        )
        if approved:
            line.approved_by = admin.id
            line.approved_at = utcnow()
            line.interpretation_snapshot = snapshot_version(ver)
        db.add(line)
    db.flush()

    # ---- one historical export ----
    export = build_export(db, script, editor.id, "送审版 v2026.10.01")
    db.commit()
    logger.info("seed complete: %s characters, export %s", 3, export.id)
