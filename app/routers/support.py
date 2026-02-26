"""
Support / QRIS: single image + description. Admin uploads & sets description. Public GET.
"""
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.auth import get_current_user_admin
from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.models.support_setting import SupportSetting
from pydantic import BaseModel

router = APIRouter(prefix="/api/support", tags=["support"])

SUPPORT_IMAGE_FILENAME = "qris.png"

# Upload folder path: from env SUPPORT_UPLOAD_DIR (absolute) or relative to backend
def _upload_dir() -> Path:
    settings = get_settings()
    if settings.support_upload_dir:
        return Path(settings.support_upload_dir)
    return Path(__file__).resolve().parent.parent.parent / "uploads" / "support"


def _ensure_upload_dir():
    _upload_dir().mkdir(parents=True, exist_ok=True)


def _get_setting(db: Session) -> SupportSetting | None:
    return db.query(SupportSetting).filter(SupportSetting.id == 1).first()


class SupportResponse(BaseModel):
    description: str | None
    image_url: str | None  # "/api/support/image" if image exists


@router.get("", response_model=SupportResponse)
def get_support(db: Session = Depends(get_db)):
    """Get support/QRIS description and image URL (public)."""
    row = _get_setting(db)
    if not row:
        return SupportResponse(description=None, image_url=None)
    image_url = "/api/support/image" if row.image_path else None
    return SupportResponse(description=row.description, image_url=image_url)


@router.get("/image")
def get_support_image(db: Session = Depends(get_db)):
    """Get QRIS/support image file (public)."""
    row = _get_setting(db)
    if not row or not row.image_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not uploaded yet.")
    upload_dir = _upload_dir()
    path = upload_dir / (row.image_path or SUPPORT_IMAGE_FILENAME)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found at {path!s}.",
        )
    return FileResponse(path, media_type="image/png")


@router.put("")
def admin_update_support(
    description: str | None = Form(None),
    file: UploadFile | None = File(None),
    _admin: User = Depends(get_current_user_admin),
    db: Session = Depends(get_db),
):
    """
    Admin: upload QRIS image and/or set description.
    Form: description (optional), file (optional, image).
    """
    row = _get_setting(db)
    if not row:
        row = SupportSetting(id=1)
        db.add(row)
        db.flush()
    if description is not None:
        row.description = (description.strip() or None) if description else None
    if file and file.filename:
        _ensure_upload_dir()
        path = _upload_dir() / SUPPORT_IMAGE_FILENAME
        with path.open("wb") as f:
            shutil.copyfileobj(file.file, f)
        row.image_path = SUPPORT_IMAGE_FILENAME
    db.commit()
    return {"message": "Support/QRIS updated successfully."}
