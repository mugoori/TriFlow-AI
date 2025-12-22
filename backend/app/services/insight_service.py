"""
TriFlow AI - Insight Service
=============================
AWS QuickSight GenBI Executive Summary 기능 구현

핵심 기능:
- LLM 기반 Fact/Reasoning/Action 인사이트 생성
- 데이터 분석 및 요약
- 피드백 수집
"""
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from anthropic import Anthropic
from sqlalchemy import text

from app.config import settings
from app.database import get_db_context
from app.schemas.bi_insight import (
    AIInsight,
    InsightAction,
    InsightFact,
    InsightReasoning,
    InsightRequest,
)

logger = logging.getLogger(__name__)


# System Prompt for Insight Generation
INSIGHT_SYSTEM_PROMPT = """당신은 제조 데이터 분석 전문가입니다.
주어진 데이터를 분석하여 AWS QuickSight GenBI 스타일의 Executive Summary를 생성합니다.

## 출력 형식
반드시 다음 JSON 형식으로 출력하세요:

```json
{
  "title": "인사이트 제목 (1줄)",
  "summary": "핵심 요약 (1-2문장)",
  "facts": [
    {
      "metric_name": "메트릭 이름",
      "current_value": 숫자,
      "previous_value": 숫자 또는 null,
      "change_percent": 변화율 또는 null,
      "trend": "up" | "down" | "stable",
      "period": "측정 기간",
      "unit": "단위"
    }
  ],
  "reasoning": {
    "analysis": "왜 이런 결과가 나왔는지 분석 (2-3문장)",
    "contributing_factors": ["원인1", "원인2"],
    "confidence": 0.0 ~ 1.0,
    "data_quality_notes": "데이터 품질 참고사항 또는 null"
  },
  "actions": [
    {
      "priority": "high" | "medium" | "low",
      "action": "구체적인 권장 조치",
      "expected_impact": "예상 효과",
      "responsible_team": "담당 팀",
      "deadline_suggestion": "권장 완료 시점"
    }
  ]
}
```

## 분석 원칙
1. **Facts**: 데이터에서 확인되는 객관적 사실만 기술
2. **Reasoning**: 사실에 기반한 논리적 분석과 원인 추론
3. **Actions**: 실행 가능하고 구체적인 조치 권장

## 제조 도메인 컨텍스트
- 온도: 70°C 초과 시 주의, 80°C 초과 시 위험
- 압력: 8 bar 초과 시 주의, 10 bar 초과 시 위험
- 진동: 150 이상 시 유지보수 필요
- 생산 효율: 90% 이상 목표
"""


class InsightService:
    """
    AI 인사이트 생성 서비스

    주요 기능:
    - generate_insight(): LLM으로 인사이트 생성
    - get_insights(): 인사이트 목록 조회
    - submit_feedback(): 피드백 제출
    """

    def __init__(self):
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-5-20250929"

    async def generate_insight(
        self,
        tenant_id: UUID,
        user_id: UUID,
        request: InsightRequest,
    ) -> AIInsight:
        """
        데이터 기반 AI 인사이트 생성

        Args:
            tenant_id: 테넌트 ID
            user_id: 요청자 ID
            request: 인사이트 생성 요청

        Returns:
            생성된 AIInsight
        """
        start_time = time.time()
        insight_id = uuid4()

        try:
            # 1. 데이터 준비
            data_context = await self._prepare_data_context(tenant_id, request)

            # 2. LLM 호출
            llm_result = self._call_llm_for_insight(data_context, request)

            # 3. 응답 파싱
            parsed = self._parse_insight_response(llm_result["content"])

            # 4. 데이터베이스 저장
            insight = AIInsight(
                insight_id=insight_id,
                tenant_id=tenant_id,
                source_type=request.source_type,
                source_id=request.source_id,
                title=parsed["title"],
                summary=parsed["summary"],
                facts=[InsightFact(**f) for f in parsed.get("facts", [])],
                reasoning=InsightReasoning(**parsed.get("reasoning", {
                    "analysis": "분석 결과를 확인할 수 없습니다.",
                    "contributing_factors": [],
                    "confidence": 0.5,
                })),
                actions=[InsightAction(**a) for a in parsed.get("actions", [])],
                model_used=self.model,
                generated_at=datetime.utcnow(),
            )

            await self._save_insight(tenant_id, user_id, insight, llm_result)

            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.info(
                f"Generated insight {insight_id} in {processing_time_ms}ms "
                f"(facts={len(insight.facts)}, actions={len(insight.actions)})"
            )

            return insight

        except Exception as e:
            logger.error(f"Failed to generate insight: {e}")
            raise

    async def _prepare_data_context(
        self,
        tenant_id: UUID,
        request: InsightRequest,
    ) -> Dict[str, Any]:
        """데이터 컨텍스트 준비"""

        # source_data가 직접 제공된 경우
        if request.source_data:
            return {
                "source_type": request.source_type,
                "data": request.source_data,
                "focus_metrics": request.focus_metrics,
                "time_range": request.time_range,
            }

        # source_id로 데이터 조회
        if request.source_type == "dashboard":
            return await self._get_dashboard_data(tenant_id, request)
        elif request.source_type == "chart":
            return await self._get_chart_data(tenant_id, request)
        else:  # dataset
            return await self._get_dataset_data(tenant_id, request)

    async def _get_dashboard_data(
        self,
        tenant_id: UUID,
        request: InsightRequest,
    ) -> Dict[str, Any]:
        """대시보드 데이터 조회 (센서 요약 데이터)"""

        with get_db_context() as db:
            # 최근 24시간 센서 요약 데이터
            result = db.execute(
                text("""
                    SELECT
                        line_code,
                        COUNT(*) as total_readings,
                        AVG(CASE WHEN sensor_type = 'temperature' THEN value END) as avg_temperature,
                        AVG(CASE WHEN sensor_type = 'pressure' THEN value END) as avg_pressure,
                        AVG(CASE WHEN sensor_type = 'humidity' THEN value END) as avg_humidity,
                        MAX(CASE WHEN sensor_type = 'temperature' THEN value END) as max_temperature,
                        MIN(CASE WHEN sensor_type = 'temperature' THEN value END) as min_temperature
                    FROM core.sensor_data
                    WHERE tenant_id = :tenant_id
                      AND recorded_at >= NOW() - INTERVAL '24 hours'
                    GROUP BY line_code
                    ORDER BY line_code
                """),
                {"tenant_id": str(tenant_id)}
            )
            rows = result.fetchall()

            summary_data = [
                {
                    "line_code": row.line_code,
                    "total_readings": row.total_readings,
                    "avg_temperature": float(row.avg_temperature) if row.avg_temperature else None,
                    "avg_pressure": float(row.avg_pressure) if row.avg_pressure else None,
                    "avg_humidity": float(row.avg_humidity) if row.avg_humidity else None,
                    "max_temperature": float(row.max_temperature) if row.max_temperature else None,
                    "min_temperature": float(row.min_temperature) if row.min_temperature else None,
                }
                for row in rows
            ]

            return {
                "source_type": "dashboard",
                "data": summary_data,
                "time_range": request.time_range or "24h",
                "focus_metrics": request.focus_metrics,
            }

    async def _get_chart_data(
        self,
        tenant_id: UUID,
        request: InsightRequest,
    ) -> Dict[str, Any]:
        """차트 데이터 조회"""
        # 차트 ID로 저장된 차트 설정 조회
        if not request.source_id:
            return {
                "source_type": "chart",
                "data": [],
                "error": "chart source_id required",
            }

        with get_db_context() as db:
            result = db.execute(
                text("""
                    SELECT chart_config, source_query
                    FROM bi.saved_charts
                    WHERE chart_id = :chart_id
                      AND tenant_id = :tenant_id
                """),
                {"chart_id": str(request.source_id), "tenant_id": str(tenant_id)}
            )
            row = result.fetchone()

            if not row:
                return {
                    "source_type": "chart",
                    "data": [],
                    "error": "chart not found",
                }

            return {
                "source_type": "chart",
                "chart_config": row.chart_config,
                "data": row.chart_config.get("data", []),
                "focus_metrics": request.focus_metrics,
            }

    async def _get_dataset_data(
        self,
        tenant_id: UUID,
        request: InsightRequest,
    ) -> Dict[str, Any]:
        """데이터셋 데이터 조회"""
        # 일반적인 센서 데이터 요약
        return await self._get_dashboard_data(tenant_id, request)

    def _call_llm_for_insight(
        self,
        data_context: Dict[str, Any],
        request: InsightRequest,
    ) -> Dict[str, Any]:
        """LLM 호출하여 인사이트 생성"""

        user_message = self._build_insight_prompt(data_context, request)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=INSIGHT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text

        return {
            "content": content,
            "prompt_tokens": response.usage.input_tokens,
            "completion_tokens": response.usage.output_tokens,
        }

    def _build_insight_prompt(
        self,
        data_context: Dict[str, Any],
        request: InsightRequest,
    ) -> str:
        """인사이트 생성 프롬프트 구성"""

        data_str = json.dumps(data_context.get("data", []), indent=2, ensure_ascii=False, default=str)

        prompt = f"""다음 데이터를 분석하여 Executive Summary를 생성해주세요.

## 데이터 소스
- 유형: {data_context.get("source_type", "unknown")}
- 기간: {data_context.get("time_range", "최근 24시간")}

## 데이터
```json
{data_str[:5000]}
```
"""

        if request.focus_metrics:
            prompt += f"\n## 집중 분석 메트릭\n{', '.join(request.focus_metrics)}\n"

        if request.comparison_period:
            prompt += f"\n## 비교 기간\n{request.comparison_period}\n"

        prompt += "\n위 데이터를 분석하고 JSON 형식으로 인사이트를 생성해주세요."

        return prompt

    def _parse_insight_response(self, content: str) -> Dict[str, Any]:
        """LLM 응답에서 JSON 파싱"""

        try:
            # JSON 블록 추출
            json_start = content.find("{")
            json_end = content.rfind("}") + 1

            if json_start == -1 or json_end <= json_start:
                raise ValueError("No JSON found in response")

            json_str = content[json_start:json_end]
            return json.loads(json_str)

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse insight JSON: {e}")
            # 기본 응답 반환
            return {
                "title": "데이터 분석 결과",
                "summary": content[:200],
                "facts": [],
                "reasoning": {
                    "analysis": content,
                    "contributing_factors": [],
                    "confidence": 0.5,
                },
                "actions": [],
            }

    async def _save_insight(
        self,
        tenant_id: UUID,
        user_id: UUID,
        insight: AIInsight,
        llm_result: Dict[str, Any],
    ) -> None:
        """인사이트 데이터베이스 저장"""

        with get_db_context() as db:
            db.execute(
                text("""
                    INSERT INTO bi.ai_insights (
                        insight_id, tenant_id, source_type, source_id,
                        title, summary, facts, reasoning, actions,
                        model_used, prompt_tokens, completion_tokens,
                        generated_at, created_by
                    ) VALUES (
                        :insight_id, :tenant_id, :source_type, :source_id,
                        :title, :summary, :facts, :reasoning, :actions,
                        :model_used, :prompt_tokens, :completion_tokens,
                        :generated_at, :created_by
                    )
                """),
                {
                    "insight_id": str(insight.insight_id),
                    "tenant_id": str(tenant_id),
                    "source_type": insight.source_type,
                    "source_id": str(insight.source_id) if insight.source_id else None,
                    "title": insight.title,
                    "summary": insight.summary,
                    "facts": json.dumps([f.model_dump() for f in insight.facts], ensure_ascii=False),
                    "reasoning": json.dumps(insight.reasoning.model_dump(), ensure_ascii=False),
                    "actions": json.dumps([a.model_dump() for a in insight.actions], ensure_ascii=False),
                    "model_used": insight.model_used,
                    "prompt_tokens": llm_result.get("prompt_tokens"),
                    "completion_tokens": llm_result.get("completion_tokens"),
                    "generated_at": insight.generated_at,
                    "created_by": str(user_id),
                }
            )
            db.commit()

    async def get_insights(
        self,
        tenant_id: UUID,
        source_type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[AIInsight]:
        """인사이트 목록 조회"""

        with get_db_context() as db:
            query = """
                SELECT
                    insight_id, tenant_id, source_type, source_id,
                    title, summary, facts, reasoning, actions,
                    model_used, feedback_score, generated_at
                FROM bi.ai_insights
                WHERE tenant_id = :tenant_id
            """
            params = {"tenant_id": str(tenant_id), "limit": limit, "offset": offset}

            if source_type:
                query += " AND source_type = :source_type"
                params["source_type"] = source_type

            query += " ORDER BY generated_at DESC LIMIT :limit OFFSET :offset"

            result = db.execute(text(query), params)
            rows = result.fetchall()

            insights = []
            for row in rows:
                facts_data = row.facts if isinstance(row.facts, list) else json.loads(row.facts or "[]")
                reasoning_data = row.reasoning if isinstance(row.reasoning, dict) else json.loads(row.reasoning or "{}")
                actions_data = row.actions if isinstance(row.actions, list) else json.loads(row.actions or "[]")

                insights.append(AIInsight(
                    insight_id=UUID(row.insight_id) if isinstance(row.insight_id, str) else row.insight_id,
                    tenant_id=UUID(row.tenant_id) if isinstance(row.tenant_id, str) else row.tenant_id,
                    source_type=row.source_type,
                    source_id=UUID(row.source_id) if row.source_id else None,
                    title=row.title,
                    summary=row.summary,
                    facts=[InsightFact(**f) for f in facts_data],
                    reasoning=InsightReasoning(**reasoning_data) if reasoning_data else InsightReasoning(
                        analysis="",
                        contributing_factors=[],
                        confidence=0.0,
                    ),
                    actions=[InsightAction(**a) for a in actions_data],
                    model_used=row.model_used,
                    feedback_score=float(row.feedback_score) if row.feedback_score else None,
                    generated_at=row.generated_at,
                ))

            return insights

    async def get_insight(
        self,
        tenant_id: UUID,
        insight_id: UUID,
    ) -> Optional[AIInsight]:
        """인사이트 상세 조회"""

        # 단일 조회용 쿼리 최적화
        with get_db_context() as db:
            result = db.execute(
                text("""
                    SELECT
                        insight_id, tenant_id, source_type, source_id,
                        title, summary, facts, reasoning, actions,
                        model_used, feedback_score, generated_at
                    FROM bi.ai_insights
                    WHERE tenant_id = :tenant_id AND insight_id = :insight_id
                """),
                {"tenant_id": str(tenant_id), "insight_id": str(insight_id)}
            )
            row = result.fetchone()

            if not row:
                return None

            facts_data = row.facts if isinstance(row.facts, list) else json.loads(row.facts or "[]")
            reasoning_data = row.reasoning if isinstance(row.reasoning, dict) else json.loads(row.reasoning or "{}")
            actions_data = row.actions if isinstance(row.actions, list) else json.loads(row.actions or "[]")

            return AIInsight(
                insight_id=UUID(row.insight_id) if isinstance(row.insight_id, str) else row.insight_id,
                tenant_id=UUID(row.tenant_id) if isinstance(row.tenant_id, str) else row.tenant_id,
                source_type=row.source_type,
                source_id=UUID(row.source_id) if row.source_id else None,
                title=row.title,
                summary=row.summary,
                facts=[InsightFact(**f) for f in facts_data],
                reasoning=InsightReasoning(**reasoning_data) if reasoning_data else InsightReasoning(
                    analysis="",
                    contributing_factors=[],
                    confidence=0.0,
                ),
                actions=[InsightAction(**a) for a in actions_data],
                model_used=row.model_used,
                feedback_score=float(row.feedback_score) if row.feedback_score else None,
                generated_at=row.generated_at,
            )

    async def submit_feedback(
        self,
        tenant_id: UUID,
        insight_id: UUID,
        user_id: UUID,
        score: int,
        comment: Optional[str] = None,
    ) -> bool:
        """인사이트 피드백 제출"""

        async with get_db_context() as db:
            result = await db.execute(
                text("""
                    UPDATE bi.ai_insights
                    SET
                        feedback_score = :score,
                        feedback_comment = :comment,
                        feedback_at = NOW(),
                        feedback_by = :user_id
                    WHERE tenant_id = :tenant_id AND insight_id = :insight_id
                """),
                {
                    "tenant_id": str(tenant_id),
                    "insight_id": str(insight_id),
                    "score": score,
                    "comment": comment,
                    "user_id": str(user_id),
                }
            )
            await db.commit()
            return result.rowcount > 0


# Singleton instance
_insight_service: Optional[InsightService] = None


def get_insight_service() -> InsightService:
    """InsightService 싱글톤 인스턴스 반환"""
    global _insight_service
    if _insight_service is None:
        _insight_service = InsightService()
    return _insight_service
