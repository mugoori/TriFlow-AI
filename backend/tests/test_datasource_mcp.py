"""
DataSource MCP Service 및 API 테스트

MES/ERP DataSource 기반 MCP 도구 통합 기능 테스트
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.datasource_mcp_service import DataSourceMCPService
from app.mcp_wrappers import MESWrapper, ERPWrapper, MCPToolDefinition


class TestDataSourceMCPService:
    """DataSourceMCPService 단위 테스트"""

    def test_get_tools_for_mes(self):
        """MES 타입에 대한 도구 목록 조회"""
        service = DataSourceMCPService(None)
        tools = service.get_tools_for_source_type("mes")

        assert len(tools) == 5
        tool_names = [t.name for t in tools]
        assert "get_production_status" in tool_names
        assert "get_defect_data" in tool_names
        assert "get_equipment_status" in tool_names
        assert "get_work_orders" in tool_names
        assert "update_production_count" in tool_names

    def test_get_tools_for_erp(self):
        """ERP 타입에 대한 도구 목록 조회"""
        service = DataSourceMCPService(None)
        tools = service.get_tools_for_source_type("erp")

        assert len(tools) == 6
        tool_names = [t.name for t in tools]
        assert "get_inventory" in tool_names
        assert "get_purchase_orders" in tool_names
        assert "create_purchase_order" in tool_names
        assert "get_sales_orders" in tool_names
        assert "get_bom" in tool_names
        assert "check_material_availability" in tool_names

    def test_get_tools_for_unknown_type(self):
        """알 수 없는 타입에 대한 빈 목록 반환"""
        service = DataSourceMCPService(None)
        tools = service.get_tools_for_source_type("unknown")

        assert len(tools) == 0

    def test_tool_definitions_have_required_fields(self):
        """도구 정의에 필수 필드 존재 확인"""
        service = DataSourceMCPService(None)

        for source_type in ["mes", "erp"]:
            tools = service.get_tools_for_source_type(source_type)
            for tool in tools:
                assert isinstance(tool, MCPToolDefinition)
                assert tool.name is not None
                assert tool.description is not None
                assert tool.input_schema is not None
                assert isinstance(tool.input_schema, dict)


class TestMESWrapper:
    """MESWrapper 단위 테스트"""

    def test_mes_wrapper_initialization(self):
        """MES 래퍼 초기화 테스트"""
        wrapper = MESWrapper(
            base_url="http://localhost:8080",
            api_key="test-key"
        )
        assert wrapper.name == "MES Wrapper"
        assert wrapper.base_url == "http://localhost:8080"
        assert wrapper.api_key == "test-key"

    def test_mes_wrapper_get_tools(self):
        """MES 래퍼 도구 목록 테스트"""
        wrapper = MESWrapper(
            base_url="http://localhost:8080"
        )
        tools = wrapper.get_tools()

        assert len(tools) == 5
        assert all(isinstance(t, MCPToolDefinition) for t in tools)

    @pytest.mark.asyncio
    async def test_mes_wrapper_unknown_tool(self):
        """알 수 없는 도구 호출 시 에러 반환"""
        wrapper = MESWrapper(base_url="http://localhost:8080")
        result = await wrapper.call_tool("unknown_tool", {})

        assert "error" in result
        assert "Unknown tool" in result["error"]

        await wrapper.close()


class TestERPWrapper:
    """ERPWrapper 단위 테스트"""

    def test_erp_wrapper_initialization(self):
        """ERP 래퍼 초기화 테스트"""
        wrapper = ERPWrapper(
            base_url="http://localhost:8081",
            api_key="erp-key",
            timeout=60.0
        )
        assert wrapper.name == "ERP Wrapper"
        assert wrapper.base_url == "http://localhost:8081"
        assert wrapper.timeout == 60.0

    def test_erp_wrapper_get_tools(self):
        """ERP 래퍼 도구 목록 테스트"""
        wrapper = ERPWrapper(base_url="http://localhost:8081")
        tools = wrapper.get_tools()

        assert len(tools) == 6
        assert all(isinstance(t, MCPToolDefinition) for t in tools)

    @pytest.mark.asyncio
    async def test_erp_wrapper_unknown_tool(self):
        """알 수 없는 도구 호출 시 에러 반환"""
        wrapper = ERPWrapper(base_url="http://localhost:8081")
        result = await wrapper.call_tool("unknown_tool", {})

        assert "error" in result
        assert "Unknown tool" in result["error"]

        await wrapper.close()


class TestDataSourceMCPServiceWithMockDB:
    """DB Mock을 사용한 DataSourceMCPService 테스트"""

    def create_mock_datasource(self, source_type="mes"):
        """Mock DataSource 생성"""
        mock_source = MagicMock()
        mock_source.source_id = uuid4()
        mock_source.tenant_id = uuid4()
        mock_source.name = f"Test {source_type.upper()}"
        mock_source.source_type = source_type
        mock_source.source_system = "custom"
        mock_source.connection_config = {
            "base_url": f"http://{source_type}-server.test.com",
            "api_key": "test-api-key"
        }
        mock_source.status = "active"
        return mock_source

    def test_get_source(self):
        """DataSource 조회 테스트"""
        mock_db = MagicMock()
        mock_source = self.create_mock_datasource("mes")

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_source
        mock_db.query.return_value = mock_query

        service = DataSourceMCPService(mock_db)
        result = service.get_source(mock_source.source_id, mock_source.tenant_id)

        assert result == mock_source

    def test_get_source_not_found(self):
        """존재하지 않는 DataSource 조회"""
        mock_db = MagicMock()

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        mock_db.query.return_value = mock_query

        service = DataSourceMCPService(mock_db)
        result = service.get_source(uuid4(), uuid4())

        assert result is None

    def test_get_active_sources(self):
        """활성 DataSource 목록 조회"""
        mock_db = MagicMock()
        mock_sources = [
            self.create_mock_datasource("mes"),
            self.create_mock_datasource("mes"),
        ]

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_sources
        mock_db.query.return_value = mock_query

        service = DataSourceMCPService(mock_db)
        tenant_id = mock_sources[0].tenant_id
        result = service.get_active_sources(tenant_id, "mes")

        assert len(result) == 2

    def test_get_all_tools_for_tenant(self):
        """테넌트의 모든 DataSource 도구 조회"""
        mock_db = MagicMock()
        mock_sources = [
            self.create_mock_datasource("mes"),
            self.create_mock_datasource("erp"),
        ]

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_sources
        mock_db.query.return_value = mock_query

        service = DataSourceMCPService(mock_db)
        tenant_id = mock_sources[0].tenant_id
        result = service.get_all_tools_for_tenant(tenant_id)

        assert len(result) == 2
        # MES source has 5 tools, ERP has 6 tools
        mes_source = next(s for s in result if s["source_type"] == "mes")
        erp_source = next(s for s in result if s["source_type"] == "erp")
        assert len(mes_source["tools"]) == 5
        assert len(erp_source["tools"]) == 6


class TestDataSourceMCPServiceCallTool:
    """도구 호출 테스트"""

    @pytest.mark.asyncio
    async def test_call_tool_source_not_found(self):
        """존재하지 않는 DataSource로 도구 호출"""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        mock_db.query.return_value = mock_query

        service = DataSourceMCPService(mock_db)
        result = await service.call_tool(
            source_id=uuid4(),
            tenant_id=uuid4(),
            tool_name="get_production_status",
            args={}
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_call_tool_unsupported_type(self):
        """지원하지 않는 source_type으로 도구 호출"""
        mock_db = MagicMock()
        mock_source = MagicMock()
        mock_source.source_id = uuid4()
        mock_source.tenant_id = uuid4()
        mock_source.source_type = "unsupported"
        mock_source.connection_config = {"base_url": "http://test.com"}

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_source
        mock_db.query.return_value = mock_query

        service = DataSourceMCPService(mock_db)
        result = await service.call_tool(
            source_id=mock_source.source_id,
            tenant_id=mock_source.tenant_id,
            tool_name="some_tool",
            args={}
        )

        assert result["success"] is False
        assert "unsupported" in result["error"].lower()


class TestHealthCheck:
    """헬스체크 테스트"""

    @pytest.mark.asyncio
    async def test_health_check_source_not_found(self):
        """존재하지 않는 DataSource 헬스체크"""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        mock_db.query.return_value = mock_query

        service = DataSourceMCPService(mock_db)
        result = await service.health_check(uuid4(), uuid4())

        # health_check returns "unhealthy" status when source not found
        assert result["status"] == "unhealthy"
        assert "not found" in result["error"].lower()


# API 엔드포인트 테스트는 PostgreSQL이 필요하므로 requires_db 마커 사용
@pytest.mark.requires_db
class TestDataSourceMCPAPIEndpoints:
    """DataSource MCP API 엔드포인트 테스트 (PostgreSQL 필요)"""

    @pytest.mark.asyncio
    async def test_list_datasource_tools_unauthorized(self, client):
        """인증 없이 도구 목록 조회 시 401"""
        response = await client.get("/api/v1/mcp/datasource-tools")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_datasource_tools_empty(self, authenticated_client):
        """DataSource가 없을 때 빈 목록 반환"""
        response = await authenticated_client.get("/api/v1/mcp/datasource-tools")
        assert response.status_code == 200
        data = response.json()
        assert "sources" in data
        assert data["total_sources"] == 0

    @pytest.mark.asyncio
    async def test_call_datasource_tool_not_found(self, authenticated_client):
        """존재하지 않는 DataSource로 도구 호출"""
        fake_id = str(uuid4())
        response = await authenticated_client.post(
            f"/api/v1/mcp/datasource-tools/{fake_id}/call",
            params={"tool_name": "get_production_status"},
            json={}
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_datasource_health_not_found(self, authenticated_client):
        """존재하지 않는 DataSource 헬스체크"""
        fake_id = str(uuid4())
        response = await authenticated_client.get(
            f"/api/v1/mcp/datasource-tools/{fake_id}/health"
        )
        # health_check returns error status but HTTP 200
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
