"""
AI endpoints for jns23lab:
- POST /ai/analyze — failure analysis (all users, rate limited; cached)
- POST /ai/chat — assistant chat (premium only; 50/day)
- POST /ai/chat/stream — assistant chat streaming (SSE)
- POST /ai/chat-with-image — chat with image (premium only; counts toward 50/day)
"""
import hashlib
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.auth import get_current_user, get_current_user_premium, require_not_blacklisted
from app.database import get_db
from app.models.user import User
from app.models.ai_usage_log import AiUsageLog
from app.models.ai_analyze_cache import AiAnalyzeCache
from app.models.ai_chat_message import AiChatMessage
from app.schemas.ai import AiAnalyzeRequest, AiAnalyzeResponse, AiChatRequest, AiChatResponse
from app.services.ai_service import generate_analyze, generate_chat, generate_chat_stream, generate_chat_with_image
from app.services.ai_rate_limiter import (
    check_analyze_limit,
    check_chat_limit,
    log_usage,
    CHAT_LIMIT_PREMIUM,
    CHAT_HISTORY_MAX_MESSAGES,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _analyze_cache_key(user_id: str, payload: dict) -> str:
    """Stable hash for caching analyze result."""
    normalized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(f"{user_id}:{normalized}".encode()).hexdigest()[:64]


def _get_chat_history(db: Session, user_id: str, max_messages: int = CHAT_HISTORY_MAX_MESSAGES) -> list[dict]:
    rows = (
        db.query(AiChatMessage)
        .filter(AiChatMessage.user_id == user_id)
        .order_by(desc(AiChatMessage.created_at))
        .limit(max_messages)
        .all()
    )
    # Oldest first for API
    rows = list(reversed(rows))
    return [{"role": r.role, "content": r.content} for r in rows]


def _save_chat_turn(db: Session, user_id: str, user_content: str, assistant_content: str, input_tokens: int, output_tokens: int) -> None:
    """Append user and assistant messages; trim to last N."""
    for role, content in [("user", user_content), ("assistant", assistant_content)]:
        msg = AiChatMessage(
            user_id=user_id,
            role=role,
            content=content,
            input_tokens=str(input_tokens) if role == "user" else None,
            output_tokens=str(output_tokens) if role == "assistant" else None,
        )
        db.add(msg)
    db.commit()
    # Keep only last CHAT_HISTORY_MAX_MESSAGES per user (delete older)
    ids_to_keep = (
        db.query(AiChatMessage.id)
        .filter(AiChatMessage.user_id == user_id)
        .order_by(desc(AiChatMessage.created_at))
        .limit(CHAT_HISTORY_MAX_MESSAGES)
        .all()
    )
    keep_ids = [r[0] for r in ids_to_keep]
    if keep_ids:
        db.query(AiChatMessage).filter(
            AiChatMessage.user_id == user_id,
            AiChatMessage.id.notin_(keep_ids),
        ).delete(synchronize_session=False)
        db.commit()


# ---------- Analyze ----------


@router.post("/analyze", response_model=AiAnalyzeResponse)
def ai_analyze(
    body: AiAnalyzeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_not_blacklisted),
):
    """
    Analyze exam failure: explain why it failed and suggest a fix.
    All authenticated users; non-premium 3/day, premium 20/day.
    Result is cached so repeated same request does not call Gemini again.
    """
    allowed, err = check_analyze_limit(db, user.id, user.is_premium)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=err)

    payload = {"exam_result_details": body.exam_result_details, "config_snippets": body.config_snippets or {}}
    cache_key = _analyze_cache_key(user.id, payload)

    cached = db.query(AiAnalyzeCache).filter(
        AiAnalyzeCache.user_id == user.id,
        AiAnalyzeCache.cache_key == cache_key,
    ).first()
    if cached:
        return AiAnalyzeResponse(explanation=cached.response_text, from_cache=True)

    try:
        explanation = generate_analyze(body.exam_result_details, body.config_snippets)
    except Exception as e:
        logger.exception("AI analyze failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service temporarily unavailable. Please try again later.",
        ) from e

    cache_entry = AiAnalyzeCache(
        user_id=user.id,
        cache_key=cache_key,
        response_text=explanation,
    )
    db.add(cache_entry)
    log_usage(db, user.id, "analyze")
    db.commit()

    return AiAnalyzeResponse(explanation=explanation, from_cache=False)


# ---------- Chat (Premium only) ----------


@router.post("/chat", response_model=AiChatResponse)
def ai_chat(
    body: AiChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_premium),
):
    """AI Assistant chat. Premium only. Max 50 messages per day."""
    allowed, err = check_chat_limit(db, user.id)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=err)

    history = _get_chat_history(db, user.id)
    try:
        reply, input_tokens, output_tokens = generate_chat(history, body.message)
    except Exception as e:
        logger.exception("AI chat failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service temporarily unavailable. Please try again later.",
        ) from e

    _save_chat_turn(db, user.id, body.message, reply, input_tokens, output_tokens)
    log_usage(db, user.id, "chat", input_tokens=input_tokens, output_tokens=output_tokens)

    from app.services.ai_rate_limiter import count_chat_today
    used = count_chat_today(db, user.id)
    remaining = max(0, CHAT_LIMIT_PREMIUM - used)

    return AiChatResponse(
        reply=reply,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        remaining_today=remaining,
    )


def _sse_message(data: dict) -> str:
    """Format a dict as one SSE event (data: json line + newline)."""
    return f"data: {json.dumps(data)}\n\n"


@router.post("/chat/stream")
def ai_chat_stream(
    body: AiChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_premium),
):
    """
    AI Assistant chat with streaming response (Server-Sent Events).
    Premium only. Counts toward 50/day. Events: data: {"delta": "..."} then data: {"done": true, "remaining_today": N}.
    """
    allowed, err = check_chat_limit(db, user.id)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=err)

    history = _get_chat_history(db, user.id)

    def event_stream():
        full_reply: list[str] = []
        try:
            for delta in generate_chat_stream(history, body.message):
                full_reply.append(delta)
                yield _sse_message({"delta": delta})
        except Exception as e:
            logger.exception("AI chat stream failed")
            yield _sse_message({"error": "AI service temporarily unavailable."})
            return
        reply_text = "".join(full_reply)
        _save_chat_turn(db, user.id, body.message, reply_text, 0, 0)
        log_usage(db, user.id, "chat")
        from app.services.ai_rate_limiter import count_chat_today
        used = count_chat_today(db, user.id)
        remaining = max(0, CHAT_LIMIT_PREMIUM - used)
        yield _sse_message({"done": True, "remaining_today": remaining})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat-with-image", response_model=AiChatResponse)
def ai_chat_with_image(
    message: str = Form(default="", max_length=8000),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_premium),
):
    """AI Assistant with image (screenshot of error, config, terminal). Premium only. Counts toward 50/day."""
    allowed, err = check_chat_limit(db, user.id)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=err)

    allowed_types = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
    ct = (image.content_type or "").split(";")[0].strip().lower()
    if ct not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image (png, jpeg, webp, gif).",
        )

    image_bytes = image.file.read()
    if len(image_bytes) > 10 * 1024 * 1024:  # 10 MB
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image too large (max 10 MB).")

    mime = ct or "image/png"
    history = _get_chat_history(db, user.id)
    try:
        reply, input_tokens, output_tokens = generate_chat_with_image(history, message or "What do you see? Please explain.", image_bytes, mime)
    except Exception as e:
        logger.exception("AI chat-with-image failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service temporarily unavailable. Please try again later.",
        ) from e

    user_content = f"[Image uploaded] {message}" if message else "[Image uploaded]"
    _save_chat_turn(db, user.id, user_content, reply, input_tokens, output_tokens)
    log_usage(db, user.id, "chat", input_tokens=input_tokens, output_tokens=output_tokens)

    from app.services.ai_rate_limiter import count_chat_today
    used = count_chat_today(db, user.id)
    remaining = max(0, CHAT_LIMIT_PREMIUM - used)

    return AiChatResponse(
        reply=reply,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        remaining_today=remaining,
    )
