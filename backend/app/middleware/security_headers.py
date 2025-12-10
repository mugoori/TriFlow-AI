"""
보안 헤더 미들웨어
OWASP 권장 보안 헤더 설정
"""
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    보안 헤더 미들웨어

    추가되는 헤더:
    - X-Content-Type-Options: MIME 타입 스니핑 방지
    - X-Frame-Options: 클릭재킹 방지
    - X-XSS-Protection: XSS 필터 활성화
    - Referrer-Policy: Referrer 정보 제한
    - Permissions-Policy: 브라우저 기능 제한
    - Strict-Transport-Security: HTTPS 강제 (Production만)
    - Cache-Control: 민감 정보 캐싱 방지
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # 기본 보안 헤더
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 브라우저 기능 제한 (불필요한 API 비활성화)
        response.headers["Permissions-Policy"] = (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=()"
        )

        # HSTS (Production 환경에서만)
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # API 응답 캐싱 방지 (민감 정보 보호)
        path = request.url.path
        if path.startswith("/api/"):
            # 인증/민감 정보 API는 캐시 금지
            if any(sensitive in path for sensitive in [
                "/auth/", "/api-keys/", "/settings/", "/users/"
            ]):
                response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"

        return response
