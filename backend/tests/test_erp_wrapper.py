"""
ERP Wrapper 테스트
app/mcp_wrappers/erp_wrapper.py의 ERPWrapper 클래스 테스트
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import httpx


# ========== ERPWrapper 초기화 테스트 ==========


class TestERPWrapperInit:
    """ERPWrapper 초기화 테스트"""

    def test_init_basic(self):
        """기본 초기화"""
        from app.mcp_wrappers.erp_wrapper import ERPWrapper

        wrapper = ERPWrapper(base_url="http://erp.example.com")

        assert wrapper.base_url == "http://erp.example.com"
        assert wrapper.api_key is None
        assert wrapper.timeout == 30.0
        assert wrapper.name == "ERP Wrapper"

    def test_init_with_api_key(self):
        """API Key와 함께 초기화"""
        from app.mcp_wrappers.erp_wrapper import ERPWrapper

        wrapper = ERPWrapper(
            base_url="http://erp.example.com",
            api_key="test-api-key",
            timeout=60.0,
        )

        assert wrapper.api_key == "test-api-key"
        assert wrapper.timeout == 60.0

    def test_init_trailing_slash_removed(self):
        """base_url 후행 슬래시 제거"""
        from app.mcp_wrappers.erp_wrapper import ERPWrapper

        wrapper = ERPWrapper(base_url="http://erp.example.com/")

        assert wrapper.base_url == "http://erp.example.com"


# ========== get_tools 테스트 ==========


class TestGetTools:
    """get_tools 메서드 테스트"""

    def test_get_tools_returns_list(self):
        """도구 목록 반환"""
        from app.mcp_wrappers.erp_wrapper import ERPWrapper

        wrapper = ERPWrapper(base_url="http://erp.example.com")
        tools = wrapper.get_tools()

        assert isinstance(tools, list)
        assert len(tools) == 6

    def test_get_tools_names(self):
        """도구 이름 확인"""
        from app.mcp_wrappers.erp_wrapper import ERPWrapper

        wrapper = ERPWrapper(base_url="http://erp.example.com")
        tools = wrapper.get_tools()

        tool_names = [t.name for t in tools]

        assert "get_inventory" in tool_names
        assert "get_purchase_orders" in tool_names
        assert "create_purchase_order" in tool_names
        assert "get_sales_orders" in tool_names
        assert "get_bom" in tool_names
        assert "check_material_availability" in tool_names

    def test_get_tools_structure(self):
        """도구 구조 확인"""
        from app.mcp_wrappers.erp_wrapper import ERPWrapper

        wrapper = ERPWrapper(base_url="http://erp.example.com")
        tools = wrapper.get_tools()

        for tool in tools:
            assert hasattr(tool, "name")
            assert hasattr(tool, "description")
            assert hasattr(tool, "input_schema")
            assert isinstance(tool.input_schema, dict)


# ========== call_tool 테스트 ==========


class TestCallTool:
    """call_tool 메서드 테스트"""

    @pytest.fixture
    def wrapper(self):
        """ERPWrapper 인스턴스"""
        from app.mcp_wrappers.erp_wrapper import ERPWrapper

        return ERPWrapper(base_url="http://erp.example.com")

    @pytest.mark.asyncio
    async def test_call_unknown_tool(self, wrapper):
        """알 수 없는 도구 호출"""
        result = await wrapper.call_tool("unknown_tool", {})

        assert "error" in result
        assert "Unknown tool" in result["error"]

    @pytest.mark.asyncio
    async def test_call_get_inventory(self, wrapper):
        """get_inventory 호출"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"items": []}
        mock_response.raise_for_status = MagicMock()

        with patch.object(wrapper.client, "get", new=AsyncMock(return_value=mock_response)):
            result = await wrapper.call_tool("get_inventory", {"warehouse_id": "WH-001"})

            assert result == {"items": []}

    @pytest.mark.asyncio
    async def test_call_get_inventory_with_all_params(self, wrapper):
        """get_inventory 모든 파라미터"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"items": [{"item": "ITEM-001"}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(wrapper.client, "get", new=AsyncMock(return_value=mock_response)) as mock_get:
            await wrapper.call_tool(
                "get_inventory",
                {
                    "warehouse_id": "WH-001",
                    "item_code": "ITEM-001",
                    "include_reserved": True,
                },
            )

            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert call_args[1]["params"]["warehouse_id"] == "WH-001"
            assert call_args[1]["params"]["item_code"] == "ITEM-001"
            assert call_args[1]["params"]["include_reserved"] is True

    @pytest.mark.asyncio
    async def test_call_get_purchase_orders(self, wrapper):
        """get_purchase_orders 호출"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"orders": []}
        mock_response.raise_for_status = MagicMock()

        with patch.object(wrapper.client, "get", new=AsyncMock(return_value=mock_response)):
            result = await wrapper.call_tool(
                "get_purchase_orders",
                {"status": "pending", "supplier_id": "SUP-001"},
            )

            assert result == {"orders": []}

    @pytest.mark.asyncio
    async def test_call_get_purchase_orders_with_dates(self, wrapper):
        """get_purchase_orders 날짜 파라미터"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"orders": []}
        mock_response.raise_for_status = MagicMock()

        with patch.object(wrapper.client, "get", new=AsyncMock(return_value=mock_response)) as mock_get:
            await wrapper.call_tool(
                "get_purchase_orders",
                {"date_from": "2024-01-01", "date_to": "2024-12-31"},
            )

            call_args = mock_get.call_args
            assert call_args[1]["params"]["date_from"] == "2024-01-01"
            assert call_args[1]["params"]["date_to"] == "2024-12-31"

    @pytest.mark.asyncio
    async def test_call_create_purchase_order(self, wrapper):
        """create_purchase_order 호출"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"order_id": "PO-001"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(wrapper.client, "post", new=AsyncMock(return_value=mock_response)):
            result = await wrapper.call_tool(
                "create_purchase_order",
                {
                    "supplier_id": "SUP-001",
                    "items": [{"item_code": "ITEM-001", "quantity": 100}],
                    "delivery_date": "2024-12-31",
                    "notes": "Test order",
                },
            )

            assert result == {"order_id": "PO-001"}

    @pytest.mark.asyncio
    async def test_call_get_sales_orders(self, wrapper):
        """get_sales_orders 호출"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"orders": []}
        mock_response.raise_for_status = MagicMock()

        with patch.object(wrapper.client, "get", new=AsyncMock(return_value=mock_response)):
            result = await wrapper.call_tool(
                "get_sales_orders",
                {"status": "pending", "customer_id": "CUST-001"},
            )

            assert result == {"orders": []}

    @pytest.mark.asyncio
    async def test_call_get_sales_orders_with_dates(self, wrapper):
        """get_sales_orders 날짜 파라미터"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"orders": []}
        mock_response.raise_for_status = MagicMock()

        with patch.object(wrapper.client, "get", new=AsyncMock(return_value=mock_response)) as mock_get:
            await wrapper.call_tool(
                "get_sales_orders",
                {"date_from": "2024-01-01", "date_to": "2024-12-31"},
            )

            call_args = mock_get.call_args
            assert call_args[1]["params"]["date_from"] == "2024-01-01"
            assert call_args[1]["params"]["date_to"] == "2024-12-31"

    @pytest.mark.asyncio
    async def test_call_get_bom(self, wrapper):
        """get_bom 호출"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"bom": {"materials": []}}
        mock_response.raise_for_status = MagicMock()

        with patch.object(wrapper.client, "get", new=AsyncMock(return_value=mock_response)):
            result = await wrapper.call_tool("get_bom", {"product_code": "PROD-001"})

            assert result == {"bom": {"materials": []}}

    @pytest.mark.asyncio
    async def test_call_get_bom_with_version(self, wrapper):
        """get_bom 버전 파라미터"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"bom": {}}
        mock_response.raise_for_status = MagicMock()

        with patch.object(wrapper.client, "get", new=AsyncMock(return_value=mock_response)) as mock_get:
            await wrapper.call_tool(
                "get_bom",
                {"product_code": "PROD-001", "version": "v2", "include_sub_assemblies": False},
            )

            call_args = mock_get.call_args
            assert call_args[1]["params"]["version"] == "v2"
            assert call_args[1]["params"]["include_sub_assemblies"] is False

    @pytest.mark.asyncio
    async def test_call_check_material_availability(self, wrapper):
        """check_material_availability 호출"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"available": True, "shortage": []}
        mock_response.raise_for_status = MagicMock()

        with patch.object(wrapper.client, "post", new=AsyncMock(return_value=mock_response)):
            result = await wrapper.call_tool(
                "check_material_availability",
                {"product_code": "PROD-001", "quantity": 50},
            )

            assert result == {"available": True, "shortage": []}

    @pytest.mark.asyncio
    async def test_call_check_material_availability_with_warehouse(self, wrapper):
        """check_material_availability 창고 파라미터"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"available": True}
        mock_response.raise_for_status = MagicMock()

        with patch.object(wrapper.client, "post", new=AsyncMock(return_value=mock_response)) as mock_post:
            await wrapper.call_tool(
                "check_material_availability",
                {"product_code": "PROD-001", "quantity": 50, "warehouse_id": "WH-001"},
            )

            call_args = mock_post.call_args
            assert call_args[1]["json"]["warehouse_id"] == "WH-001"


# ========== HTTP 에러 처리 테스트 ==========


class TestHTTPErrorHandling:
    """HTTP 에러 처리 테스트"""

    @pytest.fixture
    def wrapper(self):
        """ERPWrapper 인스턴스"""
        from app.mcp_wrappers.erp_wrapper import ERPWrapper

        return ERPWrapper(base_url="http://erp.example.com")

    @pytest.mark.asyncio
    async def test_http_status_error(self, wrapper):
        """HTTP 상태 에러"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        error = httpx.HTTPStatusError(
            "Internal Server Error",
            request=MagicMock(),
            response=mock_response,
        )

        with patch.object(wrapper.client, "get", new=AsyncMock(side_effect=error)):
            result = await wrapper.call_tool("get_inventory", {})

            assert "error" in result
            assert result["status_code"] == 500

    @pytest.mark.asyncio
    async def test_request_error(self, wrapper):
        """요청 에러"""
        error = httpx.RequestError("Connection refused")

        with patch.object(wrapper.client, "get", new=AsyncMock(side_effect=error)):
            result = await wrapper.call_tool("get_inventory", {})

            assert "error" in result
            assert result["error"] == "ERP connection error"


# ========== health_check 테스트 ==========


class TestHealthCheck:
    """health_check 메서드 테스트"""

    @pytest.fixture
    def wrapper(self):
        """ERPWrapper 인스턴스"""
        from app.mcp_wrappers.erp_wrapper import ERPWrapper

        return ERPWrapper(base_url="http://erp.example.com")

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, wrapper):
        """헬스체크 성공"""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(wrapper.client, "get", new=AsyncMock(return_value=mock_response)):
            result = await wrapper.health_check()

            assert result["status"] == "healthy"
            assert "timestamp" in result
            assert result["wrapper"] == "ERP Wrapper"
            assert result["target_url"] == "http://erp.example.com"

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_status(self, wrapper):
        """헬스체크 비정상 상태 코드"""
        mock_response = MagicMock()
        mock_response.status_code = 503

        with patch.object(wrapper.client, "get", new=AsyncMock(return_value=mock_response)):
            result = await wrapper.health_check()

            assert result["status"] == "unhealthy"
            assert result["response_code"] == 503

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
            assert "Connection failed" in result["error"]


# ========== close 테스트 ==========


class TestClose:
    """close 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_close(self):
        """클라이언트 종료"""
        from app.mcp_wrappers.erp_wrapper import ERPWrapper

        wrapper = ERPWrapper(base_url="http://erp.example.com")

        with patch.object(wrapper.client, "aclose", new=AsyncMock()) as mock_close:
            await wrapper.close()

            mock_close.assert_called_once()


# ========== create_erp_mcp_server 테스트 ==========


class TestCreateErpMcpServer:
    """create_erp_mcp_server 함수 테스트"""

    def test_create_server(self):
        """서버 생성"""
        from app.mcp_wrappers.erp_wrapper import create_erp_mcp_server, ERPWrapper
        from fastapi import FastAPI

        app, wrapper = create_erp_mcp_server(
            base_url="http://erp.example.com",
            api_key="test-key",
            timeout=60.0,
        )

        assert isinstance(app, FastAPI)
        assert isinstance(wrapper, ERPWrapper)
        assert wrapper.api_key == "test-key"
        assert wrapper.timeout == 60.0

    def test_create_server_default_params(self):
        """기본 파라미터로 서버 생성"""
        from app.mcp_wrappers.erp_wrapper import create_erp_mcp_server

        app, wrapper = create_erp_mcp_server(base_url="http://erp.example.com")

        assert wrapper.api_key is None
        assert wrapper.timeout == 30.0
