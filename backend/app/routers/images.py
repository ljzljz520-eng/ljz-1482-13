import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.deps import require_admin, require_editor, require_viewer
from app.models import ImageAsset, User
from app.services import images as svc
from app.services.serializers import image_url

router = APIRouter(prefix="/images", tags=["images"])


@router.post("", response_model=schemas.ImageOut, status_code=status.HTTP_201_CREATED)
def upload_image(
    file: UploadFile = File(...),
    license_note: str = Form(default=""),
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    asset = svc.upload_image(db, file, license_note, user)
    return schemas.ImageOut(
        id=asset.id,
        url=image_url(asset),
        original_filename=asset.original_filename,
        width=asset.width,
        height=asset.height,
        license_granted=asset.license_granted,
        license_note=asset.license_note,
        created_at=asset.created_at,
    )


@router.post("/{image_id}/license", response_model=schemas.LicenseImpactOut)
def set_license(
    image_id: uuid.UUID,
    payload: schemas.LicenseIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    asset = db.get(ImageAsset, image_id)
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "图片不存在")
    return svc.revoke_or_grant_license(db, asset, payload, user)


@router.get("/gc-candidates", response_model=list[schemas.GcCandidateOut])
def gc_candidates(db: Session = Depends(get_db), _: User = Depends(require_viewer)):
    return svc.list_gc_candidates(db)


@router.delete("/gc-run")
def run_gc(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    """仅 admin 可执行物理清理；仍被历史导出等引用的图片会被保留。"""
    return svc.delete_unreferenced(db)
