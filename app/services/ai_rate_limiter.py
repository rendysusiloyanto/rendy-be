"""
Daily rate limits for AI features.
- Analyze: non-premium 3/day, premium 20/day
- Chat: premium only, 50 messages/day
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.ai_usage_log import AiUsageLog

# Limits per user per calendar day (UTC)
ANALYZE_LIMIT_NON_PREMIUM = 3
ANALYZE_LIMIT_PREMIUM = 20
CHAT_LIMIT_PREMIUM = 50

# Conversation history length for assistant
CHAT_HISTORY_MAX_MESSAGES = 10


def _start_of_today_utc() -> datetime:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def count_analyze_today(db: Session, user_id: str) -> int:
    today = _start_of_today_utc()
    return db.query(func.count(AiUsageLog.id)).filter(
        AiUsageLog.user_id == user_id,
        AiUsageLog.feature == "analyze",
        AiUsageLog.created_at >= today,
    ).scalar() or 0


def count_chat_today(db: Session, user_id: str) -> int:
    today = _start_of_today_utc()
    return db.query(func.count(AiUsageLog.id)).filter(
        AiUsageLog.user_id == user_id,
        AiUsageLog.feature == "chat",
        AiUsageLog.created_at >= today,
    ).scalar() or 0


def check_analyze_limit(db: Session, user_id: str, is_premium: bool) -> tuple[bool, str]:
    """
    Returns (allowed, error_message).
    If allowed, error_message is empty.
    """
    limit = ANALYZE_LIMIT_PREMIUM if is_premium else ANALYZE_LIMIT_NON_PREMIUM
    count = count_analyze_today(db, user_id)
    if count >= limit:
        return False, f"Daily limit reached ({limit} analyze requests per day). Try again tomorrow."
    return True, ""


def check_chat_limit(db: Session, user_id: str) -> tuple[bool, str]:
    """Premium-only is enforced in router. Here we only check daily count."""
    count = count_chat_today(db, user_id)
    if count >= CHAT_LIMIT_PREMIUM:
        return False, f"Daily limit reached ({CHAT_LIMIT_PREMIUM} chat messages per day). Try again tomorrow."
    return True, ""


def log_usage(
    db: Session,
    user_id: str,
    feature: str,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    metadata_: str | None = None,
) -> None:
    entry = AiUsageLog(
        user_id=user_id,
        feature=feature,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        metadata_=metadata_,
    )
    db.add(entry)
    db.commit()
