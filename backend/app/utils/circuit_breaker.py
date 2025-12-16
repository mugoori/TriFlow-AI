"""
Circuit Breaker 패턴 구현
스펙 참조: B-2-1, B-5

Circuit Breaker는 외부 서비스 호출 실패를 감지하고
시스템을 보호하기 위해 일정 기간 호출을 차단합니다.

상태:
- CLOSED: 정상 상태, 모든 호출 허용
- OPEN: 차단 상태, 모든 호출 거부 (fallback 실행)
- HALF_OPEN: 복구 테스트 중, 일부 호출 허용

V2 업데이트 (2025-12-16):
- 초기 구현
- 워크플로우 노드 및 MCP 서비스용
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(str, Enum):
    """Circuit Breaker 상태"""
    CLOSED = "closed"       # 정상 - 호출 허용
    OPEN = "open"           # 차단 - 호출 거부
    HALF_OPEN = "half_open" # 복구 테스트 중


@dataclass
class CircuitBreakerConfig:
    """Circuit Breaker 설정"""
    # 실패 임계값: 이 횟수 이상 연속 실패하면 OPEN
    failure_threshold: int = 5

    # 복구 대기 시간 (초): OPEN 후 이 시간이 지나면 HALF_OPEN
    recovery_timeout: float = 30.0

    # HALF_OPEN에서 성공해야 하는 호출 수
    success_threshold: int = 2

    # 슬라이딩 윈도우 크기 (초): 이 시간 내의 실패만 카운트
    sliding_window_size: float = 60.0

    # 타임아웃 (초): 호출 타임아웃
    call_timeout: float = 30.0

    # 예외 타입: 이 타입의 예외만 실패로 카운트
    failure_exceptions: tuple = (Exception,)

    # 무시할 예외 타입: 이 타입의 예외는 실패로 카운트하지 않음
    ignored_exceptions: tuple = ()


@dataclass
class CircuitBreakerStats:
    """Circuit Breaker 통계"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    state_changes: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "rejected_calls": self.rejected_calls,
            "success_rate": self.success_rate,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
            "recent_state_changes": self.state_changes[-5:],
        }

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 1.0
        return self.successful_calls / self.total_calls


class CircuitBreakerError(Exception):
    """Circuit Breaker 열림 상태에서 발생하는 예외"""
    def __init__(self, circuit_name: str, remaining_time: float):
        self.circuit_name = circuit_name
        self.remaining_time = remaining_time
        super().__init__(
            f"Circuit '{circuit_name}' is OPEN. "
            f"Retry after {remaining_time:.1f} seconds."
        )


class CircuitBreaker:
    """
    Circuit Breaker 구현

    사용 예시:
    ```python
    # 1. 인스턴스 생성
    cb = CircuitBreaker(name="llm_service")

    # 2. 데코레이터로 사용
    @cb.protect
    async def call_llm(prompt: str):
        return await llm_client.generate(prompt)

    # 3. 컨텍스트 매니저로 사용
    async with cb:
        result = await call_external_api()

    # 4. 직접 실행
    result = await cb.execute(call_external_api)
    ```
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        fallback: Optional[Callable[..., Any]] = None,
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.fallback = fallback

        self._state = CircuitState.CLOSED
        self._failure_times: List[float] = []
        self._success_count_in_half_open: int = 0
        self._last_state_change_time: float = time.time()
        self._lock = asyncio.Lock()

        self.stats = CircuitBreakerStats()

    @property
    def state(self) -> CircuitState:
        """현재 상태 (시간 기반 자동 전이 포함)"""
        if self._state == CircuitState.OPEN:
            if self._should_transition_to_half_open():
                self._transition_to(CircuitState.HALF_OPEN)
        return self._state

    @property
    def is_closed(self) -> bool:
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        return self.state == CircuitState.HALF_OPEN

    def _should_transition_to_half_open(self) -> bool:
        """OPEN → HALF_OPEN 전이 조건 확인"""
        elapsed = time.time() - self._last_state_change_time
        return elapsed >= self.config.recovery_timeout

    def _transition_to(self, new_state: CircuitState):
        """상태 전이"""
        old_state = self._state
        if old_state == new_state:
            return

        self._state = new_state
        self._last_state_change_time = time.time()

        if new_state == CircuitState.HALF_OPEN:
            self._success_count_in_half_open = 0

        if new_state == CircuitState.CLOSED:
            self._failure_times.clear()

        # 통계 기록
        self.stats.state_changes.append({
            "from": old_state.value,
            "to": new_state.value,
            "time": datetime.utcnow().isoformat(),
        })

        logger.info(
            f"Circuit '{self.name}' state changed: {old_state.value} → {new_state.value}"
        )

    def _record_success(self):
        """성공 기록"""
        self.stats.successful_calls += 1
        self.stats.last_success_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            self._success_count_in_half_open += 1
            if self._success_count_in_half_open >= self.config.success_threshold:
                self._transition_to(CircuitState.CLOSED)

    def _record_failure(self):
        """실패 기록"""
        now = time.time()
        self.stats.failed_calls += 1
        self.stats.last_failure_time = now

        # 슬라이딩 윈도우 내의 실패만 유지
        window_start = now - self.config.sliding_window_size
        self._failure_times = [
            t for t in self._failure_times if t > window_start
        ]
        self._failure_times.append(now)

        # HALF_OPEN에서 실패 → 즉시 OPEN
        if self._state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)
        # CLOSED에서 임계값 초과 → OPEN
        elif len(self._failure_times) >= self.config.failure_threshold:
            self._transition_to(CircuitState.OPEN)

    async def execute(
        self,
        func: Callable[..., Any],
        *args,
        **kwargs
    ) -> Any:
        """
        보호된 함수 실행

        Args:
            func: 실행할 함수 (async 또는 sync)
            *args: 함수 인자
            **kwargs: 함수 키워드 인자

        Returns:
            함수 실행 결과 또는 fallback 결과

        Raises:
            CircuitBreakerError: Circuit이 OPEN 상태이고 fallback이 없을 때
        """
        self.stats.total_calls += 1

        # Circuit OPEN 상태 확인
        if self.is_open:
            self.stats.rejected_calls += 1
            remaining = self.config.recovery_timeout - (
                time.time() - self._last_state_change_time
            )

            if self.fallback:
                logger.warning(
                    f"Circuit '{self.name}' is OPEN, executing fallback"
                )
                if asyncio.iscoroutinefunction(self.fallback):
                    return await self.fallback(*args, **kwargs)
                return self.fallback(*args, **kwargs)

            raise CircuitBreakerError(self.name, max(0, remaining))

        # 함수 실행
        try:
            if asyncio.iscoroutinefunction(func):
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=self.config.call_timeout
                )
            else:
                # 동기 함수는 executor에서 실행
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: func(*args, **kwargs)),
                    timeout=self.config.call_timeout
                )

            self._record_success()
            return result

        except self.config.ignored_exceptions:
            # 무시할 예외는 성공으로 처리
            raise

        except asyncio.TimeoutError:
            self._record_failure()
            logger.warning(
                f"Circuit '{self.name}' call timeout after "
                f"{self.config.call_timeout}s"
            )
            if self.fallback:
                if asyncio.iscoroutinefunction(self.fallback):
                    return await self.fallback(*args, **kwargs)
                return self.fallback(*args, **kwargs)
            raise

        except self.config.failure_exceptions as e:
            self._record_failure()
            logger.warning(
                f"Circuit '{self.name}' call failed: {e}"
            )
            if self.fallback:
                if asyncio.iscoroutinefunction(self.fallback):
                    return await self.fallback(*args, **kwargs)
                return self.fallback(*args, **kwargs)
            raise

    def protect(self, func: Callable[..., T]) -> Callable[..., T]:
        """
        데코레이터로 함수 보호

        사용 예시:
        ```python
        cb = CircuitBreaker(name="api")

        @cb.protect
        async def call_api():
            return await api_client.get()
        ```
        """
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await self.execute(func, *args, **kwargs)
        return wrapper

    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        if self.is_open:
            remaining = self.config.recovery_timeout - (
                time.time() - self._last_state_change_time
            )
            raise CircuitBreakerError(self.name, max(0, remaining))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        if exc_type is None:
            self._record_success()
        elif not isinstance(exc_val, self.config.ignored_exceptions):
            if isinstance(exc_val, self.config.failure_exceptions):
                self._record_failure()
        return False  # 예외 전파

    def reset(self):
        """Circuit Breaker 리셋 (테스트용)"""
        self._state = CircuitState.CLOSED
        self._failure_times.clear()
        self._success_count_in_half_open = 0
        self._last_state_change_time = time.time()
        logger.info(f"Circuit '{self.name}' has been reset")

    def get_status(self) -> Dict[str, Any]:
        """현재 상태 조회"""
        return {
            "name": self.name,
            "state": self.state.value,
            "is_open": self.is_open,
            "failure_count": len(self._failure_times),
            "success_count_in_half_open": self._success_count_in_half_open,
            "time_since_last_change": time.time() - self._last_state_change_time,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "success_threshold": self.config.success_threshold,
            },
            "stats": self.stats.to_dict(),
        }


# Circuit Breaker 레지스트리 (이름으로 관리)
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None,
    fallback: Optional[Callable[..., Any]] = None,
) -> CircuitBreaker:
    """
    Circuit Breaker 인스턴스 조회 또는 생성

    같은 이름으로 여러 번 호출해도 동일 인스턴스 반환

    Args:
        name: Circuit Breaker 이름 (예: "llm_service", "mcp_slack")
        config: 설정 (첫 생성 시만 적용)
        fallback: 폴백 함수 (첫 생성 시만 적용)

    Returns:
        CircuitBreaker 인스턴스
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(
            name=name,
            config=config,
            fallback=fallback,
        )
    return _circuit_breakers[name]


def get_all_circuit_breakers() -> Dict[str, CircuitBreaker]:
    """모든 Circuit Breaker 조회"""
    return _circuit_breakers.copy()


def get_circuit_breaker_status(name: str) -> Optional[Dict[str, Any]]:
    """특정 Circuit Breaker 상태 조회"""
    cb = _circuit_breakers.get(name)
    if cb:
        return cb.get_status()
    return None


def get_all_circuit_breaker_statuses() -> Dict[str, Dict[str, Any]]:
    """모든 Circuit Breaker 상태 조회"""
    return {
        name: cb.get_status()
        for name, cb in _circuit_breakers.items()
    }


def reset_circuit_breaker(name: str) -> bool:
    """특정 Circuit Breaker 리셋"""
    cb = _circuit_breakers.get(name)
    if cb:
        cb.reset()
        return True
    return False


def reset_all_circuit_breakers():
    """모든 Circuit Breaker 리셋 (테스트용)"""
    for cb in _circuit_breakers.values():
        cb.reset()


# 편의를 위한 사전 정의된 Circuit Breaker
def get_llm_circuit_breaker() -> CircuitBreaker:
    """LLM 서비스용 Circuit Breaker"""
    return get_circuit_breaker(
        name="llm_service",
        config=CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=60.0,
            success_threshold=2,
            call_timeout=120.0,
        ),
    )


def get_mcp_circuit_breaker(server_name: str) -> CircuitBreaker:
    """MCP 서버용 Circuit Breaker"""
    return get_circuit_breaker(
        name=f"mcp_{server_name}",
        config=CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=30.0,
            success_threshold=3,
            call_timeout=30.0,
        ),
    )


def get_external_api_circuit_breaker(api_name: str) -> CircuitBreaker:
    """외부 API용 Circuit Breaker"""
    return get_circuit_breaker(
        name=f"api_{api_name}",
        config=CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=45.0,
            success_threshold=2,
            call_timeout=30.0,
        ),
    )
