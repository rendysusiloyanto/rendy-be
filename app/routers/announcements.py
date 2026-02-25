import os
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.auth import get_current_user, get_current_user_admin
from app.database import get_db
from app.models.announcement import Announcement
from app.schemas.announcement import AnnouncementResponse

router = APIRouter(prefix="/api/announcements", tags=["announcements"])

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "announcements"
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _ensure_upload_dir():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _safe_filename(original: str) -> str:
    ext = Path(original).suffix.lower() if original else ".bin"
    if ext not in ALLOWED_EXTENSIONS:
        ext = ".bin"
    return f"{uuid.uuid4().hex}{ext}"


@router.get("", response_model=list[AnnouncementResponse])
def list_announcements(db: Session = Depends(get_db)):
    items = db.query(Announcement).order_by(Announcement.created_at.desc()).all()
    return [
        AnnouncementResponse(
            id=x.id,
            title=x.title,
            content=x.content,
            attachment_filename=x.attachment_filename,
            has_attachment=bool(x.attachment_path),
            created_at=x.created_at.isoformat(),
            updated_at=x.updated_at.isoformat(),
        )
        for x in items
    ]


@router.get("/admin", response_model=list[AnnouncementResponse])
def admin_list_announcements(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user_admin),
):
    items = db.query(Announcement).order_by(Announcement.created_at.desc()).all()
    return [
        AnnouncementResponse(
            id=x.id,
            title=x.title,
            content=x.content,
            attachment_filename=x.attachment_filename,
            has_attachment=bool(x.attachment_path),
            created_at=x.created_at.isoformat(),
            updated_at=x.updated_at.isoformat(),
        )
        for x in items
    ]


@router.get("/{announcement_id}", response_model=AnnouncementResponse)
def get_announcement(announcement_id: str, db: Session = Depends(get_db)):
    item = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Announcement tidak ditemukan")
    return AnnouncementResponse(
        id=item.id,
        title=item.title,
        content=item.content,
        attachment_filename=item.attachment_filename,
        has_attachment=bool(item.attachment_path),
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


@router.get("/{announcement_id}/attachment")
def get_announcement_attachment(
    announcement_id: str,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Unduh atau tampilkan file attachment (e.g. PDF bisa dibuka di browser). Perlu login."""
    item = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not item or not item.attachment_path:
        raise HTTPException(status_code=404, detail="Attachment tidak ditemukan")
    path = UPLOAD_DIR / item.attachment_path
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    filename = item.attachment_filename or item.attachment_path
    return FileResponse(
        path,
        filename=filename,
        media_type="application/octet-stream",
    )


@router.post("", response_model=AnnouncementResponse)
async def create_announcement(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user_admin),
    title: str = Form(...),
    content: str = Form(""),
    file: UploadFile | None = File(None),
):
    _ensure_upload_dir()
    item = Announcement(title=title, content=content or None)
    if file and file.filename:
        fn = _safe_filename(file.filename)
        path = UPLOAD_DIR / fn
        content_bytes = await file.read()
        path.write_bytes(content_bytes)
        item.attachment_filename = file.filename
        item.attachment_path = fn
    db.add(item)
    db.commit()
    db.refresh(item)
    return AnnouncementResponse(
        id=item.id,
        title=item.title,
        content=item.content,
        attachment_filename=item.attachment_filename,
        has_attachment=bool(item.attachment_path),
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


@router.put("/{announcement_id}", response_model=AnnouncementResponse)
async def update_announcement(
    announcement_id: str,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user_admin),
    title: str | None = Form(None),
    content: str | None = Form(None),
    file: UploadFile | None = File(None),
):
    item = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Announcement tidak ditemukan")
    if title is not None:
        item.title = title
    if content is not None:
        item.content = content
    if file and file.filename:
        _ensure_upload_dir()
        if item.attachment_path:
            old_path = UPLOAD_DIR / item.attachment_path
            if old_path.is_file():
                old_path.unlink()
        fn = _safe_filename(file.filename)
        path = UPLOAD_DIR / fn
        content_bytes = await file.read()
        path.write_bytes(content_bytes)
        item.attachment_filename = file.filename
        item.attachment_path = fn
    db.commit()
    db.refresh(item)
    return AnnouncementResponse(
        id=item.id,
        title=item.title,
        content=item.content,
        attachment_filename=item.attachment_filename,
        has_attachment=bool(item.attachment_path),
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


@router.delete("/{announcement_id}")
def delete_announcement(
    announcement_id: str,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user_admin),
):
    item = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Announcement tidak ditemukan")
    if item.attachment_path:
        path = UPLOAD_DIR / item.attachment_path
        if path.is_file():
            path.unlink()
    db.delete(item)
    db.commit()
    return {"message": "Announcement dihapus"}
