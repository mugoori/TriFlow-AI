"""
Audit Log API 라우터
감사 로그 조회 (관리자 전용)
"""
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.auth.dependencies import get_current_user
from app.services.rbac_service import require_admin, check_permission
from app.services.audit_service import get_audit_logs, get_audit_stats
from app.schemas.audit import (
    AuditLogResponse,
    AuditLogListResponse,
    AuditStatsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    user_id: Optional[UUID] = Query(None, description="사용자 ID 필터"),
    resource: Optional[str] = Query(None, description="리소스 타입 필터"),
    action: Optional[str] = Query(None, description="액션 필터"),
    status_code: Optional[int] = Query(None, description="HTTP 상태 코드 필터"),
    start_date: Optional[datetime] = Query(None, description="시작 일시"),
    end_date: Optional[datetime] = Query(None, description="종료 일시"),
    limit: int = Query(100, ge=1, le=500, description="조회 개수"),
    offset: int = Query(0, ge=0, description="시작 위치"),
    _: None = Depends(check_permission("audit", "read")),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    감사 로그 목록 조회 (관리자 전용)

    - 모든 API 호출 기록 조회
    - 필터링 지원 (사용자, 리소스, 액션, 상태 코드, 날짜 범위)
    """
    logs = await get_audit_logs(
        db=db,
        user_id=user_id,
        tenant_id=current_user.tenant_id,  # 테넌트 격리
        resource=resource,
        action=action,
        status_code=status_code,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )

    return AuditLogListResponse(
        items=[AuditLogResponse(**log) for log in logs],
        total=len(logs),  # TODO: 실제 total count 쿼리 추가
        limit=limit,
        offset=offset,
    )


@router.get("/stats", response_model=AuditStatsResponse)
async def get_audit_statistics(
    start_date: Optional[datetime] = Query(None, description="시작 일시"),
    end_date: Optional[datetime] = Query(None, description="종료 일시"),
    _: None = Depends(check_permission("audit", "read")),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    감사 로그 통계 조회 (관리자 전용)

    - 리소스별, 액션별, 상태 코드별 통계
    - 날짜 범위 필터링 지원
    """
    stats = await get_audit_stats(
        db=db,
        tenant_id=current_user.tenant_id,
        start_date=start_date,
        end_date=end_date,
    )

    return AuditStatsResponse(**stats)


@router.get("/my", response_model=AuditLogListResponse)
async def list_my_audit_logs(
    resource: Optional[str] = Query(None, description="리소스 타입 필터"),
    action: Optional[str] = Query(None, description="액션 필터"),
    limit: int = Query(50, ge=1, le=200, description="조회 개수"),
    offset: int = Query(0, ge=0, description="시작 위치"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    내 감사 로그 조회

    - 현재 사용자의 API 호출 기록만 조회
    - 모든 인증된 사용자 접근 가능
    """
    logs = await get_audit_logs(
        db=db,
        user_id=current_user.user_id,
        resource=resource,
        action=action,
        limit=limit,
        offset=offset,
    )

    return AuditLogListResponse(
        items=[AuditLogResponse(**log) for log in logs],
        total=len(logs),
        limit=limit,
        offset=offset,
    )
