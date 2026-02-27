from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.access_request import AccessRequest, AccessRequestStatus
from app.auth import get_current_user_admin
from app.schemas.user import UserResponse, UserUpdate
from app.schemas.access_request import AccessRequestResponse, AccessRequestReview

router = APIRouter(prefix="/api/users", tags=["users"])


# ---------- Request Access (admin) ----------


@router.get("/request-access", response_model=list[AccessRequestResponse])
def list_request_access(
    status_filter: str | None = None,
    _admin: User = Depends(get_current_user_admin),
    db: Session = Depends(get_db),
):
    """List all access requests (admin only). Optional ?status_filter=PENDING."""
    q = (
        db.query(AccessRequest, User)
        .join(User, AccessRequest.user_id == User.id)
        .order_by(AccessRequest.requested_at.desc())
    )
    if status_filter and status_filter.upper() in ("PENDING", "APPROVED", "REJECTED"):
        q = q.filter(AccessRequest.status == status_filter.upper())
    rows = q.all()
    return [
        AccessRequestResponse(
            id=req.id,
            user_id=req.user_id,
            user_email=u.email,
            user_full_name=u.full_name or u.email,
            message=req.message,
            status=req.status,
            requested_at=req.requested_at,
            reviewed_at=req.reviewed_at,
        )
        for req, u in rows
    ]


@router.patch("/request-access/{request_id}", response_model=AccessRequestResponse)
def review_request_access(
    request_id: str,
    body: AccessRequestReview,
    admin: User = Depends(get_current_user_admin),
    db: Session = Depends(get_db),
):
    """Approve or reject access request (admin only). Approve sets user is_blacklisted to false."""
    if body.status not in (AccessRequestStatus.APPROVED, AccessRequestStatus.REJECTED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="status must be APPROVED or REJECTED",
        )
    req = db.query(AccessRequest).filter(AccessRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if req.status != AccessRequestStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This request has already been reviewed.",
        )
    req.status = body.status.value
    req.reviewed_at = datetime.utcnow()
    req.reviewed_by_id = admin.id
    if body.status == AccessRequestStatus.APPROVED:
        user = db.query(User).filter(User.id == req.user_id).first()
        if user:
            user.is_blacklisted = False
    db.commit()
    db.refresh(req)
    u = db.query(User).filter(User.id == req.user_id).first()
    return AccessRequestResponse(
        id=req.id,
        user_id=req.user_id,
        user_email=u.email if u else "",
        user_full_name=(u.full_name or u.email) if u else "",
        message=req.message,
        status=req.status,
        requested_at=req.requested_at,
        reviewed_at=req.reviewed_at,
    )


# ---------- Users CRUD ----------


@router.get("", response_model=list[UserResponse])
def get_all_users(
    _admin: User = Depends(get_current_user_admin),
    db: Session = Depends(get_db),
):
    """List all users (admin only)."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [
        UserResponse(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            class_name=u.class_name,
            attendance_number=u.attendance_number,
            role=u.role,
            is_premium=u.is_premium,
            is_blacklisted=u.is_blacklisted,
            created_at=u.created_at,
            updated_at=u.updated_at,
        )
        for u in users
    ]


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: str,
    _admin: User = Depends(get_current_user_admin),
    db: Session = Depends(get_db),
):
    """Get one user by id (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        class_name=user.class_name,
        attendance_number=user.attendance_number,
        role=user.role,
        is_premium=user.is_premium,
        is_blacklisted=user.is_blacklisted,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    body: UserUpdate,
    _admin: User = Depends(get_current_user_admin),
    db: Session = Depends(get_db),
):
    """Update user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.class_name is not None:
        user.class_name = body.class_name
    if body.attendance_number is not None:
        user.attendance_number = body.attendance_number
    if body.role is not None:
        user.role = body.role.value
    if body.is_premium is not None:
        user.is_premium = body.is_premium
    if body.is_blacklisted is not None:
        user.is_blacklisted = body.is_blacklisted
    db.commit()
    db.refresh(user)
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        class_name=user.class_name,
        attendance_number=user.attendance_number,
        role=user.role,
        is_premium=user.is_premium,
        is_blacklisted=user.is_blacklisted,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )
