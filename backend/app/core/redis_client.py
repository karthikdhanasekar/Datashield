"""
DataShield OSINT - Redis Client
Caching and session management
"""
from typing import Any, Optional
import json
import redis.asyncio as aioredis

from app.core.config import settings

_redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    """Get or create the Redis connection pool."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _redis_client


async def cache_set(key: str, value: Any, ttl: int = settings.REDIS_CACHE_TTL) -> None:
    """Set a value in cache with optional TTL."""
    client = await get_redis()
    serialized = json.dumps(value) if not isinstance(value, str) else value
    await client.setex(key, ttl, serialized)


async def cache_get(key: str) -> Optional[Any]:
    """Get a value from cache. Returns None if not found."""
    client = await get_redis()
    value = await client.get(key)
    if value is None:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


async def cache_delete(key: str) -> None:
    """Delete a key from cache."""
    client = await get_redis()
    await client.delete(key)


async def cache_delete_pattern(pattern: str) -> int:
    """Delete all keys matching a pattern. Returns count deleted."""
    client = await get_redis()
    keys = await client.keys(pattern)
    if keys:
        return await client.delete(*keys)
    return 0


async def add_to_blacklist(jti: str, ttl: int) -> None:
    """Add a JWT ID to the token blacklist (for logout/revocation)."""
    client = await get_redis()
    await client.setex(f"blacklist:jwt:{jti}", ttl, "1")


async def is_blacklisted(jti: str) -> bool:
    """Check if a JWT ID is blacklisted."""
    client = await get_redis()
    return await client.exists(f"blacklist:jwt:{jti}") > 0


async def close_redis() -> None:
    """Close the Redis connection."""
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
