"""
StatCard Pydantic Schemas
대시보드 StatCard 설정 및 데이터 스키마

데이터 소스 유형:
- kpi: bi.dim_kpi에서 정의된 KPI
- db_query: 사용자 정의 테이블/컬럼 쿼리
- mcp_tool: MCP 도구를 통한 외부 시스템 연동
"""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# =====================================================
# 공통 타입
# =====================================================

SourceType = Literal["kpi", "db_query", "mcp_tool"]
AggregationType = Literal["sum", "avg", "min", "max", "count", "last"]
StatusType = Literal["green", "yellow", "red", "gray"]


# =====================================================
# StatCard 설정 스키마
# =====================================================

class StatCardConfigBase(BaseModel):
    """StatCard 설정 기본 필드"""

    display_order: int = Field(default=0, description="표시 순서")
    is_visible: bool = Field(default=True, description="표시 여부")

    source_type: SourceType = Field(..., description="데이터 소스 유형")

    # KPI 소스 (source_type = 'kpi')
    kpi_code: Optional[str] = Field(None, description="KPI 코드 (bi.dim_kpi)")

    # DB Query 소스 (source_type = 'db_query')
    table_name: Optional[str] = Field(None, description="테이블명")
    column_name: Optional[str] = Field(None, description="컬럼명")
    aggregation: Optional[AggregationType] = Field(None, description="집계 함수")
    filter_condition: Optional[Dict[str, Any]] = Field(None, description="필터 조건")

    # MCP Tool 소스 (source_type = 'mcp_tool')
    mcp_server_id: Optional[UUID] = Field(None, description="MCP 서버 ID")
    mcp_tool_name: Optional[str] = Field(None, description="MCP 도구명")
    mcp_params: Optional[Dict[str, Any]] = Field(None, description="MCP 호출 파라미터")
    mcp_result_key: Optional[str] = Field(None, description="응답에서 값 추출 경로")

    # 표시 설정 (커스텀 오버라이드)
    custom_title: Optional[str] = Field(None, description="커스텀 제목")
    custom_icon: Optional[str] = Field(None, description="커스텀 아이콘 (Lucide 아이콘명)")
    custom_unit: Optional[str] = Field(None, description="커스텀 단위")

    # 임계값 (DB Query, MCP용 - KPI는 dim_kpi에서 가져옴)
    green_threshold: Optional[float] = Field(None, description="정상 임계값")
    yellow_threshold: Optional[float] = Field(None, description="주의 임계값")
    red_threshold: Optional[float] = Field(None, description="위험 임계값")
    higher_is_better: bool = Field(default=True, description="높을수록 좋은지 여부")

    # 캐시 설정
    cache_ttl_seconds: int = Field(default=60, description="캐시 TTL (초)")

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, v: str, info) -> str:
        values = info.data
        if v == "kpi" and not values.get("kpi_code"):
            # 나중에 검증 (create 시점에 체크)
            pass
        return v


class StatCardConfigCreate(StatCardConfigBase):
    """StatCard 생성 요청"""
    pass


class StatCardConfigUpdate(BaseModel):
    """StatCard 수정 요청"""

    display_order: Optional[int] = None
    is_visible: Optional[bool] = None

    source_type: Optional[SourceType] = None
    kpi_code: Optional[str] = None

    table_name: Optional[str] = None
    column_name: Optional[str] = None
    aggregation: Optional[AggregationType] = None
    filter_condition: Optional[Dict[str, Any]] = None

    mcp_server_id: Optional[UUID] = None
    mcp_tool_name: Optional[str] = None
    mcp_params: Optional[Dict[str, Any]] = None
    mcp_result_key: Optional[str] = None

    custom_title: Optional[str] = None
    custom_icon: Optional[str] = None
    custom_unit: Optional[str] = None

    green_threshold: Optional[float] = None
    yellow_threshold: Optional[float] = None
    red_threshold: Optional[float] = None
    higher_is_better: Optional[bool] = None

    cache_ttl_seconds: Optional[int] = None


class StatCardConfig(StatCardConfigBase):
    """StatCard 설정 응답 (DB에서 조회)"""

    config_id: UUID = Field(..., description="설정 ID")
    tenant_id: UUID = Field(..., description="테넌트 ID")
    user_id: UUID = Field(..., description="사용자 ID")
    created_at: datetime = Field(..., description="생성 시각")
    updated_at: datetime = Field(..., description="수정 시각")

    class Config:
        from_attributes = True


# =====================================================
# StatCard 값 스키마
# =====================================================

class StatCardValue(BaseModel):
    """StatCard 현재 값"""

    config_id: UUID = Field(..., description="설정 ID")
    value: Optional[float] = Field(None, description="현재 값")
    formatted_value: Optional[str] = Field(None, description="포맷된 값 (예: '2.3%')")
    previous_value: Optional[float] = Field(None, description="이전 값 (비교용)")
    change_percent: Optional[float] = Field(None, description="변화율 (%)")
    trend: Optional[Literal["up", "down", "stable"]] = Field(None, description="추세")
    status: StatusType = Field(default="gray", description="상태 색상")

    # 메타데이터
    title: str = Field(..., description="제목")
    icon: str = Field(default="BarChart3", description="아이콘")
    unit: Optional[str] = Field(None, description="단위")

    # 집계 기간 정보
    period_start: Optional[datetime] = Field(None, description="집계 시작일")
    period_end: Optional[datetime] = Field(None, description="집계 종료일")
    period_label: Optional[str] = Field(None, description="기간 라벨 (예: '최근 7일')")
    comparison_label: Optional[str] = Field(None, description="비교 기준 라벨 (예: 'vs 전주')")

    # 출처 정보
    source_type: SourceType = Field(..., description="데이터 소스 유형")
    fetched_at: datetime = Field(..., description="데이터 조회 시각")
    is_cached: bool = Field(default=False, description="캐시된 값 여부")


class StatCardWithValue(BaseModel):
    """StatCard 설정 + 현재 값"""

    config: StatCardConfig = Field(..., description="설정")
    value: StatCardValue = Field(..., description="현재 값")


# =====================================================
# 목록 조회 응답
# =====================================================

class StatCardListResponse(BaseModel):
    """StatCard 목록 응답"""

    cards: List[StatCardWithValue] = Field(..., description="StatCard 목록")
    total: int = Field(..., description="전체 개수")


class StatCardReorderRequest(BaseModel):
    """StatCard 순서 변경 요청"""

    card_ids: List[UUID] = Field(..., description="순서대로 정렬된 카드 ID 목록")


# =====================================================
# KPI 목록 조회
# =====================================================

class KpiInfo(BaseModel):
    """KPI 정보"""

    kpi_code: str = Field(..., description="KPI 코드")
    name: str = Field(..., description="KPI 이름")
    name_en: Optional[str] = Field(None, description="KPI 영문명")
    category: str = Field(..., description="카테고리")
    unit: Optional[str] = Field(None, description="단위")
    description: Optional[str] = Field(None, description="설명")
    higher_is_better: bool = Field(default=True, description="높을수록 좋음")
    default_target: Optional[float] = Field(None, description="기본 목표값")
    green_threshold: Optional[float] = Field(None, description="정상 임계값")
    yellow_threshold: Optional[float] = Field(None, description="주의 임계값")
    red_threshold: Optional[float] = Field(None, description="위험 임계값")


class KpiListResponse(BaseModel):
    """KPI 목록 응답"""

    kpis: List[KpiInfo] = Field(..., description="KPI 목록")
    categories: List[str] = Field(..., description="카테고리 목록")


# =====================================================
# 사용 가능한 테이블/컬럼 조회
# =====================================================

class ColumnInfo(BaseModel):
    """컬럼 정보"""

    column_name: str = Field(..., description="컬럼명")
    data_type: str = Field(..., description="데이터 타입")
    description: Optional[str] = Field(None, description="설명")
    allowed_aggregations: List[AggregationType] = Field(..., description="허용된 집계 함수")


class TableInfo(BaseModel):
    """테이블 정보"""

    schema_name: str = Field(..., description="스키마명")
    table_name: str = Field(..., description="테이블명")
    columns: List[ColumnInfo] = Field(..., description="컬럼 목록")


class AvailableTablesResponse(BaseModel):
    """사용 가능한 테이블 목록 응답"""

    tables: List[TableInfo] = Field(..., description="테이블 목록")


# =====================================================
# MCP 도구 목록 조회
# =====================================================

class McpToolInfo(BaseModel):
    """MCP 도구 정보"""

    server_id: UUID = Field(..., description="서버 ID")
    server_name: str = Field(..., description="서버 이름")
    tool_name: str = Field(..., description="도구 이름")
    description: Optional[str] = Field(None, description="설명")
    input_schema: Optional[Dict[str, Any]] = Field(None, description="입력 스키마")


class McpToolListResponse(BaseModel):
    """MCP 도구 목록 응답"""

    tools: List[McpToolInfo] = Field(..., description="도구 목록")
