"""Immutable export snapshots.

Exports freeze script content, resolved character versions, approved line
interpretations and the cover assets/images included at export time. The
export<->object links are also the protection set for image cleanup: objects
still used by a historical export must never be physically deleted.
"""
from __future__ import annotations

from fastapi import HTTPException, status
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
    Scene,
    Script,
    ScriptCharacter,
    VersionImage,
)


def build_export(db: Session, script: Script, user_id: str, label: str) -> ExportSnapshot:
    scenes = (
        db.query(Scene).filter(Scene.script_id == script.id).order_by(Scene.sort_order).all()
    )
    script_chars = db.query(ScriptCharacter).filter(ScriptCharacter.script_id == script.id).all()
    characters = {c.id: c for c in db.query(Character).filter(
        Character.id.in_([sc.character_id for sc in script_chars] or ["__none__"])
    ).all()}

    version_ids: set[str] = set()
    resolved_chars = []
    for sc in script_chars:
        character = characters.get(sc.character_id)
        if sc.pin_mode == "pinned" and sc.pinned_version_id:
            resolved_id = sc.pinned_version_id
        else:
            resolved_id = character.current_version_id if character else None
        resolved_no = None
        if resolved_id:
            v = db.query(CharacterVersion).get(resolved_id)
            resolved_no = v.version_no if v else None
            version_ids.add(resolved_id)
        resolved_chars.append(
            {
                "character_id": sc.character_id,
                "character_name": character.name if character else None,
                "pin_mode": sc.pin_mode,
                "pinned_version_id": sc.pinned_version_id,
                "resolved_version_id": resolved_id,
                "resolved_version_no": resolved_no,
                "status": character.status if character else None,
            }
        )

    scene_payload = []
    asset_ids: set[str] = set()
    line_rows = (
        db.query(Line, Scene, CharacterVersion)
        .join(Scene, Line.scene_id == Scene.id)
        .join(CharacterVersion, Line.version_id == CharacterVersion.id)
        .filter(Scene.script_id == script.id)
        .order_by(Scene.sort_order)
        .all()
    )
    lines_payload = []
    for line, scene, version in line_rows:
        version_ids.add(version.id)
        # Prefer the cover bound to the exact approved version (historical
        # accuracy); fall back to the character card's current cover.
        cover = (
            db.query(GeneratedAsset)
            .filter(
                GeneratedAsset.character_id == line.character_id,
                GeneratedAsset.is_active_cover.is_(True),
            )
            .order_by(
                # exact version match first
                # (SQLite/Postgres both support this CASE expression)
            )
            .first()
        )
        exact = (
            db.query(GeneratedAsset)
            .filter(
                GeneratedAsset.character_id == line.character_id,
                GeneratedAsset.version_id == line.version_id,
            )
            .order_by(GeneratedAsset.created_at.desc())
            .first()
        )
        if exact is not None:
            cover = exact
        if cover:
            asset_ids.add(cover.id)
        lines_payload.append(
            {
                "line_id": line.id,
                "scene_code": scene.code,
                "character_id": line.character_id,
                "resolved_version_id": version.id,
                "resolved_version_no": version.version_no,
                "content": line.content,
                "approved": line.approved,
                "needs_recheck": line.needs_recheck,
                "interpretation_snapshot": line.interpretation_snapshot,
                "cover_asset_id": cover.id if cover else None,
            }
        )
    for scene in scenes:
        scene_payload.append({"id": scene.id, "code": scene.code, "title": scene.title})

    image_ids = {
        row[0]
        for row in db.query(VersionImage.image_id)
        .filter(VersionImage.version_id.in_(list(version_ids) or ["__none__"]))
        .all()
    }
    # Also retain sources of any succeeded cover assets in the export.
    for asset in db.query(GeneratedAsset).filter(GeneratedAsset.id.in_(list(asset_ids) or ["__none__"])).all():
        if asset.source_image_id:
            image_ids.add(asset.source_image_id)

    payload = {
        "script": {"id": script.id, "title": script.title, "synopsis": script.synopsis},
        "version_ids": sorted(version_ids),
        "characters": resolved_chars,
        "scenes": scene_payload,
        "lines": lines_payload,
    }
    export = ExportSnapshot(
        script_id=script.id, label=label, payload=payload, created_by=user_id
    )
    db.add(export)
    db.flush()
    for asset_id in sorted(asset_ids):
        db.add(ExportAsset(export_id=export.id, asset_id=asset_id))
    for image_id in sorted(image_ids):
        db.add(ExportImage(export_id=export.id, image_id=image_id))
    db.commit()
    db.refresh(export)
    return export
