"""
Judgment Cache 테스트
JudgmentCache 클래스 테스트 (메모리 캐시)
"""
import pytest
from unittest.mock import patch
from uuid import uuid4
from datetime import datetime, timedelta


# ========== JudgmentCache 초기화 테스트 ==========


class TestJudgmentCacheInit:
    """JudgmentCache 초기화 테스트"""

    def test_init_no_redis(self):
        """Redis 없이 초기화"""
        from app.services.judgment_cache import JudgmentCache

        with patch("app.services.judgment_cache.settings") as mock_settings:
            mock_settings.redis_url = None
            cache = JudgmentCache(use_redis=False)

        assert cache.use_redis is False
        assert cache._redis_client is None
        assert cache._memory_cache == {}

    def test_init_redis_unavailable(self):
        """Redis 사용 불가 시 메모리 fallback"""
        from app.services.judgment_cache import JudgmentCache

        with patch("app.services.judgment_cache.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379"
            with patch.dict("sys.modules", {"redis": None}):
                cache = JudgmentCache(use_redis=True)

        # Redis 연결 실패 시 메모리로 폴백
        assert cache._memory_cache == {}

    def test_default_ttl(self):
        """기본 TTL 값"""
        from app.services.judgment_cache import JudgmentCache

        assert JudgmentCache.DEFAULT_TTL_SECONDS == 300


# ========== _compute_hash 테스트 ==========


class TestComputeHash:
    """_compute_hash 메서드 테스트"""

    def test_compute_hash_deterministic(self):
        """동일 입력에 동일 해시"""
        from app.services.judgment_cache import JudgmentCache

        with patch("app.services.judgment_cache.settings") as mock_settings:
            mock_settings.redis_url = None
            cache = JudgmentCache(use_redis=False)

        data = {"key": "value", "number": 123}
        hash1 = cache._compute_hash(data)
        hash2 = cache._compute_hash(data)

        assert hash1 == hash2

    def test_compute_hash_different_data(self):
        """다른 입력에 다른 해시"""
        from app.services.judgment_cache import JudgmentCache

        with patch("app.services.judgment_cache.settings") as mock_settings:
            mock_settings.redis_url = None
            cache = JudgmentCache(use_redis=False)

        hash1 = cache._compute_hash({"key": "value1"})
        hash2 = cache._compute_hash({"key": "value2"})

        assert hash1 != hash2

    def test_compute_hash_order_independent(self):
        """키 순서에 무관한 해시"""
        from app.services.judgment_cache import JudgmentCache

        with patch("app.services.judgment_cache.settings") as mock_settings:
            mock_settings.redis_url = None
            cache = JudgmentCache(use_redis=False)

        hash1 = cache._compute_hash({"a": 1, "b": 2})
        hash2 = cache._compute_hash({"b": 2, "a": 1})

        assert hash1 == hash2

    def test_compute_hash_length(self):
        """해시 길이 (32자)"""
        from app.services.judgment_cache import JudgmentCache

        with patch("app.services.judgment_cache.settings") as mock_settings:
            mock_settings.redis_url = None
            cache = JudgmentCache(use_redis=False)

        hash_val = cache._compute_hash({"test": "data"})

        assert len(hash_val) == 32


# ========== _build_key 테스트 ==========


class TestBuildKey:
    """_build_key 메서드 테스트"""

    def test_build_key_format(self):
        """캐시 키 형식"""
        from app.services.judgment_cache import JudgmentCache

        with patch("app.services.judgment_cache.settings") as mock_settings:
            mock_settings.redis_url = None
            cache = JudgmentCache(use_redis=False)

        tenant_id = uuid4()
        ruleset_id = uuid4()
        input_hash = "abc123"

        key = cache._build_key(tenant_id, ruleset_id, input_hash)

        assert key.startswith("judgment:")
        assert str(tenant_id) in key
        assert str(ruleset_id) in key
        assert input_hash in key


# ========== get/set 테스트 (메모리 캐시) ==========


class TestMemoryCacheGetSet:
    """메모리 캐시 get/set 테스트"""

    @pytest.fixture
    def cache(self):
        """메모리 캐시 인스턴스"""
        from app.services.judgment_cache import JudgmentCache

        with patch("app.services.judgment_cache.settings") as mock_settings:
            mock_settings.redis_url = None
            return JudgmentCache(use_redis=False)

    @pytest.mark.asyncio
    async def test_get_cache_miss(self, cache):
        """캐시 미스"""
        tenant_id = uuid4()
        ruleset_id = uuid4()
        input_data = {"sensor": "temp", "value": 100}

        result = await cache.get(tenant_id, ruleset_id, input_data)

        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache):
        """캐시 저장 및 조회"""
        tenant_id = uuid4()
        ruleset_id = uuid4()
        input_data = {"sensor": "temp", "value": 100}
        result_data = {"action": "alert", "severity": "high"}

        # 저장
        success = await cache.set(tenant_id, ruleset_id, input_data, result_data, confidence=0.95)
        assert success is True

        # 조회
        cached = await cache.get(tenant_id, ruleset_id, input_data)

        assert cached is not None
        assert cached["cache_hit"] is True
        assert cached["result"] == result_data
        assert cached["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_cache_hit_count_increases(self, cache):
        """캐시 히트 카운트 증가"""
        tenant_id = uuid4()
        ruleset_id = uuid4()
        input_data = {"key": "value"}
        result_data = {"result": "ok"}

        await cache.set(tenant_id, ruleset_id, input_data, result_data, confidence=0.9)

        # 여러 번 조회
        await cache.get(tenant_id, ruleset_id, input_data)
        await cache.get(tenant_id, ruleset_id, input_data)

        # 메모리 캐시에서 히트 카운트 확인
        input_hash = cache._compute_hash(input_data)
        cache_key = cache._build_key(tenant_id, ruleset_id, input_hash)
        assert cache._memory_cache[cache_key]["hit_count"] >= 2

    @pytest.mark.asyncio
    async def test_cache_expiry(self, cache):
        """캐시 만료"""
        tenant_id = uuid4()
        ruleset_id = uuid4()
        input_data = {"key": "value"}
        result_data = {"result": "ok"}

        # 1초 TTL로 저장
        await cache.set(tenant_id, ruleset_id, input_data, result_data, confidence=0.9, ttl_seconds=1)

        # 즉시 조회 - 히트
        cached = await cache.get(tenant_id, ruleset_id, input_data)
        assert cached is not None

        # 만료 시뮬레이션 - expires_at을 과거로 설정
        input_hash = cache._compute_hash(input_data)
        cache_key = cache._build_key(tenant_id, ruleset_id, input_hash)
        cache._memory_cache[cache_key]["expires_at"] = (datetime.utcnow() - timedelta(seconds=10)).isoformat()

        # 다시 조회 - 미스
        cached = await cache.get(tenant_id, ruleset_id, input_data)
        assert cached is None


# ========== invalidate 테스트 ==========


class TestInvalidate:
    """invalidate 메서드 테스트"""

    @pytest.fixture
    def cache(self):
        """메모리 캐시 인스턴스"""
        from app.services.judgment_cache import JudgmentCache

        with patch("app.services.judgment_cache.settings") as mock_settings:
            mock_settings.redis_url = None
            return JudgmentCache(use_redis=False)

    @pytest.mark.asyncio
    async def test_invalidate_by_ruleset(self, cache):
        """특정 ruleset 캐시 무효화"""
        tenant_id = uuid4()
        ruleset_id1 = uuid4()
        ruleset_id2 = uuid4()

        # 두 ruleset에 캐시 저장
        await cache.set(tenant_id, ruleset_id1, {"k": 1}, {"r": 1}, 0.9)
        await cache.set(tenant_id, ruleset_id2, {"k": 2}, {"r": 2}, 0.9)

        # ruleset1만 무효화
        count = await cache.invalidate(tenant_id, ruleset_id1)

        assert count == 1

        # ruleset1 캐시 미스
        assert await cache.get(tenant_id, ruleset_id1, {"k": 1}) is None

        # ruleset2 캐시 히트
        assert await cache.get(tenant_id, ruleset_id2, {"k": 2}) is not None

    @pytest.mark.asyncio
    async def test_invalidate_all_tenant(self, cache):
        """테넌트 전체 캐시 무효화"""
        tenant_id = uuid4()
        ruleset_id1 = uuid4()
        ruleset_id2 = uuid4()

        await cache.set(tenant_id, ruleset_id1, {"k": 1}, {"r": 1}, 0.9)
        await cache.set(tenant_id, ruleset_id2, {"k": 2}, {"r": 2}, 0.9)

        # 테넌트 전체 무효화
        count = await cache.invalidate(tenant_id)

        assert count == 2


# ========== get_stats 테스트 ==========


class TestGetStats:
    """get_stats 메서드 테스트"""

    @pytest.fixture
    def cache(self):
        """메모리 캐시 인스턴스"""
        from app.services.judgment_cache import JudgmentCache

        with patch("app.services.judgment_cache.settings") as mock_settings:
            mock_settings.redis_url = None
            return JudgmentCache(use_redis=False)

    @pytest.mark.asyncio
    async def test_stats_empty(self, cache):
        """빈 캐시 통계"""
        stats = await cache.get_stats()

        assert stats["backend"] == "memory"
        assert stats["total_entries"] == 0
        assert stats["total_hits"] == 0
        assert stats["default_ttl"] == 300

    @pytest.mark.asyncio
    async def test_stats_with_entries(self, cache):
        """캐시 있을 때 통계"""
        tenant_id = uuid4()
        ruleset_id = uuid4()

        await cache.set(tenant_id, ruleset_id, {"k": 1}, {"r": 1}, 0.9)
        await cache.set(tenant_id, ruleset_id, {"k": 2}, {"r": 2}, 0.9)

        # 히트 발생
        await cache.get(tenant_id, ruleset_id, {"k": 1})

        stats = await cache.get_stats()

        assert stats["backend"] == "memory"
        assert stats["total_entries"] == 2
        assert stats["total_hits"] >= 1


# ========== 싱글톤 함수 테스트 ==========


class TestSingletonFunctions:
    """싱글톤 함수 테스트"""

    def test_get_judgment_cache(self):
        """get_judgment_cache 함수"""
        from app.services.judgment_cache import get_judgment_cache, reset_judgment_cache

        reset_judgment_cache()  # 초기화
        cache1 = get_judgment_cache()
        cache2 = get_judgment_cache()

        assert cache1 is cache2

    def test_reset_judgment_cache(self):
        """reset_judgment_cache 함수"""
        from app.services.judgment_cache import get_judgment_cache, reset_judgment_cache

        cache1 = get_judgment_cache()
        reset_judgment_cache()
        cache2 = get_judgment_cache()

        assert cache1 is not cache2
