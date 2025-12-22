"""
BI Story Pydantic Schemas
AWS QuickSight GenBI Data Stories 기능 구현용
"""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class StorySectionChart(BaseModel):
    """스토리 섹션 내 차트"""

    chart_config: Dict[str, Any] = Field(..., description="ChartConfig JSON")
    caption: Optional[str] = Field(None, description="차트 캡션/설명")
    order: int = Field(default=0, description="섹션 내 차트 순서")


class StorySection(BaseModel):
    """스토리 섹션"""

    section_id: UUID = Field(..., description="섹션 ID")
    section_type: Literal["introduction", "analysis", "finding", "conclusion"] = Field(
        ..., description="섹션 타입"
    )
    order: int = Field(..., description="섹션 순서")
    title: str = Field(..., description="섹션 제목")
    narrative: str = Field(..., description="내러티브 텍스트 (Markdown)")
    charts: List[StorySectionChart] = Field(
        default_factory=list, description="섹션 내 차트 목록"
    )
    ai_generated: bool = Field(default=True, description="AI 자동 생성 여부")
    created_at: datetime = Field(..., description="생성 시각")

    class Config:
        from_attributes = True


class DataStory(BaseModel):
    """데이터 스토리 (내러티브 보고서)"""

    story_id: UUID = Field(..., description="스토리 ID")
    tenant_id: UUID = Field(..., description="테넌트 ID")
    title: str = Field(..., description="스토리 제목")
    description: Optional[str] = Field(None, description="스토리 설명")
    sections: List[StorySection] = Field(
        default_factory=list, description="섹션 목록"
    )
    is_public: bool = Field(default=False, description="공개 여부")
    created_by: UUID = Field(..., description="작성자 ID")
    created_at: datetime = Field(..., description="생성 시각")
    updated_at: datetime = Field(..., description="수정 시각")
    published_at: Optional[datetime] = Field(None, description="발행 시각")

    class Config:
        from_attributes = True


class StoryCreateRequest(BaseModel):
    """스토리 생성 요청"""

    title: str = Field(..., min_length=1, max_length=200, description="스토리 제목")
    description: Optional[str] = Field(None, description="스토리 설명")
    auto_generate: bool = Field(
        default=True, description="AI 자동 생성 여부 (False면 빈 스토리 생성)"
    )
    source_dashboard_id: Optional[UUID] = Field(
        None, description="소스 대시보드 ID (차트 가져오기용)"
    )
    source_chart_ids: Optional[List[UUID]] = Field(
        None, description="포함할 차트 ID 목록"
    )
    focus_topic: Optional[str] = Field(
        None, description="집중 주제 (예: '생산 효율', '품질 분석')"
    )
    time_range: Optional[str] = Field(
        None, description="분석 대상 기간"
    )


class StoryUpdateRequest(BaseModel):
    """스토리 수정 요청"""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    is_public: Optional[bool] = None


class StorySectionCreateRequest(BaseModel):
    """섹션 추가 요청"""

    section_type: Literal["introduction", "analysis", "finding", "conclusion"]
    title: str = Field(..., min_length=1, max_length=255)
    narrative: str = Field(..., description="Markdown 내용")
    charts: Optional[List[StorySectionChart]] = None
    order: Optional[int] = Field(None, description="삽입 위치 (None이면 끝에 추가)")


class StorySectionUpdateRequest(BaseModel):
    """섹션 수정 요청"""

    title: Optional[str] = None
    narrative: Optional[str] = None
    charts: Optional[List[StorySectionChart]] = None
    order: Optional[int] = None


class StoryListResponse(BaseModel):
    """스토리 목록 응답"""

    stories: List[DataStory] = Field(..., description="스토리 목록")
    total: int = Field(..., description="전체 개수")
    page: int = Field(default=1)
    page_size: int = Field(default=20)


class ChartRefineRequest(BaseModel):
    """차트 수정 요청 (Refinement Loop)"""

    original_chart_config: Dict[str, Any] = Field(
        ..., description="원본 ChartConfig JSON"
    )
    refinement_instruction: str = Field(
        ..., description="수정 지시 (예: '막대 차트로 바꿔줘', '제목을 월별 생산량으로 변경')"
    )
    preserve_data: bool = Field(
        default=True, description="데이터 유지 여부 (False면 새로운 쿼리 실행)"
    )


class ChartRefineResponse(BaseModel):
    """차트 수정 응답"""

    refined_chart_config: Dict[str, Any] = Field(..., description="수정된 ChartConfig")
    changes_made: List[str] = Field(..., description="적용된 변경 사항 목록")
    processing_time_ms: int = Field(..., description="처리 시간 (밀리초)")
