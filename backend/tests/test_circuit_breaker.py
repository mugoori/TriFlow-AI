"""
Circuit Breaker 유틸리티 테스트
스펙 참조: B-2-1, B-5

Circuit Breaker 패턴:
- CLOSED: 정상 상태, 모든 호출 허용
- OPEN: 차단 상태, 모든 호출 거부 (fallback 실행)
- HALF_OPEN: 복구 테스트 중, 일부 호출 허용
"""
import asyncio
import pytest

from app.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerStats,
    CircuitState,
    get_circuit_breaker,
    get_all_circuit_breakers,
    get_circuit_breaker_status,
    get_all_circuit_breaker_statuses,
    reset_circuit_breaker,
    reset_all_circuit_breakers,
    get_llm_circuit_breaker,
    get_mcp_circuit_breaker,
    get_external_api_circuit_breaker,
    _circuit_breakers,
)


class TestCircuitState:
    """CircuitState 열거형 테스트"""

    def test_circuit_state_values(self):
        """상태 값 확인"""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"

    def test_circuit_state_string_enum(self):
        """문자열 열거형 확인"""
        assert str(CircuitState.CLOSED) == "CircuitState.CLOSED"
        assert CircuitState.CLOSED == "closed"


class TestCircuitBreakerConfig:
    """CircuitBreakerConfig 테스트"""

    def test_default_config(self):
        """기본 설정 값"""
        config = CircuitBreakerConfig()

        assert config.failure_threshold == 5
        assert config.recovery_timeout == 30.0
        assert config.success_threshold == 2
        assert config.sliding_window_size == 60.0
        assert config.call_timeout == 30.0
        assert config.failure_exceptions == (Exception,)
        assert config.ignored_exceptions == ()

    def test_custom_config(self):
        """사용자 정의 설정"""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=60.0,
            success_threshold=1,
            sliding_window_size=120.0,
            call_timeout=10.0,
            failure_exceptions=(ValueError, RuntimeError),
            ignored_exceptions=(KeyError,),
        )

        assert config.failure_threshold == 3
        assert config.recovery_timeout == 60.0
        assert config.success_threshold == 1
        assert config.sliding_window_size == 120.0
        assert config.call_timeout == 10.0
        assert config.failure_exceptions == (ValueError, RuntimeError)
        assert config.ignored_exceptions == (KeyError,)


class TestCircuitBreakerStats:
    """CircuitBreakerStats 테스트"""

    def test_default_stats(self):
        """기본 통계 값"""
        stats = CircuitBreakerStats()

        assert stats.total_calls == 0
        assert stats.successful_calls == 0
        assert stats.failed_calls == 0
        assert stats.rejected_calls == 0
        assert stats.last_failure_time is None
        assert stats.last_success_time is None
        assert stats.state_changes == []

    def test_success_rate_zero_calls(self):
        """호출 없을 때 성공률"""
        stats = CircuitBreakerStats()

        assert stats.success_rate == 1.0

    def test_success_rate_with_calls(self):
        """호출 있을 때 성공률"""
        stats = CircuitBreakerStats(
            total_calls=10,
            successful_calls=8,
            failed_calls=2,
        )

        assert stats.success_rate == 0.8

    def test_to_dict(self):
        """딕셔너리 변환"""
        stats = CircuitBreakerStats(
            total_calls=100,
            successful_calls=90,
            failed_calls=10,
            rejected_calls=5,
        )

        data = stats.to_dict()

        assert data["total_calls"] == 100
        assert data["successful_calls"] == 90
        assert data["failed_calls"] == 10
        assert data["rejected_calls"] == 5
        assert data["success_rate"] == 0.9


class TestCircuitBreakerError:
    """CircuitBreakerError 테스트"""

    def test_error_message(self):
        """에러 메시지 형식"""
        error = CircuitBreakerError("test_circuit", 15.5)

        assert error.circuit_name == "test_circuit"
        assert error.remaining_time == 15.5
        assert "test_circuit" in str(error)
        assert "15.5" in str(error)
        assert "OPEN" in str(error)


class TestCircuitBreaker:
    """CircuitBreaker 클래스 테스트"""

    @pytest.fixture
    def circuit_breaker(self):
        """테스트용 Circuit Breaker"""
        return CircuitBreaker(
            name="test_cb",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=1.0,  # 빠른 테스트를 위해 짧은 시간
                success_threshold=2,
                call_timeout=5.0,
            ),
        )

    def test_initial_state(self, circuit_breaker):
        """초기 상태 확인"""
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.is_closed is True
        assert circuit_breaker.is_open is False
        assert circuit_breaker.is_half_open is False

    def test_name_and_config(self, circuit_breaker):
        """이름과 설정 확인"""
        assert circuit_breaker.name == "test_cb"
        assert circuit_breaker.config.failure_threshold == 3

    @pytest.mark.asyncio
    async def test_successful_call(self, circuit_breaker):
        """성공적인 호출"""
        async def success_func():
            return "success"

        result = await circuit_breaker.execute(success_func)

        assert result == "success"
        assert circuit_breaker.stats.successful_calls == 1
        assert circuit_breaker.stats.total_calls == 1
        assert circuit_breaker.is_closed is True

    @pytest.mark.asyncio
    async def test_failed_call(self, circuit_breaker):
        """실패한 호출"""
        async def fail_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            await circuit_breaker.execute(fail_func)

        assert circuit_breaker.stats.failed_calls == 1
        assert circuit_breaker.is_closed is True  # 아직 임계값 미도달

    @pytest.mark.asyncio
    async def test_open_circuit_after_threshold(self, circuit_breaker):
        """임계값 초과 후 OPEN 상태 전이"""
        async def fail_func():
            raise ValueError("Test error")

        # 3번 실패 (임계값)
        for _ in range(3):
            with pytest.raises(ValueError):
                await circuit_breaker.execute(fail_func)

        assert circuit_breaker.is_open is True
        assert circuit_breaker.stats.failed_calls == 3

    @pytest.mark.asyncio
    async def test_open_circuit_rejects_calls(self, circuit_breaker):
        """OPEN 상태에서 호출 거부"""
        async def fail_func():
            raise ValueError("Test error")

        # 3번 실패로 OPEN 상태로 전이
        for _ in range(3):
            with pytest.raises(ValueError):
                await circuit_breaker.execute(fail_func)

        # 추가 호출은 거부됨
        with pytest.raises(CircuitBreakerError) as exc_info:
            await circuit_breaker.execute(fail_func)

        assert "test_cb" in str(exc_info.value)
        assert circuit_breaker.stats.rejected_calls == 1

    @pytest.mark.asyncio
    async def test_fallback_on_open(self, circuit_breaker):
        """OPEN 상태에서 fallback 실행"""
        async def fail_func():
            raise ValueError("Test error")

        async def fallback_func(*args, **kwargs):
            return "fallback"

        # 3번 실패로 OPEN 상태로 전이 (fallback 없이)
        for _ in range(3):
            with pytest.raises(ValueError):
                await circuit_breaker.execute(fail_func)

        # 이제 fallback 설정
        circuit_breaker.fallback = fallback_func

        # fallback 실행
        result = await circuit_breaker.execute(fail_func)

        assert result == "fallback"
        assert circuit_breaker.stats.rejected_calls == 1

    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self, circuit_breaker):
        """타임아웃 후 HALF_OPEN 상태 전이"""
        async def fail_func():
            raise ValueError("Test error")

        # 3번 실패로 OPEN 상태
        for _ in range(3):
            with pytest.raises(ValueError):
                await circuit_breaker.execute(fail_func)

        assert circuit_breaker.is_open is True

        # recovery_timeout 대기
        await asyncio.sleep(1.1)

        # 상태 확인 시 자동 전이
        assert circuit_breaker.is_half_open is True

    @pytest.mark.asyncio
    async def test_half_open_to_closed_on_success(self, circuit_breaker):
        """HALF_OPEN에서 성공 시 CLOSED로 전이"""
        async def fail_func():
            raise ValueError("Test error")

        async def success_func():
            return "success"

        # OPEN 상태로 만들기
        for _ in range(3):
            with pytest.raises(ValueError):
                await circuit_breaker.execute(fail_func)

        # HALF_OPEN으로 전이 대기
        await asyncio.sleep(1.1)
        assert circuit_breaker.is_half_open is True

        # 2번 성공 (success_threshold = 2)
        await circuit_breaker.execute(success_func)
        assert circuit_breaker.is_half_open is True  # 아직 1번 성공

        await circuit_breaker.execute(success_func)
        assert circuit_breaker.is_closed is True  # 2번 성공 후 CLOSED

    @pytest.mark.asyncio
    async def test_half_open_to_open_on_failure(self, circuit_breaker):
        """HALF_OPEN에서 실패 시 즉시 OPEN으로 전이"""
        async def fail_func():
            raise ValueError("Test error")

        # OPEN 상태로 만들기
        for _ in range(3):
            with pytest.raises(ValueError):
                await circuit_breaker.execute(fail_func)

        # HALF_OPEN으로 전이 대기
        await asyncio.sleep(1.1)
        assert circuit_breaker.is_half_open is True

        # 실패 시 즉시 OPEN
        with pytest.raises(ValueError):
            await circuit_breaker.execute(fail_func)

        assert circuit_breaker.is_open is True

    @pytest.mark.asyncio
    async def test_protect_decorator(self, circuit_breaker):
        """protect 데코레이터 테스트"""
        @circuit_breaker.protect
        async def protected_func(value):
            return value * 2

        result = await protected_func(5)

        assert result == 10
        assert circuit_breaker.stats.successful_calls == 1

    @pytest.mark.asyncio
    async def test_context_manager_success(self, circuit_breaker):
        """컨텍스트 매니저 성공 케이스"""
        async with circuit_breaker:
            pass

        assert circuit_breaker.stats.successful_calls == 1

    @pytest.mark.asyncio
    async def test_context_manager_failure(self, circuit_breaker):
        """컨텍스트 매니저 실패 케이스"""
        with pytest.raises(ValueError):
            async with circuit_breaker:
                raise ValueError("Test error")

        assert circuit_breaker.stats.failed_calls == 1

    @pytest.mark.asyncio
    async def test_context_manager_open_state(self, circuit_breaker):
        """OPEN 상태에서 컨텍스트 매니저 진입 실패"""
        async def fail_func():
            raise ValueError("Test error")

        # OPEN 상태로 만들기
        for _ in range(3):
            with pytest.raises(ValueError):
                await circuit_breaker.execute(fail_func)

        # 컨텍스트 매니저 진입 시 에러
        with pytest.raises(CircuitBreakerError):
            async with circuit_breaker:
                pass

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """타임아웃 처리"""
        cb = CircuitBreaker(
            name="timeout_test",
            config=CircuitBreakerConfig(call_timeout=0.1),
        )

        async def slow_func():
            await asyncio.sleep(1.0)
            return "done"

        with pytest.raises(asyncio.TimeoutError):
            await cb.execute(slow_func)

        assert cb.stats.failed_calls == 1

    @pytest.mark.asyncio
    async def test_timeout_with_fallback(self):
        """타임아웃 시 fallback 실행"""
        async def fallback(*args, **kwargs):
            return "fallback_result"

        cb = CircuitBreaker(
            name="timeout_fallback_test",
            config=CircuitBreakerConfig(call_timeout=0.1),
            fallback=fallback,
        )

        async def slow_func():
            await asyncio.sleep(1.0)
            return "done"

        result = await cb.execute(slow_func)

        assert result == "fallback_result"
        assert cb.stats.failed_calls == 1

    @pytest.mark.asyncio
    async def test_sync_function_execution(self, circuit_breaker):
        """동기 함수 실행"""
        def sync_func():
            return "sync_result"

        result = await circuit_breaker.execute(sync_func)

        assert result == "sync_result"
        assert circuit_breaker.stats.successful_calls == 1

    @pytest.mark.asyncio
    async def test_ignored_exceptions(self):
        """무시할 예외 처리"""
        cb = CircuitBreaker(
            name="ignored_test",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                ignored_exceptions=(KeyError,),
            ),
        )

        async def func():
            raise KeyError("Ignored")

        with pytest.raises(KeyError):
            await cb.execute(func)

        # KeyError는 실패로 카운트하지 않음
        assert cb.stats.failed_calls == 0
        assert cb.is_closed is True

    def test_reset(self, circuit_breaker):
        """Circuit Breaker 리셋"""
        # 상태 변경
        circuit_breaker._state = CircuitState.OPEN
        circuit_breaker._failure_times = [1, 2, 3]

        circuit_breaker.reset()

        assert circuit_breaker.is_closed is True
        assert len(circuit_breaker._failure_times) == 0

    def test_get_status(self, circuit_breaker):
        """상태 조회"""
        status = circuit_breaker.get_status()

        assert status["name"] == "test_cb"
        assert status["state"] == "closed"
        assert status["is_open"] is False
        assert status["failure_count"] == 0
        assert "config" in status
        assert "stats" in status

    @pytest.mark.asyncio
    async def test_sliding_window(self):
        """슬라이딩 윈도우 테스트"""
        cb = CircuitBreaker(
            name="sliding_window_test",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                sliding_window_size=1.0,  # 1초 윈도우
            ),
        )

        async def fail_func():
            raise ValueError("Test")

        # 2번 실패
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.execute(fail_func)

        # 윈도우 만료 대기
        await asyncio.sleep(1.1)

        # 1번 더 실패해도 윈도우 내 실패는 1번뿐
        with pytest.raises(ValueError):
            await cb.execute(fail_func)

        # 아직 CLOSED (윈도우 내 실패 1번)
        assert cb.is_closed is True

    def test_state_change_logging(self, circuit_breaker):
        """상태 변경 로깅"""
        circuit_breaker._transition_to(CircuitState.OPEN)
        circuit_breaker._transition_to(CircuitState.HALF_OPEN)
        circuit_breaker._transition_to(CircuitState.CLOSED)

        assert len(circuit_breaker.stats.state_changes) == 3
        assert circuit_breaker.stats.state_changes[0]["from"] == "closed"
        assert circuit_breaker.stats.state_changes[0]["to"] == "open"


class TestCircuitBreakerRegistry:
    """Circuit Breaker 레지스트리 함수 테스트"""

    @pytest.fixture(autouse=True)
    def clear_registry(self):
        """각 테스트 전 레지스트리 초기화"""
        _circuit_breakers.clear()
        yield
        _circuit_breakers.clear()

    def test_get_circuit_breaker_creates_new(self):
        """새 Circuit Breaker 생성"""
        cb = get_circuit_breaker("new_cb")

        assert cb.name == "new_cb"
        assert "new_cb" in _circuit_breakers

    def test_get_circuit_breaker_returns_existing(self):
        """기존 Circuit Breaker 반환"""
        cb1 = get_circuit_breaker("existing_cb")
        cb2 = get_circuit_breaker("existing_cb")

        assert cb1 is cb2

    def test_get_circuit_breaker_with_config(self):
        """설정과 함께 생성"""
        config = CircuitBreakerConfig(failure_threshold=10)
        cb = get_circuit_breaker("configured_cb", config=config)

        assert cb.config.failure_threshold == 10

    def test_get_all_circuit_breakers(self):
        """모든 Circuit Breaker 조회"""
        get_circuit_breaker("cb1")
        get_circuit_breaker("cb2")
        get_circuit_breaker("cb3")

        all_cbs = get_all_circuit_breakers()

        assert len(all_cbs) == 3
        assert "cb1" in all_cbs
        assert "cb2" in all_cbs
        assert "cb3" in all_cbs

    def test_get_circuit_breaker_status(self):
        """특정 Circuit Breaker 상태 조회"""
        get_circuit_breaker("status_cb")

        status = get_circuit_breaker_status("status_cb")

        assert status is not None
        assert status["name"] == "status_cb"

    def test_get_circuit_breaker_status_not_found(self):
        """존재하지 않는 Circuit Breaker 상태 조회"""
        status = get_circuit_breaker_status("nonexistent")

        assert status is None

    def test_get_all_circuit_breaker_statuses(self):
        """모든 Circuit Breaker 상태 조회"""
        get_circuit_breaker("s1")
        get_circuit_breaker("s2")

        statuses = get_all_circuit_breaker_statuses()

        assert len(statuses) == 2
        assert "s1" in statuses
        assert "s2" in statuses

    def test_reset_circuit_breaker(self):
        """특정 Circuit Breaker 리셋"""
        cb = get_circuit_breaker("reset_cb")
        cb._state = CircuitState.OPEN

        result = reset_circuit_breaker("reset_cb")

        assert result is True
        assert cb.is_closed is True

    def test_reset_circuit_breaker_not_found(self):
        """존재하지 않는 Circuit Breaker 리셋"""
        result = reset_circuit_breaker("nonexistent")

        assert result is False

    def test_reset_all_circuit_breakers(self):
        """모든 Circuit Breaker 리셋"""
        cb1 = get_circuit_breaker("r1")
        cb2 = get_circuit_breaker("r2")
        cb1._state = CircuitState.OPEN
        cb2._state = CircuitState.HALF_OPEN

        reset_all_circuit_breakers()

        assert cb1.is_closed is True
        assert cb2.is_closed is True


class TestPredefinedCircuitBreakers:
    """사전 정의된 Circuit Breaker 테스트"""

    @pytest.fixture(autouse=True)
    def clear_registry(self):
        """각 테스트 전 레지스트리 초기화"""
        _circuit_breakers.clear()
        yield
        _circuit_breakers.clear()

    def test_get_llm_circuit_breaker(self):
        """LLM 서비스용 Circuit Breaker"""
        cb = get_llm_circuit_breaker()

        assert cb.name == "llm_service"
        assert cb.config.failure_threshold == 3
        assert cb.config.recovery_timeout == 60.0
        assert cb.config.call_timeout == 120.0

    def test_get_mcp_circuit_breaker(self):
        """MCP 서버용 Circuit Breaker"""
        cb = get_mcp_circuit_breaker("slack")

        assert cb.name == "mcp_slack"
        assert cb.config.failure_threshold == 5
        assert cb.config.recovery_timeout == 30.0

    def test_get_external_api_circuit_breaker(self):
        """외부 API용 Circuit Breaker"""
        cb = get_external_api_circuit_breaker("openai")

        assert cb.name == "api_openai"
        assert cb.config.failure_threshold == 5
        assert cb.config.recovery_timeout == 45.0
