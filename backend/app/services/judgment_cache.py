"""
Judgment 캐시 서비스
스펙 참조: B-6, B-2-1

- TTL 기반 캐시 (기본 300초)
- Redis 또는 PostgreSQL 백엔드
- 캐시 히트율 추적
"""
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from uuid import UUID

from app.config import settings

logger = logging.getLogger(__name__)


class JudgmentCache:
    """
    Judgment 결과 캐시

    캐시 키 구조: {tenant_id}:{ruleset_id}:{input_hash}
    """

    DEFAULT_TTL_SECONDS = 3600  # 1시간 (300초에서 확장)

    def __init__(self, use_redis: bool = True):
        self.use_redis = use_redis and settings.redis_url is not None
        self._redis_client = None
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

        if self.use_redis:
            try:
                import redis
                self._redis_client = redis.from_url(settings.redis_url)
                self._redis_client.ping()
                logger.info("JudgmentCache: Redis connected")
            except Exception as e:
                logger.warning(f"JudgmentCache: Redis unavailable, using memory cache: {e}")
                self.use_redis = False

    def _compute_hash(self, input_data: Dict[str, Any]) -> str:
        """입력 데이터 해시 계산"""
        # 정렬된 JSON 문자열로 변환하여 일관된 해시 생성
        json_str = json.dumps(input_data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()[:32]

    def _build_key(self, tenant_id: UUID, ruleset_id: UUID, input_hash: str) -> str:
        """캐시 키 생성"""
        return f"judgment:{tenant_id}:{ruleset_id}:{input_hash}"

    async def get(
        self,
        tenant_id: UUID,
        ruleset_id: UUID,
        input_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        캐시에서 결과 조회

        Returns:
            캐시 히트 시: {
                "result": {...},
                "confidence": 0.95,
                "cached_at": "...",
                "cache_hit": True
            }
            캐시 미스 시: None
        """
        input_hash = self._compute_hash(input_data)
        cache_key = self._build_key(tenant_id, ruleset_id, input_hash)

        try:
            if self.use_redis and self._redis_client:
                cached = self._redis_client.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    # 히트 카운트 증가
                    self._redis_client.hincrby(f"{cache_key}:meta", "hit_count", 1)
                    logger.debug(f"Cache HIT: {cache_key}")
                    return {**data, "cache_hit": True}
            else:
                # 메모리 캐시
                if cache_key in self._memory_cache:
                    entry = self._memory_cache[cache_key]
                    # TTL 체크
                    if datetime.fromisoformat(entry["expires_at"]) > datetime.utcnow():
                        entry["hit_count"] = entry.get("hit_count", 0) + 1
                        logger.debug(f"Memory cache HIT: {cache_key}")
                        return {**entry["data"], "cache_hit": True}
                    else:
                        # 만료된 캐시 삭제
                        del self._memory_cache[cache_key]

            logger.debug(f"Cache MISS: {cache_key}")
            return None

        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None

    async def set(
        self,
        tenant_id: UUID,
        ruleset_id: UUID,
        input_data: Dict[str, Any],
        result: Dict[str, Any],
        confidence: float,
        ttl_seconds: int = None,
    ) -> bool:
        """
        결과를 캐시에 저장
        """
        input_hash = self._compute_hash(input_data)
        cache_key = self._build_key(tenant_id, ruleset_id, input_hash)
        ttl = ttl_seconds or self.DEFAULT_TTL_SECONDS

        cache_data = {
            "result": result,
            "confidence": confidence,
            "cached_at": datetime.utcnow().isoformat(),
            "input_hash": input_hash,
            "ruleset_id": str(ruleset_id),
        }

        try:
            if self.use_redis and self._redis_client:
                self._redis_client.setex(
                    cache_key,
                    ttl,
                    json.dumps(cache_data, default=str),
                )
                # 메타데이터 저장
                self._redis_client.hset(f"{cache_key}:meta", mapping={
                    "hit_count": 0,
                    "created_at": datetime.utcnow().isoformat(),
                    "ttl_seconds": ttl,
                })
                self._redis_client.expire(f"{cache_key}:meta", ttl)
            else:
                # 메모리 캐시
                self._memory_cache[cache_key] = {
                    "data": cache_data,
                    "expires_at": (datetime.utcnow() + timedelta(seconds=ttl)).isoformat(),
                    "hit_count": 0,
                }

            logger.debug(f"Cache SET: {cache_key}, TTL: {ttl}s")
            return True

        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False

    async def invalidate(
        self,
        tenant_id: UUID,
        ruleset_id: UUID = None,
    ) -> int:
        """
        캐시 무효화

        ruleset_id 지정 시 해당 ruleset만, 미지정 시 tenant 전체 무효화
        """
        pattern = f"judgment:{tenant_id}:"
        if ruleset_id:
            pattern += f"{ruleset_id}:*"
        else:
            pattern += "*"

        count = 0

        try:
            if self.use_redis and self._redis_client:
                keys = self._redis_client.keys(pattern)
                if keys:
                    count = self._redis_client.delete(*keys)
            else:
                # 메모리 캐시
                keys_to_delete = [k for k in self._memory_cache.keys() if k.startswith(pattern.replace("*", ""))]
                for key in keys_to_delete:
                    del self._memory_cache[key]
                    count += 1

            logger.info(f"Cache invalidated: {pattern}, count: {count}")
            return count

        except Exception as e:
            logger.error(f"Cache invalidate error: {e}")
            return 0

    async def get_stats(self, tenant_id: UUID = None) -> Dict[str, Any]:
        """
        캐시 통계 조회
        """
        try:
            if self.use_redis and self._redis_client:
                pattern = f"judgment:{tenant_id or '*'}:*"
                keys = self._redis_client.keys(pattern)

                total_entries = len([k for k in keys if not k.decode().endswith(":meta")])
                total_hits = 0

                for key in keys:
                    if key.decode().endswith(":meta"):
                        hits = self._redis_client.hget(key, "hit_count")
                        total_hits += int(hits or 0)

                return {
                    "backend": "redis",
                    "total_entries": total_entries,
                    "total_hits": total_hits,
                    "default_ttl": self.DEFAULT_TTL_SECONDS,
                }
            else:
                # 메모리 캐시 통계
                valid_entries = [
                    e for e in self._memory_cache.values()
                    if datetime.fromisoformat(e["expires_at"]) > datetime.utcnow()
                ]
                total_hits = sum(e.get("hit_count", 0) for e in valid_entries)

                return {
                    "backend": "memory",
                    "total_entries": len(valid_entries),
                    "total_hits": total_hits,
                    "default_ttl": self.DEFAULT_TTL_SECONDS,
                }

        except Exception as e:
            logger.error(f"Cache stats error: {e}")
            return {"error": str(e)}


# 전역 인스턴스
_judgment_cache: Optional[JudgmentCache] = None


def get_judgment_cache() -> JudgmentCache:
    """JudgmentCache 싱글톤 인스턴스 반환"""
    global _judgment_cache
    if _judgment_cache is None:
        _judgment_cache = JudgmentCache()
    return _judgment_cache


def reset_judgment_cache():
    """테스트용 캐시 리셋"""
    global _judgment_cache
    _judgment_cache = None
