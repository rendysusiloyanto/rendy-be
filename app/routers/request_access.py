"""
Submit access request: user must be logged in (Bearer token). Email is taken from JWT.
Body: { "reason": "optional" } or { "message": "optional" }.
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
    Submit access request (user from JWT). Only currently blocked users may submit.
    Body: { "reason": "..." } or { "message": "..." } optional.
    """
    if not user.is_blacklisted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your account is not blocked. Please log in as usual.",
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
            "message": "Your access request has been sent. Awaiting admin review.",
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
        "message": "Access request has been submitted. Admin will review and contact you.",
    }
