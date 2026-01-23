"""
TriFlow AI - Retry 유틸리티
재시도 로직 및 Exponential Backoff
"""
import asyncio
import logging
import random
from functools import wraps
from typing import Callable, Optional, Type, Tuple, Any

logger = logging.getLogger(__name__)

# Retry 가능한 예외 목록
RETRYABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
)


def is_retryable_error(exception: Exception) -> bool:
    """
    재시도 가능한 에러인지 확인

    Args:
        exception: 발생한 예외

    Returns:
        재시도 가능 여부
    """
    error_str = str(exception).lower()

    # Rate limit 에러
    if "rate" in error_str and "limit" in error_str:
        return True

    # Overloaded 에러
    if "overloaded" in error_str:
        return True

    # 임시 네트워크 에러
    if "connection" in error_str and "reset" in error_str:
        return True

    # 타임아웃
    if "timeout" in error_str:
        return True

    # 임시 서비스 불가 (API 오류)
    if "temporarily" in error_str or "temporarily_unavailable" in error_str:
        return True

    # 기본 재시도 가능 예외
    if isinstance(exception, RETRYABLE_EXCEPTIONS):
        return True

    return False


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
):
    """
    Exponential Backoff로 재시도하는 데코레이터

    Args:
        max_retries: 최대 재시도 횟수
        base_delay: 기본 대기 시간 (초)
        max_delay: 최대 대기 시간 (초)
        exponential_base: 지수 기반
        jitter: 랜덤 지터 추가 여부
        retryable_exceptions: 재시도할 예외 타입들
    """
    def decorator(func: Callable):
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            exceptions = retryable_exceptions or RETRYABLE_EXCEPTIONS
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # 재시도 가능한 에러인지 확인
                    if not isinstance(e, exceptions) and not is_retryable_error(e):
                        logger.warning(
                            f"Non-retryable error in {func.__name__}: {e}"
                        )
                        raise

                    if attempt < max_retries:
                        # 대기 시간 계산 (Exponential Backoff)
                        delay = min(
                            base_delay * (exponential_base ** attempt),
                            max_delay
                        )

                        if jitter:
                            delay = delay * (0.5 + random.random())

                        logger.warning(
                            f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                            f"after {delay:.2f}s due to: {e}"
                        )

                        import time
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"Max retries ({max_retries}) exceeded for {func.__name__}: {e}"
                        )
                        raise

            raise last_exception

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            exceptions = retryable_exceptions or RETRYABLE_EXCEPTIONS
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # 재시도 가능한 에러인지 확인
                    if not isinstance(e, exceptions) and not is_retryable_error(e):
                        logger.warning(
                            f"Non-retryable error in {func.__name__}: {e}"
                        )
                        raise

                    if attempt < max_retries:
                        # 대기 시간 계산 (Exponential Backoff)
                        delay = min(
                            base_delay * (exponential_base ** attempt),
                            max_delay
                        )

                        if jitter:
                            delay = delay * (0.5 + random.random())

                        logger.warning(
                            f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                            f"after {delay:.2f}s due to: {e}"
                        )

                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"Max retries ({max_retries}) exceeded for {func.__name__}: {e}"
                        )
                        raise

            raise last_exception

        # 비동기 함수인지 확인
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class RetryableOperation:
    """
    재시도 가능한 작업 래퍼 클래스

    Usage:
        op = RetryableOperation(max_retries=3)
        result = op.execute(lambda: some_function())
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.attempt_count = 0
        self.last_error: Optional[Exception] = None

    def execute(self, operation: Callable[[], Any]) -> Any:
        """
        작업 실행 (동기)

        Args:
            operation: 실행할 함수

        Returns:
            작업 결과
        """
        import time

        for attempt in range(self.max_retries + 1):
            self.attempt_count = attempt + 1
            try:
                return operation()
            except Exception as e:
                self.last_error = e

                if not is_retryable_error(e):
                    raise

                if attempt < self.max_retries:
                    delay = min(
                        self.base_delay * (2 ** attempt) * (0.5 + random.random()),
                        self.max_delay
                    )
                    logger.warning(
                        f"Retry {attempt + 1}/{self.max_retries} after {delay:.2f}s: {e}"
                    )
                    time.sleep(delay)
                else:
                    raise

        raise self.last_error

    async def execute_async(self, operation: Callable[[], Any]) -> Any:
        """
        작업 실행 (비동기)

        Args:
            operation: 실행할 비동기 함수

        Returns:
            작업 결과
        """
        for attempt in range(self.max_retries + 1):
            self.attempt_count = attempt + 1
            try:
                if asyncio.iscoroutinefunction(operation):
                    return await operation()
                return operation()
            except Exception as e:
                self.last_error = e

                if not is_retryable_error(e):
                    raise

                if attempt < self.max_retries:
                    delay = min(
                        self.base_delay * (2 ** attempt) * (0.5 + random.random()),
                        self.max_delay
                    )
                    logger.warning(
                        f"Retry {attempt + 1}/{self.max_retries} after {delay:.2f}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    raise

        raise self.last_error
