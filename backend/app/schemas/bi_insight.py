"""
BI Insight Pydantic Schemas
AWS QuickSight GenBI Executive Summary 기능 구현용

v2: 고품질 인사이트 지원
- TableData: 표 형태 데이터
- AutoAnalysis: 자동 연관 분석 결과
- InsightChart: 차트 설정 (threshold_lines, annotations)
- ComparisonData: 전일/전주 대비 비교
"""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field


# =====================================================
# 고품질 인사이트 신규 스키마
# =====================================================

class TableData(BaseModel):
    """표 형태 데이터"""

    headers: List[str] = Field(..., description="테이블 헤더")
    rows: List[List[Any]] = Field(..., description="테이블 행 데이터")
    highlight_rules: Optional[Dict[str, str]] = Field(
        None, description="하이라이트 규칙 (예: {'달성률 < 80': 'critical'})"
    )


class ThresholdLine(BaseModel):
    """차트 기준선"""

    value: float = Field(..., description="기준값")
    label: str = Field(..., description="라벨 (예: '목표', '경고')")
    color: Optional[str] = Field(None, description="색상 (예: '#10b981')")


class ChartAnnotation(BaseModel):
    """차트 주석"""

    x: Union[str, float] = Field(..., description="X 좌표 (날짜 또는 값)")
    y: Optional[float] = Field(None, description="Y 좌표")
    text: str = Field(..., description="주석 텍스트")


class InsightChart(BaseModel):
    """인사이트 차트 설정"""

    chart_type: Literal["bar", "line", "pie", "area", "scatter"] = Field(
        ..., description="차트 유형"
    )
    title: str = Field(..., description="차트 제목")
    data: List[Dict[str, Any]] = Field(..., description="차트 데이터")
    x_key: Optional[str] = Field("name", description="X축 키")
    y_key: Optional[str] = Field("value", description="Y축 키")
    threshold_lines: Optional[List[ThresholdLine]] = Field(
        None, description="기준선 목록"
    )
    annotations: Optional[List[ChartAnnotation]] = Field(None, description="주석 목록")


class AnalysisTrigger(BaseModel):
    """분석 트리거 정보"""

    type: str = Field(..., description="트리거 유형 (low_achievement, high_defect 등)")
    line_code: str = Field(..., description="영향받는 라인")
    value: float = Field(..., description="실제 값")
    threshold: float = Field(..., description="기준값")
    message: Optional[str] = Field(None, description="트리거 메시지")


class DowntimeCause(BaseModel):
    """비가동 원인"""

    reason: str = Field(..., description="비가동 사유")
    duration_min: float = Field(..., description="비가동 시간 (분)")
    percentage: float = Field(..., description="비율 (%)")
    equipment_code: Optional[str] = Field(None, description="설비 코드")


class DefectCause(BaseModel):
    """불량 원인"""

    defect_type: str = Field(..., description="불량 유형")
    qty: int = Field(..., description="불량 수량")
    percentage: float = Field(..., description="비율 (%)")
    root_causes: Optional[List[str]] = Field(None, description="근본 원인")


class AutoAnalysis(BaseModel):
    """자동 연관 분석 결과"""

    has_issues: bool = Field(..., description="이상 징후 존재 여부")
    triggers: Optional[List[AnalysisTrigger]] = Field(None, description="감지된 트리거")
    downtime_causes: Optional[List[DowntimeCause]] = Field(None, description="비가동 원인")
    defect_causes: Optional[List[DefectCause]] = Field(None, description="불량 원인")
    summary: Optional[str] = Field(None, description="분석 요약")


class ComparisonData(BaseModel):
    """전일/전주 대비 비교 데이터"""

    vs_yesterday: Optional[Dict[str, Any]] = Field(None, description="전일 대비")
    vs_last_week: Optional[Dict[str, Any]] = Field(None, description="전주 대비")


# =====================================================
# 기존 스키마 (확장)
# =====================================================

class InsightFact(BaseModel):
    """데이터에서 확인되는 객관적 사실"""

    metric_name: str = Field(..., description="메트릭 이름 (예: 평균 온도, 생산량)")
    current_value: float = Field(..., description="현재 값")
    previous_value: Optional[float] = Field(None, description="이전 기간 값 (비교용)")
    change_percent: Optional[float] = Field(None, description="변화율 (%)")
    trend: Literal["up", "down", "stable", "neutral"] = Field(..., description="추세 방향")
    period: str = Field(..., description="측정 기간 (예: '최근 24시간', '이번 주')")
    unit: Optional[str] = Field(None, description="단위 (예: °C, bar, %)")
    status: Optional[Literal["normal", "warning", "critical"]] = Field(
        None, description="상태 (normal/warning/critical)"
    )


class InsightReasoning(BaseModel):
    """분석 및 원인 추론"""

    analysis: str = Field(..., description="분석 내용 (왜 이런 결과가 나왔는지)")
    contributing_factors: List[str] = Field(
        default_factory=list, description="기여 요인 목록"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="분석 신뢰도 (0.0 ~ 1.0)"
    )
    data_quality_notes: Optional[str] = Field(
        None, description="데이터 품질 관련 참고사항"
    )


class InsightAction(BaseModel):
    """권장 조치"""

    priority: Literal["high", "medium", "low"] = Field(..., description="우선순위")
    action: str = Field(..., description="권장 조치 내용")
    expected_impact: Optional[str] = Field(None, description="예상 효과")
    responsible_team: Optional[str] = Field(None, description="담당 팀/부서")
    deadline_suggestion: Optional[str] = Field(None, description="권장 완료 시점")


class AIInsight(BaseModel):
    """AI 생성 인사이트 (Executive Summary) - v2 확장"""

    insight_id: UUID = Field(..., description="인사이트 ID")
    tenant_id: UUID = Field(..., description="테넌트 ID")
    source_type: Literal["chart", "dashboard", "dataset", "chat"] = Field(
        ..., description="인사이트 소스 타입"
    )
    source_id: Optional[UUID] = Field(None, description="소스 ID (차트/대시보드 ID)")
    title: str = Field(..., description="인사이트 제목")
    summary: str = Field(..., description="요약 (1-2문장)")

    # v2: 전체 상태
    status: Optional[Literal["normal", "warning", "critical"]] = Field(
        None, description="전체 상태"
    )

    # v2: 표 형태 데이터
    table_data: Optional[TableData] = Field(None, description="표 형태 데이터")

    facts: List[InsightFact] = Field(
        default_factory=list, description="객관적 사실 목록"
    )

    # v2: 자동 연관 분석
    auto_analysis: Optional[AutoAnalysis] = Field(None, description="자동 연관 분석 결과")

    reasoning: InsightReasoning = Field(..., description="분석 및 추론")
    actions: List[InsightAction] = Field(
        default_factory=list, description="권장 조치 목록"
    )

    # v2: 전일/전주 비교
    comparison: Optional[ComparisonData] = Field(None, description="전일/전주 대비 비교")

    # v2: 차트 설정 (threshold_lines 포함)
    charts: Optional[List[InsightChart]] = Field(None, description="차트 목록")

    model_used: str = Field(
        default="claude-sonnet-4-5-20250929", description="사용된 AI 모델"
    )
    feedback_score: Optional[float] = Field(
        None, ge=-1.0, le=1.0, description="사용자 피드백 점수 (-1: 부정, 0: 중립, 1: 긍정)"
    )
    generated_at: datetime = Field(..., description="생성 시각")

    class Config:
        from_attributes = True


class InsightRequest(BaseModel):
    """인사이트 생성 요청"""

    source_type: Literal["chart", "dashboard", "dataset"] = Field(
        ..., description="인사이트 소스 타입"
    )
    source_id: Optional[UUID] = Field(None, description="소스 ID")
    source_data: Optional[Dict[str, Any]] = Field(
        None, description="직접 전달하는 소스 데이터 (chart_config 또는 raw data)"
    )
    focus_metrics: Optional[List[str]] = Field(
        None, description="집중 분석할 메트릭 이름 목록"
    )
    time_range: Optional[str] = Field(
        None, description="분석 대상 기간 (예: '24h', '7d', '30d')"
    )
    comparison_period: Optional[str] = Field(
        None, description="비교 기간 (예: 'previous_period', 'same_period_last_year')"
    )


class InsightResponse(BaseModel):
    """인사이트 생성 응답"""

    insight: AIInsight = Field(..., description="생성된 인사이트")
    processing_time_ms: int = Field(..., description="처리 시간 (밀리초)")


class InsightListResponse(BaseModel):
    """인사이트 목록 응답"""

    insights: List[AIInsight] = Field(..., description="인사이트 목록")
    total: int = Field(..., description="전체 개수")
    page: int = Field(default=1, description="현재 페이지")
    page_size: int = Field(default=20, description="페이지 크기")


class InsightFeedbackRequest(BaseModel):
    """인사이트 피드백 요청"""

    score: Literal[-1, 0, 1] = Field(..., description="피드백 점수 (-1: 부정, 0: 중립, 1: 긍정)")
    comment: Optional[str] = Field(None, description="추가 코멘트")
