"""
Insight Service 테스트
insight_service.py의 InsightService 클래스 테스트
"""
import json
import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

from app.schemas.bi_insight import InsightRequest


# ========== INSIGHT_SYSTEM_PROMPT 테스트 ==========


class TestInsightSystemPrompt:
    """시스템 프롬프트 테스트"""

    def test_prompt_import(self):
        """프롬프트 임포트 확인"""
        from app.services.insight_service import INSIGHT_SYSTEM_PROMPT
        assert isinstance(INSIGHT_SYSTEM_PROMPT, str)
        assert len(INSIGHT_SYSTEM_PROMPT) > 0

    def test_prompt_contains_json_format(self):
        """프롬프트에 JSON 형식 포함"""
        from app.services.insight_service import INSIGHT_SYSTEM_PROMPT
        assert "json" in INSIGHT_SYSTEM_PROMPT.lower()
        assert "facts" in INSIGHT_SYSTEM_PROMPT
        assert "reasoning" in INSIGHT_SYSTEM_PROMPT
        assert "actions" in INSIGHT_SYSTEM_PROMPT


# ========== InsightService 초기화 테스트 ==========


class TestInsightServiceInit:
    """InsightService 초기화 테스트"""

    @patch("app.services.insight_service.Anthropic")
    def test_service_init(self, mock_anthropic):
        """서비스 초기화"""
        from app.services.insight_service import InsightService

        service = InsightService()

        assert service.client is not None
        assert service.model == "claude-sonnet-4-5-20250929"
        mock_anthropic.assert_called_once()


# ========== get_insight_service 싱글톤 테스트 ==========


class TestGetInsightService:
    """싱글톤 패턴 테스트"""

    @patch("app.services.insight_service.Anthropic")
    def test_get_insight_service_singleton(self, mock_anthropic):
        """싱글톤 인스턴스 반환"""
        import app.services.insight_service as module
        module._insight_service = None

        from app.services.insight_service import get_insight_service

        service1 = get_insight_service()
        service2 = get_insight_service()

        assert service1 is service2


# ========== _parse_insight_response 테스트 ==========


class TestParseInsightResponse:
    """_parse_insight_response 메서드 테스트"""

    @patch("app.services.insight_service.Anthropic")
    def test_parse_valid_json(self, mock_anthropic):
        """유효한 JSON 파싱"""
        from app.services.insight_service import InsightService

        service = InsightService()

        content = '''Here is the insight:
        {
            "title": "테스트 인사이트",
            "summary": "요약",
            "facts": [],
            "reasoning": {
                "analysis": "분석",
                "contributing_factors": [],
                "confidence": 0.8
            },
            "actions": []
        }
        '''

        result = service._parse_insight_response(content)

        assert result["title"] == "테스트 인사이트"
        assert result["summary"] == "요약"
        assert result["reasoning"]["confidence"] == 0.8

    @patch("app.services.insight_service.Anthropic")
    def test_parse_no_json(self, mock_anthropic):
        """JSON 없는 경우 예외"""
        from app.services.insight_service import InsightService

        service = InsightService()

        content = "This is just plain text"

        with pytest.raises(ValueError):
            service._parse_insight_response(content)

    @patch("app.services.insight_service.Anthropic")
    def test_parse_invalid_json(self, mock_anthropic):
        """유효하지 않은 JSON"""
        from app.services.insight_service import InsightService

        service = InsightService()

        # 유효한 JSON 구조지만 불완전
        content = '{"title": "Test", "summary": "Sum"}'

        result = service._parse_insight_response(content)

        assert result["title"] == "Test"


# ========== _build_insight_prompt 테스트 ==========


class TestBuildInsightPrompt:
    """_build_insight_prompt 메서드 테스트"""

    @patch("app.services.insight_service.Anthropic")
    def test_build_prompt_basic(self, mock_anthropic):
        """기본 프롬프트 생성"""
        from app.services.insight_service import InsightService

        service = InsightService()

        data_context = {
            "source_type": "dashboard",
            "time_range": "24h",
            "data": [{"line_code": "L1", "avg_temperature": 25.5}]
        }

        request = InsightRequest(
            source_type="dashboard",
            time_range="24h"
        )

        prompt = service._build_insight_prompt(data_context, request)

        assert "dashboard" in prompt
        assert "24h" in prompt
        assert "L1" in prompt

    @patch("app.services.insight_service.Anthropic")
    def test_build_prompt_with_focus_metrics(self, mock_anthropic):
        """포커스 메트릭 포함 프롬프트"""
        from app.services.insight_service import InsightService

        service = InsightService()

        data_context = {
            "source_type": "dashboard",
            "time_range": "24h",
            "data": []
        }

        request = InsightRequest(
            source_type="dashboard",
            focus_metrics=["temperature", "pressure"]
        )

        prompt = service._build_insight_prompt(data_context, request)

        assert "temperature" in prompt
        assert "pressure" in prompt

    @patch("app.services.insight_service.Anthropic")
    def test_build_prompt_with_comparison(self, mock_anthropic):
        """비교 기간 포함 프롬프트"""
        from app.services.insight_service import InsightService

        service = InsightService()

        data_context = {
            "source_type": "dashboard",
            "data": []
        }

        request = InsightRequest(
            source_type="dashboard",
            comparison_period="7d"
        )

        prompt = service._build_insight_prompt(data_context, request)

        assert "7d" in prompt


# ========== _prepare_data_context 테스트 ==========


class TestPrepareDataContext:
    """_prepare_data_context 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.insight_service.Anthropic")
    async def test_prepare_with_source_data(self, mock_anthropic):
        """source_data가 제공된 경우"""
        from app.services.insight_service import InsightService

        service = InsightService()

        request = InsightRequest(
            source_type="dashboard",
            source_data={"records": [{"value": 100}]}
        )

        result = await service._prepare_data_context(uuid4(), request)

        assert result["data"] == {"records": [{"value": 100}]}

    @pytest.mark.asyncio
    @patch("app.services.insight_service.Anthropic")
    @patch("app.services.insight_service.get_db_context")
    async def test_prepare_dashboard_data(self, mock_db_context, mock_anthropic):
        """대시보드 데이터 조회"""
        from app.services.insight_service import InsightService
        from decimal import Decimal

        mock_db = MagicMock()
        mock_row = MagicMock()
        mock_row.line_code = "L1"
        mock_row.total_readings = 100
        mock_row.avg_temperature = Decimal("25.5")
        mock_row.avg_pressure = Decimal("1.2")
        mock_row.avg_humidity = Decimal("60.0")
        mock_row.max_temperature = Decimal("30.0")
        mock_row.min_temperature = Decimal("20.0")

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = InsightService()

        request = InsightRequest(
            source_type="dashboard",
            time_range="24h"
        )

        result = await service._prepare_data_context(uuid4(), request)

        assert result["source_type"] == "dashboard"
        assert len(result["data"]) == 1
        assert result["data"][0]["avg_temperature"] == 25.5

    @pytest.mark.asyncio
    @patch("app.services.insight_service.Anthropic")
    @patch("app.services.insight_service.get_db_context")
    async def test_prepare_chart_data_no_source_id(self, mock_db_context, mock_anthropic):
        """차트 데이터 - source_id 없음"""
        from app.services.insight_service import InsightService

        service = InsightService()

        request = InsightRequest(
            source_type="chart",
            source_id=None
        )

        result = await service._prepare_data_context(uuid4(), request)

        assert result["error"] == "chart source_id required"

    @pytest.mark.asyncio
    @patch("app.services.insight_service.Anthropic")
    @patch("app.services.insight_service.get_db_context")
    async def test_prepare_chart_data_not_found(self, mock_db_context, mock_anthropic):
        """차트 데이터 - 차트 없음"""
        from app.services.insight_service import InsightService

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = InsightService()

        request = InsightRequest(
            source_type="chart",
            source_id=uuid4()
        )

        result = await service._prepare_data_context(uuid4(), request)

        assert result["error"] == "chart not found"

    @pytest.mark.asyncio
    @patch("app.services.insight_service.Anthropic")
    @patch("app.services.insight_service.get_db_context")
    async def test_prepare_chart_data_found(self, mock_db_context, mock_anthropic):
        """차트 데이터 조회 성공"""
        from app.services.insight_service import InsightService

        mock_db = MagicMock()
        mock_row = MagicMock()
        mock_row.chart_config = {"type": "bar", "data": [1, 2, 3]}
        mock_row.source_query = "SELECT * FROM table"

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = InsightService()

        request = InsightRequest(
            source_type="chart",
            source_id=uuid4()
        )

        result = await service._prepare_data_context(uuid4(), request)

        assert result["source_type"] == "chart"
        assert result["data"] == [1, 2, 3]


# ========== _call_llm_for_insight 테스트 ==========


class TestCallLlmForInsight:
    """_call_llm_for_insight 메서드 테스트"""

    @patch("app.services.insight_service.Anthropic")
    def test_call_llm(self, mock_anthropic):
        """LLM 호출"""
        from app.services.insight_service import InsightService
        from anthropic.types import Message, TextBlock, Usage

        mock_response = MagicMock(spec=Message)
        mock_response.content = [TextBlock(type="text", text='{"title": "Test"}')]
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        service = InsightService()

        data_context = {"source_type": "dashboard", "data": []}
        request = InsightRequest(source_type="dashboard")

        result = service._call_llm_for_insight(data_context, request)

        assert result["content"] == '{"title": "Test"}'
        assert result["prompt_tokens"] == 100
        assert result["completion_tokens"] == 50


# ========== get_insights 테스트 ==========


class TestGetInsights:
    """get_insights 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.insight_service.Anthropic")
    @patch("app.services.insight_service.get_db_context")
    async def test_get_insights_empty(self, mock_db_context, mock_anthropic):
        """인사이트 없음"""
        from app.services.insight_service import InsightService

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = InsightService()

        result = await service.get_insights(uuid4())

        assert result == []

    @pytest.mark.asyncio
    @patch("app.services.insight_service.Anthropic")
    @patch("app.services.insight_service.get_db_context")
    async def test_get_insights_with_data(self, mock_db_context, mock_anthropic):
        """인사이트 조회"""
        from app.services.insight_service import InsightService

        insight_id = uuid4()
        tenant_id = uuid4()
        now = datetime.utcnow()

        mock_db = MagicMock()
        mock_row = MagicMock()
        mock_row.insight_id = str(insight_id)
        mock_row.tenant_id = str(tenant_id)
        mock_row.source_type = "dashboard"
        mock_row.source_id = None
        mock_row.title = "테스트 인사이트"
        mock_row.summary = "요약"
        mock_row.facts = json.dumps([])
        mock_row.reasoning = json.dumps({
            "analysis": "분석",
            "contributing_factors": [],
            "confidence": 0.8
        })
        mock_row.actions = json.dumps([])
        mock_row.model_used = "claude-sonnet-4-5-20250929"
        mock_row.feedback_score = None
        mock_row.generated_at = now

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = InsightService()

        result = await service.get_insights(tenant_id)

        assert len(result) == 1
        assert result[0].title == "테스트 인사이트"

    @pytest.mark.asyncio
    @patch("app.services.insight_service.Anthropic")
    @patch("app.services.insight_service.get_db_context")
    async def test_get_insights_with_source_type_filter(self, mock_db_context, mock_anthropic):
        """source_type 필터로 조회"""
        from app.services.insight_service import InsightService

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = InsightService()

        await service.get_insights(uuid4(), source_type="chart")

        # source_type 파라미터가 쿼리에 포함되었는지 확인
        call_args = mock_db.execute.call_args
        assert "source_type" in str(call_args)


# ========== get_insight 테스트 ==========


class TestGetInsight:
    """get_insight 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.insight_service.Anthropic")
    @patch("app.services.insight_service.get_db_context")
    async def test_get_insight_not_found(self, mock_db_context, mock_anthropic):
        """인사이트 없음"""
        from app.services.insight_service import InsightService

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = InsightService()

        result = await service.get_insight(uuid4(), uuid4())

        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.insight_service.Anthropic")
    @patch("app.services.insight_service.get_db_context")
    async def test_get_insight_found(self, mock_db_context, mock_anthropic):
        """인사이트 조회 성공"""
        from app.services.insight_service import InsightService

        insight_id = uuid4()
        tenant_id = uuid4()
        now = datetime.utcnow()

        mock_db = MagicMock()
        mock_row = MagicMock()
        mock_row.insight_id = str(insight_id)
        mock_row.tenant_id = str(tenant_id)
        mock_row.source_type = "dashboard"
        mock_row.source_id = None
        mock_row.title = "테스트"
        mock_row.summary = "요약"
        mock_row.facts = []
        mock_row.reasoning = {
            "analysis": "분석",
            "contributing_factors": [],
            "confidence": 0.8
        }
        mock_row.actions = []
        mock_row.model_used = "claude-sonnet-4-5-20250929"
        mock_row.feedback_score = 0.5
        mock_row.generated_at = now

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = InsightService()

        result = await service.get_insight(tenant_id, insight_id)

        assert result is not None
        assert result.title == "테스트"
        assert result.feedback_score == 0.5


# ========== _save_insight 테스트 ==========


class TestSaveInsight:
    """_save_insight 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.insight_service.Anthropic")
    @patch("app.services.insight_service.get_db_context")
    async def test_save_insight(self, mock_db_context, mock_anthropic):
        """인사이트 저장"""
        from app.services.insight_service import InsightService
        from app.schemas.bi_insight import AIInsight, InsightReasoning

        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = InsightService()

        insight = AIInsight(
            insight_id=uuid4(),
            tenant_id=uuid4(),
            source_type="dashboard",
            title="테스트",
            summary="요약",
            facts=[],
            reasoning=InsightReasoning(
                analysis="분석",
                contributing_factors=[],
                confidence=0.8
            ),
            actions=[],
            model_used="claude-sonnet-4-5-20250929",
            generated_at=datetime.utcnow()
        )

        llm_result = {
            "prompt_tokens": 100,
            "completion_tokens": 50
        }

        await service._save_insight(uuid4(), uuid4(), insight, llm_result)

        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()


# ========== generate_insight 테스트 ==========


class TestGenerateInsight:
    """generate_insight 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.insight_service.Anthropic")
    @patch("app.services.insight_service.get_db_context")
    async def test_generate_insight(self, mock_db_context, mock_anthropic):
        """인사이트 생성"""
        from app.services.insight_service import InsightService
        from anthropic.types import Message, TextBlock

        # DB Mock
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        # LLM Mock
        mock_response = MagicMock(spec=Message)
        mock_response.content = [TextBlock(type="text", text=json.dumps({
            "title": "테스트 인사이트",
            "summary": "요약",
            "facts": [],
            "reasoning": {
                "analysis": "분석",
                "contributing_factors": [],
                "confidence": 0.8
            },
            "actions": []
        }))]
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        service = InsightService()

        request = InsightRequest(
            source_type="dashboard",
            source_data={"records": [{"value": 100}]}
        )

        result = await service.generate_insight(uuid4(), uuid4(), request)

        assert result.title == "테스트 인사이트"
        assert result.summary == "요약"
