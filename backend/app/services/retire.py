"""Concurrency-safe retirement of a character.

Two strategies are compared:

* ``soft_delete`` – the character is marked retired; every existing reference is
  preserved (immutable history, exports and approvals remain readable), but no
  new references can be created.
* ``replace`` – references are migrated to a replacement character (pinned refs
  are repointed at the replacement's current version, floating refs float to
  it), after which the old character is retired.

The expected reverse-reference count from the UI is re-checked inside a row
lock so that references created after the pre-check (e.g. another user adding a
script dependency) cannot be silently dropped.
"""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import (
    Character,
    CharacterVersion,
    CoverJob,
    GeneratedAsset,
    Line,
    ScriptCharacter,
)
from app.services import reviews as review_service
from app.services.characters import ensure_editable, get_active_character
from app.services.references import collect_references, total_reference_count
from app.services.tx import immediate_transaction


def retire(
    db: Session,
    character_id: str,
    *,
    strategy: str,
    expected_ref_count: int,
    replacement_character_id: str | None,
) -> dict:
    with immediate_transaction(db):
        return _retire_locked(
            db,
            character_id,
            strategy=strategy,
            expected_ref_count=expected_ref_count,
            replacement_character_id=replacement_character_id,
        )


def _retire_locked(
    db: Session,
    character_id: str,
    *,
    strategy: str,
    expected_ref_count: int,
    replacement_character_id: str | None,
) -> dict:
    character = get_active_character(db, character_id, for_update=True)
    ensure_editable(character)

    # Lock all script refs touching this character to close the race window
    # where another user inserts a dependency between pre-check and retirement.
    existing_refs = (
        db.query(ScriptCharacter)
        .filter(ScriptCharacter.character_id == character_id)
        .with_for_update()
        .all()
    )

    refs = collect_references(db, character)
    actual_total = total_reference_count(refs)
    if actual_total != expected_ref_count:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"反向引用数量已变化（界面预估 {expected_ref_count}，实际 {actual_total}），"
            "请刷新查看受影响场次后重试",
        )

    migrated_script_refs = migrated_pins = 0
    preserved_approved_lines = refs["approved_lines"]["count"]
    review_ids: list[str] = []

    if strategy == "replace":
        if not replacement_character_id or replacement_character_id == character_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "替换策略必须指定另一个替换角色")
        replacement = get_active_character(db, replacement_character_id, for_update=True)
        target_version_id = replacement.current_version_id
        if target_version_id is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "替换角色尚无可用版本")

        for ref in existing_refs:
            # Avoid colliding with an existing dependency on the replacement.
            clash = (
                db.query(ScriptCharacter)
                .filter(
                    ScriptCharacter.script_id == ref.script_id,
                    ScriptCharacter.character_id == replacement.id,
                )
                .first()
            )
            if clash:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "替换角色已被同一脚本引用，无法自动迁移，请先人工合并",
                )
            ref.character_id = replacement.id
            migrated_script_refs += 1
            if ref.pin_mode == "pinned":
                ref.pinned_version_id = target_version_id
                migrated_pins += 1

        # Lines move with the dependency. They keep their frozen snapshot; the
        # new resolution is flagged for review rather than auto-rewritten.
        lines = db.query(Line).filter(Line.character_id == character_id).all()
        for line in lines:
            line.character_id = replacement.id
            line.needs_recheck = True
            line.recheck_reason = f"角色 {character.name} 退役，已迁移至 {replacement.name}，待复核"
            review = review_service.open_review(
                db,
                kind="line_recheck",
                severity="warning",
                message=f"退役替换：台词迁移到 {replacement.name}，需要确认解释",
                character_id=replacement.id,
                version_id=target_version_id,
                line_id=line.id,
                scene_id=line.scene_id,
            )
            review_ids.append(review.id)

        for job in db.query(CoverJob).filter(CoverJob.character_id == character_id).all():
            job.character_id = replacement.id
        for asset in (
            db.query(GeneratedAsset)
            .filter(GeneratedAsset.character_id == character_id)
            .all()
        ):
            asset.character_id = replacement.id
            asset.is_active_cover = False
    else:
        # Soft delete: history retained; raise review items for the affected
        # scenes so operators know what still references the retired character.
        for entry in refs["approved_lines"]["items"] + refs["pending_lines"]["items"]:
            review = review_service.open_review(
                db,
                kind="line_recheck",
                severity="info",
                message=(
                    f"角色 {character.name} 已软删除退役，场次 {entry['scene_code']} "
                    "仍保留历史引用，需要决定保留或替换"
                ),
                character_id=character_id,
                version_id=entry["version_id"],
                line_id=entry["line_id"],
                scene_id=entry["scene_id"],
            )
            review_ids.append(review.id)

    character.status = "retired"
    return {
        "character_id": character_id,
        "status": "retired",
        "strategy": strategy,
        "migrated_script_refs": migrated_script_refs,
        "migrated_pins": migrated_pins,
        "preserved_approved_lines": preserved_approved_lines,
        "review_ids": review_ids,
    }
