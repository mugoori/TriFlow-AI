"""
MCP 래퍼 베이스 클래스 테스트
app/mcp_wrappers/base_wrapper.py 테스트
"""
import pytest

from fastapi.testclient import TestClient


# ========== Pydantic 모델 테스트 ==========


class TestMCPModels:
    """MCP Pydantic 모델 테스트"""

    def test_mcp_tool_definition(self):
        """MCPToolDefinition 모델"""
        from app.mcp_wrappers.base_wrapper import MCPToolDefinition

        tool = MCPToolDefinition(
            name="test_tool",
            description="Test tool description"
        )

        assert tool.name == "test_tool"
        assert tool.description == "Test tool description"
        assert tool.input_schema == {"type": "object", "properties": {}}

    def test_mcp_tool_definition_with_schema(self):
        """MCPToolDefinition 모델 - 스키마 포함"""
        from app.mcp_wrappers.base_wrapper import MCPToolDefinition

        schema = {
            "type": "object",
            "properties": {
                "param1": {"type": "string"},
                "param2": {"type": "integer"}
            },
            "required": ["param1"]
        }
        tool = MCPToolDefinition(
            name="test_tool",
            description="Test tool",
            input_schema=schema
        )

        assert tool.input_schema == schema

    def test_mcp_tool_call_request(self):
        """MCPToolCallRequest 모델"""
        from app.mcp_wrappers.base_wrapper import MCPToolCallRequest

        request = MCPToolCallRequest(
            name="test_tool",
            arguments={"key": "value"}
        )

        assert request.name == "test_tool"
        assert request.arguments == {"key": "value"}

    def test_mcp_tool_call_request_empty_args(self):
        """MCPToolCallRequest 모델 - 빈 인자"""
        from app.mcp_wrappers.base_wrapper import MCPToolCallRequest

        request = MCPToolCallRequest(name="test_tool")
        assert request.arguments == {}

    def test_mcp_content(self):
        """MCPContent 모델"""
        from app.mcp_wrappers.base_wrapper import MCPContent

        content = MCPContent(text="Test content")
        assert content.type == "text"
        assert content.text == "Test content"

    def test_mcp_tool_call_response(self):
        """MCPToolCallResponse 모델"""
        from app.mcp_wrappers.base_wrapper import MCPToolCallResponse, MCPContent

        response = MCPToolCallResponse(
            content=[MCPContent(text="Result")]
        )

        assert len(response.content) == 1
        assert response.content[0].text == "Result"
        assert response.isError is False

    def test_mcp_tool_call_response_error(self):
        """MCPToolCallResponse 모델 - 에러"""
        from app.mcp_wrappers.base_wrapper import MCPToolCallResponse, MCPContent

        response = MCPToolCallResponse(
            content=[MCPContent(text="Error message")],
            isError=True
        )

        assert response.isError is True

    def test_mcp_tool_list_response(self):
        """MCPToolListResponse 모델"""
        from app.mcp_wrappers.base_wrapper import MCPToolListResponse, MCPToolDefinition

        response = MCPToolListResponse(
            tools=[
                MCPToolDefinition(name="tool1", description="Desc1"),
                MCPToolDefinition(name="tool2", description="Desc2"),
            ]
        )

        assert len(response.tools) == 2

    def test_mcp_health_response(self):
        """MCPHealthResponse 모델"""
        from app.mcp_wrappers.base_wrapper import MCPHealthResponse

        response = MCPHealthResponse(
            status="healthy",
            timestamp="2024-01-01T00:00:00"
        )

        assert response.status == "healthy"
        assert response.version == "1.0.0"


# ========== MCPWrapperBase 테스트 ==========


class TestMCPWrapperBase:
    """MCPWrapperBase 테스트"""

    @pytest.fixture
    def mock_wrapper(self):
        """Mock 래퍼 생성"""
        from app.mcp_wrappers.base_wrapper import MCPWrapperBase, MCPToolDefinition

        class MockWrapper(MCPWrapperBase):
            def get_tools(self):
                return [
                    MCPToolDefinition(name="tool1", description="Tool 1"),
                    MCPToolDefinition(name="tool2", description="Tool 2"),
                ]

            async def call_tool(self, tool_name, args):
                if tool_name == "tool1":
                    return {"result": "success"}
                return {"error": "unknown"}

        return MockWrapper(name="Mock Wrapper")

    def test_init(self, mock_wrapper):
        """초기화 테스트"""
        assert mock_wrapper.name == "Mock Wrapper"
        assert mock_wrapper._tools_cache is None

    def test_get_tools(self, mock_wrapper):
        """get_tools 테스트"""
        tools = mock_wrapper.get_tools()

        assert len(tools) == 2
        assert tools[0].name == "tool1"
        assert tools[1].name == "tool2"

    def test_get_tools_cached(self, mock_wrapper):
        """get_tools_cached 테스트"""
        # 첫 번째 호출 - 캐시 생성
        tools1 = mock_wrapper.get_tools_cached()

        # 두 번째 호출 - 캐시 사용
        tools2 = mock_wrapper.get_tools_cached()

        assert tools1 is tools2  # 동일 객체
        assert mock_wrapper._tools_cache is not None

    def test_validate_tool_name_valid(self, mock_wrapper):
        """유효한 도구 이름 검증"""
        assert mock_wrapper.validate_tool_name("tool1") is True
        assert mock_wrapper.validate_tool_name("tool2") is True

    def test_validate_tool_name_invalid(self, mock_wrapper):
        """유효하지 않은 도구 이름 검증"""
        assert mock_wrapper.validate_tool_name("unknown") is False
        assert mock_wrapper.validate_tool_name("") is False

    @pytest.mark.asyncio
    async def test_call_tool(self, mock_wrapper):
        """call_tool 테스트"""
        result = await mock_wrapper.call_tool("tool1", {})
        assert result == {"result": "success"}

    @pytest.mark.asyncio
    async def test_health_check(self, mock_wrapper):
        """health_check 테스트"""
        result = await mock_wrapper.health_check()

        assert result["status"] == "healthy"
        assert result["wrapper"] == "Mock Wrapper"
        assert "timestamp" in result


# ========== create_mcp_app 테스트 ==========


class TestCreateMcpApp:
    """create_mcp_app 함수 테스트"""

    @pytest.fixture
    def wrapper_and_app(self):
        """Mock 래퍼와 앱 생성"""
        from app.mcp_wrappers.base_wrapper import (
            MCPWrapperBase,
            MCPToolDefinition,
            create_mcp_app,
        )

        class MockWrapper(MCPWrapperBase):
            def get_tools(self):
                return [
                    MCPToolDefinition(
                        name="test_tool",
                        description="Test tool",
                        input_schema={
                            "type": "object",
                            "properties": {"param": {"type": "string"}}
                        }
                    ),
                ]

            async def call_tool(self, tool_name, args):
                if tool_name == "test_tool":
                    return {"result": args.get("param", "default")}
                raise ValueError(f"Unknown tool: {tool_name}")

        wrapper = MockWrapper(name="Test Wrapper")
        app = create_mcp_app(wrapper)
        return wrapper, app

    def test_app_creation(self, wrapper_and_app):
        """앱 생성 테스트"""
        from fastapi import FastAPI

        wrapper, app = wrapper_and_app
        assert isinstance(app, FastAPI)
        assert "Test Wrapper" in app.title

    def test_root_endpoint(self, wrapper_and_app):
        """루트 엔드포인트 테스트"""
        wrapper, app = wrapper_and_app
        client = TestClient(app)

        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "Test Wrapper"
        assert data["type"] == "mcp_wrapper"
        assert "/tools/list" in data["endpoints"]

    def test_tools_list_endpoint(self, wrapper_and_app):
        """도구 목록 엔드포인트 테스트"""
        wrapper, app = wrapper_and_app
        client = TestClient(app)

        response = client.post("/tools/list")
        assert response.status_code == 200

        data = response.json()
        assert "tools" in data
        assert len(data["tools"]) == 1
        assert data["tools"][0]["name"] == "test_tool"

    def test_tools_call_endpoint_success(self, wrapper_and_app):
        """도구 호출 엔드포인트 - 성공"""
        wrapper, app = wrapper_and_app
        client = TestClient(app)

        response = client.post(
            "/tools/call",
            json={"name": "test_tool", "arguments": {"param": "value"}}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["isError"] is False
        assert len(data["content"]) == 1
        # JSON 결과 확인
        assert '"result": "value"' in data["content"][0]["text"]

    def test_tools_call_endpoint_unknown_tool(self, wrapper_and_app):
        """도구 호출 엔드포인트 - 알 수 없는 도구"""
        wrapper, app = wrapper_and_app
        client = TestClient(app)

        response = client.post(
            "/tools/call",
            json={"name": "unknown_tool", "arguments": {}}
        )
        assert response.status_code == 404
        assert "Tool not found" in response.json()["detail"]

    def test_health_endpoint(self, wrapper_and_app):
        """헬스체크 엔드포인트 테스트"""
        wrapper, app = wrapper_and_app
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"
        assert "timestamp" in data


class TestCreateMcpAppErrorHandling:
    """create_mcp_app 에러 처리 테스트"""

    @pytest.fixture
    def error_wrapper_app(self):
        """에러를 발생시키는 래퍼"""
        from app.mcp_wrappers.base_wrapper import (
            MCPWrapperBase,
            MCPToolDefinition,
            create_mcp_app,
        )

        class ErrorWrapper(MCPWrapperBase):
            def get_tools(self):
                return [
                    MCPToolDefinition(name="error_tool", description="Error tool"),
                ]

            async def call_tool(self, tool_name, args):
                raise RuntimeError("Tool execution failed!")

        wrapper = ErrorWrapper(name="Error Wrapper")
        app = create_mcp_app(wrapper)
        return app

    def test_tool_call_error(self, error_wrapper_app):
        """도구 호출 에러 처리"""
        client = TestClient(error_wrapper_app)

        response = client.post(
            "/tools/call",
            json={"name": "error_tool", "arguments": {}}
        )
        assert response.status_code == 200  # 에러도 200으로 반환

        data = response.json()
        assert data["isError"] is True
        assert "Error:" in data["content"][0]["text"]
        assert "Tool execution failed!" in data["content"][0]["text"]


class TestCreateMcpAppResultFormats:
    """create_mcp_app 결과 형식 테스트"""

    @pytest.fixture
    def format_wrapper_app(self):
        """다양한 형식을 반환하는 래퍼"""
        from app.mcp_wrappers.base_wrapper import (
            MCPWrapperBase,
            MCPToolDefinition,
            create_mcp_app,
        )

        class FormatWrapper(MCPWrapperBase):
            def get_tools(self):
                return [
                    MCPToolDefinition(name="dict_tool", description="Returns dict"),
                    MCPToolDefinition(name="string_tool", description="Returns string"),
                    MCPToolDefinition(name="list_tool", description="Returns list"),
                ]

            async def call_tool(self, tool_name, args):
                if tool_name == "dict_tool":
                    return {"key": "value", "nested": {"a": 1}}
                elif tool_name == "string_tool":
                    return "plain string result"
                elif tool_name == "list_tool":
                    return [1, 2, 3]  # 리스트도 str()로 변환됨

        wrapper = FormatWrapper(name="Format Wrapper")
        app = create_mcp_app(wrapper)
        return app

    def test_dict_result(self, format_wrapper_app):
        """딕셔너리 결과 형식"""
        client = TestClient(format_wrapper_app)

        response = client.post(
            "/tools/call",
            json={"name": "dict_tool", "arguments": {}}
        )
        data = response.json()

        assert data["isError"] is False
        # JSON 형식 확인
        import json
        result_text = data["content"][0]["text"]
        parsed = json.loads(result_text)
        assert parsed["key"] == "value"

    def test_string_result(self, format_wrapper_app):
        """문자열 결과 형식"""
        client = TestClient(format_wrapper_app)

        response = client.post(
            "/tools/call",
            json={"name": "string_tool", "arguments": {}}
        )
        data = response.json()

        assert data["isError"] is False
        assert data["content"][0]["text"] == "plain string result"

    def test_list_result(self, format_wrapper_app):
        """리스트 결과 형식 (str 변환)"""
        client = TestClient(format_wrapper_app)

        response = client.post(
            "/tools/call",
            json={"name": "list_tool", "arguments": {}}
        )
        data = response.json()

        assert data["isError"] is False
        # 리스트는 str()로 변환
        assert "[1, 2, 3]" in data["content"][0]["text"]
