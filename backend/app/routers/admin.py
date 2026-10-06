"""Admin-only maintenance: unreferenced object cleanup."""
from fastapi import APIRouter, Depends

from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import User
from app.schemas import CleanupReport
from app.services.cleanup import cleanup as run_cleanup

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/cleanup", response_model=CleanupReport)
def cleanup(
    dry_run: bool = True,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    """Dry-run by default so UI shows impact before deleting bytes."""
    return run_cleanup(db, dry_run=dry_run)
