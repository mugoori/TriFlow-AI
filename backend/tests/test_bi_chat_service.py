"""
BI Chat Service 테스트
bi_chat_service.py의 BIChatService 클래스 테스트
"""
import json
import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

from app.services.bi_chat_service import (
    BIChatService,
    ChatRequest,
    ChatSession,
    ChatMessage,
    ChatResponse,
    PinnedInsight,
    CARD_ADD_KEYWORDS,
    CARD_REMOVE_KEYWORDS,
    KPI_KEYWORD_MAPPING,
    BI_CHAT_SYSTEM_PROMPT,
    get_bi_chat_service,
)


# ========== 상수 테스트 ==========


class TestConstants:
    """상수값 테스트"""

    def test_card_add_keywords(self):
        """카드 추가 키워드 확인"""
        assert "카드 추가" in CARD_ADD_KEYWORDS
        assert "지표 추가" in CARD_ADD_KEYWORDS
        assert len(CARD_ADD_KEYWORDS) > 5

    def test_card_remove_keywords(self):
        """카드 삭제 키워드 확인"""
        assert "카드 삭제" in CARD_REMOVE_KEYWORDS
        assert "지표 삭제" in CARD_REMOVE_KEYWORDS
        assert len(CARD_REMOVE_KEYWORDS) > 5

    def test_kpi_keyword_mapping(self):
        """KPI 키워드 매핑 확인"""
        assert KPI_KEYWORD_MAPPING["불량률"] == "defect_rate"
        assert KPI_KEYWORD_MAPPING["oee"] == "oee"
        assert KPI_KEYWORD_MAPPING["수율"] == "yield_rate"
        assert KPI_KEYWORD_MAPPING["비가동"] == "downtime"

    def test_system_prompt(self):
        """시스템 프롬프트 확인"""
        assert "TriFlow" in BI_CHAT_SYSTEM_PROMPT
        assert "JSON" in BI_CHAT_SYSTEM_PROMPT
        assert "facts" in BI_CHAT_SYSTEM_PROMPT
        assert "reasoning" in BI_CHAT_SYSTEM_PROMPT


# ========== ChatRequest 스키마 테스트 ==========


class TestChatRequest:
    """ChatRequest 스키마 테스트"""

    def test_minimal_request(self):
        """최소 요청"""
        request = ChatRequest(message="테스트 메시지")
        assert request.message == "테스트 메시지"
        assert request.session_id is None
        assert request.context_type == "general"

    def test_full_request(self):
        """전체 요청"""
        session_id = uuid4()
        context_id = uuid4()
        request = ChatRequest(
            message="테스트",
            session_id=session_id,
            context_type="dashboard",
            context_id=context_id
        )
        assert request.session_id == session_id
        assert request.context_type == "dashboard"
        assert request.context_id == context_id


# ========== BIChatService 초기화 테스트 ==========


class TestBIChatServiceInit:
    """BIChatService 초기화 테스트"""

    @patch("app.services.bi_chat_service.Anthropic")
    def test_init(self, mock_anthropic):
        """서비스 초기화"""
        service = BIChatService()
        assert service.client is not None
        assert service.model == "claude-sonnet-4-5-20250929"
        mock_anthropic.assert_called_once()


# ========== _detect_card_request 테스트 ==========


class TestDetectCardRequest:
    """_detect_card_request 메서드 테스트"""

    @patch("app.services.bi_chat_service.Anthropic")
    def test_add_card_request(self, mock_anthropic):
        """카드 추가 요청 감지"""
        service = BIChatService()

        result = service._detect_card_request("불량률 카드 추가해줘")

        assert result is not None
        assert result["action"] == "add"
        assert result["kpi_code"] == "defect_rate"

    @patch("app.services.bi_chat_service.Anthropic")
    def test_remove_card_request(self, mock_anthropic):
        """카드 삭제 요청 감지"""
        service = BIChatService()

        result = service._detect_card_request("OEE 지표 삭제해줘")

        assert result is not None
        assert result["action"] == "remove"
        assert result["kpi_code"] == "oee"

    @patch("app.services.bi_chat_service.Anthropic")
    def test_no_kpi_keyword(self, mock_anthropic):
        """KPI 키워드 없음"""
        service = BIChatService()

        result = service._detect_card_request("카드 추가해줘")

        assert result is None

    @patch("app.services.bi_chat_service.Anthropic")
    def test_no_action_keyword(self, mock_anthropic):
        """액션 키워드 없음"""
        service = BIChatService()

        result = service._detect_card_request("불량률 분석해줘")

        assert result is None

    @patch("app.services.bi_chat_service.Anthropic")
    def test_general_message(self, mock_anthropic):
        """일반 메시지"""
        service = BIChatService()

        result = service._detect_card_request("안녕하세요")

        assert result is None


# ========== _create_session 테스트 ==========


class TestCreateSession:
    """_create_session 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_create_session(self, mock_db_context, mock_anthropic):
        """세션 생성"""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()

        tenant_id = uuid4()
        user_id = uuid4()

        session = await service._create_session(tenant_id, user_id, "general", None)

        assert session.session_id is not None
        assert session.tenant_id == tenant_id
        assert session.user_id == user_id
        assert session.title == "새 대화"
        assert session.is_active is True
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()


# ========== _get_session 테스트 ==========


class TestGetSession:
    """_get_session 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_get_session_not_found(self, mock_db_context, mock_anthropic):
        """세션 없음"""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()

        result = await service._get_session(uuid4(), uuid4(), uuid4())

        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_get_session_found(self, mock_db_context, mock_anthropic):
        """세션 조회 성공"""
        session_id = uuid4()
        tenant_id = uuid4()
        user_id = uuid4()
        now = datetime.utcnow()

        mock_db = MagicMock()
        mock_row = MagicMock()
        mock_row.session_id = str(session_id)
        mock_row.tenant_id = str(tenant_id)
        mock_row.user_id = str(user_id)
        mock_row.title = "테스트 세션"
        mock_row.context_type = "general"
        mock_row.context_id = None
        mock_row.is_active = True
        mock_row.created_at = now
        mock_row.updated_at = now
        mock_row.last_message_at = None

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()

        result = await service._get_session(session_id, tenant_id, user_id)

        assert result is not None
        assert result.title == "테스트 세션"
        assert result.is_active is True


# ========== _save_message 테스트 ==========


class TestSaveMessage:
    """_save_message 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_save_message(self, mock_db_context, mock_anthropic):
        """메시지 저장"""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()

        message_id = await service._save_message(
            session_id=uuid4(),
            role="user",
            content="테스트 메시지"
        )

        assert message_id is not None
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()


# ========== _get_conversation_history 테스트 ==========


class TestGetConversationHistory:
    """_get_conversation_history 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_get_history_empty(self, mock_db_context, mock_anthropic):
        """히스토리 없음"""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()

        result = await service._get_conversation_history(uuid4())

        assert result == []

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_get_history_with_messages(self, mock_db_context, mock_anthropic):
        """메시지 있음"""
        mock_db = MagicMock()

        mock_row1 = MagicMock()
        mock_row1.role = "user"
        mock_row1.content = "안녕"

        mock_row2 = MagicMock()
        mock_row2.role = "assistant"
        mock_row2.content = "안녕하세요"

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row2, mock_row1]  # DESC order
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()

        result = await service._get_conversation_history(uuid4())

        assert len(result) == 2
        # reversed order
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"


# ========== _collect_sensor_context 테스트 ==========


class TestCollectSensorContext:
    """_collect_sensor_context 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_collect_sensor_context(self, mock_db_context, mock_anthropic):
        """센서 컨텍스트 수집"""
        mock_db = MagicMock()

        mock_row = MagicMock()
        mock_row.line_code = "L1"
        mock_row.sensor_type = "temperature"
        mock_row.avg_value = 25.5
        mock_row.min_value = 20.0
        mock_row.max_value = 30.0
        mock_row.reading_count = 100

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()

        result = await service._collect_sensor_context(uuid4(), "general")

        assert "sensor_summary" in result
        assert len(result["sensor_summary"]) == 1
        assert result["sensor_summary"][0]["line_code"] == "L1"


# ========== _update_session_timestamp 테스트 ==========


class TestUpdateSessionTimestamp:
    """_update_session_timestamp 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_update_timestamp(self, mock_db_context, mock_anthropic):
        """타임스탬프 업데이트"""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()

        await service._update_session_timestamp(uuid4())

        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()


# ========== get_sessions 테스트 ==========


class TestGetSessions:
    """get_sessions 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_get_sessions_empty(self, mock_db_context, mock_anthropic):
        """세션 없음"""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()

        result = await service.get_sessions(uuid4(), uuid4())

        assert result == []

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_get_sessions_with_data(self, mock_db_context, mock_anthropic):
        """세션 조회"""
        session_id = uuid4()
        tenant_id = uuid4()
        user_id = uuid4()
        now = datetime.utcnow()

        mock_db = MagicMock()
        mock_row = MagicMock()
        mock_row.session_id = str(session_id)
        mock_row.tenant_id = str(tenant_id)
        mock_row.user_id = str(user_id)
        mock_row.title = "세션 1"
        mock_row.context_type = "general"
        mock_row.context_id = None
        mock_row.is_active = True
        mock_row.created_at = now
        mock_row.updated_at = now
        mock_row.last_message_at = now

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()

        result = await service.get_sessions(tenant_id, user_id)

        assert len(result) == 1
        assert result[0].title == "세션 1"


# ========== delete_session 테스트 ==========


class TestDeleteSession:
    """delete_session 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_delete_session_success(self, mock_db_context, mock_anthropic):
        """세션 삭제 성공"""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()

        result = await service.delete_session(uuid4(), uuid4(), uuid4())

        assert result is True

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_delete_session_not_found(self, mock_db_context, mock_anthropic):
        """세션 삭제 실패 (없음)"""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()

        result = await service.delete_session(uuid4(), uuid4(), uuid4())

        assert result is False


# ========== update_session_title 테스트 ==========


class TestUpdateSessionTitle:
    """update_session_title 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_update_title_success(self, mock_db_context, mock_anthropic):
        """제목 변경 성공"""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()

        result = await service.update_session_title(
            uuid4(), uuid4(), uuid4(), "새 제목"
        )

        assert result is True


# ========== pin_insight 테스트 ==========


class TestPinInsight:
    """pin_insight 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_pin_insight(self, mock_db_context, mock_anthropic):
        """인사이트 고정"""
        mock_db = MagicMock()
        mock_row = MagicMock()
        mock_row.next_order = 0

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()

        tenant_id = uuid4()
        user_id = uuid4()
        insight_id = uuid4()

        result = await service.pin_insight(tenant_id, user_id, insight_id)

        assert result.pin_id is not None
        assert result.tenant_id == tenant_id
        assert result.insight_id == insight_id
        assert result.display_mode == "card"


# ========== unpin_insight 테스트 ==========


class TestUnpinInsight:
    """unpin_insight 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_unpin_insight_success(self, mock_db_context, mock_anthropic):
        """인사이트 고정 해제 성공"""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()

        result = await service.unpin_insight(uuid4(), uuid4())

        assert result is True

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_unpin_insight_not_found(self, mock_db_context, mock_anthropic):
        """인사이트 고정 해제 실패"""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()

        result = await service.unpin_insight(uuid4(), uuid4())

        assert result is False


# ========== get_pinned_insights 테스트 ==========


class TestGetPinnedInsights:
    """get_pinned_insights 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_get_pinned_empty(self, mock_db_context, mock_anthropic):
        """고정된 인사이트 없음"""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()

        result = await service.get_pinned_insights(uuid4())

        assert result == []


# ========== get_bi_chat_service 싱글톤 테스트 ==========


class TestGetBIChatService:
    """get_bi_chat_service 싱글톤 테스트"""

    @patch("app.services.bi_chat_service.Anthropic")
    def test_singleton(self, mock_anthropic):
        """싱글톤 확인"""
        import app.services.bi_chat_service as module
        module._bi_chat_service = None

        service1 = get_bi_chat_service()
        service2 = get_bi_chat_service()

        assert service1 is service2


# ========== _save_insight_from_response 테스트 ==========


class TestSaveInsightFromResponse:
    """_save_insight_from_response 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_save_insight_not_insight_type(self, mock_db_context, mock_anthropic):
        """인사이트 타입 아님"""
        service = BIChatService()

        result = await service._save_insight_from_response(
            uuid4(), uuid4(), {"response_type": "text", "content": "안녕"}
        )

        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_save_insight_success(self, mock_db_context, mock_anthropic):
        """인사이트 저장 성공"""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()

        response = {
            "response_type": "insight",
            "title": "테스트 인사이트",
            "summary": "요약",
            "facts": [
                {
                    "metric_name": "생산량",
                    "current_value": 1000,
                    "trend": "up",
                    "period": "금일"
                }
            ],
            "reasoning": {
                "analysis": "분석 결과",
                "contributing_factors": [],
                "confidence": 0.9
            },
            "actions": [
                {
                    "priority": "high",
                    "action": "조치 내용"
                }
            ]
        }

        result = await service._save_insight_from_response(uuid4(), uuid4(), response)

        assert result is not None
        assert result.title == "테스트 인사이트"
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_save_insight_error(self, mock_db_context, mock_anthropic):
        """인사이트 저장 에러"""
        mock_db = MagicMock()
        mock_db.execute.side_effect = Exception("DB error")
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()

        response = {
            "response_type": "insight",
            "title": "테스트",
            "summary": "요약",
            "reasoning": {"analysis": "", "confidence": 0.5}
        }

        result = await service._save_insight_from_response(uuid4(), uuid4(), response)

        # 에러 시 None 반환
        assert result is None


# ========== chat 메서드 테스트 ==========


class TestChatMethod:
    """chat 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_chat_creates_new_session(self, mock_db_context, mock_anthropic):
        """세션 없으면 새로 생성"""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        # LLM response mock
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"response_type": "text", "content": "안녕하세요"}')]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        service = BIChatService()
        service._collect_context_data = AsyncMock(return_value={"context_type": "general"})

        tenant_id = uuid4()
        user_id = uuid4()
        request = ChatRequest(message="안녕")

        result = await service.chat(tenant_id, user_id, request)

        assert result.session_id is not None
        assert result.response_type == "text"

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_chat_with_existing_session(self, mock_db_context, mock_anthropic):
        """기존 세션 사용"""
        session_id = uuid4()
        tenant_id = uuid4()
        user_id = uuid4()
        now = datetime.utcnow()

        mock_db = MagicMock()
        # 첫 번째 호출: 세션 조회
        mock_row = MagicMock()
        mock_row.session_id = str(session_id)
        mock_row.tenant_id = str(tenant_id)
        mock_row.user_id = str(user_id)
        mock_row.title = "기존 세션"
        mock_row.context_type = "general"
        mock_row.context_id = None
        mock_row.is_active = True
        mock_row.created_at = now
        mock_row.updated_at = now
        mock_row.last_message_at = None

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        # LLM response mock
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"response_type": "text", "content": "응답"}')]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        service = BIChatService()
        service._collect_context_data = AsyncMock(return_value={"context_type": "general"})

        request = ChatRequest(message="질문", session_id=session_id)

        result = await service.chat(tenant_id, user_id, request)

        assert result.session_id == session_id

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_chat_llm_error(self, mock_db_context, mock_anthropic):
        """LLM 호출 에러"""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()
        service._collect_context_data = AsyncMock(return_value={})
        service._call_llm = AsyncMock(side_effect=Exception("LLM 오류"))

        tenant_id = uuid4()
        user_id = uuid4()
        request = ChatRequest(message="테스트")

        result = await service.chat(tenant_id, user_id, request)

        assert result.response_type == "error"
        assert "오류" in result.content

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_chat_insight_response(self, mock_db_context, mock_anthropic):
        """인사이트 응답 처리"""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()
        service._collect_context_data = AsyncMock(return_value={})
        service._call_llm = AsyncMock(return_value={
            "response_type": "insight",
            "title": "생산 현황",
            "summary": "생산량 요약",
            "status": "normal",
            "facts": [],
            "reasoning": {"analysis": "분석", "confidence": 0.9},
            "actions": [],
        })
        service._save_insight_from_response = AsyncMock(return_value=None)

        tenant_id = uuid4()
        user_id = uuid4()
        request = ChatRequest(message="생산 현황 분석해줘")

        result = await service.chat(tenant_id, user_id, request)

        assert result.response_type == "insight"
        assert "생산량 요약" in result.content


# ========== _handle_card_request 테스트 ==========


class TestHandleCardRequest:
    """_handle_card_request 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_handle_add_card_request(self, mock_db_context, mock_anthropic):
        """카드 추가 요청 처리"""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()
        service._add_stat_card = AsyncMock(return_value={
            "success": True,
            "message": "'불량률' 카드를 추가했습니다.",
            "card_id": str(uuid4()),
        })

        session = ChatSession(
            session_id=uuid4(),
            tenant_id=uuid4(),
            user_id=uuid4(),
            title="테스트",
            context_type="general",
            context_id=None,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            last_message_at=None,
        )
        request = ChatRequest(message="불량률 카드 추가해줘")
        card_request = {"action": "add", "kpi_code": "defect_rate"}

        result = await service._handle_card_request(
            tenant_id=session.tenant_id,
            user_id=session.user_id,
            session=session,
            request=request,
            card_request=card_request,
        )

        assert result.response_type == "card_action"
        assert result.response_data["action"] == "add"
        assert result.response_data["success"] is True

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_handle_remove_card_request(self, mock_db_context, mock_anthropic):
        """카드 삭제 요청 처리"""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()
        service._remove_stat_card = AsyncMock(return_value={
            "success": True,
            "message": "'OEE' 카드를 삭제했습니다.",
        })

        session = ChatSession(
            session_id=uuid4(),
            tenant_id=uuid4(),
            user_id=uuid4(),
            title="테스트",
            context_type="general",
            context_id=None,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            last_message_at=None,
        )
        request = ChatRequest(message="OEE 카드 삭제해줘")
        card_request = {"action": "remove", "kpi_code": "oee"}

        result = await service._handle_card_request(
            tenant_id=session.tenant_id,
            user_id=session.user_id,
            session=session,
            request=request,
            card_request=card_request,
        )

        assert result.response_type == "card_action"
        assert result.response_data["action"] == "remove"

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_handle_card_request_error(self, mock_db_context, mock_anthropic):
        """카드 작업 에러 처리"""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()
        service._add_stat_card = AsyncMock(side_effect=Exception("서비스 오류"))

        session = ChatSession(
            session_id=uuid4(),
            tenant_id=uuid4(),
            user_id=uuid4(),
            title="테스트",
            context_type="general",
            context_id=None,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            last_message_at=None,
        )
        request = ChatRequest(message="불량률 카드 추가해줘")
        card_request = {"action": "add", "kpi_code": "defect_rate"}

        result = await service._handle_card_request(
            tenant_id=session.tenant_id,
            user_id=session.user_id,
            session=session,
            request=request,
            card_request=card_request,
        )

        assert result.response_data["success"] is False


# ========== _add_stat_card 테스트 ==========


class TestAddStatCard:
    """_add_stat_card 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_add_card_success(self, mock_db_context, mock_anthropic):
        """카드 추가 성공"""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()

        # StatCardService Mock (원본 모듈 패치)
        with patch("app.services.stat_card_service.StatCardService") as MockService:
            mock_service = MagicMock()
            mock_service.list_configs.return_value = []  # 기존 카드 없음
            mock_created = MagicMock()
            mock_created.config_id = uuid4()
            mock_service.create_config.return_value = mock_created
            MockService.return_value = mock_service

            result = await service._add_stat_card(uuid4(), uuid4(), "defect_rate")

            assert result["success"] is True
            assert "불량률" in result["message"]
            mock_service.create_config.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_add_card_already_exists(self, mock_db_context, mock_anthropic):
        """카드 이미 존재"""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()

        # StatCardService Mock - 기존 카드 있음
        with patch("app.services.stat_card_service.StatCardService") as MockService:
            mock_service = MagicMock()
            existing_config = MagicMock()
            existing_config.kpi_code = "defect_rate"
            existing_config.config_id = uuid4()
            mock_service.list_configs.return_value = [existing_config]
            MockService.return_value = mock_service

            result = await service._add_stat_card(uuid4(), uuid4(), "defect_rate")

            assert result["success"] is False
            assert "이미" in result["message"]


# ========== _remove_stat_card 테스트 ==========


class TestRemoveStatCard:
    """_remove_stat_card 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_remove_card_success(self, mock_db_context, mock_anthropic):
        """카드 삭제 성공"""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()

        with patch("app.services.stat_card_service.StatCardService") as MockService:
            mock_service = MagicMock()
            existing_config = MagicMock()
            existing_config.kpi_code = "oee"
            existing_config.config_id = uuid4()
            mock_service.list_configs.return_value = [existing_config]
            mock_service.delete_config.return_value = True
            MockService.return_value = mock_service

            result = await service._remove_stat_card(uuid4(), uuid4(), "oee")

            assert result["success"] is True
            assert "삭제" in result["message"]

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_remove_card_not_found(self, mock_db_context, mock_anthropic):
        """카드 없음"""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()

        with patch("app.services.stat_card_service.StatCardService") as MockService:
            mock_service = MagicMock()
            mock_service.list_configs.return_value = []  # 카드 없음
            MockService.return_value = mock_service

            result = await service._remove_stat_card(uuid4(), uuid4(), "oee")

            assert result["success"] is False
            assert "찾을 수 없습니다" in result["message"]

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_remove_card_delete_failed(self, mock_db_context, mock_anthropic):
        """카드 삭제 실패"""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()

        with patch("app.services.stat_card_service.StatCardService") as MockService:
            mock_service = MagicMock()
            existing_config = MagicMock()
            existing_config.kpi_code = "yield_rate"
            existing_config.config_id = uuid4()
            mock_service.list_configs.return_value = [existing_config]
            mock_service.delete_config.return_value = False  # 삭제 실패
            MockService.return_value = mock_service

            result = await service._remove_stat_card(uuid4(), uuid4(), "yield_rate")

            assert result["success"] is False
            assert "실패" in result["message"]


# ========== _call_llm 테스트 ==========


class TestCallLLM:
    """_call_llm 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    async def test_call_llm_json_response(self, mock_anthropic):
        """JSON 응답 파싱"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"response_type": "text", "content": "테스트 응답"}')]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        service = BIChatService()

        history = [{"role": "user", "content": "안녕"}]
        context_data = {"context_type": "general"}

        result = await service._call_llm(history, context_data)

        assert result["response_type"] == "text"
        assert result["content"] == "테스트 응답"

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    async def test_call_llm_json_block_response(self, mock_anthropic):
        """JSON 블록 포함 응답"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='분석 결과입니다:\n```json\n{"response_type": "insight", "title": "분석"}\n```')]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        service = BIChatService()

        history = [{"role": "user", "content": "분석해줘"}]
        context_data = {}

        result = await service._call_llm(history, context_data)

        assert result["response_type"] == "insight"

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    async def test_call_llm_plain_text_response(self, mock_anthropic):
        """일반 텍스트 응답"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='안녕하세요, 무엇을 도와드릴까요?')]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        service = BIChatService()

        history = [{"role": "user", "content": "안녕"}]
        context_data = {}

        result = await service._call_llm(history, context_data)

        assert result["response_type"] == "text"
        assert "안녕하세요" in result["content"]

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    async def test_call_llm_invalid_json(self, mock_anthropic):
        """잘못된 JSON 응답"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"invalid json')]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        service = BIChatService()

        history = [{"role": "user", "content": "테스트"}]
        context_data = {}

        result = await service._call_llm(history, context_data)

        # JSON 파싱 실패 시 텍스트로 반환
        assert result["response_type"] == "text"

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    async def test_call_llm_with_context_data(self, mock_anthropic):
        """컨텍스트 데이터 포함"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"response_type": "text", "content": "OK"}')]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        service = BIChatService()

        history = [{"role": "user", "content": "현황 분석"}]
        context_data = {
            "target_date": "2024-01-15",
            "line_metadata": [{"line_code": "L1", "name": "라인1"}],
            "production_data": [{"line": "L1", "qty": 1000}],
            "defect_data": [{"type": "외관불량", "qty": 10}],
            "downtime_data": [{"reason": "점검", "duration": 30}],
            "comparison": {"vs_yesterday": {"qty": "+5%"}},
            "trend_data": [{"date": "2024-01-14", "qty": 950}],
            "correlation_analysis": {"has_issues": True, "triggers": []},
            "thresholds": {"achievement_rate": {"warning": 95}},
        }

        result = await service._call_llm(history, context_data)

        # API 호출 확인
        mock_client.messages.create.assert_called_once()
        # 응답 확인
        assert result["response_type"] == "text"


# ========== _collect_context_data 테스트 ==========


class TestCollectContextData:
    """_collect_context_data 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    async def test_collect_context_data_success(self, mock_anthropic):
        """컨텍스트 데이터 수집 - fallback 경로 테스트"""
        service = BIChatService()

        # _collect_context_data 내부에서 예외 발생 시 _collect_sensor_context fallback 호출
        with patch.object(service, "_collect_sensor_context") as mock_sensor:
            mock_sensor.return_value = {
                "context_type": "general",
                "timestamp": "2024-01-01T00:00:00",
                "equipment_status": [{"equipment_name": "Line1", "status": "running"}],
                "production_summary": {"total": 1000},
            }

            result = await service._collect_context_data(uuid4(), "general", None)

            # fallback이 호출되어 context 반환
            assert "equipment_status" in result
            mock_sensor.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_collect_context_data_fallback(self, mock_db_context, mock_anthropic):
        """컨텍스트 수집 실패 시 fallback - _collect_sensor_context 호출"""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()

        # _collect_sensor_context 직접 테스트
        result = await service._collect_sensor_context(uuid4(), "general")

        # 결과 확인
        assert "context_type" in result
        assert "sensor_summary" in result


# ========== get_session_messages 테스트 ==========


class TestGetSessionMessages:
    """get_session_messages 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_get_messages_no_session(self, mock_db_context, mock_anthropic):
        """세션이 없으면 빈 목록 반환"""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()

        result = await service.get_session_messages(uuid4(), uuid4(), uuid4())

        assert result == []

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_get_messages_with_data(self, mock_db_context, mock_anthropic):
        """메시지 조회 성공"""
        session_id = uuid4()
        tenant_id = uuid4()
        user_id = uuid4()
        message_id = uuid4()
        now = datetime.utcnow()

        # 세션 조회용 mock
        mock_session_row = MagicMock()
        mock_session_row.session_id = str(session_id)
        mock_session_row.tenant_id = str(tenant_id)
        mock_session_row.user_id = str(user_id)
        mock_session_row.title = "테스트"
        mock_session_row.context_type = "general"
        mock_session_row.context_id = None
        mock_session_row.is_active = True
        mock_session_row.created_at = now
        mock_session_row.updated_at = now
        mock_session_row.last_message_at = None

        # 메시지 조회용 mock
        mock_msg_row = MagicMock()
        mock_msg_row.message_id = str(message_id)
        mock_msg_row.session_id = str(session_id)
        mock_msg_row.role = "user"
        mock_msg_row.content = "테스트 메시지"
        mock_msg_row.response_type = None
        mock_msg_row.response_data = None
        mock_msg_row.linked_insight_id = None
        mock_msg_row.linked_chart_id = None
        mock_msg_row.created_at = now

        mock_db = MagicMock()
        mock_result1 = MagicMock()
        mock_result1.fetchone.return_value = mock_session_row
        mock_result2 = MagicMock()
        mock_result2.fetchall.return_value = [mock_msg_row]

        mock_db.execute.side_effect = [mock_result1, mock_result2]
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()

        result = await service.get_session_messages(tenant_id, user_id, session_id)

        assert len(result) == 1
        assert result[0].content == "테스트 메시지"


# ========== get_pinned_insights with data 테스트 ==========


class TestGetPinnedInsightsWithData:
    """get_pinned_insights 추가 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.bi_chat_service.Anthropic")
    @patch("app.services.bi_chat_service.get_db_context")
    async def test_get_pinned_with_data(self, mock_db_context, mock_anthropic):
        """고정된 인사이트 조회"""
        pin_id = uuid4()
        insight_id = uuid4()
        now = datetime.utcnow()

        mock_db = MagicMock()
        mock_row = MagicMock()
        mock_row.pin_id = str(pin_id)
        mock_row.insight_id = str(insight_id)
        mock_row.dashboard_order = 0
        mock_row.grid_position = None
        mock_row.display_mode = "card"
        mock_row.show_facts = True
        mock_row.show_reasoning = True
        mock_row.show_actions = True
        mock_row.pinned_at = now
        mock_row.title = "테스트 인사이트"
        mock_row.summary = "요약"
        mock_row.facts = json.dumps([])
        mock_row.reasoning = json.dumps({"analysis": ""})
        mock_row.actions = json.dumps([])
        mock_row.source_type = "chat"
        mock_row.feedback_score = 4.5
        mock_row.generated_at = now

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = BIChatService()

        result = await service.get_pinned_insights(uuid4())

        assert len(result) == 1
        assert result[0]["insight"]["title"] == "테스트 인사이트"
        assert result[0]["insight"]["feedback_score"] == 4.5


# ========== 추가 스키마 테스트 ==========


class TestChatSessionSchema:
    """ChatSession 스키마 테스트"""

    def test_chat_session_creation(self):
        """ChatSession 생성"""
        session = ChatSession(
            session_id=uuid4(),
            tenant_id=uuid4(),
            user_id=uuid4(),
            title="테스트 세션",
            context_type="dashboard",
            context_id=uuid4(),
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            last_message_at=datetime.utcnow(),
        )
        assert session.title == "테스트 세션"
        assert session.context_type == "dashboard"


class TestChatMessageSchema:
    """ChatMessage 스키마 테스트"""

    def test_chat_message_user(self):
        """사용자 메시지"""
        msg = ChatMessage(
            message_id=uuid4(),
            session_id=uuid4(),
            role="user",
            content="질문입니다",
            response_type=None,
            response_data=None,
            linked_insight_id=None,
            linked_chart_id=None,
            created_at=datetime.utcnow(),
        )
        assert msg.role == "user"

    def test_chat_message_assistant(self):
        """어시스턴트 메시지"""
        msg = ChatMessage(
            message_id=uuid4(),
            session_id=uuid4(),
            role="assistant",
            content="응답입니다",
            response_type="insight",
            response_data={"key": "value"},
            linked_insight_id=uuid4(),
            linked_chart_id=None,
            created_at=datetime.utcnow(),
        )
        assert msg.role == "assistant"
        assert msg.response_type == "insight"


class TestChatResponseSchema:
    """ChatResponse 스키마 테스트"""

    def test_chat_response_text(self):
        """텍스트 응답"""
        response = ChatResponse(
            session_id=uuid4(),
            message_id=uuid4(),
            content="응답 내용",
            response_type="text",
        )
        assert response.response_type == "text"

    def test_chat_response_insight(self):
        """인사이트 응답"""
        insight_id = uuid4()
        response = ChatResponse(
            session_id=uuid4(),
            message_id=uuid4(),
            content="인사이트 요약",
            response_type="insight",
            response_data={"title": "분석 결과"},
            linked_insight_id=insight_id,
        )
        assert response.response_type == "insight"
        assert response.linked_insight_id == insight_id


class TestPinnedInsightSchema:
    """PinnedInsight 스키마 테스트"""

    def test_pinned_insight_creation(self):
        """PinnedInsight 생성"""
        pinned = PinnedInsight(
            pin_id=uuid4(),
            tenant_id=uuid4(),
            insight_id=uuid4(),
            dashboard_order=1,
            grid_position={"x": 0, "y": 0, "w": 4, "h": 2},
            display_mode="expanded",
            show_facts=True,
            show_reasoning=False,
            show_actions=True,
            pinned_at=datetime.utcnow(),
            pinned_by=uuid4(),
        )
        assert pinned.display_mode == "expanded"
        assert pinned.grid_position["w"] == 4
