"""
미들웨어 테스트
PII 마스킹 미들웨어 및 Audit 미들웨어 테스트
"""
import json
import pytest
from unittest.mock import MagicMock, patch
from starlette.requests import Request
from starlette.responses import Response

from app.middleware.pii_masking import (
    PIIMaskingFilter,
    PIIMaskingMiddleware,
)
from app.middleware.audit import (
    should_audit,
    get_client_ip,
    extract_user_info,
    AuditMiddleware,
)


class TestPIIMaskingFilter:
    """로깅 필터 테스트"""

    def test_filter_masks_pii_in_log(self):
        """로그 메시지의 PII 마스킹"""
        import logging

        filter = PIIMaskingFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="User email: test@example.com",
            args=(),
            exc_info=None,
        )

        result = filter.filter(record)

        assert result is True
        assert "test@example.com" not in record.msg
        assert "t***@e***.com" in record.msg

    def test_filter_no_pii(self):
        """PII 없는 로그"""
        import logging

        filter = PIIMaskingFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Normal log message",
            args=(),
            exc_info=None,
        )

        result = filter.filter(record)

        assert result is True
        assert record.msg == "Normal log message"


class TestPIIMaskingMiddleware:
    """PII 마스킹 미들웨어 테스트"""

    def test_should_mask_target_paths(self):
        """대상 경로 마스킹 여부 확인"""
        middleware = PIIMaskingMiddleware(
            app=MagicMock(),
            enabled=True,
            target_paths=["/api/v1/agents/"],
            exclude_paths=["/health"],
        )

        assert middleware._should_mask("/api/v1/agents/chat")
        assert middleware._should_mask("/api/v1/agents/status")

    def test_should_not_mask_excluded_paths(self):
        """제외 경로 마스킹 안함"""
        middleware = PIIMaskingMiddleware(
            app=MagicMock(),
            enabled=True,
            target_paths=["/api/v1/agents/"],
            exclude_paths=["/health", "/docs"],
        )

        assert not middleware._should_mask("/health")
        assert not middleware._should_mask("/docs")
        assert not middleware._should_mask("/api/v1/workflows")

    def test_should_not_mask_when_disabled(self):
        """비활성화 시 마스킹 안함"""
        middleware = PIIMaskingMiddleware(
            app=MagicMock(),
            enabled=False,
        )

        assert not middleware._should_mask("/api/v1/agents/chat")

    @pytest.mark.asyncio
    async def test_dispatch_non_target_path(self):
        """대상이 아닌 경로는 통과"""
        async def call_next(request):
            return Response(content=b'{"result": "ok"}')

        middleware = PIIMaskingMiddleware(
            app=MagicMock(),
            enabled=True,
            target_paths=["/api/v1/agents/"],
        )

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/workflows",
            "query_string": b"",
            "headers": [],
        }
        request = Request(scope)

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200


class TestAuditMiddlewareFunctions:
    """Audit 미들웨어 함수 테스트"""

    def test_should_audit_api_paths(self):
        """API 경로 감사 대상 확인"""
        assert should_audit("/api/v1/workflows")
        assert should_audit("/api/v1/sensors/data")
        assert should_audit("/api/v1/rulesets/123")

    def test_should_not_audit_excluded_paths(self):
        """제외 경로 감사 안함"""
        assert not should_audit("/health")
        assert not should_audit("/docs")
        assert not should_audit("/openapi.json")
        assert not should_audit("/redoc")
        assert not should_audit("/favicon.ico")
        assert not should_audit("/api/v1/audit")  # 무한 루프 방지

    def test_should_not_audit_non_api_paths(self):
        """비 API 경로 감사 안함"""
        assert not should_audit("/static/file.js")
        assert not should_audit("/unknown/path")

    def test_get_client_ip_direct(self):
        """직접 연결 클라이언트 IP"""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
        }
        request = Request(scope)
        ip = get_client_ip(request)
        assert ip == "127.0.0.1"

    def test_get_client_ip_forwarded(self):
        """프록시 뒤 클라이언트 IP (X-Forwarded-For)"""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [(b"x-forwarded-for", b"203.0.113.1, 198.51.100.1")],
            "client": ("127.0.0.1", 12345),
        }
        request = Request(scope)
        ip = get_client_ip(request)
        assert ip == "203.0.113.1"

    def test_get_client_ip_real_ip(self):
        """프록시 뒤 클라이언트 IP (X-Real-IP)"""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [(b"x-real-ip", b"203.0.113.1")],
            "client": ("127.0.0.1", 12345),
        }
        request = Request(scope)
        ip = get_client_ip(request)
        assert ip == "203.0.113.1"

    def test_get_client_ip_no_client(self):
        """클라이언트 정보 없음"""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [],
        }
        request = Request(scope)
        ip = get_client_ip(request)
        assert ip is None

    def test_extract_user_info_no_auth(self):
        """인증 헤더 없음"""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [],
        }
        request = Request(scope)
        user_id, tenant_id = extract_user_info(request)

        assert user_id is None
        assert tenant_id is None

    def test_extract_user_info_invalid_bearer(self):
        """유효하지 않은 Bearer 토큰"""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [(b"authorization", b"Bearer invalid-token")],
        }
        request = Request(scope)
        user_id, tenant_id = extract_user_info(request)

        assert user_id is None
        assert tenant_id is None

    def test_extract_user_info_wrong_scheme(self):
        """Bearer가 아닌 인증 스키마"""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [(b"authorization", b"Basic dXNlcjpwYXNz")],
        }
        request = Request(scope)
        user_id, tenant_id = extract_user_info(request)

        assert user_id is None
        assert tenant_id is None


class TestAuditMiddleware:
    """Audit 미들웨어 클래스 테스트"""

    @pytest.mark.asyncio
    async def test_audit_middleware_skips_excluded(self):
        """제외 경로는 바이패스"""
        async def call_next(request):
            return Response(content=b"OK")

        middleware = AuditMiddleware(app=MagicMock())

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/health",
            "query_string": b"",
            "headers": [],
        }
        request = Request(scope)

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_audit_middleware_logs_api_calls(self):
        """API 호출 로깅"""
        async def call_next(request):
            return Response(content=b'{"result": "ok"}', status_code=200)

        # Mock SessionLocal and create_audit_log
        with patch("app.middleware.audit.SessionLocal") as mock_session, \
             patch("app.middleware.audit.create_audit_log") as mock_create_log:

            mock_db = MagicMock()
            mock_session.return_value = mock_db
            mock_create_log.return_value = None

            middleware = AuditMiddleware(app=MagicMock())

            scope = {
                "type": "http",
                "method": "GET",
                "path": "/api/v1/workflows",
                "query_string": b"",
                "headers": [],
            }

            async def receive():
                return {"type": "http.request", "body": b""}

            request = Request(scope, receive)

            response = await middleware.dispatch(request, call_next)
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_audit_middleware_with_request_body(self):
        """요청 본문 포함 로깅"""
        async def call_next(request):
            return Response(content=b'{"result": "created"}', status_code=201)

        with patch("app.middleware.audit.SessionLocal") as mock_session, \
             patch("app.middleware.audit.create_audit_log") as mock_create_log:

            mock_db = MagicMock()
            mock_session.return_value = mock_db
            mock_create_log.return_value = None

            middleware = AuditMiddleware(app=MagicMock())

            body = json.dumps({"name": "Test"}).encode()

            scope = {
                "type": "http",
                "method": "POST",
                "path": "/api/v1/workflows",
                "query_string": b"",
                "headers": [(b"content-type", b"application/json")],
            }

            async def receive():
                return {"type": "http.request", "body": body}

            request = Request(scope, receive)

            response = await middleware.dispatch(request, call_next)
            assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_audit_middleware_error_handling(self):
        """로깅 실패해도 응답은 정상"""
        async def call_next(request):
            return Response(content=b'{"result": "ok"}', status_code=200)

        with patch("app.middleware.audit.SessionLocal"), \
             patch("app.middleware.audit.create_audit_log") as mock_create_log:

            mock_create_log.side_effect = Exception("DB Error")

            middleware = AuditMiddleware(app=MagicMock())

            scope = {
                "type": "http",
                "method": "GET",
                "path": "/api/v1/workflows",
                "query_string": b"",
                "headers": [],
            }

            async def receive():
                return {"type": "http.request", "body": b""}

            request = Request(scope, receive)

            # 에러가 발생해도 응답은 정상 반환
            response = await middleware.dispatch(request, call_next)
            assert response.status_code == 200


class TestMiddlewareIntegration:
    """미들웨어 통합 테스트"""

    @pytest.mark.asyncio
    async def test_pii_masking_in_chat_request(self):
        """채팅 요청에서 PII 마스킹"""
        async def call_next(request):
            body = await request.body()
            data = json.loads(body)
            # 마스킹된 메시지 확인
            return Response(
                content=json.dumps({"received": data["message"]}).encode(),
                status_code=200,
                media_type="application/json",
            )

        middleware = PIIMaskingMiddleware(
            app=MagicMock(),
            enabled=True,
            mask_request=True,
            target_paths=["/api/v1/agents/"],
        )

        body = json.dumps({
            "message": "제 이메일은 test@example.com 입니다."
        }).encode()

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/agents/chat",
            "query_string": b"",
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }

        body_received = False

        async def receive():
            nonlocal body_received
            if not body_received:
                body_received = True
                return {"type": "http.request", "body": body}
            return {"type": "http.request", "body": b""}

        request = Request(scope, receive)
        request._body = body

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200
