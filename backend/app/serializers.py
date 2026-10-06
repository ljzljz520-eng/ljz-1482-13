"""ORM -> JSON-friendly dicts for API responses."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import (
    Character,
    CharacterVersion,
    CoverJob,
    GeneratedAsset,
    Line,
    ReferenceImage,
    Scene,
    Script,
    ScriptCharacter,
)
from app.services import media
from app.services.reviews import serialise as review_serialise


def image_out(img: ReferenceImage) -> dict:
    return {
        "id": img.id,
        "filename": img.filename,
        "url": media.image_url(img.storage_path),
        "mime_type": img.mime_type,
        "width": img.width,
        "height": img.height,
        "license_status": img.license_status,
        "created_at": img.created_at,
    }


def version_out(db: Session, version: CharacterVersion, *, include_images: bool = True) -> dict:
    data = {
        "id": version.id,
        "character_id": version.character_id,
        "version_no": version.version_no,
        "appearance": version.appearance,
        "tone": version.tone,
        "restrictions": version.restrictions,
        "change_note": version.change_note,
        "created_by": version.created_by,
        "created_at": version.created_at,
    }
    if include_images:
        data["images"] = [image_out(vi.image) for vi in version.images]
    else:
        data["images"] = []
    return data


def active_cover(db: Session, character_id: str) -> GeneratedAsset | None:
    return (
        db.query(GeneratedAsset)
        .filter(
            GeneratedAsset.character_id == character_id,
            GeneratedAsset.is_active_cover.is_(True),
        )
        .first()
    )


def character_out(db: Session, ch: Character, *, include_versions: bool = False) -> dict:
    current_no = None
    if ch.current_version_id:
        cv = db.query(CharacterVersion).get(ch.current_version_id)
        current_no = cv.version_no if cv else None
    cover = active_cover(db, ch.id)
    data = {
        "id": ch.id,
        "name": ch.name,
        "slug": ch.slug,
        "summary": ch.summary,
        "status": ch.status,
        "revision": ch.revision,
        "current_version_id": ch.current_version_id,
        "current_version_no": current_no,
        "active_cover_url": media.image_url(cover.storage_path) if cover else None,
        "created_by": ch.created_by,
        "updated_at": ch.updated_at,
        "created_at": ch.created_at,
    }
    if include_versions:
        versions = (
            db.query(CharacterVersion)
            .filter(CharacterVersion.character_id == ch.id)
            .order_by(CharacterVersion.version_no.desc())
            .all()
        )
        data["versions"] = [version_out(db, v) for v in versions]
    else:
        data["versions"] = []
    return data


def line_out(db: Session, line: Line) -> dict:
    scene = db.query(Scene).get(line.scene_id)
    version = db.query(CharacterVersion).get(line.version_id)
    character = db.query(Character).get(line.character_id)
    cover = None
    if line.approved:
        cover = (
            db.query(GeneratedAsset)
            .filter(
                GeneratedAsset.character_id == line.character_id,
                GeneratedAsset.version_id == line.version_id,
                GeneratedAsset.is_active_cover.is_(True),
            )
            .first()
        )
    return {
        "id": line.id,
        "scene_id": line.scene_id,
        "scene_code": scene.code if scene else None,
        "scene_title": scene.title if scene else None,
        "script_id": scene.script_id if scene else None,
        "character_id": line.character_id,
        "character_name": character.name if character else None,
        "version_id": line.version_id,
        "version_no": version.version_no if version else None,
        "content": line.content,
        "approved": line.approved,
        "approved_at": line.approved_at,
        "needs_recheck": line.needs_recheck,
        "recheck_reason": line.recheck_reason,
        "interpretation_snapshot": line.interpretation_snapshot,
        "cover_url": media.image_url(cover.storage_path) if cover else None,
        "created_at": line.created_at,
    }


def script_character_out(db: Session, sc: ScriptCharacter) -> dict:
    character = db.query(Character).get(sc.character_id)
    if sc.pin_mode == "pinned" and sc.pinned_version_id:
        resolved_id = sc.pinned_version_id
    else:
        resolved_id = character.current_version_id if character else None
    resolved_no = None
    if resolved_id:
        v = db.query(CharacterVersion).get(resolved_id)
        resolved_no = v.version_no if v else None
    return {
        "id": sc.id,
        "character_id": sc.character_id,
        "character_name": character.name if character else None,
        "pin_mode": sc.pin_mode,
        "pinned_version_id": sc.pinned_version_id,
        "resolved_version_id": resolved_id,
        "resolved_version_no": resolved_no,
        "floating": sc.pin_mode == "latest",
    }


def script_out(db: Session, script: Script) -> dict:
    return {
        "id": script.id,
        "title": script.title,
        "synopsis": script.synopsis,
        "created_at": script.created_at,
        "scenes": [
            {"id": s.id, "code": s.code, "title": s.title, "sort_order": s.sort_order}
            for s in sorted(script.scenes, key=lambda x: x.sort_order)
        ],
        "characters": [script_character_out(db, sc) for sc in script.characters],
    }


def job_out(db: Session, job: CoverJob) -> dict:
    return {
        "id": job.id,
        "character_id": job.character_id,
        "version_id": job.version_id,
        "source_image_id": job.source_image_id,
        "crop_params": job.crop_params,
        "status": job.status,
        "attempts": job.attempts,
        "error_message": job.error_message,
        "result_asset_id": job.result_asset_id,
        "result_url": media.image_url(job.result_asset.storage_path) if job.result_asset else None,
        "created_at": job.created_at,
        "processed_at": job.processed_at,
    }
