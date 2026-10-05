"""导出快照：冻结当时的角色版本与图片集合；历史导出参与图片 GC 引用计数。"""
from __future__ import annotations

import json

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app import schemas
from app.models import (
    Character,
    CharacterVersion,
    ExportImageRef,
    ExportSnapshot,
    ExportVersionRef,
    GeneratedAsset,
    RefMode,
    ReferenceImage,
    Script,
    User,
)


def create_export(db: Session, payload: schemas.ExportIn, user: User) -> ExportSnapshot:
    snapshot = ExportSnapshot(
        label=payload.label, script_id=payload.script_id, created_by=user.id
    )
    db.add(snapshot)
    db.flush()

    # 导出范围：指定脚本 -> 该脚本引用的角色；否则导出全部活跃角色
    version_pairs: list[tuple[Character, CharacterVersion, RefMode]] = []
    image_ids: set = set()
    if payload.script_id is not None:
        script = db.get(Script, payload.script_id)
        if script is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "脚本不存在")
        snapshot.payload = json.dumps(
            {"type": "script", "scene_code": script.scene_code, "title": script.title},
            ensure_ascii=False,
        )
        for link in script.links:
            character = db.get(Character, link.character_id)
            if link.ref_mode == RefMode.pinned and link.pinned_version_id:
                version = db.get(CharacterVersion, link.pinned_version_id)
            else:
                version = (
                    db.query(CharacterVersion)
                    .filter_by(character_id=character.id, version=character.latest_version)
                    .one()
                )
            version_pairs.append((character, version, link.ref_mode))
    else:
        snapshot.payload = json.dumps({"type": "full"}, ensure_ascii=False)
        for character in db.query(Character).all():
            version = (
                db.query(CharacterVersion)
                .filter_by(character_id=character.id, version=character.latest_version)
                .one()
            )
            version_pairs.append((character, version, RefMode.floating))

    for character, version, mode in version_pairs:
        db.add(
            ExportVersionRef(
                snapshot_id=snapshot.id,
                character_id=character.id,
                character_version_id=version.id,
                ref_mode_at_export=mode,
            )
        )
        for ri in db.query(ReferenceImage).filter_by(version_id=version.id).all():
            image_ids.add(ri.image_asset_id)
        for ga in db.query(GeneratedAsset).filter_by(character_version_id=version.id).all():
            image_ids.add(ga.source_asset_id)
            image_ids.add(ga.output_asset_id)

    for asset_id in image_ids:
        db.add(ExportImageRef(snapshot_id=snapshot.id, image_asset_id=asset_id))

    db.commit()
    db.refresh(snapshot)
    return snapshot
