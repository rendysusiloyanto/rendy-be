import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey
from app.database import Base


class Learning(Base):
    __tablename__ = "learnings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    thumbnail = Column(String(512), nullable=True)  # external URL or null if thumbnail_path set
    thumbnail_path = Column(String(512), nullable=True)  # uploaded image filename under learning_thumbnails/
    content = Column(Text, nullable=True)
    video_url = Column(String(512), nullable=True)  # external URL (e.g. YouTube) when video_id is null
    video_id = Column(String(36), ForeignKey("videos.id"), nullable=True)  # our uploaded video for streaming
    is_published = Column(Boolean, nullable=False, default=False)
    is_premium = Column(Boolean, nullable=False, default=False)
    # variant: "introduction" = simple/nginx static; "full" = stream (FFmpeg HLS)
    variant = Column(String(32), nullable=False, default="introduction")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
