"""
MCP Proxy 테스트

MCP 서버 호출 프록시 및 에러 처리 테스트
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import httpx


class TestMCPExceptions:
    """MCP 예외 클래스 테스트"""

    def test_mcp_error_base(self):
        """MCPError 기본 예외"""
        from app.services.mcp_proxy import MCPError

        error = MCPError("Test error")
        assert str(error) == "Test error"

    def test_mcp_timeout_error(self):
        """MCPTimeoutError 예외"""
        from app.services.mcp_proxy import MCPTimeoutError

        server_id = str(uuid4())
        timeout_ms = 5000
        error = MCPTimeoutError(server_id=server_id, timeout_ms=timeout_ms)

        assert error.server_id == server_id
        assert error.timeout_ms == timeout_ms
        assert "timeout" in str(error).lower()

    def test_mcp_http_error(self):
        """MCPHTTPError 예외"""
        from app.services.mcp_proxy import MCPHTTPError

        server_id = str(uuid4())
        error = MCPHTTPError(server_id=server_id, status_code=500, detail="Internal Server Error")

        assert error.server_id == server_id
        assert error.status_code == 500
        assert error.detail == "Internal Server Error"

    def test_mcp_http_error_no_detail(self):
        """MCPHTTPError 예외 (상세 없음)"""
        from app.services.mcp_proxy import MCPHTTPError

        server_id = str(uuid4())
        error = MCPHTTPError(server_id=server_id, status_code=404)

        assert error.detail is None

    def test_mcp_protocol_error(self):
        """MCPProtocolError 예외"""
        from app.services.mcp_proxy import MCPProtocolError

        server_id = str(uuid4())
        error = MCPProtocolError(
            server_id=server_id,
            error_code=-32600,
            error_message="Invalid Request",
        )

        assert error.server_id == server_id
        assert error.error_code == -32600
        assert error.error_message == "Invalid Request"

    def test_circuit_breaker_open_error(self):
        """CircuitBreakerOpenError 예외"""
        from app.services.mcp_proxy import CircuitBreakerOpenError

        server_id = str(uuid4())
        error = CircuitBreakerOpenError(server_id=server_id)

        assert error.server_id == server_id
        assert "OPEN" in str(error)


class TestAuthType:
    """인증 타입 테스트"""

    def test_api_key_auth(self):
        """API Key 인증"""
        from app.models.mcp import AuthType

        assert AuthType.API_KEY.value == "api_key"

    def test_oauth2_auth(self):
        """OAuth2 인증"""
        from app.models.mcp import AuthType

        assert AuthType.OAUTH2.value == "oauth2"

    def test_basic_auth(self):
        """Basic 인증"""
        from app.models.mcp import AuthType

        assert AuthType.BASIC.value == "basic"

    def test_none_auth(self):
        """인증 없음"""
        from app.models.mcp import AuthType

        assert AuthType.NONE.value == "none"


class TestMCPCallStatus:
    """MCPCallStatus 테스트"""

    def test_success_status(self):
        """성공 상태"""
        from app.models.mcp import MCPCallStatus

        assert MCPCallStatus.SUCCESS.value == "success"

    def test_failure_status(self):
        """실패 상태"""
        from app.models.mcp import MCPCallStatus

        assert MCPCallStatus.FAILURE.value == "failure"

    def test_timeout_status(self):
        """타임아웃 상태"""
        from app.models.mcp import MCPCallStatus

        assert MCPCallStatus.TIMEOUT.value == "timeout"

    def test_circuit_open_status(self):
        """Circuit Open 상태"""
        from app.models.mcp import MCPCallStatus

        assert MCPCallStatus.CIRCUIT_OPEN.value == "circuit_open"


class TestMCPCallResponse:
    """MCPCallResponse 테스트"""

    def test_success_response(self):
        """성공 응답"""
        from app.models.mcp import MCPCallResponse, MCPCallStatus

        # MCPCallResponse requires request_id and latency_ms
        response = MCPCallResponse(
            request_id="req-123",
            status=MCPCallStatus.SUCCESS,
            result={"data": "test"},
            latency_ms=150,
        )

        assert response.status == MCPCallStatus.SUCCESS
        assert response.result["data"] == "test"
        assert response.latency_ms == 150

    def test_error_response(self):
        """에러 응답"""
        from app.models.mcp import MCPCallResponse, MCPCallStatus

        response = MCPCallResponse(
            request_id="req-456",
            status=MCPCallStatus.FAILURE,
            error_code="-32600",  # error_code is string
            error_message="Invalid Request",
            latency_ms=50,
        )

        assert response.status == MCPCallStatus.FAILURE
        assert response.error_code == "-32600"

    def test_timeout_response(self):
        """타임아웃 응답"""
        from app.models.mcp import MCPCallResponse, MCPCallStatus

        response = MCPCallResponse(
            request_id="req-789",
            status=MCPCallStatus.TIMEOUT,
            error_message="Request timeout",
            latency_ms=5000,
        )

        assert response.status == MCPCallStatus.TIMEOUT


class TestJSONRPCFormat:
    """JSON-RPC 2.0 형식 테스트"""

    def test_request_format(self):
        """요청 형식"""
        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "get_weather",
                "arguments": {"city": "Seoul"},
            },
            "id": "1",
        }

        assert request["jsonrpc"] == "2.0"
        assert request["method"] == "tools/call"
        assert "id" in request

    def test_success_response_format(self):
        """성공 응답 형식"""
        response = {
            "jsonrpc": "2.0",
            "result": {"weather": "sunny"},
            "id": "1",
        }

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        assert "error" not in response

    def test_error_response_format(self):
        """에러 응답 형식"""
        response = {
            "jsonrpc": "2.0",
            "error": {
                "code": -32600,
                "message": "Invalid Request",
            },
            "id": "1",
        }

        assert "error" in response
        assert response["error"]["code"] == -32600


class TestMCPProxyConstants:
    """MCP Proxy 상수 테스트"""

    def test_default_timeout(self):
        """기본 타임아웃"""
        default_timeout_ms = 30000  # 30초
        assert default_timeout_ms > 0

    def test_max_retries(self):
        """최대 재시도 횟수"""
        max_retries = 3
        assert max_retries > 0


class TestExponentialBackoff:
    """Exponential Backoff 테스트"""

    def test_backoff_calculation(self):
        """백오프 계산"""
        base_delay = 1.0  # 초
        max_delay = 32.0  # 초

        delays = []
        for attempt in range(5):
            delay = min(base_delay * (2 ** attempt), max_delay)
            delays.append(delay)

        assert delays == [1.0, 2.0, 4.0, 8.0, 16.0]

    def test_backoff_with_max(self):
        """최대 지연 제한"""
        base_delay = 1.0
        max_delay = 10.0

        for attempt in range(10):
            delay = min(base_delay * (2 ** attempt), max_delay)
            assert delay <= max_delay


class TestAuthHeaderGeneration:
    """인증 헤더 생성 테스트"""

    def test_api_key_header(self):
        """API Key 헤더"""
        api_key = "test_api_key_12345"
        headers = {"X-API-Key": api_key}

        assert headers["X-API-Key"] == api_key

    def test_bearer_token_header(self):
        """Bearer 토큰 헤더"""
        token = "oauth_access_token_xyz"
        headers = {"Authorization": f"Bearer {token}"}

        assert "Bearer" in headers["Authorization"]
        assert token in headers["Authorization"]

    def test_basic_auth_header(self):
        """Basic 인증 헤더"""
        import base64

        username = "user"
        password = "pass"
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        headers = {"Authorization": f"Basic {credentials}"}

        assert "Basic" in headers["Authorization"]


class TestRequestValidation:
    """요청 유효성 검사 테스트"""

    def test_valid_tool_name(self):
        """유효한 도구 이름"""
        tool_name = "get_weather"
        assert len(tool_name) > 0
        assert "/" not in tool_name or tool_name.startswith("tools/")

    def test_valid_arguments(self):
        """유효한 인자"""
        arguments = {"city": "Seoul", "unit": "celsius"}
        assert isinstance(arguments, dict)


class TestResponseParsing:
    """응답 파싱 테스트"""

    def test_parse_success_response(self):
        """성공 응답 파싱"""
        response_data = {
            "jsonrpc": "2.0",
            "result": {"temperature": 25},
            "id": "1",
        }

        assert "result" in response_data
        result = response_data["result"]
        assert result["temperature"] == 25

    def test_parse_error_response(self):
        """에러 응답 파싱"""
        response_data = {
            "jsonrpc": "2.0",
            "error": {
                "code": -32602,
                "message": "Invalid params",
            },
            "id": "1",
        }

        assert "error" in response_data
        error = response_data["error"]
        assert error["code"] == -32602

    def test_parse_null_result(self):
        """null 결과 파싱"""
        response_data = {
            "jsonrpc": "2.0",
            "result": None,
            "id": "1",
        }

        assert "result" in response_data
        assert response_data["result"] is None


class TestLatencyMeasurement:
    """지연 시간 측정 테스트"""

    def test_latency_calculation(self):
        """지연 시간 계산"""
        from datetime import datetime, timedelta

        start = datetime.now(timezone.utc)
        # Simulate some work
        end = start + timedelta(milliseconds=150)

        latency_ms = (end - start).total_seconds() * 1000
        assert latency_ms == 150.0

    def test_latency_in_response(self):
        """응답 내 지연 시간"""
        from app.models.mcp import MCPCallResponse, MCPCallStatus

        response = MCPCallResponse(
            request_id="latency-test",
            status=MCPCallStatus.SUCCESS,
            result={"data": "test"},
            latency_ms=250,
        )

        assert response.latency_ms == 250


class TestServerConfiguration:
    """서버 설정 테스트"""

    def test_server_endpoint(self):
        """서버 엔드포인트"""
        endpoint = "https://mcp.example.com/v1"
        assert endpoint.startswith("https://")

    def test_server_with_port(self):
        """포트 포함 서버"""
        endpoint = "http://localhost:8080/mcp"
        assert ":8080" in endpoint


class TestErrorHandlingStrategies:
    """에러 처리 전략 테스트"""

    def test_retryable_errors(self):
        """재시도 가능 에러"""
        retryable_status_codes = [429, 500, 502, 503, 504]
        status_code = 503

        is_retryable = status_code in retryable_status_codes
        assert is_retryable is True

    def test_non_retryable_errors(self):
        """재시도 불가 에러"""
        retryable_status_codes = [429, 500, 502, 503, 504]
        status_code = 400  # Bad Request

        is_retryable = status_code in retryable_status_codes
        assert is_retryable is False


class TestRequestIdGeneration:
    """요청 ID 생성 테스트"""

    def test_uuid_request_id(self):
        """UUID 요청 ID"""
        import uuid

        request_id = str(uuid.uuid4())
        assert len(request_id) == 36
        assert "-" in request_id

    def test_unique_request_ids(self):
        """고유 요청 ID"""
        import uuid

        ids = [str(uuid.uuid4()) for _ in range(10)]
        unique_ids = set(ids)

        assert len(unique_ids) == 10


class TestMCPServerModel:
    """MCPServer 모델 테스트"""

    def test_server_creation(self):
        """서버 생성"""
        from app.models.mcp import MCPServer, AuthType

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Test MCP Server",
            base_url="https://mcp.example.com",  # use base_url not endpoint
            auth_type=AuthType.API_KEY,
            created_at=now,
            updated_at=now,
        )

        assert server.name == "Test MCP Server"
        assert server.base_url == "https://mcp.example.com"

    def test_server_with_timeout(self):
        """타임아웃 설정 서버"""
        from app.models.mcp import MCPServer, AuthType

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Fast Server",
            base_url="https://fast.mcp.com",
            auth_type=AuthType.NONE,
            timeout_ms=5000,
            created_at=now,
            updated_at=now,
        )

        assert server.timeout_ms == 5000


class TestHTTPMCPProxyInit:
    """HTTPMCPProxy 초기화 테스트"""

    def test_init_with_defaults(self):
        """기본값으로 초기화"""
        from app.services.mcp_proxy import HTTPMCPProxy

        proxy = HTTPMCPProxy()

        assert proxy.circuit_breaker is None
        assert proxy.redis is None
        assert proxy._http_client is None
        assert proxy._owns_client is True

    def test_init_with_circuit_breaker(self):
        """Circuit Breaker 포함 초기화"""
        from app.services.mcp_proxy import HTTPMCPProxy

        mock_cb = MagicMock()
        proxy = HTTPMCPProxy(circuit_breaker=mock_cb)

        assert proxy.circuit_breaker == mock_cb

    def test_init_with_redis(self):
        """Redis 포함 초기화"""
        from app.services.mcp_proxy import HTTPMCPProxy

        mock_redis = MagicMock()
        proxy = HTTPMCPProxy(redis=mock_redis)

        assert proxy.redis == mock_redis

    def test_init_with_http_client(self):
        """HTTP 클라이언트 포함 초기화"""
        from app.services.mcp_proxy import HTTPMCPProxy

        mock_client = MagicMock()
        proxy = HTTPMCPProxy(http_client=mock_client)

        assert proxy._http_client == mock_client
        assert proxy._owns_client is False


class TestHTTPMCPProxyContextManager:
    """HTTPMCPProxy 컨텍스트 매니저 테스트"""

    @pytest.mark.asyncio
    async def test_aenter_creates_client(self):
        """__aenter__가 클라이언트 생성"""
        from app.services.mcp_proxy import HTTPMCPProxy

        proxy = HTTPMCPProxy()
        assert proxy._http_client is None

        async with proxy as p:
            assert p._http_client is not None
            assert isinstance(p._http_client, httpx.AsyncClient)

    @pytest.mark.asyncio
    async def test_aexit_closes_client(self):
        """__aexit__가 클라이언트 닫음"""
        from app.services.mcp_proxy import HTTPMCPProxy

        proxy = HTTPMCPProxy()

        async with proxy:
            pass

        # Client should be closed but may still exist
        # We just verify no exception is raised

    @pytest.mark.asyncio
    async def test_aenter_with_existing_client(self):
        """기존 클라이언트 있으면 생성 안함"""
        from app.services.mcp_proxy import HTTPMCPProxy

        mock_client = AsyncMock()
        proxy = HTTPMCPProxy(http_client=mock_client)

        async with proxy as p:
            assert p._http_client == mock_client


class TestHTTPMCPProxyClientProperty:
    """HTTPMCPProxy client 속성 테스트"""

    def test_client_creates_if_none(self):
        """클라이언트 없으면 생성"""
        from app.services.mcp_proxy import HTTPMCPProxy

        proxy = HTTPMCPProxy()
        assert proxy._http_client is None

        client = proxy.client
        assert client is not None
        assert isinstance(client, httpx.AsyncClient)

    def test_client_returns_existing(self):
        """기존 클라이언트 반환"""
        from app.services.mcp_proxy import HTTPMCPProxy

        mock_client = MagicMock()
        proxy = HTTPMCPProxy(http_client=mock_client)

        client = proxy.client
        assert client == mock_client


class TestHTTPMCPProxyCallTool:
    """HTTPMCPProxy call_tool 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_call_tool_circuit_open(self):
        """Circuit Breaker OPEN 시 호출 거부"""
        from app.services.mcp_proxy import HTTPMCPProxy
        from app.models.mcp import MCPServer, AuthType, MCPCallStatus

        mock_cb = AsyncMock()
        mock_cb.is_open.return_value = True

        proxy = HTTPMCPProxy(circuit_breaker=mock_cb)

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Test Server",
            base_url="https://mcp.test.com",
            auth_type=AuthType.NONE,
            timeout_ms=5000,
            created_at=now,
            updated_at=now,
        )

        result = await proxy.call_tool(server, "test_tool", {"arg": "value"})

        assert result.status == MCPCallStatus.CIRCUIT_OPEN
        assert "OPEN" in result.error_message

    @pytest.mark.asyncio
    async def test_call_tool_success(self):
        """call_tool 성공"""
        from app.services.mcp_proxy import HTTPMCPProxy
        from app.models.mcp import MCPServer, AuthType, MCPCallStatus

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"jsonrpc": "2.0", "result": {"data": "test"}, "id": "1"}
        mock_client.post.return_value = mock_response

        proxy = HTTPMCPProxy(http_client=mock_client)

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Test Server",
            base_url="https://mcp.test.com",
            auth_type=AuthType.NONE,
            timeout_ms=5000,
            created_at=now,
            updated_at=now,
        )

        result = await proxy.call_tool(server, "test_tool", {"arg": "value"})

        assert result.status == MCPCallStatus.SUCCESS
        assert result.result["data"] == "test"

    @pytest.mark.asyncio
    async def test_call_tool_timeout(self):
        """call_tool 타임아웃"""
        from app.services.mcp_proxy import HTTPMCPProxy
        from app.models.mcp import MCPServer, AuthType, MCPCallStatus

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("Timeout")

        proxy = HTTPMCPProxy(http_client=mock_client)

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Test Server",
            base_url="https://mcp.test.com",
            auth_type=AuthType.NONE,
            timeout_ms=5000,
            retry_count=0,  # 재시도 없음
            created_at=now,
            updated_at=now,
        )

        result = await proxy.call_tool(server, "test_tool", {})

        assert result.status == MCPCallStatus.TIMEOUT

    @pytest.mark.asyncio
    async def test_call_tool_http_error_4xx_no_retry(self):
        """call_tool HTTP 4xx 에러는 재시도 안함"""
        from app.services.mcp_proxy import HTTPMCPProxy
        from app.models.mcp import MCPServer, AuthType, MCPCallStatus

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_client.post.return_value = mock_response

        proxy = HTTPMCPProxy(http_client=mock_client)

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Test Server",
            base_url="https://mcp.test.com",
            auth_type=AuthType.NONE,
            timeout_ms=5000,
            retry_count=3,
            created_at=now,
            updated_at=now,
        )

        result = await proxy.call_tool(server, "test_tool", {})

        assert result.status == MCPCallStatus.FAILURE
        # 4xx는 재시도 안하므로 1번만 호출
        assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_call_tool_protocol_error(self):
        """call_tool 프로토콜 에러"""
        from app.services.mcp_proxy import HTTPMCPProxy
        from app.models.mcp import MCPServer, AuthType, MCPCallStatus

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "error": {"code": -32600, "message": "Invalid Request"},
            "id": "1",
        }
        mock_client.post.return_value = mock_response

        proxy = HTTPMCPProxy(http_client=mock_client)

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Test Server",
            base_url="https://mcp.test.com",
            auth_type=AuthType.NONE,
            timeout_ms=5000,
            retry_count=3,
            created_at=now,
            updated_at=now,
        )

        result = await proxy.call_tool(server, "test_tool", {})

        assert result.status == MCPCallStatus.FAILURE
        assert "-32600" in result.error_code

    @pytest.mark.asyncio
    async def test_call_tool_with_retry_success(self):
        """call_tool 재시도 후 성공"""
        from app.services.mcp_proxy import HTTPMCPProxy
        from app.models.mcp import MCPServer, AuthType, MCPCallStatus

        mock_client = AsyncMock()

        # 첫 번째 호출은 실패, 두 번째는 성공
        mock_fail_response = MagicMock()
        mock_fail_response.status_code = 500
        mock_fail_response.text = "Internal Server Error"

        mock_success_response = MagicMock()
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = {"jsonrpc": "2.0", "result": {"ok": True}, "id": "1"}

        mock_client.post.side_effect = [mock_fail_response, mock_success_response]

        mock_cb = AsyncMock()
        mock_cb.is_open.return_value = False

        proxy = HTTPMCPProxy(http_client=mock_client, circuit_breaker=mock_cb)

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Test Server",
            base_url="https://mcp.test.com",
            auth_type=AuthType.NONE,
            timeout_ms=5000,
            retry_count=2,
            retry_delay_ms=100,  # 최소값
            created_at=now,
            updated_at=now,
        )

        result = await proxy.call_tool(server, "test_tool", {})

        assert result.status == MCPCallStatus.SUCCESS
        mock_cb.record_success.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_tool_all_retries_fail(self):
        """call_tool 모든 재시도 실패"""
        from app.services.mcp_proxy import HTTPMCPProxy
        from app.models.mcp import MCPServer, AuthType, MCPCallStatus

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("Timeout")

        mock_cb = AsyncMock()
        mock_cb.is_open.return_value = False

        proxy = HTTPMCPProxy(http_client=mock_client, circuit_breaker=mock_cb)

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Test Server",
            base_url="https://mcp.test.com",
            auth_type=AuthType.NONE,
            timeout_ms=5000,
            retry_count=2,
            retry_delay_ms=100,
            created_at=now,
            updated_at=now,
        )

        result = await proxy.call_tool(server, "test_tool", {})

        assert result.status == MCPCallStatus.TIMEOUT
        mock_cb.record_failure.assert_called_once()


class TestHTTPMCPProxyDoCall:
    """HTTPMCPProxy _do_call 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_do_call_request_error(self):
        """_do_call 요청 에러"""
        from app.services.mcp_proxy import HTTPMCPProxy, MCPHTTPError
        from app.models.mcp import MCPServer, AuthType

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.RequestError("Connection refused")

        proxy = HTTPMCPProxy(http_client=mock_client)

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Test Server",
            base_url="https://mcp.test.com",
            auth_type=AuthType.NONE,
            timeout_ms=5000,
            created_at=now,
            updated_at=now,
        )

        with pytest.raises(MCPHTTPError) as exc:
            await proxy._do_call(server, "test_tool", {}, "req-123")

        assert exc.value.status_code == 0

    @pytest.mark.asyncio
    async def test_do_call_json_parse_error(self):
        """_do_call JSON 파싱 에러"""
        from app.services.mcp_proxy import HTTPMCPProxy, MCPProtocolError
        from app.models.mcp import MCPServer, AuthType

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = Exception("Invalid JSON")
        mock_client.post.return_value = mock_response

        proxy = HTTPMCPProxy(http_client=mock_client)

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Test Server",
            base_url="https://mcp.test.com",
            auth_type=AuthType.NONE,
            timeout_ms=5000,
            created_at=now,
            updated_at=now,
        )

        with pytest.raises(MCPProtocolError) as exc:
            await proxy._do_call(server, "test_tool", {}, "req-123")

        assert exc.value.error_code == "PARSE_ERROR"


class TestHTTPMCPProxyBuildAuthHeaders:
    """HTTPMCPProxy _build_auth_headers 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_build_auth_headers_none(self):
        """인증 없음"""
        from app.services.mcp_proxy import HTTPMCPProxy
        from app.models.mcp import MCPServer, AuthType

        proxy = HTTPMCPProxy()

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Test Server",
            base_url="https://mcp.test.com",
            auth_type=AuthType.NONE,
            timeout_ms=5000,
            created_at=now,
            updated_at=now,
        )

        headers = await proxy._build_auth_headers(server)
        assert headers == {}

    @pytest.mark.asyncio
    async def test_build_auth_headers_api_key(self):
        """API Key 인증"""
        from app.services.mcp_proxy import HTTPMCPProxy
        from app.models.mcp import MCPServer, AuthType

        proxy = HTTPMCPProxy()

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Test Server",
            base_url="https://mcp.test.com",
            auth_type=AuthType.API_KEY,
            api_key="test-api-key-123",
            timeout_ms=5000,
            created_at=now,
            updated_at=now,
        )

        headers = await proxy._build_auth_headers(server)
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test-api-key-123"

    @pytest.mark.asyncio
    async def test_build_auth_headers_api_key_missing(self):
        """API Key 없음"""
        from app.services.mcp_proxy import HTTPMCPProxy
        from app.models.mcp import MCPServer, AuthType

        proxy = HTTPMCPProxy()

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Test Server",
            base_url="https://mcp.test.com",
            auth_type=AuthType.API_KEY,
            api_key=None,
            timeout_ms=5000,
            created_at=now,
            updated_at=now,
        )

        headers = await proxy._build_auth_headers(server)
        assert headers == {}

    @pytest.mark.asyncio
    async def test_build_auth_headers_basic(self):
        """Basic 인증"""
        from app.services.mcp_proxy import HTTPMCPProxy
        from app.models.mcp import MCPServer, AuthType, BasicAuthConfig
        import base64

        proxy = HTTPMCPProxy()

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Test Server",
            base_url="https://mcp.test.com",
            auth_type=AuthType.BASIC,
            basic_auth_config=BasicAuthConfig(username="user", password="pass"),
            timeout_ms=5000,
            created_at=now,
            updated_at=now,
        )

        headers = await proxy._build_auth_headers(server)
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")

        # 디코딩 확인
        encoded = headers["Authorization"].replace("Basic ", "")
        decoded = base64.b64decode(encoded).decode()
        assert decoded == "user:pass"

    @pytest.mark.asyncio
    async def test_build_auth_headers_basic_missing(self):
        """Basic 인증 설정 없음"""
        from app.services.mcp_proxy import HTTPMCPProxy
        from app.models.mcp import MCPServer, AuthType

        proxy = HTTPMCPProxy()

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Test Server",
            base_url="https://mcp.test.com",
            auth_type=AuthType.BASIC,
            basic_auth_config=None,
            timeout_ms=5000,
            created_at=now,
            updated_at=now,
        )

        headers = await proxy._build_auth_headers(server)
        assert headers == {}


class TestHTTPMCPProxyGetOAuthToken:
    """HTTPMCPProxy _get_oauth_token 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_get_oauth_token_no_config(self):
        """OAuth2 설정 없음"""
        from app.services.mcp_proxy import HTTPMCPProxy, MCPError
        from app.models.mcp import MCPServer, AuthType

        proxy = HTTPMCPProxy()

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Test Server",
            base_url="https://mcp.test.com",
            auth_type=AuthType.OAUTH2,
            oauth_config=None,
            timeout_ms=5000,
            created_at=now,
            updated_at=now,
        )

        with pytest.raises(MCPError, match="OAuth2 config not found"):
            await proxy._get_oauth_token(server)

    @pytest.mark.asyncio
    async def test_get_oauth_token_from_cache(self):
        """캐시된 토큰 반환"""
        from app.services.mcp_proxy import HTTPMCPProxy
        from app.models.mcp import MCPServer, AuthType, OAuth2Config

        mock_redis = AsyncMock()
        mock_redis.get.return_value = b"cached-token-123"

        proxy = HTTPMCPProxy(redis=mock_redis)

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Test Server",
            base_url="https://mcp.test.com",
            auth_type=AuthType.OAUTH2,
            oauth_config=OAuth2Config(
                token_url="https://auth.test.com/token",
                client_id="client-id",
                client_secret="client-secret",
            ),
            timeout_ms=5000,
            created_at=now,
            updated_at=now,
        )

        token = await proxy._get_oauth_token(server)

        assert token == "cached-token-123"
        mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_oauth_token_fresh_request(self):
        """새 토큰 요청"""
        from app.services.mcp_proxy import HTTPMCPProxy
        from app.models.mcp import MCPServer, AuthType, OAuth2Config

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "new-token-456", "expires_in": 3600}
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        proxy = HTTPMCPProxy(redis=mock_redis, http_client=mock_client)

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Test Server",
            base_url="https://mcp.test.com",
            auth_type=AuthType.OAUTH2,
            oauth_config=OAuth2Config(
                token_url="https://auth.test.com/token",
                client_id="client-id",
                client_secret="client-secret",
                scope="read write",
            ),
            timeout_ms=5000,
            created_at=now,
            updated_at=now,
        )

        token = await proxy._get_oauth_token(server)

        assert token == "new-token-456"
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_oauth_token_http_error(self):
        """OAuth2 HTTP 에러"""
        from app.services.mcp_proxy import HTTPMCPProxy, MCPError
        from app.models.mcp import MCPServer, AuthType, OAuth2Config

        mock_client = AsyncMock()

        # HTTPStatusError 발생
        mock_response = MagicMock()
        mock_response.status_code = 401
        error = httpx.HTTPStatusError("Unauthorized", request=MagicMock(), response=mock_response)
        mock_client.post.side_effect = error

        proxy = HTTPMCPProxy(http_client=mock_client)

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Test Server",
            base_url="https://mcp.test.com",
            auth_type=AuthType.OAUTH2,
            oauth_config=OAuth2Config(
                token_url="https://auth.test.com/token",
                client_id="client-id",
                client_secret="client-secret",
            ),
            timeout_ms=5000,
            created_at=now,
            updated_at=now,
        )

        with pytest.raises(MCPError, match="OAuth2 token request failed"):
            await proxy._get_oauth_token(server)

    @pytest.mark.asyncio
    async def test_get_oauth_token_request_error(self):
        """OAuth2 요청 에러"""
        from app.services.mcp_proxy import HTTPMCPProxy, MCPError
        from app.models.mcp import MCPServer, AuthType, OAuth2Config

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.RequestError("Connection refused")

        proxy = HTTPMCPProxy(http_client=mock_client)

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Test Server",
            base_url="https://mcp.test.com",
            auth_type=AuthType.OAUTH2,
            oauth_config=OAuth2Config(
                token_url="https://auth.test.com/token",
                client_id="client-id",
                client_secret="client-secret",
            ),
            timeout_ms=5000,
            created_at=now,
            updated_at=now,
        )

        with pytest.raises(MCPError, match="OAuth2 token request failed"):
            await proxy._get_oauth_token(server)

    @pytest.mark.asyncio
    async def test_get_oauth_token_missing_access_token(self):
        """OAuth2 응답에 access_token 없음"""
        from app.services.mcp_proxy import HTTPMCPProxy, MCPError
        from app.models.mcp import MCPServer, AuthType, OAuth2Config

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"token_type": "Bearer"}  # access_token 없음
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        proxy = HTTPMCPProxy(http_client=mock_client)

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Test Server",
            base_url="https://mcp.test.com",
            auth_type=AuthType.OAUTH2,
            oauth_config=OAuth2Config(
                token_url="https://auth.test.com/token",
                client_id="client-id",
                client_secret="client-secret",
            ),
            timeout_ms=5000,
            created_at=now,
            updated_at=now,
        )

        with pytest.raises(MCPError, match="missing access_token"):
            await proxy._get_oauth_token(server)


class TestHTTPMCPProxyHealthCheck:
    """HTTPMCPProxy health_check 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """헬스체크 성공"""
        from app.services.mcp_proxy import HTTPMCPProxy
        from app.models.mcp import MCPServer, AuthType

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.get.return_value = mock_response

        proxy = HTTPMCPProxy(http_client=mock_client)

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Test Server",
            base_url="https://mcp.test.com",
            auth_type=AuthType.NONE,
            timeout_ms=5000,
            created_at=now,
            updated_at=now,
        )

        is_healthy, latency_ms, error = await proxy.health_check(server)

        assert is_healthy is True
        assert latency_ms is not None
        assert error is None

    @pytest.mark.asyncio
    async def test_health_check_failure_status(self):
        """헬스체크 실패 (HTTP 상태)"""
        from app.services.mcp_proxy import HTTPMCPProxy
        from app.models.mcp import MCPServer, AuthType

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_client.get.return_value = mock_response

        proxy = HTTPMCPProxy(http_client=mock_client)

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Test Server",
            base_url="https://mcp.test.com",
            auth_type=AuthType.NONE,
            timeout_ms=5000,
            created_at=now,
            updated_at=now,
        )

        is_healthy, latency_ms, error = await proxy.health_check(server)

        assert is_healthy is False
        assert "503" in error

    @pytest.mark.asyncio
    async def test_health_check_timeout(self):
        """헬스체크 타임아웃"""
        from app.services.mcp_proxy import HTTPMCPProxy
        from app.models.mcp import MCPServer, AuthType

        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("Timeout")

        proxy = HTTPMCPProxy(http_client=mock_client)

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Test Server",
            base_url="https://mcp.test.com",
            auth_type=AuthType.NONE,
            timeout_ms=5000,
            created_at=now,
            updated_at=now,
        )

        is_healthy, latency_ms, error = await proxy.health_check(server)

        assert is_healthy is False
        assert error == "Timeout"

    @pytest.mark.asyncio
    async def test_health_check_exception(self):
        """헬스체크 예외"""
        from app.services.mcp_proxy import HTTPMCPProxy
        from app.models.mcp import MCPServer, AuthType

        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection refused")

        proxy = HTTPMCPProxy(http_client=mock_client)

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Test Server",
            base_url="https://mcp.test.com",
            auth_type=AuthType.NONE,
            timeout_ms=5000,
            created_at=now,
            updated_at=now,
        )

        is_healthy, latency_ms, error = await proxy.health_check(server)

        assert is_healthy is False
        assert "Connection refused" in error


class TestHTTPMCPProxyCallToolSync:
    """HTTPMCPProxy call_tool_sync 메서드 테스트"""

    def test_call_tool_sync_no_url(self):
        """서버 URL 없음"""
        from app.services.mcp_proxy import HTTPMCPProxy

        proxy = HTTPMCPProxy()

        # URL이 없는 서버
        server = MagicMock()
        server.base_url = None
        server.endpoint = None

        result = proxy.call_tool_sync(server, "test_tool", {})

        assert result["success"] is False
        assert "URL not found" in result["error"]

    def test_call_tool_sync_success(self):
        """call_tool_sync 성공"""
        from app.services.mcp_proxy import HTTPMCPProxy
        import httpx as sync_httpx

        proxy = HTTPMCPProxy()

        server = MagicMock()
        server.base_url = "https://mcp.test.com"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"jsonrpc": "2.0", "result": {"data": "sync_test"}, "id": "1"}

        with patch.object(sync_httpx.Client, "post", return_value=mock_response):
            with patch.object(sync_httpx.Client, "__enter__", return_value=MagicMock(post=MagicMock(return_value=mock_response))):
                with patch.object(sync_httpx.Client, "__exit__", return_value=None):
                    # 실제 httpx.Client를 mock으로 대체
                    with patch("httpx.Client") as MockClient:
                        mock_client_instance = MagicMock()
                        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
                        mock_client_instance.__exit__ = MagicMock(return_value=None)
                        mock_client_instance.post.return_value = mock_response
                        MockClient.return_value = mock_client_instance

                        result = proxy.call_tool_sync(server, "test_tool", {"arg": "value"})

        assert result["success"] is True
        assert result["result"]["data"] == "sync_test"

    def test_call_tool_sync_http_error(self):
        """call_tool_sync HTTP 에러"""
        from app.services.mcp_proxy import HTTPMCPProxy

        proxy = HTTPMCPProxy()

        server = MagicMock()
        server.base_url = "https://mcp.test.com"

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("httpx.Client") as MockClient:
            mock_client_instance = MagicMock()
            mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__exit__ = MagicMock(return_value=None)
            mock_client_instance.post.return_value = mock_response
            MockClient.return_value = mock_client_instance

            result = proxy.call_tool_sync(server, "test_tool", {})

        assert result["success"] is False
        assert "500" in result["error"]

    def test_call_tool_sync_json_rpc_error(self):
        """call_tool_sync JSON-RPC 에러"""
        from app.services.mcp_proxy import HTTPMCPProxy

        proxy = HTTPMCPProxy()

        server = MagicMock()
        server.base_url = "https://mcp.test.com"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "error": {"code": -32600, "message": "Invalid Request"},
            "id": "1",
        }

        with patch("httpx.Client") as MockClient:
            mock_client_instance = MagicMock()
            mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__exit__ = MagicMock(return_value=None)
            mock_client_instance.post.return_value = mock_response
            MockClient.return_value = mock_client_instance

            result = proxy.call_tool_sync(server, "test_tool", {})

        assert result["success"] is False
        assert "Invalid Request" in result["error"]

    def test_call_tool_sync_exception(self):
        """call_tool_sync 예외"""
        from app.services.mcp_proxy import HTTPMCPProxy

        proxy = HTTPMCPProxy()

        server = MagicMock()
        server.base_url = "https://mcp.test.com"

        with patch("httpx.Client") as MockClient:
            mock_client_instance = MagicMock()
            mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__exit__ = MagicMock(return_value=None)
            mock_client_instance.post.side_effect = Exception("Connection failed")
            MockClient.return_value = mock_client_instance

            result = proxy.call_tool_sync(server, "test_tool", {})

        assert result["success"] is False
        assert "Connection failed" in result["error"]


class TestMockMCPProxy:
    """MockMCPProxy 테스트"""

    def test_mock_proxy_init(self):
        """초기화"""
        from app.services.mcp_proxy import MockMCPProxy

        proxy = MockMCPProxy()

        assert proxy.call_history == []
        assert proxy.mock_responses == {}
        assert proxy.should_fail is False

    def test_set_mock_response(self):
        """Mock 응답 설정"""
        from app.services.mcp_proxy import MockMCPProxy

        proxy = MockMCPProxy()
        proxy.set_mock_response("test_tool", {"data": "mocked"})

        assert "test_tool" in proxy.mock_responses
        assert proxy.mock_responses["test_tool"]["data"] == "mocked"

    def test_set_failure_mode(self):
        """실패 모드 설정"""
        from app.services.mcp_proxy import MockMCPProxy

        proxy = MockMCPProxy()
        proxy.set_failure_mode(True, 3)

        assert proxy.should_fail is True
        assert proxy.max_fail_count == 3
        assert proxy.fail_count == 0

    @pytest.mark.asyncio
    async def test_call_tool_success(self):
        """Mock call_tool 성공"""
        from app.services.mcp_proxy import MockMCPProxy
        from app.models.mcp import MCPServer, AuthType, MCPCallStatus

        proxy = MockMCPProxy()
        proxy.set_mock_response("my_tool", {"result": "success"})

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Mock Server",
            base_url="https://mock.mcp.com",
            auth_type=AuthType.NONE,
            timeout_ms=5000,
            created_at=now,
            updated_at=now,
        )

        result = await proxy.call_tool(server, "my_tool", {"arg": 1})

        assert result.status == MCPCallStatus.SUCCESS
        assert result.result["result"] == "success"
        assert len(proxy.call_history) == 1

    @pytest.mark.asyncio
    async def test_call_tool_failure_mode(self):
        """Mock call_tool 실패 모드"""
        from app.services.mcp_proxy import MockMCPProxy
        from app.models.mcp import MCPServer, AuthType, MCPCallStatus

        proxy = MockMCPProxy()
        proxy.set_failure_mode(True)

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Mock Server",
            base_url="https://mock.mcp.com",
            auth_type=AuthType.NONE,
            timeout_ms=5000,
            created_at=now,
            updated_at=now,
        )

        result = await proxy.call_tool(server, "my_tool", {})

        assert result.status == MCPCallStatus.FAILURE
        assert "Mock failure" in result.error_message

    @pytest.mark.asyncio
    async def test_call_tool_limited_failures(self):
        """Mock call_tool 제한된 실패"""
        from app.services.mcp_proxy import MockMCPProxy
        from app.models.mcp import MCPServer, AuthType, MCPCallStatus

        proxy = MockMCPProxy()
        proxy.set_failure_mode(True, max_failures=2)

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Mock Server",
            base_url="https://mock.mcp.com",
            auth_type=AuthType.NONE,
            timeout_ms=5000,
            created_at=now,
            updated_at=now,
        )

        # 첫 번째, 두 번째는 실패
        result1 = await proxy.call_tool(server, "my_tool", {})
        result2 = await proxy.call_tool(server, "my_tool", {})

        assert result1.status == MCPCallStatus.FAILURE
        assert result2.status == MCPCallStatus.FAILURE

        # 세 번째는 성공 (max_failures 초과)
        result3 = await proxy.call_tool(server, "my_tool", {})
        assert result3.status == MCPCallStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Mock health_check 성공"""
        from app.services.mcp_proxy import MockMCPProxy
        from app.models.mcp import MCPServer, AuthType

        proxy = MockMCPProxy()

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Mock Server",
            base_url="https://mock.mcp.com",
            auth_type=AuthType.NONE,
            timeout_ms=5000,
            created_at=now,
            updated_at=now,
        )

        is_healthy, latency_ms, error = await proxy.health_check(server)

        assert is_healthy is True
        assert latency_ms == 50
        assert error is None

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Mock health_check 실패"""
        from app.services.mcp_proxy import MockMCPProxy
        from app.models.mcp import MCPServer, AuthType

        proxy = MockMCPProxy()
        proxy.set_failure_mode(True)

        now = datetime.now(timezone.utc)
        server = MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="Mock Server",
            base_url="https://mock.mcp.com",
            auth_type=AuthType.NONE,
            timeout_ms=5000,
            created_at=now,
            updated_at=now,
        )

        is_healthy, latency_ms, error = await proxy.health_check(server)

        assert is_healthy is False
        assert "Mock failure" in error
