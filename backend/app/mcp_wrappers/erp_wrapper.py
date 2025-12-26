"""
ERP (Enterprise Resource Planning) MCP 래퍼

ERP 시스템 API를 MCP 표준으로 래핑합니다.

지원 도구:
- get_inventory: 재고 현황 조회
- get_purchase_orders: 구매 발주 목록 조회
- create_purchase_order: 구매 발주 생성
- get_sales_orders: 판매 주문 조회
- get_bom: BOM(자재 명세서) 조회
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

import httpx

from .base_wrapper import MCPWrapperBase, MCPToolDefinition, create_mcp_app

logger = logging.getLogger(__name__)


class ERPWrapper(MCPWrapperBase):
    """
    ERP 시스템 MCP 래퍼

    Args:
        base_url: ERP API 서버 URL (예: http://erp-server.company.com)
        api_key: API 인증 키 (선택)
        timeout: 요청 타임아웃 (초)
    """

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: float = 30.0
    ):
        super().__init__(name="ERP Wrapper")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

        # HTTP 클라이언트 설정
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        headers["Content-Type"] = "application/json"

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=timeout
        )

    def get_tools(self) -> List[MCPToolDefinition]:
        """ERP 도구 목록 반환"""
        return [
            MCPToolDefinition(
                name="get_inventory",
                description="재고 현황을 조회합니다. 품목별 재고량, 위치, 상태 등을 반환합니다.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "warehouse_id": {
                            "type": "string",
                            "description": "창고 ID (예: WH-001)"
                        },
                        "item_code": {
                            "type": "string",
                            "description": "품목 코드 (선택, 미지정 시 전체 조회)"
                        },
                        "include_reserved": {
                            "type": "boolean",
                            "description": "예약 재고 포함 여부 (기본값: true)"
                        }
                    }
                }
            ),
            MCPToolDefinition(
                name="get_purchase_orders",
                description="구매 발주 목록을 조회합니다.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["draft", "pending", "approved", "ordered", "received", "cancelled"],
                            "description": "발주 상태 필터"
                        },
                        "supplier_id": {
                            "type": "string",
                            "description": "공급업체 ID"
                        },
                        "date_from": {
                            "type": "string",
                            "description": "조회 시작일 (YYYY-MM-DD)"
                        },
                        "date_to": {
                            "type": "string",
                            "description": "조회 종료일 (YYYY-MM-DD)"
                        }
                    }
                }
            ),
            MCPToolDefinition(
                name="create_purchase_order",
                description="구매 발주를 생성합니다.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "supplier_id": {
                            "type": "string",
                            "description": "공급업체 ID"
                        },
                        "items": {
                            "type": "array",
                            "description": "발주 품목 목록",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "item_code": {"type": "string"},
                                    "quantity": {"type": "integer"},
                                    "unit_price": {"type": "number"}
                                },
                                "required": ["item_code", "quantity"]
                            }
                        },
                        "delivery_date": {
                            "type": "string",
                            "description": "희망 납품일 (YYYY-MM-DD)"
                        },
                        "notes": {
                            "type": "string",
                            "description": "비고"
                        }
                    },
                    "required": ["supplier_id", "items"]
                }
            ),
            MCPToolDefinition(
                name="get_sales_orders",
                description="판매 주문 목록을 조회합니다.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["pending", "confirmed", "shipped", "delivered", "cancelled"],
                            "description": "주문 상태 필터"
                        },
                        "customer_id": {
                            "type": "string",
                            "description": "고객 ID"
                        },
                        "date_from": {
                            "type": "string",
                            "description": "조회 시작일 (YYYY-MM-DD)"
                        },
                        "date_to": {
                            "type": "string",
                            "description": "조회 종료일 (YYYY-MM-DD)"
                        }
                    }
                }
            ),
            MCPToolDefinition(
                name="get_bom",
                description="BOM(Bill of Materials, 자재 명세서)을 조회합니다.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "product_code": {
                            "type": "string",
                            "description": "제품 코드"
                        },
                        "version": {
                            "type": "string",
                            "description": "BOM 버전 (선택, 미지정 시 최신 버전)"
                        },
                        "include_sub_assemblies": {
                            "type": "boolean",
                            "description": "하위 조립품 포함 여부 (기본값: true)"
                        }
                    },
                    "required": ["product_code"]
                }
            ),
            MCPToolDefinition(
                name="check_material_availability",
                description="자재 가용성을 확인합니다. 생산에 필요한 자재가 충분한지 검사합니다.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "product_code": {
                            "type": "string",
                            "description": "제품 코드"
                        },
                        "quantity": {
                            "type": "integer",
                            "description": "생산 수량"
                        },
                        "warehouse_id": {
                            "type": "string",
                            "description": "창고 ID (선택)"
                        }
                    },
                    "required": ["product_code", "quantity"]
                }
            ),
        ]

    async def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """ERP API 호출"""
        try:
            if tool_name == "get_inventory":
                return await self._get_inventory(args)
            elif tool_name == "get_purchase_orders":
                return await self._get_purchase_orders(args)
            elif tool_name == "create_purchase_order":
                return await self._create_purchase_order(args)
            elif tool_name == "get_sales_orders":
                return await self._get_sales_orders(args)
            elif tool_name == "get_bom":
                return await self._get_bom(args)
            elif tool_name == "check_material_availability":
                return await self._check_material_availability(args)
            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except httpx.HTTPStatusError as e:
            logger.error(f"ERP API HTTP error: {e.response.status_code}")
            return {
                "error": "ERP API error",
                "status_code": e.response.status_code,
                "detail": str(e)
            }
        except httpx.RequestError as e:
            logger.error(f"ERP API request error: {e}")
            return {
                "error": "ERP connection error",
                "detail": str(e)
            }

    async def _get_inventory(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """재고 현황 조회"""
        params = {}
        if "warehouse_id" in args:
            params["warehouse_id"] = args["warehouse_id"]
        if "item_code" in args:
            params["item_code"] = args["item_code"]
        if "include_reserved" in args:
            params["include_reserved"] = args["include_reserved"]

        response = await self.client.get("/api/inventory", params=params)
        response.raise_for_status()
        return response.json()

    async def _get_purchase_orders(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """구매 발주 목록 조회"""
        params = {}
        if "status" in args:
            params["status"] = args["status"]
        if "supplier_id" in args:
            params["supplier_id"] = args["supplier_id"]
        if "date_from" in args:
            params["date_from"] = args["date_from"]
        if "date_to" in args:
            params["date_to"] = args["date_to"]

        response = await self.client.get("/api/purchase-orders", params=params)
        response.raise_for_status()
        return response.json()

    async def _create_purchase_order(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """구매 발주 생성"""
        payload = {
            "supplier_id": args["supplier_id"],
            "items": args["items"],
            "delivery_date": args.get("delivery_date"),
            "notes": args.get("notes", "")
        }

        response = await self.client.post("/api/purchase-orders", json=payload)
        response.raise_for_status()
        return response.json()

    async def _get_sales_orders(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """판매 주문 조회"""
        params = {}
        if "status" in args:
            params["status"] = args["status"]
        if "customer_id" in args:
            params["customer_id"] = args["customer_id"]
        if "date_from" in args:
            params["date_from"] = args["date_from"]
        if "date_to" in args:
            params["date_to"] = args["date_to"]

        response = await self.client.get("/api/sales-orders", params=params)
        response.raise_for_status()
        return response.json()

    async def _get_bom(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """BOM 조회"""
        product_code = args["product_code"]
        params = {}
        if "version" in args:
            params["version"] = args["version"]
        if "include_sub_assemblies" in args:
            params["include_sub_assemblies"] = args["include_sub_assemblies"]

        response = await self.client.get(f"/api/bom/{product_code}", params=params)
        response.raise_for_status()
        return response.json()

    async def _check_material_availability(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """자재 가용성 확인"""
        payload = {
            "product_code": args["product_code"],
            "quantity": args["quantity"]
        }
        if "warehouse_id" in args:
            payload["warehouse_id"] = args["warehouse_id"]

        response = await self.client.post("/api/inventory/check-availability", json=payload)
        response.raise_for_status()
        return response.json()

    async def health_check(self) -> Dict[str, Any]:
        """ERP 서버 헬스체크"""
        try:
            response = await self.client.get("/health", timeout=5.0)
            is_healthy = response.status_code == 200
            return {
                "status": "healthy" if is_healthy else "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "wrapper": self.name,
                "target_url": self.base_url,
                "response_code": response.status_code
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "wrapper": self.name,
                "target_url": self.base_url,
                "error": str(e)
            }

    async def close(self):
        """HTTP 클라이언트 종료"""
        await self.client.aclose()


def create_erp_mcp_server(
    base_url: str,
    api_key: Optional[str] = None,
    timeout: float = 30.0
) -> tuple:
    """
    ERP MCP 서버 생성

    Args:
        base_url: ERP API 서버 URL
        api_key: API 인증 키
        timeout: 요청 타임아웃

    Returns:
        tuple: (FastAPI 앱, ERPWrapper 인스턴스)
    """
    wrapper = ERPWrapper(base_url, api_key, timeout)
    app = create_mcp_app(wrapper)
    return app, wrapper
