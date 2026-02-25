from datetime import datetime
from pydantic import BaseModel
from app.models.access_request import AccessRequestStatus


class RequestAccessBody(BaseModel):
    """Body untuk submit request access. User dari JWT. Hanya alasan (optional)."""
    reason: str | None = None
    message: str | None = None  # alias; reason/message disimpan ke kolom message


class AccessRequestResponse(BaseModel):
    """Response untuk satu access request (admin list/detail)."""
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
    """Body untuk admin approve/reject."""
    status: AccessRequestStatus  # APPROVED atau REJECTED
