"""
Audit Log 관련 Pydantic 스키마
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field


class AuditLogResponse(BaseModel):
    """감사 로그 응답"""
    log_id: str = Field(..., description="로그 ID")
    user_id: Optional[str] = Field(None, description="사용자 ID")
    tenant_id: Optional[str] = Field(None, description="테넌트 ID")
    action: str = Field(..., description="액션 (create, read, update, delete 등)")
    resource: str = Field(..., description="리소스 타입")
    resource_id: Optional[str] = Field(None, description="리소스 ID")
    method: str = Field(..., description="HTTP 메서드")
    path: str = Field(..., description="API 경로")
    status_code: int = Field(..., description="HTTP 상태 코드")
    ip_address: Optional[str] = Field(None, description="클라이언트 IP")
    user_agent: Optional[str] = Field(None, description="User-Agent")
    request_body: Optional[Dict[str, Any]] = Field(None, description="요청 본문 (마스킹됨)")
    response_summary: Optional[str] = Field(None, description="응답 요약")
    duration_ms: Optional[int] = Field(None, description="처리 시간 (ms)")
    created_at: Optional[str] = Field(None, description="생성 일시")


class AuditLogListResponse(BaseModel):
    """감사 로그 목록 응답"""
    items: List[AuditLogResponse] = Field(..., description="로그 목록")
    total: int = Field(..., description="전체 개수")
    limit: int = Field(..., description="조회 개수")
    offset: int = Field(..., description="시작 위치")


class AuditStatsResponse(BaseModel):
    """감사 로그 통계 응답"""
    total: int = Field(..., description="전체 로그 수")
    by_resource: Dict[str, int] = Field(..., description="리소스별 로그 수")
    by_action: Dict[str, int] = Field(..., description="액션별 로그 수")
    by_status: Dict[str, int] = Field(..., description="상태별 로그 수")


class AuditLogFilter(BaseModel):
    """감사 로그 필터"""
    user_id: Optional[UUID] = Field(None, description="사용자 ID 필터")
    resource: Optional[str] = Field(None, description="리소스 타입 필터")
    action: Optional[str] = Field(None, description="액션 필터")
    status_code: Optional[int] = Field(None, description="HTTP 상태 코드 필터")
    start_date: Optional[datetime] = Field(None, description="시작 일시")
    end_date: Optional[datetime] = Field(None, description="종료 일시")
