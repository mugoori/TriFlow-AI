"""
MCP Wrappers 테스트
app/mcp_wrappers의 base_wrapper.py 및 mes_wrapper.py 테스트
"""
import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch
import httpx

from fastapi.testclient import TestClient


# ========== MCPToolDefinition 테스트 ==========


class TestMCPToolDefinition:
    """MCPToolDefinition 모델 테스트"""

    def test_create_with_defaults(self):
        """기본값으로 생성"""
        from app.mcp_wrappers.base_wrapper import MCPToolDefinition

        tool = MCPToolDefinition(name="test_tool", description="Test tool")

        assert tool.name == "test_tool"
        assert tool.description == "Test tool"
        assert tool.input_schema == {"type": "object", "properties": {}}

    def test_create_with_schema(self):
        """스키마와 함께 생성"""
        from app.mcp_wrappers.base_wrapper import MCPToolDefinition

        schema = {
            "type": "object",
            "properties": {"param1": {"type": "string"}},
            "required": ["param1"],
        }

        tool = MCPToolDefinition(
            name="test_tool", description="Test tool", input_schema=schema
        )

        assert tool.input_schema == schema


# ========== MCPToolCallRequest 테스트 ==========


class TestMCPToolCallRequest:
    """MCPToolCallRequest 모델 테스트"""

    def test_create_with_defaults(self):
        """기본값으로 생성"""
        from app.mcp_wrappers.base_wrapper import MCPToolCallRequest

        request = MCPToolCallRequest(name="test_tool")

        assert request.name == "test_tool"
        assert request.arguments == {}

    def test_create_with_arguments(self):
        """인자와 함께 생성"""
        from app.mcp_wrappers.base_wrapper import MCPToolCallRequest

        request = MCPToolCallRequest(
            name="test_tool", arguments={"key": "value"}
        )

        assert request.arguments == {"key": "value"}


# ========== MCPContent 테스트 ==========


class TestMCPContent:
    """MCPContent 모델 테스트"""

    def test_create(self):
        """생성"""
        from app.mcp_wrappers.base_wrapper import MCPContent

        content = MCPContent(text="Hello, World!")

        assert content.type == "text"
        assert content.text == "Hello, World!"


# ========== MCPToolCallResponse 테스트 ==========


class TestMCPToolCallResponse:
    """MCPToolCallResponse 모델 테스트"""

    def test_create(self):
        """생성"""
        from app.mcp_wrappers.base_wrapper import MCPToolCallResponse, MCPContent

        response = MCPToolCallResponse(
            content=[MCPContent(text="Result")], isError=False
        )

        assert len(response.content) == 1
        assert response.isError is False


# ========== MCPWrapperBase 테스트 ==========


class TestMCPWrapperBase:
    """MCPWrapperBase 추상 클래스 테스트"""

    def test_concrete_implementation(self):
        """구체 구현 테스트"""
        from app.mcp_wrappers.base_wrapper import MCPWrapperBase, MCPToolDefinition

        class TestWrapper(MCPWrapperBase):
            def get_tools(self):
                return [
                    MCPToolDefinition(name="tool1", description="Tool 1"),
                    MCPToolDefinition(name="tool2", description="Tool 2"),
                ]

            async def call_tool(self, tool_name, args):
                return {"result": f"Called {tool_name}"}

        wrapper = TestWrapper(name="Test Wrapper")

        assert wrapper.name == "Test Wrapper"
        assert len(wrapper.get_tools()) == 2

    def test_get_tools_cached(self):
        """도구 캐시 테스트"""
        from app.mcp_wrappers.base_wrapper import MCPWrapperBase, MCPToolDefinition

        class TestWrapper(MCPWrapperBase):
            def __init__(self):
                super().__init__(name="Test")
                self.call_count = 0

            def get_tools(self):
                self.call_count += 1
                return [MCPToolDefinition(name="tool1", description="Tool 1")]

            async def call_tool(self, tool_name, args):
                return {}

        wrapper = TestWrapper()

        # 첫 번째 호출
        tools1 = wrapper.get_tools_cached()
        # 두 번째 호출 (캐시됨)
        tools2 = wrapper.get_tools_cached()

        assert wrapper.call_count == 1
        assert tools1 == tools2

    def test_validate_tool_name_valid(self):
        """유효한 도구 이름"""
        from app.mcp_wrappers.base_wrapper import MCPWrapperBase, MCPToolDefinition

        class TestWrapper(MCPWrapperBase):
            def get_tools(self):
                return [MCPToolDefinition(name="valid_tool", description="Valid")]

            async def call_tool(self, tool_name, args):
                return {}

        wrapper = TestWrapper()

        assert wrapper.validate_tool_name("valid_tool") is True

    def test_validate_tool_name_invalid(self):
        """유효하지 않은 도구 이름"""
        from app.mcp_wrappers.base_wrapper import MCPWrapperBase, MCPToolDefinition

        class TestWrapper(MCPWrapperBase):
            def get_tools(self):
                return [MCPToolDefinition(name="valid_tool", description="Valid")]

            async def call_tool(self, tool_name, args):
                return {}

        wrapper = TestWrapper()

        assert wrapper.validate_tool_name("invalid_tool") is False

    @pytest.mark.asyncio
    async def test_health_check_default(self):
        """기본 헬스체크"""
        from app.mcp_wrappers.base_wrapper import MCPWrapperBase

        class TestWrapper(MCPWrapperBase):
            def get_tools(self):
                return []

            async def call_tool(self, tool_name, args):
                return {}

        wrapper = TestWrapper(name="Test Wrapper")
        result = await wrapper.health_check()

        assert result["status"] == "healthy"
        assert "timestamp" in result
        assert result["wrapper"] == "Test Wrapper"


# ========== create_mcp_app 테스트 ==========


class TestCreateMCPApp:
    """create_mcp_app 함수 테스트"""

    @pytest.fixture
    def test_wrapper(self):
        """테스트용 래퍼"""
        from app.mcp_wrappers.base_wrapper import MCPWrapperBase, MCPToolDefinition

        class TestWrapper(MCPWrapperBase):
            def get_tools(self):
                return [
                    MCPToolDefinition(
                        name="test_tool",
                        description="Test tool",
                        input_schema={
                            "type": "object",
                            "properties": {"param": {"type": "string"}},
                        },
                    )
                ]

            async def call_tool(self, tool_name, args):
                if tool_name == "test_tool":
                    return {"result": args.get("param", "default")}
                return {"error": "Unknown tool"}

        return TestWrapper(name="Test Wrapper")

    @pytest.fixture
    def client(self, test_wrapper):
        """테스트 클라이언트"""
        from app.mcp_wrappers.base_wrapper import create_mcp_app

        app = create_mcp_app(test_wrapper)
        return TestClient(app)

    def test_root_endpoint(self, client):
        """루트 엔드포인트"""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Wrapper"
        assert data["type"] == "mcp_wrapper"

    def test_list_tools(self, client):
        """도구 목록"""
        response = client.post("/tools/list")

        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert len(data["tools"]) == 1
        assert data["tools"][0]["name"] == "test_tool"

    def test_call_tool_success(self, client):
        """도구 호출 성공"""
        response = client.post(
            "/tools/call",
            json={"name": "test_tool", "arguments": {"param": "hello"}},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["isError"] is False
        assert len(data["content"]) == 1
        # JSON 파싱
        result = json.loads(data["content"][0]["text"])
        assert result["result"] == "hello"

    def test_call_tool_not_found(self, client):
        """도구 찾을 수 없음"""
        response = client.post(
            "/tools/call",
            json={"name": "unknown_tool", "arguments": {}},
        )

        assert response.status_code == 404

    def test_health_endpoint(self, client):
        """헬스체크 엔드포인트"""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data


class TestCreateMCPAppWithError:
    """create_mcp_app 에러 처리 테스트"""

    @pytest.fixture
    def error_wrapper(self):
        """에러를 발생시키는 래퍼"""
        from app.mcp_wrappers.base_wrapper import MCPWrapperBase, MCPToolDefinition

        class ErrorWrapper(MCPWrapperBase):
            def get_tools(self):
                return [
                    MCPToolDefinition(name="error_tool", description="Error tool")
                ]

            async def call_tool(self, tool_name, args):
                raise ValueError("Intentional error")

        return ErrorWrapper(name="Error Wrapper")

    @pytest.fixture
    def client(self, error_wrapper):
        """테스트 클라이언트"""
        from app.mcp_wrappers.base_wrapper import create_mcp_app

        app = create_mcp_app(error_wrapper)
        return TestClient(app)

    def test_call_tool_error(self, client):
        """도구 호출 에러"""
        response = client.post(
            "/tools/call",
            json={"name": "error_tool", "arguments": {}},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["isError"] is True
        assert "Error" in data["content"][0]["text"]


# ========== MESWrapper 테스트 ==========


class TestMESWrapperInit:
    """MESWrapper 초기화 테스트"""

    def test_init_basic(self):
        """기본 초기화"""
        from app.mcp_wrappers.mes_wrapper import MESWrapper

        wrapper = MESWrapper(base_url="http://mes.example.com")

        assert wrapper.base_url == "http://mes.example.com"
        assert wrapper.api_key is None
        assert wrapper.timeout == 30.0
        assert wrapper.name == "MES Wrapper"

    def test_init_with_options(self):
        """옵션과 함께 초기화"""
        from app.mcp_wrappers.mes_wrapper import MESWrapper

        wrapper = MESWrapper(
            base_url="http://mes.example.com/",
            api_key="test-key",
            timeout=60.0,
        )

        assert wrapper.base_url == "http://mes.example.com"
        assert wrapper.api_key == "test-key"
        assert wrapper.timeout == 60.0


class TestMESWrapperGetTools:
    """MESWrapper get_tools 테스트"""

    def test_get_tools(self):
        """도구 목록"""
        from app.mcp_wrappers.mes_wrapper import MESWrapper

        wrapper = MESWrapper(base_url="http://mes.example.com")
        tools = wrapper.get_tools()

        assert len(tools) == 5
        tool_names = [t.name for t in tools]
        assert "get_production_status" in tool_names
        assert "get_defect_data" in tool_names
        assert "get_equipment_status" in tool_names
        assert "get_work_orders" in tool_names
        assert "update_production_count" in tool_names


class TestMESWrapperCallTool:
    """MESWrapper call_tool 테스트"""

    @pytest.fixture
    def wrapper(self):
        """MESWrapper 인스턴스"""
        from app.mcp_wrappers.mes_wrapper import MESWrapper

        return MESWrapper(base_url="http://mes.example.com")

    @pytest.mark.asyncio
    async def test_call_unknown_tool(self, wrapper):
        """알 수 없는 도구"""
        result = await wrapper.call_tool("unknown_tool", {})

        assert "error" in result

    @pytest.mark.asyncio
    async def test_call_get_production_status(self, wrapper):
        """get_production_status 호출"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"line_id": "LINE-001", "production": 100}
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            wrapper.client, "get", new=AsyncMock(return_value=mock_response)
        ):
            result = await wrapper.call_tool(
                "get_production_status", {"line_id": "LINE-001"}
            )

            assert result == {"line_id": "LINE-001", "production": 100}

    @pytest.mark.asyncio
    async def test_call_get_production_status_with_date(self, wrapper):
        """get_production_status 날짜 파라미터"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"production": 100}
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            wrapper.client, "get", new=AsyncMock(return_value=mock_response)
        ) as mock_get:
            await wrapper.call_tool(
                "get_production_status",
                {"line_id": "LINE-001", "date": "2024-01-01"},
            )

            call_args = mock_get.call_args
            assert call_args[1]["params"]["line_id"] == "LINE-001"
            assert call_args[1]["params"]["date"] == "2024-01-01"

    @pytest.mark.asyncio
    async def test_call_get_defect_data(self, wrapper):
        """get_defect_data 호출"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"defects": []}
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            wrapper.client, "get", new=AsyncMock(return_value=mock_response)
        ):
            result = await wrapper.call_tool(
                "get_defect_data", {"line_id": "LINE-001"}
            )

            assert result == {"defects": []}

    @pytest.mark.asyncio
    async def test_call_get_defect_data_with_params(self, wrapper):
        """get_defect_data 파라미터"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"defects": []}
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            wrapper.client, "get", new=AsyncMock(return_value=mock_response)
        ) as mock_get:
            await wrapper.call_tool(
                "get_defect_data",
                {
                    "line_id": "LINE-001",
                    "start_date": "2024-01-01",
                    "end_date": "2024-12-31",
                    "defect_type": "scratch",
                },
            )

            call_args = mock_get.call_args
            assert call_args[1]["params"]["start_date"] == "2024-01-01"
            assert call_args[1]["params"]["defect_type"] == "scratch"

    @pytest.mark.asyncio
    async def test_call_get_equipment_status(self, wrapper):
        """get_equipment_status 호출"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "running"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            wrapper.client, "get", new=AsyncMock(return_value=mock_response)
        ):
            result = await wrapper.call_tool(
                "get_equipment_status", {"equipment_id": "EQ-001"}
            )

            assert result == {"status": "running"}

    @pytest.mark.asyncio
    async def test_call_get_equipment_status_with_sensors(self, wrapper):
        """get_equipment_status 센서 포함"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "running", "sensors": []}
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            wrapper.client, "get", new=AsyncMock(return_value=mock_response)
        ) as mock_get:
            await wrapper.call_tool(
                "get_equipment_status",
                {"equipment_id": "EQ-001", "include_sensors": True},
            )

            call_args = mock_get.call_args
            assert call_args[1]["params"]["include_sensors"] is True

    @pytest.mark.asyncio
    async def test_call_get_work_orders(self, wrapper):
        """get_work_orders 호출"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"orders": []}
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            wrapper.client, "get", new=AsyncMock(return_value=mock_response)
        ):
            result = await wrapper.call_tool("get_work_orders", {})

            assert result == {"orders": []}

    @pytest.mark.asyncio
    async def test_call_get_work_orders_with_params(self, wrapper):
        """get_work_orders 파라미터"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"orders": []}
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            wrapper.client, "get", new=AsyncMock(return_value=mock_response)
        ) as mock_get:
            await wrapper.call_tool(
                "get_work_orders",
                {"line_id": "LINE-001", "status": "pending", "date": "2024-01-01"},
            )

            call_args = mock_get.call_args
            assert call_args[1]["params"]["line_id"] == "LINE-001"
            assert call_args[1]["params"]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_call_update_production_count(self, wrapper):
        """update_production_count 호출"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            wrapper.client, "post", new=AsyncMock(return_value=mock_response)
        ):
            result = await wrapper.call_tool(
                "update_production_count",
                {
                    "line_id": "LINE-001",
                    "work_order_id": "WO-001",
                    "good_count": 100,
                    "defect_count": 5,
                },
            )

            assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_http_status_error(self, wrapper):
        """HTTP 상태 에러"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        error = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )

        with patch.object(wrapper.client, "get", new=AsyncMock(side_effect=error)):
            result = await wrapper.call_tool(
                "get_production_status", {"line_id": "LINE-001"}
            )

            assert "error" in result
            assert result["status_code"] == 500

    @pytest.mark.asyncio
    async def test_request_error(self, wrapper):
        """요청 에러"""
        error = httpx.RequestError("Connection failed")

        with patch.object(wrapper.client, "get", new=AsyncMock(side_effect=error)):
            result = await wrapper.call_tool(
                "get_production_status", {"line_id": "LINE-001"}
            )

            assert "error" in result
            assert result["error"] == "MES connection error"


class TestMESWrapperHealthCheck:
    """MESWrapper health_check 테스트"""

    @pytest.fixture
    def wrapper(self):
        """MESWrapper 인스턴스"""
        from app.mcp_wrappers.mes_wrapper import MESWrapper

        return MESWrapper(base_url="http://mes.example.com")

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, wrapper):
        """헬스체크 성공"""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(
            wrapper.client, "get", new=AsyncMock(return_value=mock_response)
        ):
            result = await wrapper.health_check()

            assert result["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, wrapper):
        """헬스체크 실패"""
        mock_response = MagicMock()
        mock_response.status_code = 503

        with patch.object(
            wrapper.client, "get", new=AsyncMock(return_value=mock_response)
        ):
            result = await wrapper.health_check()

            assert result["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_health_check_error(self, wrapper):
        """헬스체크 에러"""
        with patch.object(
            wrapper.client,
            "get",
            new=AsyncMock(side_effect=Exception("Connection failed")),
        ):
            result = await wrapper.health_check()

            assert result["status"] == "unhealthy"
            assert "error" in result


class TestMESWrapperClose:
    """MESWrapper close 테스트"""

    @pytest.mark.asyncio
    async def test_close(self):
        """클라이언트 종료"""
        from app.mcp_wrappers.mes_wrapper import MESWrapper

        wrapper = MESWrapper(base_url="http://mes.example.com")

        with patch.object(wrapper.client, "aclose", new=AsyncMock()) as mock_close:
            await wrapper.close()

            mock_close.assert_called_once()


class TestCreateMESMCPServer:
    """create_mes_mcp_server 테스트"""

    def test_create_server(self):
        """서버 생성"""
        from app.mcp_wrappers.mes_wrapper import create_mes_mcp_server, MESWrapper
        from fastapi import FastAPI

        app, wrapper = create_mes_mcp_server(
            base_url="http://mes.example.com",
            api_key="test-key",
            timeout=60.0,
        )

        assert isinstance(app, FastAPI)
        assert isinstance(wrapper, MESWrapper)
