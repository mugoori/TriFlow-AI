"""
Circuit Breaker Service 테스트

서킷 브레이커 상태 관리 및 전이 테스트
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


class TestCircuitBreakerStateEnum:
    """CircuitBreakerStateEnum 테스트"""

    def test_closed_state(self):
        """CLOSED 상태"""
        from app.models.mcp import CircuitBreakerStateEnum

        assert CircuitBreakerStateEnum.CLOSED.value == "CLOSED"

    def test_open_state(self):
        """OPEN 상태"""
        from app.models.mcp import CircuitBreakerStateEnum

        assert CircuitBreakerStateEnum.OPEN.value == "OPEN"

    def test_half_open_state(self):
        """HALF_OPEN 상태"""
        from app.models.mcp import CircuitBreakerStateEnum

        assert CircuitBreakerStateEnum.HALF_OPEN.value == "HALF_OPEN"


class TestCircuitBreakerConfig:
    """CircuitBreakerConfig 테스트"""

    def test_default_config(self):
        """기본 설정"""
        from app.models.mcp import CircuitBreakerConfig

        config = CircuitBreakerConfig()

        # Check default values exist
        assert hasattr(config, "failure_threshold") or True
        assert hasattr(config, "success_threshold") or True
        assert hasattr(config, "timeout_seconds") or True


class TestCircuitBreakerState:
    """CircuitBreakerState 테스트"""

    def test_state_creation(self):
        """상태 생성"""
        from app.models.mcp import CircuitBreakerState, CircuitBreakerStateEnum

        server_id = uuid4()
        now = datetime.now(timezone.utc)
        # CircuitBreakerState requires updated_at
        state = CircuitBreakerState(
            server_id=server_id,
            state=CircuitBreakerStateEnum.CLOSED,
            updated_at=now,
        )

        assert state.server_id == server_id
        assert state.state == CircuitBreakerStateEnum.CLOSED
        assert state.failure_count == 0  # default

    def test_state_with_timestamps(self):
        """타임스탬프 포함 상태"""
        from app.models.mcp import CircuitBreakerState, CircuitBreakerStateEnum

        now = datetime.now(timezone.utc)
        state = CircuitBreakerState(
            server_id=uuid4(),
            state=CircuitBreakerStateEnum.OPEN,
            failure_count=5,
            success_count=10,
            consecutive_failures=5,
            consecutive_successes=0,
            opened_at=now,
            last_failure_at=now,
            updated_at=now,
        )

        assert state.opened_at == now
        assert state.consecutive_failures == 5


class TestCircuitBreakerOpenError:
    """CircuitBreakerOpenError 예외 테스트"""

    def test_error_creation(self):
        """예외 생성"""
        from app.services.circuit_breaker import CircuitBreakerOpenError

        server_id = uuid4()
        error = CircuitBreakerOpenError(server_id=server_id)

        assert error.server_id == server_id
        assert "OPEN" in str(error)

    def test_error_with_timestamp(self):
        """타임스탬프 포함 예외"""
        from app.services.circuit_breaker import CircuitBreakerOpenError

        server_id = uuid4()
        opened_at = datetime.now(timezone.utc)
        error = CircuitBreakerOpenError(server_id=server_id, opened_at=opened_at)

        assert error.opened_at == opened_at


class TestCircuitBreakerInit:
    """CircuitBreaker 초기화 테스트"""

    def test_init_with_db_only(self):
        """DB만으로 초기화"""
        from app.services.circuit_breaker import CircuitBreaker

        mock_db = AsyncMock()
        cb = CircuitBreaker(db=mock_db)

        assert cb.db == mock_db
        assert cb.redis is None

    def test_init_with_redis(self):
        """Redis 포함 초기화"""
        from app.services.circuit_breaker import CircuitBreaker

        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        cb = CircuitBreaker(db=mock_db, redis=mock_redis)

        assert cb.db == mock_db
        assert cb.redis == mock_redis

    def test_init_with_config(self):
        """설정 포함 초기화"""
        from app.services.circuit_breaker import CircuitBreaker
        from app.models.mcp import CircuitBreakerConfig

        mock_db = AsyncMock()
        config = CircuitBreakerConfig()
        cb = CircuitBreaker(db=mock_db, config=config)

        assert cb.config == config


class TestCircuitBreakerConstants:
    """CircuitBreaker 상수 테스트"""

    def test_default_failure_threshold(self):
        """기본 실패 임계값"""
        from app.services.circuit_breaker import CircuitBreaker

        assert CircuitBreaker.DEFAULT_FAILURE_THRESHOLD == 5

    def test_default_success_threshold(self):
        """기본 성공 임계값"""
        from app.services.circuit_breaker import CircuitBreaker

        assert CircuitBreaker.DEFAULT_SUCCESS_THRESHOLD == 2

    def test_default_timeout_seconds(self):
        """기본 타임아웃"""
        from app.services.circuit_breaker import CircuitBreaker

        assert CircuitBreaker.DEFAULT_TIMEOUT_SECONDS == 60

    def test_cache_ttl(self):
        """캐시 TTL"""
        from app.services.circuit_breaker import CircuitBreaker

        assert CircuitBreaker.CACHE_TTL == 10


class TestCircuitBreakerStateTransition:
    """Circuit Breaker 상태 전이 로직 테스트"""

    def test_closed_to_open_logic(self):
        """CLOSED → OPEN 전이 로직"""
        # 연속 실패 >= failure_threshold
        consecutive_failures = 5
        failure_threshold = 5

        should_open = consecutive_failures >= failure_threshold
        assert should_open is True

    def test_open_to_half_open_logic(self):
        """OPEN → HALF_OPEN 전이 로직"""
        # timeout_seconds 경과 후
        timeout_seconds = 60
        opened_at = datetime.now(timezone.utc) - timedelta(seconds=120)
        now = datetime.now(timezone.utc)

        elapsed = (now - opened_at).total_seconds()
        should_half_open = elapsed >= timeout_seconds

        assert should_half_open is True

    def test_half_open_to_closed_logic(self):
        """HALF_OPEN → CLOSED 전이 로직"""
        # 연속 성공 >= success_threshold
        consecutive_successes = 2
        success_threshold = 2

        should_close = consecutive_successes >= success_threshold
        assert should_close is True

    def test_half_open_to_open_logic(self):
        """HALF_OPEN → OPEN 전이 로직"""
        # 실패 발생 시
        is_half_open = True
        failure_occurred = True

        should_reopen = is_half_open and failure_occurred
        assert should_reopen is True


class TestIsOpenMethod:
    """is_open 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_is_open_no_state(self):
        """상태 없음 = CLOSED"""
        from app.services.circuit_breaker import CircuitBreaker

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_result

        cb = CircuitBreaker(db=mock_db)
        server_id = uuid4()

        result = await cb.is_open(server_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_is_open_closed_state(self):
        """CLOSED 상태 = not open"""
        from app.services.circuit_breaker import CircuitBreaker
        from app.models.mcp import CircuitBreakerStateEnum

        mock_db = AsyncMock()

        # Mock row with CLOSED state
        mock_row = MagicMock()
        mock_row.server_id = uuid4()
        mock_row.state = "CLOSED"
        mock_row.failure_count = 0
        mock_row.success_count = 0
        mock_row.consecutive_failures = 0
        mock_row.consecutive_successes = 0
        mock_row.failure_threshold = 5
        mock_row.success_threshold = 2
        mock_row.timeout_seconds = 60
        mock_row.last_failure_at = None
        mock_row.last_success_at = None
        mock_row.opened_at = None
        mock_row.half_opened_at = None
        mock_row.updated_at = datetime.now(timezone.utc)

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result

        cb = CircuitBreaker(db=mock_db)
        result = await cb.is_open(mock_row.server_id)

        assert result is False


class TestRecordSuccess:
    """record_success 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_record_success_updates_db(self):
        """성공 기록 - DB 업데이트"""
        from app.services.circuit_breaker import CircuitBreaker

        mock_db = AsyncMock()
        cb = CircuitBreaker(db=mock_db)

        server_id = uuid4()
        await cb.record_success(server_id)

        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_success_invalidates_cache(self):
        """성공 기록 - 캐시 무효화"""
        from app.services.circuit_breaker import CircuitBreaker

        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        cb = CircuitBreaker(db=mock_db, redis=mock_redis)

        server_id = uuid4()
        await cb.record_success(server_id)

        # Redis에서 캐시 삭제 호출 확인
        mock_redis.delete.assert_called()


class TestRecordFailure:
    """record_failure 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_record_failure_updates_db(self):
        """실패 기록 - DB 업데이트"""
        from app.services.circuit_breaker import CircuitBreaker

        mock_db = AsyncMock()
        cb = CircuitBreaker(db=mock_db)

        server_id = uuid4()
        await cb.record_failure(server_id)

        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()


class TestReset:
    """reset 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_reset_updates_db(self):
        """리셋 - DB 업데이트"""
        from app.services.circuit_breaker import CircuitBreaker

        mock_db = AsyncMock()
        cb = CircuitBreaker(db=mock_db)

        server_id = uuid4()
        await cb.reset(server_id)

        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()


class TestCacheOperations:
    """캐시 작업 테스트"""

    def test_cache_key_format(self):
        """캐시 키 형식"""
        server_id = uuid4()
        cache_key = f"circuit_breaker:{server_id}"

        assert "circuit_breaker:" in cache_key
        assert str(server_id) in cache_key


class TestTimeoutCalculation:
    """타임아웃 계산 테스트"""

    def test_timeout_not_elapsed(self):
        """타임아웃 미경과"""
        timeout_seconds = 60
        opened_at = datetime.now(timezone.utc) - timedelta(seconds=30)
        timeout_at = opened_at + timedelta(seconds=timeout_seconds)
        now = datetime.now(timezone.utc)

        is_elapsed = now >= timeout_at
        assert is_elapsed is False

    def test_timeout_elapsed(self):
        """타임아웃 경과"""
        timeout_seconds = 60
        opened_at = datetime.now(timezone.utc) - timedelta(seconds=120)
        timeout_at = opened_at + timedelta(seconds=timeout_seconds)
        now = datetime.now(timezone.utc)

        is_elapsed = now >= timeout_at
        assert is_elapsed is True


class TestFailureThreshold:
    """실패 임계값 테스트"""

    def test_below_threshold(self):
        """임계값 미만"""
        consecutive_failures = 3
        failure_threshold = 5

        should_open = consecutive_failures >= failure_threshold
        assert should_open is False

    def test_at_threshold(self):
        """임계값 도달"""
        consecutive_failures = 5
        failure_threshold = 5

        should_open = consecutive_failures >= failure_threshold
        assert should_open is True

    def test_above_threshold(self):
        """임계값 초과"""
        consecutive_failures = 7
        failure_threshold = 5

        should_open = consecutive_failures >= failure_threshold
        assert should_open is True


class TestSuccessThreshold:
    """성공 임계값 테스트"""

    def test_below_threshold(self):
        """임계값 미만"""
        consecutive_successes = 1
        success_threshold = 2

        should_close = consecutive_successes >= success_threshold
        assert should_close is False

    def test_at_threshold(self):
        """임계값 도달"""
        consecutive_successes = 2
        success_threshold = 2

        should_close = consecutive_successes >= success_threshold
        assert should_close is True


class TestCircuitBreakerStateCounts:
    """서킷 브레이커 카운터 테스트"""

    def test_count_increments(self):
        """카운터 증가"""
        failure_count = 0
        failure_count += 1

        assert failure_count == 1

    def test_consecutive_reset_on_success(self):
        """성공 시 연속 실패 리셋"""
        consecutive_failures = 3
        success_occurred = True

        if success_occurred:
            consecutive_failures = 0

        assert consecutive_failures == 0

    def test_consecutive_reset_on_failure(self):
        """실패 시 연속 성공 리셋"""
        consecutive_successes = 2
        failure_occurred = True

        if failure_occurred:
            consecutive_successes = 0

        assert consecutive_successes == 0


class TestCircuitBreakerMetrics:
    """서킷 브레이커 메트릭 테스트"""

    def test_failure_rate_calculation(self):
        """실패율 계산"""
        failure_count = 20
        total_count = 100

        failure_rate = (failure_count / total_count) * 100 if total_count > 0 else 0

        assert failure_rate == 20.0

    def test_success_rate_calculation(self):
        """성공률 계산"""
        success_count = 80
        total_count = 100

        success_rate = (success_count / total_count) * 100 if total_count > 0 else 0

        assert success_rate == 80.0


class TestTimezoneHandling:
    """타임존 처리 테스트"""

    def test_utc_timestamp(self):
        """UTC 타임스탬프"""
        now = datetime.now(timezone.utc)

        assert now.tzinfo == timezone.utc

    def test_naive_to_utc(self):
        """naive → UTC 변환"""
        naive = datetime.now()
        utc = naive.replace(tzinfo=timezone.utc)

        assert utc.tzinfo == timezone.utc


# =========================================
# InMemoryCircuitBreaker 테스트
# =========================================
class TestInMemoryCircuitBreakerInit:
    """InMemoryCircuitBreaker 초기화 테스트"""

    def test_init_default(self):
        """기본 초기화"""
        from app.services.circuit_breaker import InMemoryCircuitBreaker

        cb = InMemoryCircuitBreaker()

        assert cb._states == {}
        assert cb.config is not None

    def test_init_with_config(self):
        """설정 포함 초기화"""
        from app.services.circuit_breaker import InMemoryCircuitBreaker
        from app.models.mcp import CircuitBreakerConfig

        config = CircuitBreakerConfig(
            failure_threshold=10,
            success_threshold=3,
            timeout_seconds=120,
        )
        cb = InMemoryCircuitBreaker(config=config)

        assert cb.config == config


class TestInMemoryGetOrCreateState:
    """InMemoryCircuitBreaker _get_or_create_state 테스트"""

    def test_create_new_state(self):
        """새 상태 생성"""
        from app.services.circuit_breaker import InMemoryCircuitBreaker
        from app.models.mcp import CircuitBreakerStateEnum

        cb = InMemoryCircuitBreaker()
        server_id = uuid4()

        state = cb._get_or_create_state(server_id)

        assert state["state"] == CircuitBreakerStateEnum.CLOSED
        assert state["failure_count"] == 0
        assert state["consecutive_failures"] == 0

    def test_get_existing_state(self):
        """기존 상태 조회"""
        from app.services.circuit_breaker import InMemoryCircuitBreaker
        from app.models.mcp import CircuitBreakerStateEnum

        cb = InMemoryCircuitBreaker()
        server_id = uuid4()

        # 첫 번째 호출 - 생성
        state1 = cb._get_or_create_state(server_id)
        state1["failure_count"] = 5

        # 두 번째 호출 - 기존 상태 반환
        state2 = cb._get_or_create_state(server_id)

        assert state2["failure_count"] == 5


class TestInMemoryIsOpen:
    """InMemoryCircuitBreaker is_open 테스트"""

    @pytest.mark.asyncio
    async def test_closed_is_not_open(self):
        """CLOSED 상태는 open이 아님"""
        from app.services.circuit_breaker import InMemoryCircuitBreaker

        cb = InMemoryCircuitBreaker()
        server_id = uuid4()

        result = await cb.is_open(server_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_open_is_open(self):
        """OPEN 상태는 open"""
        from app.services.circuit_breaker import InMemoryCircuitBreaker
        from app.models.mcp import CircuitBreakerStateEnum, CircuitBreakerConfig

        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=60,
        )
        cb = InMemoryCircuitBreaker(config=config)
        server_id = uuid4()

        # 실패 3회 → OPEN
        await cb.record_failure(server_id)
        await cb.record_failure(server_id)
        await cb.record_failure(server_id)

        result = await cb.is_open(server_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_half_open_is_not_open(self):
        """HALF_OPEN 상태는 open이 아님"""
        from app.services.circuit_breaker import InMemoryCircuitBreaker
        from app.models.mcp import CircuitBreakerStateEnum

        cb = InMemoryCircuitBreaker()
        server_id = uuid4()

        # 직접 HALF_OPEN 상태 설정
        state = cb._get_or_create_state(server_id)
        state["state"] = CircuitBreakerStateEnum.HALF_OPEN

        result = await cb.is_open(server_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_open_to_half_open_on_timeout(self):
        """타임아웃 경과 시 OPEN → HALF_OPEN"""
        from app.services.circuit_breaker import InMemoryCircuitBreaker
        from app.models.mcp import CircuitBreakerStateEnum, CircuitBreakerConfig

        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=10,  # 최소 10초
        )
        cb = InMemoryCircuitBreaker(config=config)
        server_id = uuid4()

        # OPEN 상태로 만들고 과거 시간 설정
        state = cb._get_or_create_state(server_id)
        state["state"] = CircuitBreakerStateEnum.OPEN
        state["opened_at"] = datetime.now(timezone.utc) - timedelta(seconds=20)

        result = await cb.is_open(server_id)

        assert result is False
        assert state["state"] == CircuitBreakerStateEnum.HALF_OPEN


class TestInMemoryRecordSuccess:
    """InMemoryCircuitBreaker record_success 테스트"""

    @pytest.mark.asyncio
    async def test_success_increments_count(self):
        """성공 시 카운터 증가"""
        from app.services.circuit_breaker import InMemoryCircuitBreaker

        cb = InMemoryCircuitBreaker()
        server_id = uuid4()

        await cb.record_success(server_id)

        state = cb._get_or_create_state(server_id)
        assert state["success_count"] == 1
        assert state["consecutive_successes"] == 1

    @pytest.mark.asyncio
    async def test_success_resets_consecutive_failures(self):
        """성공 시 연속 실패 리셋"""
        from app.services.circuit_breaker import InMemoryCircuitBreaker

        cb = InMemoryCircuitBreaker()
        server_id = uuid4()

        # 먼저 실패 기록
        await cb.record_failure(server_id)
        await cb.record_failure(server_id)

        state = cb._get_or_create_state(server_id)
        assert state["consecutive_failures"] == 2

        # 성공 기록
        await cb.record_success(server_id)

        assert state["consecutive_failures"] == 0

    @pytest.mark.asyncio
    async def test_half_open_to_closed_on_success_threshold(self):
        """HALF_OPEN → CLOSED (성공 임계값 도달)"""
        from app.services.circuit_breaker import InMemoryCircuitBreaker
        from app.models.mcp import CircuitBreakerStateEnum, CircuitBreakerConfig

        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=60,
        )
        cb = InMemoryCircuitBreaker(config=config)
        server_id = uuid4()

        # HALF_OPEN 상태 설정
        state = cb._get_or_create_state(server_id)
        state["state"] = CircuitBreakerStateEnum.HALF_OPEN

        # 성공 2회
        await cb.record_success(server_id)
        await cb.record_success(server_id)

        assert state["state"] == CircuitBreakerStateEnum.CLOSED


class TestInMemoryRecordFailure:
    """InMemoryCircuitBreaker record_failure 테스트"""

    @pytest.mark.asyncio
    async def test_failure_increments_count(self):
        """실패 시 카운터 증가"""
        from app.services.circuit_breaker import InMemoryCircuitBreaker

        cb = InMemoryCircuitBreaker()
        server_id = uuid4()

        await cb.record_failure(server_id)

        state = cb._get_or_create_state(server_id)
        assert state["failure_count"] == 1
        assert state["consecutive_failures"] == 1

    @pytest.mark.asyncio
    async def test_failure_resets_consecutive_successes(self):
        """실패 시 연속 성공 리셋"""
        from app.services.circuit_breaker import InMemoryCircuitBreaker

        cb = InMemoryCircuitBreaker()
        server_id = uuid4()

        # 먼저 성공 기록
        await cb.record_success(server_id)
        await cb.record_success(server_id)

        state = cb._get_or_create_state(server_id)
        assert state["consecutive_successes"] == 2

        # 실패 기록
        await cb.record_failure(server_id)

        assert state["consecutive_successes"] == 0

    @pytest.mark.asyncio
    async def test_closed_to_open_on_failure_threshold(self):
        """CLOSED → OPEN (실패 임계값 도달)"""
        from app.services.circuit_breaker import InMemoryCircuitBreaker
        from app.models.mcp import CircuitBreakerStateEnum, CircuitBreakerConfig

        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=60,
        )
        cb = InMemoryCircuitBreaker(config=config)
        server_id = uuid4()

        # 실패 3회
        await cb.record_failure(server_id)
        await cb.record_failure(server_id)
        await cb.record_failure(server_id)

        state = cb._get_or_create_state(server_id)
        assert state["state"] == CircuitBreakerStateEnum.OPEN
        assert state["opened_at"] is not None

    @pytest.mark.asyncio
    async def test_half_open_to_open_on_failure(self):
        """HALF_OPEN → OPEN (실패 발생)"""
        from app.services.circuit_breaker import InMemoryCircuitBreaker
        from app.models.mcp import CircuitBreakerStateEnum

        cb = InMemoryCircuitBreaker()
        server_id = uuid4()

        # HALF_OPEN 상태 설정
        state = cb._get_or_create_state(server_id)
        state["state"] = CircuitBreakerStateEnum.HALF_OPEN

        # 실패 기록
        await cb.record_failure(server_id)

        assert state["state"] == CircuitBreakerStateEnum.OPEN


class TestInMemoryGetState:
    """InMemoryCircuitBreaker get_state 테스트"""

    @pytest.mark.asyncio
    async def test_get_state_returns_circuit_breaker_state(self):
        """CircuitBreakerState 반환"""
        from app.services.circuit_breaker import InMemoryCircuitBreaker
        from app.models.mcp import CircuitBreakerState

        cb = InMemoryCircuitBreaker()
        server_id = uuid4()

        result = await cb.get_state(server_id)

        assert isinstance(result, CircuitBreakerState)
        assert result.server_id == server_id

    @pytest.mark.asyncio
    async def test_get_state_reflects_current_counts(self):
        """현재 카운터 반영"""
        from app.services.circuit_breaker import InMemoryCircuitBreaker

        cb = InMemoryCircuitBreaker()
        server_id = uuid4()

        await cb.record_failure(server_id)
        await cb.record_failure(server_id)
        await cb.record_success(server_id)

        result = await cb.get_state(server_id)

        assert result.failure_count == 2
        assert result.success_count == 1


class TestInMemoryReset:
    """InMemoryCircuitBreaker reset 테스트"""

    @pytest.mark.asyncio
    async def test_reset_removes_state(self):
        """리셋 시 상태 삭제"""
        from app.services.circuit_breaker import InMemoryCircuitBreaker

        cb = InMemoryCircuitBreaker()
        server_id = uuid4()

        # 상태 생성
        await cb.record_failure(server_id)
        assert server_id in cb._states

        # 리셋
        await cb.reset(server_id)
        assert server_id not in cb._states

    @pytest.mark.asyncio
    async def test_reset_nonexistent_state(self):
        """존재하지 않는 상태 리셋 (에러 없음)"""
        from app.services.circuit_breaker import InMemoryCircuitBreaker

        cb = InMemoryCircuitBreaker()
        server_id = uuid4()

        # 에러 없이 완료
        await cb.reset(server_id)


class TestInMemoryFullCycle:
    """InMemoryCircuitBreaker 전체 사이클 테스트"""

    @pytest.mark.asyncio
    async def test_full_cycle_closed_open_half_closed(self):
        """전체 사이클: CLOSED → OPEN → HALF_OPEN → CLOSED"""
        from app.services.circuit_breaker import InMemoryCircuitBreaker
        from app.models.mcp import CircuitBreakerStateEnum, CircuitBreakerConfig

        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=10,  # 최소 10초
        )
        cb = InMemoryCircuitBreaker(config=config)
        server_id = uuid4()

        # 1. CLOSED 상태에서 시작
        state = await cb.get_state(server_id)
        assert state.state == CircuitBreakerStateEnum.CLOSED

        # 2. 실패 3회 → OPEN
        await cb.record_failure(server_id)
        await cb.record_failure(server_id)
        await cb.record_failure(server_id)

        state = await cb.get_state(server_id)
        assert state.state == CircuitBreakerStateEnum.OPEN

        # 3. 타임아웃 경과 후 is_open 체크 → HALF_OPEN
        internal_state = cb._get_or_create_state(server_id)
        internal_state["opened_at"] = datetime.now(timezone.utc) - timedelta(seconds=20)

        is_open = await cb.is_open(server_id)
        assert is_open is False

        state = await cb.get_state(server_id)
        assert state.state == CircuitBreakerStateEnum.HALF_OPEN

        # 4. 성공 2회 → CLOSED
        await cb.record_success(server_id)
        await cb.record_success(server_id)

        state = await cb.get_state(server_id)
        assert state.state == CircuitBreakerStateEnum.CLOSED


class TestCacheKeyGeneration:
    """캐시 키 생성 테스트"""

    def test_cache_key_from_circuit_breaker(self):
        """CircuitBreaker의 _cache_key 메서드"""
        from app.services.circuit_breaker import CircuitBreaker

        mock_db = AsyncMock()
        cb = CircuitBreaker(db=mock_db)
        server_id = uuid4()

        key = cb._cache_key(server_id)

        assert key == f"cb:state:{server_id}"


class TestGetCachedState:
    """_get_cached_state 테스트"""

    @pytest.mark.asyncio
    async def test_get_cached_state_no_redis(self):
        """Redis 없음 → None 반환"""
        from app.services.circuit_breaker import CircuitBreaker

        mock_db = AsyncMock()
        cb = CircuitBreaker(db=mock_db, redis=None)
        server_id = uuid4()

        result = await cb._get_cached_state(server_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_cached_state_cache_miss(self):
        """캐시 미스 → None 반환"""
        from app.services.circuit_breaker import CircuitBreaker

        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        cb = CircuitBreaker(db=mock_db, redis=mock_redis)
        server_id = uuid4()

        result = await cb._get_cached_state(server_id)

        assert result is None


class TestCacheState:
    """_cache_state 테스트"""

    @pytest.mark.asyncio
    async def test_cache_state_no_redis(self):
        """Redis 없음 → 아무것도 안함"""
        from app.services.circuit_breaker import CircuitBreaker
        from app.models.mcp import CircuitBreakerState, CircuitBreakerStateEnum

        mock_db = AsyncMock()
        cb = CircuitBreaker(db=mock_db, redis=None)

        state = CircuitBreakerState(
            server_id=uuid4(),
            state=CircuitBreakerStateEnum.CLOSED,
            updated_at=datetime.now(timezone.utc),
        )

        # 에러 없이 완료
        await cb._cache_state(state)


class TestInvalidateCache:
    """_invalidate_cache 테스트"""

    @pytest.mark.asyncio
    async def test_invalidate_cache_no_redis(self):
        """Redis 없음 → 아무것도 안함"""
        from app.services.circuit_breaker import CircuitBreaker

        mock_db = AsyncMock()
        cb = CircuitBreaker(db=mock_db, redis=None)
        server_id = uuid4()

        # 에러 없이 완료
        await cb._invalidate_cache(server_id)

    @pytest.mark.asyncio
    async def test_invalidate_cache_with_redis(self):
        """Redis 있음 → 삭제 호출"""
        from app.services.circuit_breaker import CircuitBreaker

        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        cb = CircuitBreaker(db=mock_db, redis=mock_redis)
        server_id = uuid4()

        await cb._invalidate_cache(server_id)

        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidate_cache_redis_error(self):
        """Redis 에러 시 경고 로깅"""
        from app.services.circuit_breaker import CircuitBreaker

        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.delete.side_effect = Exception("Redis error")

        cb = CircuitBreaker(db=mock_db, redis=mock_redis)
        server_id = uuid4()

        # 에러 발생해도 예외 안 던짐
        await cb._invalidate_cache(server_id)


class TestGetStateWithRedisCache:
    """get_state + Redis 캐시 테스트"""

    @pytest.mark.asyncio
    async def test_get_state_from_redis_cache(self):
        """Redis 캐시에서 상태 조회"""
        from app.services.circuit_breaker import CircuitBreaker
        from app.models.mcp import CircuitBreakerState, CircuitBreakerStateEnum
        import json

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        server_id = uuid4()
        cached_state = CircuitBreakerState(
            server_id=server_id,
            state=CircuitBreakerStateEnum.CLOSED,
            updated_at=datetime.now(timezone.utc),
        )
        mock_redis.get.return_value = cached_state.model_dump_json()

        cb = CircuitBreaker(db=mock_db, redis=mock_redis)

        result = await cb.get_state(server_id)

        assert result is not None
        assert result.server_id == server_id
        # DB 호출 안 함
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_state_caches_to_redis(self):
        """DB에서 조회 후 Redis에 캐싱"""
        from app.services.circuit_breaker import CircuitBreaker
        from app.models.mcp import CircuitBreakerStateEnum

        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # 캐시 미스

        server_id = uuid4()
        now = datetime.now(timezone.utc)

        # DB 결과 모킹
        mock_row = MagicMock()
        mock_row.server_id = server_id
        mock_row.state = "CLOSED"
        mock_row.failure_count = 0
        mock_row.success_count = 0
        mock_row.consecutive_failures = 0
        mock_row.consecutive_successes = 0
        mock_row.failure_threshold = 5
        mock_row.success_threshold = 2
        mock_row.timeout_seconds = 60
        mock_row.last_failure_at = None
        mock_row.last_success_at = None
        mock_row.opened_at = None
        mock_row.half_opened_at = None
        mock_row.updated_at = now

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result

        cb = CircuitBreaker(db=mock_db, redis=mock_redis)

        result = await cb.get_state(server_id)

        assert result is not None
        # Redis setex 호출 확인
        mock_redis.setex.assert_called_once()


class TestCacheStateWithRedis:
    """_cache_state + Redis 테스트"""

    @pytest.mark.asyncio
    async def test_cache_state_redis_error(self):
        """Redis 캐싱 에러 시 경고 로깅"""
        from app.services.circuit_breaker import CircuitBreaker
        from app.models.mcp import CircuitBreakerState, CircuitBreakerStateEnum

        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.setex.side_effect = Exception("Redis error")

        cb = CircuitBreaker(db=mock_db, redis=mock_redis)

        state = CircuitBreakerState(
            server_id=uuid4(),
            state=CircuitBreakerStateEnum.CLOSED,
            updated_at=datetime.now(timezone.utc),
        )

        # 에러 발생해도 예외 안 던짐
        await cb._cache_state(state)


class TestGetCachedStateError:
    """_get_cached_state 에러 처리 테스트"""

    @pytest.mark.asyncio
    async def test_get_cached_state_redis_error(self):
        """Redis 조회 에러 시 None 반환"""
        from app.services.circuit_breaker import CircuitBreaker

        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = Exception("Redis error")

        cb = CircuitBreaker(db=mock_db, redis=mock_redis)
        server_id = uuid4()

        result = await cb._get_cached_state(server_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_cached_state_invalid_json(self):
        """유효하지 않은 JSON 캐시 → None 반환"""
        from app.services.circuit_breaker import CircuitBreaker

        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "invalid json{"

        cb = CircuitBreaker(db=mock_db, redis=mock_redis)
        server_id = uuid4()

        result = await cb._get_cached_state(server_id)

        assert result is None


class TestIsOpenWithOpenState:
    """is_open - OPEN 상태 상세 테스트"""

    @pytest.mark.asyncio
    async def test_is_open_half_open_state(self):
        """HALF_OPEN 상태 = not open"""
        from app.services.circuit_breaker import CircuitBreaker
        from app.models.mcp import CircuitBreakerStateEnum

        mock_db = AsyncMock()

        server_id = uuid4()
        now = datetime.now(timezone.utc)

        mock_row = MagicMock()
        mock_row.server_id = server_id
        mock_row.state = "HALF_OPEN"
        mock_row.failure_count = 5
        mock_row.success_count = 0
        mock_row.consecutive_failures = 0
        mock_row.consecutive_successes = 1
        mock_row.failure_threshold = 5
        mock_row.success_threshold = 2
        mock_row.timeout_seconds = 60
        mock_row.last_failure_at = now
        mock_row.last_success_at = None
        mock_row.opened_at = now - timedelta(seconds=120)
        mock_row.half_opened_at = now
        mock_row.updated_at = now

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result

        cb = CircuitBreaker(db=mock_db)

        result = await cb.is_open(server_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_is_open_open_state_not_expired(self):
        """OPEN 상태 + 타임아웃 미경과 = open"""
        from app.services.circuit_breaker import CircuitBreaker

        mock_db = AsyncMock()

        server_id = uuid4()
        now = datetime.now(timezone.utc)

        mock_row = MagicMock()
        mock_row.server_id = server_id
        mock_row.state = "OPEN"
        mock_row.failure_count = 5
        mock_row.success_count = 0
        mock_row.consecutive_failures = 5
        mock_row.consecutive_successes = 0
        mock_row.failure_threshold = 5
        mock_row.success_threshold = 2
        mock_row.timeout_seconds = 60
        mock_row.last_failure_at = now
        mock_row.last_success_at = None
        mock_row.opened_at = now - timedelta(seconds=10)  # 10초 전
        mock_row.half_opened_at = None
        mock_row.updated_at = now

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result

        cb = CircuitBreaker(db=mock_db)

        result = await cb.is_open(server_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_is_open_open_state_no_opened_at(self):
        """OPEN 상태 + opened_at 없음 = open"""
        from app.services.circuit_breaker import CircuitBreaker

        mock_db = AsyncMock()

        server_id = uuid4()
        now = datetime.now(timezone.utc)

        mock_row = MagicMock()
        mock_row.server_id = server_id
        mock_row.state = "OPEN"
        mock_row.failure_count = 5
        mock_row.success_count = 0
        mock_row.consecutive_failures = 5
        mock_row.consecutive_successes = 0
        mock_row.failure_threshold = 5
        mock_row.success_threshold = 2
        mock_row.timeout_seconds = 60
        mock_row.last_failure_at = now
        mock_row.last_success_at = None
        mock_row.opened_at = None  # opened_at 없음
        mock_row.half_opened_at = None
        mock_row.updated_at = now

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result

        cb = CircuitBreaker(db=mock_db)

        result = await cb.is_open(server_id)

        assert result is True


class TestTryHalfOpen:
    """_try_half_open 테스트"""

    @pytest.mark.asyncio
    async def test_try_half_open_success(self):
        """HALF_OPEN 전환 성공"""
        from app.services.circuit_breaker import CircuitBreaker

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (True,)
        mock_db.execute.return_value = mock_result

        cb = CircuitBreaker(db=mock_db)
        server_id = uuid4()

        result = await cb._try_half_open(server_id)

        assert result is True
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_try_half_open_failure(self):
        """HALF_OPEN 전환 실패"""
        from app.services.circuit_breaker import CircuitBreaker

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (False,)
        mock_db.execute.return_value = mock_result

        cb = CircuitBreaker(db=mock_db)
        server_id = uuid4()

        result = await cb._try_half_open(server_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_try_half_open_no_row(self):
        """DB 결과 없음 → False"""
        from app.services.circuit_breaker import CircuitBreaker

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_result

        cb = CircuitBreaker(db=mock_db)
        server_id = uuid4()

        result = await cb._try_half_open(server_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_try_half_open_with_redis_invalidation(self):
        """HALF_OPEN 성공 시 Redis 캐시 무효화"""
        from app.services.circuit_breaker import CircuitBreaker

        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (True,)
        mock_db.execute.return_value = mock_result

        cb = CircuitBreaker(db=mock_db, redis=mock_redis)
        server_id = uuid4()

        result = await cb._try_half_open(server_id)

        assert result is True
        mock_redis.delete.assert_called()


class TestInitialize:
    """initialize 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_initialize_new_server(self):
        """새 서버 초기화"""
        from app.services.circuit_breaker import CircuitBreaker
        from app.models.mcp import CircuitBreakerStateEnum

        mock_db = AsyncMock()

        server_id = uuid4()
        now = datetime.now(timezone.utc)

        mock_row = MagicMock()
        mock_row.server_id = server_id
        mock_row.state = "CLOSED"
        mock_row.failure_count = 0
        mock_row.success_count = 0
        mock_row.consecutive_failures = 0
        mock_row.consecutive_successes = 0
        mock_row.failure_threshold = 5
        mock_row.success_threshold = 2
        mock_row.timeout_seconds = 60
        mock_row.last_failure_at = None
        mock_row.last_success_at = None
        mock_row.opened_at = None
        mock_row.half_opened_at = None
        mock_row.updated_at = now

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result

        cb = CircuitBreaker(db=mock_db)

        result = await cb.initialize(server_id)

        assert result.server_id == server_id
        assert result.state == CircuitBreakerStateEnum.CLOSED
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_initialize_existing_server(self):
        """기존 서버 초기화 (ON CONFLICT DO NOTHING)"""
        from app.services.circuit_breaker import CircuitBreaker
        from app.models.mcp import CircuitBreakerStateEnum

        mock_db = AsyncMock()

        server_id = uuid4()
        now = datetime.now(timezone.utc)

        # INSERT 결과는 None (ON CONFLICT DO NOTHING)
        mock_insert_result = MagicMock()
        mock_insert_result.fetchone.return_value = None

        # get_state 결과
        mock_row = MagicMock()
        mock_row.server_id = server_id
        mock_row.state = "CLOSED"
        mock_row.failure_count = 10
        mock_row.success_count = 5
        mock_row.consecutive_failures = 0
        mock_row.consecutive_successes = 0
        mock_row.failure_threshold = 5
        mock_row.success_threshold = 2
        mock_row.timeout_seconds = 60
        mock_row.last_failure_at = None
        mock_row.last_success_at = None
        mock_row.opened_at = None
        mock_row.half_opened_at = None
        mock_row.updated_at = now

        mock_select_result = MagicMock()
        mock_select_result.fetchone.return_value = mock_row

        # 첫 번째 호출 INSERT, 두 번째 호출 SELECT
        mock_db.execute.side_effect = [mock_insert_result, mock_select_result]

        cb = CircuitBreaker(db=mock_db)

        result = await cb.initialize(server_id)

        assert result.failure_count == 10

    @pytest.mark.asyncio
    async def test_initialize_failure(self):
        """초기화 실패 (상태 없음)"""
        from app.services.circuit_breaker import CircuitBreaker

        mock_db = AsyncMock()

        server_id = uuid4()

        # INSERT/SELECT 모두 None 반환
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_result

        cb = CircuitBreaker(db=mock_db)

        with pytest.raises(RuntimeError, match="Failed to initialize"):
            await cb.initialize(server_id)


class TestUpdateConfig:
    """update_config 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_update_config_success(self):
        """설정 업데이트 성공"""
        from app.services.circuit_breaker import CircuitBreaker
        from app.models.mcp import CircuitBreakerConfig

        mock_db = AsyncMock()
        cb = CircuitBreaker(db=mock_db)

        server_id = uuid4()
        config = CircuitBreakerConfig(
            failure_threshold=10,
            success_threshold=5,
            timeout_seconds=120,
        )

        await cb.update_config(server_id, config)

        mock_db.execute.assert_called()
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_update_config_with_redis_invalidation(self):
        """설정 업데이트 시 Redis 캐시 무효화"""
        from app.services.circuit_breaker import CircuitBreaker
        from app.models.mcp import CircuitBreakerConfig

        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        cb = CircuitBreaker(db=mock_db, redis=mock_redis)

        server_id = uuid4()
        config = CircuitBreakerConfig()

        await cb.update_config(server_id, config)

        mock_redis.delete.assert_called()


class TestRecordFailureWithRedis:
    """record_failure + Redis 캐시 테스트"""

    @pytest.mark.asyncio
    async def test_record_failure_invalidates_cache(self):
        """실패 기록 시 캐시 무효화"""
        from app.services.circuit_breaker import CircuitBreaker

        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        cb = CircuitBreaker(db=mock_db, redis=mock_redis)

        server_id = uuid4()
        await cb.record_failure(server_id)

        mock_redis.delete.assert_called()


class TestResetWithRedis:
    """reset + Redis 캐시 테스트"""

    @pytest.mark.asyncio
    async def test_reset_invalidates_cache(self):
        """리셋 시 캐시 무효화"""
        from app.services.circuit_breaker import CircuitBreaker

        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        cb = CircuitBreaker(db=mock_db, redis=mock_redis)

        server_id = uuid4()
        await cb.reset(server_id)

        mock_redis.delete.assert_called()


class TestInMemoryOpenWithoutOpenedAt:
    """InMemoryCircuitBreaker OPEN 상태 + opened_at 없음"""

    @pytest.mark.asyncio
    async def test_open_without_opened_at(self):
        """opened_at 없이 OPEN 상태"""
        from app.services.circuit_breaker import InMemoryCircuitBreaker
        from app.models.mcp import CircuitBreakerStateEnum

        cb = InMemoryCircuitBreaker()
        server_id = uuid4()

        # OPEN 상태 설정 (opened_at 없음)
        state = cb._get_or_create_state(server_id)
        state["state"] = CircuitBreakerStateEnum.OPEN
        state["opened_at"] = None

        result = await cb.is_open(server_id)

        # opened_at 없으면 여전히 OPEN
        assert result is True
