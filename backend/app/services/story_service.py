"""
TriFlow AI - Story Service
===========================
AWS QuickSight GenBI Data Stories 기능 구현

핵심 기능:
- 데이터 스토리 생성 (자동/수동)
- LLM 기반 내러티브 생성
- 섹션 관리
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from anthropic import Anthropic
from sqlalchemy import text

from app.config import settings
from app.database import get_db_context
from app.schemas.bi_story import (
    DataStory,
    StoryCreateRequest,
    StorySection,
    StorySectionChart,
    StorySectionCreateRequest,
)

logger = logging.getLogger(__name__)


STORY_SYSTEM_PROMPT = """당신은 제조 데이터 분석 보고서 작성 전문가입니다.
주어진 데이터와 차트를 기반으로 Data Story를 작성합니다.

## 스토리 구조
1. **Introduction**: 보고서 목적과 범위 소개
2. **Analysis**: 핵심 데이터 분석 (차트 설명 포함)
3. **Finding**: 주요 발견 사항
4. **Conclusion**: 결론 및 권장 사항

## 출력 형식
반드시 다음 JSON 형식으로 출력하세요:

```json
{
  "sections": [
    {
      "section_type": "introduction",
      "title": "섹션 제목",
      "narrative": "Markdown 형식의 내러티브 텍스트"
    },
    {
      "section_type": "analysis",
      "title": "데이터 분석",
      "narrative": "차트와 함께 데이터 분석 내용"
    },
    {
      "section_type": "finding",
      "title": "주요 발견",
      "narrative": "핵심 인사이트 및 발견 사항"
    },
    {
      "section_type": "conclusion",
      "title": "결론",
      "narrative": "요약 및 권장 조치"
    }
  ]
}
```

## 작성 원칙
1. **명확성**: 기술 용어는 풀어서 설명
2. **간결성**: 핵심 내용만 전달
3. **실행 가능성**: 구체적인 권장 사항 포함
4. **데이터 기반**: 모든 주장은 데이터로 뒷받침

## Markdown 스타일
- 제목: ## 사용
- 강조: **텍스트**
- 목록: - 또는 1. 2. 3.
- 인용: > 사용
"""


class StoryService:
    """
    데이터 스토리 서비스

    주요 기능:
    - create_story(): 스토리 생성 (자동 생성 옵션)
    - get_stories(): 스토리 목록 조회
    - update_story(): 스토리 수정
    - delete_story(): 스토리 삭제
    - add_section(): 섹션 추가
    - update_section(): 섹션 수정
    - delete_section(): 섹션 삭제
    """

    def __init__(self):
        self.client = Anthropic(api_key=settings.anthropic_api_key)

    def get_model(self, tenant_id: UUID = None) -> str:
        """테넌트별 모델 설정 조회"""
        from app.services.settings_service import settings_service
        model = settings_service.get_setting_with_scope(
            "default_llm_model",
            tenant_id=str(tenant_id) if tenant_id else None
        )
        return model or settings.default_llm_model or "claude-sonnet-4-5-20250929"

    async def create_story(
        self,
        tenant_id: UUID,
        user_id: UUID,
        request: StoryCreateRequest,
    ) -> DataStory:
        """
        데이터 스토리 생성

        Args:
            tenant_id: 테넌트 ID
            user_id: 작성자 ID
            request: 스토리 생성 요청

        Returns:
            생성된 DataStory
        """
        story_id = uuid4()
        now = datetime.utcnow()

        # 스토리 메타데이터 저장
        with get_db_context() as db:
            db.execute(
                text("""
                    INSERT INTO bi.data_stories (
                        story_id, tenant_id, title, description,
                        is_public, created_by, created_at, updated_at
                    ) VALUES (
                        :story_id, :tenant_id, :title, :description,
                        FALSE, :created_by, :created_at, :updated_at
                    )
                """),
                {
                    "story_id": str(story_id),
                    "tenant_id": str(tenant_id),
                    "title": request.title,
                    "description": request.description,
                    "created_by": str(user_id),
                    "created_at": now,
                    "updated_at": now,
                }
            )
            db.commit()

        sections: List[StorySection] = []

        # 자동 생성 요청인 경우
        if request.auto_generate:
            sections = await self._generate_story_sections(
                tenant_id=tenant_id,
                story_id=story_id,
                focus_topic=request.focus_topic,
                time_range=request.time_range,
                source_chart_ids=request.source_chart_ids,
            )

        return DataStory(
            story_id=story_id,
            tenant_id=tenant_id,
            title=request.title,
            description=request.description,
            sections=sections,
            is_public=False,
            created_by=user_id,
            created_at=now,
            updated_at=now,
            published_at=None,
        )

    async def _generate_story_sections(
        self,
        tenant_id: UUID,
        story_id: UUID,
        focus_topic: Optional[str],
        time_range: Optional[str],
        source_chart_ids: Optional[List[UUID]],
    ) -> List[StorySection]:
        """LLM으로 스토리 섹션 자동 생성"""

        # 데이터 수집
        data_context = await self._collect_story_data(
            tenant_id, focus_topic, time_range, source_chart_ids
        )

        # LLM 호출
        user_message = self._build_story_prompt(data_context, focus_topic)

        response = self.client.messages.create(
            model=self.get_model(tenant_id),  # 테넌트별 동적 모델 조회
            max_tokens=4096,
            system=STORY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text

        # 응답 파싱
        parsed = self._parse_story_response(content)

        # 섹션 저장
        sections = []
        now = datetime.utcnow()

        for i, sec_data in enumerate(parsed.get("sections", [])):
            section_id = uuid4()

            section = StorySection(
                section_id=section_id,
                section_type=sec_data.get("section_type", "analysis"),
                order=i,
                title=sec_data.get("title", f"섹션 {i + 1}"),
                narrative=sec_data.get("narrative", ""),
                charts=[],
                ai_generated=True,
                created_at=now,
            )

            # DB 저장
            with get_db_context() as db:
                db.execute(
                    text("""
                        INSERT INTO bi.story_sections (
                            section_id, story_id, section_type, "order",
                            title, narrative, charts, ai_generated, created_at, updated_at
                        ) VALUES (
                            :section_id, :story_id, :section_type, :order,
                            :title, :narrative, :charts, :ai_generated, :created_at, :updated_at
                        )
                    """),
                    {
                        "section_id": str(section_id),
                        "story_id": str(story_id),
                        "section_type": section.section_type,
                        "order": section.order,
                        "title": section.title,
                        "narrative": section.narrative,
                        "charts": json.dumps([], ensure_ascii=False),
                        "ai_generated": True,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
                db.commit()

            sections.append(section)

        logger.info(f"Generated {len(sections)} sections for story {story_id}")
        return sections

    async def _collect_story_data(
        self,
        tenant_id: UUID,
        focus_topic: Optional[str],
        time_range: Optional[str],
        source_chart_ids: Optional[List[UUID]],
    ) -> Dict[str, Any]:
        """스토리 생성용 데이터 수집"""

        data = {
            "focus_topic": focus_topic,
            "time_range": time_range or "24h",
            "charts": [],
            "summary_data": [],
        }

        with get_db_context() as db:
            # 센서 요약 데이터
            result = db.execute(
                text("""
                    SELECT
                        line_code,
                        COUNT(*) as total_readings,
                        AVG(CASE WHEN sensor_type = 'temperature' THEN value END) as avg_temp,
                        AVG(CASE WHEN sensor_type = 'pressure' THEN value END) as avg_pressure,
                        AVG(CASE WHEN sensor_type = 'humidity' THEN value END) as avg_humidity
                    FROM core.sensor_data
                    WHERE tenant_id = :tenant_id
                      AND recorded_at >= NOW() - INTERVAL '24 hours'
                    GROUP BY line_code
                    ORDER BY line_code
                """),
                {"tenant_id": str(tenant_id)}
            )

            data["summary_data"] = [
                {
                    "line_code": row.line_code,
                    "total_readings": row.total_readings,
                    "avg_temp": float(row.avg_temp) if row.avg_temp else None,
                    "avg_pressure": float(row.avg_pressure) if row.avg_pressure else None,
                    "avg_humidity": float(row.avg_humidity) if row.avg_humidity else None,
                }
                for row in result.fetchall()
            ]

            # 소스 차트 조회
            if source_chart_ids:
                chart_ids_str = ",".join(f"'{str(cid)}'" for cid in source_chart_ids)
                chart_result = db.execute(
                    text(f"""
                        SELECT chart_id, title, chart_config
                        FROM bi.saved_charts
                        WHERE tenant_id = :tenant_id
                          AND chart_id IN ({chart_ids_str})
                    """),
                    {"tenant_id": str(tenant_id)}
                )

                data["charts"] = [
                    {
                        "chart_id": str(row.chart_id),
                        "title": row.title,
                        "config": row.chart_config,
                    }
                    for row in chart_result.fetchall()
                ]

        return data

    def _build_story_prompt(
        self,
        data_context: Dict[str, Any],
        focus_topic: Optional[str],
    ) -> str:
        """스토리 생성 프롬프트 구성"""

        data_str = json.dumps(
            data_context.get("summary_data", []),
            indent=2,
            ensure_ascii=False,
            default=str
        )

        prompt = f"""다음 데이터를 기반으로 Data Story를 작성해주세요.

## 분석 주제
{focus_topic or "제조 현황 종합 분석"}

## 분석 기간
{data_context.get("time_range", "최근 24시간")}

## 데이터
```json
{data_str[:5000]}
```

위 데이터를 분석하여 Introduction, Analysis, Finding, Conclusion 4개 섹션으로 구성된 Data Story를 JSON 형식으로 생성해주세요.
각 섹션의 narrative는 Markdown 형식으로 작성해주세요.
"""

        return prompt

    def _parse_story_response(self, content: str) -> Dict[str, Any]:
        """LLM 응답에서 JSON 파싱"""

        try:
            json_start = content.find("{")
            json_end = content.rfind("}") + 1

            if json_start == -1 or json_end <= json_start:
                raise ValueError("No JSON found in response")

            json_str = content[json_start:json_end]
            return json.loads(json_str)

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse story JSON: {e}")
            # 기본 섹션 반환
            return {
                "sections": [
                    {
                        "section_type": "introduction",
                        "title": "개요",
                        "narrative": "이 보고서는 제조 현황을 분석합니다.",
                    },
                    {
                        "section_type": "analysis",
                        "title": "분석",
                        "narrative": content[:500],
                    },
                    {
                        "section_type": "conclusion",
                        "title": "결론",
                        "narrative": "추가 분석이 필요합니다.",
                    },
                ]
            }

    async def get_stories(
        self,
        tenant_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> List[DataStory]:
        """스토리 목록 조회"""

        with get_db_context() as db:
            result = db.execute(
                text("""
                    SELECT
                        story_id, tenant_id, title, description,
                        is_public, created_by, created_at, updated_at, published_at
                    FROM bi.data_stories
                    WHERE tenant_id = :tenant_id
                    ORDER BY updated_at DESC
                    LIMIT :limit OFFSET :offset
                """),
                {"tenant_id": str(tenant_id), "limit": limit, "offset": offset}
            )

            stories = []
            for row in result.fetchall():
                # 섹션 조회
                sections = await self._get_story_sections(
                    UUID(row.story_id) if isinstance(row.story_id, str) else row.story_id
                )

                stories.append(DataStory(
                    story_id=UUID(row.story_id) if isinstance(row.story_id, str) else row.story_id,
                    tenant_id=UUID(row.tenant_id) if isinstance(row.tenant_id, str) else row.tenant_id,
                    title=row.title,
                    description=row.description,
                    sections=sections,
                    is_public=row.is_public,
                    created_by=UUID(row.created_by) if isinstance(row.created_by, str) else row.created_by,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                    published_at=row.published_at,
                ))

            return stories

    async def get_story(
        self,
        tenant_id: UUID,
        story_id: UUID,
    ) -> Optional[DataStory]:
        """스토리 상세 조회"""

        with get_db_context() as db:
            result = db.execute(
                text("""
                    SELECT
                        story_id, tenant_id, title, description,
                        is_public, created_by, created_at, updated_at, published_at
                    FROM bi.data_stories
                    WHERE tenant_id = :tenant_id AND story_id = :story_id
                """),
                {"tenant_id": str(tenant_id), "story_id": str(story_id)}
            )
            row = result.fetchone()

            if not row:
                return None

            sections = await self._get_story_sections(story_id)

            return DataStory(
                story_id=UUID(row.story_id) if isinstance(row.story_id, str) else row.story_id,
                tenant_id=UUID(row.tenant_id) if isinstance(row.tenant_id, str) else row.tenant_id,
                title=row.title,
                description=row.description,
                sections=sections,
                is_public=row.is_public,
                created_by=UUID(row.created_by) if isinstance(row.created_by, str) else row.created_by,
                created_at=row.created_at,
                updated_at=row.updated_at,
                published_at=row.published_at,
            )

    async def _get_story_sections(self, story_id: UUID) -> List[StorySection]:
        """스토리 섹션 조회"""

        with get_db_context() as db:
            result = db.execute(
                text("""
                    SELECT
                        section_id, section_type, "order", title,
                        narrative, charts, ai_generated, created_at
                    FROM bi.story_sections
                    WHERE story_id = :story_id
                    ORDER BY "order"
                """),
                {"story_id": str(story_id)}
            )

            sections = []
            for row in result.fetchall():
                charts_data = row.charts if isinstance(row.charts, list) else json.loads(row.charts or "[]")

                sections.append(StorySection(
                    section_id=UUID(row.section_id) if isinstance(row.section_id, str) else row.section_id,
                    section_type=row.section_type,
                    order=row.order,
                    title=row.title,
                    narrative=row.narrative,
                    charts=[StorySectionChart(**c) for c in charts_data],
                    ai_generated=row.ai_generated,
                    created_at=row.created_at,
                ))

            return sections

    async def update_story(
        self,
        tenant_id: UUID,
        story_id: UUID,
        title: Optional[str] = None,
        description: Optional[str] = None,
        is_public: Optional[bool] = None,
    ) -> bool:
        """스토리 수정"""

        updates = []
        params = {
            "tenant_id": str(tenant_id),
            "story_id": str(story_id),
            "updated_at": datetime.utcnow(),
        }

        if title is not None:
            updates.append("title = :title")
            params["title"] = title
        if description is not None:
            updates.append("description = :description")
            params["description"] = description
        if is_public is not None:
            updates.append("is_public = :is_public")
            params["is_public"] = is_public

        if not updates:
            return False

        updates.append("updated_at = :updated_at")

        with get_db_context() as db:
            result = db.execute(
                text(f"""
                    UPDATE bi.data_stories
                    SET {", ".join(updates)}
                    WHERE tenant_id = :tenant_id AND story_id = :story_id
                """),
                params
            )
            db.commit()
            return result.rowcount > 0

    async def delete_story(
        self,
        tenant_id: UUID,
        story_id: UUID,
    ) -> bool:
        """스토리 삭제 (CASCADE로 섹션도 삭제)"""

        with get_db_context() as db:
            result = db.execute(
                text("""
                    DELETE FROM bi.data_stories
                    WHERE tenant_id = :tenant_id AND story_id = :story_id
                """),
                {"tenant_id": str(tenant_id), "story_id": str(story_id)}
            )
            db.commit()
            return result.rowcount > 0

    async def add_section(
        self,
        tenant_id: UUID,
        story_id: UUID,
        request: StorySectionCreateRequest,
    ) -> StorySection:
        """섹션 추가"""

        section_id = uuid4()
        now = datetime.utcnow()

        # order 결정
        order = request.order
        if order is None:
            # 마지막에 추가
            with get_db_context() as db:
                result = db.execute(
                    text("""
                        SELECT COALESCE(MAX("order"), -1) + 1 as next_order
                        FROM bi.story_sections
                        WHERE story_id = :story_id
                    """),
                    {"story_id": str(story_id)}
                )
                row = result.fetchone()
                order = row.next_order if row else 0

        charts_json = json.dumps(
            [c.model_dump() for c in request.charts] if request.charts else [],
            ensure_ascii=False
        )

        with get_db_context() as db:
            db.execute(
                text("""
                    INSERT INTO bi.story_sections (
                        section_id, story_id, section_type, "order",
                        title, narrative, charts, ai_generated, created_at, updated_at
                    ) VALUES (
                        :section_id, :story_id, :section_type, :order,
                        :title, :narrative, :charts, FALSE, :created_at, :updated_at
                    )
                """),
                {
                    "section_id": str(section_id),
                    "story_id": str(story_id),
                    "section_type": request.section_type,
                    "order": order,
                    "title": request.title,
                    "narrative": request.narrative,
                    "charts": charts_json,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            db.commit()

        return StorySection(
            section_id=section_id,
            section_type=request.section_type,
            order=order,
            title=request.title,
            narrative=request.narrative,
            charts=request.charts or [],
            ai_generated=False,
            created_at=now,
        )

    async def delete_section(
        self,
        tenant_id: UUID,
        story_id: UUID,
        section_id: UUID,
    ) -> bool:
        """섹션 삭제"""

        with get_db_context() as db:
            # 스토리 소유권 확인
            check = db.execute(
                text("""
                    SELECT 1 FROM bi.data_stories
                    WHERE tenant_id = :tenant_id AND story_id = :story_id
                """),
                {"tenant_id": str(tenant_id), "story_id": str(story_id)}
            )
            if not check.fetchone():
                return False

            result = db.execute(
                text("""
                    DELETE FROM bi.story_sections
                    WHERE story_id = :story_id AND section_id = :section_id
                """),
                {"story_id": str(story_id), "section_id": str(section_id)}
            )
            db.commit()
            return result.rowcount > 0


# Singleton instance
_story_service: Optional[StoryService] = None


def get_story_service() -> StoryService:
    """StoryService 싱글톤 인스턴스 반환"""
    global _story_service
    if _story_service is None:
        _story_service = StoryService()
    return _story_service
