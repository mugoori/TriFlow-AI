"""
Workflow Router
워크플로우 CRUD 및 실행 API
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field

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


# ============ Mock Data ============

# 액션 카탈로그 (workflow_planner.py와 동일)
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

# Mock 워크플로우 저장소 (MVP용)
MOCK_WORKFLOWS: Dict[str, Dict[str, Any]] = {}
MOCK_INSTANCES: Dict[str, Dict[str, Any]] = {}


def _init_mock_data():
    """Mock 데이터 초기화"""
    if not MOCK_WORKFLOWS:
        # 샘플 워크플로우 추가
        sample_workflows = [
            {
                "workflow_id": str(uuid4()),
                "name": "불량률 경고 알림",
                "description": "불량률이 5%를 초과하면 Slack으로 알림을 전송합니다",
                "dsl_definition": {
                    "name": "불량률 경고 알림",
                    "description": "불량률 5% 초과 시 Slack 알림",
                    "trigger": {"type": "event", "config": {"event_type": "defect_alert"}},
                    "nodes": [
                        {
                            "id": "check_defect",
                            "type": "condition",
                            "config": {"condition": "defect_rate > 0.05"},
                            "next": ["send_alert"],
                        },
                        {
                            "id": "send_alert",
                            "type": "action",
                            "config": {
                                "action": "send_slack_notification",
                                "parameters": {
                                    "channel": "#production-alerts",
                                    "message": "불량률 경고: 현재 불량률이 5%를 초과했습니다.",
                                },
                            },
                            "next": [],
                        },
                    ],
                },
                "version": "1.0.0",
                "is_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            },
            {
                "workflow_id": str(uuid4()),
                "name": "온도 이상 긴급 대응",
                "description": "온도가 80°C를 초과하면 라인 중지 및 이메일 알림",
                "dsl_definition": {
                    "name": "온도 이상 긴급 대응",
                    "description": "온도 80°C 초과 시 긴급 대응",
                    "trigger": {"type": "event", "config": {"event_type": "temperature_alert"}},
                    "nodes": [
                        {
                            "id": "check_temp",
                            "type": "condition",
                            "config": {"condition": "temperature > 80"},
                            "next": ["stop_line", "notify_manager"],
                        },
                        {
                            "id": "stop_line",
                            "type": "action",
                            "config": {
                                "action": "stop_production_line",
                                "parameters": {"line_code": "LINE_A", "reason": "온도 이상"},
                            },
                            "next": [],
                        },
                        {
                            "id": "notify_manager",
                            "type": "action",
                            "config": {
                                "action": "send_email",
                                "parameters": {
                                    "to": "manager@factory.com",
                                    "subject": "[긴급] 온도 이상 감지",
                                    "body": "LINE_A에서 온도 이상이 감지되어 라인이 중지되었습니다.",
                                },
                            },
                            "next": [],
                        },
                    ],
                },
                "version": "1.0.0",
                "is_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            },
            {
                "workflow_id": str(uuid4()),
                "name": "정기 장비 점검",
                "description": "매일 오전 9시에 장비 상태를 점검하고 리포트 생성",
                "dsl_definition": {
                    "name": "정기 장비 점검",
                    "description": "일일 장비 상태 점검",
                    "trigger": {"type": "schedule", "config": {"cron": "0 9 * * *"}},
                    "nodes": [
                        {
                            "id": "analyze_sensors",
                            "type": "action",
                            "config": {
                                "action": "analyze_sensor_trend",
                                "parameters": {"sensor_type": "all", "hours": 24},
                            },
                            "next": ["check_anomaly"],
                        },
                        {
                            "id": "check_anomaly",
                            "type": "condition",
                            "config": {"condition": "anomaly_detected == true"},
                            "next": ["trigger_maintenance"],
                        },
                        {
                            "id": "trigger_maintenance",
                            "type": "action",
                            "config": {
                                "action": "trigger_maintenance",
                                "parameters": {"equipment_id": "detected_equipment", "priority": "medium"},
                            },
                            "next": [],
                        },
                    ],
                },
                "version": "1.0.0",
                "is_active": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            },
        ]

        for wf in sample_workflows:
            MOCK_WORKFLOWS[wf["workflow_id"]] = wf


_init_mock_data()


# ============ API Endpoints ============

@router.get("", response_model=WorkflowListResponse)
async def list_workflows(
    is_active: Optional[bool] = Query(None, description="활성 상태 필터"),
    search: Optional[str] = Query(None, description="이름/설명 검색"),
):
    """
    워크플로우 목록 조회
    """
    workflows = list(MOCK_WORKFLOWS.values())

    # 필터링
    if is_active is not None:
        workflows = [w for w in workflows if w["is_active"] == is_active]

    if search:
        search_lower = search.lower()
        workflows = [
            w for w in workflows
            if search_lower in w["name"].lower() or
               (w["description"] and search_lower in w["description"].lower())
        ]

    # 정렬 (최신순)
    workflows.sort(key=lambda x: x["created_at"], reverse=True)

    return WorkflowListResponse(
        workflows=[WorkflowResponse(**w) for w in workflows],
        total=len(workflows),
    )


@router.get("/actions", response_model=ActionCatalogResponse)
async def get_action_catalog(
    category: Optional[str] = Query(None, description="카테고리 필터"),
):
    """
    사용 가능한 액션 카탈로그 조회
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
async def get_workflow(workflow_id: str):
    """
    워크플로우 상세 조회
    """
    if workflow_id not in MOCK_WORKFLOWS:
        raise HTTPException(status_code=404, detail="Workflow not found")

    return WorkflowResponse(**MOCK_WORKFLOWS[workflow_id])


@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workflow(workflow: WorkflowCreate):
    """
    새 워크플로우 생성
    """
    workflow_id = str(uuid4())
    now = datetime.utcnow()

    new_workflow = {
        "workflow_id": workflow_id,
        "name": workflow.name,
        "description": workflow.description,
        "dsl_definition": workflow.dsl_definition.model_dump(),
        "version": "1.0.0",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }

    MOCK_WORKFLOWS[workflow_id] = new_workflow

    return WorkflowResponse(**new_workflow)


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    is_active: Optional[bool] = None,
):
    """
    워크플로우 수정
    """
    if workflow_id not in MOCK_WORKFLOWS:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow = MOCK_WORKFLOWS[workflow_id]

    if name is not None:
        workflow["name"] = name
    if description is not None:
        workflow["description"] = description
    if is_active is not None:
        workflow["is_active"] = is_active

    workflow["updated_at"] = datetime.utcnow()

    return WorkflowResponse(**workflow)


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(workflow_id: str):
    """
    워크플로우 삭제
    """
    if workflow_id not in MOCK_WORKFLOWS:
        raise HTTPException(status_code=404, detail="Workflow not found")

    del MOCK_WORKFLOWS[workflow_id]

    return None


@router.post("/{workflow_id}/run", response_model=WorkflowInstanceResponse)
async def run_workflow(
    workflow_id: str,
    input_data: Optional[Dict[str, Any]] = None,
):
    """
    워크플로우 실행 (Mock)
    """
    if workflow_id not in MOCK_WORKFLOWS:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow = MOCK_WORKFLOWS[workflow_id]

    if not workflow["is_active"]:
        raise HTTPException(status_code=400, detail="Workflow is not active")

    instance_id = str(uuid4())
    now = datetime.utcnow()

    # Mock 실행 (즉시 완료)
    instance = {
        "instance_id": instance_id,
        "workflow_id": workflow_id,
        "workflow_name": workflow["name"],
        "status": "completed",
        "input_data": input_data or {},
        "output_data": {
            "message": "Workflow executed successfully (Mock)",
            "nodes_executed": len(workflow["dsl_definition"]["nodes"]),
        },
        "error_message": None,
        "started_at": now,
        "completed_at": now,
    }

    MOCK_INSTANCES[instance_id] = instance

    return WorkflowInstanceResponse(**instance)


@router.get("/{workflow_id}/instances", response_model=WorkflowInstanceListResponse)
async def list_workflow_instances(
    workflow_id: str,
    status: Optional[str] = Query(None, description="상태 필터"),
):
    """
    워크플로우 실행 이력 조회
    """
    if workflow_id not in MOCK_WORKFLOWS:
        raise HTTPException(status_code=404, detail="Workflow not found")

    instances = [
        inst for inst in MOCK_INSTANCES.values()
        if inst["workflow_id"] == workflow_id
    ]

    if status:
        instances = [inst for inst in instances if inst["status"] == status]

    instances.sort(key=lambda x: x["started_at"], reverse=True)

    return WorkflowInstanceListResponse(
        instances=[WorkflowInstanceResponse(**inst) for inst in instances],
        total=len(instances),
    )
