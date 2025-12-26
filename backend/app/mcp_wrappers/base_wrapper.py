"""
MCP 래퍼 베이스 클래스

외부 시스템 API를 MCP 표준 형식으로 변환하는 기본 클래스입니다.
이 클래스를 상속받아 MES, ERP, SCADA 등의 래퍼를 구현합니다.

MCP 표준 엔드포인트:
- POST /tools/list: 사용 가능한 도구 목록 반환
- POST /tools/call: 도구 실행
- GET /health: 헬스체크
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MCPToolDefinition(BaseModel):
    """MCP 도구 정의"""
    name: str = Field(..., description="도구 이름")
    description: str = Field(..., description="도구 설명")
    input_schema: Dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}},
        description="입력 JSON Schema"
    )


class MCPToolCallRequest(BaseModel):
    """MCP 도구 호출 요청"""
    name: str = Field(..., description="호출할 도구 이름")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="도구 인자")


class MCPContent(BaseModel):
    """MCP 응답 콘텐츠"""
    type: str = "text"
    text: str


class MCPToolCallResponse(BaseModel):
    """MCP 도구 호출 응답"""
    content: List[MCPContent]
    isError: bool = False


class MCPToolListResponse(BaseModel):
    """MCP 도구 목록 응답"""
    tools: List[MCPToolDefinition]


class MCPHealthResponse(BaseModel):
    """MCP 헬스체크 응답"""
    status: str
    timestamp: str
    version: str = "1.0.0"


class MCPWrapperBase(ABC):
    """
    MCP 래퍼 베이스 클래스

    외부 시스템 API를 MCP 표준으로 래핑하려면 이 클래스를 상속받아
    get_tools()와 call_tool()을 구현하세요.

    Example:
        class MyWrapper(MCPWrapperBase):
            def get_tools(self):
                return [MCPToolDefinition(name="my_tool", description="...", input_schema={...})]

            async def call_tool(self, tool_name, args):
                # 외부 API 호출
                return {"result": "..."}
    """

    def __init__(self, name: str = "MCP Wrapper"):
        self.name = name
        self._tools_cache: Optional[List[MCPToolDefinition]] = None

    @abstractmethod
    def get_tools(self) -> List[MCPToolDefinition]:
        """
        사용 가능한 도구 목록 반환

        Returns:
            List[MCPToolDefinition]: 도구 정의 목록
        """
        pass

    @abstractmethod
    async def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        도구 실행

        Args:
            tool_name: 실행할 도구 이름
            args: 도구 인자

        Returns:
            Dict[str, Any]: 도구 실행 결과
        """
        pass

    async def health_check(self) -> Dict[str, Any]:
        """
        헬스체크 (선택적으로 오버라이드 가능)

        Returns:
            Dict[str, Any]: 헬스체크 결과
        """
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "wrapper": self.name
        }

    def get_tools_cached(self) -> List[MCPToolDefinition]:
        """도구 목록 캐시 반환"""
        if self._tools_cache is None:
            self._tools_cache = self.get_tools()
        return self._tools_cache

    def validate_tool_name(self, tool_name: str) -> bool:
        """도구 이름 유효성 검사"""
        valid_names = [t.name for t in self.get_tools_cached()]
        return tool_name in valid_names


def create_mcp_app(wrapper: MCPWrapperBase) -> FastAPI:
    """
    MCP 표준 FastAPI 앱 생성

    Args:
        wrapper: MCPWrapperBase 인스턴스

    Returns:
        FastAPI: MCP 표준 엔드포인트가 구성된 FastAPI 앱
    """
    app = FastAPI(
        title=f"MCP Wrapper - {wrapper.name}",
        description="MCP 표준 래퍼 서버",
        version="1.0.0"
    )

    # CORS 설정
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.post("/tools/list", response_model=MCPToolListResponse)
    async def list_tools():
        """사용 가능한 도구 목록 반환"""
        tools = wrapper.get_tools_cached()
        return MCPToolListResponse(tools=tools)

    @app.post("/tools/call", response_model=MCPToolCallResponse)
    async def call_tool(request: MCPToolCallRequest):
        """도구 실행"""
        tool_name = request.name
        args = request.arguments

        # 도구 유효성 검사
        if not wrapper.validate_tool_name(tool_name):
            logger.warning(f"Unknown tool requested: {tool_name}")
            raise HTTPException(
                status_code=404,
                detail=f"Tool not found: {tool_name}"
            )

        try:
            logger.info(f"Calling tool: {tool_name} with args: {args}")
            result = await wrapper.call_tool(tool_name, args)

            # 결과를 문자열로 변환
            import json
            if isinstance(result, dict):
                result_text = json.dumps(result, ensure_ascii=False, indent=2)
            else:
                result_text = str(result)

            return MCPToolCallResponse(
                content=[MCPContent(type="text", text=result_text)],
                isError=False
            )

        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name}, error: {e}")
            return MCPToolCallResponse(
                content=[MCPContent(type="text", text=f"Error: {str(e)}")],
                isError=True
            )

    @app.get("/health", response_model=MCPHealthResponse)
    async def health():
        """헬스체크"""
        result = await wrapper.health_check()
        return MCPHealthResponse(
            status=result.get("status", "healthy"),
            timestamp=result.get("timestamp", datetime.utcnow().isoformat()),
            version="1.0.0"
        )

    @app.get("/")
    async def root():
        """루트 엔드포인트"""
        return {
            "name": wrapper.name,
            "type": "mcp_wrapper",
            "version": "1.0.0",
            "endpoints": ["/tools/list", "/tools/call", "/health"]
        }

    return app
