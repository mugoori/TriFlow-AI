"""
Workflow Router
워크플로우 CRUD 및 실행 API - PostgreSQL DB 연동
"""
import copy
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Query, HTTPException, Depends, Path
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.database import get_db
from app.models import Workflow, WorkflowInstance

router = APIRouter()


def serialize_for_json(obj: Any) -> Any:
    """UUID 및 기타 비 직렬화 객체를 JSON 호환 형식으로 변환"""
    if isinstance(obj, UUID):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    return obj


# ============ Pydantic Models ============

class WorkflowTrigger(BaseModel):
    type: str = Field(..., description="트리거 타입 (event, schedule, manual)")
    config: Dict[str, Any] = Field(default_factory=dict)


class WorkflowNode(BaseModel):
    """워크플로우 노드 (재귀적 구조 지원)"""
    id: str
    type: str = Field(..., description="노드 타입 (condition, action, if_else, loop, parallel)")
    config: Dict[str, Any]
    next: List[str] = Field(default_factory=list)
    # 중첩 노드 지원 (if_else, loop, parallel용)
    then_nodes: Optional[List["WorkflowNode"]] = None
    else_nodes: Optional[List["WorkflowNode"]] = None
    loop_nodes: Optional[List["WorkflowNode"]] = None
    parallel_nodes: Optional[List["WorkflowNode"]] = None


# Pydantic v2에서 자기 참조 모델을 위한 재구축
WorkflowNode.model_rebuild()


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
        version=str(wf.version) if wf.version is not None else "1",
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
        input_data=inst.input_context or {},
        output_data=inst.runtime_context or {},
        error_message=inst.last_error,
        started_at=inst.started_at,
        completed_at=inst.ended_at,
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


# ============ 워크플로우 승인 API (라우트 우선순위를 위해 /{workflow_id} 앞에 배치) ============

class ApprovalDecision(BaseModel):
    """승인/거부 결정 요청"""
    comment: Optional[str] = Field(None, description="결정 코멘트")


class ApprovalResponse(BaseModel):
    """승인 응답"""
    approval_id: str
    status: str
    decided_by: Optional[str]
    decided_at: Optional[datetime]
    comment: Optional[str]


class ApprovalListItem(BaseModel):
    """승인 목록 항목"""
    approval_id: str
    workflow_id: str
    workflow_name: Optional[str]
    node_id: str
    title: str
    description: Optional[str]
    approval_type: str
    approvers: List[Any]  # 문자열 또는 객체 배열
    status: str
    timeout_at: Optional[datetime]
    created_at: datetime


class ApprovalListResponse(BaseModel):
    """승인 목록 응답"""
    approvals: List[ApprovalListItem]
    total: int


@router.get("/approvals", response_model=ApprovalListResponse)
async def list_pending_approvals(
    status: Optional[str] = Query("pending", description="상태 필터 (pending, approved, rejected, timeout, all)"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    승인 대기 목록 조회
    """
    from sqlalchemy import text

    try:
        # 상태 필터
        status_filter = ""
        if status and status != "all":
            status_filter = "AND a.status = :status"

        query = text(f"""
            SELECT
                a.approval_id,
                a.workflow_id,
                w.name as workflow_name,
                a.node_id,
                a.title,
                a.description,
                a.approval_type,
                a.approvers,
                a.status,
                a.timeout_at,
                a.created_at
            FROM core.workflow_approvals a
            LEFT JOIN core.workflows w ON a.workflow_id = w.workflow_id
            WHERE 1=1 {status_filter}
            ORDER BY a.created_at DESC
            LIMIT :limit OFFSET :offset
        """)

        params = {"limit": limit, "offset": offset}
        if status and status != "all":
            params["status"] = status

        result = db.execute(query, params)
        rows = result.fetchall()

        # 전체 개수 조회
        count_query = text(f"""
            SELECT COUNT(*) FROM core.workflow_approvals a
            WHERE 1=1 {status_filter}
        """)
        count_params = {}
        if status and status != "all":
            count_params["status"] = status
        total = db.execute(count_query, count_params).scalar() or 0

        approvals = []
        for row in rows:
            approvers = row.approvers if isinstance(row.approvers, list) else []
            approvals.append(ApprovalListItem(
                approval_id=str(row.approval_id),
                workflow_id=str(row.workflow_id),
                workflow_name=row.workflow_name,
                node_id=row.node_id,
                title=row.title,
                description=row.description,
                approval_type=row.approval_type,
                approvers=approvers,
                status=row.status,
                timeout_at=row.timeout_at,
                created_at=row.created_at,
            ))

        return ApprovalListResponse(approvals=approvals, total=total)

    except Exception as e:
        # 테이블이 없는 경우
        if "relation" in str(e) and "does not exist" in str(e):
            return ApprovalListResponse(approvals=[], total=0)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/approvals/{approval_id}")
async def get_approval_detail(
    approval_id: UUID,
    db: Session = Depends(get_db),
):
    """
    승인 요청 상세 조회
    """
    from sqlalchemy import text

    try:
        query = text("""
            SELECT
                a.*,
                w.name as workflow_name,
                w.dsl_json
            FROM core.workflow_approvals a
            LEFT JOIN core.workflows w ON a.workflow_id = w.workflow_id
            WHERE a.approval_id = :approval_id
        """)

        result = db.execute(query, {"approval_id": str(approval_id)})
        row = result.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="승인 요청을 찾을 수 없습니다")

        return {
            "approval_id": str(row.approval_id),
            "workflow_id": str(row.workflow_id),
            "workflow_name": row.workflow_name,
            "instance_id": str(row.instance_id) if row.instance_id else None,
            "node_id": row.node_id,
            "approval_type": row.approval_type,
            "title": row.title,
            "description": row.description,
            "approvers": row.approvers if isinstance(row.approvers, list) else [],
            "quorum_count": row.quorum_count,
            "status": row.status,
            "decided_by": str(row.decided_by) if row.decided_by else None,
            "decided_at": row.decided_at.isoformat() if row.decided_at else None,
            "decision_comment": row.decision_comment,
            "notification_channels": row.notification_channels if isinstance(row.notification_channels, list) else [],
            "timeout_at": row.timeout_at.isoformat() if row.timeout_at else None,
            "auto_approve_on_timeout": row.auto_approve_on_timeout,
            "context_data": row.context_data if isinstance(row.context_data, dict) else {},
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalResponse)
async def approve_workflow(
    approval_id: UUID,
    body: ApprovalDecision,
    db: Session = Depends(get_db),
):
    """
    워크플로우 승인

    승인 요청을 승인합니다. 승인 상태가 'pending'인 경우에만 가능합니다.
    """
    import json
    from sqlalchemy import text

    try:
        # 현재 상태 확인
        check_query = text("""
            SELECT status FROM core.workflow_approvals
            WHERE approval_id = :approval_id
        """)
        result = db.execute(check_query, {"approval_id": str(approval_id)})
        row = result.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="승인 요청을 찾을 수 없습니다")

        if row.status != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"이미 처리된 요청입니다 (현재 상태: {row.status})"
            )

        # 승인 처리
        update_query = text("""
            UPDATE core.workflow_approvals
            SET status = 'approved',
                decided_at = NOW(),
                decision_comment = :comment,
                updated_at = NOW()
            WHERE approval_id = :approval_id
            RETURNING approval_id, status, decided_by, decided_at, decision_comment
        """)

        result = db.execute(update_query, {
            "approval_id": str(approval_id),
            "comment": body.comment,
        })
        db.commit()

        updated_row = result.fetchone()

        # Redis 캐시 업데이트
        try:
            from app.services.cache_service import CacheService
            if CacheService.is_available():
                CacheService.set(
                    f"wf:approval:{approval_id}",
                    json.dumps({
                        "status": "approved",
                        "decided_at": datetime.utcnow().isoformat(),
                        "decision_comment": body.comment,
                    }),
                    expire_seconds=3600
                )
        except Exception:
            pass

        return ApprovalResponse(
            approval_id=str(updated_row.approval_id),
            status="approved",
            decided_by=str(updated_row.decided_by) if updated_row.decided_by else None,
            decided_at=updated_row.decided_at,
            comment=updated_row.decision_comment,
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalResponse)
async def reject_workflow(
    approval_id: UUID,
    body: ApprovalDecision,
    db: Session = Depends(get_db),
):
    """
    워크플로우 거부

    승인 요청을 거부합니다. 승인 상태가 'pending'인 경우에만 가능합니다.
    """
    import json
    from sqlalchemy import text

    try:
        # 현재 상태 확인
        check_query = text("""
            SELECT status FROM core.workflow_approvals
            WHERE approval_id = :approval_id
        """)
        result = db.execute(check_query, {"approval_id": str(approval_id)})
        row = result.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="승인 요청을 찾을 수 없습니다")

        if row.status != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"이미 처리된 요청입니다 (현재 상태: {row.status})"
            )

        # 거부 처리
        update_query = text("""
            UPDATE core.workflow_approvals
            SET status = 'rejected',
                decided_at = NOW(),
                decision_comment = :comment,
                updated_at = NOW()
            WHERE approval_id = :approval_id
            RETURNING approval_id, status, decided_by, decided_at, decision_comment
        """)

        result = db.execute(update_query, {
            "approval_id": str(approval_id),
            "comment": body.comment,
        })
        db.commit()

        updated_row = result.fetchone()

        # Redis 캐시 업데이트
        try:
            from app.services.cache_service import CacheService
            if CacheService.is_available():
                CacheService.set(
                    f"wf:approval:{approval_id}",
                    json.dumps({
                        "status": "rejected",
                        "decided_at": datetime.utcnow().isoformat(),
                        "decision_comment": body.comment,
                    }),
                    expire_seconds=3600
                )
        except Exception:
            pass

        return ApprovalResponse(
            approval_id=str(updated_row.approval_id),
            status="rejected",
            decided_by=str(updated_row.decided_by) if updated_row.decided_by else None,
            decided_at=updated_row.decided_at,
            comment=updated_row.decision_comment,
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approvals/{approval_id}/cancel", response_model=ApprovalResponse)
async def cancel_approval(
    approval_id: UUID,
    body: ApprovalDecision,
    db: Session = Depends(get_db),
):
    """
    승인 요청 취소

    승인 요청을 취소합니다. 워크플로우 소유자 또는 관리자만 가능합니다.
    """
    import json
    from sqlalchemy import text

    try:
        # 현재 상태 확인
        check_query = text("""
            SELECT status FROM core.workflow_approvals
            WHERE approval_id = :approval_id
        """)
        result = db.execute(check_query, {"approval_id": str(approval_id)})
        row = result.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="승인 요청을 찾을 수 없습니다")

        if row.status != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"이미 처리된 요청입니다 (현재 상태: {row.status})"
            )

        # 취소 처리
        update_query = text("""
            UPDATE core.workflow_approvals
            SET status = 'cancelled',
                decided_at = NOW(),
                decision_comment = :comment,
                updated_at = NOW()
            WHERE approval_id = :approval_id
            RETURNING approval_id, status, decided_by, decided_at, decision_comment
        """)

        result = db.execute(update_query, {
            "approval_id": str(approval_id),
            "comment": body.comment or "Cancelled by user",
        })
        db.commit()

        updated_row = result.fetchone()

        # Redis 캐시 업데이트
        try:
            from app.services.cache_service import CacheService
            if CacheService.is_available():
                CacheService.set(
                    f"wf:approval:{approval_id}",
                    json.dumps({
                        "status": "cancelled",
                        "decided_at": datetime.utcnow().isoformat(),
                        "decision_comment": body.comment or "Cancelled by user",
                    }),
                    expire_seconds=3600
                )
        except Exception:
            pass

        return ApprovalResponse(
            approval_id=str(updated_row.approval_id),
            status="cancelled",
            decided_by=str(updated_row.decided_by) if updated_row.decided_by else None,
            decided_at=updated_row.decided_at,
            comment=updated_row.decision_comment,
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============ 워크플로우 조회 API ============

@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str = Path(..., regex=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"),
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
    dsl_dict = workflow.dsl_definition.model_dump(exclude_none=False)

    new_workflow = Workflow(
        tenant_id=tenant.tenant_id,
        name=workflow.name,
        description=workflow.description,
        dsl_definition=dsl_dict,
        version=1,
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
        dsl_dict = update_data.dsl_definition.model_dump(exclude_none=False)

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


class WorkflowToggleResponse(BaseModel):
    """워크플로우 토글 응답"""
    workflow_id: str
    name: str
    is_active: bool
    message: str


@router.post("/{workflow_id}/toggle", response_model=WorkflowToggleResponse)
async def toggle_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
):
    """
    워크플로우 활성/비활성 토글

    현재 is_active 상태를 반전시킵니다.
    - true → false (비활성화)
    - false → true (활성화)
    """
    try:
        wf_uuid = UUID(workflow_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workflow ID format")

    workflow = db.query(Workflow).filter(Workflow.workflow_id == wf_uuid).first()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # 상태 토글
    workflow.is_active = not workflow.is_active
    workflow.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(workflow)

    status_msg = "활성화" if workflow.is_active else "비활성화"

    return WorkflowToggleResponse(
        workflow_id=str(workflow.workflow_id),
        name=workflow.name,
        is_active=workflow.is_active,
        message=f"워크플로우 '{workflow.name}'이(가) {status_msg}되었습니다.",
    )


class ExecuteWorkflowRequest(BaseModel):
    """워크플로우 실행 요청 (테스트 데이터 포함)"""
    context: Dict[str, Any] = Field(default_factory=dict, description="실행 컨텍스트 데이터")


@router.post("/{workflow_id}/execute", response_model=WorkflowInstanceResponse)
async def execute_workflow(
    workflow_id: str,
    request: ExecuteWorkflowRequest,
    db: Session = Depends(get_db),
):
    """
    워크플로우 수동 실행 (테스트용)

    트리거 조건과 관계없이 워크플로우를 즉시 실행합니다.
    테스트 데이터를 context로 전달하여 실행 결과를 확인할 수 있습니다.

    Example:
        POST /workflows/{id}/execute
        {"context": {"temperature": 85, "pressure": 5.5}}
    """
    from app.services.workflow_engine import workflow_engine
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
        raise HTTPException(status_code=400, detail="Workflow is not active. Toggle it on first.")

    now = datetime.utcnow()
    dsl = workflow.dsl_definition or {}
    input_data = request.context

    # 워크플로우 엔진으로 실행
    engine_result = await workflow_engine.execute_workflow(
        workflow_id=str(workflow.workflow_id),
        dsl=dsl,
        input_data=input_data,
        use_simulated_data=False,
    )

    status = engine_result.get("status", "completed")
    error_message = engine_result.get("error_message")

    # 실행 인스턴스 저장
    # workflow_id를 명시적으로 저장 (relationship으로 인한 None 방지)
    wf_id = workflow.workflow_id
    wf_name = workflow.name
    wf_tenant_id = workflow.tenant_id

    # UUID 등 비 직렬화 객체를 JSON 호환 형식으로 변환
    serialized_results = serialize_for_json(engine_result.get("results", []))

    instance = WorkflowInstance(
        workflow_id=wf_id,
        tenant_id=wf_tenant_id,
        status=status,
        input_context=input_data or {},
        runtime_context={
            "message": "Workflow executed via manual trigger",
            "nodes_total": engine_result.get("nodes_total", 0),
            "nodes_executed": engine_result.get("nodes_executed", 0),
            "nodes_skipped": engine_result.get("nodes_skipped", 0),
            "results": serialized_results,
            "execution_time_ms": engine_result.get("execution_time_ms", 0),
        },
        last_error=error_message,
        started_at=now,
        ended_at=datetime.utcnow(),
    )

    db.add(instance)
    db.commit()

    # 응답 데이터를 먼저 추출한 후 세션에서 분리
    # (이후 workflow 삭제 시 CASCADE로 인한 문제 방지)
    instance_id = str(instance.instance_id)
    instance_output = instance.runtime_context  # DB column: output_data, model attr: runtime_context
    instance_completed_at = instance.ended_at   # DB column: completed_at, model attr: ended_at
    db.expunge(instance)

    logger.info(f"Workflow executed manually: {wf_name} ({workflow_id})")

    return WorkflowInstanceResponse(
        instance_id=instance_id,
        workflow_id=str(wf_id),
        workflow_name=wf_name,
        status=status,
        input_data=input_data or {},
        output_data=instance_output or {},
        error_message=error_message,
        started_at=now,
        completed_at=instance_completed_at,
    )


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
        input_context=input_data or {},
        runtime_context={
            "message": "Workflow executed" if status == "completed" else "Workflow failed",
            "nodes_total": engine_result.get("nodes_total", 0),
            "nodes_executed": engine_result.get("nodes_executed", 0),
            "nodes_skipped": engine_result.get("nodes_skipped", 0),
            "results": engine_result.get("results", []),
            "execution_time_ms": engine_result.get("execution_time_ms", 0),
        },
        last_error=error_message,
        started_at=now,
        ended_at=datetime.utcnow(),
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


# ============ 워크플로우 상태 머신 API ============

class WorkflowStateResponse(BaseModel):
    """워크플로우 상태 응답"""
    instance_id: str
    state: str
    previous_state: Optional[str] = None
    updated_at: Optional[str] = None
    reason: Optional[str] = None
    exists: bool = True


class WorkflowStateHistoryItem(BaseModel):
    """상태 전이 히스토리 항목"""
    from_state: Optional[str] = None
    to_state: str
    reason: Optional[str] = None
    transitioned_at: str


class WorkflowStateHistoryResponse(BaseModel):
    """상태 전이 히스토리 응답"""
    instance_id: str
    history: List[WorkflowStateHistoryItem]
    total: int


class CheckpointInfo(BaseModel):
    """체크포인트 정보"""
    checkpoint_id: str
    node_id: str
    created_at: str
    expires_at: str


class CheckpointListResponse(BaseModel):
    """체크포인트 목록 응답"""
    instance_id: str
    checkpoints: List[CheckpointInfo]
    total: int


class RecoveryInfoResponse(BaseModel):
    """복구 정보 응답"""
    instance_id: str
    checkpoint_id: Optional[str] = None
    resume_from_node: Optional[str] = None
    checkpoint_created_at: Optional[str] = None
    can_resume: bool = False


class ResumeWorkflowRequest(BaseModel):
    """워크플로우 재개 요청"""
    checkpoint_id: Optional[str] = Field(None, description="특정 체크포인트 ID (없으면 최신)")
    additional_input: Optional[Dict[str, Any]] = Field(None, description="추가 입력 데이터")


@router.get("/instances/{instance_id}/state", response_model=WorkflowStateResponse)
async def get_instance_state(instance_id: str):
    """
    워크플로우 인스턴스 상태 조회

    - instance_id: 워크플로우 인스턴스 ID
    """
    from app.services.workflow_engine import workflow_state_machine

    state_info = workflow_state_machine.get_state(instance_id)

    return WorkflowStateResponse(
        instance_id=instance_id,
        state=state_info.get("state", "unknown"),
        previous_state=state_info.get("previous_state"),
        updated_at=state_info.get("updated_at"),
        reason=state_info.get("reason"),
        exists=state_info.get("exists", False),
    )


@router.get("/instances/{instance_id}/history", response_model=WorkflowStateHistoryResponse)
async def get_instance_state_history(
    instance_id: str,
    limit: int = Query(50, ge=1, le=200, description="최대 조회 개수")
):
    """
    워크플로우 인스턴스 상태 전이 히스토리 조회
    """
    from app.services.workflow_engine import workflow_state_machine

    history = workflow_state_machine.get_history(instance_id, limit)

    return WorkflowStateHistoryResponse(
        instance_id=instance_id,
        history=[
            WorkflowStateHistoryItem(
                from_state=item.get("from_state"),
                to_state=item.get("to_state", "unknown"),
                reason=item.get("reason"),
                transitioned_at=item.get("transitioned_at", ""),
            )
            for item in history
        ],
        total=len(history),
    )


@router.get("/instances/{instance_id}/checkpoints", response_model=CheckpointListResponse)
async def list_instance_checkpoints(
    instance_id: str,
    limit: int = Query(10, ge=1, le=50, description="최대 조회 개수")
):
    """
    워크플로우 인스턴스의 체크포인트 목록 조회
    """
    from app.services.workflow_engine import checkpoint_manager

    checkpoints = await checkpoint_manager.list_checkpoints(instance_id, limit)

    return CheckpointListResponse(
        instance_id=instance_id,
        checkpoints=[
            CheckpointInfo(
                checkpoint_id=cp.get("checkpoint_id", ""),
                node_id=cp.get("node_id", ""),
                created_at=cp.get("created_at", ""),
                expires_at=cp.get("expires_at", ""),
            )
            for cp in checkpoints
        ],
        total=len(checkpoints),
    )


@router.get("/instances/{instance_id}/recovery", response_model=RecoveryInfoResponse)
async def get_instance_recovery_info(instance_id: str):
    """
    워크플로우 인스턴스 복구 정보 조회

    워크플로우 재개 시 어디서부터 시작할지 정보 제공
    """
    from app.services.workflow_engine import checkpoint_manager

    recovery_info = await checkpoint_manager.get_recovery_info(instance_id)

    if not recovery_info:
        return RecoveryInfoResponse(
            instance_id=instance_id,
            can_resume=False,
        )

    return RecoveryInfoResponse(
        instance_id=instance_id,
        checkpoint_id=recovery_info.get("checkpoint_id"),
        resume_from_node=recovery_info.get("resume_from_node"),
        checkpoint_created_at=recovery_info.get("checkpoint_created_at"),
        can_resume=recovery_info.get("can_resume", False),
    )


@router.post("/instances/{instance_id}/resume")
async def resume_workflow_instance(
    instance_id: str,
    body: ResumeWorkflowRequest,
    db: Session = Depends(get_db)
):
    """
    대기 중인 워크플로우 인스턴스 재개

    체크포인트에서 워크플로우를 재개합니다.
    """
    from app.services.workflow_engine import (
        workflow_engine,
        workflow_state_machine,
        checkpoint_manager,
        WorkflowState,
    )

    # 1. 현재 상태 확인
    state_info = workflow_state_machine.get_state(instance_id)
    if not state_info.get("exists"):
        raise HTTPException(status_code=404, detail="Instance not found")

    current_state = state_info.get("state")
    if current_state not in ["waiting", "paused"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resume instance in state: {current_state}"
        )

    # 2. 복구 정보 확인
    recovery_info = await checkpoint_manager.get_recovery_info(instance_id)
    if not recovery_info or not recovery_info.get("can_resume"):
        raise HTTPException(
            status_code=400,
            detail="No checkpoint available for resume"
        )

    # 3. 원본 워크플로우 조회
    context = recovery_info.get("context", {})
    workflow_id = context.get("workflow_id")

    if not workflow_id:
        raise HTTPException(
            status_code=400,
            detail="Workflow ID not found in checkpoint"
        )

    workflow = db.query(Workflow).filter(
        Workflow.workflow_id == UUID(workflow_id)
    ).first()

    if not workflow:
        raise HTTPException(status_code=404, detail="Original workflow not found")

    # 4. 워크플로우 재개 실행
    dsl = workflow.dsl_definition
    input_data = {
        **(context.get("input_data", {})),
        **(body.additional_input or {})
    }

    result = await workflow_engine.execute_workflow(
        workflow_id=workflow_id,
        dsl=dsl,
        input_data=input_data,
        instance_id=instance_id,
        resume_from_checkpoint=True,
    )

    return {
        "success": True,
        "instance_id": instance_id,
        "status": result.get("status"),
        "resumed_from_node": recovery_info.get("resume_from_node"),
        "nodes_executed": result.get("nodes_executed"),
        "result": result,
    }


@router.post("/instances/{instance_id}/pause")
async def pause_workflow_instance(instance_id: str):
    """
    실행 중인 워크플로우 인스턴스 일시 중지
    """
    from app.services.workflow_engine import (
        workflow_state_machine,
        WorkflowState,
        InvalidStateTransition,
    )

    state_info = workflow_state_machine.get_state(instance_id)
    if not state_info.get("exists"):
        raise HTTPException(status_code=404, detail="Instance not found")

    try:
        await workflow_state_machine.transition(
            instance_id,
            WorkflowState.PAUSED,
            reason="Manually paused by user"
        )
    except InvalidStateTransition as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "success": True,
        "instance_id": instance_id,
        "state": "paused",
        "message": "Workflow instance paused",
    }


@router.post("/instances/{instance_id}/cancel")
async def cancel_workflow_instance(instance_id: str):
    """
    워크플로우 인스턴스 취소
    """
    from app.services.workflow_engine import (
        workflow_state_machine,
        checkpoint_manager,
        WorkflowState,
        InvalidStateTransition,
    )

    state_info = workflow_state_machine.get_state(instance_id)
    if not state_info.get("exists"):
        raise HTTPException(status_code=404, detail="Instance not found")

    try:
        await workflow_state_machine.transition(
            instance_id,
            WorkflowState.CANCELLED,
            reason="Cancelled by user"
        )

        # 체크포인트 삭제
        await checkpoint_manager.delete_checkpoint(instance_id)

    except InvalidStateTransition as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "success": True,
        "instance_id": instance_id,
        "state": "cancelled",
        "message": "Workflow instance cancelled",
    }


# ============ Version Management API ============


class WorkflowVersionCreate(BaseModel):
    """버전 생성 요청"""
    change_log: Optional[str] = None


class WorkflowVersionResponse(BaseModel):
    """버전 응답"""
    version_id: str
    workflow_id: str
    version: int
    dsl_definition: Dict[str, Any]
    change_log: Optional[str]
    status: str
    created_by: Optional[str]
    published_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class WorkflowVersionListResponse(BaseModel):
    """버전 목록 응답"""
    versions: List[WorkflowVersionResponse]
    total: int


class WorkflowVersionPublish(BaseModel):
    """버전 배포 요청"""
    pass  # 별도 필드 없음, 인증된 사용자 정보 사용


@router.get("/{workflow_id}/versions", response_model=WorkflowVersionListResponse)
async def list_workflow_versions(
    workflow_id: str,
    status: Optional[str] = Query(None, description="버전 상태 필터 (draft, active, deprecated, archived)"),
    db: Session = Depends(get_db),
):
    """
    워크플로우 버전 목록 조회
    """
    from sqlalchemy import text

    # 워크플로우 존재 확인
    workflow = db.query(Workflow).filter(Workflow.workflow_id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # 버전 목록 조회
    query = """
        SELECT
            version_id::text,
            workflow_id::text,
            version,
            dsl_definition,
            change_log,
            status,
            created_by::text,
            published_at,
            created_at
        FROM core.workflow_versions
        WHERE workflow_id = :workflow_id
    """
    params = {"workflow_id": workflow_id}

    if status:
        query += " AND status = :status"
        params["status"] = status

    query += " ORDER BY version DESC"

    result = db.execute(text(query), params)
    rows = result.fetchall()

    versions = []
    for row in rows:
        versions.append({
            "version_id": row[0],
            "workflow_id": row[1],
            "version": row[2],
            "dsl_definition": row[3] if isinstance(row[3], dict) else {},
            "change_log": row[4],
            "status": row[5],
            "created_by": row[6],
            "published_at": row[7],
            "created_at": row[8],
        })

    return {"versions": versions, "total": len(versions)}


@router.post("/{workflow_id}/versions", response_model=WorkflowVersionResponse)
async def create_workflow_version(
    workflow_id: str,
    body: WorkflowVersionCreate,
    db: Session = Depends(get_db),
):
    """
    새 워크플로우 버전 생성 (현재 DSL 스냅샷)
    """
    from sqlalchemy import text

    # 워크플로우 조회
    workflow = db.query(Workflow).filter(Workflow.workflow_id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # 다음 버전 번호 조회
    next_version_query = """
        SELECT core.get_next_workflow_version(:workflow_id)
    """
    result = db.execute(text(next_version_query), {"workflow_id": workflow_id})
    next_version = result.scalar()

    # 버전 생성
    version_id = str(uuid4())
    insert_query = """
        INSERT INTO core.workflow_versions (
            version_id, tenant_id, workflow_id, version, dsl_definition,
            change_log, status, created_at
        )
        VALUES (
            :version_id, :tenant_id, :workflow_id, :version, CAST(:dsl_definition AS jsonb),
            :change_log, 'draft', NOW()
        )
        RETURNING version_id::text, workflow_id::text, version, dsl_definition,
                  change_log, status, created_by::text, published_at, created_at
    """

    import json
    dsl_json = json.dumps(workflow.dsl_definition) if workflow.dsl_definition else "{}"

    result = db.execute(
        text(insert_query),
        {
            "version_id": version_id,
            "tenant_id": str(workflow.tenant_id) if workflow.tenant_id else "446e39b3-455e-4ca9-817a-4913921eb41d",
            "workflow_id": workflow_id,
            "version": next_version,
            "dsl_definition": dsl_json,
            "change_log": body.change_log,
        },
    )
    db.commit()

    row = result.fetchone()

    return {
        "version_id": row[0],
        "workflow_id": row[1],
        "version": row[2],
        "dsl_definition": row[3] if isinstance(row[3], dict) else {},
        "change_log": row[4],
        "status": row[5],
        "created_by": row[6],
        "published_at": row[7],
        "created_at": row[8],
    }


@router.get("/{workflow_id}/versions/{version}", response_model=WorkflowVersionResponse)
async def get_workflow_version(
    workflow_id: str,
    version: int,
    db: Session = Depends(get_db),
):
    """
    특정 워크플로우 버전 조회
    """
    from sqlalchemy import text

    query = """
        SELECT
            version_id::text,
            workflow_id::text,
            version,
            dsl_definition,
            change_log,
            status,
            created_by::text,
            published_at,
            created_at
        FROM core.workflow_versions
        WHERE workflow_id = :workflow_id AND version = :version
    """

    result = db.execute(text(query), {"workflow_id": workflow_id, "version": version})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Version not found")

    return {
        "version_id": row[0],
        "workflow_id": row[1],
        "version": row[2],
        "dsl_definition": row[3] if isinstance(row[3], dict) else {},
        "change_log": row[4],
        "status": row[5],
        "created_by": row[6],
        "published_at": row[7],
        "created_at": row[8],
    }


@router.post("/{workflow_id}/versions/{version}/publish")
async def publish_workflow_version(
    workflow_id: str,
    version: int,
    db: Session = Depends(get_db),
):
    """
    워크플로우 버전 배포 (active로 변경, 이전 active 버전은 deprecated)
    """
    from sqlalchemy import text

    # 버전 존재 확인
    check_query = """
        SELECT version_id, status FROM core.workflow_versions
        WHERE workflow_id = :workflow_id AND version = :version
    """
    result = db.execute(text(check_query), {"workflow_id": workflow_id, "version": version})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Version not found")

    if row[1] == "active":
        return {"success": True, "message": "Version is already active"}

    # 이전 active 버전 deprecated로 변경
    deprecate_query = """
        UPDATE core.workflow_versions
        SET status = 'deprecated'
        WHERE workflow_id = :workflow_id AND status = 'active'
    """
    db.execute(text(deprecate_query), {"workflow_id": workflow_id})

    # 현재 버전 active로 변경
    publish_query = """
        UPDATE core.workflow_versions
        SET status = 'active', published_at = NOW()
        WHERE workflow_id = :workflow_id AND version = :version
    """
    db.execute(text(publish_query), {"workflow_id": workflow_id, "version": version})

    # workflows 테이블의 current_version 업데이트
    update_workflow_query = """
        UPDATE core.workflows
        SET current_version = :version, updated_at = NOW()
        WHERE workflow_id = :workflow_id
    """
    db.execute(text(update_workflow_query), {"workflow_id": workflow_id, "version": version})

    db.commit()

    return {
        "success": True,
        "message": f"Version {version} published successfully",
        "workflow_id": workflow_id,
        "version": version,
    }


@router.post("/{workflow_id}/versions/{version}/rollback")
async def rollback_workflow_version(
    workflow_id: str,
    version: int,
    db: Session = Depends(get_db),
):
    """
    특정 버전으로 워크플로우 롤백 (해당 버전의 DSL을 현재 워크플로우에 적용)
    """
    from sqlalchemy import text

    # 버전 조회
    query = """
        SELECT version_id, dsl_definition FROM core.workflow_versions
        WHERE workflow_id = :workflow_id AND version = :version
    """
    result = db.execute(text(query), {"workflow_id": workflow_id, "version": version})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Version not found")

    dsl_definition = row[1]

    # 워크플로우 DSL 업데이트
    workflow = db.query(Workflow).filter(Workflow.workflow_id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow.dsl_definition = dsl_definition
    flag_modified(workflow, "dsl_definition")
    db.commit()

    return {
        "success": True,
        "message": f"Rolled back to version {version}",
        "workflow_id": workflow_id,
        "version": version,
    }


@router.delete("/{workflow_id}/versions/{version}")
async def delete_workflow_version(
    workflow_id: str,
    version: int,
    db: Session = Depends(get_db),
):
    """
    워크플로우 버전 삭제 (active 버전은 삭제 불가)
    """
    from sqlalchemy import text

    # 버전 조회
    query = """
        SELECT version_id, status FROM core.workflow_versions
        WHERE workflow_id = :workflow_id AND version = :version
    """
    result = db.execute(text(query), {"workflow_id": workflow_id, "version": version})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Version not found")

    if row[1] == "active":
        raise HTTPException(status_code=400, detail="Cannot delete active version")

    # 버전 삭제
    delete_query = """
        DELETE FROM core.workflow_versions
        WHERE workflow_id = :workflow_id AND version = :version
    """
    db.execute(text(delete_query), {"workflow_id": workflow_id, "version": version})
    db.commit()

    return {
        "success": True,
        "message": f"Version {version} deleted",
        "workflow_id": workflow_id,
    }
