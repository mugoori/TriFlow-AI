"""
Cache Service 테스트
Redis 캐싱 유틸리티 테스트
"""
import pytest
from unittest.mock import patch, MagicMock
import json

from app.services.cache_service import (
    CacheService,
    CacheKeys,
    cached,
    cached_async,
    invalidate_sensor_cache,
    invalidate_workflow_cache,
    invalidate_ruleset_cache,
)


class TestCacheService:
    """CacheService 테스트"""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis 클라이언트"""
        with patch.object(CacheService, '_client', None):
            with patch.object(CacheService, '_pool', None):
                mock_client = MagicMock()
                mock_client.ping.return_value = True
                mock_client.get.return_value = None
                mock_client.setex.return_value = True
                mock_client.delete.return_value = 1
                mock_client.scan_iter.return_value = []

                with patch.object(CacheService, 'get_client', return_value=mock_client):
                    yield mock_client

    def test_generate_key_simple(self):
        """간단한 키 생성"""
        key = CacheService.generate_key("users", "123")
        assert key == "users:123"

    def test_generate_key_with_kwargs(self):
        """kwargs가 포함된 키 생성"""
        key = CacheService.generate_key("users", tenant_id="abc", role="admin")
        assert "users" in key
        assert "tenant_id=abc" in key
        assert "role=admin" in key

    def test_generate_key_long_input(self):
        """긴 입력값 키 생성 (해시 사용)"""
        long_value = "x" * 300
        key = CacheService.generate_key("data", long_value)
        # 긴 키는 해시로 변환됨
        assert len(key) < 200
        assert key.startswith("data:")

    def test_get_cache_miss(self, mock_redis):
        """캐시 미스"""
        mock_redis.get.return_value = None
        result = CacheService.get("test:key")
        assert result is None
        mock_redis.get.assert_called_once_with("test:key")

    def test_get_cache_hit(self, mock_redis):
        """캐시 히트"""
        mock_redis.get.return_value = json.dumps({"data": "test"})
        result = CacheService.get("test:key")
        assert result == {"data": "test"}

    def test_get_invalid_json(self, mock_redis):
        """잘못된 JSON 데이터"""
        mock_redis.get.return_value = "not-valid-json"
        result = CacheService.get("test:key")
        assert result is None

    def test_set_cache(self, mock_redis):
        """캐시 저장"""
        result = CacheService.set("test:key", {"data": "test"}, ttl=60)
        assert result is True
        mock_redis.setex.assert_called_once()

    def test_set_with_default_ttl(self, mock_redis):
        """기본 TTL로 캐시 저장"""
        CacheService.set("test:key", "value")
        args = mock_redis.setex.call_args
        assert args[0][1] == CacheService.DEFAULT_TTL

    def test_delete_cache(self, mock_redis):
        """캐시 삭제"""
        result = CacheService.delete("test:key")
        assert result is True
        mock_redis.delete.assert_called_once_with("test:key")

    def test_delete_pattern(self, mock_redis):
        """패턴 캐시 삭제"""
        mock_redis.scan_iter.return_value = ["key1", "key2", "key3"]
        mock_redis.delete.return_value = 3

        result = CacheService.delete_pattern("test:*")
        assert result == 3

    def test_delete_pattern_no_keys(self, mock_redis):
        """패턴에 맞는 키 없음"""
        mock_redis.scan_iter.return_value = []
        result = CacheService.delete_pattern("test:*")
        assert result == 0

    def test_is_available_true(self, mock_redis):
        """Redis 사용 가능"""
        mock_redis.ping.return_value = True
        assert CacheService.is_available() is True

    def test_is_available_false(self):
        """Redis 사용 불가"""
        with patch.object(CacheService, 'get_client', return_value=None):
            assert CacheService.is_available() is False

    def test_get_or_set_cache_hit(self, mock_redis):
        """get_or_set - 캐시 히트"""
        mock_redis.get.return_value = json.dumps("cached_value")

        factory_called = False
        def factory():
            nonlocal factory_called
            factory_called = True
            return "new_value"

        result = CacheService.get_or_set("test:key", factory)
        assert result == "cached_value"
        assert factory_called is False

    def test_get_or_set_cache_miss(self, mock_redis):
        """get_or_set - 캐시 미스"""
        mock_redis.get.return_value = None

        def factory():
            return "new_value"

        result = CacheService.get_or_set("test:key", factory)
        assert result == "new_value"
        mock_redis.setex.assert_called_once()

    def test_increment(self, mock_redis):
        """카운터 증가"""
        mock_redis.incrby.return_value = 5
        result = CacheService.increment("counter:key", 1)
        assert result == 5

    def test_rate_limit_allowed(self, mock_redis):
        """Rate limit - 허용"""
        mock_redis.get.return_value = "5"  # 현재 5회 요청

        result = CacheService.rate_limit("user:123", max_requests=10, window_seconds=60)
        assert result is True  # 10회 미만이므로 허용

    def test_rate_limit_exceeded(self, mock_redis):
        """Rate limit - 초과"""
        mock_redis.get.return_value = "10"  # 현재 10회 요청

        result = CacheService.rate_limit("user:123", max_requests=10, window_seconds=60)
        assert result is False  # 10회 이상이므로 거부

    def test_rate_limit_new_window(self, mock_redis):
        """Rate limit - 새 윈도우"""
        mock_redis.get.return_value = None  # 기존 기록 없음

        result = CacheService.rate_limit("user:123", max_requests=10, window_seconds=60)
        assert result is True
        mock_redis.setex.assert_called_once()


class TestCacheKeys:
    """캐시 키 프리픽스 테스트"""

    def test_all_keys_defined(self):
        """모든 필수 키가 정의되어 있는지 확인"""
        required_keys = [
            "SENSOR_DATA",
            "WORKFLOW",
            "RULESET",
            "USER",
            "TENANT",
            "AGENT_RESULT",
            "STATS",
            "API_KEY",
            "RATE_LIMIT",
        ]
        for key in required_keys:
            assert hasattr(CacheKeys, key), f"Missing cache key: {key}"


class TestCachedDecorator:
    """cached 데코레이터 테스트"""

    @pytest.fixture
    def mock_cache(self):
        """캐시 모킹"""
        with patch.object(CacheService, 'get', return_value=None) as mock_get:
            with patch.object(CacheService, 'set', return_value=True) as mock_set:
                yield mock_get, mock_set

    def test_cached_decorator_miss(self, mock_cache):
        """캐시 미스 시 함수 실행"""
        mock_get, mock_set = mock_cache

        call_count = 0

        @cached("test", ttl=60)
        def test_func(arg1):
            nonlocal call_count
            call_count += 1
            return f"result:{arg1}"

        result = test_func("hello")

        assert result == "result:hello"
        assert call_count == 1
        mock_set.assert_called_once()

    def test_cached_decorator_hit(self):
        """캐시 히트 시 캐시된 값 반환"""
        with patch.object(CacheService, 'get', return_value="cached_result") as mock_get:
            with patch.object(CacheService, 'set') as mock_set:
                call_count = 0

                @cached("test", ttl=60)
                def test_func(arg1):
                    nonlocal call_count
                    call_count += 1
                    return f"result:{arg1}"

                result = test_func("hello")

                assert result == "cached_result"
                assert call_count == 0  # 함수 호출 안됨
                mock_set.assert_not_called()

    def test_cached_with_custom_key_builder(self, mock_cache):
        """커스텀 키 빌더 사용"""
        mock_get, mock_set = mock_cache

        @cached("test", key_builder=lambda x: f"custom:{x}")
        def test_func(x):
            return x * 2

        test_func("value")

        # 커스텀 키 사용 확인
        mock_get.assert_called_with("custom:value")


class TestCachedAsyncDecorator:
    """cached_async 데코레이터 테스트"""

    @pytest.mark.asyncio
    async def test_cached_async_miss(self):
        """비동기 캐시 미스"""
        with patch.object(CacheService, 'get', return_value=None):
            with patch.object(CacheService, 'set', return_value=True):
                call_count = 0

                @cached_async("test", ttl=60)
                async def async_func(arg1):
                    nonlocal call_count
                    call_count += 1
                    return f"result:{arg1}"

                result = await async_func("hello")

                assert result == "result:hello"
                assert call_count == 1

    @pytest.mark.asyncio
    async def test_cached_async_hit(self):
        """비동기 캐시 히트"""
        with patch.object(CacheService, 'get', return_value="cached_result"):
            call_count = 0

            @cached_async("test", ttl=60)
            async def async_func(arg1):
                nonlocal call_count
                call_count += 1
                return f"result:{arg1}"

            result = await async_func("hello")

            assert result == "cached_result"
            assert call_count == 0


class TestCacheInvalidation:
    """캐시 무효화 함수 테스트"""

    def test_invalidate_sensor_cache_with_tenant(self):
        """테넌트별 센서 캐시 무효화"""
        with patch.object(CacheService, 'delete_pattern') as mock_delete:
            invalidate_sensor_cache("tenant123")
            mock_delete.assert_called_once_with("sensor:tenant123:*")

    def test_invalidate_sensor_cache_all(self):
        """전체 센서 캐시 무효화"""
        with patch.object(CacheService, 'delete_pattern') as mock_delete:
            invalidate_sensor_cache()
            mock_delete.assert_called_once_with("sensor:*")

    def test_invalidate_workflow_cache_with_id(self):
        """워크플로우별 캐시 무효화"""
        with patch.object(CacheService, 'delete_pattern') as mock_delete:
            invalidate_workflow_cache("wf123")
            mock_delete.assert_called_once_with("workflow:wf123:*")

    def test_invalidate_workflow_cache_all(self):
        """전체 워크플로우 캐시 무효화"""
        with patch.object(CacheService, 'delete_pattern') as mock_delete:
            invalidate_workflow_cache()
            mock_delete.assert_called_once_with("workflow:*")

    def test_invalidate_ruleset_cache_with_id(self):
        """룰셋별 캐시 무효화"""
        with patch.object(CacheService, 'delete_pattern') as mock_delete:
            invalidate_ruleset_cache("rs123")
            mock_delete.assert_called_once_with("ruleset:rs123:*")

    def test_invalidate_ruleset_cache_all(self):
        """전체 룰셋 캐시 무효화"""
        with patch.object(CacheService, 'delete_pattern') as mock_delete:
            invalidate_ruleset_cache()
            mock_delete.assert_called_once_with("ruleset:*")


class TestCacheTTL:
    """TTL 상수 테스트"""

    def test_ttl_constants(self):
        """TTL 상수 확인"""
        assert CacheService.DEFAULT_TTL == 300  # 5분
        assert CacheService.SHORT_TTL == 60  # 1분
        assert CacheService.MEDIUM_TTL == 600  # 10분
        assert CacheService.LONG_TTL == 3600  # 1시간

    def test_ttl_ordering(self):
        """TTL 순서 확인"""
        assert CacheService.SHORT_TTL < CacheService.DEFAULT_TTL
        assert CacheService.DEFAULT_TTL < CacheService.MEDIUM_TTL
        assert CacheService.MEDIUM_TTL < CacheService.LONG_TTL


class TestCacheServiceNoRedis:
    """Redis 없을 때 동작 테스트"""

    def test_get_without_redis(self):
        """Redis 없을 때 get"""
        with patch.object(CacheService, 'get_client', return_value=None):
            result = CacheService.get("test:key")
            assert result is None

    def test_set_without_redis(self):
        """Redis 없을 때 set"""
        with patch.object(CacheService, 'get_client', return_value=None):
            result = CacheService.set("test:key", "value")
            assert result is False

    def test_delete_without_redis(self):
        """Redis 없을 때 delete"""
        with patch.object(CacheService, 'get_client', return_value=None):
            result = CacheService.delete("test:key")
            assert result is False

    def test_rate_limit_without_redis(self):
        """Redis 없을 때 rate limit (항상 허용)"""
        with patch.object(CacheService, 'get_client', return_value=None):
            result = CacheService.rate_limit("user:123", max_requests=1, window_seconds=60)
            assert result is True  # Redis 없으면 제한 없이 허용
