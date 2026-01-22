"""
Redis Client 헬퍼
"""
import logging
from typing import Optional
import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger(__name__)

# Redis 클라이언트 인스턴스
_redis_client: Optional[redis.Redis] = None


async def get_redis_client() -> redis.Redis:
    """
    Redis 클라이언트 반환 (싱글톤)

    Returns:
        Redis 클라이언트 인스턴스
    """
    global _redis_client

    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=settings.redis_max_connections,
        )
        logger.info(f"Redis client initialized: {settings.redis_url}")

    return _redis_client


async def close_redis_client():
    """Redis 클라이언트 종료"""
    global _redis_client

    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis client closed")
