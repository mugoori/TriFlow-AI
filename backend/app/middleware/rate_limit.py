"""
Rate Limiting 미들웨어
Redis 기반 슬라이딩 윈도우 Rate Limiter
"""
import time
import logging
from typing import Tuple
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from app.services.cache_service import CacheService
from app.config import settings

logger = logging.getLogger(__name__)


# Rate Limit 설정 (경로 패턴 -> (max_requests, window_seconds))
RATE_LIMIT_RULES = {
    # 인증 엔드포인트 (공격 방지)
    "/api/v1/auth/login": (10, 60),  # 10 req/min
    "/api/v1/auth/register": (5, 60),  # 5 req/min
    "/api/v1/auth/refresh": (20, 60),  # 20 req/min
    "/api/v1/auth/google": (10, 60),  # 10 req/min

    # AI 에이전트 (비용 제한)
    "/api/v1/agents/chat": (30, 60),  # 30 req/min
    "/api/v1/agents/chat/stream": (30, 60),  # 30 req/min
    "/api/v1/agents/judgment": (30, 60),  # 30 req/min

    # RAG (임베딩 비용)
    "/api/v1/rag/search": (60, 60),  # 60 req/min
    "/api/v1/rag/documents": (30, 60),  # 30 req/min
}

# 기본 Rate Limit (위 규칙에 없는 경로)
DEFAULT_RATE_LIMIT = (100, 60)  # 100 req/min

# Rate Limit 제외 경로
EXCLUDED_PATHS = {
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/favicon.ico",
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate Limiting 미들웨어

    기능:
    - IP 기반 Rate Limiting
    - 엔드포인트별 다른 제한 설정
    - Redis 기반 슬라이딩 윈도우
    - X-RateLimit-* 응답 헤더
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # CORS 프리플라이트 요청(OPTIONS)은 Rate Limit 제외
        if request.method == "OPTIONS":
            return await call_next(request)

        # 제외 경로 체크
        if path in EXCLUDED_PATHS or path.startswith("/docs") or path.startswith("/redoc"):
            return await call_next(request)

        # 클라이언트 IP 추출
        client_ip = self._get_client_ip(request)

        # Rate Limit 규칙 찾기
        max_requests, window_seconds = self._get_rate_limit(path)

        # Rate Limit 키 생성
        rate_key = f"rate_limit:{client_ip}:{path}"

        # Rate Limit 체크
        allowed, remaining, reset_time = self._check_rate_limit(
            rate_key, max_requests, window_seconds
        )

        # Rate Limit 헤더 생성
        headers = {
            "X-RateLimit-Limit": str(max_requests),
            "X-RateLimit-Remaining": str(max(0, remaining)),
            "X-RateLimit-Reset": str(reset_time),
        }

        if not allowed:
            logger.warning(
                f"Rate limit exceeded: {client_ip} -> {path} "
                f"(limit: {max_requests}/{window_seconds}s)"
            )
            # CORS 헤더 추가 (브라우저가 429 응답을 받을 수 있도록)
            origin = request.headers.get("origin", "")
            if origin in settings.cors_origins_list:
                headers["Access-Control-Allow-Origin"] = origin
                headers["Access-Control-Allow-Credentials"] = "true"

            return JSONResponse(
                status_code=429,
                content={
                    "error": True,
                    "category": "rate_limit",
                    "message": "요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요.",
                    "retry_after": window_seconds,
                },
                headers=headers,
            )

        # 요청 처리
        response = await call_next(request)

        # Rate Limit 헤더 추가
        for key, value in headers.items():
            response.headers[key] = value

        return response

    def _get_client_ip(self, request: Request) -> str:
        """클라이언트 IP 추출 (프록시 고려)"""
        # X-Forwarded-For 헤더 (프록시/로드밸런서)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # 첫 번째 IP가 실제 클라이언트
            return forwarded_for.split(",")[0].strip()

        # X-Real-IP 헤더 (nginx)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # 직접 연결
        if request.client:
            return request.client.host

        return "unknown"

    def _get_rate_limit(self, path: str) -> Tuple[int, int]:
        """경로에 맞는 Rate Limit 규칙 반환"""
        # 정확한 경로 매칭
        if path in RATE_LIMIT_RULES:
            return RATE_LIMIT_RULES[path]

        # 접두사 매칭 (예: /api/v1/agents/chat/stream -> /api/v1/agents/chat)
        for rule_path, limits in RATE_LIMIT_RULES.items():
            if path.startswith(rule_path):
                return limits

        return DEFAULT_RATE_LIMIT

    def _check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> Tuple[bool, int, int]:
        """
        Rate Limit 체크

        Returns:
            (allowed, remaining, reset_time)
            - allowed: 요청 허용 여부
            - remaining: 남은 요청 수
            - reset_time: 리셋 시간 (Unix timestamp)
        """
        current_time = int(time.time())
        reset_time = current_time + window_seconds

        # CacheService.rate_limit() 사용
        allowed = CacheService.rate_limit(key, max_requests, window_seconds)

        if allowed:
            # 현재 사용량 조회
            current_count = CacheService.get(key)
            if current_count:
                try:
                    count = int(current_count)
                    remaining = max_requests - count
                except (ValueError, TypeError):
                    remaining = max_requests - 1
            else:
                remaining = max_requests - 1
        else:
            remaining = 0

        return allowed, remaining, reset_time
