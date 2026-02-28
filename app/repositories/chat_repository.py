"""
Chat persistence: Conversation (one per user) + Message. DB as source of truth.
All operations are sync (used from sync endpoints or run_in_executor from async).
Ownership: conversation.user_id == current user; all history APIs validate this.
"""
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.ai_chat_message import AiChatMessage
from app.models.ai_conversation import AiConversation


def get_or_create_conversation(db: Session, user_id: str) -> AiConversation:
    """Get the user's conversation (single thread per user); create if missing."""
    conv = db.query(AiConversation).filter(AiConversation.user_id == user_id).first()
    if conv is not None:
        return conv
    conv = AiConversation(user_id=user_id)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def save_message(
    db: Session,
    user_id: str,
    role: str,
    content: str,
    *,
    conversation_id: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
) -> AiChatMessage:
    """Persist one message. Optionally attach to conversation. Caller commits via this function."""
    msg = AiChatMessage(
        user_id=user_id,
        conversation_id=conversation_id,
        role=role,
        content=content,
        input_tokens=str(input_tokens) if input_tokens is not None else None,
        output_tokens=str(output_tokens) if output_tokens is not None else None,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def get_last_messages(
    db: Session,
    user_id: str,
    limit: int = 10,
) -> list[dict]:
    """
    Load last `limit` messages for user, ordered oldest-first (for Gemini context).
    Uses user's conversation when present; falls back to user_id for legacy rows.
    Returns list of {"role": "user"|"assistant", "content": "..."}.
    """
    conv = db.query(AiConversation).filter(AiConversation.user_id == user_id).first()
    if conv:
        rows = (
            db.query(AiChatMessage)
            .filter(AiChatMessage.conversation_id == conv.id)
            .order_by(desc(AiChatMessage.created_at))
            .limit(limit)
            .all()
        )
    else:
        rows = (
            db.query(AiChatMessage)
            .filter(AiChatMessage.user_id == user_id)
            .order_by(desc(AiChatMessage.created_at))
            .limit(limit)
            .all()
        )
    rows = list(reversed(rows))  # oldest-first for Gemini context
    return [{"role": r.role, "content": r.content} for r in rows]


def get_messages_ordered_for_user(
    db: Session,
    user_id: str,
    limit: int = 100,
) -> list[dict]:
    """
    Get history for GET endpoint: messages in user's conversation, ordered by created_at asc.
    Ownership: only the conversation owned by user_id is read. Returns list of
    {"id", "role", "content", "created_at"}.
    """
    conv = db.query(AiConversation).filter(AiConversation.user_id == user_id).first()
    if not conv:
        return []
    rows = (
        db.query(AiChatMessage)
        .filter(AiChatMessage.conversation_id == conv.id)
        .order_by(AiChatMessage.created_at)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "role": r.role,
            "content": r.content,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def trim_to_last_n(db: Session, user_id: str, limit: int = 10) -> None:
    """Keep only the last `limit` messages per user (in their conversation); delete older."""
    conv = db.query(AiConversation).filter(AiConversation.user_id == user_id).first()
    if conv:
        subq = (
            db.query(AiChatMessage.id)
            .filter(AiChatMessage.conversation_id == conv.id)
            .order_by(desc(AiChatMessage.created_at))
            .limit(limit)
        )
        ids_to_keep = [r[0] for r in subq.all()]
        if ids_to_keep:
            db.query(AiChatMessage).filter(
                AiChatMessage.conversation_id == conv.id,
                AiChatMessage.id.notin_(ids_to_keep),
            ).delete(synchronize_session=False)
    else:
        subq = (
            db.query(AiChatMessage.id)
            .filter(AiChatMessage.user_id == user_id)
            .order_by(desc(AiChatMessage.created_at))
            .limit(limit)
        )
        ids_to_keep = [r[0] for r in subq.all()]
        if ids_to_keep:
            db.query(AiChatMessage).filter(
                AiChatMessage.user_id == user_id,
                AiChatMessage.id.notin_(ids_to_keep),
            ).delete(synchronize_session=False)
    db.commit()


class ChatRepository:
    """Thin wrapper for dependency injection; delegates to module functions."""

    @staticmethod
    def get_or_create_conversation(db: Session, user_id: str) -> AiConversation:
        return get_or_create_conversation(db, user_id)

    @staticmethod
    def save_message(
        db: Session,
        user_id: str,
        role: str,
        content: str,
        *,
        conversation_id: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> AiChatMessage:
        return save_message(
            db, user_id, role, content,
            conversation_id=conversation_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    @staticmethod
    def get_last_messages(db: Session, user_id: str, limit: int = 10) -> list[dict]:
        return get_last_messages(db, user_id, limit)

    @staticmethod
    def get_messages_ordered_for_user(db: Session, user_id: str, limit: int = 100) -> list[dict]:
        return get_messages_ordered_for_user(db, user_id, limit)

    @staticmethod
    def trim_to_last_n(db: Session, user_id: str, limit: int = 10) -> None:
        return trim_to_last_n(db, user_id, limit)
