"""
Submit request akses: user harus login (Bearer token). Email diambil dari JWT.
Body: { "reason": "optional" } atau { "message": "optional" }.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.access_request import AccessRequest, AccessRequestStatus
from app.schemas.access_request import RequestAccessBody

router = APIRouter(prefix="/api", tags=["request-access"])


@router.post("/request-access")
def submit_request_access(
    body: RequestAccessBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit request akses (user dari JWT). Hanya user yang sedang diblokir yang boleh submit.
    Body: { "reason": "..." } atau { "message": "..." } optional.
    """
    if not user.is_blacklisted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Akun Anda tidak diblokir. Silakan login seperti biasa.",
        )
    existing = (
        db.query(AccessRequest)
        .filter(
            AccessRequest.user_id == user.id,
            AccessRequest.status == AccessRequestStatus.PENDING.value,
        )
        .first()
    )
    if existing:
        return {
            "message": "Request akses Anda sudah terkirim. Menunggu peninjauan admin.",
        }
    message_val = (body.reason or body.message or "").strip() or None
    req = AccessRequest(
        user_id=user.id,
        message=message_val,
        status=AccessRequestStatus.PENDING.value,
    )
    db.add(req)
    db.commit()
    return {
        "message": "Request akses telah dikirim. Admin akan meninjau dan menghubungi Anda.",
    }
