"""
AI endpoints for jns23lab:
- POST /ai/analyze — failure analysis (all users, rate limited; cached)
- POST /ai/chat — assistant chat (premium only; 50/day)
- GET /ai/chat/history — chat history for current user (premium; ownership validated)
- POST /ai/chat/stream — assistant chat streaming (SSE)
- POST /ai/chat-with-image — chat with image (premium only; counts toward 50/day)
"""
import hashlib
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.auth import get_current_user, get_current_user_premium, require_not_blacklisted
from app.database import get_db, SessionLocal
from app.models.user import User
from app.models.ai_analyze_cache import AiAnalyzeCache
from app.schemas.ai import (
    AiAnalyzeRequest,
    AiAnalyzeResponse,
    AiChatRequest,
    AiChatResponse,
    AiChatHistoryResponse,
    AiChatMessageOut,
)
from app.services.ai_service import generate_analyze, generate_chat, generate_chat_stream, generate_chat_with_image
from app.services.ai_rate_limiter import (
    check_analyze_limit,
    check_chat_limit,
    log_usage,
    CHAT_LIMIT_PREMIUM,
    count_chat_today,
)
from app.services.ai_stream_service import stream_chat_response
from app.services.chat_service import ChatService
from app.repositories.chat_repository import ChatRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _analyze_cache_key(user_id: str, payload: dict) -> str:
    """Stable hash for caching analyze result."""
    normalized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(f"{user_id}:{normalized}".encode()).hexdigest()[:64]


# ---------- Dependencies: Redis (optional) + ChatService (Cache-Aside) ----------


async def _get_redis_chat_cache_dep():
    """Async dependency: Redis chat cache or None if Redis disabled/down."""
    from app.core.redis import get_redis_client, build_redis_chat_cache
    client = await get_redis_client()
    return build_redis_chat_cache(client) if client else None


def _get_chat_service_dep(
    redis_cache=Depends(_get_redis_chat_cache_dep),
) -> ChatService:
    """ChatService with optional Redis cache (Cache-Aside). DB is source of truth."""
    return ChatService(redis_cache=redis_cache, repository=ChatRepository())


# ---------- Health (Redis optional) ----------


@router.get("/health")
async def ai_health():
    """Health check: Redis status (optional). DB not checked here."""
    from app.core.redis import get_redis_client
    client = await get_redis_client()
    if client is None:
        return {"redis": "unavailable", "message": "Redis disabled or connection failed"}
    try:
        await client.ping()
        return {"redis": "ok"}
    except Exception as e:
        logger.warning("Redis health ping failed: %s", e)
        return {"redis": "error", "message": str(e)}


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
async def ai_chat(
    body: AiChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_premium),
    chat_service: ChatService = Depends(_get_chat_service_dep),
):
    """AI Assistant chat. Premium only. Max 50 messages per day. History via Cache-Aside (DB + Redis)."""
    allowed, err = check_chat_limit(db, user.id)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=err)

    # 1) Load history (Redis on hit, else DB then warm Redis)
    history = await chat_service.get_history(db, user.id)
    try:
        reply, input_tokens, output_tokens = generate_chat(history, body.message)
    except Exception as e:
        logger.exception("AI chat failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service temporarily unavailable. Please try again later.",
        ) from e

    # 2) Save to DB first, then Redis (best-effort)
    await chat_service.save_turn(
        db, user.id, body.message, reply,
        input_tokens=input_tokens, output_tokens=output_tokens,
    )
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


@router.get("/chat/history", response_model=AiChatHistoryResponse)
async def ai_chat_history(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_premium),
    chat_service: ChatService = Depends(_get_chat_service_dep),
):
    """
    Get chat history for the current user. Premium only.
    Ownership: only messages in the user's conversation are returned; ordered by created_at asc.
    """
    messages = await chat_service.get_history_for_user(db, user.id, limit=100)
    return AiChatHistoryResponse(
        messages=[AiChatMessageOut(**m) for m in messages],
    )


@router.post("/chat/stream")
async def ai_chat_stream(
    body: AiChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_premium),
    chat_service: ChatService = Depends(_get_chat_service_dep),
):
    """
    AI Assistant chat with streaming response (Server-Sent Events).
    Word-grouped stream with small delay for natural feel. Premium only. 50/day.
    History via Cache-Aside (DB + Redis).
    """
    allowed, err = check_chat_limit(db, user.id)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=err)

    history = await chat_service.get_history(db, user.id)

    # Persist user message before streaming so history is stored even if stream fails later
    try:
        await chat_service.save_user_message(db, user.id, body.message)
    except Exception as e:
        logger.warning("save_user_message failed before stream: %s", e)

    # Use fresh session in callback: by the time stream ends, request-scoped db/user may be closed/detached
    user_id = user.id
    message_text = body.message

    async def on_stream_done(full_reply_text: str) -> int:
        """Save assistant message after stream, log usage, return remaining_today. Uses fresh DB session."""
        db_fresh = SessionLocal()
        try:
            await chat_service.save_assistant_message(db_fresh, user_id, full_reply_text)
            log_usage(db_fresh, user_id, "chat")
            used = count_chat_today(db_fresh, user_id)
            return max(0, CHAT_LIMIT_PREMIUM - used)
        except Exception as e:
            logger.warning("save_assistant_message/log_usage failed (stream already sent): %s", e)
            return 0
        finally:
            db_fresh.close()

    return await stream_chat_response(history, body.message, on_stream_done)


@router.post("/chat-with-image", response_model=AiChatResponse)
async def ai_chat_with_image(
    message: str = Form(default="", max_length=8000),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_premium),
    chat_service: ChatService = Depends(_get_chat_service_dep),
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

    image_bytes = await image.read()
    if len(image_bytes) > 10 * 1024 * 1024:  # 10 MB
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image too large (max 10 MB).")

    mime = ct or "image/png"
    history = await chat_service.get_history(db, user.id)
    try:
        reply, input_tokens, output_tokens = generate_chat_with_image(history, message or "What do you see? Please explain.", image_bytes, mime)
    except Exception as e:
        logger.exception("AI chat-with-image failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service temporarily unavailable. Please try again later.",
        ) from e

    user_content = f"[Image uploaded] {message}" if message else "[Image uploaded]"
    await chat_service.save_turn(db, user.id, user_content, reply, input_tokens=input_tokens, output_tokens=output_tokens)
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
