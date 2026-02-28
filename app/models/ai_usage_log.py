"""AI feature usage log for rate limiting and analytics."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from app.database import Base


class AiUsageLog(Base):
    __tablename__ = "ai_usage_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    feature = Column(String(32), nullable=False, index=True)  # "analyze" | "chat"
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    # Optional: input_token_count, output_token_count for chat
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    metadata_ = Column("metadata", Text, nullable=True)  # JSON string for extra info
