"""
Chat orchestration: Conversation + Message persistence, Cache-Aside over DB + Redis.
- Save user message before streaming; save assistant message after streaming.
- Load: try Redis; on miss load from DB, warm Redis, return.
- Ownership: all reads/writes are scoped to the user's conversation (conversation.user_id).
"""
import asyncio
import logging

from sqlalchemy.orm import Session

from app.config import get_settings
from app.repositories.chat_repository import ChatRepository
from app.services.redis_chat_cache import RedisChatCache
from app.utils.markdown import normalize_markdown

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
        Returns last N messages in user's conversation, oldest-first (for Gemini context).
        """
        if self._cache:
            messages = await self._cache.get_last_messages(user_id)
            if messages is not None:
                return messages
        loop = asyncio.get_event_loop()
        messages = await loop.run_in_executor(
            None,
            lambda: self._repo.get_last_messages(db, user_id, self._limit),
        )
        if self._cache and messages:
            await self._cache.warm(user_id, messages)
        return messages

    async def save_user_message(self, db: Session, user_id: str, content: str) -> None:
        """
        Save the user message (e.g. before streaming). Creates conversation if needed.
        DB first, then best-effort Redis append.
        """
        loop = asyncio.get_event_loop()

        def _do():
            conv = self._repo.get_or_create_conversation(db, user_id)
            self._repo.save_message(
                db, user_id, "user", content, conversation_id=conv.id
            )
            return conv.id

        await loop.run_in_executor(None, _do)
        if self._cache:
            await self._cache.append_message(user_id, {"role": "user", "content": content})

    async def save_assistant_message(
        self,
        db: Session,
        user_id: str,
        content: str,
        *,
        output_tokens: int | None = None,
    ) -> None:
        """
        Save the assistant message (e.g. after streaming). Uses existing conversation.
        Normalizes Markdown before saving. DB first, then Redis, then trim.
        """
        content = normalize_markdown(content)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._repo.save_message(
                db,
                user_id,
                "assistant",
                content,
                conversation_id=self._repo.get_or_create_conversation(db, user_id).id,
                output_tokens=output_tokens,
            ),
        )
        if self._cache:
            await self._cache.append_message(user_id, {"role": "assistant", "content": content})
        await loop.run_in_executor(None, lambda: self._repo.trim_to_last_n(db, user_id, self._limit))

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
        Save user + assistant in one go (non-streaming / chat-with-image).
        Normalizes assistant Markdown before saving. Uses conversation; DB first, then Redis; trim to last N.
        """
        assistant_content = normalize_markdown(assistant_content)
        loop = asyncio.get_event_loop()

        def _do():
            conv = self._repo.get_or_create_conversation(db, user_id)
            self._repo.save_message(
                db, user_id, "user", user_content,
                conversation_id=conv.id,
                input_tokens=input_tokens,
            )
            self._repo.save_message(
                db, user_id, "assistant", assistant_content,
                conversation_id=conv.id,
                output_tokens=output_tokens,
            )
            self._repo.trim_to_last_n(db, user_id, self._limit)

        await loop.run_in_executor(None, _do)
        if self._cache:
            await self._cache.append_message(user_id, {"role": "user", "content": user_content})
            await self._cache.append_message(user_id, {"role": "assistant", "content": assistant_content})

    async def get_history_for_user(self, db: Session, user_id: str, limit: int = 100) -> list[dict]:
        """
        Get full ordered history for GET endpoint. Ownership: only messages in
        the conversation owned by user_id. Ordered by created_at asc.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._repo.get_messages_ordered_for_user(db, user_id, limit),
        )
