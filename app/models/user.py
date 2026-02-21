import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime
from app.database import Base


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    STUDENT = "STUDENT"
    GUEST = "GUEST"


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=True)
    full_name = Column(String(100), nullable=False, default="")
    class_name = Column(String(50), nullable=True, default=None)
    attendance_number = Column(String(5), nullable=True, default=None)
    role = Column(String(20), nullable=False, default=UserRole.GUEST.value)
    is_premium = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
