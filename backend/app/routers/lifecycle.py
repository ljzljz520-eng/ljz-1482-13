"""Character reverse-references and retirement workflow."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import current_user, require_roles
from app.models import User
from app.schemas import ReferencesOut, RetireRequest, RetireResponse
from app.services.characters import get_active_character
from app.services.references import collect_references, total_reference_count
from app.services.retire import retire as run_retire

router = APIRouter(prefix="/characters", tags=["lifecycle"])


@router.get("/{character_id}/references", response_model=ReferencesOut)
def references(
    character_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    character = get_active_character(db, character_id)
    refs = collect_references(db, character)
    total = (
        refs["pinned_script_refs"]["count"]
        + refs["floating_script_refs"]
        + refs["approved_lines"]["count"]
        + refs["pending_lines"]["count"]
        + refs["cover_jobs"]["count"]
        + refs["generated_assets"]["count"]
        + refs["export_snapshots"]["count"]
    )
    return {
        "character_id": character_id,
        "character_status": character.status,
        "total": total,
        **refs,
    }


@router.post("/{character_id}/retire", response_model=RetireResponse)
def retire(
    character_id: str,
    payload: RetireRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    return run_retire(
        db,
        character_id,
        strategy=payload.strategy,
        expected_ref_count=payload.expected_ref_count,
        replacement_character_id=payload.replacement_character_id,
    )
