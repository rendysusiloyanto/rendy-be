"""
Chat persistence: database as source of truth.
All operations are sync (used from sync endpoints or run_in_executor from async).
"""
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.ai_chat_message import AiChatMessage


def save_message(
    db: Session,
    user_id: str,
    role: str,
    content: str,
    *,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
) -> AiChatMessage:
    """Persist one message to DB. Caller must commit if needed (we commit here for clarity)."""
    msg = AiChatMessage(
        user_id=user_id,
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
    Load last `limit` messages for user, ordered oldest-first (for API/context).
    Returns list of {"role": "user"|"assistant", "content": "..."}.
    """
    rows = (
        db.query(AiChatMessage)
        .filter(AiChatMessage.user_id == user_id)
        .order_by(desc(AiChatMessage.created_at))
        .limit(limit)
        .all()
    )
    # Oldest first for Gemini context
    rows = list(reversed(rows))
    return [{"role": r.role, "content": r.content} for r in rows]


def trim_to_last_n(db: Session, user_id: str, limit: int = 10) -> None:
    """Keep only the last `limit` messages per user; delete older. Call after save if desired."""
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
    def save_message(
        db: Session,
        user_id: str,
        role: str,
        content: str,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> AiChatMessage:
        return save_message(db, user_id, role, content, input_tokens=input_tokens, output_tokens=output_tokens)

    @staticmethod
    def get_last_messages(db: Session, user_id: str, limit: int = 10) -> list[dict]:
        return get_last_messages(db, user_id, limit)

    @staticmethod
    def trim_to_last_n(db: Session, user_id: str, limit: int = 10) -> None:
        return trim_to_last_n(db, user_id, limit)
