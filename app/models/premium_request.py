"""Premium request: user uploads transfer proof (screenshot) + message, admin approve → is_premium."""
import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from app.database import Base


class PremiumRequestStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class PremiumRequest(Base):
    __tablename__ = "premium_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    image_path = Column(String(512), nullable=True)
    message = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default=PremiumRequestStatus.PENDING.value)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
