"""Uploaded video file for streaming. URL is generated; only premium users can access."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime
from app.database import Base


class Video(Base):
    __tablename__ = "videos"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    path = Column(String(512), nullable=False)  # relative path under upload dir
    original_filename = Column(String(255), nullable=True)
    content_type = Column(String(100), nullable=True)  # video/mp4 etc
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
