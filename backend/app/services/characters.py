"""角色领域服务：不可变版本追加、乐观锁、退役/软删除并发安全流程。"""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.models import (
    Character,
    CharacterStatus,
    CharacterVersion,
    ImageAsset,
    RefMode,
    ReferenceImage,
    ReviewItem,
    ReviewKind,
    ReviewState,
    Script,
    ScriptCharacterLink,
    User,
)
from app.services import references


class ConflictError(HTTPException):
    def __init__(self, detail: str, extra: dict | None = None):
        super().__init__(status.HTTP_409_CONFLICT, detail)
        self.extra = extra or {}


def create_character(db: Session, payload: schemas.CharacterCreateIn, user: User) -> Character:
    exists = db.query(Character).filter_by(code=payload.code).one_or_none()
    if exists:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"角色编码 {payload.code} 已存在")
    character = Character(
        name=payload.name,
        code=payload.code,
        status=CharacterStatus.active,
        latest_version=1,
        lock_version=1,
        created_by=user.id,
    )
    db.add(character)
    db.flush()
    v1 = CharacterVersion(
        character_id=character.id,
        version=1,
        appearance=payload.appearance,
        tone=payload.tone,
        restrictions=payload.restrictions,
        change_note="初始版本",
        created_by=user.id,
    )
    db.add(v1)
    db.flush()
    db.commit()
    db.refresh(character)
    return character


def append_version(
    db: Session,
    character: Character,
    payload: schemas.VersionCreateIn,
    user: User,
) -> CharacterVersion:
    """以追加方式修改角色。乐观锁防止两人改同一字段互相覆盖。"""
    # SELECT ... FOR UPDATE 锁住角色行，序列化并发提交
    locked = db.execute(
        select(Character).where(Character.id == character.id).with_for_update()
    ).scalar_one()

    if locked.lock_version != payload.expected_lock_version:
        # 记录冲突复核项：后提交者必须先看到先提交者的改动
        review = ReviewItem(
            kind=ReviewKind.edit_conflict,
            state=ReviewState.open,
            character_id=locked.id,
            title=f"角色「{locked.name}」存在并发编辑冲突",
            detail=(
                f"{user.display_name} 基于 lock_version={payload.expected_lock_version} 提交，"
                f"但当前版本已推进到 {locked.lock_version}。请刷新后合并改动再提交。"
            ),
            created_by=user.id,
        )
        db.add(review)
        db.commit()
        raise ConflictError(
            f"角色已被他人修改（当前 lock_version={locked.lock_version}，"
            f"你提交基于 {payload.expected_lock_version}），请刷新合并后重试"
        )

    if locked.status != CharacterStatus.active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "非活跃角色不能追加版本")

    # 校验图片存在且授权有效；新的不可变版本直接绑定当前授权状态通过 ReferenceImage
    assets = db.query(ImageAsset).filter(ImageAsset.id.in_(payload.image_asset_ids)).all()
    found = {a.id for a in assets}
    missing = set(payload.image_asset_ids) - found
    if missing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"参考图不存在: {[str(m) for m in missing]}")
    revoked = [a for a in assets if not a.license_granted]
    if revoked:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"参考图授权已撤销，不能用于新版本: {[str(a.id) for a in revoked]}",
        )

    new_no = locked.latest_version + 1
    version = CharacterVersion(
        character_id=locked.id,
        version=new_no,
        appearance=payload.appearance,
        tone=payload.tone,
        restrictions=payload.restrictions,
        change_note=payload.change_note or f"第 {new_no} 版",
        created_by=user.id,
    )
    db.add(version)
    db.flush()
    for asset in assets:
        db.add(ReferenceImage(version_id=version.id, image_asset_id=asset.id))
    locked.latest_version = new_no
    locked.lock_version += 1
    db.flush()

    # 改版后：已批准的 floating 台词进入待复核（绝不自动改解释）
    _flag_drift_for_floating(db, locked, user)
    db.commit()
    db.refresh(version)
    return version


def _flag_drift_for_floating(db: Session, character: Character, actor: User) -> None:
    links = (
        db.query(ScriptCharacterLink)
        .filter(
            ScriptCharacterLink.character_id == character.id,
            ScriptCharacterLink.ref_mode == RefMode.floating,
            ScriptCharacterLink.approved_text.is_not(None),
        )
        .all()
    )
    for link in links:
        baseline = link.approved_version or link.effective_version
        if baseline is not None and character.latest_version > baseline:
            script = db.get(Script, link.script_id)
            db.add(
                ReviewItem(
                    kind=ReviewKind.approved_drift,
                    state=ReviewState.open,
                    character_id=character.id,
                    script_id=link.script_id,
                    title=f"场次 {script.scene_code if script else link.script_id} 已批准台词待复核",
                    detail=(
                        f"角色「{character.name}」发布 v{character.latest_version}，"
                        f"该场次为“跟随最新版”引用，已批准台词基于 v{baseline}。"
                        "系统保留原解释不变，请人工确认是否重新批准。"
                    ),
                    created_by=actor.id,
                )
            )


# ---------- 退役 / 软删除 ----------

def retire_dry_run(db: Session, character: Character, mode: str) -> schemas.RetireDryRunOut:
    pairs = references.scripts_for_character(db, character.id)
    blocking: list[schemas.ScriptRefOut] = []
    floating = pinned = 0
    from app.services.serializers import script_ref_out

    for script, link in pairs:
        ref = script_ref_out(db, link)
        ref.title = script.title
        ref.scene_code = script.scene_code
        if link.ref_mode == RefMode.pinned:
            pinned += 1
        else:
            floating += 1
        blocking.append(ref)

    gen_count = len(references.generated_assets_for_character(db, character.id))
    exp_count = len(references.export_snapshots_for_character(db, character.id))

    if mode == "soft_delete":
        recommendation = (
            "软删除保留全部反向引用与历史版本；脚本侧引用仍可解析，"
            "角色标记为 soft_deleted 并从默认列表隐藏。适合暂时下线。"
        )
    else:
        if blocking:
            recommendation = (
                "存在脚本引用：建议先迁移到替代角色或改为固定版本归档，再执行退役。"
                "若提供替代角色，流程会在同一事务内把引用迁移后再退役。"
            )
        else:
            recommendation = "无脚本反向引用，可直接退役；历史导出快照中的版本引用会被保留。"
    return schemas.RetireDryRunOut(
        mode=mode,
        blocking_scripts=blocking,
        generated_assets=gen_count,
        export_snapshots=exp_count,
        floating_links=floating,
        pinned_links=pinned,
        recommendation=recommendation,
    )


def retire(
    db: Session,
    character: Character,
    payload: schemas.RetireIn,
    user: User,
) -> Character:
    """并发安全退役流程：

    1. 行级锁锁定角色，复核 lock_version；
    2. 再次查询真实反向引用（脚本/素材/导出）；
    3. soft_delete：只改状态，引用全部保留；
       retire + replacement：在同一事务把脚本引用迁移到替代角色，再退役；
       retire 无替代且仍有引用：409，要求人工处理，不静默断链。
    """
    locked = db.execute(
        select(Character).where(Character.id == character.id).with_for_update()
    ).scalar_one()

    if locked.lock_version != payload.expected_lock_version:
        raise ConflictError(
            f"退役期间角色已被修改（lock_version {payload.expected_lock_version} "
            f"!= {locked.lock_version}），请重新核对反向引用"
        )

    if locked.status in (CharacterStatus.retired, CharacterStatus.soft_deleted):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "角色已处于退役/软删除状态")

    links = db.query(ScriptCharacterLink).filter_by(character_id=locked.id).all()

    if payload.mode == "soft_delete":
        locked.status = CharacterStatus.soft_deleted
        locked.lock_version += 1
        db.commit()
        db.refresh(locked)
        return locked

    # mode == retire
    replacement = None
    if payload.replacement_character_id is not None:
        if payload.replacement_character_id == locked.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "替代角色不能是自身")
        replacement = db.get(Character, payload.replacement_character_id)
        if replacement is None or replacement.status != CharacterStatus.active:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "替代角色不存在或非活跃")

    if links and replacement is None:
        # 退役受阻：登记待复核，拒绝执行，避免“悄悄断引用”
        db.add(
            ReviewItem(
                kind=ReviewKind.retired_referenced,
                state=ReviewState.open,
                character_id=locked.id,
                title=f"角色「{locked.name}」退役受阻：仍有 {len(links)} 处脚本引用",
                detail="请提供替代角色迁移引用，或改用软删除保留引用。",
                created_by=user.id,
            )
        )
        db.commit()
        raise ConflictError(
            f"仍有 {len(links)} 处脚本引用，无法直接退役；请选择替代角色或软删除"
        )

    if replacement is not None:
        _migrate_links(db, locked, replacement, user)

    # 历史导出快照（ExportVersionRef）是不可变归档，保持指向旧版本，不迁移。
    locked.status = CharacterStatus.retired
    locked.lock_version += 1
    db.commit()
    db.refresh(locked)
    return locked


def _migrate_links(
    db: Session, old: Character, replacement: Character, actor: User
) -> None:
    """把脚本引用迁移到替代角色。

    - 原 pinned 引用：迁移为对替代角色最新版的 pinned，并重置已批准状态，
      因为解释对象已换人，必须重新批准；
    - 原 floating 引用：直接跟随替代角色，重置批准基线。
    同一脚本若已引用替代角色，则合并并把旧链接的待复核项保留提示。
    """
    links = db.query(ScriptCharacterLink).filter_by(character_id=old.id).all()
    rep_latest = (
        db.query(CharacterVersion)
        .filter_by(character_id=replacement.id, version=replacement.latest_version)
        .one()
    )
    for link in links:
        existing = (
            db.query(ScriptCharacterLink)
            .filter_by(script_id=link.script_id, character_id=replacement.id)
            .one_or_none()
        )
        if existing is not None:
            script = db.get(Script, link.script_id)
            db.add(
                ReviewItem(
                    kind=ReviewKind.retired_referenced,
                    state=ReviewState.open,
                    character_id=replacement.id,
                    script_id=link.script_id,
                    title=f"场次 {script.scene_code if script else ''} 引用迁移需人工确认",
                    detail=(
                        f"该场次原本同时引用「{old.name}」与「{replacement.name}」，"
                        "退役迁移时保留了替代角色引用，请确认台词解释。"
                    ),
                    created_by=actor.id,
                )
            )
            db.delete(link)
            continue

        link.character_id = replacement.id
        link.ref_mode = RefMode.pinned if link.ref_mode == RefMode.pinned else RefMode.floating
        if link.ref_mode == RefMode.pinned:
            link.pinned_version_id = rep_latest.id
        else:
            link.pinned_version_id = None
        was_approved = link.approved_text is not None
        if was_approved:
            script = db.get(Script, link.script_id)
            db.add(
                ReviewItem(
                    kind=ReviewKind.retired_referenced,
                    state=ReviewState.open,
                    character_id=replacement.id,
                    script_id=link.script_id,
                    title=f"场次 {script.scene_code if script else ''} 已迁移到替代角色，需重新批准",
                    detail=(
                        f"引用由「{old.name}」替换为「{replacement.name}」，"
                        "原已批准台词不再自动生效，请复核。"
                    ),
                    created_by=actor.id,
                )
            )
        link.approved_text = None
        link.approved_version = None
        link.effective_version = rep_latest.version


def restore(db: Session, character: Character, user: User) -> Character:
    locked = db.execute(
        select(Character).where(Character.id == character.id).with_for_update()
    ).scalar_one()
    if locked.status != CharacterStatus.soft_deleted:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "仅软删除角色可恢复")
    locked.status = CharacterStatus.active
    locked.lock_version += 1
    db.commit()
    db.refresh(locked)
    return locked
