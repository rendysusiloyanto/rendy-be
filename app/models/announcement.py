import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text
from app.database import Base


class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=True)
    attachment_filename = Column(String(255), nullable=True)  # original filename for display
    attachment_path = Column(String(512), nullable=True)      # path stored on server
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
