"""
MES (Manufacturing Execution System) MCP 래퍼

MES 시스템 API를 MCP 표준으로 래핑합니다.

지원 도구:
- get_production_status: 생산 현황 조회
- get_defect_data: 불량 데이터 조회
- get_equipment_status: 설비 상태 조회
- get_work_orders: 작업 지시 조회
- update_production_count: 생산 수량 업데이트
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

import httpx

from .base_wrapper import MCPWrapperBase, MCPToolDefinition, create_mcp_app

logger = logging.getLogger(__name__)


class MESWrapper(MCPWrapperBase):
    """
    MES 시스템 MCP 래퍼

    Args:
        base_url: MES API 서버 URL (예: http://mes-server.company.com)
        api_key: API 인증 키 (선택)
        timeout: 요청 타임아웃 (초)
    """

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: float = 30.0
    ):
        super().__init__(name="MES Wrapper")
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
        """MES 도구 목록 반환"""
        return [
            MCPToolDefinition(
                name="get_production_status",
                description="생산 라인의 현재 생산 현황을 조회합니다. 생산량, 목표량, 달성률 등을 반환합니다.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "line_id": {
                            "type": "string",
                            "description": "생산 라인 ID (예: LINE-001)"
                        },
                        "date": {
                            "type": "string",
                            "description": "조회 일자 (YYYY-MM-DD 형식, 기본값: 오늘)"
                        }
                    },
                    "required": ["line_id"]
                }
            ),
            MCPToolDefinition(
                name="get_defect_data",
                description="불량 데이터를 조회합니다. 불량 유형, 수량, 발생 위치 등을 반환합니다.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "line_id": {
                            "type": "string",
                            "description": "생산 라인 ID"
                        },
                        "start_date": {
                            "type": "string",
                            "description": "조회 시작일 (YYYY-MM-DD)"
                        },
                        "end_date": {
                            "type": "string",
                            "description": "조회 종료일 (YYYY-MM-DD)"
                        },
                        "defect_type": {
                            "type": "string",
                            "description": "불량 유형 필터 (선택)"
                        }
                    },
                    "required": ["line_id"]
                }
            ),
            MCPToolDefinition(
                name="get_equipment_status",
                description="설비의 현재 상태를 조회합니다. 가동 상태, 온도, 속도 등을 반환합니다.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "equipment_id": {
                            "type": "string",
                            "description": "설비 ID (예: EQ-001)"
                        },
                        "include_sensors": {
                            "type": "boolean",
                            "description": "센서 데이터 포함 여부 (기본값: false)"
                        }
                    },
                    "required": ["equipment_id"]
                }
            ),
            MCPToolDefinition(
                name="get_work_orders",
                description="작업 지시 목록을 조회합니다.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "line_id": {
                            "type": "string",
                            "description": "생산 라인 ID"
                        },
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed", "cancelled"],
                            "description": "작업 상태 필터"
                        },
                        "date": {
                            "type": "string",
                            "description": "작업 예정일 (YYYY-MM-DD)"
                        }
                    }
                }
            ),
            MCPToolDefinition(
                name="update_production_count",
                description="생산 수량을 업데이트합니다.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "line_id": {
                            "type": "string",
                            "description": "생산 라인 ID"
                        },
                        "work_order_id": {
                            "type": "string",
                            "description": "작업 지시 ID"
                        },
                        "good_count": {
                            "type": "integer",
                            "description": "양품 수량"
                        },
                        "defect_count": {
                            "type": "integer",
                            "description": "불량 수량"
                        }
                    },
                    "required": ["line_id", "work_order_id", "good_count"]
                }
            ),
        ]

    async def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """MES API 호출"""
        try:
            if tool_name == "get_production_status":
                return await self._get_production_status(args)
            elif tool_name == "get_defect_data":
                return await self._get_defect_data(args)
            elif tool_name == "get_equipment_status":
                return await self._get_equipment_status(args)
            elif tool_name == "get_work_orders":
                return await self._get_work_orders(args)
            elif tool_name == "update_production_count":
                return await self._update_production_count(args)
            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except httpx.HTTPStatusError as e:
            logger.error(f"MES API HTTP error: {e.response.status_code}")
            return {
                "error": "MES API error",
                "status_code": e.response.status_code,
                "detail": str(e)
            }
        except httpx.RequestError as e:
            logger.error(f"MES API request error: {e}")
            return {
                "error": "MES connection error",
                "detail": str(e)
            }

    async def _get_production_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """생산 현황 조회"""
        line_id = args.get("line_id")
        date = args.get("date", datetime.now().strftime("%Y-%m-%d"))

        response = await self.client.get(
            "/api/production/status",
            params={"line_id": line_id, "date": date}
        )
        response.raise_for_status()
        return response.json()

    async def _get_defect_data(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """불량 데이터 조회"""
        params = {"line_id": args.get("line_id")}

        if "start_date" in args:
            params["start_date"] = args["start_date"]
        if "end_date" in args:
            params["end_date"] = args["end_date"]
        if "defect_type" in args:
            params["defect_type"] = args["defect_type"]

        response = await self.client.get("/api/quality/defects", params=params)
        response.raise_for_status()
        return response.json()

    async def _get_equipment_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """설비 상태 조회"""
        equipment_id = args.get("equipment_id")
        include_sensors = args.get("include_sensors", False)

        response = await self.client.get(
            f"/api/equipment/{equipment_id}/status",
            params={"include_sensors": include_sensors}
        )
        response.raise_for_status()
        return response.json()

    async def _get_work_orders(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """작업 지시 조회"""
        params = {}
        if "line_id" in args:
            params["line_id"] = args["line_id"]
        if "status" in args:
            params["status"] = args["status"]
        if "date" in args:
            params["date"] = args["date"]

        response = await self.client.get("/api/work-orders", params=params)
        response.raise_for_status()
        return response.json()

    async def _update_production_count(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """생산 수량 업데이트"""
        payload = {
            "line_id": args.get("line_id"),
            "work_order_id": args.get("work_order_id"),
            "good_count": args.get("good_count"),
            "defect_count": args.get("defect_count", 0)
        }

        response = await self.client.post("/api/production/count", json=payload)
        response.raise_for_status()
        return response.json()

    async def health_check(self) -> Dict[str, Any]:
        """MES 서버 헬스체크"""
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


def create_mes_mcp_server(
    base_url: str,
    api_key: Optional[str] = None,
    timeout: float = 30.0
) -> tuple:
    """
    MES MCP 서버 생성

    Args:
        base_url: MES API 서버 URL
        api_key: API 인증 키
        timeout: 요청 타임아웃

    Returns:
        tuple: (FastAPI 앱, MESWrapper 인스턴스)
    """
    wrapper = MESWrapper(base_url, api_key, timeout)
    app = create_mcp_app(wrapper)
    return app, wrapper
