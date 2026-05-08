import redis.asyncio as redis

from src.config import settings


_redis_client: redis.Redis | None = None


async def get_redis_client() -> redis.Redis:
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def close_redis_client() -> None:
    """Close Redis client connection."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
