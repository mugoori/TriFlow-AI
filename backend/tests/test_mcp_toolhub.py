"""
MCP ToolHub Tests

테스트 대상:
1. Circuit Breaker 상태 전이
2. HTTPMCPProxy 호출 (Mock)
3. MCPToolHubService CRUD
4. Schema Drift Detection
"""

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

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
from app.services.mcp_proxy import MCPCallResponse, MockMCPProxy


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
            timeout_seconds=1,  # 테스트를 위해 짧게 설정
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

        # 타임아웃 대기 (1초)
        await asyncio.sleep(1.1)

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

        # 타임아웃 대기 → HALF_OPEN
        await asyncio.sleep(1.1)
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

        # 타임아웃 대기 → HALF_OPEN
        await asyncio.sleep(1.1)
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
