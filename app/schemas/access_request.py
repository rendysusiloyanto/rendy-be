from datetime import datetime
from pydantic import BaseModel
from app.models.access_request import AccessRequestStatus


class RequestAccessBody(BaseModel):
    """Body for submitting access request. User from JWT. Reason only (optional)."""
    reason: str | None = None
    message: str | None = None  # alias; reason/message stored in message column


class AccessRequestResponse(BaseModel):
    """Response for a single access request (admin list/detail)."""
    id: str
    user_id: str
    user_email: str
    user_full_name: str
    message: str | None
    status: str
    requested_at: datetime
    reviewed_at: datetime | None

    class Config:
        from_attributes = True


class AccessRequestReview(BaseModel):
    """Body for admin approve/reject."""
    status: AccessRequestStatus  # APPROVED or REJECTED
