"""
BI Chat Service - 대화형 GenBI (고품질 인사이트 버전)

AWS QuickSight GenBI 채팅 기능:
- 자연어 질문 → AI 인사이트 생성
- Star Schema 기반 데이터 수집
- Threshold 기반 상태 판단
- 자동 연관 분석 (비가동/불량 원인)
- 대화 컨텍스트 유지
- 인사이트/차트 생성 및 Pin
"""

import json
import logging
from datetime import date, datetime
from typing import List, Optional, Dict, Any, Literal
from uuid import UUID, uuid4

from anthropic import Anthropic
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import get_db_context
from app.schemas.bi_insight import (
    AIInsight,
    InsightFact,
    InsightReasoning,
    InsightAction,
)
from app.services.bi_data_collector import BIDataCollector
from app.services.bi_correlation_analyzer import CorrelationAnalyzer
from app.schemas.statcard import StatCardConfigCreate

logger = logging.getLogger(__name__)

# =====================================================
# Card Request Detection Patterns
# =====================================================

CARD_ADD_KEYWORDS = [
    "카드 추가", "카드추가", "지표 추가", "지표추가",
    "카드 생성", "카드생성", "카드 만들어", "카드만들어",
    "추가해줘", "추가해", "넣어줘", "보여줘",
]

CARD_REMOVE_KEYWORDS = [
    "카드 삭제", "카드삭제", "카드 제거", "카드제거",
    "지표 삭제", "지표삭제", "지표 제거", "지표제거",
    "삭제해줘", "삭제해", "없애줘", "빼줘",
]

# KPI 코드 매핑 (자연어 → kpi_code)
KPI_KEYWORD_MAPPING = {
    "불량률": "defect_rate",
    "불량": "defect_rate",
    "defect": "defect_rate",
    "oee": "oee",
    "설비종합효율": "oee",
    "종합효율": "oee",
    "수율": "yield_rate",
    "yield": "yield_rate",
    "양품률": "yield_rate",
    "비가동": "downtime",
    "downtime": "downtime",
    "가동률": "oee",
    "생산량": "daily_production",
    "달성률": "achievement_rate",
}

# =====================================================
# Pydantic Models
# =====================================================

from pydantic import BaseModel


class ChatSession(BaseModel):
    """채팅 세션"""
    session_id: UUID
    tenant_id: UUID
    user_id: UUID
    title: str
    context_type: str
    context_id: Optional[UUID]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_message_at: Optional[datetime]


class ChatMessage(BaseModel):
    """채팅 메시지"""
    message_id: UUID
    session_id: UUID
    role: Literal["user", "assistant", "system"]
    content: str
    response_type: Optional[str]
    response_data: Optional[Dict[str, Any]]
    linked_insight_id: Optional[UUID]
    linked_chart_id: Optional[UUID]
    created_at: datetime


class ChatRequest(BaseModel):
    """채팅 요청"""
    message: str
    session_id: Optional[UUID] = None
    context_type: str = "general"
    context_id: Optional[UUID] = None


class ChatResponse(BaseModel):
    """채팅 응답"""
    session_id: UUID
    message_id: UUID
    content: str
    response_type: str  # text, insight, chart, story, error
    response_data: Optional[Dict[str, Any]] = None
    linked_insight_id: Optional[UUID] = None
    linked_chart_id: Optional[UUID] = None


class PinnedInsight(BaseModel):
    """고정된 인사이트"""
    pin_id: UUID
    tenant_id: UUID
    insight_id: UUID
    dashboard_order: int
    grid_position: Optional[Dict[str, int]]
    display_mode: str
    show_facts: bool
    show_reasoning: bool
    show_actions: bool
    pinned_at: datetime
    pinned_by: UUID


# =====================================================
# System Prompts (고품질 인사이트용)
# =====================================================

BI_CHAT_SYSTEM_PROMPT = """당신은 TriFlow AI의 **제조 데이터 인사이트 전문가**입니다.
생산 현황, 품질 지표, 설비 상태를 분석하고 실행 가능한 인사이트를 제공합니다.

## 핵심 역할
1. **데이터 기반 분석**: 제공된 생산/품질/설비 데이터를 정확히 해석
2. **Threshold 기반 판단**: KPI 기준값으로 정상/주의/위험 상태 판별
3. **자동 원인 분석**: 이상 징후 발생 시 원인 데이터 활용
4. **실행 가능한 권장사항**: 구체적이고 현실적인 조치 제안

## 판단 기준 (Threshold)
아래 기준을 사용하여 상태를 판단하세요:
- **달성률**: ≥95% 정상, 80~95% 주의, <80% 위험
- **불량률**: ≤2% 정상, 2~3% 주의, >3% 위험
- **수율**: ≥97% 정상, 95~97% 주의, <95% 위험
- **비가동**: ≤30분 정상, 30~60분 주의, >60분 위험

## 응답 형식
분석 요청 시 반드시 다음 JSON 구조로 응답하세요:

```json
{
  "response_type": "insight",
  "status": "normal|warning|critical",
  "title": "인사이트 제목",
  "summary": "핵심 요약 (결과 중심, 1-2문장)",
  "table_data": {
    "headers": ["라인", "생산량", "목표", "달성률", "상태"],
    "rows": [
      ["LINE_A", "12,450", "15,000", "83.0%", "⚠️ 주의"],
      ["LINE_B", "19,230", "20,000", "96.2%", "✅ 정상"]
    ],
    "highlight_rules": {"달성률 < 80": "critical", "달성률 < 95": "warning"}
  },
  "facts": [
    {
      "metric_name": "총 생산량",
      "current_value": 31680,
      "previous_value": 32500,
      "change_percent": -2.5,
      "trend": "down",
      "period": "금일",
      "unit": "EA",
      "status": "warning"
    }
  ],
  "auto_analysis": {
    "has_issues": true,
    "triggers": [
      {"type": "low_achievement", "line_code": "LINE_A", "value": 83.0, "threshold": 95}
    ],
    "downtime_causes": [
      {"reason": "설비점검(PM)", "duration_min": 120, "percentage": 65.5}
    ],
    "defect_causes": [
      {"defect_type": "외관불량", "qty": 45, "percentage": 42.1}
    ]
  },
  "reasoning": {
    "analysis": "LINE_A 달성률 83%로 목표 미달. 주요 원인: 14:00~16:00 설비점검으로 120분 비가동 발생",
    "contributing_factors": ["정기 예방보전(PM)", "계획정지"],
    "confidence": 0.92
  },
  "actions": [
    {
      "priority": "high",
      "action": "PM 일정을 야간(22:00~)으로 조정 검토",
      "expected_impact": "주간 가동률 8% 개선 예상",
      "responsible_team": "생산관리팀"
    },
    {
      "priority": "medium",
      "action": "내일 LINE_A 30분 연장 운영으로 생산량 보완",
      "expected_impact": "누적 달성률 95% 회복",
      "responsible_team": "생산1팀"
    }
  ],
  "comparison": {
    "vs_yesterday": {"total_qty": -2.5, "downtime": "+15min"},
    "vs_last_week": {"total_qty": +3.2, "defect_rate": -0.5}
  },
  "chart": {
    "chart_type": "bar",
    "title": "라인별 달성률",
    "data": [
      {"name": "LINE_A", "value": 83.0, "target": 95},
      {"name": "LINE_B", "value": 96.2, "target": 95}
    ],
    "threshold_lines": [
      {"value": 95, "label": "목표", "color": "#10b981"},
      {"value": 80, "label": "경고", "color": "#f59e0b"}
    ]
  }
}
```

## 상태 이모지
- ✅ 정상 (normal): 목표 달성
- ⚠️ 주의 (warning): 목표 미달, 조치 필요
- 🚨 위험 (critical): 심각한 이상, 즉시 조치

## 중요 규칙
1. **제공된 데이터만 사용**: 추측하지 말고 실제 데이터 기반으로 분석
2. **숫자는 정확히**: 데이터에 있는 값을 그대로 사용
3. **표 형식 필수**: 라인별 현황은 반드시 table_data로 제공
4. **비교 포함**: 가능하면 전일/전주 대비 변화율 포함
5. **원인 분석**: 이상 징후 시 auto_analysis의 원인 데이터 활용
6. **차트는 1개만**: 한 번에 1개의 차트만 생성 (chart 필드 사용, charts 배열 금지)

일반 대화(인사, 질문 등)의 경우:
```json
{
  "response_type": "text",
  "content": "응답 내용"
}
```

항상 유효한 JSON 형식으로 응답하세요."""


# =====================================================
# BI Chat Service
# =====================================================

class BIChatService:
    """BI 채팅 서비스"""

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

    async def chat(
        self,
        tenant_id: UUID,
        user_id: UUID,
        request: ChatRequest,
    ) -> ChatResponse:
        """
        채팅 메시지 처리

        1. 세션 생성/조회
        2. 카드 관리 요청 감지 및 처리
        3. 대화 히스토리 로드
        4. LLM 호출
        5. 응답 저장 및 반환
        """
        # 디버그: 요청 메시지 로깅
        logger.info("[BIChat] ========== chat() CALLED ==========")
        logger.info(f"[BIChat] message: {request.message}")

        # 1. 세션 처리
        if request.session_id:
            session = await self._get_session(request.session_id, tenant_id, user_id)
            if not session:
                # 세션이 없으면 새로 생성
                session = await self._create_session(
                    tenant_id, user_id, request.context_type, request.context_id
                )
        else:
            session = await self._create_session(
                tenant_id, user_id, request.context_type, request.context_id
            )

        # 2. 카드 관리 요청 감지 및 처리
        card_request = self._detect_card_request(request.message)
        logger.info(f"[BIChat] _detect_card_request result: {card_request}")
        if card_request:
            return await self._handle_card_request(
                tenant_id=tenant_id,
                user_id=user_id,
                session=session,
                request=request,
                card_request=card_request,
            )

        # 3. 사용자 메시지 저장
        await self._save_message(
            session_id=session.session_id,
            role="user",
            content=request.message,
        )

        # 4. 대화 히스토리 로드
        history = await self._get_conversation_history(session.session_id, limit=10)

        # 5. 컨텍스트 데이터 수집
        context_data = await self._collect_context_data(
            tenant_id, request.context_type, request.context_id
        )

        # 6. LLM 호출
        try:
            llm_response = await self._call_llm(tenant_id, history, context_data)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            llm_response = {
                "response_type": "error",
                "content": f"죄송합니다. 응답 생성 중 오류가 발생했습니다: {str(e)}"
            }

        # 7. 응답 파싱
        response_type = llm_response.get("response_type", "text")
        content = llm_response.get("content", "")

        # 디버깅: LLM 응답 타입 및 구조 로깅
        logger.info(f"[BIChat] LLM response_type: {response_type}")
        logger.info(f"[BIChat] LLM response keys: {list(llm_response.keys())}")

        # insight 타입인 경우 content 생성
        if response_type == "insight":
            content = llm_response.get("summary", "인사이트가 생성되었습니다.")

        response_data = None
        linked_insight_id = None

        # 8. 인사이트 저장 (필요한 경우)
        if response_type == "insight":
            logger.info("[BIChat] response_type is 'insight', attempting to save...")
            insight = await self._save_insight_from_response(
                tenant_id, user_id, llm_response
            )
            if insight:
                linked_insight_id = insight.insight_id
                logger.info(f"[BIChat] Insight saved successfully: {insight.insight_id}")
                response_data = {
                    "insight_id": str(insight.insight_id),
                    "title": insight.title,
                    "summary": insight.summary,
                    # v2: 상태
                    "status": llm_response.get("status"),
                    # v2: 표 형태 데이터
                    "table_data": llm_response.get("table_data"),
                    "facts": [f.model_dump() for f in insight.facts],
                    # v2: 자동 연관 분석
                    "auto_analysis": llm_response.get("auto_analysis"),
                    "reasoning": insight.reasoning.model_dump(),
                    "actions": [a.model_dump() for a in insight.actions],
                    # v2: 전일/전주 비교
                    "comparison": llm_response.get("comparison"),
                    # v2: 차트 (1개만)
                    "chart": llm_response.get("chart"),
                }
            else:
                # 인사이트 저장 실패 시에도 LLM 응답 데이터 전달
                logger.warning("[BIChat] Insight save FAILED, returning raw LLM response (linked_insight_id will be None)")
                response_data = {
                    "title": llm_response.get("title", "분석 결과"),
                    "summary": llm_response.get("summary", ""),
                    "status": llm_response.get("status"),
                    "table_data": llm_response.get("table_data"),
                    "facts": llm_response.get("facts", []),
                    "auto_analysis": llm_response.get("auto_analysis"),
                    "reasoning": llm_response.get("reasoning", {}),
                    "actions": llm_response.get("actions", []),
                    "comparison": llm_response.get("comparison"),
                    "chart": llm_response.get("chart"),
                }

        # 9. 어시스턴트 메시지 저장
        assistant_message_id = await self._save_message(
            session_id=session.session_id,
            role="assistant",
            content=content,
            response_type=response_type,
            response_data=response_data,
            linked_insight_id=linked_insight_id,
        )

        # 10. 세션 업데이트
        await self._update_session_timestamp(session.session_id)

        return ChatResponse(
            session_id=session.session_id,
            message_id=assistant_message_id,
            content=content,
            response_type=response_type,
            response_data=response_data,
            linked_insight_id=linked_insight_id,
        )

    # =====================================================
    # Card Request Detection & Handling
    # =====================================================

    def _detect_card_request(self, message: str) -> Optional[Dict[str, Any]]:
        """
        사용자 메시지에서 카드 관리 요청 감지

        Returns:
            None: 카드 요청이 아님
            {"action": "add", "kpi_code": "..."}: 카드 추가 요청
            {"action": "remove", "kpi_code": "..."}: 카드 삭제 요청
        """
        message_lower = message.lower()

        # KPI 코드 추출
        detected_kpi = None
        for keyword, kpi_code in KPI_KEYWORD_MAPPING.items():
            if keyword in message_lower:
                detected_kpi = kpi_code
                break

        if not detected_kpi:
            return None

        # 추가 요청 감지
        for keyword in CARD_ADD_KEYWORDS:
            if keyword in message:
                return {"action": "add", "kpi_code": detected_kpi}

        # 삭제 요청 감지
        for keyword in CARD_REMOVE_KEYWORDS:
            if keyword in message:
                return {"action": "remove", "kpi_code": detected_kpi}

        return None

    async def _handle_card_request(
        self,
        tenant_id: UUID,
        user_id: UUID,
        session: ChatSession,
        request: ChatRequest,
        card_request: Dict[str, Any],
    ) -> ChatResponse:
        """
        카드 추가/삭제 요청 처리

        StatCardService를 사용하여 실제 카드를 추가/삭제합니다.
        """
        action = card_request["action"]
        kpi_code = card_request["kpi_code"]

        logger.info(f"[BIChat] Card request detected: action={action}, kpi_code={kpi_code}")

        # 사용자 메시지 저장
        await self._save_message(
            session_id=session.session_id,
            role="user",
            content=request.message,
        )

        try:
            if action == "add":
                result = await self._add_stat_card(tenant_id, user_id, kpi_code)
            else:  # remove
                result = await self._remove_stat_card(tenant_id, user_id, kpi_code)
        except Exception as e:
            logger.error(f"[BIChat] Card operation failed: {e}")
            result = {
                "success": False,
                "message": f"카드 작업 중 오류가 발생했습니다: {str(e)}",
            }

        # 응답 생성
        response_type = "card_action"
        content = result.get("message", "")
        response_data = {
            "action": action,
            "kpi_code": kpi_code,
            "success": result.get("success", False),
            "card_id": result.get("card_id"),
        }

        # 어시스턴트 메시지 저장
        assistant_message_id = await self._save_message(
            session_id=session.session_id,
            role="assistant",
            content=content,
            response_type=response_type,
            response_data=response_data,
        )

        await self._update_session_timestamp(session.session_id)

        return ChatResponse(
            session_id=session.session_id,
            message_id=assistant_message_id,
            content=content,
            response_type=response_type,
            response_data=response_data,
        )

    async def _add_stat_card(
        self,
        tenant_id: UUID,
        user_id: UUID,
        kpi_code: str,
    ) -> Dict[str, Any]:
        """StatCard 추가"""
        from app.services.stat_card_service import StatCardService

        # KPI 이름 조회
        kpi_name_map = {
            "defect_rate": "불량률",
            "oee": "OEE",
            "yield_rate": "수율",
            "downtime": "비가동",
            "daily_production": "생산량",
            "achievement_rate": "달성률",
        }
        kpi_name = kpi_name_map.get(kpi_code, kpi_code)

        result = None
        with get_db_context() as db:
            stat_card_service = StatCardService(db)

            # 이미 존재하는지 확인
            existing_configs = stat_card_service.list_configs(tenant_id, user_id, visible_only=False)
            for config in existing_configs:
                if config.kpi_code == kpi_code:
                    result = {
                        "success": False,
                        "message": f"'{kpi_name}' 카드가 이미 대시보드에 있습니다.",
                        "card_id": str(config.config_id),
                    }
                    break

            if result is None:
                # 새 카드 생성
                new_config = StatCardConfigCreate(
                    source_type="kpi",
                    kpi_code=kpi_code,
                    display_order=0,
                    is_visible=True,
                )

                created = stat_card_service.create_config(tenant_id, user_id, new_config)

                result = {
                    "success": True,
                    "message": f"'{kpi_name}' 카드를 대시보드에 추가했습니다.",
                    "card_id": str(created.config_id),
                }
        # with 블록 종료 후 commit 완료된 상태에서 return
        return result

    async def _remove_stat_card(
        self,
        tenant_id: UUID,
        user_id: UUID,
        kpi_code: str,
    ) -> Dict[str, Any]:
        """StatCard 삭제"""
        from app.services.stat_card_service import StatCardService

        kpi_name_map = {
            "defect_rate": "불량률",
            "oee": "OEE",
            "yield_rate": "수율",
            "downtime": "비가동",
            "daily_production": "생산량",
            "achievement_rate": "달성률",
        }
        kpi_name = kpi_name_map.get(kpi_code, kpi_code)

        result = None
        with get_db_context() as db:
            stat_card_service = StatCardService(db)

            # 해당 KPI 카드 찾기
            existing_configs = stat_card_service.list_configs(tenant_id, user_id, visible_only=False)
            target_config = None
            for config in existing_configs:
                if config.kpi_code == kpi_code:
                    target_config = config
                    break

            if not target_config:
                result = {
                    "success": False,
                    "message": f"'{kpi_name}' 카드를 찾을 수 없습니다.",
                }
            else:
                # 삭제
                deleted = stat_card_service.delete_config(target_config.config_id, tenant_id, user_id)

                if deleted:
                    result = {
                        "success": True,
                        "message": f"'{kpi_name}' 카드를 대시보드에서 삭제했습니다.",
                    }
                else:
                    result = {
                        "success": False,
                        "message": f"'{kpi_name}' 카드 삭제에 실패했습니다.",
                    }
        # with 블록 종료 후 commit 완료된 상태에서 return
        return result

    async def _create_session(
        self,
        tenant_id: UUID,
        user_id: UUID,
        context_type: str,
        context_id: Optional[UUID],
    ) -> ChatSession:
        """새 채팅 세션 생성"""
        session_id = uuid4()
        now = datetime.utcnow()

        with get_db_context() as db:
            db.execute(
                text("""
                    INSERT INTO bi.chat_sessions (
                        session_id, tenant_id, user_id, title,
                        context_type, context_id, is_active,
                        created_at, updated_at
                    ) VALUES (
                        :session_id, :tenant_id, :user_id, :title,
                        :context_type, :context_id, TRUE,
                        :created_at, :updated_at
                    )
                """),
                {
                    "session_id": str(session_id),
                    "tenant_id": str(tenant_id),
                    "user_id": str(user_id),
                    "title": "새 대화",
                    "context_type": context_type,
                    "context_id": str(context_id) if context_id else None,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            db.commit()

        return ChatSession(
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            title="새 대화",
            context_type=context_type,
            context_id=context_id,
            is_active=True,
            created_at=now,
            updated_at=now,
            last_message_at=None,
        )

    async def _get_session(
        self,
        session_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
    ) -> Optional[ChatSession]:
        """채팅 세션 조회"""
        with get_db_context() as db:
            result = db.execute(
                text("""
                    SELECT session_id, tenant_id, user_id, title,
                           context_type, context_id, is_active,
                           created_at, updated_at, last_message_at
                    FROM bi.chat_sessions
                    WHERE session_id = :session_id
                      AND tenant_id = :tenant_id
                      AND user_id = :user_id
                """),
                {
                    "session_id": str(session_id),
                    "tenant_id": str(tenant_id),
                    "user_id": str(user_id),
                }
            )
            row = result.fetchone()

        if not row:
            return None

        return ChatSession(
            session_id=UUID(row.session_id) if isinstance(row.session_id, str) else row.session_id,
            tenant_id=UUID(row.tenant_id) if isinstance(row.tenant_id, str) else row.tenant_id,
            user_id=UUID(row.user_id) if isinstance(row.user_id, str) else row.user_id,
            title=row.title,
            context_type=row.context_type,
            context_id=UUID(row.context_id) if row.context_id else None,
            is_active=row.is_active,
            created_at=row.created_at,
            updated_at=row.updated_at,
            last_message_at=row.last_message_at,
        )

    async def _save_message(
        self,
        session_id: UUID,
        role: str,
        content: str,
        response_type: Optional[str] = None,
        response_data: Optional[Dict[str, Any]] = None,
        linked_insight_id: Optional[UUID] = None,
        linked_chart_id: Optional[UUID] = None,
    ) -> UUID:
        """메시지 저장"""
        message_id = uuid4()
        now = datetime.utcnow()

        with get_db_context() as db:
            db.execute(
                text("""
                    INSERT INTO bi.chat_messages (
                        message_id, session_id, role, content,
                        response_type, response_data,
                        linked_insight_id, linked_chart_id,
                        created_at
                    ) VALUES (
                        :message_id, :session_id, :role, :content,
                        :response_type, :response_data,
                        :linked_insight_id, :linked_chart_id,
                        :created_at
                    )
                """),
                {
                    "message_id": str(message_id),
                    "session_id": str(session_id),
                    "role": role,
                    "content": content,
                    "response_type": response_type,
                    "response_data": json.dumps(response_data, ensure_ascii=False) if response_data else None,
                    "linked_insight_id": str(linked_insight_id) if linked_insight_id else None,
                    "linked_chart_id": str(linked_chart_id) if linked_chart_id else None,
                    "created_at": now,
                }
            )
            db.commit()

        return message_id

    async def _get_conversation_history(
        self,
        session_id: UUID,
        limit: int = 10,
    ) -> List[Dict[str, str]]:
        """대화 히스토리 조회"""
        with get_db_context() as db:
            result = db.execute(
                text("""
                    SELECT role, content
                    FROM bi.chat_messages
                    WHERE session_id = :session_id
                    ORDER BY created_at DESC
                    LIMIT :limit
                """),
                {"session_id": str(session_id), "limit": limit}
            )
            rows = result.fetchall()

        # 시간순으로 정렬 (역순 조회했으므로)
        messages = [{"role": row.role, "content": row.content} for row in reversed(rows)]
        return messages

    async def _collect_context_data(
        self,
        tenant_id: UUID,
        context_type: str,
        context_id: Optional[UUID],
    ) -> Dict[str, Any]:
        """
        고품질 인사이트를 위한 컨텍스트 데이터 수집

        Star Schema 기반으로 생산/품질/설비 데이터를 수집하고
        연관 분석을 수행합니다.
        """
        context = {
            "context_type": context_type,
            "timestamp": datetime.utcnow().isoformat(),
            "target_date": date.today().isoformat(),
        }

        try:
            # 비동기 DB 세션 생성
            from app.database import async_engine
            async_session = sessionmaker(
                async_engine, class_=AsyncSession, expire_on_commit=False
            )

            async with async_session() as db:
                # 1. DataCollector로 Star Schema 데이터 수집
                collector = BIDataCollector(db, tenant_id)

                # 종합 컨텍스트 수집
                bi_context = await collector.collect_insight_context(
                    target_date=date.today(),
                    include_trends=True,
                )

                context["thresholds"] = bi_context.get("thresholds", {})
                context["line_metadata"] = bi_context.get("line_metadata", [])
                context["production_data"] = bi_context.get("production_data", [])
                context["defect_data"] = bi_context.get("defect_data", [])
                context["downtime_data"] = bi_context.get("downtime_data", [])
                context["comparison"] = bi_context.get("comparison", {})
                context["trend_data"] = bi_context.get("trend_data", [])

                # 2. CorrelationAnalyzer로 연관 분석 수행
                analyzer = CorrelationAnalyzer(db, tenant_id)

                correlation_result = await analyzer.run_correlation_analysis(
                    production_data=context["production_data"],
                    comparison_data=context["comparison"],
                    thresholds=context["thresholds"],
                    target_date=date.today(),
                )

                context["correlation_analysis"] = correlation_result

        except Exception as e:
            logger.warning(f"Star Schema 데이터 수집 실패, fallback to sensor data: {e}")
            # Fallback: 기존 센서 데이터 수집
            context = await self._collect_sensor_context(tenant_id, context_type)

        return context

    async def _collect_sensor_context(
        self,
        tenant_id: UUID,
        context_type: str,
    ) -> Dict[str, Any]:
        """기존 센서 데이터 기반 컨텍스트 (Fallback)"""
        context = {
            "context_type": context_type,
            "timestamp": datetime.utcnow().isoformat(),
        }

        with get_db_context() as db:
            # 최근 센서 데이터 요약
            result = db.execute(
                text("""
                    SELECT
                        line_code,
                        sensor_type,
                        AVG(value) as avg_value,
                        MIN(value) as min_value,
                        MAX(value) as max_value,
                        COUNT(*) as reading_count
                    FROM core.sensor_data
                    WHERE tenant_id = :tenant_id
                      AND recorded_at >= now() - interval '24 hours'
                    GROUP BY line_code, sensor_type
                    ORDER BY line_code, sensor_type
                    LIMIT 50
                """),
                {"tenant_id": str(tenant_id)}
            )
            sensor_summary = [
                {
                    "line_code": row.line_code,
                    "sensor_type": row.sensor_type,
                    "avg_value": float(row.avg_value) if row.avg_value else 0,
                    "min_value": float(row.min_value) if row.min_value else 0,
                    "max_value": float(row.max_value) if row.max_value else 0,
                    "reading_count": row.reading_count,
                }
                for row in result.fetchall()
            ]
            context["sensor_summary"] = sensor_summary

        return context

    async def _call_llm(
        self,
        tenant_id: UUID,
        history: List[Dict[str, str]],
        context_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """LLM 호출 (고품질 컨텍스트 포함)"""
        # 시스템 메시지에 컨텍스트 추가
        system_message = BI_CHAT_SYSTEM_PROMPT

        # 고품질 컨텍스트 추가
        context_sections = []

        # 1. 기준 날짜
        if context_data.get("target_date"):
            context_sections.append(f"## 분석 기준일: {context_data['target_date']}")

        # 2. 라인 메타데이터
        if context_data.get("line_metadata"):
            context_sections.append(
                f"## 생산 라인 정보\n```json\n{json.dumps(context_data['line_metadata'], indent=2, ensure_ascii=False)}\n```"
            )

        # 3. 생산 현황 (핵심 데이터)
        if context_data.get("production_data"):
            context_sections.append(
                f"## 금일 생산 현황 (라인별)\n```json\n{json.dumps(context_data['production_data'], indent=2, ensure_ascii=False)}\n```"
            )

        # 4. 불량 현황
        if context_data.get("defect_data"):
            context_sections.append(
                f"## 불량 현황\n```json\n{json.dumps(context_data['defect_data'], indent=2, ensure_ascii=False)}\n```"
            )

        # 5. 비가동 현황
        if context_data.get("downtime_data"):
            context_sections.append(
                f"## 비가동 현황\n```json\n{json.dumps(context_data['downtime_data'], indent=2, ensure_ascii=False)}\n```"
            )

        # 6. 전일/전주 비교
        if context_data.get("comparison"):
            context_sections.append(
                f"## 전일/전주 대비 비교\n```json\n{json.dumps(context_data['comparison'], indent=2, ensure_ascii=False)}\n```"
            )

        # 7. 7일 추이
        if context_data.get("trend_data"):
            context_sections.append(
                f"## 최근 7일 생산 추이\n```json\n{json.dumps(context_data['trend_data'], indent=2, ensure_ascii=False)}\n```"
            )

        # 8. 연관 분석 결과 (이상 징후 시)
        if context_data.get("correlation_analysis"):
            corr = context_data["correlation_analysis"]
            if corr.get("has_issues"):
                context_sections.append(
                    f"## ⚠️ 자동 연관 분석 결과 (이상 징후 감지)\n```json\n{json.dumps(corr, indent=2, ensure_ascii=False)}\n```"
                )

        # 9. KPI 기준값
        if context_data.get("thresholds"):
            context_sections.append(
                f"## KPI 기준값 (Threshold)\n```json\n{json.dumps(context_data['thresholds'], indent=2, ensure_ascii=False)}\n```"
            )

        # 10. Fallback: 센서 데이터
        if context_data.get("sensor_summary") and not context_data.get("production_data"):
            context_sections.append(
                f"## 센서 데이터 요약 (최근 24시간)\n```json\n{json.dumps(context_data['sensor_summary'], indent=2, ensure_ascii=False)}\n```"
            )

        if context_sections:
            system_message += "\n\n# 현재 데이터 컨텍스트\n" + "\n\n".join(context_sections)

        # Anthropic API 호출
        messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in history
            if msg["role"] in ["user", "assistant"]
        ]

        response = self.client.messages.create(
            model=self.get_model(tenant_id),  # 테넌트별 동적 모델 조회
            max_tokens=4096,  # 더 긴 응답 허용
            system=system_message,
            messages=messages,
        )

        # 응답 파싱
        response_text = response.content[0].text

        # JSON 추출 시도
        try:
            # JSON 블록 찾기
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_str = response_text[json_start:json_end].strip()
            elif response_text.strip().startswith("{"):
                json_str = response_text.strip()
            else:
                # JSON이 아닌 경우 텍스트 응답으로 처리
                return {
                    "response_type": "text",
                    "content": response_text,
                }

            return json.loads(json_str)
        except json.JSONDecodeError:
            return {
                "response_type": "text",
                "content": response_text,
            }

    async def _save_insight_from_response(
        self,
        tenant_id: UUID,
        user_id: UUID,
        response: Dict[str, Any],
    ) -> Optional[AIInsight]:
        """LLM 응답에서 인사이트 저장"""
        if response.get("response_type") != "insight":
            return None

        from app.services.insight_service import get_insight_service
        get_insight_service()

        try:
            # Facts 파싱
            facts = []
            for f in response.get("facts", []):
                facts.append(InsightFact(
                    metric_name=f.get("metric_name", "Unknown"),
                    current_value=f.get("current_value", 0),
                    previous_value=f.get("previous_value"),
                    change_percent=f.get("change_percent"),
                    trend=f.get("trend", "stable"),
                    period=f.get("period", ""),
                    unit=f.get("unit"),
                ))

            # Reasoning 파싱
            r = response.get("reasoning", {})
            reasoning = InsightReasoning(
                analysis=r.get("analysis", ""),
                contributing_factors=r.get("contributing_factors", []),
                confidence=r.get("confidence", 0.5),
            )

            # Actions 파싱
            actions = []
            for a in response.get("actions", []):
                actions.append(InsightAction(
                    priority=a.get("priority", "medium"),
                    action=a.get("action", ""),
                    expected_impact=a.get("expected_impact"),
                    responsible_team=a.get("responsible_team"),
                ))

            # DB에 저장
            insight_id = uuid4()
            now = datetime.utcnow()

            with get_db_context() as db:
                db.execute(
                    text("""
                        INSERT INTO bi.ai_insights (
                            insight_id, tenant_id, source_type, title, summary,
                            facts, reasoning, actions, model_used,
                            generated_at, created_by
                        ) VALUES (
                            :insight_id, :tenant_id, 'chat', :title, :summary,
                            :facts, :reasoning, :actions, :model_used,
                            :generated_at, :created_by
                        )
                    """),
                    {
                        "insight_id": str(insight_id),
                        "tenant_id": str(tenant_id),
                        "title": response.get("title", "채팅 인사이트"),
                        "summary": response.get("summary", ""),
                        "facts": json.dumps([f.model_dump() for f in facts], ensure_ascii=False),
                        "reasoning": json.dumps(reasoning.model_dump(), ensure_ascii=False),
                        "actions": json.dumps([a.model_dump() for a in actions], ensure_ascii=False),
                        "model_used": self.model,
                        "generated_at": now,
                        "created_by": str(user_id),
                    }
                )
                db.commit()

            return AIInsight(
                insight_id=insight_id,
                tenant_id=tenant_id,
                source_type="chat",
                title=response.get("title", "채팅 인사이트"),
                summary=response.get("summary", ""),
                facts=facts,
                reasoning=reasoning,
                actions=actions,
                model_used=self.model,
                generated_at=now,
            )

        except Exception as e:
            import traceback
            logger.error(f"Failed to save insight: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    async def _update_session_timestamp(self, session_id: UUID):
        """세션 타임스탬프 업데이트"""
        now = datetime.utcnow()
        with get_db_context() as db:
            db.execute(
                text("""
                    UPDATE bi.chat_sessions
                    SET updated_at = :now, last_message_at = :now
                    WHERE session_id = :session_id
                """),
                {"session_id": str(session_id), "now": now}
            )
            db.commit()

    # =====================================================
    # 세션 관리 API
    # =====================================================

    async def get_sessions(
        self,
        tenant_id: UUID,
        user_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> List[ChatSession]:
        """사용자의 채팅 세션 목록 조회"""
        with get_db_context() as db:
            result = db.execute(
                text("""
                    SELECT session_id, tenant_id, user_id, title,
                           context_type, context_id, is_active,
                           created_at, updated_at, last_message_at
                    FROM bi.chat_sessions
                    WHERE tenant_id = :tenant_id AND user_id = :user_id
                    ORDER BY updated_at DESC
                    LIMIT :limit OFFSET :offset
                """),
                {
                    "tenant_id": str(tenant_id),
                    "user_id": str(user_id),
                    "limit": limit,
                    "offset": offset,
                }
            )
            rows = result.fetchall()

        return [
            ChatSession(
                session_id=UUID(row.session_id) if isinstance(row.session_id, str) else row.session_id,
                tenant_id=UUID(row.tenant_id) if isinstance(row.tenant_id, str) else row.tenant_id,
                user_id=UUID(row.user_id) if isinstance(row.user_id, str) else row.user_id,
                title=row.title,
                context_type=row.context_type,
                context_id=UUID(row.context_id) if row.context_id else None,
                is_active=row.is_active,
                created_at=row.created_at,
                updated_at=row.updated_at,
                last_message_at=row.last_message_at,
            )
            for row in rows
        ]

    async def get_session_messages(
        self,
        tenant_id: UUID,
        user_id: UUID,
        session_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ChatMessage]:
        """세션의 메시지 목록 조회"""
        # 세션 소유권 확인
        session = await self._get_session(session_id, tenant_id, user_id)
        if not session:
            return []

        with get_db_context() as db:
            result = db.execute(
                text("""
                    SELECT message_id, session_id, role, content,
                           response_type, response_data,
                           linked_insight_id, linked_chart_id, created_at
                    FROM bi.chat_messages
                    WHERE session_id = :session_id
                    ORDER BY created_at ASC
                    LIMIT :limit OFFSET :offset
                """),
                {"session_id": str(session_id), "limit": limit, "offset": offset}
            )
            rows = result.fetchall()

        return [
            ChatMessage(
                message_id=UUID(row.message_id) if isinstance(row.message_id, str) else row.message_id,
                session_id=UUID(row.session_id) if isinstance(row.session_id, str) else row.session_id,
                role=row.role,
                content=row.content,
                response_type=row.response_type,
                response_data=row.response_data if isinstance(row.response_data, dict) else (json.loads(row.response_data) if row.response_data else None),
                linked_insight_id=row.linked_insight_id if isinstance(row.linked_insight_id, UUID) else (UUID(row.linked_insight_id) if row.linked_insight_id else None),
                linked_chart_id=row.linked_chart_id if isinstance(row.linked_chart_id, UUID) else (UUID(row.linked_chart_id) if row.linked_chart_id else None),
                created_at=row.created_at,
            )
            for row in rows
        ]

    async def delete_session(
        self,
        tenant_id: UUID,
        user_id: UUID,
        session_id: UUID,
    ) -> bool:
        """세션 삭제"""
        with get_db_context() as db:
            result = db.execute(
                text("""
                    DELETE FROM bi.chat_sessions
                    WHERE session_id = :session_id
                      AND tenant_id = :tenant_id
                      AND user_id = :user_id
                """),
                {
                    "session_id": str(session_id),
                    "tenant_id": str(tenant_id),
                    "user_id": str(user_id),
                }
            )
            db.commit()
            return result.rowcount > 0

    async def update_session_title(
        self,
        tenant_id: UUID,
        user_id: UUID,
        session_id: UUID,
        title: str,
    ) -> bool:
        """세션 제목 변경"""
        with get_db_context() as db:
            result = db.execute(
                text("""
                    UPDATE bi.chat_sessions
                    SET title = :title, updated_at = :now
                    WHERE session_id = :session_id
                      AND tenant_id = :tenant_id
                      AND user_id = :user_id
                """),
                {
                    "session_id": str(session_id),
                    "tenant_id": str(tenant_id),
                    "user_id": str(user_id),
                    "title": title,
                    "now": datetime.utcnow(),
                }
            )
            db.commit()
            return result.rowcount > 0

    # =====================================================
    # Pin 관리 API
    # =====================================================

    async def pin_insight(
        self,
        tenant_id: UUID,
        user_id: UUID,
        insight_id: UUID,
        display_mode: str = "card",
    ) -> PinnedInsight:
        """인사이트 고정"""
        pin_id = uuid4()
        now = datetime.utcnow()

        # 현재 최대 order 조회
        with get_db_context() as db:
            result = db.execute(
                text("""
                    SELECT COALESCE(MAX(dashboard_order), -1) + 1 as next_order
                    FROM bi.pinned_insights
                    WHERE tenant_id = :tenant_id
                """),
                {"tenant_id": str(tenant_id)}
            )
            row = result.fetchone()
            next_order = row.next_order if row else 0

            # 고정
            db.execute(
                text("""
                    INSERT INTO bi.pinned_insights (
                        pin_id, tenant_id, insight_id, dashboard_order,
                        display_mode, show_facts, show_reasoning, show_actions,
                        pinned_at, pinned_by
                    ) VALUES (
                        :pin_id, :tenant_id, :insight_id, :dashboard_order,
                        :display_mode, TRUE, TRUE, TRUE,
                        :pinned_at, :pinned_by
                    )
                    ON CONFLICT (tenant_id, insight_id) DO UPDATE
                    SET display_mode = :display_mode, pinned_at = :pinned_at
                """),
                {
                    "pin_id": str(pin_id),
                    "tenant_id": str(tenant_id),
                    "insight_id": str(insight_id),
                    "dashboard_order": next_order,
                    "display_mode": display_mode,
                    "pinned_at": now,
                    "pinned_by": str(user_id),
                }
            )
            db.commit()

        return PinnedInsight(
            pin_id=pin_id,
            tenant_id=tenant_id,
            insight_id=insight_id,
            dashboard_order=next_order,
            grid_position=None,
            display_mode=display_mode,
            show_facts=True,
            show_reasoning=True,
            show_actions=True,
            pinned_at=now,
            pinned_by=user_id,
        )

    async def unpin_insight(
        self,
        tenant_id: UUID,
        insight_id: UUID,
    ) -> bool:
        """인사이트 고정 해제"""
        with get_db_context() as db:
            result = db.execute(
                text("""
                    DELETE FROM bi.pinned_insights
                    WHERE tenant_id = :tenant_id AND insight_id = :insight_id
                """),
                {"tenant_id": str(tenant_id), "insight_id": str(insight_id)}
            )
            db.commit()
            return result.rowcount > 0

    async def get_pinned_insights(
        self,
        tenant_id: UUID,
    ) -> List[Dict[str, Any]]:
        """고정된 인사이트 목록 조회 (인사이트 데이터 포함)"""
        with get_db_context() as db:
            result = db.execute(
                text("""
                    SELECT
                        p.pin_id, p.dashboard_order, p.grid_position,
                        p.display_mode, p.show_facts, p.show_reasoning, p.show_actions,
                        p.pinned_at, p.pinned_by,
                        i.insight_id, i.title, i.summary, i.facts, i.reasoning, i.actions,
                        i.source_type, i.feedback_score, i.generated_at
                    FROM bi.pinned_insights p
                    JOIN bi.ai_insights i ON p.insight_id = i.insight_id
                    WHERE p.tenant_id = :tenant_id
                    ORDER BY p.dashboard_order
                """),
                {"tenant_id": str(tenant_id)}
            )
            rows = result.fetchall()

        return [
            {
                "pin_id": str(row.pin_id),
                "insight_id": str(row.insight_id),  # 루트 레벨에 추가
                "dashboard_order": row.dashboard_order,
                "grid_position": row.grid_position if isinstance(row.grid_position, (dict, list)) else (json.loads(row.grid_position) if row.grid_position else None),
                "display_mode": row.display_mode,
                "show_facts": row.show_facts,
                "show_reasoning": row.show_reasoning,
                "show_actions": row.show_actions,
                "pinned_at": row.pinned_at.isoformat(),
                "insight": {
                    "insight_id": str(row.insight_id),
                    "title": row.title,
                    "summary": row.summary,
                    "facts": row.facts if isinstance(row.facts, list) else (json.loads(row.facts) if row.facts else []),
                    "reasoning": row.reasoning if isinstance(row.reasoning, dict) else (json.loads(row.reasoning) if row.reasoning else {}),
                    "actions": row.actions if isinstance(row.actions, list) else (json.loads(row.actions) if row.actions else []),
                    "source_type": row.source_type,
                    "feedback_score": float(row.feedback_score) if row.feedback_score else None,
                    "generated_at": row.generated_at.isoformat(),
                },
            }
            for row in rows
        ]


# Singleton instance
_bi_chat_service: Optional[BIChatService] = None


def get_bi_chat_service() -> BIChatService:
    """BIChatService 싱글톤 인스턴스 반환"""
    global _bi_chat_service
    if _bi_chat_service is None:
        _bi_chat_service = BIChatService()
    return _bi_chat_service


# =====================================================
# Streaming Response Generator
# =====================================================

async def stream_bi_chat_response(
    tenant_id: UUID,
    user_id: UUID,
    request: ChatRequest,
):
    """
    BI Chat 스트리밍 응답 생성기 (SSE)

    Server-Sent Events 형식으로 LLM 응답을 실시간 스트리밍합니다.

    Event Types:
        - start: 처리 시작
        - context: 데이터 수집 중
        - thinking: LLM 응답 생성 중
        - content: 응답 텍스트 청크 (스트리밍)
        - insight: 인사이트 저장 완료
        - done: 처리 완료
        - error: 오류 발생

    Yields:
        SSE 형식 문자열 (data: {json}\n\n)
    """
    import asyncio

    chat_service = get_bi_chat_service()

    try:
        # Event: start
        yield f"data: {json.dumps({'type': 'start', 'message': 'BI 채팅 처리 시작'}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.01)  # 클라이언트가 이벤트 수신할 시간

        # 1. 세션 처리
        if request.session_id:
            session = await chat_service._get_session(request.session_id, tenant_id, user_id)
            if not session:
                session = await chat_service._create_session(
                    tenant_id, user_id, request.context_type, request.context_id
                )
        else:
            session = await chat_service._create_session(
                tenant_id, user_id, request.context_type, request.context_id
            )

        yield f"data: {json.dumps({'type': 'session', 'session_id': str(session.session_id)}, ensure_ascii=False)}\n\n"

        # 2. 카드 관리 요청 감지
        card_request = chat_service._detect_card_request(request.message)
        if card_request:
            # 카드 관리는 스트리밍하지 않고 바로 처리
            response = await chat_service._handle_card_request(
                tenant_id=tenant_id,
                user_id=user_id,
                session=session,
                request=request,
                card_request=card_request,
            )

            yield f"data: {json.dumps({'type': 'content', 'content': response.content}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'response_type': response.response_type}, ensure_ascii=False)}\n\n"
            return

        # 3. 사용자 메시지 저장
        await chat_service._save_message(
            session_id=session.session_id,
            role="user",
            content=request.message,
        )

        # Event: context collection
        yield f"data: {json.dumps({'type': 'context', 'message': '데이터 수집 중...'}, ensure_ascii=False)}\n\n"

        # 4. 대화 히스토리 로드
        history = await chat_service._get_conversation_history(session.session_id, limit=10)

        # 5. 컨텍스트 데이터 수집
        context_data = await chat_service._collect_context_data(
            tenant_id, request.context_type, request.context_id
        )

        # Event: thinking
        yield f"data: {json.dumps({'type': 'thinking', 'message': 'AI가 응답을 생성하는 중...'}, ensure_ascii=False)}\n\n"

        # 6. LLM 스트리밍 호출
        system_message = chat_service._build_system_prompt(context_data)
        messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in history
            if msg["role"] in ["user", "assistant"]
        ]

        # Anthropic Streaming API
        full_response_text = ""

        with chat_service.client.messages.stream(
            model=chat_service.get_model(tenant_id),  # 테넌트별 동적 모델 조회
            max_tokens=4096,
            system=system_message,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                full_response_text += text
                # Event: content chunk
                yield f"data: {json.dumps({'type': 'content', 'content': text}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.01)  # 작은 지연으로 UI 부드럽게

        # 7. 응답 파싱 및 저장
        try:
            # JSON 추출
            if "```json" in full_response_text:
                json_start = full_response_text.find("```json") + 7
                json_end = full_response_text.find("```", json_start)
                json_str = full_response_text[json_start:json_end].strip()
            elif full_response_text.strip().startswith("{"):
                json_str = full_response_text.strip()
            else:
                json_str = None

            if json_str:
                llm_response = json.loads(json_str)
            else:
                llm_response = {
                    "response_type": "text",
                    "content": full_response_text,
                }
        except json.JSONDecodeError:
            llm_response = {
                "response_type": "text",
                "content": full_response_text,
            }

        # 8. 인사이트 저장
        response_type = llm_response.get("response_type", "text")
        linked_insight_id = None

        if response_type == "insight":
            insight = await chat_service._save_insight_from_response(
                tenant_id, user_id, llm_response
            )
            if insight:
                linked_insight_id = insight.insight_id
                yield f"data: {json.dumps({'type': 'insight', 'insight_id': str(insight.insight_id)}, ensure_ascii=False)}\n\n"

        # 9. 응답 메시지 저장
        message_id = await chat_service._save_message(
            session_id=session.session_id,
            role="assistant",
            content=llm_response.get("content", full_response_text),
            response_type=response_type,
            response_data=llm_response,
            linked_insight_id=linked_insight_id,
        )

        # Event: done
        yield f"data: {json.dumps({'type': 'done', 'message_id': str(message_id), 'response_type': response_type}, ensure_ascii=False)}\n\n"

    except Exception as e:
        logger.error(f"Streaming chat error: {e}", exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'message': f'응답 생성 중 오류가 발생했습니다: {str(e)}'}, ensure_ascii=False)}\n\n"
