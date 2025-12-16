"""
TriFlow AI - 캐시 서비스
Redis 기반 캐싱 유틸리티
"""
import json
import hashlib
import logging
from typing import Any, Optional, Callable, TypeVar
from functools import wraps

import redis
from redis import ConnectionPool

from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheService:
    """Redis 캐시 서비스"""

    _pool: Optional[ConnectionPool] = None
    _client: Optional[redis.Redis] = None

    # 기본 캐시 TTL (초)
    DEFAULT_TTL = 300  # 5분
    SHORT_TTL = 60  # 1분
    MEDIUM_TTL = 600  # 10분
    LONG_TTL = 3600  # 1시간

    @classmethod
    def get_pool(cls) -> ConnectionPool:
        """Redis 연결 풀 가져오기"""
        if cls._pool is None:
            try:
                cls._pool = ConnectionPool.from_url(
                    settings.redis_url,
                    max_connections=settings.redis_max_connections,
                    decode_responses=True,
                )
                logger.info("Redis connection pool created")
            except Exception as e:
                logger.warning(f"Failed to create Redis pool: {e}")
                raise
        return cls._pool

    @classmethod
    def get_client(cls) -> Optional[redis.Redis]:
        """Redis 클라이언트 가져오기"""
        if cls._client is None:
            try:
                pool = cls.get_pool()
                cls._client = redis.Redis(connection_pool=pool)
                # 연결 테스트
                cls._client.ping()
                logger.info("Redis client connected")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}. Caching disabled.")
                cls._client = None
        return cls._client

    @classmethod
    def is_available(cls) -> bool:
        """Redis 사용 가능 여부 확인"""
        client = cls.get_client()
        if client is None:
            return False
        try:
            client.ping()
            return True
        except Exception:
            return False

    @classmethod
    def generate_key(cls, prefix: str, *args, **kwargs) -> str:
        """캐시 키 생성"""
        # args와 kwargs를 문자열로 변환하여 해시
        key_parts = [prefix]
        key_parts.extend(str(arg) for arg in args)
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))

        key_string = ":".join(key_parts)

        # 키가 너무 길면 해시 사용
        if len(key_string) > 200:
            hash_suffix = hashlib.md5(key_string.encode()).hexdigest()[:16]
            return f"{prefix}:{hash_suffix}"

        return key_string

    @classmethod
    def get(cls, key: str) -> Optional[Any]:
        """캐시에서 값 조회"""
        client = cls.get_client()
        if client is None:
            return None

        try:
            value = client.get(key)
            if value is not None:
                logger.debug(f"Cache hit: {key}")
                return json.loads(value)
            logger.debug(f"Cache miss: {key}")
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"Cache JSON decode error for {key}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Cache get error: {e}")
            return None

    @classmethod
    def set(
        cls,
        key: str,
        value: Any,
        ttl: int = DEFAULT_TTL,
    ) -> bool:
        """캐시에 값 저장"""
        client = cls.get_client()
        if client is None:
            return False

        try:
            serialized = json.dumps(value, default=str)
            client.setex(key, ttl, serialized)
            logger.debug(f"Cache set: {key} (TTL: {ttl}s)")
            return True
        except (TypeError, json.JSONEncoder) as e:
            logger.warning(f"Cache serialization error for {key}: {e}")
            return False
        except Exception as e:
            logger.warning(f"Cache set error: {e}")
            return False

    @classmethod
    def delete(cls, key: str) -> bool:
        """캐시에서 값 삭제"""
        client = cls.get_client()
        if client is None:
            return False

        try:
            client.delete(key)
            logger.debug(f"Cache deleted: {key}")
            return True
        except Exception as e:
            logger.warning(f"Cache delete error: {e}")
            return False

    @classmethod
    def delete_pattern(cls, pattern: str) -> int:
        """패턴에 맞는 모든 키 삭제"""
        client = cls.get_client()
        if client is None:
            return 0

        try:
            keys = list(client.scan_iter(match=pattern))
            if keys:
                deleted = client.delete(*keys)
                logger.debug(f"Cache deleted {deleted} keys matching {pattern}")
                return deleted
            return 0
        except Exception as e:
            logger.warning(f"Cache delete pattern error: {e}")
            return 0

    @classmethod
    def clear_all(cls) -> bool:
        """모든 캐시 삭제 (주의!)"""
        client = cls.get_client()
        if client is None:
            return False

        try:
            client.flushdb()
            logger.warning("All cache cleared!")
            return True
        except Exception as e:
            logger.warning(f"Cache clear error: {e}")
            return False

    @classmethod
    def get_or_set(
        cls,
        key: str,
        factory: Callable[[], T],
        ttl: int = DEFAULT_TTL,
    ) -> Optional[T]:
        """캐시에서 값을 가져오거나, 없으면 생성하여 저장"""
        # 캐시에서 먼저 조회
        cached = cls.get(key)
        if cached is not None:
            return cached

        # 없으면 팩토리 함수로 생성
        try:
            value = factory()
            cls.set(key, value, ttl)
            return value
        except Exception as e:
            logger.error(f"Cache factory error: {e}")
            raise

    @classmethod
    def increment(cls, key: str, amount: int = 1) -> Optional[int]:
        """카운터 증가"""
        client = cls.get_client()
        if client is None:
            return None

        try:
            return client.incrby(key, amount)
        except Exception as e:
            logger.warning(f"Cache increment error: {e}")
            return None

    @classmethod
    def rate_limit(cls, key: str, max_requests: int, window_seconds: int) -> bool:
        """Rate limiting 체크 (True: 허용, False: 제한)"""
        client = cls.get_client()
        if client is None:
            return True  # Redis 없으면 제한 없이 허용

        try:
            current = client.get(key)
            if current is None:
                # 새 윈도우 시작
                client.setex(key, window_seconds, 1)
                return True

            count = int(current)
            if count >= max_requests:
                return False

            client.incr(key)
            return True
        except Exception as e:
            logger.warning(f"Rate limit error: {e}")
            return True


def cached(
    prefix: str,
    ttl: int = CacheService.DEFAULT_TTL,
    key_builder: Optional[Callable[..., str]] = None,
):
    """
    캐싱 데코레이터

    Usage:
        @cached("users", ttl=300)
        def get_user(user_id: str):
            return db.query(User).filter(User.id == user_id).first()

        @cached("stats", key_builder=lambda tenant_id, **kw: f"stats:{tenant_id}")
        def get_tenant_stats(tenant_id: str):
            return calculate_stats(tenant_id)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # 캐시 키 생성
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                cache_key = CacheService.generate_key(prefix, *args, **kwargs)

            # 캐시 조회 시도
            cached_value = CacheService.get(cache_key)
            if cached_value is not None:
                return cached_value

            # 원본 함수 실행
            result = func(*args, **kwargs)

            # 결과 캐싱
            CacheService.set(cache_key, result, ttl)

            return result

        return wrapper
    return decorator


def cached_async(
    prefix: str,
    ttl: int = CacheService.DEFAULT_TTL,
    key_builder: Optional[Callable[..., str]] = None,
):
    """
    비동기 캐싱 데코레이터

    Usage:
        @cached_async("users", ttl=300)
        async def get_user(user_id: str):
            return await db.query(User).filter(User.id == user_id).first()
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # 캐시 키 생성
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                cache_key = CacheService.generate_key(prefix, *args, **kwargs)

            # 캐시 조회 시도
            cached_value = CacheService.get(cache_key)
            if cached_value is not None:
                return cached_value

            # 원본 함수 실행
            result = await func(*args, **kwargs)

            # 결과 캐싱
            CacheService.set(cache_key, result, ttl)

            return result

        return wrapper
    return decorator


# 캐시 키 프리픽스 상수
class CacheKeys:
    """캐시 키 프리픽스"""
    SENSOR_DATA = "sensor"
    WORKFLOW = "workflow"
    RULESET = "ruleset"
    USER = "user"
    TENANT = "tenant"
    AGENT_RESULT = "agent"
    STATS = "stats"
    API_KEY = "apikey"
    RATE_LIMIT = "ratelimit"


# 편의 함수들
def invalidate_sensor_cache(tenant_id: str = None):
    """센서 데이터 캐시 무효화"""
    if tenant_id:
        CacheService.delete_pattern(f"{CacheKeys.SENSOR_DATA}:{tenant_id}:*")
    else:
        CacheService.delete_pattern(f"{CacheKeys.SENSOR_DATA}:*")


def invalidate_workflow_cache(workflow_id: str = None):
    """워크플로우 캐시 무효화"""
    if workflow_id:
        CacheService.delete_pattern(f"{CacheKeys.WORKFLOW}:{workflow_id}:*")
    else:
        CacheService.delete_pattern(f"{CacheKeys.WORKFLOW}:*")


def invalidate_ruleset_cache(ruleset_id: str = None):
    """룰셋 캐시 무효화"""
    if ruleset_id:
        CacheService.delete_pattern(f"{CacheKeys.RULESET}:{ruleset_id}:*")
    else:
        CacheService.delete_pattern(f"{CacheKeys.RULESET}:*")
