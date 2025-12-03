"""
TriFlow AI - 에러 유틸리티
사용자 친화적 에러 메시지 및 에러 분류
"""
import logging
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass

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

    # 네트워크 에러
    if "timeout" in error_str or "timed out" in error_str:
        return ERROR_MESSAGES["agent_timeout"]
    if "connectionerror" in error_type or "networkerror" in error_type:
        return ERROR_MESSAGES["network_error"]

    # 기본 에러
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
