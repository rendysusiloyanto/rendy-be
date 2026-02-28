"""
Optional async Redis client for chat cache. If redis_url is empty or connection fails, returns None.
No mass migration or startup sync; cache warms on read (Cache-Aside).
"""
import logging
from typing import Any

from app.config import get_settings
from app.services.redis_chat_cache import RedisChatCache

logger = logging.getLogger(__name__)

_redis_client: Any = None


async def get_redis_client() -> Any:
    """Lazy singleton: one async Redis client or None if disabled/unavailable."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    url = (get_settings().redis_url or "").strip()
    if not url:
        return None
    try:
        from redis.asyncio import Redis
        client = Redis.from_url(url, decode_responses=True)
        await client.ping()
        _redis_client = client
        logger.info("Redis chat cache connected: %s", url.split("@")[-1] if "@" in url else url)
        return _redis_client
    except Exception as e:
        logger.warning("Redis unavailable (chat cache disabled): %s", e, exc_info=False)
        return None


def build_redis_chat_cache(client: Any) -> RedisChatCache:
    """Build RedisChatCache from an async Redis client."""
    return RedisChatCache(client)


async def close_redis() -> None:
    """Graceful shutdown: close Redis connection."""
    global _redis_client
    if _redis_client is not None:
        try:
            await _redis_client.aclose()
        except Exception as e:
            logger.warning("Redis close error: %s", e)
        _redis_client = None
