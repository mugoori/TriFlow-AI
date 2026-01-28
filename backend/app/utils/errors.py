"""
TriFlow AI - 에러 유틸리티
사용자 친화적 에러 메시지 및 에러 분류
"""
import asyncio
import logging
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass

# Optional imports for specific timeout exceptions
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

try:
    import redis.exceptions
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


class ErrorCategory(str, Enum):
    """에러 카테고리"""
    VALIDATION = "validation"        # 입력 검증 실패
    AUTHENTICATION = "auth"          # 인증 실패
    AUTHORIZATION = "permission"     # 권한 부족
    NOT_FOUND = "not_found"          # 리소스 없음
    CONFLICT = "conflict"            # 충돌 (중복 등)
    RATE_LIMIT = "rate_limit"        # API 한도 초과
    SERVICE = "service"              # 외부 서비스 오류
    DATABASE = "database"            # DB 오류
    AGENT = "agent"                  # AI Agent 오류
    INTERNAL = "internal"            # 내부 서버 오류
    NETWORK = "network"              # 네트워크 오류
    TIMEOUT = "timeout"              # 타임아웃


@dataclass
class UserFriendlyError:
    """사용자 친화적 에러"""
    category: ErrorCategory
    message_ko: str
    message_en: str
    suggestion_ko: Optional[str] = None
    suggestion_en: Optional[str] = None
    technical_detail: Optional[str] = None
    http_status: int = 500
    retryable: bool = False


# 에러 메시지 매핑
ERROR_MESSAGES: Dict[str, UserFriendlyError] = {
    # Anthropic API 에러
    "rate_limit_error": UserFriendlyError(
        category=ErrorCategory.RATE_LIMIT,
        message_ko="AI 서비스 요청 한도를 초과했습니다.",
        message_en="AI service rate limit exceeded.",
        suggestion_ko="잠시 후 다시 시도해 주세요.",
        suggestion_en="Please try again in a moment.",
        http_status=429,
        retryable=True,
    ),
    "invalid_api_key": UserFriendlyError(
        category=ErrorCategory.AUTHENTICATION,
        message_ko="AI 서비스 인증에 실패했습니다.",
        message_en="AI service authentication failed.",
        suggestion_ko="관리자에게 문의하세요.",
        suggestion_en="Please contact the administrator.",
        http_status=503,
        retryable=False,
    ),
    "overloaded_error": UserFriendlyError(
        category=ErrorCategory.SERVICE,
        message_ko="AI 서비스가 현재 과부하 상태입니다.",
        message_en="AI service is currently overloaded.",
        suggestion_ko="잠시 후 다시 시도해 주세요.",
        suggestion_en="Please try again in a moment.",
        http_status=503,
        retryable=True,
    ),
    "invalid_request_error": UserFriendlyError(
        category=ErrorCategory.VALIDATION,
        message_ko="요청 형식이 올바르지 않습니다.",
        message_en="Invalid request format.",
        suggestion_ko="입력 내용을 확인해 주세요.",
        suggestion_en="Please check your input.",
        http_status=400,
        retryable=False,
    ),

    # 데이터베이스 에러
    "connection_error": UserFriendlyError(
        category=ErrorCategory.DATABASE,
        message_ko="데이터베이스 연결에 실패했습니다.",
        message_en="Database connection failed.",
        suggestion_ko="잠시 후 다시 시도해 주세요.",
        suggestion_en="Please try again in a moment.",
        http_status=503,
        retryable=True,
    ),
    "duplicate_key": UserFriendlyError(
        category=ErrorCategory.CONFLICT,
        message_ko="이미 존재하는 데이터입니다.",
        message_en="Data already exists.",
        suggestion_ko="다른 값을 입력해 주세요.",
        suggestion_en="Please enter a different value.",
        http_status=409,
        retryable=False,
    ),

    # Agent 에러
    "agent_timeout": UserFriendlyError(
        category=ErrorCategory.TIMEOUT,
        message_ko="AI 처리 시간이 초과되었습니다.",
        message_en="AI processing timeout.",
        suggestion_ko="질문을 더 간단하게 해보세요.",
        suggestion_en="Try simplifying your question.",
        http_status=504,
        retryable=True,
    ),
    "agent_max_iterations": UserFriendlyError(
        category=ErrorCategory.AGENT,
        message_ko="AI가 최대 처리 횟수에 도달했습니다.",
        message_en="AI reached maximum processing iterations.",
        suggestion_ko="질문을 더 구체적으로 해보세요.",
        suggestion_en="Try being more specific with your question.",
        http_status=500,
        retryable=True,
    ),
    "empty_message": UserFriendlyError(
        category=ErrorCategory.VALIDATION,
        message_ko="메시지가 비어있습니다.",
        message_en="Message is empty.",
        suggestion_ko="질문이나 요청 내용을 입력해 주세요.",
        suggestion_en="Please enter your question or request.",
        http_status=400,
        retryable=False,
    ),

    # 네트워크 에러
    "network_error": UserFriendlyError(
        category=ErrorCategory.NETWORK,
        message_ko="네트워크 연결에 문제가 있습니다.",
        message_en="Network connection error.",
        suggestion_ko="인터넷 연결을 확인해 주세요.",
        suggestion_en="Please check your internet connection.",
        http_status=503,
        retryable=True,
    ),
}


def _is_timeout_exception(exception: Exception) -> bool:
    """
    실제 timeout 예외인지 확인
    단순 문자열 매칭이 아닌 예외 타입 기반 확인
    """
    # Python 내장 timeout 예외
    if isinstance(exception, (asyncio.TimeoutError, TimeoutError)):
        return True

    # httpx timeout 예외
    if HTTPX_AVAILABLE and isinstance(exception, httpx.TimeoutException):
        return True

    # redis timeout 예외
    if REDIS_AVAILABLE and isinstance(exception, redis.exceptions.TimeoutError):
        return True

    return False


def classify_error(exception: Exception) -> UserFriendlyError:
    """
    예외를 분류하여 사용자 친화적 에러로 변환

    Args:
        exception: 발생한 예외

    Returns:
        UserFriendlyError
    """
    error_str = str(exception).lower()
    error_type = type(exception).__name__.lower()

    # 디버그 로깅: 실제 예외 정보 출력
    logger.debug(
        f"classify_error called: type={type(exception).__name__}, "
        f"message={str(exception)[:200]}"
    )

    # Timeout 에러 - 예외 타입 우선 확인 (문자열 매칭보다 우선)
    if _is_timeout_exception(exception):
        logger.info(f"Timeout exception detected: {type(exception).__name__}")
        return ERROR_MESSAGES["agent_timeout"]

    # Anthropic API 에러
    if "rate" in error_str and "limit" in error_str:
        return ERROR_MESSAGES["rate_limit_error"]
    if "api_key" in error_str or "authentication" in error_str:
        return ERROR_MESSAGES["invalid_api_key"]
    if "overloaded" in error_str:
        return ERROR_MESSAGES["overloaded_error"]
    if "invalid_request_error" in error_str or "all messages must have non-empty content" in error_str:
        return ERROR_MESSAGES["empty_message"]

    # DB 에러
    if "connection" in error_str and ("refused" in error_str or "failed" in error_str):
        return ERROR_MESSAGES["connection_error"]
    if "duplicate" in error_str or "unique" in error_str:
        return ERROR_MESSAGES["duplicate_key"]

    # 네트워크 에러 (timeout 문자열 매칭 제거 - 위에서 타입 기반으로 처리)
    if "connectionerror" in error_type or "networkerror" in error_type:
        return ERROR_MESSAGES["network_error"]

    # 기본 에러 - 기술적 세부사항 포함하여 디버깅 지원
    logger.warning(
        f"Unclassified exception: type={type(exception).__name__}, "
        f"message={str(exception)[:500]}"
    )
    return UserFriendlyError(
        category=ErrorCategory.INTERNAL,
        message_ko="예기치 않은 오류가 발생했습니다.",
        message_en="An unexpected error occurred.",
        suggestion_ko="문제가 지속되면 관리자에게 문의하세요.",
        suggestion_en="If the problem persists, please contact the administrator.",
        technical_detail=str(exception),
        http_status=500,
        retryable=False,
    )


def format_error_response(
    error: UserFriendlyError,
    lang: str = "ko",
    include_technical: bool = False,
) -> Dict[str, Any]:
    """
    에러를 API 응답 형식으로 포맷

    Args:
        error: UserFriendlyError
        lang: 언어 (ko 또는 en)
        include_technical: 기술적 세부사항 포함 여부

    Returns:
        에러 응답 딕셔너리
    """
    is_korean = lang.lower().startswith("ko")

    response = {
        "error": {
            "category": error.category.value,
            "message": error.message_ko if is_korean else error.message_en,
            "retryable": error.retryable,
        }
    }

    suggestion = error.suggestion_ko if is_korean else error.suggestion_en
    if suggestion:
        response["error"]["suggestion"] = suggestion

    if include_technical and error.technical_detail:
        response["error"]["detail"] = error.technical_detail

    return response


# ============================================================================
# Repository 패턴을 위한 추가 헬퍼 함수
# ============================================================================

def raise_not_found(resource: str, resource_id: Optional[str] = None):
    """
    404 Not Found 에러 발생

    Args:
        resource: 리소스 이름 (예: "User", "Workflow")
        resource_id: 리소스 ID (선택사항)
    """
    from fastapi import HTTPException
    detail = f"{resource} not found"
    if resource_id:
        detail += f": {resource_id}"
    raise HTTPException(status_code=404, detail=detail)


def raise_access_denied(resource: str, action: str = "access"):
    """
    403 Forbidden 에러 발생

    Args:
        resource: 리소스 이름
        action: 수행하려는 작업 (예: "modify", "delete")
    """
    from fastapi import HTTPException
    raise HTTPException(
        status_code=403,
        detail=f"You don't have permission to {action} this {resource}"
    )


def raise_validation_error(field: str, message: str):
    """
    400 Bad Request 에러 발생

    Args:
        field: 필드 이름
        message: 에러 메시지
    """
    from fastapi import HTTPException
    raise HTTPException(
        status_code=400,
        detail=f"Validation error in {field}: {message}"
    )


def require_resource(
    resource: Any,
    resource_name: str,
    resource_id: Optional[str] = None
) -> Any:
    """
    리소스 존재 확인 (없으면 404 에러)

    Args:
        resource: 확인할 리소스
        resource_name: 리소스 이름
        resource_id: 리소스 ID (선택사항)

    Returns:
        resource: 존재하는 경우 리소스 반환

    Raises:
        HTTPException: 리소스가 없는 경우 404
    """
    if not resource:
        raise_not_found(resource_name, resource_id)
    return resource


def require_ownership(
    resource: Any,
    user_id,  # UUID
    action: str = "access"
):
    """
    리소스 소유권 확인 (소유자가 아니면 403 에러)

    Args:
        resource: 확인할 리소스 (owner_id 속성 필요)
        user_id: 현재 사용자 ID
        action: 수행하려는 작업

    Raises:
        HTTPException: 소유자가 아닌 경우 403
    """
    if not hasattr(resource, 'owner_id'):
        return  # owner_id 속성이 없으면 검사하지 않음

    if resource.owner_id != user_id:
        resource_name = type(resource).__name__
        raise_access_denied(resource_name, action)


def require_tenant_access(
    resource: Any,
    tenant_id,  # UUID
    resource_name: str = "Resource",
) -> Any:
    """
    테넌트 접근 권한 확인 (권한 없으면 404 에러)

    Multi-tenant 환경에서 리소스가 현재 테넌트 소속인지 확인.
    보안상 403 대신 404를 반환하여 리소스 존재 여부 노출 방지.

    Args:
        resource: 확인할 리소스 (tenant_id 속성 필요)
        tenant_id: 현재 사용자의 테넌트 ID
        resource_name: 에러 메시지에 표시할 리소스 이름

    Returns:
        resource: 접근 권한이 있는 경우 리소스 반환

    Raises:
        HTTPException: 리소스가 없거나 테넌트가 다른 경우 404

    Usage:
        deployment = require_tenant_access(
            deployment_service.get(deployment_id),
            current_user.tenant_id,
            "배포"
        )
    """
    from fastapi import HTTPException

    if not resource:
        raise HTTPException(status_code=404, detail=f"{resource_name}을(를) 찾을 수 없습니다")

    if hasattr(resource, 'tenant_id') and resource.tenant_id != tenant_id:
        # 보안상 403 대신 404 반환 (리소스 존재 여부 노출 방지)
        raise HTTPException(status_code=404, detail=f"{resource_name}을(를) 찾을 수 없습니다")

    return resource


def handle_service_error(e: Exception, default_message: str = "처리 중 오류가 발생했습니다"):
    """
    서비스 레이어 에러를 HTTP 에러로 변환

    ValueError -> 400 Bad Request
    기타 -> 500 Internal Server Error

    Args:
        e: 발생한 예외
        default_message: 기본 에러 메시지

    Raises:
        HTTPException: 적절한 상태 코드와 메시지
    """
    from fastapi import HTTPException

    if isinstance(e, ValueError):
        raise HTTPException(status_code=400, detail=str(e))
    else:
        logger.error(f"Service error: {e}")
        raise HTTPException(status_code=500, detail=default_message)
