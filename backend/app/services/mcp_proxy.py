"""
HTTP MCP Proxy

스펙 참조: B-2-3_MCP_DataHub_Chat_Design.md

MCP 서버 호출 프록시:
- JSON-RPC 2.0 프로토콜
- API Key / OAuth2 / Basic 인증
- 타임아웃 + 재시도 (exponential backoff)
- Circuit Breaker 통합
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Protocol

import httpx

from app.models.mcp import (
    AuthType,
    MCPCallResponse,
    MCPCallStatus,
    MCPServer,
)

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)


# =========================================
# Exceptions
# =========================================
class MCPError(Exception):
    """MCP 관련 기본 예외"""

    pass


class MCPTimeoutError(MCPError):
    """MCP 서버 타임아웃"""

    def __init__(self, server_id: str, timeout_ms: int):
        self.server_id = server_id
        self.timeout_ms = timeout_ms
        super().__init__(f"MCP server timeout (> {timeout_ms}ms)")


class MCPHTTPError(MCPError):
    """MCP HTTP 에러"""

    def __init__(self, server_id: str, status_code: int, detail: str | None = None):
        self.server_id = server_id
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"MCP server error: HTTP {status_code}")


class MCPProtocolError(MCPError):
    """MCP 프로토콜 에러 (JSON-RPC 에러 응답)"""

    def __init__(self, server_id: str, error_code: int | str, error_message: str):
        self.server_id = server_id
        self.error_code = error_code
        self.error_message = error_message
        super().__init__(f"MCP protocol error: [{error_code}] {error_message}")


class CircuitBreakerOpenError(MCPError):
    """Circuit Breaker가 OPEN 상태"""

    def __init__(self, server_id: str):
        self.server_id = server_id
        super().__init__(f"Circuit breaker OPEN for server {server_id}")


# =========================================
# Interfaces
# =========================================
class ICircuitBreaker(Protocol):
    """Circuit Breaker 인터페이스"""

    async def is_open(self, server_id: Any) -> bool: ...
    async def record_success(self, server_id: Any) -> None: ...
    async def record_failure(self, server_id: Any) -> None: ...


# =========================================
# HTTP MCP Proxy
# =========================================
class HTTPMCPProxy:
    """
    HTTP 기반 MCP Proxy

    JSON-RPC 2.0 프로토콜로 MCP 서버와 통신
    """

    # OAuth2 토큰 캐시 TTL (기본 50분, 만료 10분 전 재발급)
    OAUTH_TOKEN_CACHE_TTL = 3000

    def __init__(
        self,
        circuit_breaker: ICircuitBreaker | None = None,
        redis: "Redis | None" = None,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.circuit_breaker = circuit_breaker
        self.redis = redis
        self._http_client = http_client
        self._owns_client = http_client is None

    async def __aenter__(self):
        if self._http_client is None:
            self._http_client = httpx.AsyncClient()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._owns_client and self._http_client:
            await self._http_client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient()
        return self._http_client

    async def call_tool(
        self,
        server: MCPServer,
        tool_name: str,
        args: dict[str, Any],
        correlation_id: str | None = None,
    ) -> MCPCallResponse:
        """
        MCP 도구 호출

        Args:
            server: MCP 서버 정보
            tool_name: 도구 이름
            args: 도구 인자
            correlation_id: 연관 요청 추적 ID

        Returns:
            MCPCallResponse
        """
        request_id = str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)

        # 1. Circuit Breaker 확인
        if self.circuit_breaker:
            if await self.circuit_breaker.is_open(server.server_id):
                logger.warning(
                    f"Circuit breaker OPEN for server {server.server_id}, rejecting request"
                )
                return MCPCallResponse(
                    request_id=request_id,
                    status=MCPCallStatus.CIRCUIT_OPEN,
                    error_message=f"Circuit breaker OPEN for server {server.server_id}",
                    latency_ms=0,
                )

        # 2. 재시도 루프
        last_error: Exception | None = None
        retry_count = 0

        for attempt in range(server.retry_count + 1):
            try:
                result = await self._do_call(server, tool_name, args, request_id)

                # 성공
                latency_ms = int(
                    (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                )

                if self.circuit_breaker:
                    await self.circuit_breaker.record_success(server.server_id)

                logger.info(
                    f"MCP call success: server={server.name}, tool={tool_name}, latency={latency_ms}ms"
                )

                return MCPCallResponse(
                    request_id=request_id,
                    status=MCPCallStatus.SUCCESS,
                    result=result,
                    latency_ms=latency_ms,
                    retry_count=retry_count,
                )

            except MCPTimeoutError as e:
                last_error = e
                retry_count = attempt
                logger.warning(
                    f"MCP timeout (attempt {attempt + 1}/{server.retry_count + 1}): {e}"
                )

            except MCPHTTPError as e:
                last_error = e
                retry_count = attempt
                # 4xx 에러는 재시도하지 않음
                if 400 <= e.status_code < 500:
                    break
                logger.warning(
                    f"MCP HTTP error (attempt {attempt + 1}/{server.retry_count + 1}): {e}"
                )

            except MCPProtocolError as e:
                last_error = e
                retry_count = attempt
                logger.warning(f"MCP protocol error: {e}")
                break  # 프로토콜 에러는 재시도하지 않음

            except Exception as e:
                last_error = e
                retry_count = attempt
                logger.error(
                    f"MCP unexpected error (attempt {attempt + 1}/{server.retry_count + 1}): {e}"
                )

            # 재시도 대기 (exponential backoff)
            if attempt < server.retry_count:
                delay = server.retry_delay_ms * (2**attempt) / 1000
                await asyncio.sleep(delay)

        # 모든 재시도 실패
        latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

        if self.circuit_breaker:
            await self.circuit_breaker.record_failure(server.server_id)

        # 에러 타입별 응답
        if isinstance(last_error, MCPTimeoutError):
            return MCPCallResponse(
                request_id=request_id,
                status=MCPCallStatus.TIMEOUT,
                error_message=str(last_error),
                latency_ms=latency_ms,
                retry_count=retry_count,
            )

        error_code = None
        if isinstance(last_error, MCPHTTPError):
            error_code = str(last_error.status_code)
        elif isinstance(last_error, MCPProtocolError):
            error_code = str(last_error.error_code)

        return MCPCallResponse(
            request_id=request_id,
            status=MCPCallStatus.FAILURE,
            error_message=str(last_error) if last_error else "Unknown error",
            error_code=error_code,
            latency_ms=latency_ms,
            retry_count=retry_count,
        )

    async def _do_call(
        self,
        server: MCPServer,
        tool_name: str,
        args: dict[str, Any],
        request_id: str,
    ) -> dict[str, Any]:
        """실제 HTTP 호출 수행"""
        # 인증 헤더
        headers = await self._build_auth_headers(server)
        headers["Content-Type"] = "application/json"

        # JSON-RPC 2.0 페이로드
        payload = {
            "jsonrpc": "2.0",
            "method": f"tools/{tool_name}",
            "params": args,
            "id": request_id,
        }

        # HTTP 요청
        try:
            response = await self.client.post(
                f"{server.base_url}/mcp",
                json=payload,
                headers=headers,
                timeout=server.timeout_ms / 1000,
            )
        except httpx.TimeoutException:
            raise MCPTimeoutError(str(server.server_id), server.timeout_ms)
        except httpx.RequestError as e:
            raise MCPHTTPError(str(server.server_id), 0, str(e))

        # HTTP 상태 확인
        if response.status_code >= 400:
            raise MCPHTTPError(
                str(server.server_id),
                response.status_code,
                response.text[:500] if response.text else None,
            )

        # JSON-RPC 응답 파싱
        try:
            result = response.json()
        except Exception as e:
            raise MCPProtocolError(str(server.server_id), "PARSE_ERROR", str(e))

        # JSON-RPC 에러 확인
        if "error" in result:
            error = result["error"]
            raise MCPProtocolError(
                str(server.server_id),
                error.get("code", "UNKNOWN"),
                error.get("message", "Unknown error"),
            )

        return result.get("result", {})

    async def _build_auth_headers(self, server: MCPServer) -> dict[str, str]:
        """인증 헤더 구성"""
        if server.auth_type == AuthType.NONE:
            return {}

        if server.auth_type == AuthType.API_KEY:
            if server.api_key:
                return {"Authorization": f"Bearer {server.api_key}"}
            return {}

        if server.auth_type == AuthType.OAUTH2:
            token = await self._get_oauth_token(server)
            return {"Authorization": f"Bearer {token}"}

        if server.auth_type == AuthType.BASIC:
            if server.basic_auth_config:
                import base64

                credentials = f"{server.basic_auth_config.username}:{server.basic_auth_config.password}"
                encoded = base64.b64encode(credentials.encode()).decode()
                return {"Authorization": f"Basic {encoded}"}
            return {}

        return {}

    async def _get_oauth_token(self, server: MCPServer) -> str:
        """OAuth2 토큰 조회 (캐시 또는 재발급)"""
        if not server.oauth_config:
            raise MCPError("OAuth2 config not found")

        cache_key = f"oauth:token:{server.server_id}"

        # Redis 캐시 확인
        if self.redis:
            cached_token = await self.redis.get(cache_key)
            if cached_token:
                return cached_token.decode() if isinstance(cached_token, bytes) else cached_token

        # 토큰 재발급
        try:
            response = await self.client.post(
                server.oauth_config.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": server.oauth_config.client_id,
                    "client_secret": server.oauth_config.client_secret,
                    "scope": server.oauth_config.scope or "",
                },
                timeout=30.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise MCPError(f"OAuth2 token request failed: {e.response.status_code}")
        except httpx.RequestError as e:
            raise MCPError(f"OAuth2 token request failed: {e}")

        token_data = response.json()
        access_token = token_data.get("access_token")

        if not access_token:
            raise MCPError("OAuth2 response missing access_token")

        expires_in = token_data.get("expires_in", 3600)

        # Redis에 캐싱 (만료 60초 전)
        if self.redis:
            cache_ttl = max(expires_in - 60, 60)
            await self.redis.setex(cache_key, cache_ttl, access_token)

        return access_token

    def call_tool_sync(
        self,
        server: Any,  # MCPServer 또는 MCPServerResponse
        tool_name: str,
        args: dict[str, Any],
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """
        동기 방식 MCP 도구 호출 (동기 컨텍스트에서 사용)

        Args:
            server: MCP 서버 정보 (MCPServer 또는 MCPServerResponse)
            tool_name: 도구 이름
            args: 도구 인자
            trace_id: 추적 ID

        Returns:
            도구 호출 결과 딕셔너리
        """
        import httpx as sync_httpx

        request_id = str(uuid.uuid4())

        # 동기 HTTP 클라이언트로 직접 호출
        headers = {"Content-Type": "application/json"}

        # 서버 URL 가져오기 (MCPServer 또는 MCPServerResponse 호환)
        server_url = getattr(server, "base_url", None) or getattr(server, "endpoint", None)
        if not server_url:
            return {
                "success": False,
                "error": "Server URL not found",
            }

        # JSON-RPC 2.0 페이로드 (tools/call 형식)
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": args,
            },
            "id": request_id,
        }

        try:
            with sync_httpx.Client() as client:
                response = client.post(
                    server_url,
                    json=payload,
                    headers=headers,
                    timeout=30.0,
                )

                if response.status_code >= 400:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text[:200]}",
                    }

                result = response.json()

                # JSON-RPC 에러 확인
                if "error" in result:
                    error = result["error"]
                    return {
                        "success": False,
                        "error": error.get("message", "Unknown error"),
                    }

                # 성공 결과 반환
                return {
                    "success": True,
                    "result": result.get("result", {}),
                }

        except Exception as e:
            logger.error(f"MCP call_tool_sync error: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def health_check(self, server: MCPServer) -> tuple[bool, int | None, str | None]:
        """
        MCP 서버 헬스체크

        Returns:
            (is_healthy, latency_ms, error_message)
        """
        start_time = datetime.now(timezone.utc)

        try:
            headers = await self._build_auth_headers(server)

            # 간단한 ping 요청
            response = await self.client.get(
                f"{server.base_url}/health",
                headers=headers,
                timeout=10.0,
            )

            latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

            if response.status_code == 200:
                return True, latency_ms, None

            return False, latency_ms, f"HTTP {response.status_code}"

        except httpx.TimeoutException:
            latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            return False, latency_ms, "Timeout"

        except Exception as e:
            latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            return False, latency_ms, str(e)


# =========================================
# Mock MCP Proxy (테스트용)
# =========================================
class MockMCPProxy:
    """테스트용 Mock MCP Proxy"""

    def __init__(self):
        self.call_history: list[dict] = []
        self.mock_responses: dict[str, Any] = {}
        self.should_fail = False
        self.fail_count = 0
        self.max_fail_count = 0

    def set_mock_response(self, tool_name: str, response: Any) -> None:
        """Mock 응답 설정"""
        self.mock_responses[tool_name] = response

    def set_failure_mode(self, fail: bool = True, max_failures: int = 0) -> None:
        """실패 모드 설정"""
        self.should_fail = fail
        self.max_fail_count = max_failures
        self.fail_count = 0

    async def call_tool(
        self,
        server: MCPServer,
        tool_name: str,
        args: dict[str, Any],
        correlation_id: str | None = None,
    ) -> MCPCallResponse:
        request_id = str(uuid.uuid4())

        self.call_history.append(
            {
                "server_id": str(server.server_id),
                "tool_name": tool_name,
                "args": args,
                "correlation_id": correlation_id,
            }
        )

        # 실패 모드
        if self.should_fail:
            if self.max_fail_count == 0 or self.fail_count < self.max_fail_count:
                self.fail_count += 1
                return MCPCallResponse(
                    request_id=request_id,
                    status=MCPCallStatus.FAILURE,
                    error_message="Mock failure",
                    latency_ms=100,
                )

        # Mock 응답
        result = self.mock_responses.get(tool_name, {"success": True})

        return MCPCallResponse(
            request_id=request_id,
            status=MCPCallStatus.SUCCESS,
            result=result,
            latency_ms=50,
        )

    async def health_check(self, server: MCPServer) -> tuple[bool, int | None, str | None]:
        if self.should_fail:
            return False, 100, "Mock failure"
        return True, 50, None
