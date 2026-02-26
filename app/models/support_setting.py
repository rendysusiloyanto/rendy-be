"""Single row for support/QRIS settings: image + description."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database import Base


class SupportSetting(Base):
    __tablename__ = "support_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    image_path = Column(String(512), nullable=True)  # path relative to uploads/support/
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
