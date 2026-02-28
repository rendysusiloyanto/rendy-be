"""
Chat orchestration: Cache-Aside over DB (source of truth) + Redis (cache).
- Load: try Redis; on miss load from DB, warm Redis, return.
- Save: write to DB first, then best-effort Redis (RPUSH + LTRIM + EXPIRE).
If Redis is down, all operations use DB only; no crash, no mass migration.
"""
import asyncio
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.repositories.chat_repository import ChatRepository
from app.services.redis_chat_cache import RedisChatCache

logger = logging.getLogger(__name__)


class ChatService:
    """Orchestrates chat history: DB as source of truth, Redis as cache (Cache-Aside)."""

    def __init__(
        self,
        redis_cache: RedisChatCache | None,
        repository: ChatRepository | None = None,
    ):
        self._cache = redis_cache
        self._repo = repository or ChatRepository()
        self._limit = get_settings().chat_history_max_messages

    async def get_history(self, db: Session, user_id: str) -> list[dict]:
        """
        Cache-Aside: try Redis first; on miss load from DB, warm Redis, return.
        If Redis is down, returns DB result only.
        """
        # 1) Try Redis
        if self._cache:
            messages = await self._cache.get_last_messages(user_id)
            if messages is not None:
                return messages
        # 2) Cache miss or Redis down: load from DB
        loop = asyncio.get_event_loop()
        messages = await loop.run_in_executor(
            None,
            lambda: self._repo.get_last_messages(db, user_id, self._limit),
        )
        # 3) Warm Redis (best-effort; ignore failure)
        if self._cache and messages:
            await self._cache.warm(user_id, messages)
        return messages

    async def save_turn(
        self,
        db: Session,
        user_id: str,
        user_content: str,
        assistant_content: str,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> None:
        """
        Save user + assistant message. DB first (source of truth), then Redis.
        Redis failures are logged only; correctness does not depend on Redis.
        """
        loop = asyncio.get_event_loop()
        # 1) Save to DB first
        await loop.run_in_executor(
            None,
            lambda: self._repo.save_message(db, user_id, "user", user_content, input_tokens=input_tokens),
        )
        if self._cache:
            await self._cache.append_message(user_id, {"role": "user", "content": user_content})

        await loop.run_in_executor(
            None,
            lambda: self._repo.save_message(
                db, user_id, "assistant", assistant_content, output_tokens=output_tokens
            ),
        )
        if self._cache:
            await self._cache.append_message(user_id, {"role": "assistant", "content": assistant_content})
        # Keep DB to last N only (same as Redis window)
        await loop.run_in_executor(None, lambda: self._repo.trim_to_last_n(db, user_id, self._limit))
