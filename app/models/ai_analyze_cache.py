"""Cache for AI Analyze results so repeated same request does not call Gemini again."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index
from app.database import Base


class AiAnalyzeCache(Base):
    __tablename__ = "ai_analyze_cache"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    cache_key = Column(String(64), nullable=False, index=True)  # hash of normalized input
    response_text = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (Index("ix_ai_analyze_cache_user_key", "user_id", "cache_key", unique=True),)
