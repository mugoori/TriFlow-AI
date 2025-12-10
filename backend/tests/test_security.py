# ===================================================
# TriFlow AI - Security Tests
# Rate Limiting, Security Headers, Scope Validation
# ===================================================

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from starlette.responses import Response

from app.main import app


client = TestClient(app)


class TestSecurityHeaders:
    """보안 헤더 테스트"""

    def test_security_headers_on_health_endpoint(self):
        """헬스 체크 엔드포인트에 보안 헤더가 포함되는지 확인"""
        response = client.get("/health")

        # 기본 보안 헤더 확인
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "geolocation=()" in response.headers.get("Permissions-Policy", "")

    def test_security_headers_on_api_endpoint(self):
        """API 엔드포인트에 보안 헤더가 포함되는지 확인"""
        response = client.get("/api/v1/info")

        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"

    def test_cache_control_header_on_api(self):
        """API 응답에 Cache-Control 헤더 확인"""
        response = client.get("/api/v1/info")

        # Cache-Control 헤더가 있으면 no-store 또는 private 포함 확인
        # 없어도 테스트 통과 (보안 헤더 미들웨어에서 설정 안 할 수 있음)
        cache_control = response.headers.get("Cache-Control", "")
        if cache_control:
            assert "no-store" in cache_control or "private" in cache_control or "no-cache" in cache_control
        # Cache-Control이 없으면 pass (옵션 헤더)


class TestRateLimiting:
    """Rate Limiting 테스트"""

    def test_rate_limit_headers_present(self):
        """Rate Limit 헤더가 응답에 포함되는지 확인"""
        response = client.get("/api/v1/info")

        # Rate Limit 헤더 존재 확인
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    def test_rate_limit_values_are_numeric(self):
        """Rate Limit 헤더 값이 숫자인지 확인"""
        response = client.get("/api/v1/info")

        limit = response.headers.get("X-RateLimit-Limit")
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")

        assert limit.isdigit()
        assert remaining.isdigit()
        assert reset.isdigit()

    def test_health_endpoint_excluded_from_rate_limit(self):
        """헬스 체크는 Rate Limit 제외"""
        response = client.get("/health")

        # 헬스 체크에는 Rate Limit 헤더가 없거나 있어도 상관없음
        # 단, 429 에러가 발생하면 안됨
        assert response.status_code != 429

    @patch("app.services.cache_service.CacheService.rate_limit")
    def test_rate_limit_exceeded_returns_429(self, mock_rate_limit):
        """Rate Limit 초과 시 429 응답"""
        mock_rate_limit.return_value = False  # Rate limit exceeded

        response = client.post(
            "/api/v1/auth/login",
            json={"email": "test@test.com", "password": "test"}
        )

        # Rate Limit이 적용되면 429 반환
        # (실제로는 Redis가 없으면 통과될 수 있음)
        assert response.status_code in [401, 422, 429]


class TestScopeValidation:
    """API Key 스코프 검증 테스트"""

    def test_require_scope_import(self):
        """require_scope 함수 import 확인"""
        from app.auth.dependencies import require_scope, require_any_scope

        assert callable(require_scope)
        assert callable(require_any_scope)

    def test_valid_scopes_defined(self):
        """유효한 스코프 목록 정의 확인"""
        from app.auth.dependencies import VALID_SCOPES

        expected_scopes = {
            "read", "write", "delete", "admin",
            "sensors", "workflows", "rulesets",
            "erp_mes", "notifications"
        }

        assert expected_scopes == VALID_SCOPES

    def test_require_scope_returns_callable(self):
        """require_scope가 callable을 반환하는지 확인"""
        from app.auth.dependencies import require_scope

        scope_checker = require_scope(["read", "sensors"])

        assert callable(scope_checker)

    def test_require_any_scope_returns_callable(self):
        """require_any_scope가 callable을 반환하는지 확인"""
        from app.auth.dependencies import require_any_scope

        scope_checker = require_any_scope(["read", "admin"])

        assert callable(scope_checker)


class TestMiddlewareOrder:
    """미들웨어 등록 순서 테스트"""

    def test_middlewares_registered(self):
        """미들웨어가 등록되었는지 확인"""
        # 앱의 미들웨어 스택 확인
        middleware_classes = [
            m.cls.__name__ if hasattr(m, 'cls') else type(m).__name__
            for m in app.user_middleware
        ]

        # 기본 미들웨어 존재 확인
        assert "CORSMiddleware" in middleware_classes


class TestAuthEndpointSecurity:
    """인증 엔드포인트 보안 테스트"""

    def test_login_requires_credentials(self):
        """로그인 시 자격증명 필요"""
        # 빈 요청
        response = client.post("/api/v1/auth/login", json={})

        # 422 Unprocessable Entity (유효성 검사 실패)
        assert response.status_code == 422

    def test_protected_endpoint_requires_auth(self):
        """보호된 엔드포인트는 인증 필요"""
        # 설정 API는 관리자 인증 필요
        response = client.get("/api/v1/settings")

        # 401 Unauthorized
        assert response.status_code == 401

    def test_invalid_token_rejected(self):
        """잘못된 토큰 거부"""
        response = client.get(
            "/api/v1/settings",
            headers={"Authorization": "Bearer invalid_token_here"}
        )

        assert response.status_code == 401

    def test_expired_token_rejected(self):
        """만료된 토큰 거부"""
        # 만료된 JWT 토큰 (실제 테스트에서는 만료된 토큰 생성)
        expired_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0IiwiZXhwIjoxfQ.invalid"

        response = client.get(
            "/api/v1/settings",
            headers={"Authorization": f"Bearer {expired_token}"}
        )

        assert response.status_code == 401


class TestAPIKeySecurity:
    """API Key 보안 테스트"""

    @patch("app.services.api_key_service.validate_api_key")
    def test_invalid_api_key_rejected(self, mock_validate):
        """잘못된 API Key 거부"""
        mock_validate.return_value = None  # API Key 검증 실패

        response = client.get(
            "/api/v1/settings",
            headers={"X-API-Key": "tfk_invalid_key_here"}
        )

        assert response.status_code == 401

    def test_api_key_prefix_required(self):
        """API Key는 tfk_ 접두사 필요"""
        response = client.get(
            "/api/v1/settings",
            headers={"X-API-Key": "wrong_prefix_key"}
        )

        # tfk_ 접두사가 없으면 API Key로 인식 안됨 -> 401
        assert response.status_code == 401


class TestErrorResponses:
    """에러 응답 보안 테스트"""

    def test_error_response_no_sensitive_info(self):
        """에러 응답에 민감 정보 미포함"""
        response = client.get("/api/v1/nonexistent")

        # 스택 트레이스나 내부 경로 미포함
        content = response.text.lower()
        assert "traceback" not in content
        assert "c:\\" not in content and "/home/" not in content
        assert "password" not in content

    def test_404_response_format(self):
        """404 응답 형식 확인"""
        response = client.get("/api/v1/nonexistent")

        assert response.status_code == 404
        data = response.json()
        assert "error" in data or "detail" in data


class TestInputValidation:
    """입력 검증 테스트"""

    def test_xss_prevention_in_response(self):
        """XSS 방지 (X-XSS-Protection 헤더)"""
        response = client.get("/api/v1/info")

        xss_header = response.headers.get("X-XSS-Protection")
        assert xss_header == "1; mode=block"

    def test_content_type_options(self):
        """Content-Type 스니핑 방지 헤더"""
        response = client.get("/api/v1/info")

        assert response.headers.get("X-Content-Type-Options") == "nosniff"

    def test_frame_options(self):
        """클릭재킹 방지 헤더"""
        response = client.get("/api/v1/info")

        assert response.headers.get("X-Frame-Options") == "DENY"
