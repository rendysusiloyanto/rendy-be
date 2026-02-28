"""
Redis cache for AI chat history. Cache-Aside: Redis is read-through cache only.
All Redis errors are handled internally; never raise to caller. System works if Redis is down.
Key: chat:{user_id} — Redis LIST of JSON strings. Last 10 items, TTL 1 day.
"""
import json
import logging
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

CHAT_KEY_PREFIX = "chat:"
# Keep last N in LIST (LTRIM -N -1)
DEFAULT_LIMIT = 10


def _key(user_id: str) -> str:
    return f"{CHAT_KEY_PREFIX}{user_id}"


def _serialize(message: dict) -> str:
    return json.dumps({"role": message["role"], "content": message.get("content", "")})


def _deserialize(s: str) -> dict | None:
    try:
        data = json.loads(s)
        if isinstance(data, dict) and "role" in data:
            return {"role": data["role"], "content": data.get("content", "")}
    except (json.JSONDecodeError, TypeError):
        pass
    return None


class RedisChatCache:
    """
    Async Redis cache for chat history. LIST-based: RPUSH, LTRIM, EXPIRE.
    All methods swallow Redis errors and log; caller gets None or no-op on failure.
    """

    def __init__(self, redis_client: Any, ttl_seconds: int | None = None, limit: int = DEFAULT_LIMIT):
        self._redis = redis_client
        self._ttl = ttl_seconds or get_settings().chat_cache_ttl_seconds
        self._limit = limit

    async def get_last_messages(self, user_id: str) -> list[dict] | None:
        """
        Cache-Aside read: LRANGE chat:{user_id} -limit -1.
        Returns list of {role, content} or None on miss/error (caller should hit DB).
        """
        if not self._redis:
            return None
        try:
            key = _key(user_id)
            # LRANGE -10 -1 => last 10 elements, left-to-right (oldest to newest)
            raw_list = await self._redis.lrange(key, -self._limit, -1)
            if not raw_list:
                return None
            out = []
            for item in raw_list:
                s = item.decode() if isinstance(item, bytes) else item
                m = _deserialize(s)
                if m:
                    out.append(m)
            return out if out else None
        except Exception as e:
            logger.warning("Redis chat cache get failed for user %s: %s", user_id, e, exc_info=False)
            return None

    async def append_message(self, user_id: str, message: dict) -> None:
        """
        After DB save: RPUSH one message, LTRIM to last N, EXPIRE.
        On Redis error: log only, do not raise.
        """
        if not self._redis:
            return
        try:
            key = _key(user_id)
            payload = _serialize(message)
            await self._redis.rpush(key, payload)
            await self._redis.ltrim(key, -self._limit, -1)
            await self._redis.expire(key, self._ttl)
        except Exception as e:
            logger.warning("Redis chat cache append failed for user %s: %s", user_id, e, exc_info=False)

    async def warm(self, user_id: str, messages: list[dict]) -> None:
        """
        Cache-Aside warm on DB miss: replace list with last N from DB, set EXPIRE.
        Does not delete key first; we RPUSH each then LTRIM so key is recreated.
        """
        if not self._redis or not messages:
            return
        try:
            key = _key(user_id)
            pipe = self._redis.pipeline()
            pipe.delete(key)  # start fresh so order is correct
            for m in messages:
                pipe.rpush(key, _serialize(m))
            pipe.ltrim(key, -self._limit, -1)
            pipe.expire(key, self._ttl)
            await pipe.execute()
        except Exception as e:
            logger.warning("Redis chat cache warm failed for user %s: %s", user_id, e, exc_info=False)
