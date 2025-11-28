"""
Workflow Router
워크플로우 CRUD 및 실행 API - PostgreSQL DB 연동
"""
import copy
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

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
    display_name: str
    description: str
    category: str
    category_display_name: str
    parameters: Dict[str, str]


class CategoryInfo(BaseModel):
    name: str
    display_name: str


class ActionCatalogResponse(BaseModel):
    categories: List[CategoryInfo]
    actions: List[ActionCatalogItem]
    total: int


# ============ Action Catalog (Static) ============

# 액션 카탈로그 (정적 데이터)
# 카테고리 한글명 매핑
CATEGORY_DISPLAY_NAMES = {
    "notification": "알림",
    "data": "데이터",
    "control": "제어",
    "analysis": "분석",
}

ACTION_CATALOG = {
    "notification": [
        {
            "name": "send_slack_notification",
            "display_name": "슬랙 알림 전송",
            "description": "Slack 채널에 알림 메시지를 전송합니다",
            "parameters": {
                "channel": "string (슬랙 채널명)",
                "message": "string (메시지 내용)",
                "mention": "string (멘션할 사용자, 선택)",
            },
        },
        {
            "name": "send_email",
            "display_name": "이메일 전송",
            "description": "지정된 수신자에게 이메일을 전송합니다",
            "parameters": {
                "to": "string (수신자 이메일)",
                "subject": "string (제목)",
                "body": "string (본문)",
            },
        },
        {
            "name": "send_sms",
            "display_name": "SMS 문자 전송",
            "description": "휴대폰으로 SMS 문자를 전송합니다",
            "parameters": {
                "phone": "string (전화번호)",
                "message": "string (메시지 내용)",
            },
        },
    ],
    "data": [
        {
            "name": "save_to_database",
            "display_name": "DB 저장",
            "description": "데이터를 데이터베이스 테이블에 저장합니다",
            "parameters": {
                "table": "string (테이블명)",
                "data": "object (저장할 데이터)",
            },
        },
        {
            "name": "export_to_csv",
            "display_name": "CSV 내보내기",
            "description": "데이터를 CSV 파일로 내보냅니다",
            "parameters": {
                "data": "array (내보낼 데이터)",
                "filename": "string (파일명)",
            },
        },
        {
            "name": "log_event",
            "display_name": "이벤트 로그 기록",
            "description": "시스템 로그에 이벤트를 기록합니다",
            "parameters": {
                "event_type": "string (이벤트 타입)",
                "details": "object (상세 정보)",
            },
        },
    ],
    "control": [
        {
            "name": "stop_production_line",
            "display_name": "생산라인 중지",
            "description": "지정된 생산 라인의 가동을 중지합니다",
            "parameters": {
                "line_code": "string (라인 코드)",
                "reason": "string (중지 사유)",
            },
        },
        {
            "name": "adjust_sensor_threshold",
            "display_name": "센서 임계값 조정",
            "description": "센서의 경고/알림 임계값을 변경합니다",
            "parameters": {
                "sensor_id": "string (센서 ID)",
                "threshold": "number (새 임계값)",
            },
        },
        {
            "name": "trigger_maintenance",
            "display_name": "유지보수 요청",
            "description": "장비 유지보수 작업을 요청합니다",
            "parameters": {
                "equipment_id": "string (장비 ID)",
                "priority": "string (우선순위: low, medium, high)",
            },
        },
    ],
    "analysis": [
        {
            "name": "calculate_defect_rate",
            "display_name": "불량률 계산",
            "description": "생산 라인의 불량률을 계산합니다",
            "parameters": {
                "line_code": "string (라인 코드)",
                "time_range": "string (시간 범위)",
            },
        },
        {
            "name": "analyze_sensor_trend",
            "display_name": "센서 추세 분석",
            "description": "센서 데이터의 변화 추세를 분석합니다",
            "parameters": {
                "sensor_type": "string (센서 타입)",
                "hours": "number (분석 기간, 시간 단위)",
            },
        },
        {
            "name": "predict_equipment_failure",
            "display_name": "고장 예측",
            "description": "장비의 고장 가능성을 예측합니다",
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

    한글 display_name과 category_display_name을 포함합니다.
    """
    actions = []
    categories = [
        CategoryInfo(name=cat, display_name=CATEGORY_DISPLAY_NAMES.get(cat, cat))
        for cat in ACTION_CATALOG.keys()
    ]

    if category and category in ACTION_CATALOG:
        cat_display = CATEGORY_DISPLAY_NAMES.get(category, category)
        for action in ACTION_CATALOG[category]:
            actions.append(ActionCatalogItem(
                name=action["name"],
                display_name=action.get("display_name", action["name"]),
                description=action["description"],
                category=category,
                category_display_name=cat_display,
                parameters=action["parameters"],
            ))
    else:
        for cat, cat_actions in ACTION_CATALOG.items():
            cat_display = CATEGORY_DISPLAY_NAMES.get(cat, cat)
            for action in cat_actions:
                actions.append(ActionCatalogItem(
                    name=action["name"],
                    display_name=action.get("display_name", action["name"]),
                    description=action["description"],
                    category=cat,
                    category_display_name=cat_display,
                    parameters=action["parameters"],
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


class WorkflowUpdate(BaseModel):
    """워크플로우 수정 요청 모델"""
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    dsl_definition: Optional[WorkflowDSL] = None


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str,
    update_data: WorkflowUpdate,
    db: Session = Depends(get_db),
):
    """
    워크플로우 수정 (PostgreSQL)
    - name, description, is_active: 기본 정보 수정
    - dsl_definition: 워크플로우 DSL 전체 수정
    """
    try:
        wf_uuid = UUID(workflow_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workflow ID format")

    workflow = db.query(Workflow).filter(Workflow.workflow_id == wf_uuid).first()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if update_data.name is not None:
        workflow.name = update_data.name
    if update_data.description is not None:
        workflow.description = update_data.description
    if update_data.is_active is not None:
        workflow.is_active = update_data.is_active
    if update_data.dsl_definition is not None:
        # DSL 업데이트 시 name, description도 함께 업데이트
        dsl_dict = update_data.dsl_definition.model_dump()

        # JSONB 필드 업데이트를 위해 새 dict로 복사하여 할당
        new_dsl = copy.deepcopy(dsl_dict)
        workflow.dsl_definition = new_dsl

        # SQLAlchemy에 JSONB 필드 변경을 명시적으로 알림
        flag_modified(workflow, "dsl_definition")

        # DSL에서 name, description이 있으면 워크플로우에도 반영
        if update_data.dsl_definition.name:
            workflow.name = update_data.dsl_definition.name
        if update_data.dsl_definition.description:
            workflow.description = update_data.dsl_definition.description

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


class WorkflowRunRequest(BaseModel):
    """워크플로우 실행 요청"""
    input_data: Optional[Dict[str, Any]] = Field(default=None, description="입력 데이터 (센서 값 등)")
    use_simulated_data: bool = Field(default=False, description="시뮬레이션 데이터 사용 여부")
    simulation_scenario: str = Field(default="random", description="시뮬레이션 시나리오 (normal, alert, random)")


@router.post("/{workflow_id}/run", response_model=WorkflowInstanceResponse)
async def run_workflow(
    workflow_id: str,
    request: Optional[WorkflowRunRequest] = None,
    db: Session = Depends(get_db),
):
    """
    워크플로우 실행 (PostgreSQL + WorkflowEngine)

    조건 노드를 평가하고, 액션을 실행합니다.
    시뮬레이션 데이터를 사용하거나 직접 데이터를 전달할 수 있습니다.
    """
    from app.services.notifications import notification_manager
    from app.services.workflow_engine import workflow_engine, sensor_simulator
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

    # 요청 데이터 파싱
    req = request or WorkflowRunRequest()
    input_data = req.input_data

    # 시뮬레이션 데이터 생성
    if req.use_simulated_data and not input_data:
        input_data = sensor_simulator.generate_sensor_data(scenario=req.simulation_scenario)
        logger.info(f"시뮬레이션 데이터 생성됨: {req.simulation_scenario}")

    # DSL 가져오기
    dsl = workflow.dsl_definition or {}

    # 워크플로우 엔진으로 실행
    engine_result = await workflow_engine.execute_workflow(
        workflow_id=str(workflow.workflow_id),
        dsl=dsl,
        input_data=input_data,
        use_simulated_data=False,  # 이미 위에서 생성함
    )

    # 알림 액션 별도 처리 (workflow_engine에서 delegated 처리된 것들)
    nodes = dsl.get("nodes", [])
    for node in nodes:
        if node.get("type") == "action":
            config = node.get("config", {})
            action_name = config.get("action")

            if action_name in ["send_slack_notification", "send_email", "send_sms"]:
                try:
                    merged_params = {**config.get("parameters", {})}
                    if input_data:
                        merged_params.update(input_data.get(node.get("id"), {}))

                    result = await notification_manager.execute_action(
                        action_name,
                        merged_params
                    )

                    # engine_result의 해당 노드 결과 업데이트
                    for r in engine_result.get("results", []):
                        if r.get("node_id") == node.get("id"):
                            r["status"] = result.status.value
                            r["message"] = result.message
                            r["details"] = result.details

                    logger.info(f"알림 액션 실행: {action_name} -> {result.status.value}")

                except Exception as e:
                    logger.error(f"알림 액션 실행 오류: {action_name} - {e}")

    # 최종 상태 결정
    status = engine_result.get("status", "completed")
    error_message = engine_result.get("error_message")

    # 새 실행 인스턴스 생성
    instance = WorkflowInstance(
        workflow_id=workflow.workflow_id,
        tenant_id=workflow.tenant_id,
        status=status,
        input_data=input_data or {},
        output_data={
            "message": "Workflow executed" if status == "completed" else "Workflow failed",
            "nodes_total": engine_result.get("nodes_total", 0),
            "nodes_executed": engine_result.get("nodes_executed", 0),
            "nodes_skipped": engine_result.get("nodes_skipped", 0),
            "results": engine_result.get("results", []),
            "execution_time_ms": engine_result.get("execution_time_ms", 0),
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


# ============ 센서 시뮬레이터 API ============

class SensorSimulatorRequest(BaseModel):
    """센서 데이터 시뮬레이션 요청"""
    sensors: Optional[List[str]] = Field(default=None, description="생성할 센서 목록")
    scenario: str = Field(default="random", description="시나리오 (normal, alert, random)")
    scenario_name: Optional[str] = Field(default=None, description="사전 정의된 시나리오 이름")


@router.post("/simulator/generate")
async def generate_simulated_data(
    request: Optional[SensorSimulatorRequest] = None,
):
    """
    센서 시뮬레이션 데이터 생성

    시나리오:
    - normal: 정상 범위 데이터
    - alert: 임계값 초과 데이터
    - random: 완전 랜덤 데이터

    사전 정의된 시나리오:
    - high_temperature, low_pressure, equipment_error
    - high_defect_rate, production_delay, shift_change
    - normal_operation
    """
    from app.services.workflow_engine import sensor_simulator

    req = request or SensorSimulatorRequest()

    # 사전 정의된 시나리오 사용
    if req.scenario_name:
        data = sensor_simulator.generate_test_scenario(req.scenario_name)
    else:
        data = sensor_simulator.generate_sensor_data(
            sensors=req.sensors,
            scenario=req.scenario
        )

    return {
        "success": True,
        "data": data,
        "available_sensors": [
            "temperature", "pressure", "humidity", "vibration",
            "defect_rate", "consecutive_defects", "runtime_hours",
            "production_count", "units_per_hour", "current_hour",
            "equipment_status"
        ],
        "available_scenarios": [
            "high_temperature", "low_pressure", "equipment_error",
            "high_defect_rate", "production_delay", "shift_change",
            "normal_operation"
        ],
    }


# ============ 실행 로그 API ============

class ExecutionLogResponse(BaseModel):
    """실행 로그 응답"""
    logs: List[Dict[str, Any]]
    total: int


@router.get("/logs/execution")
async def get_execution_logs(
    workflow_id: Optional[str] = Query(None, description="워크플로우 ID 필터"),
    event_type: Optional[str] = Query(None, description="이벤트 타입 필터"),
    limit: int = Query(50, ge=1, le=500, description="최대 조회 개수"),
):
    """
    실행 로그 조회 (인메모리)

    워크플로우 실행 중 기록된 이벤트 로그를 조회합니다.
    """
    from app.services.workflow_engine import execution_log_store

    logs = execution_log_store.get_logs(
        workflow_id=workflow_id,
        event_type=event_type,
        limit=limit
    )

    return ExecutionLogResponse(
        logs=logs,
        total=len(logs),
    )


@router.delete("/logs/execution")
async def clear_execution_logs():
    """
    실행 로그 초기화 (인메모리)
    """
    from app.services.workflow_engine import execution_log_store

    execution_log_store.clear()

    return {"success": True, "message": "실행 로그가 초기화되었습니다."}


# ============ 조건 평가 테스트 API ============

class ConditionTestRequest(BaseModel):
    """조건 평가 테스트 요청"""
    condition: str = Field(..., description="평가할 조건식")
    context: Dict[str, Any] = Field(default_factory=dict, description="컨텍스트 변수")


@router.post("/test/condition")
async def test_condition(
    request: ConditionTestRequest,
):
    """
    조건식 평가 테스트

    조건식과 컨텍스트를 전달하면 평가 결과를 반환합니다.

    예시:
    - condition: "temperature > 80"
    - context: {"temperature": 85}
    - 결과: true
    """
    from app.services.workflow_engine import condition_evaluator

    result, message = condition_evaluator.evaluate(
        request.condition,
        request.context
    )

    return {
        "condition": request.condition,
        "context": request.context,
        "result": result,
        "message": message,
    }
