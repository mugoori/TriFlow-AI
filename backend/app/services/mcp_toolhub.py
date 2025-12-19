"""
MCP ToolHub Service

스펙 참조: B-2-3_MCP_DataHub_Chat_Design.md

MCP ToolHub: 외부 MCP 서버 호출을 표준화하는 게이트웨이
- MCP 서버 레지스트리 관리
- 도구 메타데이터 저장
- 도구 호출 프록시 (인증, 타임아웃, 재시도)
- Circuit Breaker
- 커넥터 헬스 체크
"""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp import (
    CircuitBreakerConfig,
    CircuitBreakerState,
    HealthStatus,
    MCPCallRequest,
    MCPCallResponse,
    MCPCallStatus,
    MCPHealthCheckResponse,
    MCPServer,
    MCPServerCreate,
    MCPServerList,
    MCPServerStatus,
    MCPServerUpdate,
    MCPTool,
    MCPToolCreate,
    MCPToolList,
    MCPToolUpdate,
)
from app.services.circuit_breaker import CircuitBreaker
from app.services.mcp_proxy import HTTPMCPProxy

logger = logging.getLogger(__name__)


class MCPToolHubService:
    """
    MCP ToolHub 메인 서비스

    외부 MCP 서버 등록, 도구 호출, 헬스체크 등 관리
    """

    def __init__(
        self,
        db: AsyncSession,
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
    async def register_server(
        self,
        tenant_id: UUID,
        data: MCPServerCreate,
        created_by: UUID | None = None,
    ) -> MCPServer:
        """MCP 서버 등록"""
        query = text("""
            INSERT INTO core.mcp_servers (
                tenant_id, name, description, base_url,
                auth_type, api_key, oauth_config, basic_auth_config,
                timeout_ms, retry_count, retry_delay_ms,
                tags, attributes, created_by
            )
            VALUES (
                :tenant_id, :name, :description, :base_url,
                :auth_type, :api_key, :oauth_config, :basic_auth_config,
                :timeout_ms, :retry_count, :retry_delay_ms,
                :tags, :attributes, :created_by
            )
            RETURNING server_id, tenant_id, name, description, base_url,
                      auth_type, api_key, oauth_config, basic_auth_config,
                      timeout_ms, retry_count, retry_delay_ms,
                      status, last_health_check, last_health_status, health_check_error,
                      tags, attributes, created_at, updated_at, created_by
        """)

        import json

        result = await self.db.execute(
            query,
            {
                "tenant_id": str(tenant_id),
                "name": data.name,
                "description": data.description,
                "base_url": data.base_url,
                "auth_type": data.auth_type.value,
                "api_key": data.api_key,
                "oauth_config": json.dumps(data.oauth_config.model_dump())
                if data.oauth_config
                else None,
                "basic_auth_config": json.dumps(data.basic_auth_config.model_dump())
                if data.basic_auth_config
                else None,
                "timeout_ms": data.timeout_ms,
                "retry_count": data.retry_count,
                "retry_delay_ms": data.retry_delay_ms,
                "tags": data.tags,
                "attributes": json.dumps(data.attributes),
                "created_by": str(created_by) if created_by else None,
            },
        )
        await self.db.commit()

        row = result.fetchone()
        server = self._row_to_server(row)

        # Circuit Breaker 초기화
        await self.circuit_breaker.initialize(server.server_id)

        logger.info(f"MCP server registered: {server.name} ({server.server_id})")
        return server

    async def get_server(self, server_id: UUID, tenant_id: UUID) -> MCPServer | None:
        """MCP 서버 조회"""
        query = text("""
            SELECT server_id, tenant_id, name, description, base_url,
                   auth_type, api_key, oauth_config, basic_auth_config,
                   timeout_ms, retry_count, retry_delay_ms,
                   status, last_health_check, last_health_status, health_check_error,
                   tags, attributes, created_at, updated_at, created_by
            FROM core.mcp_servers
            WHERE server_id = :server_id AND tenant_id = :tenant_id
        """)

        result = await self.db.execute(
            query,
            {"server_id": str(server_id), "tenant_id": str(tenant_id)},
        )
        row = result.fetchone()

        if not row:
            return None

        return self._row_to_server(row)

    async def list_servers(
        self,
        tenant_id: UUID,
        page: int = 1,
        size: int = 20,
        status: MCPServerStatus | None = None,
        tags: list[str] | None = None,
    ) -> MCPServerList:
        """MCP 서버 목록 조회"""
        # WHERE 조건 구성
        conditions = ["tenant_id = :tenant_id"]
        params: dict[str, Any] = {"tenant_id": str(tenant_id)}

        if status:
            conditions.append("status = :status")
            params["status"] = status.value

        if tags:
            conditions.append("tags @> :tags")
            params["tags"] = tags

        where_clause = " AND ".join(conditions)

        # 카운트 쿼리
        count_query = text(f"""
            SELECT COUNT(*)
            FROM core.mcp_servers
            WHERE {where_clause}
        """)
        count_result = await self.db.execute(count_query, params)
        total = count_result.scalar() or 0

        # 목록 쿼리
        offset = (page - 1) * size
        params["limit"] = size
        params["offset"] = offset

        list_query = text(f"""
            SELECT server_id, tenant_id, name, description, base_url,
                   auth_type, api_key, oauth_config, basic_auth_config,
                   timeout_ms, retry_count, retry_delay_ms,
                   status, last_health_check, last_health_status, health_check_error,
                   tags, attributes, created_at, updated_at, created_by
            FROM core.mcp_servers
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """)
        list_result = await self.db.execute(list_query, params)
        rows = list_result.fetchall()

        items = [self._row_to_server(row) for row in rows]

        return MCPServerList(items=items, total=total, page=page, size=size)

    async def update_server(
        self,
        server_id: UUID,
        tenant_id: UUID,
        data: MCPServerUpdate,
    ) -> MCPServer | None:
        """MCP 서버 수정"""
        # 동적 UPDATE 쿼리 구성
        updates = []
        params: dict[str, Any] = {
            "server_id": str(server_id),
            "tenant_id": str(tenant_id),
        }

        import json

        if data.name is not None:
            updates.append("name = :name")
            params["name"] = data.name

        if data.description is not None:
            updates.append("description = :description")
            params["description"] = data.description

        if data.base_url is not None:
            updates.append("base_url = :base_url")
            params["base_url"] = data.base_url

        if data.auth_type is not None:
            updates.append("auth_type = :auth_type")
            params["auth_type"] = data.auth_type.value

        if data.api_key is not None:
            updates.append("api_key = :api_key")
            params["api_key"] = data.api_key

        if data.oauth_config is not None:
            updates.append("oauth_config = :oauth_config")
            params["oauth_config"] = json.dumps(data.oauth_config.model_dump())

        if data.basic_auth_config is not None:
            updates.append("basic_auth_config = :basic_auth_config")
            params["basic_auth_config"] = json.dumps(data.basic_auth_config.model_dump())

        if data.timeout_ms is not None:
            updates.append("timeout_ms = :timeout_ms")
            params["timeout_ms"] = data.timeout_ms

        if data.retry_count is not None:
            updates.append("retry_count = :retry_count")
            params["retry_count"] = data.retry_count

        if data.retry_delay_ms is not None:
            updates.append("retry_delay_ms = :retry_delay_ms")
            params["retry_delay_ms"] = data.retry_delay_ms

        if data.status is not None:
            updates.append("status = :status")
            params["status"] = data.status.value

        if data.tags is not None:
            updates.append("tags = :tags")
            params["tags"] = data.tags

        if data.attributes is not None:
            updates.append("attributes = :attributes")
            params["attributes"] = json.dumps(data.attributes)

        if not updates:
            return await self.get_server(server_id, tenant_id)

        update_clause = ", ".join(updates)

        query = text(f"""
            UPDATE core.mcp_servers
            SET {update_clause}
            WHERE server_id = :server_id AND tenant_id = :tenant_id
            RETURNING server_id, tenant_id, name, description, base_url,
                      auth_type, api_key, oauth_config, basic_auth_config,
                      timeout_ms, retry_count, retry_delay_ms,
                      status, last_health_check, last_health_status, health_check_error,
                      tags, attributes, created_at, updated_at, created_by
        """)

        result = await self.db.execute(query, params)
        await self.db.commit()

        row = result.fetchone()
        if not row:
            return None

        return self._row_to_server(row)

    async def delete_server(self, server_id: UUID, tenant_id: UUID) -> bool:
        """MCP 서버 삭제"""
        query = text("""
            DELETE FROM core.mcp_servers
            WHERE server_id = :server_id AND tenant_id = :tenant_id
            RETURNING server_id
        """)

        result = await self.db.execute(
            query,
            {"server_id": str(server_id), "tenant_id": str(tenant_id)},
        )
        await self.db.commit()

        deleted = result.fetchone() is not None

        if deleted:
            logger.info(f"MCP server deleted: {server_id}")

        return deleted

    # =========================================
    # MCP Tool CRUD
    # =========================================
    async def create_tool(
        self,
        tenant_id: UUID,
        data: MCPToolCreate,
    ) -> MCPTool:
        """MCP 도구 등록"""
        import json

        query = text("""
            INSERT INTO core.mcp_tools (
                server_id, tenant_id, name, description, method,
                input_schema, output_schema, is_enabled, tags, attributes
            )
            VALUES (
                :server_id, :tenant_id, :name, :description, :method,
                :input_schema, :output_schema, :is_enabled, :tags, :attributes
            )
            RETURNING tool_id, server_id, tenant_id, name, description, method,
                      input_schema, output_schema, is_enabled, tags, attributes,
                      call_count, success_count, failure_count, avg_latency_ms, last_called_at,
                      created_at, updated_at
        """)

        result = await self.db.execute(
            query,
            {
                "server_id": str(data.server_id),
                "tenant_id": str(tenant_id),
                "name": data.name,
                "description": data.description,
                "method": data.method,
                "input_schema": json.dumps(data.input_schema),
                "output_schema": json.dumps(data.output_schema),
                "is_enabled": data.is_enabled,
                "tags": data.tags,
                "attributes": json.dumps(data.attributes),
            },
        )
        await self.db.commit()

        row = result.fetchone()
        return self._row_to_tool(row)

    async def get_tool(self, tool_id: UUID, tenant_id: UUID) -> MCPTool | None:
        """MCP 도구 조회"""
        query = text("""
            SELECT tool_id, server_id, tenant_id, name, description, method,
                   input_schema, output_schema, is_enabled, tags, attributes,
                   call_count, success_count, failure_count, avg_latency_ms, last_called_at,
                   created_at, updated_at
            FROM core.mcp_tools
            WHERE tool_id = :tool_id AND tenant_id = :tenant_id
        """)

        result = await self.db.execute(
            query,
            {"tool_id": str(tool_id), "tenant_id": str(tenant_id)},
        )
        row = result.fetchone()

        if not row:
            return None

        return self._row_to_tool(row)

    async def list_tools(
        self,
        tenant_id: UUID,
        server_id: UUID | None = None,
        page: int = 1,
        size: int = 50,
        is_enabled: bool | None = None,
    ) -> MCPToolList:
        """MCP 도구 목록 조회"""
        conditions = ["tenant_id = :tenant_id"]
        params: dict[str, Any] = {"tenant_id": str(tenant_id)}

        if server_id:
            conditions.append("server_id = :server_id")
            params["server_id"] = str(server_id)

        if is_enabled is not None:
            conditions.append("is_enabled = :is_enabled")
            params["is_enabled"] = is_enabled

        where_clause = " AND ".join(conditions)

        # 카운트
        count_query = text(f"""
            SELECT COUNT(*)
            FROM core.mcp_tools
            WHERE {where_clause}
        """)
        count_result = await self.db.execute(count_query, params)
        total = count_result.scalar() or 0

        # 목록
        offset = (page - 1) * size
        params["limit"] = size
        params["offset"] = offset

        list_query = text(f"""
            SELECT tool_id, server_id, tenant_id, name, description, method,
                   input_schema, output_schema, is_enabled, tags, attributes,
                   call_count, success_count, failure_count, avg_latency_ms, last_called_at,
                   created_at, updated_at
            FROM core.mcp_tools
            WHERE {where_clause}
            ORDER BY name ASC
            LIMIT :limit OFFSET :offset
        """)
        list_result = await self.db.execute(list_query, params)
        rows = list_result.fetchall()

        items = [self._row_to_tool(row) for row in rows]

        return MCPToolList(items=items, total=total, page=page, size=size)

    async def update_tool(
        self,
        tool_id: UUID,
        tenant_id: UUID,
        data: MCPToolUpdate,
    ) -> MCPTool | None:
        """MCP 도구 수정"""
        import json

        updates = []
        params: dict[str, Any] = {
            "tool_id": str(tool_id),
            "tenant_id": str(tenant_id),
        }

        if data.name is not None:
            updates.append("name = :name")
            params["name"] = data.name

        if data.description is not None:
            updates.append("description = :description")
            params["description"] = data.description

        if data.method is not None:
            updates.append("method = :method")
            params["method"] = data.method

        if data.input_schema is not None:
            updates.append("input_schema = :input_schema")
            params["input_schema"] = json.dumps(data.input_schema)

        if data.output_schema is not None:
            updates.append("output_schema = :output_schema")
            params["output_schema"] = json.dumps(data.output_schema)

        if data.is_enabled is not None:
            updates.append("is_enabled = :is_enabled")
            params["is_enabled"] = data.is_enabled

        if data.tags is not None:
            updates.append("tags = :tags")
            params["tags"] = data.tags

        if data.attributes is not None:
            updates.append("attributes = :attributes")
            params["attributes"] = json.dumps(data.attributes)

        if not updates:
            return await self.get_tool(tool_id, tenant_id)

        update_clause = ", ".join(updates)

        query = text(f"""
            UPDATE core.mcp_tools
            SET {update_clause}
            WHERE tool_id = :tool_id AND tenant_id = :tenant_id
            RETURNING tool_id, server_id, tenant_id, name, description, method,
                      input_schema, output_schema, is_enabled, tags, attributes,
                      call_count, success_count, failure_count, avg_latency_ms, last_called_at,
                      created_at, updated_at
        """)

        result = await self.db.execute(query, params)
        await self.db.commit()

        row = result.fetchone()
        if not row:
            return None

        return self._row_to_tool(row)

    async def delete_tool(self, tool_id: UUID, tenant_id: UUID) -> bool:
        """MCP 도구 삭제"""
        query = text("""
            DELETE FROM core.mcp_tools
            WHERE tool_id = :tool_id AND tenant_id = :tenant_id
            RETURNING tool_id
        """)

        result = await self.db.execute(
            query,
            {"tool_id": str(tool_id), "tenant_id": str(tenant_id)},
        )
        await self.db.commit()

        return result.fetchone() is not None

    # =========================================
    # Tool Calling
    # =========================================
    async def call_tool(
        self,
        tenant_id: UUID,
        request: MCPCallRequest,
        called_by: UUID | None = None,
    ) -> MCPCallResponse:
        """MCP 도구 호출"""
        # 서버 조회
        server = await self.get_server(request.server_id, tenant_id)
        if not server:
            return MCPCallResponse(
                request_id="",
                status=MCPCallStatus.FAILURE,
                error_message=f"Server not found: {request.server_id}",
                latency_ms=0,
            )

        if server.status != MCPServerStatus.ACTIVE:
            return MCPCallResponse(
                request_id="",
                status=MCPCallStatus.FAILURE,
                error_message=f"Server is not active: {server.status}",
                latency_ms=0,
            )

        # 프록시 호출
        response = await self.proxy.call_tool(
            server=server,
            tool_name=request.tool_name,
            args=request.args,
            correlation_id=request.correlation_id,
        )

        # 호출 로그 저장
        await self._save_call_log(
            tenant_id=tenant_id,
            server_id=server.server_id,
            tool_name=request.tool_name,
            request_id=response.request_id,
            request_payload=request.args,
            response_payload=response.result,
            status=response.status,
            error_message=response.error_message,
            error_code=response.error_code,
            latency_ms=response.latency_ms,
            retry_count=response.retry_count,
            called_by=called_by,
            correlation_id=request.correlation_id,
        )

        # 도구 통계 업데이트
        await self._update_tool_stats(
            server_id=server.server_id,
            tool_name=request.tool_name,
            success=response.status == MCPCallStatus.SUCCESS,
            latency_ms=response.latency_ms,
        )

        return response

    # =========================================
    # Health Check
    # =========================================
    async def health_check(
        self,
        server_id: UUID,
        tenant_id: UUID,
    ) -> MCPHealthCheckResponse:
        """MCP 서버 헬스체크"""
        server = await self.get_server(server_id, tenant_id)
        if not server:
            return MCPHealthCheckResponse(
                server_id=server_id,
                status=HealthStatus.UNKNOWN,
                error="Server not found",
            )

        # 헬스체크 수행
        is_healthy, latency_ms, error = await self.proxy.health_check(server)

        status = HealthStatus.HEALTHY if is_healthy else HealthStatus.UNHEALTHY

        # 서버 상태 업데이트
        await self._update_health_status(server_id, status, error)

        return MCPHealthCheckResponse(
            server_id=server_id,
            status=status,
            latency_ms=latency_ms,
            error=error,
        )

    async def health_check_all(self, tenant_id: UUID) -> list[MCPHealthCheckResponse]:
        """모든 활성 서버 헬스체크"""
        servers = await self.list_servers(tenant_id, size=100, status=MCPServerStatus.ACTIVE)

        results = []
        for server in servers.items:
            result = await self.health_check(server.server_id, tenant_id)
            results.append(result)

        return results

    # =========================================
    # Circuit Breaker
    # =========================================
    async def get_circuit_breaker_state(
        self,
        server_id: UUID,
    ) -> CircuitBreakerState | None:
        """Circuit Breaker 상태 조회"""
        return await self.circuit_breaker.get_state(server_id)

    async def reset_circuit_breaker(self, server_id: UUID) -> None:
        """Circuit Breaker 리셋"""
        await self.circuit_breaker.reset(server_id)

    async def update_circuit_breaker_config(
        self,
        server_id: UUID,
        config: CircuitBreakerConfig,
    ) -> None:
        """Circuit Breaker 설정 업데이트"""
        await self.circuit_breaker.update_config(server_id, config)

    # =========================================
    # Private Methods
    # =========================================
    def _row_to_server(self, row) -> MCPServer:
        """DB row → MCPServer"""
        from app.models.mcp import AuthType, BasicAuthConfig, OAuth2Config

        oauth_config = None
        if row.oauth_config:
            oauth_config = OAuth2Config.model_validate(row.oauth_config)

        basic_auth_config = None
        if row.basic_auth_config:
            basic_auth_config = BasicAuthConfig.model_validate(row.basic_auth_config)

        return MCPServer(
            server_id=row.server_id,
            tenant_id=row.tenant_id,
            name=row.name,
            description=row.description,
            base_url=row.base_url,
            auth_type=AuthType(row.auth_type),
            api_key=row.api_key,
            oauth_config=oauth_config,
            basic_auth_config=basic_auth_config,
            timeout_ms=row.timeout_ms,
            retry_count=row.retry_count,
            retry_delay_ms=row.retry_delay_ms,
            status=MCPServerStatus(row.status),
            last_health_check=row.last_health_check,
            last_health_status=HealthStatus(row.last_health_status)
            if row.last_health_status
            else None,
            health_check_error=row.health_check_error,
            tags=row.tags or [],
            attributes=row.attributes or {},
            created_at=row.created_at,
            updated_at=row.updated_at,
            created_by=row.created_by,
        )

    def _row_to_tool(self, row) -> MCPTool:
        """DB row → MCPTool"""
        return MCPTool(
            tool_id=row.tool_id,
            server_id=row.server_id,
            tenant_id=row.tenant_id,
            name=row.name,
            description=row.description,
            method=row.method,
            input_schema=row.input_schema or {},
            output_schema=row.output_schema or {},
            is_enabled=row.is_enabled,
            tags=row.tags or [],
            attributes=row.attributes or {},
            call_count=row.call_count,
            success_count=row.success_count,
            failure_count=row.failure_count,
            avg_latency_ms=float(row.avg_latency_ms) if row.avg_latency_ms else None,
            last_called_at=row.last_called_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def _save_call_log(
        self,
        tenant_id: UUID,
        server_id: UUID,
        tool_name: str,
        request_id: str,
        request_payload: dict,
        response_payload: dict | None,
        status: MCPCallStatus,
        error_message: str | None,
        error_code: str | None,
        latency_ms: int,
        retry_count: int,
        called_by: UUID | None,
        correlation_id: str | None,
    ) -> None:
        """호출 로그 저장"""
        import json

        query = text("""
            INSERT INTO core.mcp_call_logs (
                tenant_id, server_id, tool_name, request_id,
                request_payload, response_payload,
                status, error_message, error_code,
                latency_ms, retry_count, called_by, correlation_id
            )
            VALUES (
                :tenant_id, :server_id, :tool_name, :request_id,
                :request_payload, :response_payload,
                :status, :error_message, :error_code,
                :latency_ms, :retry_count, :called_by, :correlation_id
            )
        """)

        await self.db.execute(
            query,
            {
                "tenant_id": str(tenant_id),
                "server_id": str(server_id),
                "tool_name": tool_name,
                "request_id": request_id,
                "request_payload": json.dumps(request_payload),
                "response_payload": json.dumps(response_payload) if response_payload else None,
                "status": status.value,
                "error_message": error_message,
                "error_code": error_code,
                "latency_ms": latency_ms,
                "retry_count": retry_count,
                "called_by": str(called_by) if called_by else None,
                "correlation_id": correlation_id,
            },
        )
        await self.db.commit()

    async def _update_tool_stats(
        self,
        server_id: UUID,
        tool_name: str,
        success: bool,
        latency_ms: int,
    ) -> None:
        """도구 통계 업데이트"""
        if success:
            query = text("""
                UPDATE core.mcp_tools
                SET call_count = call_count + 1,
                    success_count = success_count + 1,
                    avg_latency_ms = COALESCE(
                        (avg_latency_ms * call_count + :latency_ms) / (call_count + 1),
                        :latency_ms
                    ),
                    last_called_at = now()
                WHERE server_id = :server_id AND name = :tool_name
            """)
        else:
            query = text("""
                UPDATE core.mcp_tools
                SET call_count = call_count + 1,
                    failure_count = failure_count + 1,
                    last_called_at = now()
                WHERE server_id = :server_id AND name = :tool_name
            """)

        await self.db.execute(
            query,
            {
                "server_id": str(server_id),
                "tool_name": tool_name,
                "latency_ms": latency_ms,
            },
        )
        await self.db.commit()

    async def _update_health_status(
        self,
        server_id: UUID,
        status: HealthStatus,
        error: str | None,
    ) -> None:
        """서버 헬스 상태 업데이트"""
        query = text("""
            UPDATE core.mcp_servers
            SET last_health_check = now(),
                last_health_status = :status,
                health_check_error = :error
            WHERE server_id = :server_id
        """)

        await self.db.execute(
            query,
            {
                "server_id": str(server_id),
                "status": status.value,
                "error": error,
            },
        )
        await self.db.commit()
