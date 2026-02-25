"""
Support / QRIS: satu gambar + deskripsi. Admin upload & set description. Public GET.
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

# Path folder upload: dari env SUPPORT_UPLOAD_DIR (absolut) atau relative ke backend
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
    image_url: str | None  # "/api/support/image" jika ada gambar


@router.get("", response_model=SupportResponse)
def get_support(db: Session = Depends(get_db)):
    """Get deskripsi dan URL gambar support/QRIS (public)."""
    row = _get_setting(db)
    if not row:
        return SupportResponse(description=None, image_url=None)
    image_url = "/api/support/image" if row.image_path else None
    return SupportResponse(description=row.description, image_url=image_url)


@router.get("/image")
def get_support_image(db: Session = Depends(get_db)):
    """Get file gambar QRIS/support (public)."""
    row = _get_setting(db)
    if not row or not row.image_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gambar belum diunggah.")
    upload_dir = _upload_dir()
    path = upload_dir / (row.image_path or SUPPORT_IMAGE_FILENAME)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File tidak ditemukan di {path!s}.",
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
    Admin: upload gambar QRIS dan/atau set description.
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
    return {"message": "Support/QRIS berhasil diperbarui."}
