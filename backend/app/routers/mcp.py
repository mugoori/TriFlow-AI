"""
MCP ToolHub API Router

스펙 참조: B-2-3_MCP_DataHub_Chat_Design.md

엔드포인트:
- POST   /api/v1/mcp/servers              서버 등록
- GET    /api/v1/mcp/servers              서버 목록
- GET    /api/v1/mcp/servers/{id}         서버 상세
- PUT    /api/v1/mcp/servers/{id}         서버 수정
- DELETE /api/v1/mcp/servers/{id}         서버 삭제
- POST   /api/v1/mcp/call                 도구 호출
- GET    /api/v1/mcp/tools                도구 목록
- POST   /api/v1/mcp/tools                도구 등록
- GET    /api/v1/mcp/tools/{id}           도구 상세
- PUT    /api/v1/mcp/tools/{id}           도구 수정
- DELETE /api/v1/mcp/tools/{id}           도구 삭제
- GET    /api/v1/mcp/health               전체 헬스체크
- GET    /api/v1/mcp/health/{id}          서버 헬스체크
- GET    /api/v1/mcp/circuit-breaker/{id} CB 상태
- POST   /api/v1/mcp/circuit-breaker/{id}/reset CB 리셋
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.services.circuit_breaker import CircuitBreaker
from app.services.mcp_proxy import HTTPMCPProxy
from app.services.mcp_toolhub import (
    MCPToolHubService,
    MCPServerResponse,
    MCPServerCreate,
    MCPServerUpdate,
    MCPServerList,
    MCPToolResponse,
    MCPToolCreate,
    MCPToolUpdate,
    MCPToolList,
    MCPCallRequest,
    MCPCallResponse,
    MCPHealthCheckResponse,
    CircuitBreakerStateResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["MCP ToolHub"])


# =========================================
# Dependencies
# =========================================
def get_mcp_service(
    db: Session = Depends(get_db),
) -> MCPToolHubService:
    """MCPToolHubService 의존성"""
    circuit_breaker = CircuitBreaker(db)
    proxy = HTTPMCPProxy(circuit_breaker=circuit_breaker)
    return MCPToolHubService(db=db, proxy=proxy, circuit_breaker=circuit_breaker)


# =========================================
# MCP Server Endpoints
# =========================================
@router.post(
    "/servers",
    response_model=MCPServerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="MCP 서버 등록",
)
def create_server(
    data: MCPServerCreate,
    current_user: User = Depends(get_current_user),
    service: MCPToolHubService = Depends(get_mcp_service),
) -> MCPServerResponse:
    """
    새 MCP 서버를 등록합니다.

    - **name**: 서버 이름 (테넌트 내 고유)
    - **endpoint**: MCP 서버 엔드포인트 URL
    - **protocol**: stdio, sse, websocket
    - **config**: 서버별 설정 (JSON)
    - **auth_config**: 인증 설정 (JSON, optional)
    """
    return service.register_server(
        tenant_id=current_user.tenant_id,
        data=data,
    )


@router.get(
    "/servers",
    response_model=MCPServerList,
    summary="MCP 서버 목록 조회",
)
def list_servers(
    current_user: User = Depends(get_current_user),
    service: MCPToolHubService = Depends(get_mcp_service),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    server_status: str | None = Query(None, alias="status"),
) -> MCPServerList:
    """MCP 서버 목록을 조회합니다."""
    return service.list_servers(
        tenant_id=current_user.tenant_id,
        page=page,
        size=size,
        status=server_status,
    )


@router.get(
    "/servers/{server_id}",
    response_model=MCPServerResponse,
    summary="MCP 서버 상세 조회",
)
def get_server(
    server_id: UUID,
    current_user: User = Depends(get_current_user),
    service: MCPToolHubService = Depends(get_mcp_service),
) -> MCPServerResponse:
    """MCP 서버 상세 정보를 조회합니다."""
    server = service.get_server(server_id, current_user.tenant_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server


@router.put(
    "/servers/{server_id}",
    response_model=MCPServerResponse,
    summary="MCP 서버 수정",
)
def update_server(
    server_id: UUID,
    data: MCPServerUpdate,
    current_user: User = Depends(get_current_user),
    service: MCPToolHubService = Depends(get_mcp_service),
) -> MCPServerResponse:
    """MCP 서버 정보를 수정합니다."""
    server = service.update_server(server_id, current_user.tenant_id, data)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server


@router.delete(
    "/servers/{server_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="MCP 서버 삭제",
)
def delete_server(
    server_id: UUID,
    current_user: User = Depends(get_current_user),
    service: MCPToolHubService = Depends(get_mcp_service),
) -> None:
    """MCP 서버를 삭제합니다."""
    deleted = service.delete_server(server_id, current_user.tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Server not found")


# =========================================
# MCP Tool Endpoints
# =========================================
@router.post(
    "/tools",
    response_model=MCPToolResponse,
    status_code=status.HTTP_201_CREATED,
    summary="MCP 도구 등록",
)
def create_tool(
    data: MCPToolCreate,
    current_user: User = Depends(get_current_user),
    service: MCPToolHubService = Depends(get_mcp_service),
) -> MCPToolResponse:
    """
    새 MCP 도구를 등록합니다.

    - **mcp_server_id**: 도구가 속한 서버 ID
    - **tool_name**: 도구 이름
    - **input_schema**: 입력 JSON Schema
    """
    return service.create_tool(
        tenant_id=current_user.tenant_id,
        data=data,
    )


@router.get(
    "/tools",
    response_model=MCPToolList,
    summary="MCP 도구 목록 조회",
)
def list_tools(
    current_user: User = Depends(get_current_user),
    service: MCPToolHubService = Depends(get_mcp_service),
    mcp_server_id: UUID | None = Query(None, alias="server_id"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    is_enabled: bool | None = None,
) -> MCPToolList:
    """MCP 도구 목록을 조회합니다."""
    return service.list_tools(
        mcp_server_id=mcp_server_id,
        page=page,
        size=size,
        is_enabled=is_enabled,
    )


@router.get(
    "/tools/{tool_id}",
    response_model=MCPToolResponse,
    summary="MCP 도구 상세 조회",
)
def get_tool(
    tool_id: UUID,
    current_user: User = Depends(get_current_user),
    service: MCPToolHubService = Depends(get_mcp_service),
) -> MCPToolResponse:
    """MCP 도구 상세 정보를 조회합니다."""
    tool = service.get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@router.put(
    "/tools/{tool_id}",
    response_model=MCPToolResponse,
    summary="MCP 도구 수정",
)
def update_tool(
    tool_id: UUID,
    data: MCPToolUpdate,
    current_user: User = Depends(get_current_user),
    service: MCPToolHubService = Depends(get_mcp_service),
) -> MCPToolResponse:
    """MCP 도구 정보를 수정합니다."""
    tool = service.update_tool(tool_id, data)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@router.delete(
    "/tools/{tool_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="MCP 도구 삭제",
)
def delete_tool(
    tool_id: UUID,
    current_user: User = Depends(get_current_user),
    service: MCPToolHubService = Depends(get_mcp_service),
) -> None:
    """MCP 도구를 삭제합니다."""
    deleted = service.delete_tool(tool_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Tool not found")


# =========================================
# Tool Call Endpoint
# =========================================
@router.post(
    "/call",
    response_model=MCPCallResponse,
    summary="MCP 도구 호출",
)
def call_tool(
    request: MCPCallRequest,
    current_user: User = Depends(get_current_user),
    service: MCPToolHubService = Depends(get_mcp_service),
) -> MCPCallResponse:
    """
    MCP 도구를 호출합니다.

    - **mcp_server_id**: 대상 서버 ID
    - **tool_name**: 호출할 도구 이름
    - **input_data**: 도구 입력 데이터
    """
    return service.call_tool(
        tenant_id=current_user.tenant_id,
        request=request,
    )


# =========================================
# Health Check Endpoints
# =========================================
@router.get(
    "/health",
    response_model=list[MCPHealthCheckResponse],
    summary="전체 서버 헬스체크",
)
def health_check_all(
    current_user: User = Depends(get_current_user),
    service: MCPToolHubService = Depends(get_mcp_service),
) -> list[MCPHealthCheckResponse]:
    """모든 활성 MCP 서버의 헬스를 체크합니다."""
    return service.health_check_all(current_user.tenant_id)


@router.get(
    "/health/{server_id}",
    response_model=MCPHealthCheckResponse,
    summary="서버 헬스체크",
)
def health_check(
    server_id: UUID,
    current_user: User = Depends(get_current_user),
    service: MCPToolHubService = Depends(get_mcp_service),
) -> MCPHealthCheckResponse:
    """특정 MCP 서버의 헬스를 체크합니다."""
    return service.health_check(server_id, current_user.tenant_id)


# =========================================
# Circuit Breaker Endpoints
# =========================================
@router.get(
    "/circuit-breaker/{server_id}",
    response_model=CircuitBreakerStateResponse | None,
    summary="Circuit Breaker 상태 조회",
)
def get_circuit_breaker_state(
    server_id: UUID,
    current_user: User = Depends(get_current_user),
    service: MCPToolHubService = Depends(get_mcp_service),
) -> CircuitBreakerStateResponse | None:
    """
    서버의 Circuit Breaker 상태를 조회합니다.

    - **closed**: 정상 상태 (모든 요청 통과)
    - **open**: 차단 상태 (모든 요청 거부)
    - **half_open**: 테스트 상태 (일부 요청만 통과)
    """
    return service.get_circuit_breaker_state(server_id, current_user.tenant_id)


@router.post(
    "/circuit-breaker/{server_id}/reset",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Circuit Breaker 리셋",
)
def reset_circuit_breaker(
    server_id: UUID,
    current_user: User = Depends(get_current_user),
    service: MCPToolHubService = Depends(get_mcp_service),
) -> None:
    """Circuit Breaker를 closed 상태로 리셋합니다."""
    service.reset_circuit_breaker(server_id, current_user.tenant_id)


# =========================================
# DataSource MCP Tools (동적 MES/ERP 도구)
# =========================================
@router.get(
    "/datasource-tools",
    summary="DataSource 기반 MCP 도구 목록",
)
def list_datasource_tools(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    source_type: str | None = Query(None, description="mes 또는 erp"),
):
    """
    DataSource에 등록된 MES/ERP 시스템의 사용 가능한 MCP 도구를 조회합니다.

    각 DataSource(MES/ERP 연결)에 대해 사용 가능한 도구 목록을 반환합니다.
    워크플로우 DATA 노드나 Agent에서 이 도구들을 호출할 수 있습니다.
    """
    from app.services.datasource_mcp_service import DataSourceMCPService

    service = DataSourceMCPService(db)

    if source_type:
        # 특정 타입만 조회
        sources = service.get_active_sources(current_user.tenant_id, source_type)
        result = []
        for source in sources:
            tools = service.get_tools_for_source_type(source.source_type)
            result.append({
                "source_id": str(source.source_id),
                "source_name": source.name,
                "source_type": source.source_type,
                "source_system": source.source_system,
                "tools": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "input_schema": t.input_schema,
                    }
                    for t in tools
                ]
            })
        return {"sources": result, "total": len(result)}
    else:
        # 전체 조회
        tools = service.get_all_tools_for_tenant(current_user.tenant_id)
        return {
            "sources": tools,
            "total_sources": len(tools),
            "total_tools": sum(len(s["tools"]) for s in tools)
        }


@router.post(
    "/datasource-tools/{source_id}/call",
    summary="DataSource MCP 도구 호출",
)
async def call_datasource_tool(
    source_id: UUID,
    tool_name: str = Query(..., description="호출할 도구 이름"),
    arguments: dict = {},
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    DataSource의 MCP 도구를 호출합니다.

    예시:
    - source_id: MES DataSource ID
    - tool_name: "get_production_status"
    - arguments: {"line_id": "LINE-001"}
    """
    from app.services.datasource_mcp_service import DataSourceMCPService

    service = DataSourceMCPService(db)
    result = await service.call_tool(
        source_id=source_id,
        tenant_id=current_user.tenant_id,
        tool_name=tool_name,
        args=arguments
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "도구 실행 실패")
        )

    return result


@router.get(
    "/datasource-tools/{source_id}/health",
    summary="DataSource 연결 상태 확인",
)
async def datasource_health_check(
    source_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """DataSource(MES/ERP) 연결 상태를 확인합니다."""
    from app.services.datasource_mcp_service import DataSourceMCPService

    service = DataSourceMCPService(db)
    result = await service.health_check(source_id, current_user.tenant_id)

    return result
