"""Message in an AI Assistant conversation. Belongs to one Conversation (one thread per user)."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class AiChatMessage(Base):
    __tablename__ = "ai_chat_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    conversation_id = Column(
        String(36),
        ForeignKey("ai_conversations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    role = Column(String(16), nullable=False)  # "user" | "assistant"
    content = Column(Text, nullable=False)
    input_tokens = Column(String(20), nullable=True)
    output_tokens = Column(String(20), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    conversation = relationship("AiConversation", back_populates="messages")
