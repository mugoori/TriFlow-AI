"""
PII 마스킹 미들웨어 테스트
app/middleware/pii_masking.py의 PIIMaskingMiddleware 및 PIIMaskingFilter 테스트
"""
import pytest
import json
import logging
from unittest.mock import MagicMock, AsyncMock, patch

from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from starlette.testclient import TestClient
from fastapi import FastAPI


# ========== PIIMaskingFilter 테스트 ==========


class TestPIIMaskingFilter:
    """PIIMaskingFilter 테스트"""

    def test_filter_basic(self):
        """기본 필터링 동작"""
        from app.middleware.pii_masking import PIIMaskingFilter

        filter_obj = PIIMaskingFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="일반 메시지입니다.",
            args=(),
            exc_info=None,
        )

        result = filter_obj.filter(record)

        assert result is True
        assert record.msg == "일반 메시지입니다."

    def test_filter_masks_email(self):
        """이메일 마스킹"""
        from app.middleware.pii_masking import PIIMaskingFilter

        filter_obj = PIIMaskingFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="연락처: test@example.com 입니다.",
            args=(),
            exc_info=None,
        )

        result = filter_obj.filter(record)

        assert result is True
        assert "test@example.com" not in record.msg

    def test_filter_masks_phone(self):
        """전화번호 마스킹"""
        from app.middleware.pii_masking import PIIMaskingFilter

        filter_obj = PIIMaskingFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="전화: 010-1234-5678",
            args=(),
            exc_info=None,
        )

        result = filter_obj.filter(record)

        assert result is True
        assert "010-1234-5678" not in record.msg

    def test_filter_non_string_msg(self):
        """문자열이 아닌 메시지 처리"""
        from app.middleware.pii_masking import PIIMaskingFilter

        filter_obj = PIIMaskingFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg=123,  # int type
            args=(),
            exc_info=None,
        )

        result = filter_obj.filter(record)

        assert result is True
        assert record.msg == 123

    def test_filter_no_msg_attribute(self):
        """msg 속성 없는 경우"""
        from app.middleware.pii_masking import PIIMaskingFilter

        filter_obj = PIIMaskingFilter()
        record = MagicMock(spec=[])  # no 'msg' attribute

        result = filter_obj.filter(record)

        assert result is True


# ========== PIIMaskingMiddleware 초기화 테스트 ==========


class TestPIIMaskingMiddlewareInit:
    """PIIMaskingMiddleware 초기화 테스트"""

    def test_init_defaults(self):
        """기본 설정으로 초기화"""
        from app.middleware.pii_masking import PIIMaskingMiddleware

        app = MagicMock()
        middleware = PIIMaskingMiddleware(app)

        assert middleware.enabled is True
        assert middleware.mask_request is True
        assert middleware.mask_response is True
        assert "/api/v1/agents/" in middleware.target_paths
        assert "/health" in middleware.exclude_paths

    def test_init_custom_settings(self):
        """커스텀 설정으로 초기화"""
        from app.middleware.pii_masking import PIIMaskingMiddleware

        app = MagicMock()
        middleware = PIIMaskingMiddleware(
            app,
            enabled=False,
            mask_request=False,
            mask_response=False,
            target_paths=["/custom/path/"],
            exclude_paths=["/skip/"],
        )

        assert middleware.enabled is False
        assert middleware.mask_request is False
        assert middleware.mask_response is False
        assert "/custom/path/" in middleware.target_paths
        assert "/skip/" in middleware.exclude_paths


# ========== _should_mask 테스트 ==========


class TestShouldMask:
    """_should_mask 메서드 테스트"""

    def test_should_mask_disabled(self):
        """비활성화 시 마스킹 안함"""
        from app.middleware.pii_masking import PIIMaskingMiddleware

        app = MagicMock()
        middleware = PIIMaskingMiddleware(app, enabled=False)

        result = middleware._should_mask("/api/v1/agents/chat")

        assert result is False

    def test_should_mask_exclude_path(self):
        """제외 경로는 마스킹 안함"""
        from app.middleware.pii_masking import PIIMaskingMiddleware

        app = MagicMock()
        middleware = PIIMaskingMiddleware(app)

        assert middleware._should_mask("/health") is False
        assert middleware._should_mask("/docs") is False
        assert middleware._should_mask("/redoc") is False
        assert middleware._should_mask("/openapi.json") is False

    def test_should_mask_target_path(self):
        """대상 경로는 마스킹"""
        from app.middleware.pii_masking import PIIMaskingMiddleware

        app = MagicMock()
        middleware = PIIMaskingMiddleware(app)

        result = middleware._should_mask("/api/v1/agents/chat")

        assert result is True

    def test_should_mask_non_target_path(self):
        """대상이 아닌 경로는 마스킹 안함"""
        from app.middleware.pii_masking import PIIMaskingMiddleware

        app = MagicMock()
        middleware = PIIMaskingMiddleware(app)

        result = middleware._should_mask("/api/v1/workflows")

        assert result is False


# ========== dispatch 테스트 ==========


class TestDispatch:
    """dispatch 메서드 테스트"""

    @pytest.fixture
    def mock_app(self):
        """FastAPI 앱 Fixture"""
        app = FastAPI()

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        @app.post("/api/v1/agents/chat")
        async def chat(request: dict = None):
            return {"response": "Hello"}

        return app

    @pytest.mark.asyncio
    async def test_dispatch_skip_non_target_path(self):
        """대상 아닌 경로는 바로 통과"""
        from app.middleware.pii_masking import PIIMaskingMiddleware

        app = MagicMock()
        middleware = PIIMaskingMiddleware(app)

        mock_request = MagicMock()
        mock_request.url.path = "/health"

        mock_response = MagicMock()
        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(mock_request, call_next)

        call_next.assert_called_once_with(mock_request)
        assert result == mock_response

    @pytest.mark.asyncio
    async def test_dispatch_masks_post_request(self):
        """POST 요청 마스킹"""
        from app.middleware.pii_masking import PIIMaskingMiddleware

        app = MagicMock()
        middleware = PIIMaskingMiddleware(app)

        # Request body with PII
        body_content = json.dumps({"message": "연락처: 010-1234-5678"}).encode("utf-8")

        mock_request = MagicMock()
        mock_request.url.path = "/api/v1/agents/chat"
        mock_request.method = "POST"
        mock_request.headers = {"content-type": "application/json"}
        mock_request.body = AsyncMock(return_value=body_content)
        mock_request.scope = {"type": "http", "method": "POST", "path": "/api/v1/agents/chat"}
        mock_request._send = MagicMock()

        mock_response = MagicMock()
        mock_response.headers = {"content-type": "text/plain"}
        call_next = AsyncMock(return_value=mock_response)

        with patch.object(middleware, "_mask_request_body", new=AsyncMock(return_value=mock_request)):
            result = await middleware.dispatch(mock_request, call_next)

        assert result is not None


# ========== _mask_request_body 테스트 ==========


class TestMaskRequestBody:
    """_mask_request_body 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_mask_request_body_non_json(self):
        """JSON이 아닌 요청은 그대로"""
        from app.middleware.pii_masking import PIIMaskingMiddleware

        app = MagicMock()
        middleware = PIIMaskingMiddleware(app)

        mock_request = MagicMock()
        mock_request.headers = {"content-type": "text/plain"}

        result = await middleware._mask_request_body(mock_request)

        assert result == mock_request

    @pytest.mark.asyncio
    async def test_mask_request_body_empty(self):
        """빈 요청"""
        from app.middleware.pii_masking import PIIMaskingMiddleware

        app = MagicMock()
        middleware = PIIMaskingMiddleware(app)

        mock_request = MagicMock()
        mock_request.headers = {"content-type": "application/json"}
        mock_request.body = AsyncMock(return_value=b"")

        result = await middleware._mask_request_body(mock_request)

        assert result == mock_request

    @pytest.mark.asyncio
    async def test_mask_request_body_with_message(self):
        """메시지 필드 마스킹"""
        from app.middleware.pii_masking import PIIMaskingMiddleware

        app = MagicMock()
        middleware = PIIMaskingMiddleware(app)

        body_content = json.dumps({"message": "이메일: test@example.com"}).encode("utf-8")

        mock_request = MagicMock()
        mock_request.headers = MagicMock()
        mock_request.headers.get = MagicMock(return_value="application/json")
        mock_request.body = AsyncMock(return_value=body_content)
        mock_request.scope = {"type": "http", "method": "POST", "path": "/test"}
        mock_request._send = MagicMock()

        result = await middleware._mask_request_body(mock_request)

        assert isinstance(result, Request)

    @pytest.mark.asyncio
    async def test_mask_request_body_with_context(self):
        """context 필드 마스킹"""
        from app.middleware.pii_masking import PIIMaskingMiddleware

        app = MagicMock()
        middleware = PIIMaskingMiddleware(app)

        body_content = json.dumps({
            "message": "Hello",
            "context": {
                "user_info": "전화: 010-9999-8888"
            }
        }).encode("utf-8")

        mock_request = MagicMock()
        mock_request.headers = MagicMock()
        mock_request.headers.get = MagicMock(return_value="application/json")
        mock_request.body = AsyncMock(return_value=body_content)
        mock_request.scope = {"type": "http", "method": "POST", "path": "/test"}
        mock_request._send = MagicMock()

        result = await middleware._mask_request_body(mock_request)

        assert isinstance(result, Request)

    @pytest.mark.asyncio
    async def test_mask_request_body_invalid_json(self):
        """잘못된 JSON"""
        from app.middleware.pii_masking import PIIMaskingMiddleware

        app = MagicMock()
        middleware = PIIMaskingMiddleware(app)

        mock_request = MagicMock()
        mock_request.headers = MagicMock()
        mock_request.headers.get = MagicMock(return_value="application/json")
        mock_request.body = AsyncMock(return_value=b"not valid json{")
        mock_request.scope = {"type": "http", "method": "POST", "path": "/test"}
        mock_request._send = MagicMock()
        mock_request._body = b"not valid json{"

        result = await middleware._mask_request_body(mock_request)

        assert isinstance(result, Request)

    @pytest.mark.asyncio
    async def test_mask_request_body_exception(self):
        """예외 발생 시"""
        from app.middleware.pii_masking import PIIMaskingMiddleware

        app = MagicMock()
        middleware = PIIMaskingMiddleware(app)

        mock_request = MagicMock()
        mock_request.headers = MagicMock()
        mock_request.headers.get = MagicMock(side_effect=Exception("Test error"))

        result = await middleware._mask_request_body(mock_request)

        assert result == mock_request

    @pytest.mark.asyncio
    async def test_mask_request_body_cp949_encoding(self):
        """CP949 인코딩 처리"""
        from app.middleware.pii_masking import PIIMaskingMiddleware

        app = MagicMock()
        middleware = PIIMaskingMiddleware(app)

        # CP949로 인코딩된 한글 데이터 (UTF-8 디코딩 실패 케이스)
        body_content = '{"message": "테스트"}'.encode("cp949")

        mock_request = MagicMock()
        mock_request.headers = MagicMock()
        mock_request.headers.get = MagicMock(return_value="application/json")
        mock_request.body = AsyncMock(return_value=body_content)
        mock_request.scope = {"type": "http", "method": "POST", "path": "/test"}
        mock_request._send = MagicMock()

        result = await middleware._mask_request_body(mock_request)

        assert isinstance(result, Request)


# ========== _mask_response_body 테스트 ==========


class TestMaskResponseBody:
    """_mask_response_body 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_mask_response_body_streaming(self):
        """StreamingResponse는 그대로"""
        from app.middleware.pii_masking import PIIMaskingMiddleware

        app = MagicMock()
        middleware = PIIMaskingMiddleware(app)

        async def gen():
            yield b"data"

        response = StreamingResponse(gen())

        result = await middleware._mask_response_body(response)

        assert result == response

    @pytest.mark.asyncio
    async def test_mask_response_body_non_json(self):
        """JSON이 아닌 응답은 그대로"""
        from app.middleware.pii_masking import PIIMaskingMiddleware

        app = MagicMock()
        middleware = PIIMaskingMiddleware(app)

        response = MagicMock()
        response.headers = {"content-type": "text/html"}

        result = await middleware._mask_response_body(response)

        assert result == response

    @pytest.mark.asyncio
    async def test_mask_response_body_empty(self):
        """빈 응답"""
        from app.middleware.pii_masking import PIIMaskingMiddleware

        app = MagicMock()
        middleware = PIIMaskingMiddleware(app)

        async def body_iter():
            return
            yield  # make it a generator

        response = MagicMock()
        response.headers = {"content-type": "application/json"}
        response.body_iterator = body_iter()
        response.status_code = 200
        response.media_type = "application/json"

        result = await middleware._mask_response_body(response)

        assert isinstance(result, Response)

    @pytest.mark.asyncio
    async def test_mask_response_body_with_response_field(self):
        """response 필드 마스킹"""
        from app.middleware.pii_masking import PIIMaskingMiddleware

        app = MagicMock()
        middleware = PIIMaskingMiddleware(app)

        body_content = json.dumps({"response": "이메일: user@test.com"}).encode("utf-8")

        async def body_iter():
            yield body_content

        response = MagicMock()
        response.headers = {"content-type": "application/json"}
        response.body_iterator = body_iter()
        response.status_code = 200
        response.media_type = "application/json"

        result = await middleware._mask_response_body(response)

        assert isinstance(result, Response)
        # 응답 내용에 원본 이메일이 없어야 함
        result_body = result.body.decode("utf-8")
        assert "user@test.com" not in result_body

    @pytest.mark.asyncio
    async def test_mask_response_body_with_tool_calls(self):
        """tool_calls 필드 마스킹"""
        from app.middleware.pii_masking import PIIMaskingMiddleware

        app = MagicMock()
        middleware = PIIMaskingMiddleware(app)

        body_content = json.dumps({
            "tool_calls": [
                {
                    "name": "get_info",
                    "result": {"data": "전화: 010-1234-5678"}
                }
            ]
        }).encode("utf-8")

        async def body_iter():
            yield body_content

        response = MagicMock()
        response.headers = {"content-type": "application/json"}
        response.body_iterator = body_iter()
        response.status_code = 200
        response.media_type = "application/json"

        result = await middleware._mask_response_body(response)

        assert isinstance(result, Response)

    @pytest.mark.asyncio
    async def test_mask_response_body_invalid_json(self):
        """잘못된 JSON 응답"""
        from app.middleware.pii_masking import PIIMaskingMiddleware

        app = MagicMock()
        middleware = PIIMaskingMiddleware(app)

        async def body_iter():
            yield b"not valid json{"

        response = MagicMock()
        response.headers = {"content-type": "application/json"}
        response.body_iterator = body_iter()

        result = await middleware._mask_response_body(response)

        assert result == response

    @pytest.mark.asyncio
    async def test_mask_response_body_exception(self):
        """예외 발생 시"""
        from app.middleware.pii_masking import PIIMaskingMiddleware

        app = MagicMock()
        middleware = PIIMaskingMiddleware(app)

        response = MagicMock()
        response.headers = {"content-type": "application/json"}

        async def error_iter():
            raise Exception("Test error")
            yield  # make it a generator

        response.body_iterator = error_iter()

        result = await middleware._mask_response_body(response)

        assert result == response

    @pytest.mark.asyncio
    async def test_mask_response_body_no_pii(self):
        """PII 없는 응답"""
        from app.middleware.pii_masking import PIIMaskingMiddleware

        app = MagicMock()
        middleware = PIIMaskingMiddleware(app)

        body_content = json.dumps({"response": "안녕하세요!"}).encode("utf-8")

        async def body_iter():
            yield body_content

        response = MagicMock()
        response.headers = {"content-type": "application/json"}
        response.body_iterator = body_iter()
        response.status_code = 200
        response.media_type = "application/json"

        result = await middleware._mask_response_body(response)

        assert isinstance(result, Response)
        # 원본과 동일해야 함
        assert result.body == body_content


# ========== 통합 테스트 ==========


class TestMiddlewareIntegration:
    """미들웨어 통합 테스트"""

    def test_middleware_with_fastapi_app(self):
        """FastAPI 앱과 통합"""
        from app.middleware.pii_masking import PIIMaskingMiddleware

        app = FastAPI()
        app.add_middleware(PIIMaskingMiddleware)

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_middleware_non_target_post(self):
        """대상 아닌 경로 POST"""
        from app.middleware.pii_masking import PIIMaskingMiddleware

        app = FastAPI()
        app.add_middleware(PIIMaskingMiddleware)

        @app.post("/api/v1/workflows")
        async def create_workflow(data: dict):
            return data

        client = TestClient(app)
        response = client.post(
            "/api/v1/workflows",
            json={"name": "test", "email": "test@example.com"},
        )

        assert response.status_code == 200
        # 마스킹되지 않음 (대상 경로 아님)
        assert response.json()["email"] == "test@example.com"


# ========== 로깅 필터 설정 테스트 ==========


class TestLoggingFilterSetup:
    """로깅 필터 설정 테스트"""

    def test_setup_logging_filter(self):
        """로깅 필터 설정"""
        from app.middleware.pii_masking import PIIMaskingMiddleware, PIIMaskingFilter

        app = MagicMock()
        middleware = PIIMaskingMiddleware(app)

        # 루트 로거에 필터가 추가되었는지 확인
        root_logger = logging.getLogger()
        pii_filters = [f for f in root_logger.filters if isinstance(f, PIIMaskingFilter)]

        assert len(pii_filters) >= 1
