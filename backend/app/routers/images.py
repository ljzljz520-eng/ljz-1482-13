"""Source reference image upload and authorization lifecycle."""
import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from PIL import Image
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import current_user, require_roles
from app.models import ReferenceImage, User
from app.schemas import ImageOut, LicenseRevokeResponse
from app.serializers import image_out
from app.services import media
from app.services.licenses import revoke as revoke_license

router = APIRouter(prefix="/images", tags=["images"])

ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp"}


@router.get("", response_model=list[ImageOut])
def list_images(db: Session = Depends(get_db), _: User = Depends(current_user)):
    rows = db.query(ReferenceImage).order_by(ReferenceImage.created_at.desc()).all()
    return [image_out(img) for img in rows]


@router.post("", response_model=ImageOut, status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "editor")),
):
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "仅支持 PNG / JPEG / WebP 图片")
    data = await file.read()
    if not data or len(data) > 12 * 1024 * 1024:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "图片为空或超过 12MB")
    try:
        probe = Image.open(io.BytesIO(data))
        width, height = probe.size
        probe.verify()
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "图片文件损坏或格式不受支持")
    path, _name = media.save_source_image(data, file.filename or "upload.png", file.content_type)
    image = ReferenceImage(
        filename=file.filename or "upload.png",
        storage_path=path,
        mime_type=file.content_type,
        width=width,
        height=height,
        uploaded_by=user.id,
    )
    db.add(image)
    db.commit()
    db.refresh(image)
    return image_out(image)


@router.get("/{image_id}", response_model=ImageOut)
def get_image(image_id: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    img = db.query(ReferenceImage).get(image_id)
    if img is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "图片不存在")
    return image_out(img)


@router.post("/{image_id}/revoke", response_model=LicenseRevokeResponse)
def revoke_image(
    image_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    img = db.query(ReferenceImage).get(image_id)
    if img is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "图片不存在")
    if img.license_status == "revoked":
        raise HTTPException(status.HTTP_409_CONFLICT, "授权已处于撤销状态")
    result = revoke_license(db, img)
    db.refresh(img)
    return LicenseRevokeResponse(image=image_out(img), **result)
