"""One conversation (thread) per user for AI Assistant chat. Messages belong to a conversation."""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class AiConversation(Base):
    __tablename__ = "ai_conversations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Messages ordered by created_at for correct ordering
    messages = relationship(
        "AiChatMessage",
        back_populates="conversation",
        order_by="AiChatMessage.created_at",
        lazy="select",
    )
