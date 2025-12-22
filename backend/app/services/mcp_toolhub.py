"""
MCP ToolHub Service

스펙 참조: B-2-3_MCP_DataHub_Chat_Design.md

MCP ToolHub: 외부 MCP 서버 호출을 표준화하는 게이트웨이
- MCP 서버 레지스트리 관리
- 도구 메타데이터 저장
- 도구 호출 프록시 (인증, 타임아웃, 재시도)
- Circuit Breaker
- 커넥터 헬스 체크

DB 스키마:
- mcp_servers: id, tenant_id, name, endpoint, protocol, config, auth_config,
               status, last_health_check_at, circuit_breaker_state, fail_count
- mcp_tools: id, mcp_server_id, tool_name, description, input_schema, output_schema,
             is_enabled, usage_count, avg_latency_ms, last_used_at
- mcp_call_logs: id, tenant_id, mcp_tool_id, workflow_instance_id, input_data,
                 output_data, success, error_message, latency_ms, retry_count, trace_id
"""

import json
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.circuit_breaker import CircuitBreaker
from app.services.mcp_proxy import HTTPMCPProxy

logger = logging.getLogger(__name__)


# =====================================================
# Simplified Response Models (matching actual DB schema)
# =====================================================
class MCPServerResponse(BaseModel):
    """MCP 서버 응답 모델 (DB 스키마 기반)"""
    id: UUID
    tenant_id: UUID
    name: str
    endpoint: str
    protocol: str = "stdio"
    config: dict[str, Any] = {}
    auth_config: dict[str, Any] | None = None
    status: str = "inactive"
    last_health_check_at: datetime | None = None
    circuit_breaker_state: str = "closed"
    fail_count: int = 0
    created_at: datetime
    updated_at: datetime


class MCPServerCreate(BaseModel):
    """MCP 서버 생성 요청"""
    name: str
    endpoint: str
    protocol: str = "stdio"  # stdio, sse, websocket
    config: dict[str, Any] = {}
    auth_config: dict[str, Any] | None = None


class MCPServerUpdate(BaseModel):
    """MCP 서버 수정 요청"""
    name: str | None = None
    endpoint: str | None = None
    protocol: str | None = None
    config: dict[str, Any] | None = None
    auth_config: dict[str, Any] | None = None
    status: str | None = None


class MCPServerList(BaseModel):
    """MCP 서버 목록 응답"""
    items: list[MCPServerResponse]
    total: int
    page: int
    size: int


class MCPToolResponse(BaseModel):
    """MCP 도구 응답 모델 (DB 스키마 기반)"""
    id: UUID
    mcp_server_id: UUID
    tool_name: str
    description: str | None = None
    input_schema: dict[str, Any] = {}
    output_schema: dict[str, Any] | None = None
    is_enabled: bool = True
    usage_count: int = 0
    avg_latency_ms: int | None = None
    last_used_at: datetime | None = None
    created_at: datetime


class MCPToolCreate(BaseModel):
    """MCP 도구 생성 요청"""
    mcp_server_id: UUID
    tool_name: str
    description: str | None = None
    input_schema: dict[str, Any] = {}
    output_schema: dict[str, Any] | None = None
    is_enabled: bool = True


class MCPToolUpdate(BaseModel):
    """MCP 도구 수정 요청"""
    tool_name: str | None = None
    description: str | None = None
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    is_enabled: bool | None = None


class MCPToolList(BaseModel):
    """MCP 도구 목록 응답"""
    items: list[MCPToolResponse]
    total: int
    page: int
    size: int


class MCPCallRequest(BaseModel):
    """MCP 도구 호출 요청"""
    mcp_server_id: UUID
    tool_name: str
    input_data: dict[str, Any] = {}
    workflow_instance_id: UUID | None = None
    trace_id: str | None = None


class MCPCallResponse(BaseModel):
    """MCP 도구 호출 응답"""
    id: UUID | None = None
    success: bool
    output_data: dict[str, Any] | None = None
    error_message: str | None = None
    latency_ms: int | None = None
    retry_count: int = 0


class MCPHealthCheckResponse(BaseModel):
    """MCP 서버 헬스체크 응답"""
    server_id: UUID
    status: str  # healthy, unhealthy, unknown
    latency_ms: int | None = None
    error: str | None = None
    checked_at: datetime


class CircuitBreakerStateResponse(BaseModel):
    """Circuit Breaker 상태 응답"""
    server_id: UUID
    state: str  # closed, open, half_open
    fail_count: int = 0


class MCPToolHubService:
    """
    MCP ToolHub 메인 서비스

    외부 MCP 서버 등록, 도구 호출, 헬스체크 등 관리
    """

    def __init__(
        self,
        db: Session,
        proxy: HTTPMCPProxy | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ):
        self.db = db
        self._proxy = proxy
        self._circuit_breaker = circuit_breaker

    @property
    def proxy(self) -> HTTPMCPProxy:
        if self._proxy is None:
            cb = self._circuit_breaker or CircuitBreaker(self.db)
            self._proxy = HTTPMCPProxy(circuit_breaker=cb)
        return self._proxy

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        if self._circuit_breaker is None:
            self._circuit_breaker = CircuitBreaker(self.db)
        return self._circuit_breaker

    # =========================================
    # MCP Server CRUD
    # =========================================
    def register_server(
        self,
        tenant_id: UUID,
        data: MCPServerCreate,
    ) -> MCPServerResponse:
        """MCP 서버 등록"""
        query = text("""
            INSERT INTO core.mcp_servers (
                tenant_id, name, endpoint, protocol, config, auth_config
            )
            VALUES (
                :tenant_id, :name, :endpoint, :protocol, :config, :auth_config
            )
            RETURNING id, tenant_id, name, endpoint, protocol, config, auth_config,
                      status, last_health_check_at, circuit_breaker_state, fail_count,
                      created_at, updated_at
        """)

        result = self.db.execute(
            query,
            {
                "tenant_id": str(tenant_id),
                "name": data.name,
                "endpoint": data.endpoint,
                "protocol": data.protocol,
                "config": json.dumps(data.config),
                "auth_config": json.dumps(data.auth_config) if data.auth_config else None,
            },
        )
        self.db.commit()

        row = result.fetchone()
        server = self._row_to_server(row)

        logger.info(f"MCP server registered: {server.name} ({server.id})")
        return server

    def get_server(self, server_id: UUID, tenant_id: UUID) -> MCPServerResponse | None:
        """MCP 서버 조회"""
        query = text("""
            SELECT id, tenant_id, name, endpoint, protocol, config, auth_config,
                   status, last_health_check_at, circuit_breaker_state, fail_count,
                   created_at, updated_at
            FROM core.mcp_servers
            WHERE id = :server_id AND tenant_id = :tenant_id
        """)

        result = self.db.execute(
            query,
            {"server_id": str(server_id), "tenant_id": str(tenant_id)},
        )
        row = result.fetchone()

        if not row:
            return None

        return self._row_to_server(row)

    def list_servers(
        self,
        tenant_id: UUID,
        page: int = 1,
        size: int = 20,
        status: str | None = None,
    ) -> MCPServerList:
        """MCP 서버 목록 조회"""
        # WHERE 조건 구성
        conditions = ["tenant_id = :tenant_id"]
        params: dict[str, Any] = {"tenant_id": str(tenant_id)}

        if status:
            conditions.append("status = :status")
            params["status"] = status

        where_clause = " AND ".join(conditions)

        # 카운트 쿼리
        count_query = text(f"""
            SELECT COUNT(*)
            FROM core.mcp_servers
            WHERE {where_clause}
        """)
        count_result = self.db.execute(count_query, params)
        total = count_result.scalar() or 0

        # 목록 쿼리
        offset = (page - 1) * size
        params["limit"] = size
        params["offset"] = offset

        list_query = text(f"""
            SELECT id, tenant_id, name, endpoint, protocol, config, auth_config,
                   status, last_health_check_at, circuit_breaker_state, fail_count,
                   created_at, updated_at
            FROM core.mcp_servers
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """)
        list_result = self.db.execute(list_query, params)
        rows = list_result.fetchall()

        items = [self._row_to_server(row) for row in rows]

        return MCPServerList(items=items, total=total, page=page, size=size)

    def update_server(
        self,
        server_id: UUID,
        tenant_id: UUID,
        data: MCPServerUpdate,
    ) -> MCPServerResponse | None:
        """MCP 서버 수정"""
        # 동적 UPDATE 쿼리 구성
        updates = ["updated_at = now()"]
        params: dict[str, Any] = {
            "server_id": str(server_id),
            "tenant_id": str(tenant_id),
        }

        if data.name is not None:
            updates.append("name = :name")
            params["name"] = data.name

        if data.endpoint is not None:
            updates.append("endpoint = :endpoint")
            params["endpoint"] = data.endpoint

        if data.protocol is not None:
            updates.append("protocol = :protocol")
            params["protocol"] = data.protocol

        if data.config is not None:
            updates.append("config = :config")
            params["config"] = json.dumps(data.config)

        if data.auth_config is not None:
            updates.append("auth_config = :auth_config")
            params["auth_config"] = json.dumps(data.auth_config)

        if data.status is not None:
            updates.append("status = :status")
            params["status"] = data.status

        update_clause = ", ".join(updates)

        query = text(f"""
            UPDATE core.mcp_servers
            SET {update_clause}
            WHERE id = :server_id AND tenant_id = :tenant_id
            RETURNING id, tenant_id, name, endpoint, protocol, config, auth_config,
                      status, last_health_check_at, circuit_breaker_state, fail_count,
                      created_at, updated_at
        """)

        result = self.db.execute(query, params)
        self.db.commit()

        row = result.fetchone()
        if not row:
            return None

        return self._row_to_server(row)

    def delete_server(self, server_id: UUID, tenant_id: UUID) -> bool:
        """MCP 서버 삭제"""
        query = text("""
            DELETE FROM core.mcp_servers
            WHERE id = :server_id AND tenant_id = :tenant_id
            RETURNING id
        """)

        result = self.db.execute(
            query,
            {"server_id": str(server_id), "tenant_id": str(tenant_id)},
        )
        self.db.commit()

        deleted = result.fetchone() is not None

        if deleted:
            logger.info(f"MCP server deleted: {server_id}")

        return deleted

    # =========================================
    # MCP Tool CRUD
    # =========================================
    def create_tool(
        self,
        tenant_id: UUID,
        data: MCPToolCreate,
    ) -> MCPToolResponse:
        """MCP 도구 등록"""
        query = text("""
            INSERT INTO core.mcp_tools (
                mcp_server_id, tool_name, description, input_schema, output_schema, is_enabled
            )
            VALUES (
                :mcp_server_id, :tool_name, :description, :input_schema, :output_schema, :is_enabled
            )
            RETURNING id, mcp_server_id, tool_name, description, input_schema, output_schema,
                      is_enabled, usage_count, avg_latency_ms, last_used_at, created_at
        """)

        result = self.db.execute(
            query,
            {
                "mcp_server_id": str(data.mcp_server_id),
                "tool_name": data.tool_name,
                "description": data.description,
                "input_schema": json.dumps(data.input_schema),
                "output_schema": json.dumps(data.output_schema) if data.output_schema else None,
                "is_enabled": data.is_enabled,
            },
        )
        self.db.commit()

        row = result.fetchone()
        return self._row_to_tool(row)

    def get_tool(self, tool_id: UUID) -> MCPToolResponse | None:
        """MCP 도구 조회"""
        query = text("""
            SELECT id, mcp_server_id, tool_name, description, input_schema, output_schema,
                   is_enabled, usage_count, avg_latency_ms, last_used_at, created_at
            FROM core.mcp_tools
            WHERE id = :tool_id
        """)

        result = self.db.execute(query, {"tool_id": str(tool_id)})
        row = result.fetchone()

        if not row:
            return None

        return self._row_to_tool(row)

    def get_tool_by_name(self, mcp_server_id: UUID, tool_name: str) -> MCPToolResponse | None:
        """MCP 도구 이름으로 조회"""
        query = text("""
            SELECT id, mcp_server_id, tool_name, description, input_schema, output_schema,
                   is_enabled, usage_count, avg_latency_ms, last_used_at, created_at
            FROM core.mcp_tools
            WHERE mcp_server_id = :mcp_server_id AND tool_name = :tool_name
        """)

        result = self.db.execute(
            query,
            {"mcp_server_id": str(mcp_server_id), "tool_name": tool_name},
        )
        row = result.fetchone()

        if not row:
            return None

        return self._row_to_tool(row)

    def list_tools(
        self,
        mcp_server_id: UUID | None = None,
        page: int = 1,
        size: int = 50,
        is_enabled: bool | None = None,
    ) -> MCPToolList:
        """MCP 도구 목록 조회"""
        conditions = []
        params: dict[str, Any] = {}

        if mcp_server_id:
            conditions.append("mcp_server_id = :mcp_server_id")
            params["mcp_server_id"] = str(mcp_server_id)

        if is_enabled is not None:
            conditions.append("is_enabled = :is_enabled")
            params["is_enabled"] = is_enabled

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # 카운트
        count_query = text(f"""
            SELECT COUNT(*)
            FROM core.mcp_tools
            WHERE {where_clause}
        """)
        count_result = self.db.execute(count_query, params)
        total = count_result.scalar() or 0

        # 목록
        offset = (page - 1) * size
        params["limit"] = size
        params["offset"] = offset

        list_query = text(f"""
            SELECT id, mcp_server_id, tool_name, description, input_schema, output_schema,
                   is_enabled, usage_count, avg_latency_ms, last_used_at, created_at
            FROM core.mcp_tools
            WHERE {where_clause}
            ORDER BY tool_name ASC
            LIMIT :limit OFFSET :offset
        """)
        list_result = self.db.execute(list_query, params)
        rows = list_result.fetchall()

        items = [self._row_to_tool(row) for row in rows]

        return MCPToolList(items=items, total=total, page=page, size=size)

    def update_tool(
        self,
        tool_id: UUID,
        data: MCPToolUpdate,
    ) -> MCPToolResponse | None:
        """MCP 도구 수정"""
        updates = []
        params: dict[str, Any] = {"tool_id": str(tool_id)}

        if data.tool_name is not None:
            updates.append("tool_name = :tool_name")
            params["tool_name"] = data.tool_name

        if data.description is not None:
            updates.append("description = :description")
            params["description"] = data.description

        if data.input_schema is not None:
            updates.append("input_schema = :input_schema")
            params["input_schema"] = json.dumps(data.input_schema)

        if data.output_schema is not None:
            updates.append("output_schema = :output_schema")
            params["output_schema"] = json.dumps(data.output_schema)

        if data.is_enabled is not None:
            updates.append("is_enabled = :is_enabled")
            params["is_enabled"] = data.is_enabled

        if not updates:
            return self.get_tool(tool_id)

        update_clause = ", ".join(updates)

        query = text(f"""
            UPDATE core.mcp_tools
            SET {update_clause}
            WHERE id = :tool_id
            RETURNING id, mcp_server_id, tool_name, description, input_schema, output_schema,
                      is_enabled, usage_count, avg_latency_ms, last_used_at, created_at
        """)

        result = self.db.execute(query, params)
        self.db.commit()

        row = result.fetchone()
        if not row:
            return None

        return self._row_to_tool(row)

    def delete_tool(self, tool_id: UUID) -> bool:
        """MCP 도구 삭제"""
        query = text("""
            DELETE FROM core.mcp_tools
            WHERE id = :tool_id
            RETURNING id
        """)

        result = self.db.execute(query, {"tool_id": str(tool_id)})
        self.db.commit()

        return result.fetchone() is not None

    # =========================================
    # Tool Calling
    # =========================================
    def call_tool(
        self,
        tenant_id: UUID,
        request: MCPCallRequest,
    ) -> MCPCallResponse:
        """MCP 도구 호출"""
        import time

        start_time = time.time()

        # 서버 조회
        server = self.get_server(request.mcp_server_id, tenant_id)
        if not server:
            return MCPCallResponse(
                success=False,
                error_message=f"Server not found: {request.mcp_server_id}",
            )

        if server.status != "active":
            return MCPCallResponse(
                success=False,
                error_message=f"Server is not active: {server.status}",
            )

        # 도구 조회
        tool = self.get_tool_by_name(request.mcp_server_id, request.tool_name)
        if not tool:
            return MCPCallResponse(
                success=False,
                error_message=f"Tool not found: {request.tool_name}",
            )

        if not tool.is_enabled:
            return MCPCallResponse(
                success=False,
                error_message=f"Tool is disabled: {request.tool_name}",
            )

        # 실제 도구 호출 (프록시 사용)
        try:
            # 프록시를 통한 MCP 호출
            result = self.proxy.call_tool_sync(
                server=server,
                tool_name=request.tool_name,
                args=request.input_data,
                trace_id=request.trace_id,
            )

            latency_ms = int((time.time() - start_time) * 1000)
            success = result.get("success", True)
            output_data = result.get("result", result)
            error_message = result.get("error") if not success else None

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            success = False
            output_data = None
            error_message = str(e)

        # 호출 로그 저장
        log_id = self._save_call_log(
            tenant_id=tenant_id,
            mcp_tool_id=tool.id,
            workflow_instance_id=request.workflow_instance_id,
            input_data=request.input_data,
            output_data=output_data,
            success=success,
            error_message=error_message,
            latency_ms=latency_ms,
            trace_id=request.trace_id,
        )

        # 도구 통계 업데이트
        self._update_tool_stats(
            tool_id=tool.id,
            success=success,
            latency_ms=latency_ms,
        )

        return MCPCallResponse(
            id=log_id,
            success=success,
            output_data=output_data,
            error_message=error_message,
            latency_ms=latency_ms,
        )

    # =========================================
    # Health Check
    # =========================================
    def _perform_health_check(
        self,
        endpoint: str,
    ) -> tuple[bool, int | None, str | None]:
        """
        동기식 HTTP 헬스체크 수행

        Returns:
            (is_healthy, latency_ms, error_message)
        """
        import httpx
        import time

        start_time = time.time()

        try:
            # 동기식 httpx 클라이언트 사용
            with httpx.Client(timeout=10.0) as client:
                # health 엔드포인트 또는 루트 엔드포인트 체크
                health_url = endpoint.rstrip("/")
                if not health_url.endswith("/health"):
                    health_url = f"{health_url}/health"

                response = client.get(health_url)
                latency_ms = int((time.time() - start_time) * 1000)

                if response.status_code == 200:
                    return True, latency_ms, None
                else:
                    return False, latency_ms, f"HTTP {response.status_code}"

        except httpx.TimeoutException:
            latency_ms = int((time.time() - start_time) * 1000)
            return False, latency_ms, "Timeout"

        except httpx.ConnectError as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return False, latency_ms, f"Connection error: {str(e)}"

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return False, latency_ms, str(e)

    def health_check(
        self,
        server_id: UUID,
        tenant_id: UUID,
    ) -> MCPHealthCheckResponse:
        """MCP 서버 헬스체크"""
        server = self.get_server(server_id, tenant_id)
        if not server:
            return MCPHealthCheckResponse(
                server_id=server_id,
                status="unknown",
                error="Server not found",
                checked_at=datetime.utcnow(),
            )

        # 헬스체크 수행 (동기식)
        is_healthy, latency_ms, error = self._perform_health_check(server.endpoint)

        status = "healthy" if is_healthy else "unhealthy"

        # 서버 상태 업데이트
        self._update_health_status(server_id, status, error)

        return MCPHealthCheckResponse(
            server_id=server_id,
            status=status,
            latency_ms=latency_ms,
            error=error,
            checked_at=datetime.utcnow(),
        )

    def health_check_all(self, tenant_id: UUID) -> list[MCPHealthCheckResponse]:
        """모든 활성 서버 헬스체크"""
        servers = self.list_servers(tenant_id, size=100, status="active")

        results = []
        for server in servers.items:
            result = self.health_check(server.id, tenant_id)
            results.append(result)

        return results

    # =========================================
    # Circuit Breaker
    # =========================================
    def get_circuit_breaker_state(
        self,
        server_id: UUID,
        tenant_id: UUID,
    ) -> CircuitBreakerStateResponse | None:
        """Circuit Breaker 상태 조회"""
        server = self.get_server(server_id, tenant_id)
        if not server:
            return None

        return CircuitBreakerStateResponse(
            server_id=server_id,
            state=server.circuit_breaker_state,
            fail_count=server.fail_count,
        )

    def reset_circuit_breaker(self, server_id: UUID, tenant_id: UUID) -> bool:
        """Circuit Breaker 리셋"""
        query = text("""
            UPDATE core.mcp_servers
            SET circuit_breaker_state = 'closed', fail_count = 0
            WHERE id = :server_id AND tenant_id = :tenant_id
            RETURNING id
        """)

        result = self.db.execute(
            query,
            {"server_id": str(server_id), "tenant_id": str(tenant_id)},
        )
        self.db.commit()

        return result.fetchone() is not None

    # =========================================
    # Private Methods
    # =========================================
    def _row_to_server(self, row) -> MCPServerResponse:
        """DB row → MCPServerResponse"""
        config = row.config if isinstance(row.config, dict) else {}
        auth_config = row.auth_config if isinstance(row.auth_config, dict) else None

        return MCPServerResponse(
            id=row.id,
            tenant_id=row.tenant_id,
            name=row.name,
            endpoint=row.endpoint,
            protocol=row.protocol,
            config=config,
            auth_config=auth_config,
            status=row.status,
            last_health_check_at=row.last_health_check_at,
            circuit_breaker_state=row.circuit_breaker_state,
            fail_count=row.fail_count,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _row_to_tool(self, row) -> MCPToolResponse:
        """DB row → MCPToolResponse"""
        input_schema = row.input_schema if isinstance(row.input_schema, dict) else {}
        output_schema = row.output_schema if isinstance(row.output_schema, dict) else None

        return MCPToolResponse(
            id=row.id,
            mcp_server_id=row.mcp_server_id,
            tool_name=row.tool_name,
            description=row.description,
            input_schema=input_schema,
            output_schema=output_schema,
            is_enabled=row.is_enabled,
            usage_count=row.usage_count,
            avg_latency_ms=row.avg_latency_ms,
            last_used_at=row.last_used_at,
            created_at=row.created_at,
        )

    def _save_call_log(
        self,
        tenant_id: UUID,
        mcp_tool_id: UUID,
        workflow_instance_id: UUID | None,
        input_data: dict,
        output_data: dict | None,
        success: bool,
        error_message: str | None,
        latency_ms: int | None,
        trace_id: str | None,
        retry_count: int = 0,
    ) -> UUID | None:
        """호출 로그 저장"""
        query = text("""
            INSERT INTO core.mcp_call_logs (
                tenant_id, mcp_tool_id, workflow_instance_id,
                input_data, output_data, success, error_message,
                latency_ms, retry_count, trace_id
            )
            VALUES (
                :tenant_id, :mcp_tool_id, :workflow_instance_id,
                :input_data, :output_data, :success, :error_message,
                :latency_ms, :retry_count, :trace_id
            )
            RETURNING id
        """)

        result = self.db.execute(
            query,
            {
                "tenant_id": str(tenant_id),
                "mcp_tool_id": str(mcp_tool_id),
                "workflow_instance_id": str(workflow_instance_id) if workflow_instance_id else None,
                "input_data": json.dumps(input_data),
                "output_data": json.dumps(output_data) if output_data else None,
                "success": success,
                "error_message": error_message,
                "latency_ms": latency_ms,
                "retry_count": retry_count,
                "trace_id": trace_id,
            },
        )
        self.db.commit()

        row = result.fetchone()
        return row.id if row else None

    def _update_tool_stats(
        self,
        tool_id: UUID,
        success: bool,
        latency_ms: int,
    ) -> None:
        """도구 통계 업데이트"""
        if success:
            query = text("""
                UPDATE core.mcp_tools
                SET usage_count = usage_count + 1,
                    avg_latency_ms = COALESCE(
                        (COALESCE(avg_latency_ms, 0) * usage_count + :latency_ms) / (usage_count + 1),
                        :latency_ms
                    ),
                    last_used_at = now()
                WHERE id = :tool_id
            """)
        else:
            query = text("""
                UPDATE core.mcp_tools
                SET usage_count = usage_count + 1,
                    last_used_at = now()
                WHERE id = :tool_id
            """)

        self.db.execute(
            query,
            {
                "tool_id": str(tool_id),
                "latency_ms": latency_ms,
            },
        )
        self.db.commit()

    def _update_health_status(
        self,
        server_id: UUID,
        status: str,
        error: str | None,
    ) -> None:
        """서버 헬스 상태 업데이트"""
        new_status = "active" if status == "healthy" else "error"

        query = text("""
            UPDATE core.mcp_servers
            SET last_health_check_at = now(),
                status = :new_status,
                fail_count = CASE WHEN :status = 'healthy' THEN 0 ELSE fail_count + 1 END
            WHERE id = :server_id
        """)

        self.db.execute(
            query,
            {
                "server_id": str(server_id),
                "new_status": new_status,
                "status": status,
            },
        )
        self.db.commit()
