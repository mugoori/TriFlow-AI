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
- POST   /api/v1/mcp/connectors           커넥터 등록
- GET    /api/v1/mcp/connectors           커넥터 목록
- GET    /api/v1/mcp/connectors/{id}      커넥터 상세
- PUT    /api/v1/mcp/connectors/{id}      커넥터 수정
- DELETE /api/v1/mcp/connectors/{id}      커넥터 삭제
- POST   /api/v1/mcp/drift/detect/{id}    Drift 감지
- GET    /api/v1/mcp/drift/{id}           Drift 기록
- POST   /api/v1/mcp/drift/{id}/ack       Drift 확인
"""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.mcp import (
    CircuitBreakerConfig,
    CircuitBreakerState,
    ConnectorType,
    DataConnector,
    DataConnectorCreate,
    DataConnectorList,
    DataConnectorUpdate,
    DriftReport,
    MCPCallRequest,
    MCPCallResponse,
    MCPHealthCheckResponse,
    MCPServer,
    MCPServerCreate,
    MCPServerList,
    MCPServerStatus,
    MCPServerUpdate,
    MCPTool,
    MCPToolCreate,
    MCPToolList,
    MCPToolUpdate,
    SchemaDriftDetectionList,
)
from app.models.user import User
from app.services.circuit_breaker import CircuitBreaker
from app.services.drift_detector import SchemaDriftDetector
from app.services.mcp_proxy import HTTPMCPProxy
from app.services.mcp_toolhub import MCPToolHubService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["MCP ToolHub"])


# =========================================
# Dependencies
# =========================================
async def get_mcp_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MCPToolHubService:
    """MCPToolHubService 의존성"""
    circuit_breaker = CircuitBreaker(db)
    proxy = HTTPMCPProxy(circuit_breaker=circuit_breaker)
    return MCPToolHubService(db=db, proxy=proxy, circuit_breaker=circuit_breaker)


async def get_drift_detector(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SchemaDriftDetector:
    """SchemaDriftDetector 의존성"""
    return SchemaDriftDetector(db=db)


# =========================================
# MCP Server Endpoints
# =========================================
@router.post(
    "/servers",
    response_model=MCPServer,
    status_code=status.HTTP_201_CREATED,
    summary="MCP 서버 등록",
)
async def create_server(
    data: MCPServerCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MCPToolHubService, Depends(get_mcp_service)],
) -> MCPServer:
    """
    새 MCP 서버를 등록합니다.

    - **name**: 서버 이름 (테넌트 내 고유)
    - **base_url**: MCP 서버 기본 URL
    - **auth_type**: 인증 타입 (none, api_key, oauth2, basic)
    """
    return await service.register_server(
        tenant_id=current_user.tenant_id,
        data=data,
        created_by=current_user.user_id,
    )


@router.get(
    "/servers",
    response_model=MCPServerList,
    summary="MCP 서버 목록 조회",
)
async def list_servers(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MCPToolHubService, Depends(get_mcp_service)],
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: MCPServerStatus | None = None,
    tags: list[str] | None = Query(None),
) -> MCPServerList:
    """MCP 서버 목록을 조회합니다."""
    return await service.list_servers(
        tenant_id=current_user.tenant_id,
        page=page,
        size=size,
        status=status,
        tags=tags,
    )


@router.get(
    "/servers/{server_id}",
    response_model=MCPServer,
    summary="MCP 서버 상세 조회",
)
async def get_server(
    server_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MCPToolHubService, Depends(get_mcp_service)],
) -> MCPServer:
    """MCP 서버 상세 정보를 조회합니다."""
    server = await service.get_server(server_id, current_user.tenant_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server


@router.put(
    "/servers/{server_id}",
    response_model=MCPServer,
    summary="MCP 서버 수정",
)
async def update_server(
    server_id: UUID,
    data: MCPServerUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MCPToolHubService, Depends(get_mcp_service)],
) -> MCPServer:
    """MCP 서버 정보를 수정합니다."""
    server = await service.update_server(server_id, current_user.tenant_id, data)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server


@router.delete(
    "/servers/{server_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="MCP 서버 삭제",
)
async def delete_server(
    server_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MCPToolHubService, Depends(get_mcp_service)],
) -> None:
    """MCP 서버를 삭제합니다."""
    deleted = await service.delete_server(server_id, current_user.tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Server not found")


# =========================================
# MCP Tool Endpoints
# =========================================
@router.post(
    "/tools",
    response_model=MCPTool,
    status_code=status.HTTP_201_CREATED,
    summary="MCP 도구 등록",
)
async def create_tool(
    data: MCPToolCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MCPToolHubService, Depends(get_mcp_service)],
) -> MCPTool:
    """
    새 MCP 도구를 등록합니다.

    - **server_id**: 도구가 속한 서버 ID
    - **name**: 도구 이름
    - **method**: JSON-RPC method 이름
    """
    return await service.create_tool(
        tenant_id=current_user.tenant_id,
        data=data,
    )


@router.get(
    "/tools",
    response_model=MCPToolList,
    summary="MCP 도구 목록 조회",
)
async def list_tools(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MCPToolHubService, Depends(get_mcp_service)],
    server_id: UUID | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    is_enabled: bool | None = None,
) -> MCPToolList:
    """MCP 도구 목록을 조회합니다."""
    return await service.list_tools(
        tenant_id=current_user.tenant_id,
        server_id=server_id,
        page=page,
        size=size,
        is_enabled=is_enabled,
    )


@router.get(
    "/tools/{tool_id}",
    response_model=MCPTool,
    summary="MCP 도구 상세 조회",
)
async def get_tool(
    tool_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MCPToolHubService, Depends(get_mcp_service)],
) -> MCPTool:
    """MCP 도구 상세 정보를 조회합니다."""
    tool = await service.get_tool(tool_id, current_user.tenant_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@router.put(
    "/tools/{tool_id}",
    response_model=MCPTool,
    summary="MCP 도구 수정",
)
async def update_tool(
    tool_id: UUID,
    data: MCPToolUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MCPToolHubService, Depends(get_mcp_service)],
) -> MCPTool:
    """MCP 도구 정보를 수정합니다."""
    tool = await service.update_tool(tool_id, current_user.tenant_id, data)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@router.delete(
    "/tools/{tool_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="MCP 도구 삭제",
)
async def delete_tool(
    tool_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MCPToolHubService, Depends(get_mcp_service)],
) -> None:
    """MCP 도구를 삭제합니다."""
    deleted = await service.delete_tool(tool_id, current_user.tenant_id)
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
async def call_tool(
    request: MCPCallRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MCPToolHubService, Depends(get_mcp_service)],
) -> MCPCallResponse:
    """
    MCP 도구를 호출합니다.

    - **server_id**: 대상 서버 ID
    - **tool_name**: 호출할 도구 이름
    - **args**: 도구 인자
    """
    return await service.call_tool(
        tenant_id=current_user.tenant_id,
        request=request,
        called_by=current_user.user_id,
    )


# =========================================
# Health Check Endpoints
# =========================================
@router.get(
    "/health",
    response_model=list[MCPHealthCheckResponse],
    summary="전체 서버 헬스체크",
)
async def health_check_all(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MCPToolHubService, Depends(get_mcp_service)],
) -> list[MCPHealthCheckResponse]:
    """모든 활성 MCP 서버의 헬스를 체크합니다."""
    return await service.health_check_all(current_user.tenant_id)


@router.get(
    "/health/{server_id}",
    response_model=MCPHealthCheckResponse,
    summary="서버 헬스체크",
)
async def health_check(
    server_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MCPToolHubService, Depends(get_mcp_service)],
) -> MCPHealthCheckResponse:
    """특정 MCP 서버의 헬스를 체크합니다."""
    return await service.health_check(server_id, current_user.tenant_id)


# =========================================
# Circuit Breaker Endpoints
# =========================================
@router.get(
    "/circuit-breaker/{server_id}",
    response_model=CircuitBreakerState | None,
    summary="Circuit Breaker 상태 조회",
)
async def get_circuit_breaker_state(
    server_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MCPToolHubService, Depends(get_mcp_service)],
) -> CircuitBreakerState | None:
    """
    서버의 Circuit Breaker 상태를 조회합니다.

    - **CLOSED**: 정상 상태 (모든 요청 통과)
    - **OPEN**: 차단 상태 (모든 요청 거부)
    - **HALF_OPEN**: 테스트 상태 (일부 요청만 통과)
    """
    return await service.get_circuit_breaker_state(server_id)


@router.post(
    "/circuit-breaker/{server_id}/reset",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Circuit Breaker 리셋",
)
async def reset_circuit_breaker(
    server_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MCPToolHubService, Depends(get_mcp_service)],
) -> None:
    """Circuit Breaker를 CLOSED 상태로 리셋합니다."""
    await service.reset_circuit_breaker(server_id)


@router.put(
    "/circuit-breaker/{server_id}/config",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Circuit Breaker 설정 수정",
)
async def update_circuit_breaker_config(
    server_id: UUID,
    config: CircuitBreakerConfig,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MCPToolHubService, Depends(get_mcp_service)],
) -> None:
    """
    Circuit Breaker 설정을 수정합니다.

    - **failure_threshold**: OPEN 전환 실패 임계값
    - **success_threshold**: CLOSED 전환 성공 임계값
    - **timeout_seconds**: OPEN 상태 타임아웃
    """
    await service.update_circuit_breaker_config(server_id, config)


# =========================================
# Data Connector Endpoints
# =========================================
@router.post(
    "/connectors",
    response_model=DataConnector,
    status_code=status.HTTP_201_CREATED,
    summary="데이터 커넥터 등록",
)
async def create_connector(
    data: DataConnectorCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    detector: Annotated[SchemaDriftDetector, Depends(get_drift_detector)],
) -> DataConnector:
    """
    새 데이터 커넥터를 등록합니다.

    지원 타입: postgresql, mysql, mssql, oracle, rest_api, mqtt, s3, gcs
    """
    return await detector.create_connector(
        tenant_id=current_user.tenant_id,
        data=data,
        created_by=current_user.user_id,
    )


@router.get(
    "/connectors",
    response_model=DataConnectorList,
    summary="데이터 커넥터 목록 조회",
)
async def list_connectors(
    current_user: Annotated[User, Depends(get_current_user)],
    detector: Annotated[SchemaDriftDetector, Depends(get_drift_detector)],
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    connector_type: ConnectorType | None = None,
) -> DataConnectorList:
    """데이터 커넥터 목록을 조회합니다."""
    return await detector.list_connectors(
        tenant_id=current_user.tenant_id,
        page=page,
        size=size,
        connector_type=connector_type,
    )


@router.get(
    "/connectors/{connector_id}",
    response_model=DataConnector,
    summary="데이터 커넥터 상세 조회",
)
async def get_connector(
    connector_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    detector: Annotated[SchemaDriftDetector, Depends(get_drift_detector)],
) -> DataConnector:
    """데이터 커넥터 상세 정보를 조회합니다."""
    connector = await detector.get_connector(connector_id, current_user.tenant_id)
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    return connector


@router.put(
    "/connectors/{connector_id}",
    response_model=DataConnector,
    summary="데이터 커넥터 수정",
)
async def update_connector(
    connector_id: UUID,
    data: DataConnectorUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    detector: Annotated[SchemaDriftDetector, Depends(get_drift_detector)],
) -> DataConnector:
    """데이터 커넥터 정보를 수정합니다."""
    connector = await detector.update_connector(connector_id, current_user.tenant_id, data)
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    return connector


@router.delete(
    "/connectors/{connector_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="데이터 커넥터 삭제",
)
async def delete_connector(
    connector_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    detector: Annotated[SchemaDriftDetector, Depends(get_drift_detector)],
) -> None:
    """데이터 커넥터를 삭제합니다."""
    deleted = await detector.delete_connector(connector_id, current_user.tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Connector not found")


# =========================================
# Schema Drift Endpoints
# =========================================
@router.post(
    "/drift/detect/{connector_id}",
    response_model=DriftReport,
    summary="스키마 변경 감지",
)
async def detect_drift(
    connector_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    detector: Annotated[SchemaDriftDetector, Depends(get_drift_detector)],
) -> DriftReport:
    """
    데이터 커넥터의 스키마 변경을 감지합니다.

    1. 현재 스키마 조회
    2. 마지막 스냅샷과 비교
    3. 변경 내용 반환
    """
    try:
        return await detector.detect_drift(
            connector_id=connector_id,
            tenant_id=current_user.tenant_id,
            captured_by=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Drift detection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Drift detection failed: {e}")


@router.get(
    "/drift/{connector_id}",
    response_model=SchemaDriftDetectionList,
    summary="스키마 변경 기록 조회",
)
async def get_drift_history(
    connector_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    detector: Annotated[SchemaDriftDetector, Depends(get_drift_detector)],
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    unacknowledged_only: bool = Query(False),
) -> SchemaDriftDetectionList:
    """스키마 변경 감지 기록을 조회합니다."""
    return await detector.get_drift_detections(
        connector_id=connector_id,
        tenant_id=current_user.tenant_id,
        page=page,
        size=size,
        unacknowledged_only=unacknowledged_only,
    )


@router.post(
    "/drift/{detection_id}/ack",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="스키마 변경 확인",
)
async def acknowledge_drift(
    detection_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    detector: Annotated[SchemaDriftDetector, Depends(get_drift_detector)],
) -> None:
    """스키마 변경을 확인 처리합니다."""
    acknowledged = await detector.acknowledge_drift(
        detection_id=detection_id,
        tenant_id=current_user.tenant_id,
        acknowledged_by=current_user.user_id,
    )
    if not acknowledged:
        raise HTTPException(status_code=404, detail="Detection not found")
