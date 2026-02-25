"""
Premium request: user upload bukti transfer (screenshot) + message.
User bisa re-upload (edit) dan ubah message. Admin lihat semua, approve → user is_premium.
"""
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from app.auth import get_current_user, get_current_user_admin
from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.models.premium_request import PremiumRequest, PremiumRequestStatus
from pydantic import BaseModel

router = APIRouter(prefix="/api/premium", tags=["premium"])


def _upload_dir() -> Path:
    settings = get_settings()
    if settings.premium_upload_dir:
        return Path(settings.premium_upload_dir)
    return Path(__file__).resolve().parent.parent.parent / "uploads" / "premium"


def _ensure_upload_dir():
    _upload_dir().mkdir(parents=True, exist_ok=True)


# ---------- User: submit / get my request ----------


@router.post("/request")
def submit_premium_request(
    file: UploadFile = File(...),
    message: str | None = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    User: upload screenshot bukti transfer + optional message.
    Jika sudah ada request PENDING, akan di-update (ganti gambar + message).
    """
    if not file.filename or not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File harus gambar (image).")
    existing = (
        db.query(PremiumRequest)
        .filter(PremiumRequest.user_id == user.id, PremiumRequest.status == PremiumRequestStatus.PENDING.value)
        .first()
    )
    _ensure_upload_dir()
    if existing:
        req = existing
        path = _upload_dir() / f"{req.id}.png"
        with path.open("wb") as f:
            shutil.copyfileobj(file.file, f)
        req.image_path = path.name
        req.message = (message or "").strip() or None
    else:
        req = PremiumRequest(user_id=user.id, message=(message or "").strip() or None)
        db.add(req)
        db.flush()
        path = _upload_dir() / f"{req.id}.png"
        with path.open("wb") as f:
            shutil.copyfileobj(file.file, f)
        req.image_path = path.name
    db.commit()
    db.refresh(req)
    return {
        "message": "Bukti transfer berhasil dikirim. Admin akan meninjau.",
        "id": req.id,
        "status": req.status,
    }


@router.get("/request")
def get_my_premium_request(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """User: lihat request premium saya (jika ada). Jika PENDING, tampilkan image_url dan message; bisa di-update lewat PATCH."""
    req = (
        db.query(PremiumRequest)
        .filter(PremiumRequest.user_id == user.id)
        .order_by(PremiumRequest.created_at.desc())
        .first()
    )
    if not req:
        return JSONResponse(content={"request": None})
    return JSONResponse(
        content={
            "request": {
                "id": req.id,
                "status": req.status,
                "message": req.message,
                "image_url": f"/api/premium/requests/{req.id}/image" if req.image_path else None,
                "created_at": req.created_at.isoformat(),
                "updated_at": req.updated_at.isoformat(),
                "can_edit": req.status == PremiumRequestStatus.PENDING.value,
            }
        }
    )


@router.patch("/request")
def update_my_premium_request(
    message: str | None = Form(None),
    file: UploadFile | None = File(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    User: update message dan/atau image untuk request PENDING saya.
    Hanya request dengan status PENDING yang bisa di-edit. Kirim message dan/atau file (gambar).
    """
    req = (
        db.query(PremiumRequest)
        .filter(PremiumRequest.user_id == user.id, PremiumRequest.status == PremiumRequestStatus.PENDING.value)
        .first()
    )
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tidak ada request premium PENDING. Buat dulu lewat POST /api/premium/request.",
        )
    if message is not None:
        req.message = (message.strip() or None) if message else None
    if file and file.filename and file.content_type and file.content_type.startswith("image/"):
        _ensure_upload_dir()
        path = _upload_dir() / f"{req.id}.png"
        with path.open("wb") as f:
            shutil.copyfileobj(file.file, f)
        req.image_path = path.name
    db.commit()
    db.refresh(req)
    return {
        "message": "Request premium berhasil di-update.",
        "request": {
            "id": req.id,
            "status": req.status,
            "message": req.message,
            "image_url": f"/api/premium/requests/{req.id}/image" if req.image_path else None,
            "created_at": req.created_at.isoformat(),
            "updated_at": req.updated_at.isoformat(),
        },
    }


# ---------- Admin: list, view image, approve ----------


class PremiumRequestListItem(BaseModel):
    id: str
    user_id: str
    user_email: str
    user_full_name: str
    message: str | None
    status: str
    image_url: str | None
    created_at: str
    updated_at: str


@router.get("/requests", response_model=list[PremiumRequestListItem])
def admin_list_premium_requests(
    status_filter: str | None = None,
    _admin: User = Depends(get_current_user_admin),
    db: Session = Depends(get_db),
):
    """Admin: daftar semua premium request dengan user info."""
    q = (
        db.query(PremiumRequest, User)
        .join(User, PremiumRequest.user_id == User.id)
        .order_by(PremiumRequest.created_at.desc())
    )
    if status_filter and status_filter.upper() in ("PENDING", "APPROVED", "REJECTED"):
        q = q.filter(PremiumRequest.status == status_filter.upper())
    rows = q.all()
    return [
        PremiumRequestListItem(
            id=req.id,
            user_id=req.user_id,
            user_email=u.email,
            user_full_name=u.full_name or u.email,
            message=req.message,
            status=req.status,
            image_url=f"/api/premium/requests/{req.id}/image" if req.image_path else None,
            created_at=req.created_at.isoformat(),
            updated_at=req.updated_at.isoformat(),
        )
        for req, u in rows
    ]


@router.get("/requests/{request_id}/image")
def get_premium_request_image(
    request_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get image bukti transfer. User hanya bisa akses request sendiri; admin bisa akses semua.
    """
    req = db.query(PremiumRequest).filter(PremiumRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request tidak ditemukan")
    if user.role != "ADMIN" and req.user_id != user.id:
        raise HTTPException(status_code=403, detail="Tidak boleh akses request orang lain")
    if not req.image_path:
        raise HTTPException(status_code=404, detail="Gambar belum diunggah")
    path = _upload_dir() / req.image_path
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    return FileResponse(path, media_type="image/png")


class PremiumRequestReview(BaseModel):
    status: str  # APPROVED | REJECTED


@router.patch("/requests/{request_id}")
def admin_review_premium_request(
    request_id: str,
    body: PremiumRequestReview,
    _admin: User = Depends(get_current_user_admin),
    db: Session = Depends(get_db),
):
    """
    Admin: set status APPROVED atau REJECTED.
    Jika APPROVED, user.is_premium di-set True.
    """
    if body.status.upper() not in ("APPROVED", "REJECTED"):
        raise HTTPException(status_code=400, detail="status harus APPROVED atau REJECTED")
    req = db.query(PremiumRequest).filter(PremiumRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request tidak ditemukan")
    req.status = body.status.upper()
    if body.status.upper() == "APPROVED":
        u = db.query(User).filter(User.id == req.user_id).first()
        if u:
            u.is_premium = True
    db.commit()
    return {"message": "Request berhasil ditinjau.", "status": req.status}
