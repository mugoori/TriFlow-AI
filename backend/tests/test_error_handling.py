"""
Error Handling 테스트
에러 분류, 포맷팅, Retry 로직 테스트
"""
import pytest

from app.utils.errors import (
    ErrorCategory,
    UserFriendlyError,
    ERROR_MESSAGES,
    classify_error,
    format_error_response,
)
from app.utils.retry import (
    is_retryable_error,
    retry_with_backoff,
    RetryableOperation,
)
from app.agents.base_agent import is_retryable_api_error


class TestErrorCategory:
    """에러 카테고리 테스트"""

    def test_error_categories_exist(self):
        """모든 필수 카테고리가 존재하는지 확인"""
        required_categories = [
            "VALIDATION",
            "AUTHENTICATION",
            "AUTHORIZATION",
            "NOT_FOUND",
            "CONFLICT",
            "RATE_LIMIT",
            "SERVICE",
            "DATABASE",
            "AGENT",
            "INTERNAL",
            "NETWORK",
            "TIMEOUT",
        ]
        for cat in required_categories:
            assert hasattr(ErrorCategory, cat), f"Missing category: {cat}"

    def test_error_messages_defined(self):
        """에러 메시지가 정의되어 있는지 확인"""
        expected_keys = [
            "rate_limit_error",
            "invalid_api_key",
            "overloaded_error",
            "invalid_request_error",
            "connection_error",
            "duplicate_key",
            "agent_timeout",
            "agent_max_iterations",
            "empty_message",
            "network_error",
        ]
        for key in expected_keys:
            assert key in ERROR_MESSAGES, f"Missing error message: {key}"


class TestClassifyError:
    """에러 분류 테스트"""

    def test_classify_rate_limit_error(self):
        """Rate limit 에러 분류"""
        exc = Exception("Rate limit exceeded")
        result = classify_error(exc)
        assert result.category == ErrorCategory.RATE_LIMIT
        assert result.retryable is True

    def test_classify_overloaded_error(self):
        """Overloaded 에러 분류"""
        exc = Exception("API is overloaded")
        result = classify_error(exc)
        assert result.category == ErrorCategory.SERVICE
        assert result.retryable is True

    def test_classify_api_key_error(self):
        """API 키 에러 분류"""
        exc = Exception("invalid api_key provided")
        result = classify_error(exc)
        assert result.category == ErrorCategory.AUTHENTICATION

    def test_classify_authentication_error(self):
        """인증 에러 분류"""
        exc = Exception("authentication failed")
        result = classify_error(exc)
        assert result.category == ErrorCategory.AUTHENTICATION
        assert result.retryable is False

    def test_classify_database_connection_error(self):
        """데이터베이스 연결 에러 분류"""
        exc = Exception("Database connection refused")
        result = classify_error(exc)
        assert result.category == ErrorCategory.DATABASE
        assert result.retryable is True

    def test_classify_database_failed_error(self):
        """데이터베이스 실패 에러 분류"""
        exc = Exception("Database connection failed")
        result = classify_error(exc)
        assert result.category == ErrorCategory.DATABASE

    def test_classify_duplicate_error(self):
        """중복 에러 분류"""
        exc = Exception("duplicate key violates constraint")
        result = classify_error(exc)
        assert result.category == ErrorCategory.CONFLICT
        assert result.retryable is False

    def test_classify_unique_error(self):
        """유니크 제약 에러 분류"""
        exc = Exception("unique constraint violated")
        result = classify_error(exc)
        assert result.category == ErrorCategory.CONFLICT

    def test_classify_timeout_error_string(self):
        """타임아웃 에러 문자열 분류"""
        exc = Exception("Request timed out")
        result = classify_error(exc)
        assert result.category == ErrorCategory.TIMEOUT
        assert result.retryable is True

    def test_classify_timeout_error_type(self):
        """타임아웃 에러 타입 분류"""
        exc = Exception("timeout occurred")
        result = classify_error(exc)
        assert result.category == ErrorCategory.TIMEOUT

    def test_classify_empty_message_error(self):
        """빈 메시지 에러 분류"""
        exc = Exception("all messages must have non-empty content")
        result = classify_error(exc)
        assert result.category == ErrorCategory.VALIDATION
        assert result.retryable is False

    def test_classify_unknown_error(self):
        """알 수 없는 에러 분류 (기본값)"""
        exc = Exception("Something completely unexpected")
        result = classify_error(exc)
        assert result.category == ErrorCategory.INTERNAL
        assert result.retryable is False


class TestFormatErrorResponse:
    """에러 응답 포맷팅 테스트"""

    def test_format_korean_response(self):
        """한국어 에러 응답"""
        error = UserFriendlyError(
            category=ErrorCategory.RATE_LIMIT,
            message_ko="요청이 너무 많습니다.",
            message_en="Too many requests.",
            suggestion_ko="잠시 후 다시 시도해 주세요.",
            suggestion_en="Please try again later.",
            http_status=429,
            retryable=True,
        )
        result = format_error_response(error, lang="ko")

        assert "error" in result
        assert result["error"]["category"] == "rate_limit"
        assert result["error"]["message"] == "요청이 너무 많습니다."
        assert result["error"]["suggestion"] == "잠시 후 다시 시도해 주세요."
        assert result["error"]["retryable"] is True

    def test_format_english_response(self):
        """영어 에러 응답"""
        error = UserFriendlyError(
            category=ErrorCategory.AUTHENTICATION,
            message_ko="인증에 실패했습니다.",
            message_en="Authentication failed.",
            suggestion_ko="다시 로그인해 주세요.",
            suggestion_en="Please log in again.",
            http_status=401,
            retryable=False,
        )
        result = format_error_response(error, lang="en")

        assert result["error"]["message"] == "Authentication failed."
        assert result["error"]["suggestion"] == "Please log in again."

    def test_format_default_to_korean(self):
        """언어 미지정 시 한국어 기본값"""
        error = ERROR_MESSAGES["rate_limit_error"]
        result = format_error_response(error)

        assert "error" in result
        assert result["error"]["message"] == error.message_ko

    def test_format_with_technical_detail(self):
        """기술적 세부사항 포함"""
        error = UserFriendlyError(
            category=ErrorCategory.INTERNAL,
            message_ko="에러 발생",
            message_en="Error occurred",
            technical_detail="Stack trace here",
            http_status=500,
            retryable=False,
        )
        result = format_error_response(error, include_technical=True)

        assert result["error"]["detail"] == "Stack trace here"

    def test_format_without_suggestion(self):
        """제안 없는 에러 응답"""
        error = UserFriendlyError(
            category=ErrorCategory.INTERNAL,
            message_ko="에러 발생",
            message_en="Error occurred",
            suggestion_ko=None,
            suggestion_en=None,
            http_status=500,
            retryable=False,
        )
        result = format_error_response(error)

        assert "suggestion" not in result["error"]


class TestIsRetryableApiError:
    """API 에러 재시도 가능 여부 테스트"""

    def test_rate_limit_is_retryable(self):
        """Rate limit 에러는 재시도 가능"""
        exc = Exception("rate limit exceeded")
        assert is_retryable_api_error(exc) is True

    def test_overloaded_is_retryable(self):
        """Overloaded 에러는 재시도 가능"""
        exc = Exception("API is overloaded, please retry")
        assert is_retryable_api_error(exc) is True

    def test_temporarily_unavailable_is_retryable(self):
        """임시 불가능 에러는 재시도 가능"""
        exc = Exception("Service temporarily unavailable")
        assert is_retryable_api_error(exc) is True

    def test_connection_error_is_retryable(self):
        """연결 에러는 재시도 가능"""
        exc = ConnectionError("Connection refused")
        assert is_retryable_api_error(exc) is True

    def test_timeout_error_is_retryable(self):
        """타임아웃 에러는 재시도 가능"""
        exc = TimeoutError("Request timed out")
        assert is_retryable_api_error(exc) is True

    def test_invalid_api_key_not_retryable(self):
        """API 키 에러는 재시도 불가"""
        exc = Exception("Invalid API key")
        assert is_retryable_api_error(exc) is False

    def test_validation_error_not_retryable(self):
        """유효성 에러는 재시도 불가"""
        exc = ValueError("Invalid input parameter")
        assert is_retryable_api_error(exc) is False


class TestRetryableError:
    """retry.py의 is_retryable_error 테스트"""

    def test_connection_error_retryable(self):
        """연결 에러 재시도 가능"""
        exc = ConnectionError("Connection failed")
        assert is_retryable_error(exc) is True

    def test_timeout_error_retryable(self):
        """타임아웃 에러 재시도 가능"""
        exc = TimeoutError("Request timed out")
        assert is_retryable_error(exc) is True

    def test_os_error_retryable(self):
        """OS 에러 재시도 가능"""
        exc = OSError("Network is unreachable")
        assert is_retryable_error(exc) is True

    def test_rate_limit_string_retryable(self):
        """Rate limit 문자열 에러 재시도 가능"""
        exc = Exception("rate limit exceeded")
        assert is_retryable_error(exc) is True

    def test_overloaded_string_retryable(self):
        """Overloaded 문자열 에러 재시도 가능"""
        exc = Exception("Server overloaded")
        assert is_retryable_error(exc) is True

    def test_connection_reset_retryable(self):
        """Connection reset 에러 재시도 가능"""
        exc = Exception("connection reset by peer")
        assert is_retryable_error(exc) is True

    def test_random_error_not_retryable(self):
        """일반 에러는 재시도 불가"""
        exc = Exception("Something random happened")
        assert is_retryable_error(exc) is False


class TestRetryWithBackoff:
    """retry_with_backoff 데코레이터 테스트"""

    def test_successful_on_first_try(self):
        """첫 시도에 성공"""
        call_count = 0

        @retry_with_backoff(max_retries=3)
        def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = success_func()
        assert result == "success"
        assert call_count == 1

    def test_retry_on_connection_error(self):
        """ConnectionError 시 재시도"""
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Connection failed")
            return "success"

        result = fail_then_succeed()
        assert result == "success"
        assert call_count == 2

    def test_no_retry_on_value_error(self):
        """ValueError는 재시도 안 함"""
        call_count = 0

        @retry_with_backoff(max_retries=3)
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid value")

        with pytest.raises(ValueError):
            always_fail()

        assert call_count == 1  # 재시도 없이 바로 실패

    def test_max_retries_exceeded(self):
        """최대 재시도 횟수 초과"""
        call_count = 0

        @retry_with_backoff(max_retries=2, base_delay=0.01)
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Always fails")

        with pytest.raises(ConnectionError):
            always_fail()

        assert call_count == 3  # 초기 1회 + 재시도 2회


class TestRetryableOperation:
    """RetryableOperation 클래스 테스트"""

    def test_successful_operation(self):
        """성공적인 작업 실행"""
        op = RetryableOperation(max_retries=3)
        result = op.execute(lambda: "success")

        assert result == "success"
        assert op.attempt_count == 1
        assert op.last_error is None

    def test_retry_then_succeed(self):
        """재시도 후 성공"""
        call_count = 0

        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Temporary failure")
            return "success"

        op = RetryableOperation(max_retries=3, base_delay=0.01)
        result = op.execute(fail_then_succeed)

        assert result == "success"
        assert call_count == 2

    def test_max_retries_exceeded_operation(self):
        """최대 재시도 후 실패"""
        def always_fail():
            raise ConnectionError("Permanent failure")

        op = RetryableOperation(max_retries=2, base_delay=0.01)

        with pytest.raises(ConnectionError):
            op.execute(always_fail)

        assert op.attempt_count == 3
        assert op.last_error is not None


class TestAsyncRetry:
    """비동기 재시도 테스트"""

    @pytest.mark.asyncio
    async def test_async_successful_on_first_try(self):
        """비동기 - 첫 시도에 성공"""
        call_count = 0

        @retry_with_backoff(max_retries=3)
        async def async_success():
            nonlocal call_count
            call_count += 1
            return "async success"

        result = await async_success()
        assert result == "async success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_async_retry_on_error(self):
        """비동기 - 에러 시 재시도"""
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        async def async_fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Async connection failed")
            return "async success"

        result = await async_fail_then_succeed()
        assert result == "async success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_async_operation_execute(self):
        """RetryableOperation 비동기 실행"""
        call_count = 0

        async def async_func():
            nonlocal call_count
            call_count += 1
            return "async result"

        op = RetryableOperation(max_retries=3)
        result = await op.execute_async(async_func)

        assert result == "async result"
        assert call_count == 1


class TestErrorMessageCompleteness:
    """에러 메시지 완전성 테스트"""

    def test_all_messages_have_korean(self):
        """모든 에러 메시지에 한국어가 있는지 확인"""
        for key, error in ERROR_MESSAGES.items():
            assert error.message_ko, f"Missing Korean message for {key}"
            assert len(error.message_ko) > 0

    def test_all_messages_have_english(self):
        """모든 에러 메시지에 영어가 있는지 확인"""
        for key, error in ERROR_MESSAGES.items():
            assert error.message_en, f"Missing English message for {key}"
            assert len(error.message_en) > 0

    def test_all_messages_have_suggestions(self):
        """모든 에러 메시지에 제안이 있는지 확인"""
        for key, error in ERROR_MESSAGES.items():
            assert error.suggestion_ko, f"Missing Korean suggestion for {key}"
            assert error.suggestion_en, f"Missing English suggestion for {key}"

    def test_http_status_codes_are_valid(self):
        """HTTP 상태 코드가 유효한지 확인"""
        valid_status_codes = [400, 401, 403, 404, 408, 409, 422, 429, 500, 502, 503, 504]
        for key, error in ERROR_MESSAGES.items():
            assert error.http_status in valid_status_codes, \
                f"Invalid HTTP status {error.http_status} for {key}"


class TestUserFriendlyError:
    """UserFriendlyError 데이터클래스 테스트"""

    def test_default_values(self):
        """기본값 테스트"""
        error = UserFriendlyError(
            category=ErrorCategory.INTERNAL,
            message_ko="에러",
            message_en="Error",
        )
        assert error.suggestion_ko is None
        assert error.suggestion_en is None
        assert error.technical_detail is None
        assert error.http_status == 500
        assert error.retryable is False

    def test_all_fields(self):
        """모든 필드 설정 테스트"""
        error = UserFriendlyError(
            category=ErrorCategory.RATE_LIMIT,
            message_ko="한도 초과",
            message_en="Limit exceeded",
            suggestion_ko="기다려주세요",
            suggestion_en="Please wait",
            technical_detail="429 Too Many Requests",
            http_status=429,
            retryable=True,
        )
        assert error.category == ErrorCategory.RATE_LIMIT
        assert error.message_ko == "한도 초과"
        assert error.message_en == "Limit exceeded"
        assert error.suggestion_ko == "기다려주세요"
        assert error.suggestion_en == "Please wait"
        assert error.technical_detail == "429 Too Many Requests"
        assert error.http_status == 429
        assert error.retryable is True
