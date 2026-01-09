"""
MCP ToolHub Tests

테스트 대상:
1. Circuit Breaker 상태 전이
2. HTTPMCPProxy 호출 (Mock)
3. MCPToolHubService CRUD
4. Schema Drift Detection
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.models.mcp import (
    AuthType,
    CircuitBreakerConfig,
    CircuitBreakerStateEnum,
    ConnectorType,
    DataConnectorCreate,
    DriftChangeType,
    DriftSeverity,
    MCPCallRequest,
    MCPCallStatus,
    MCPServer,
    MCPServerCreate,
    MCPServerStatus,
    MCPToolCreate,
)
from app.services.circuit_breaker import InMemoryCircuitBreaker
from app.services.drift_detector import SchemaDriftDetector
from app.services.mcp_proxy import MockMCPProxy


# =====================================================
# Circuit Breaker Tests
# =====================================================
class TestInMemoryCircuitBreaker:
    """InMemoryCircuitBreaker 테스트"""

    @pytest.fixture
    def circuit_breaker(self):
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=10,  # 최소값 10초 (Pydantic 검증)
        )
        return InMemoryCircuitBreaker(config)

    @pytest.fixture
    def server_id(self):
        return uuid4()

    @pytest.mark.asyncio
    async def test_initial_state_is_closed(self, circuit_breaker, server_id):
        """초기 상태는 CLOSED"""
        is_open = await circuit_breaker.is_open(server_id)
        assert is_open is False

        state = await circuit_breaker.get_state(server_id)
        assert state.state == CircuitBreakerStateEnum.CLOSED

    @pytest.mark.asyncio
    async def test_closed_to_open_on_failures(self, circuit_breaker, server_id):
        """연속 실패 시 CLOSED → OPEN"""
        # 3번 실패 (failure_threshold = 3)
        await circuit_breaker.record_failure(server_id)
        await circuit_breaker.record_failure(server_id)

        # 아직 CLOSED
        is_open = await circuit_breaker.is_open(server_id)
        assert is_open is False

        # 3번째 실패
        await circuit_breaker.record_failure(server_id)

        # OPEN으로 전환
        is_open = await circuit_breaker.is_open(server_id)
        assert is_open is True

        state = await circuit_breaker.get_state(server_id)
        assert state.state == CircuitBreakerStateEnum.OPEN

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self, circuit_breaker, server_id):
        """성공하면 연속 실패 카운트 리셋"""
        await circuit_breaker.record_failure(server_id)
        await circuit_breaker.record_failure(server_id)

        # 성공으로 리셋
        await circuit_breaker.record_success(server_id)

        # 다시 실패해도 아직 CLOSED
        await circuit_breaker.record_failure(server_id)
        await circuit_breaker.record_failure(server_id)

        is_open = await circuit_breaker.is_open(server_id)
        assert is_open is False

    @pytest.mark.asyncio
    async def test_open_to_half_open_after_timeout(self, circuit_breaker, server_id):
        """타임아웃 후 OPEN → HALF_OPEN"""
        # OPEN 상태로 만들기
        for _ in range(3):
            await circuit_breaker.record_failure(server_id)

        assert await circuit_breaker.is_open(server_id) is True

        # opened_at을 과거로 설정하여 타임아웃 시뮬레이션
        internal_state = circuit_breaker._states[server_id]
        internal_state["opened_at"] = datetime.now(timezone.utc) - timedelta(seconds=15)

        # is_open 호출 시 HALF_OPEN으로 전환
        is_open = await circuit_breaker.is_open(server_id)
        assert is_open is False

        state = await circuit_breaker.get_state(server_id)
        assert state.state == CircuitBreakerStateEnum.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_to_closed_on_success(self, circuit_breaker, server_id):
        """HALF_OPEN에서 성공하면 CLOSED"""
        # OPEN으로 만들기
        for _ in range(3):
            await circuit_breaker.record_failure(server_id)

        # opened_at을 과거로 설정하여 타임아웃 시뮬레이션 → HALF_OPEN
        internal_state = circuit_breaker._states[server_id]
        internal_state["opened_at"] = datetime.now(timezone.utc) - timedelta(seconds=15)
        await circuit_breaker.is_open(server_id)

        # success_threshold = 2
        await circuit_breaker.record_success(server_id)
        state = await circuit_breaker.get_state(server_id)
        assert state.state == CircuitBreakerStateEnum.HALF_OPEN

        await circuit_breaker.record_success(server_id)
        state = await circuit_breaker.get_state(server_id)
        assert state.state == CircuitBreakerStateEnum.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_to_open_on_failure(self, circuit_breaker, server_id):
        """HALF_OPEN에서 실패하면 즉시 OPEN"""
        # OPEN으로 만들기
        for _ in range(3):
            await circuit_breaker.record_failure(server_id)

        # opened_at을 과거로 설정하여 타임아웃 시뮬레이션 → HALF_OPEN
        internal_state = circuit_breaker._states[server_id]
        internal_state["opened_at"] = datetime.now(timezone.utc) - timedelta(seconds=15)
        await circuit_breaker.is_open(server_id)

        state = await circuit_breaker.get_state(server_id)
        assert state.state == CircuitBreakerStateEnum.HALF_OPEN

        # 실패 → 즉시 OPEN
        await circuit_breaker.record_failure(server_id)

        state = await circuit_breaker.get_state(server_id)
        assert state.state == CircuitBreakerStateEnum.OPEN

    @pytest.mark.asyncio
    async def test_reset(self, circuit_breaker, server_id):
        """리셋하면 CLOSED로"""
        # OPEN으로 만들기
        for _ in range(3):
            await circuit_breaker.record_failure(server_id)

        await circuit_breaker.reset(server_id)

        is_open = await circuit_breaker.is_open(server_id)
        assert is_open is False


# =====================================================
# Mock MCP Proxy Tests
# =====================================================
class TestMockMCPProxy:
    """MockMCPProxy 테스트"""

    @pytest.fixture
    def proxy(self):
        return MockMCPProxy()

    @pytest.fixture
    def mock_server(self):
        return MCPServer(
            server_id=uuid4(),
            tenant_id=uuid4(),
            name="test-server",
            base_url="http://localhost:8080",
            auth_type=AuthType.NONE,
            timeout_ms=30000,
            retry_count=3,
            retry_delay_ms=1000,
            status=MCPServerStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    @pytest.mark.asyncio
    async def test_call_tool_success(self, proxy, mock_server):
        """도구 호출 성공"""
        proxy.set_mock_response("read_file", {"content": "hello world"})

        response = await proxy.call_tool(
            server=mock_server,
            tool_name="read_file",
            args={"path": "/test.txt"},
        )

        assert response.status == MCPCallStatus.SUCCESS
        assert response.result == {"content": "hello world"}
        assert len(proxy.call_history) == 1

    @pytest.mark.asyncio
    async def test_call_tool_failure(self, proxy, mock_server):
        """도구 호출 실패"""
        proxy.set_failure_mode(True)

        response = await proxy.call_tool(
            server=mock_server,
            tool_name="read_file",
            args={"path": "/test.txt"},
        )

        assert response.status == MCPCallStatus.FAILURE
        assert response.error_message == "Mock failure"

    @pytest.mark.asyncio
    async def test_call_tool_with_max_failures(self, proxy, mock_server):
        """제한된 횟수만 실패"""
        proxy.set_failure_mode(True, max_failures=2)

        # 첫 번째 호출: 실패
        response1 = await proxy.call_tool(mock_server, "test", {})
        assert response1.status == MCPCallStatus.FAILURE

        # 두 번째 호출: 실패
        response2 = await proxy.call_tool(mock_server, "test", {})
        assert response2.status == MCPCallStatus.FAILURE

        # 세 번째 호출: 성공
        response3 = await proxy.call_tool(mock_server, "test", {})
        assert response3.status == MCPCallStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_health_check(self, proxy, mock_server):
        """헬스체크"""
        is_healthy, latency, error = await proxy.health_check(mock_server)
        assert is_healthy is True
        assert latency == 50
        assert error is None

        proxy.set_failure_mode(True)
        is_healthy, latency, error = await proxy.health_check(mock_server)
        assert is_healthy is False
        assert error == "Mock failure"


# =====================================================
# Schema Drift Detection Tests
# =====================================================
class TestSchemaDriftDetector:
    """SchemaDriftDetector 테스트 (순수 비교 로직)"""

    def test_compare_schemas_no_changes(self):
        """변경 없음"""
        old_schema = {
            "users": {
                "columns": [
                    {"column_name": "id", "data_type": "integer", "is_nullable": "NO"},
                    {"column_name": "name", "data_type": "varchar", "is_nullable": "YES"},
                ]
            }
        }
        new_schema = old_schema.copy()

        detector = SchemaDriftDetector.__new__(SchemaDriftDetector)
        changes = detector._compare_schemas(old_schema, new_schema)

        assert len(changes) == 0

    def test_compare_schemas_table_added(self):
        """테이블 추가"""
        old_schema = {
            "users": {"columns": [{"column_name": "id", "data_type": "integer", "is_nullable": "NO"}]}
        }
        new_schema = {
            "users": {"columns": [{"column_name": "id", "data_type": "integer", "is_nullable": "NO"}]},
            "orders": {"columns": [{"column_name": "id", "data_type": "integer", "is_nullable": "NO"}]},
        }

        detector = SchemaDriftDetector.__new__(SchemaDriftDetector)
        changes = detector._compare_schemas(old_schema, new_schema)

        assert len(changes) == 1
        assert changes[0].type == DriftChangeType.TABLE_ADDED
        assert changes[0].table_name == "orders"

    def test_compare_schemas_table_deleted(self):
        """테이블 삭제"""
        old_schema = {
            "users": {"columns": [{"column_name": "id", "data_type": "integer", "is_nullable": "NO"}]},
            "orders": {"columns": [{"column_name": "id", "data_type": "integer", "is_nullable": "NO"}]},
        }
        new_schema = {
            "users": {"columns": [{"column_name": "id", "data_type": "integer", "is_nullable": "NO"}]}
        }

        detector = SchemaDriftDetector.__new__(SchemaDriftDetector)
        changes = detector._compare_schemas(old_schema, new_schema)

        assert len(changes) == 1
        assert changes[0].type == DriftChangeType.TABLE_DELETED
        assert changes[0].table_name == "orders"

    def test_compare_schemas_column_added(self):
        """컬럼 추가"""
        old_schema = {
            "users": {"columns": [{"column_name": "id", "data_type": "integer", "is_nullable": "NO"}]}
        }
        new_schema = {
            "users": {
                "columns": [
                    {"column_name": "id", "data_type": "integer", "is_nullable": "NO"},
                    {"column_name": "email", "data_type": "varchar", "is_nullable": "YES"},
                ]
            }
        }

        detector = SchemaDriftDetector.__new__(SchemaDriftDetector)
        changes = detector._compare_schemas(old_schema, new_schema)

        assert len(changes) == 1
        assert changes[0].type == DriftChangeType.COLUMN_ADDED
        assert changes[0].table_name == "users"
        assert changes[0].column_name == "email"

    def test_compare_schemas_column_deleted(self):
        """컬럼 삭제"""
        old_schema = {
            "users": {
                "columns": [
                    {"column_name": "id", "data_type": "integer", "is_nullable": "NO"},
                    {"column_name": "email", "data_type": "varchar", "is_nullable": "YES"},
                ]
            }
        }
        new_schema = {
            "users": {"columns": [{"column_name": "id", "data_type": "integer", "is_nullable": "NO"}]}
        }

        detector = SchemaDriftDetector.__new__(SchemaDriftDetector)
        changes = detector._compare_schemas(old_schema, new_schema)

        assert len(changes) == 1
        assert changes[0].type == DriftChangeType.COLUMN_DELETED
        assert changes[0].table_name == "users"
        assert changes[0].column_name == "email"

    def test_compare_schemas_type_changed(self):
        """타입 변경"""
        old_schema = {
            "users": {"columns": [{"column_name": "age", "data_type": "integer", "is_nullable": "YES"}]}
        }
        new_schema = {
            "users": {"columns": [{"column_name": "age", "data_type": "bigint", "is_nullable": "YES"}]}
        }

        detector = SchemaDriftDetector.__new__(SchemaDriftDetector)
        changes = detector._compare_schemas(old_schema, new_schema)

        assert len(changes) == 1
        assert changes[0].type == DriftChangeType.TYPE_CHANGED
        assert changes[0].table_name == "users"
        assert changes[0].column_name == "age"
        assert changes[0].old_value == "integer"
        assert changes[0].new_value == "bigint"

    def test_calculate_severity_critical_on_deletion(self):
        """삭제가 있으면 CRITICAL"""
        from app.models.mcp import DriftChange

        changes = [
            DriftChange(type=DriftChangeType.TABLE_DELETED, table_name="users"),
        ]

        detector = SchemaDriftDetector.__new__(SchemaDriftDetector)
        severity = detector._calculate_severity(changes)

        assert severity == DriftSeverity.CRITICAL

    def test_calculate_severity_warning_on_type_change(self):
        """타입 변경은 WARNING"""
        from app.models.mcp import DriftChange

        changes = [
            DriftChange(
                type=DriftChangeType.TYPE_CHANGED,
                table_name="users",
                column_name="age",
                old_value="integer",
                new_value="bigint",
            ),
        ]

        detector = SchemaDriftDetector.__new__(SchemaDriftDetector)
        severity = detector._calculate_severity(changes)

        assert severity == DriftSeverity.WARNING

    def test_calculate_severity_info_on_addition(self):
        """추가만 있으면 INFO"""
        from app.models.mcp import DriftChange

        changes = [
            DriftChange(
                type=DriftChangeType.COLUMN_ADDED,
                table_name="users",
                column_name="email",
            ),
        ]

        detector = SchemaDriftDetector.__new__(SchemaDriftDetector)
        severity = detector._calculate_severity(changes)

        assert severity == DriftSeverity.INFO

    def test_compute_schema_hash(self):
        """스키마 해시 일관성"""
        schema1 = {"users": {"columns": [{"column_name": "id", "data_type": "integer"}]}}
        schema2 = {"users": {"columns": [{"column_name": "id", "data_type": "integer"}]}}
        schema3 = {"users": {"columns": [{"column_name": "id", "data_type": "varchar"}]}}

        detector = SchemaDriftDetector.__new__(SchemaDriftDetector)

        hash1 = detector._compute_schema_hash(schema1)
        hash2 = detector._compute_schema_hash(schema2)
        hash3 = detector._compute_schema_hash(schema3)

        assert hash1 == hash2  # 동일한 스키마
        assert hash1 != hash3  # 다른 스키마


# =====================================================
# Pydantic Model Tests
# =====================================================
class TestMCPModels:
    """Pydantic 모델 테스트"""

    def test_mcp_server_create_validation(self):
        """MCPServerCreate 유효성 검사"""
        # 정상 케이스
        server = MCPServerCreate(
            name="test-server",
            base_url="https://mcp.example.com",
            auth_type=AuthType.API_KEY,
            api_key="secret-key",
            timeout_ms=30000,
        )
        assert server.name == "test-server"
        assert server.base_url == "https://mcp.example.com"

        # URL 정규화 (trailing slash 제거)
        server2 = MCPServerCreate(
            name="test-server",
            base_url="https://mcp.example.com/",
            auth_type=AuthType.NONE,
        )
        assert server2.base_url == "https://mcp.example.com"

    def test_mcp_server_create_invalid_url(self):
        """잘못된 URL 검증"""
        with pytest.raises(ValueError):
            MCPServerCreate(
                name="test-server",
                base_url="not-a-url",  # http:// 또는 https:// 없음
                auth_type=AuthType.NONE,
            )

    def test_mcp_tool_create(self):
        """MCPToolCreate 생성"""
        tool = MCPToolCreate(
            server_id=uuid4(),
            name="read_file",
            method="tools/read_file",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        )
        assert tool.name == "read_file"
        assert tool.method == "tools/read_file"

    def test_mcp_call_request(self):
        """MCPCallRequest 생성"""
        request = MCPCallRequest(
            server_id=uuid4(),
            tool_name="read_file",
            args={"path": "/test.txt"},
            correlation_id="workflow-123",
        )
        assert request.tool_name == "read_file"
        assert request.args["path"] == "/test.txt"

    def test_data_connector_create(self):
        """DataConnectorCreate 생성"""
        connector = DataConnectorCreate(
            name="prod-db",
            description="Production PostgreSQL",
            connector_type=ConnectorType.POSTGRESQL,
            connection_config={
                "host": "db.example.com",
                "port": 5432,
                "database": "production",
                "username": "admin",
                "password": "secret",
            },
        )
        assert connector.name == "prod-db"
        assert connector.connector_type == ConnectorType.POSTGRESQL

    def test_circuit_breaker_config(self):
        """CircuitBreakerConfig 범위 검증"""
        # 정상 케이스
        config = CircuitBreakerConfig(
            failure_threshold=5,
            success_threshold=2,
            timeout_seconds=60,
        )
        assert config.failure_threshold == 5

        # 범위 초과
        with pytest.raises(ValueError):
            CircuitBreakerConfig(failure_threshold=0)  # ge=1

        with pytest.raises(ValueError):
            CircuitBreakerConfig(timeout_seconds=1000)  # le=600


# =====================================================
# MCPToolHubService Response Models 테스트
# =====================================================
class TestMCPToolHubResponseModels:
    """MCPToolHubService 응답 모델 테스트"""

    def test_mcp_server_response_creation(self):
        """MCPServerResponse 생성"""
        from app.services.mcp_toolhub import MCPServerResponse

        now = datetime.now(timezone.utc)
        server_id = uuid4()
        tenant_id = uuid4()

        response = MCPServerResponse(
            id=server_id,
            tenant_id=tenant_id,
            name="Test MCP Server",
            endpoint="https://mcp.example.com",
            protocol="stdio",
            config={},
            auth_config=None,
            status="inactive",
            last_health_check_at=None,
            circuit_breaker_state="closed",
            fail_count=0,
            created_at=now,
            updated_at=now,
        )

        assert response.id == server_id
        assert response.name == "Test MCP Server"
        assert response.protocol == "stdio"

    def test_mcp_server_response_with_auth(self):
        """MCPServerResponse 인증 설정 포함"""
        from app.services.mcp_toolhub import MCPServerResponse

        now = datetime.now(timezone.utc)

        response = MCPServerResponse(
            id=uuid4(),
            tenant_id=uuid4(),
            name="Secure Server",
            endpoint="https://secure.mcp.com",
            protocol="sse",
            config={"timeout": 30},
            auth_config={"type": "api_key", "key": "secret"},
            status="active",
            circuit_breaker_state="closed",
            fail_count=0,
            created_at=now,
            updated_at=now,
        )

        assert response.auth_config["type"] == "api_key"
        assert response.config["timeout"] == 30

    def test_mcp_server_response_defaults(self):
        """MCPServerResponse 기본값"""
        from app.services.mcp_toolhub import MCPServerResponse

        now = datetime.now(timezone.utc)

        response = MCPServerResponse(
            id=uuid4(),
            tenant_id=uuid4(),
            name="Default Server",
            endpoint="https://default.mcp.com",
            created_at=now,
            updated_at=now,
        )

        assert response.protocol == "stdio"
        assert response.config == {}
        assert response.status == "inactive"
        assert response.circuit_breaker_state == "closed"
        assert response.fail_count == 0


class TestMCPToolHubCreateModels:
    """MCPToolHubService 생성 모델 테스트"""

    def test_mcp_server_create_minimal(self):
        """MCPServerCreate 최소"""
        from app.services.mcp_toolhub import MCPServerCreate

        data = MCPServerCreate(
            name="New Server",
            endpoint="https://new.mcp.com",
        )

        assert data.name == "New Server"
        assert data.protocol == "stdio"
        assert data.config == {}

    def test_mcp_server_create_full(self):
        """MCPServerCreate 전체"""
        from app.services.mcp_toolhub import MCPServerCreate

        data = MCPServerCreate(
            name="Full Server",
            endpoint="https://full.mcp.com",
            protocol="websocket",
            config={"retry": 3},
            auth_config={"type": "oauth2"},
        )

        assert data.protocol == "websocket"
        assert data.auth_config["type"] == "oauth2"

    def test_mcp_server_update_partial(self):
        """MCPServerUpdate 부분"""
        from app.services.mcp_toolhub import MCPServerUpdate

        data = MCPServerUpdate(name="Updated Name")

        assert data.name == "Updated Name"
        assert data.endpoint is None
        assert data.status is None

    def test_mcp_server_update_full(self):
        """MCPServerUpdate 전체"""
        from app.services.mcp_toolhub import MCPServerUpdate

        data = MCPServerUpdate(
            name="Full Update",
            endpoint="https://updated.mcp.com",
            protocol="sse",
            config={"new_key": "value"},
            auth_config={"type": "basic"},
            status="active",
        )

        assert data.name == "Full Update"
        assert data.status == "active"


class TestMCPToolHubListModels:
    """MCPToolHubService 목록 모델 테스트"""

    def test_mcp_server_list_empty(self):
        """MCPServerList 빈 목록"""
        from app.services.mcp_toolhub import MCPServerList

        server_list = MCPServerList(
            items=[],
            total=0,
            page=1,
            size=20,
        )

        assert len(server_list.items) == 0
        assert server_list.total == 0

    def test_mcp_server_list_with_items(self):
        """MCPServerList 항목 포함"""
        from app.services.mcp_toolhub import MCPServerList, MCPServerResponse

        now = datetime.now(timezone.utc)
        servers = [
            MCPServerResponse(
                id=uuid4(),
                tenant_id=uuid4(),
                name=f"Server {i}",
                endpoint=f"https://server{i}.mcp.com",
                created_at=now,
                updated_at=now,
            )
            for i in range(3)
        ]

        server_list = MCPServerList(
            items=servers,
            total=3,
            page=1,
            size=20,
        )

        assert len(server_list.items) == 3
        assert server_list.total == 3


class TestMCPToolHubToolModels:
    """MCPToolHubService 도구 모델 테스트"""

    def test_mcp_tool_response_creation(self):
        """MCPToolResponse 생성"""
        from app.services.mcp_toolhub import MCPToolResponse

        now = datetime.now(timezone.utc)

        response = MCPToolResponse(
            id=uuid4(),
            mcp_server_id=uuid4(),
            tool_name="get_weather",
            description="날씨 조회",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            is_enabled=True,
            usage_count=100,
            avg_latency_ms=150,
            last_used_at=now,
            created_at=now,
        )

        assert response.tool_name == "get_weather"
        assert response.usage_count == 100

    def test_mcp_tool_response_defaults(self):
        """MCPToolResponse 기본값"""
        from app.services.mcp_toolhub import MCPToolResponse

        now = datetime.now(timezone.utc)

        response = MCPToolResponse(
            id=uuid4(),
            mcp_server_id=uuid4(),
            tool_name="simple_tool",
            created_at=now,
        )

        assert response.is_enabled is True
        assert response.usage_count == 0
        assert response.input_schema == {}

    def test_mcp_tool_create_minimal(self):
        """MCPToolCreate 최소"""
        from app.services.mcp_toolhub import MCPToolCreate

        server_id = uuid4()
        data = MCPToolCreate(
            mcp_server_id=server_id,
            tool_name="new_tool",
        )

        assert data.mcp_server_id == server_id
        assert data.is_enabled is True

    def test_mcp_tool_create_full(self):
        """MCPToolCreate 전체"""
        from app.services.mcp_toolhub import MCPToolCreate

        data = MCPToolCreate(
            mcp_server_id=uuid4(),
            tool_name="full_tool",
            description="완전한 도구",
            input_schema={"type": "object"},
            output_schema={"type": "array"},
            is_enabled=False,
        )

        assert data.description == "완전한 도구"
        assert data.is_enabled is False

    def test_mcp_tool_update_partial(self):
        """MCPToolUpdate 부분"""
        from app.services.mcp_toolhub import MCPToolUpdate

        data = MCPToolUpdate(description="Updated description")

        assert data.description == "Updated description"
        assert data.tool_name is None

    def test_mcp_tool_update_disable(self):
        """MCPToolUpdate 비활성화"""
        from app.services.mcp_toolhub import MCPToolUpdate

        data = MCPToolUpdate(is_enabled=False)

        assert data.is_enabled is False

    def test_mcp_tool_list(self):
        """MCPToolList 목록"""
        from app.services.mcp_toolhub import MCPToolList, MCPToolResponse

        now = datetime.now(timezone.utc)
        server_id = uuid4()
        tools = [
            MCPToolResponse(
                id=uuid4(),
                mcp_server_id=server_id,
                tool_name=f"tool_{i}",
                created_at=now,
            )
            for i in range(5)
        ]

        tool_list = MCPToolList(
            items=tools,
            total=5,
            page=1,
            size=50,
        )

        assert len(tool_list.items) == 5


class TestMCPToolHubCallModels:
    """MCPToolHubService 호출 모델 테스트"""

    def test_mcp_call_request_minimal(self):
        """MCPCallRequest (ToolHub) 최소"""
        from app.services.mcp_toolhub import MCPCallRequest as ToolHubCallRequest

        request = ToolHubCallRequest(
            mcp_server_id=uuid4(),
            tool_name="test_tool",
        )

        assert request.tool_name == "test_tool"
        assert request.input_data == {}

    def test_mcp_call_request_with_data(self):
        """MCPCallRequest (ToolHub) 데이터 포함"""
        from app.services.mcp_toolhub import MCPCallRequest as ToolHubCallRequest

        workflow_id = uuid4()
        request = ToolHubCallRequest(
            mcp_server_id=uuid4(),
            tool_name="data_tool",
            input_data={"key": "value"},
            workflow_instance_id=workflow_id,
            trace_id="trace-123",
        )

        assert request.input_data["key"] == "value"
        assert request.trace_id == "trace-123"

    def test_mcp_call_response_success(self):
        """MCPCallResponse (ToolHub) 성공"""
        from app.services.mcp_toolhub import MCPCallResponse as ToolHubCallResponse

        response = ToolHubCallResponse(
            id=uuid4(),
            success=True,
            output_data={"result": "ok"},
            latency_ms=100,
        )

        assert response.success is True
        assert response.output_data["result"] == "ok"

    def test_mcp_call_response_failure(self):
        """MCPCallResponse (ToolHub) 실패"""
        from app.services.mcp_toolhub import MCPCallResponse as ToolHubCallResponse

        response = ToolHubCallResponse(
            success=False,
            error_message="Connection failed",
            latency_ms=5000,
            retry_count=3,
        )

        assert response.success is False
        assert response.retry_count == 3


class TestMCPToolHubHealthModels:
    """MCPToolHubService 헬스체크 모델 테스트"""

    def test_health_check_response_healthy(self):
        """MCPHealthCheckResponse 정상"""
        from app.services.mcp_toolhub import MCPHealthCheckResponse

        now = datetime.now(timezone.utc)
        response = MCPHealthCheckResponse(
            server_id=uuid4(),
            status="healthy",
            latency_ms=50,
            checked_at=now,
        )

        assert response.status == "healthy"
        assert response.error is None

    def test_health_check_response_unhealthy(self):
        """MCPHealthCheckResponse 비정상"""
        from app.services.mcp_toolhub import MCPHealthCheckResponse

        now = datetime.now(timezone.utc)
        response = MCPHealthCheckResponse(
            server_id=uuid4(),
            status="unhealthy",
            latency_ms=10000,
            error="Timeout",
            checked_at=now,
        )

        assert response.status == "unhealthy"
        assert response.error == "Timeout"

    def test_circuit_breaker_state_response_closed(self):
        """CircuitBreakerStateResponse 닫힘"""
        from app.services.mcp_toolhub import CircuitBreakerStateResponse

        response = CircuitBreakerStateResponse(
            server_id=uuid4(),
            state="closed",
            fail_count=0,
        )

        assert response.state == "closed"
        assert response.fail_count == 0

    def test_circuit_breaker_state_response_open(self):
        """CircuitBreakerStateResponse 열림"""
        from app.services.mcp_toolhub import CircuitBreakerStateResponse

        response = CircuitBreakerStateResponse(
            server_id=uuid4(),
            state="open",
            fail_count=5,
        )

        assert response.state == "open"
        assert response.fail_count == 5


# =====================================================
# MCPToolHubService 초기화 테스트
# =====================================================
class TestMCPToolHubServiceInit:
    """MCPToolHubService 초기화 테스트"""

    def test_init_with_db_only(self):
        """DB만으로 초기화"""
        from unittest.mock import MagicMock
        from app.services.mcp_toolhub import MCPToolHubService

        mock_db = MagicMock()
        service = MCPToolHubService(db=mock_db)

        assert service.db == mock_db
        assert service._proxy is None
        assert service._circuit_breaker is None

    def test_init_with_all_dependencies(self):
        """모든 의존성으로 초기화"""
        from unittest.mock import MagicMock
        from app.services.mcp_toolhub import MCPToolHubService
        from app.services.mcp_proxy import HTTPMCPProxy
        from app.services.circuit_breaker import CircuitBreaker

        mock_db = MagicMock()
        mock_proxy = MagicMock(spec=HTTPMCPProxy)
        mock_cb = MagicMock(spec=CircuitBreaker)

        service = MCPToolHubService(
            db=mock_db,
            proxy=mock_proxy,
            circuit_breaker=mock_cb,
        )

        assert service._proxy == mock_proxy
        assert service._circuit_breaker == mock_cb

    def test_lazy_proxy_initialization(self):
        """프록시 지연 초기화"""
        from unittest.mock import MagicMock
        from app.services.mcp_toolhub import MCPToolHubService

        mock_db = MagicMock()
        service = MCPToolHubService(db=mock_db)

        # proxy 프로퍼티 접근 시 초기화
        proxy = service.proxy

        assert proxy is not None

    def test_lazy_circuit_breaker_initialization(self):
        """Circuit Breaker 지연 초기화"""
        from unittest.mock import MagicMock
        from app.services.mcp_toolhub import MCPToolHubService

        mock_db = MagicMock()
        service = MCPToolHubService(db=mock_db)

        # circuit_breaker 프로퍼티 접근 시 초기화
        cb = service.circuit_breaker

        assert cb is not None


# =====================================================
# MCPToolHubService Server CRUD 테스트
# =====================================================
class TestMCPToolHubServiceServerCRUD:
    """MCPToolHubService 서버 CRUD 테스트"""

    @pytest.fixture
    def mock_service(self):
        """Mock 서비스 생성"""
        from unittest.mock import MagicMock
        from app.services.mcp_toolhub import MCPToolHubService

        mock_db = MagicMock()
        return MCPToolHubService(db=mock_db)

    def test_register_server(self, mock_service):
        """서버 등록"""
        from unittest.mock import MagicMock
        from app.services.mcp_toolhub import MCPServerCreate

        tenant_id = uuid4()
        now = datetime.now(timezone.utc)
        server_id = uuid4()

        mock_row = MagicMock()
        mock_row.id = server_id
        mock_row.tenant_id = tenant_id
        mock_row.name = "New Server"
        mock_row.endpoint = "https://new.mcp.com"
        mock_row.protocol = "stdio"
        mock_row.config = {}
        mock_row.auth_config = None
        mock_row.status = "inactive"
        mock_row.last_health_check_at = None
        mock_row.circuit_breaker_state = "closed"
        mock_row.fail_count = 0
        mock_row.created_at = now
        mock_row.updated_at = now

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_service.db.execute.return_value = mock_result

        data = MCPServerCreate(
            name="New Server",
            endpoint="https://new.mcp.com",
        )

        result = mock_service.register_server(tenant_id, data)

        assert result.name == "New Server"
        mock_service.db.execute.assert_called_once()
        mock_service.db.commit.assert_called_once()

    def test_get_server_found(self, mock_service):
        """서버 조회 - 존재"""
        from unittest.mock import MagicMock

        tenant_id = uuid4()
        server_id = uuid4()
        now = datetime.now(timezone.utc)

        mock_row = MagicMock()
        mock_row.id = server_id
        mock_row.tenant_id = tenant_id
        mock_row.name = "Existing Server"
        mock_row.endpoint = "https://existing.mcp.com"
        mock_row.protocol = "stdio"
        mock_row.config = {}
        mock_row.auth_config = None
        mock_row.status = "active"
        mock_row.last_health_check_at = now
        mock_row.circuit_breaker_state = "closed"
        mock_row.fail_count = 0
        mock_row.created_at = now
        mock_row.updated_at = now

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_service.db.execute.return_value = mock_result

        result = mock_service.get_server(server_id, tenant_id)

        assert result is not None
        assert result.name == "Existing Server"

    def test_get_server_not_found(self, mock_service):
        """서버 조회 - 미존재"""
        from unittest.mock import MagicMock

        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_service.db.execute.return_value = mock_result

        result = mock_service.get_server(uuid4(), uuid4())

        assert result is None

    def test_list_servers(self, mock_service):
        """서버 목록 조회"""
        from unittest.mock import MagicMock

        tenant_id = uuid4()
        now = datetime.now(timezone.utc)

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2

        mock_rows = []
        for i in range(2):
            row = MagicMock()
            row.id = uuid4()
            row.tenant_id = tenant_id
            row.name = f"Server {i}"
            row.endpoint = f"https://server{i}.mcp.com"
            row.protocol = "stdio"
            row.config = {}
            row.auth_config = None
            row.status = "active"
            row.last_health_check_at = now
            row.circuit_breaker_state = "closed"
            row.fail_count = 0
            row.created_at = now
            row.updated_at = now
            mock_rows.append(row)

        mock_list_result = MagicMock()
        mock_list_result.fetchall.return_value = mock_rows

        mock_service.db.execute.side_effect = [mock_count_result, mock_list_result]

        result = mock_service.list_servers(tenant_id)

        assert result.total == 2
        assert len(result.items) == 2

    def test_list_servers_with_status_filter(self, mock_service):
        """서버 목록 조회 - 상태 필터"""
        from unittest.mock import MagicMock

        tenant_id = uuid4()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_list_result = MagicMock()
        mock_list_result.fetchall.return_value = []

        mock_service.db.execute.side_effect = [mock_count_result, mock_list_result]

        result = mock_service.list_servers(tenant_id, status="inactive")

        assert result.total == 0

    def test_update_server(self, mock_service):
        """서버 수정"""
        from unittest.mock import MagicMock
        from app.services.mcp_toolhub import MCPServerUpdate

        tenant_id = uuid4()
        server_id = uuid4()
        now = datetime.now(timezone.utc)

        mock_row = MagicMock()
        mock_row.id = server_id
        mock_row.tenant_id = tenant_id
        mock_row.name = "Updated Server"
        mock_row.endpoint = "https://updated.mcp.com"
        mock_row.protocol = "stdio"
        mock_row.config = {}
        mock_row.auth_config = None
        mock_row.status = "active"
        mock_row.last_health_check_at = now
        mock_row.circuit_breaker_state = "closed"
        mock_row.fail_count = 0
        mock_row.created_at = now
        mock_row.updated_at = now

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_service.db.execute.return_value = mock_result

        data = MCPServerUpdate(name="Updated Server", status="active")
        result = mock_service.update_server(server_id, tenant_id, data)

        assert result is not None
        assert result.name == "Updated Server"
        mock_service.db.commit.assert_called_once()

    def test_update_server_not_found(self, mock_service):
        """서버 수정 - 미존재"""
        from unittest.mock import MagicMock
        from app.services.mcp_toolhub import MCPServerUpdate

        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_service.db.execute.return_value = mock_result

        data = MCPServerUpdate(name="New Name")
        result = mock_service.update_server(uuid4(), uuid4(), data)

        assert result is None

    def test_delete_server_success(self, mock_service):
        """서버 삭제 - 성공"""
        from unittest.mock import MagicMock

        mock_row = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_service.db.execute.return_value = mock_result

        result = mock_service.delete_server(uuid4(), uuid4())

        assert result is True
        mock_service.db.commit.assert_called_once()

    def test_delete_server_not_found(self, mock_service):
        """서버 삭제 - 미존재"""
        from unittest.mock import MagicMock

        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_service.db.execute.return_value = mock_result

        result = mock_service.delete_server(uuid4(), uuid4())

        assert result is False


# =====================================================
# MCPToolHubService Tool CRUD 테스트
# =====================================================
class TestMCPToolHubServiceToolCRUD:
    """MCPToolHubService 도구 CRUD 테스트"""

    @pytest.fixture
    def mock_service(self):
        """Mock 서비스 생성"""
        from unittest.mock import MagicMock
        from app.services.mcp_toolhub import MCPToolHubService

        mock_db = MagicMock()
        return MCPToolHubService(db=mock_db)

    def test_create_tool(self, mock_service):
        """도구 생성"""
        from unittest.mock import MagicMock
        from app.services.mcp_toolhub import MCPToolCreate

        now = datetime.now(timezone.utc)
        tool_id = uuid4()
        server_id = uuid4()

        mock_row = MagicMock()
        mock_row.id = tool_id
        mock_row.mcp_server_id = server_id
        mock_row.tool_name = "new_tool"
        mock_row.description = "새 도구"
        mock_row.input_schema = {}
        mock_row.output_schema = None
        mock_row.is_enabled = True
        mock_row.usage_count = 0
        mock_row.avg_latency_ms = None
        mock_row.last_used_at = None
        mock_row.created_at = now

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_service.db.execute.return_value = mock_result

        data = MCPToolCreate(
            mcp_server_id=server_id,
            tool_name="new_tool",
            description="새 도구",
        )

        result = mock_service.create_tool(uuid4(), data)

        assert result.tool_name == "new_tool"
        mock_service.db.commit.assert_called_once()

    def test_get_tool_found(self, mock_service):
        """도구 조회 - 존재"""
        from unittest.mock import MagicMock

        now = datetime.now(timezone.utc)
        tool_id = uuid4()

        mock_row = MagicMock()
        mock_row.id = tool_id
        mock_row.mcp_server_id = uuid4()
        mock_row.tool_name = "existing_tool"
        mock_row.description = "기존 도구"
        mock_row.input_schema = {}
        mock_row.output_schema = None
        mock_row.is_enabled = True
        mock_row.usage_count = 50
        mock_row.avg_latency_ms = 100
        mock_row.last_used_at = now
        mock_row.created_at = now

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_service.db.execute.return_value = mock_result

        result = mock_service.get_tool(tool_id)

        assert result is not None
        assert result.tool_name == "existing_tool"

    def test_get_tool_not_found(self, mock_service):
        """도구 조회 - 미존재"""
        from unittest.mock import MagicMock

        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_service.db.execute.return_value = mock_result

        result = mock_service.get_tool(uuid4())

        assert result is None

    def test_get_tool_by_name_found(self, mock_service):
        """도구 이름으로 조회 - 존재"""
        from unittest.mock import MagicMock

        now = datetime.now(timezone.utc)
        server_id = uuid4()

        mock_row = MagicMock()
        mock_row.id = uuid4()
        mock_row.mcp_server_id = server_id
        mock_row.tool_name = "get_weather"
        mock_row.description = "날씨 조회"
        mock_row.input_schema = {"type": "object"}
        mock_row.output_schema = None
        mock_row.is_enabled = True
        mock_row.usage_count = 100
        mock_row.avg_latency_ms = 200
        mock_row.last_used_at = now
        mock_row.created_at = now

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_service.db.execute.return_value = mock_result

        result = mock_service.get_tool_by_name(server_id, "get_weather")

        assert result is not None
        assert result.tool_name == "get_weather"

    def test_get_tool_by_name_not_found(self, mock_service):
        """도구 이름으로 조회 - 미존재"""
        from unittest.mock import MagicMock

        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_service.db.execute.return_value = mock_result

        result = mock_service.get_tool_by_name(uuid4(), "nonexistent")

        assert result is None

    def test_list_tools(self, mock_service):
        """도구 목록 조회"""
        from unittest.mock import MagicMock

        now = datetime.now(timezone.utc)
        server_id = uuid4()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 3

        mock_rows = []
        for i in range(3):
            row = MagicMock()
            row.id = uuid4()
            row.mcp_server_id = server_id
            row.tool_name = f"tool_{i}"
            row.description = f"도구 {i}"
            row.input_schema = {}
            row.output_schema = None
            row.is_enabled = True
            row.usage_count = i * 10
            row.avg_latency_ms = 100 + i
            row.last_used_at = now
            row.created_at = now
            mock_rows.append(row)

        mock_list_result = MagicMock()
        mock_list_result.fetchall.return_value = mock_rows

        mock_service.db.execute.side_effect = [mock_count_result, mock_list_result]

        result = mock_service.list_tools(mcp_server_id=server_id)

        assert result.total == 3
        assert len(result.items) == 3

    def test_list_tools_with_enabled_filter(self, mock_service):
        """도구 목록 조회 - 활성화 필터"""
        from unittest.mock import MagicMock

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        now = datetime.now(timezone.utc)
        mock_row = MagicMock()
        mock_row.id = uuid4()
        mock_row.mcp_server_id = uuid4()
        mock_row.tool_name = "enabled_tool"
        mock_row.description = "활성 도구"
        mock_row.input_schema = {}
        mock_row.output_schema = None
        mock_row.is_enabled = True
        mock_row.usage_count = 10
        mock_row.avg_latency_ms = 100
        mock_row.last_used_at = now
        mock_row.created_at = now

        mock_list_result = MagicMock()
        mock_list_result.fetchall.return_value = [mock_row]

        mock_service.db.execute.side_effect = [mock_count_result, mock_list_result]

        result = mock_service.list_tools(is_enabled=True)

        assert result.total == 1

    def test_update_tool(self, mock_service):
        """도구 수정"""
        from unittest.mock import MagicMock
        from app.services.mcp_toolhub import MCPToolUpdate

        now = datetime.now(timezone.utc)
        tool_id = uuid4()

        mock_row = MagicMock()
        mock_row.id = tool_id
        mock_row.mcp_server_id = uuid4()
        mock_row.tool_name = "updated_tool"
        mock_row.description = "수정된 도구"
        mock_row.input_schema = {}
        mock_row.output_schema = None
        mock_row.is_enabled = False
        mock_row.usage_count = 50
        mock_row.avg_latency_ms = 150
        mock_row.last_used_at = now
        mock_row.created_at = now

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_service.db.execute.return_value = mock_result

        data = MCPToolUpdate(description="수정된 도구", is_enabled=False)
        result = mock_service.update_tool(tool_id, data)

        assert result is not None
        assert result.is_enabled is False
        mock_service.db.commit.assert_called_once()

    def test_update_tool_no_changes(self, mock_service):
        """도구 수정 - 변경 없음"""
        from unittest.mock import MagicMock
        from app.services.mcp_toolhub import MCPToolUpdate

        now = datetime.now(timezone.utc)
        tool_id = uuid4()

        mock_row = MagicMock()
        mock_row.id = tool_id
        mock_row.mcp_server_id = uuid4()
        mock_row.tool_name = "unchanged_tool"
        mock_row.description = "변경 없음"
        mock_row.input_schema = {}
        mock_row.output_schema = None
        mock_row.is_enabled = True
        mock_row.usage_count = 10
        mock_row.avg_latency_ms = 100
        mock_row.last_used_at = now
        mock_row.created_at = now

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_service.db.execute.return_value = mock_result

        data = MCPToolUpdate()
        result = mock_service.update_tool(tool_id, data)

        assert result is not None

    def test_delete_tool_success(self, mock_service):
        """도구 삭제 - 성공"""
        from unittest.mock import MagicMock

        mock_row = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_service.db.execute.return_value = mock_result

        result = mock_service.delete_tool(uuid4())

        assert result is True
        mock_service.db.commit.assert_called_once()

    def test_delete_tool_not_found(self, mock_service):
        """도구 삭제 - 미존재"""
        from unittest.mock import MagicMock

        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_service.db.execute.return_value = mock_result

        result = mock_service.delete_tool(uuid4())

        assert result is False


# =====================================================
# MCPToolHubService Call Tool 테스트
# =====================================================
class TestMCPToolHubServiceCallTool:
    """MCPToolHubService call_tool 테스트"""

    @pytest.fixture
    def mock_service(self):
        """Mock 서비스 생성"""
        from unittest.mock import MagicMock
        from app.services.mcp_toolhub import MCPToolHubService

        mock_db = MagicMock()
        mock_proxy = MagicMock()
        return MCPToolHubService(db=mock_db, proxy=mock_proxy)

    def test_call_tool_server_not_found(self, mock_service):
        """도구 호출 - 서버 미존재"""
        from unittest.mock import MagicMock
        from app.services.mcp_toolhub import MCPCallRequest as ToolHubCallRequest

        mock_service.get_server = MagicMock(return_value=None)

        request = ToolHubCallRequest(
            mcp_server_id=uuid4(),
            tool_name="test_tool",
        )

        result = mock_service.call_tool(uuid4(), request)

        assert result.success is False
        assert "not found" in result.error_message.lower()

    def test_call_tool_server_not_active(self, mock_service):
        """도구 호출 - 서버 비활성"""
        from unittest.mock import MagicMock
        from app.services.mcp_toolhub import (
            MCPCallRequest as ToolHubCallRequest,
            MCPServerResponse,
        )

        now = datetime.now(timezone.utc)
        mock_server = MCPServerResponse(
            id=uuid4(),
            tenant_id=uuid4(),
            name="Inactive Server",
            endpoint="https://inactive.mcp.com",
            status="inactive",
            created_at=now,
            updated_at=now,
        )

        mock_service.get_server = MagicMock(return_value=mock_server)

        request = ToolHubCallRequest(
            mcp_server_id=mock_server.id,
            tool_name="test_tool",
        )

        result = mock_service.call_tool(uuid4(), request)

        assert result.success is False
        assert "not active" in result.error_message.lower()

    def test_call_tool_tool_not_found(self, mock_service):
        """도구 호출 - 도구 미존재"""
        from unittest.mock import MagicMock
        from app.services.mcp_toolhub import (
            MCPCallRequest as ToolHubCallRequest,
            MCPServerResponse,
        )

        now = datetime.now(timezone.utc)
        mock_server = MCPServerResponse(
            id=uuid4(),
            tenant_id=uuid4(),
            name="Active Server",
            endpoint="https://active.mcp.com",
            status="active",
            created_at=now,
            updated_at=now,
        )

        mock_service.get_server = MagicMock(return_value=mock_server)
        mock_service.get_tool_by_name = MagicMock(return_value=None)

        request = ToolHubCallRequest(
            mcp_server_id=mock_server.id,
            tool_name="nonexistent",
        )

        result = mock_service.call_tool(uuid4(), request)

        assert result.success is False
        assert "not found" in result.error_message.lower()

    def test_call_tool_tool_disabled(self, mock_service):
        """도구 호출 - 도구 비활성"""
        from unittest.mock import MagicMock
        from app.services.mcp_toolhub import (
            MCPCallRequest as ToolHubCallRequest,
            MCPServerResponse,
            MCPToolResponse,
        )

        now = datetime.now(timezone.utc)
        server_id = uuid4()

        mock_server = MCPServerResponse(
            id=server_id,
            tenant_id=uuid4(),
            name="Active Server",
            endpoint="https://active.mcp.com",
            status="active",
            created_at=now,
            updated_at=now,
        )

        mock_tool = MCPToolResponse(
            id=uuid4(),
            mcp_server_id=server_id,
            tool_name="disabled_tool",
            is_enabled=False,
            created_at=now,
        )

        mock_service.get_server = MagicMock(return_value=mock_server)
        mock_service.get_tool_by_name = MagicMock(return_value=mock_tool)

        request = ToolHubCallRequest(
            mcp_server_id=server_id,
            tool_name="disabled_tool",
        )

        result = mock_service.call_tool(uuid4(), request)

        assert result.success is False
        assert "disabled" in result.error_message.lower()


# =====================================================
# MCPToolHubService Health Check 테스트
# =====================================================
class TestMCPToolHubServiceHealthCheck:
    """MCPToolHubService 헬스체크 테스트"""

    @pytest.fixture
    def mock_service(self):
        """Mock 서비스 생성"""
        from unittest.mock import MagicMock
        from app.services.mcp_toolhub import MCPToolHubService

        mock_db = MagicMock()
        return MCPToolHubService(db=mock_db)

    def test_health_check_server_not_found(self, mock_service):
        """헬스체크 - 서버 미존재"""
        from unittest.mock import MagicMock

        mock_service.get_server = MagicMock(return_value=None)

        result = mock_service.health_check(uuid4(), uuid4())

        assert result.status == "unknown"
        assert result.error == "Server not found"

    def test_health_check_healthy(self, mock_service):
        """헬스체크 - 정상"""
        from unittest.mock import MagicMock
        from app.services.mcp_toolhub import MCPServerResponse

        now = datetime.now(timezone.utc)
        server_id = uuid4()

        mock_server = MCPServerResponse(
            id=server_id,
            tenant_id=uuid4(),
            name="Healthy Server",
            endpoint="https://healthy.mcp.com",
            status="active",
            created_at=now,
            updated_at=now,
        )

        mock_service.get_server = MagicMock(return_value=mock_server)
        mock_service._perform_health_check = MagicMock(return_value=(True, 50, None))
        mock_service._update_health_status = MagicMock()

        result = mock_service.health_check(server_id, uuid4())

        assert result.status == "healthy"
        assert result.latency_ms == 50

    def test_health_check_unhealthy(self, mock_service):
        """헬스체크 - 비정상"""
        from unittest.mock import MagicMock
        from app.services.mcp_toolhub import MCPServerResponse

        now = datetime.now(timezone.utc)
        server_id = uuid4()

        mock_server = MCPServerResponse(
            id=server_id,
            tenant_id=uuid4(),
            name="Unhealthy Server",
            endpoint="https://unhealthy.mcp.com",
            status="active",
            created_at=now,
            updated_at=now,
        )

        mock_service.get_server = MagicMock(return_value=mock_server)
        mock_service._perform_health_check = MagicMock(return_value=(False, 10000, "Timeout"))
        mock_service._update_health_status = MagicMock()

        result = mock_service.health_check(server_id, uuid4())

        assert result.status == "unhealthy"
        assert result.error == "Timeout"


# =====================================================
# MCPToolHubService Circuit Breaker 테스트
# =====================================================
class TestMCPToolHubServiceCircuitBreaker:
    """MCPToolHubService Circuit Breaker 테스트"""

    @pytest.fixture
    def mock_service(self):
        """Mock 서비스 생성"""
        from unittest.mock import MagicMock
        from app.services.mcp_toolhub import MCPToolHubService

        mock_db = MagicMock()
        return MCPToolHubService(db=mock_db)

    def test_get_circuit_breaker_state_not_found(self, mock_service):
        """Circuit Breaker 상태 조회 - 서버 미존재"""
        from unittest.mock import MagicMock

        mock_service.get_server = MagicMock(return_value=None)

        result = mock_service.get_circuit_breaker_state(uuid4(), uuid4())

        assert result is None

    def test_get_circuit_breaker_state_found(self, mock_service):
        """Circuit Breaker 상태 조회 - 존재"""
        from unittest.mock import MagicMock
        from app.services.mcp_toolhub import MCPServerResponse

        now = datetime.now(timezone.utc)
        server_id = uuid4()

        mock_server = MCPServerResponse(
            id=server_id,
            tenant_id=uuid4(),
            name="CB Test Server",
            endpoint="https://cb.mcp.com",
            circuit_breaker_state="open",
            fail_count=5,
            created_at=now,
            updated_at=now,
        )

        mock_service.get_server = MagicMock(return_value=mock_server)

        result = mock_service.get_circuit_breaker_state(server_id, uuid4())

        assert result is not None
        assert result.state == "open"
        assert result.fail_count == 5

    def test_reset_circuit_breaker_success(self, mock_service):
        """Circuit Breaker 리셋 - 성공"""
        from unittest.mock import MagicMock

        mock_row = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_service.db.execute.return_value = mock_result

        result = mock_service.reset_circuit_breaker(uuid4(), uuid4())

        assert result is True
        mock_service.db.commit.assert_called_once()

    def test_reset_circuit_breaker_not_found(self, mock_service):
        """Circuit Breaker 리셋 - 서버 미존재"""
        from unittest.mock import MagicMock

        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_service.db.execute.return_value = mock_result

        result = mock_service.reset_circuit_breaker(uuid4(), uuid4())

        assert result is False


# =====================================================
# MCPToolHubService Private Methods 테스트
# =====================================================
class TestMCPToolHubServicePrivateMethods:
    """MCPToolHubService 프라이빗 메서드 테스트"""

    @pytest.fixture
    def mock_service(self):
        """Mock 서비스 생성"""
        from unittest.mock import MagicMock
        from app.services.mcp_toolhub import MCPToolHubService

        mock_db = MagicMock()
        return MCPToolHubService(db=mock_db)

    def test_row_to_server(self, mock_service):
        """_row_to_server 변환"""
        from unittest.mock import MagicMock

        now = datetime.now(timezone.utc)
        server_id = uuid4()
        tenant_id = uuid4()

        mock_row = MagicMock()
        mock_row.id = server_id
        mock_row.tenant_id = tenant_id
        mock_row.name = "Test Server"
        mock_row.endpoint = "https://test.mcp.com"
        mock_row.protocol = "stdio"
        mock_row.config = {"key": "value"}
        mock_row.auth_config = None
        mock_row.status = "active"
        mock_row.last_health_check_at = now
        mock_row.circuit_breaker_state = "closed"
        mock_row.fail_count = 0
        mock_row.created_at = now
        mock_row.updated_at = now

        result = mock_service._row_to_server(mock_row)

        assert result.id == server_id
        assert result.name == "Test Server"
        assert result.config == {"key": "value"}

    def test_row_to_server_non_dict_config(self, mock_service):
        """_row_to_server - config가 dict가 아닌 경우"""
        from unittest.mock import MagicMock

        now = datetime.now(timezone.utc)

        mock_row = MagicMock()
        mock_row.id = uuid4()
        mock_row.tenant_id = uuid4()
        mock_row.name = "Test Server"
        mock_row.endpoint = "https://test.mcp.com"
        mock_row.protocol = "stdio"
        mock_row.config = "not_a_dict"
        mock_row.auth_config = 123
        mock_row.status = "active"
        mock_row.last_health_check_at = None
        mock_row.circuit_breaker_state = "closed"
        mock_row.fail_count = 0
        mock_row.created_at = now
        mock_row.updated_at = now

        result = mock_service._row_to_server(mock_row)

        assert result.config == {}
        assert result.auth_config is None

    def test_row_to_tool(self, mock_service):
        """_row_to_tool 변환"""
        from unittest.mock import MagicMock

        now = datetime.now(timezone.utc)
        tool_id = uuid4()
        server_id = uuid4()

        mock_row = MagicMock()
        mock_row.id = tool_id
        mock_row.mcp_server_id = server_id
        mock_row.tool_name = "test_tool"
        mock_row.description = "테스트 도구"
        mock_row.input_schema = {"type": "object"}
        mock_row.output_schema = {"type": "array"}
        mock_row.is_enabled = True
        mock_row.usage_count = 100
        mock_row.avg_latency_ms = 150
        mock_row.last_used_at = now
        mock_row.created_at = now

        result = mock_service._row_to_tool(mock_row)

        assert result.id == tool_id
        assert result.tool_name == "test_tool"
        assert result.input_schema == {"type": "object"}

    def test_row_to_tool_non_dict_schema(self, mock_service):
        """_row_to_tool - schema가 dict가 아닌 경우"""
        from unittest.mock import MagicMock

        now = datetime.now(timezone.utc)

        mock_row = MagicMock()
        mock_row.id = uuid4()
        mock_row.mcp_server_id = uuid4()
        mock_row.tool_name = "test_tool"
        mock_row.description = None
        mock_row.input_schema = "not_a_dict"
        mock_row.output_schema = 123
        mock_row.is_enabled = True
        mock_row.usage_count = 0
        mock_row.avg_latency_ms = None
        mock_row.last_used_at = None
        mock_row.created_at = now

        result = mock_service._row_to_tool(mock_row)

        assert result.input_schema == {}
        assert result.output_schema is None

    def test_save_call_log(self, mock_service):
        """_save_call_log 호출 로그 저장"""
        from unittest.mock import MagicMock

        log_id = uuid4()
        mock_row = MagicMock()
        mock_row.id = log_id

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_service.db.execute.return_value = mock_result

        result = mock_service._save_call_log(
            tenant_id=uuid4(),
            mcp_tool_id=uuid4(),
            workflow_instance_id=uuid4(),
            input_data={"key": "value"},
            output_data={"result": "ok"},
            success=True,
            error_message=None,
            latency_ms=100,
            trace_id="trace-123",
        )

        assert result == log_id
        mock_service.db.commit.assert_called_once()

    def test_save_call_log_failure(self, mock_service):
        """_save_call_log 저장 실패"""
        from unittest.mock import MagicMock

        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_service.db.execute.return_value = mock_result

        result = mock_service._save_call_log(
            tenant_id=uuid4(),
            mcp_tool_id=uuid4(),
            workflow_instance_id=None,
            input_data={},
            output_data=None,
            success=False,
            error_message="Error occurred",
            latency_ms=5000,
            trace_id=None,
        )

        assert result is None

    def test_update_tool_stats_success(self, mock_service):
        """_update_tool_stats 성공 케이스"""
        mock_service._update_tool_stats(
            tool_id=uuid4(),
            success=True,
            latency_ms=100,
        )

        mock_service.db.execute.assert_called_once()
        mock_service.db.commit.assert_called_once()

    def test_update_tool_stats_failure(self, mock_service):
        """_update_tool_stats 실패 케이스"""
        mock_service._update_tool_stats(
            tool_id=uuid4(),
            success=False,
            latency_ms=5000,
        )

        mock_service.db.execute.assert_called_once()
        mock_service.db.commit.assert_called_once()

    def test_update_health_status(self, mock_service):
        """_update_health_status 상태 업데이트"""
        mock_service._update_health_status(
            server_id=uuid4(),
            status="healthy",
            error=None,
        )

        mock_service.db.execute.assert_called_once()
        mock_service.db.commit.assert_called_once()


# =====================================================
# Perform Health Check 테스트
# =====================================================
class TestPerformHealthCheck:
    """_perform_health_check 테스트"""

    @pytest.fixture
    def mock_service(self):
        """Mock 서비스 생성"""
        from unittest.mock import MagicMock
        from app.services.mcp_toolhub import MCPToolHubService

        mock_db = MagicMock()
        return MCPToolHubService(db=mock_db)

    def test_health_check_success(self, mock_service):
        """헬스체크 성공"""
        from unittest.mock import MagicMock, patch

        with patch("httpx.Client") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200

            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_class.return_value = mock_client

            is_healthy, latency_ms, error = mock_service._perform_health_check(
                "https://healthy.mcp.com"
            )

            assert is_healthy is True
            assert latency_ms is not None
            assert error is None

    def test_health_check_http_error(self, mock_service):
        """헬스체크 HTTP 에러"""
        from unittest.mock import MagicMock, patch

        with patch("httpx.Client") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 500

            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_class.return_value = mock_client

            is_healthy, latency_ms, error = mock_service._perform_health_check(
                "https://error.mcp.com"
            )

            assert is_healthy is False
            assert "500" in error

    def test_health_check_timeout(self, mock_service):
        """헬스체크 타임아웃"""
        from unittest.mock import MagicMock, patch
        import httpx

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get.side_effect = httpx.TimeoutException("Timeout")
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_class.return_value = mock_client

            is_healthy, latency_ms, error = mock_service._perform_health_check(
                "https://slow.mcp.com"
            )

            assert is_healthy is False
            assert error == "Timeout"

    def test_health_check_connect_error(self, mock_service):
        """헬스체크 연결 에러"""
        from unittest.mock import MagicMock, patch
        import httpx

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get.side_effect = httpx.ConnectError("Connection refused")
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_class.return_value = mock_client

            is_healthy, latency_ms, error = mock_service._perform_health_check(
                "https://unreachable.mcp.com"
            )

            assert is_healthy is False
            assert "Connection error" in error

    def test_health_check_generic_exception(self, mock_service):
        """헬스체크 일반 예외"""
        from unittest.mock import MagicMock, patch

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get.side_effect = Exception("Unknown error")
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_class.return_value = mock_client

            is_healthy, latency_ms, error = mock_service._perform_health_check(
                "https://broken.mcp.com"
            )

            assert is_healthy is False
            assert error == "Unknown error"

    def test_health_check_url_normalization(self, mock_service):
        """헬스체크 URL 정규화"""
        from unittest.mock import MagicMock, patch

        with patch("httpx.Client") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200

            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_class.return_value = mock_client

            mock_service._perform_health_check("https://api.mcp.com/v1/")

            # /health가 추가된 URL로 호출되는지 확인
            call_args = mock_client.get.call_args
            assert "/health" in call_args[0][0]


# =====================================================
# Factory Function 테스트
# =====================================================
class TestGetMCPToolHubService:
    """get_mcp_toolhub_service 팩토리 함수 테스트"""

    def test_with_provided_db(self):
        """제공된 DB 세션 사용"""
        from unittest.mock import MagicMock
        from app.services.mcp_toolhub import get_mcp_toolhub_service

        mock_db = MagicMock()
        service = get_mcp_toolhub_service(db=mock_db)

        assert service.db == mock_db

    def test_with_default_db(self):
        """기본 DB 세션 생성"""
        from unittest.mock import MagicMock, patch
        from app.services.mcp_toolhub import get_mcp_toolhub_service

        mock_db = MagicMock()

        with patch("app.database.SessionLocal", return_value=mock_db):
            service = get_mcp_toolhub_service(db=None)

            assert service.db == mock_db
