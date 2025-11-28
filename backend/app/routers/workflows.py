"""
Workflow Router
워크플로우 CRUD 및 실행 API - PostgreSQL DB 연동
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Workflow, WorkflowInstance

router = APIRouter()


# ============ Pydantic Models ============

class WorkflowTrigger(BaseModel):
    type: str = Field(..., description="트리거 타입 (event, schedule, manual)")
    config: Dict[str, Any] = Field(default_factory=dict)


class WorkflowNode(BaseModel):
    id: str
    type: str = Field(..., description="노드 타입 (condition, action)")
    config: Dict[str, Any]
    next: List[str] = Field(default_factory=list)


class WorkflowDSL(BaseModel):
    name: str
    description: Optional[str] = None
    trigger: WorkflowTrigger
    nodes: List[WorkflowNode]


class WorkflowCreate(BaseModel):
    name: str
    description: Optional[str] = None
    dsl_definition: WorkflowDSL


class WorkflowResponse(BaseModel):
    workflow_id: str
    name: str
    description: Optional[str]
    dsl_definition: Dict[str, Any]
    version: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkflowListResponse(BaseModel):
    workflows: List[WorkflowResponse]
    total: int


class WorkflowInstanceResponse(BaseModel):
    instance_id: str
    workflow_id: str
    workflow_name: str
    status: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    error_message: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class WorkflowInstanceListResponse(BaseModel):
    instances: List[WorkflowInstanceResponse]
    total: int


class ActionCatalogItem(BaseModel):
    name: str
    description: str
    category: str
    parameters: Dict[str, str]


class ActionCatalogResponse(BaseModel):
    categories: List[str]
    actions: List[ActionCatalogItem]
    total: int


# ============ Action Catalog (Static) ============

# 액션 카탈로그 (정적 데이터)
ACTION_CATALOG = {
    "notification": [
        {
            "name": "send_slack_notification",
            "description": "Slack 채널에 알림을 전송합니다",
            "parameters": {
                "channel": "string (슬랙 채널명)",
                "message": "string (메시지 내용)",
                "mention": "string (멘션할 사용자, 선택)",
            },
        },
        {
            "name": "send_email",
            "description": "이메일을 전송합니다",
            "parameters": {
                "to": "string (수신자 이메일)",
                "subject": "string (제목)",
                "body": "string (본문)",
            },
        },
        {
            "name": "send_sms",
            "description": "SMS 문자를 전송합니다",
            "parameters": {
                "phone": "string (전화번호)",
                "message": "string (메시지 내용)",
            },
        },
    ],
    "data": [
        {
            "name": "save_to_database",
            "description": "데이터를 데이터베이스에 저장합니다",
            "parameters": {
                "table": "string (테이블명)",
                "data": "object (저장할 데이터)",
            },
        },
        {
            "name": "export_to_csv",
            "description": "데이터를 CSV 파일로 내보냅니다",
            "parameters": {
                "data": "array (내보낼 데이터)",
                "filename": "string (파일명)",
            },
        },
        {
            "name": "log_event",
            "description": "이벤트를 로그에 기록합니다",
            "parameters": {
                "event_type": "string (이벤트 타입)",
                "details": "object (상세 정보)",
            },
        },
    ],
    "control": [
        {
            "name": "stop_production_line",
            "description": "생산 라인을 중지합니다",
            "parameters": {
                "line_code": "string (라인 코드)",
                "reason": "string (중지 사유)",
            },
        },
        {
            "name": "adjust_sensor_threshold",
            "description": "센서 임계값을 조정합니다",
            "parameters": {
                "sensor_id": "string (센서 ID)",
                "threshold": "number (새 임계값)",
            },
        },
        {
            "name": "trigger_maintenance",
            "description": "유지보수 작업을 트리거합니다",
            "parameters": {
                "equipment_id": "string (장비 ID)",
                "priority": "string (우선순위: low, medium, high)",
            },
        },
    ],
    "analysis": [
        {
            "name": "calculate_defect_rate",
            "description": "불량률을 계산합니다",
            "parameters": {
                "line_code": "string (라인 코드)",
                "time_range": "string (시간 범위)",
            },
        },
        {
            "name": "analyze_sensor_trend",
            "description": "센서 데이터 추세를 분석합니다",
            "parameters": {
                "sensor_type": "string (센서 타입)",
                "hours": "number (분석 기간, 시간 단위)",
            },
        },
        {
            "name": "predict_equipment_failure",
            "description": "장비 고장을 예측합니다",
            "parameters": {
                "equipment_id": "string (장비 ID)",
                "sensor_data": "array (센서 데이터)",
            },
        },
    ],
}

# ============ Helper Functions ============

def _workflow_to_response(wf: Workflow) -> WorkflowResponse:
    """ORM 객체를 Response 모델로 변환"""
    return WorkflowResponse(
        workflow_id=str(wf.workflow_id),
        name=wf.name,
        description=wf.description,
        dsl_definition=wf.dsl_definition or {},
        version=wf.version,
        is_active=wf.is_active,
        created_at=wf.created_at,
        updated_at=wf.updated_at,
    )


def _instance_to_response(inst: WorkflowInstance, workflow_name: str) -> WorkflowInstanceResponse:
    """ORM 객체를 Response 모델로 변환"""
    return WorkflowInstanceResponse(
        instance_id=str(inst.instance_id),
        workflow_id=str(inst.workflow_id),
        workflow_name=workflow_name,
        status=inst.status,
        input_data=inst.input_data or {},
        output_data=inst.output_data or {},
        error_message=inst.error_message,
        started_at=inst.started_at,
        completed_at=inst.completed_at,
    )


# Default tenant_id for MVP (single tenant)
DEFAULT_TENANT_ID = uuid4()


# ============ API Endpoints ============

@router.get("", response_model=WorkflowListResponse)
async def list_workflows(
    db: Session = Depends(get_db),
    is_active: Optional[bool] = Query(None, description="활성 상태 필터"),
    search: Optional[str] = Query(None, description="이름/설명 검색"),
):
    """
    워크플로우 목록 조회 (PostgreSQL)
    """
    try:
        query = db.query(Workflow)

        # 필터링
        if is_active is not None:
            query = query.filter(Workflow.is_active == is_active)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                (Workflow.name.ilike(search_pattern)) |
                (Workflow.description.ilike(search_pattern))
            )

        # 정렬 (최신순)
        query = query.order_by(Workflow.created_at.desc())

        workflows = query.all()
        total = len(workflows)

        return WorkflowListResponse(
            workflows=[_workflow_to_response(w) for w in workflows],
            total=total,
        )
    except Exception:
        # DB 연결 실패 시 빈 목록 반환
        return WorkflowListResponse(
            workflows=[],
            total=0,
        )


@router.get("/actions", response_model=ActionCatalogResponse)
async def get_action_catalog(
    category: Optional[str] = Query(None, description="카테고리 필터"),
):
    """
    사용 가능한 액션 카탈로그 조회 (정적 데이터)
    """
    actions = []
    categories = list(ACTION_CATALOG.keys())

    if category and category in ACTION_CATALOG:
        for action in ACTION_CATALOG[category]:
            actions.append(ActionCatalogItem(
                **action,
                category=category,
            ))
    else:
        for cat, cat_actions in ACTION_CATALOG.items():
            for action in cat_actions:
                actions.append(ActionCatalogItem(
                    **action,
                    category=cat,
                ))

    return ActionCatalogResponse(
        categories=categories,
        actions=actions,
        total=len(actions),
    )


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
):
    """
    워크플로우 상세 조회 (PostgreSQL)
    """
    try:
        wf_uuid = UUID(workflow_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workflow ID format")

    workflow = db.query(Workflow).filter(Workflow.workflow_id == wf_uuid).first()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    return _workflow_to_response(workflow)


@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workflow(
    workflow: WorkflowCreate,
    db: Session = Depends(get_db),
):
    """
    새 워크플로우 생성 (PostgreSQL)
    """
    # tenant 확인 또는 생성 (MVP: default tenant)
    from app.models import Tenant

    tenant = db.query(Tenant).first()
    if not tenant:
        # Default tenant 생성
        tenant = Tenant(
            name="Default Tenant",
            slug="default",
            settings={},
        )
        db.add(tenant)
        db.commit()
        db.refresh(tenant)

    # 새 워크플로우 생성
    new_workflow = Workflow(
        tenant_id=tenant.tenant_id,
        name=workflow.name,
        description=workflow.description,
        dsl_definition=workflow.dsl_definition.model_dump(),
        version="1.0.0",
        is_active=True,
    )

    db.add(new_workflow)
    db.commit()
    db.refresh(new_workflow)

    return _workflow_to_response(new_workflow)


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    name: Optional[str] = None,
    description: Optional[str] = None,
    is_active: Optional[bool] = None,
):
    """
    워크플로우 수정 (PostgreSQL)
    """
    try:
        wf_uuid = UUID(workflow_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workflow ID format")

    workflow = db.query(Workflow).filter(Workflow.workflow_id == wf_uuid).first()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if name is not None:
        workflow.name = name
    if description is not None:
        workflow.description = description
    if is_active is not None:
        workflow.is_active = is_active

    workflow.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(workflow)

    return _workflow_to_response(workflow)


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
):
    """
    워크플로우 삭제 (PostgreSQL)
    """
    try:
        wf_uuid = UUID(workflow_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workflow ID format")

    workflow = db.query(Workflow).filter(Workflow.workflow_id == wf_uuid).first()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    db.delete(workflow)
    db.commit()

    return None


@router.post("/{workflow_id}/run", response_model=WorkflowInstanceResponse)
async def run_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    input_data: Optional[Dict[str, Any]] = None,
):
    """
    워크플로우 실행 (PostgreSQL)

    DSL 노드를 순차적으로 실행하고, 알림 액션은 실제로 전송합니다.
    """
    from app.services.notifications import notification_manager, NotificationStatus
    import logging

    logger = logging.getLogger(__name__)

    try:
        wf_uuid = UUID(workflow_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workflow ID format")

    workflow = db.query(Workflow).filter(Workflow.workflow_id == wf_uuid).first()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if not workflow.is_active:
        raise HTTPException(status_code=400, detail="Workflow is not active")

    now = datetime.utcnow()
    execution_results = []
    error_message = None
    status = "completed"

    # DSL 노드 실행
    dsl = workflow.dsl_definition or {}
    nodes = dsl.get("nodes", [])

    for node in nodes:
        node_type = node.get("type")
        node_id = node.get("id")
        config = node.get("config", {})

        # 알림 액션 실행
        if node_type == "action":
            action_name = config.get("action")

            # 알림 액션인 경우 실제 실행
            if action_name in ["send_slack_notification", "send_email", "send_sms"]:
                try:
                    # input_data로 파라미터 오버라이드 가능
                    merged_params = {**config.get("parameters", {})}
                    if input_data:
                        merged_params.update(input_data.get(node_id, {}))

                    result = await notification_manager.execute_action(
                        action_name,
                        merged_params
                    )

                    execution_results.append({
                        "node_id": node_id,
                        "action": action_name,
                        "status": result.status.value,
                        "message": result.message,
                        "details": result.details,
                    })

                    # FAILED 상태면 에러 기록 (SKIPPED는 설정 미완료로 허용)
                    if result.status == NotificationStatus.FAILED:
                        error_message = f"Node {node_id}: {result.message}"
                        status = "failed"
                        break

                    logger.info(f"워크플로우 액션 실행: {action_name} -> {result.status.value}")

                except Exception as e:
                    logger.error(f"워크플로우 액션 실행 오류: {action_name} - {e}")
                    error_message = f"Node {node_id}: {str(e)}"
                    status = "failed"
                    execution_results.append({
                        "node_id": node_id,
                        "action": action_name,
                        "status": "error",
                        "error": str(e),
                    })
                    break
            else:
                # 기타 액션은 로그만 기록 (V1에서 구현 예정)
                execution_results.append({
                    "node_id": node_id,
                    "action": action_name,
                    "status": "skipped",
                    "message": "Action not implemented yet",
                })

    # 새 실행 인스턴스 생성
    instance = WorkflowInstance(
        workflow_id=workflow.workflow_id,
        tenant_id=workflow.tenant_id,
        status=status,
        input_data=input_data or {},
        output_data={
            "message": "Workflow executed" if status == "completed" else "Workflow failed",
            "nodes_total": len(nodes),
            "nodes_executed": len(execution_results),
            "results": execution_results,
        },
        error_message=error_message,
        started_at=now,
        completed_at=datetime.utcnow(),
    )

    db.add(instance)
    db.commit()
    db.refresh(instance)

    return _instance_to_response(instance, workflow.name)


@router.get("/{workflow_id}/instances", response_model=WorkflowInstanceListResponse)
async def list_workflow_instances(
    workflow_id: str,
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None, description="상태 필터"),
):
    """
    워크플로우 실행 이력 조회 (PostgreSQL)
    """
    try:
        wf_uuid = UUID(workflow_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workflow ID format")

    workflow = db.query(Workflow).filter(Workflow.workflow_id == wf_uuid).first()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    query = db.query(WorkflowInstance).filter(WorkflowInstance.workflow_id == wf_uuid)

    if status:
        query = query.filter(WorkflowInstance.status == status)

    query = query.order_by(WorkflowInstance.started_at.desc())

    instances = query.all()

    return WorkflowInstanceListResponse(
        instances=[_instance_to_response(inst, workflow.name) for inst in instances],
        total=len(instances),
    )
