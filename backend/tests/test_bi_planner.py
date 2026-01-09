"""
BI Planner Agent 테스트

BIPlannerAgent 클래스의 모든 메서드 테스트
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import json


class TestBIPlannerAgentInit:
    """BIPlannerAgent 초기화 테스트"""

    def test_agent_init(self):
        """에이전트 초기화"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()

        assert agent.name == "BIPlannerAgent"
        assert agent.model == "claude-sonnet-4-5-20250929"
        assert agent.max_tokens == 4096

    def test_agent_inherits_base_agent(self):
        """BaseAgent 상속 확인"""
        from app.agents.bi_planner import BIPlannerAgent
        from app.agents.base_agent import BaseAgent

        agent = BIPlannerAgent()

        assert isinstance(agent, BaseAgent)


class TestGetSystemPrompt:
    """get_system_prompt 메서드 테스트"""

    def test_get_system_prompt_returns_string(self):
        """시스템 프롬프트 반환"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()
        prompt = agent.get_system_prompt()

        assert isinstance(prompt, str)
        assert len(prompt) > 0

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_get_system_prompt_fallback(self, mock_open):
        """프롬프트 파일 없을 때 기본값"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()
        prompt = agent.get_system_prompt()

        assert "BI Planner Agent" in prompt


class TestGetTools:
    """get_tools 메서드 테스트"""

    def test_get_tools_returns_list(self):
        """도구 목록 반환"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()
        tools = agent.get_tools()

        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_get_tools_contains_required_tools(self):
        """필수 도구 포함 확인"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()
        tools = agent.get_tools()
        tool_names = [t["name"] for t in tools]

        assert "get_table_schema" in tool_names
        assert "execute_safe_sql" in tool_names
        assert "generate_chart_config" in tool_names
        assert "analyze_rank" in tool_names
        assert "analyze_predict" in tool_names
        assert "analyze_what_if" in tool_names
        assert "refine_chart" in tool_names
        assert "generate_insight" in tool_names
        assert "manage_stat_cards" in tool_names

    def test_tool_has_required_fields(self):
        """도구 필수 필드 확인"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()
        tools = agent.get_tools()

        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert "type" in tool["input_schema"]
            assert "properties" in tool["input_schema"]


class TestExecuteTool:
    """execute_tool 메서드 테스트"""

    def test_execute_unknown_tool_raises_error(self):
        """알 수 없는 도구 실행 시 에러"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()

        with pytest.raises(ValueError) as exc_info:
            agent.execute_tool("unknown_tool", {})

        assert "Unknown tool" in str(exc_info.value)


class TestGetTableSchema:
    """_get_table_schema 메서드 테스트"""

    @patch("app.agents.bi_planner.get_table_schema")
    def test_get_table_schema_success(self, mock_get_schema):
        """테이블 스키마 조회 성공"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_get_schema.return_value = {
            "columns": [
                {"name": "id", "type": "uuid"},
                {"name": "value", "type": "float"},
            ]
        }

        agent = BIPlannerAgent()
        result = agent._get_table_schema("sensor_data", "core")

        assert result["success"] is True
        assert result["table"] == "sensor_data"
        assert result["schema"] == "core"
        assert len(result["columns"]) == 2

    @patch("app.agents.bi_planner.get_table_schema")
    def test_get_table_schema_error(self, mock_get_schema):
        """테이블 스키마 조회 에러"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_get_schema.side_effect = Exception("Table not found")

        agent = BIPlannerAgent()
        result = agent._get_table_schema("invalid_table", "core")

        assert result["success"] is False
        assert "error" in result
        assert result["columns"] == []


class TestExecuteSafeSql:
    """_execute_safe_sql 메서드 테스트"""

    @patch("app.agents.bi_planner.execute_safe_sql")
    def test_execute_safe_sql_success(self, mock_execute):
        """SQL 쿼리 실행 성공"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_execute.return_value = [
            {"id": 1, "value": 85.5},
            {"id": 2, "value": 90.0},
        ]

        agent = BIPlannerAgent()
        result = agent._execute_safe_sql(
            "SELECT * FROM sensor_data WHERE tenant_id = :tenant_id",
            {"tenant_id": str(uuid4())}
        )

        assert result["success"] is True
        assert result["row_count"] == 2
        assert len(result["data"]) == 2

    def test_execute_safe_sql_without_tenant_id(self):
        """tenant_id 필터 없는 쿼리 거부"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()
        result = agent._execute_safe_sql("SELECT * FROM sensor_data")

        assert result["success"] is False
        assert "tenant_id" in result["error"]

    @patch("app.agents.bi_planner.execute_safe_sql")
    def test_execute_safe_sql_value_error(self, mock_execute):
        """허용되지 않는 SQL 쿼리"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_execute.side_effect = ValueError("DELETE not allowed")

        agent = BIPlannerAgent()
        result = agent._execute_safe_sql(
            "DELETE FROM sensor_data WHERE tenant_id = :tenant_id",
            {"tenant_id": str(uuid4())}
        )

        assert result["success"] is False
        assert "SELECT" in result["error"]

    @patch("app.agents.bi_planner.execute_safe_sql")
    def test_execute_safe_sql_general_error(self, mock_execute):
        """일반 SQL 실행 에러"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_execute.side_effect = Exception("Database connection error")

        agent = BIPlannerAgent()
        result = agent._execute_safe_sql(
            "SELECT * FROM sensor_data WHERE tenant_id = :tenant_id",
            {"tenant_id": str(uuid4())}
        )

        assert result["success"] is False
        assert "error" in result


class TestGenerateChartConfig:
    """_generate_chart_config 메서드 테스트"""

    def test_generate_chart_config_line(self):
        """라인 차트 설정 생성"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()
        data = [
            {"date": "2024-01-01", "temperature": 75.5, "humidity": 45.0},
            {"date": "2024-01-02", "temperature": 76.0, "humidity": 46.0},
        ]

        result = agent._generate_chart_config(
            data=data,
            chart_type="line",
            analysis_goal="온도 추이 분석",
            x_axis="date",
            y_axis="temperature",
        )

        assert result["success"] is True
        assert result["config"]["type"] == "line"
        assert "xAxis" in result["config"]
        assert "lines" in result["config"]

    def test_generate_chart_config_bar(self):
        """막대 차트 설정 생성"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()
        data = [
            {"category": "LINE_A", "count": 100},
            {"category": "LINE_B", "count": 150},
        ]

        result = agent._generate_chart_config(
            data=data,
            chart_type="bar",
            analysis_goal="라인별 생산량 비교",
            x_axis="category",
        )

        assert result["success"] is True
        assert result["config"]["type"] == "bar"
        assert "bars" in result["config"]

    def test_generate_chart_config_pie(self):
        """파이 차트 설정 생성"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()
        data = [
            {"name": "정상", "value": 95},
            {"name": "불량", "value": 5},
        ]

        result = agent._generate_chart_config(
            data=data,
            chart_type="pie",
            analysis_goal="품질 비율 분석",
        )

        assert result["success"] is True
        assert result["config"]["type"] == "pie"
        assert "nameKey" in result["config"]
        assert "dataKey" in result["config"]

    def test_generate_chart_config_area(self):
        """영역 차트 설정 생성"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()
        data = [
            {"date": "2024-01-01", "value": 100},
            {"date": "2024-01-02", "value": 120},
        ]

        result = agent._generate_chart_config(
            data=data,
            chart_type="area",
            analysis_goal="누적 추이 분석",
        )

        assert result["success"] is True
        assert result["config"]["type"] == "area"
        assert "areas" in result["config"]

    def test_generate_chart_config_scatter(self):
        """산점도 설정 생성"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()
        data = [
            {"x": 10, "y": 20},
            {"x": 15, "y": 25},
        ]

        result = agent._generate_chart_config(
            data=data,
            chart_type="scatter",
            analysis_goal="상관관계 분석",
            x_axis="x",
            y_axis="y",
        )

        assert result["success"] is True
        assert result["config"]["type"] == "scatter"

    def test_generate_chart_config_table(self):
        """테이블 설정 생성"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()
        data = [
            {"id": 1, "name": "Item 1", "value": 100},
        ]

        result = agent._generate_chart_config(
            data=data,
            chart_type="table",
            analysis_goal="상세 데이터 조회",
        )

        assert result["success"] is True
        assert result["config"]["type"] == "table"
        assert "columns" in result["config"]

    def test_generate_chart_config_empty_data(self):
        """빈 데이터 처리"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()
        result = agent._generate_chart_config(
            data=[],
            chart_type="line",
            analysis_goal="테스트",
        )

        assert result["success"] is False
        assert "error" in result


class TestExtractNumericKeys:
    """_extract_numeric_keys 메서드 테스트"""

    def test_extract_numeric_keys(self):
        """숫자 키 추출"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()
        data = [
            {"date": "2024-01-01", "temperature": 75.5, "count": 100, "name": "Test"},
        ]

        result = agent._extract_numeric_keys(data)

        assert "temperature" in result
        assert "count" in result
        assert "date" not in result
        assert "name" not in result

    def test_extract_numeric_keys_with_exclude(self):
        """제외 키 처리"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()
        data = [
            {"date": "2024-01-01", "temperature": 75.5, "count": 100},
        ]

        result = agent._extract_numeric_keys(data, exclude=["count"])

        assert "temperature" in result
        assert "count" not in result

    def test_extract_numeric_keys_empty_data(self):
        """빈 데이터 처리"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()
        result = agent._extract_numeric_keys([])

        assert result == []


class TestAnalyzeRank:
    """_analyze_rank 메서드 테스트"""

    @patch("app.agents.bi_planner.get_bi_service")
    def test_analyze_rank_success(self, mock_get_service):
        """RANK 분석 성공"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_service = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"dimension": "LINE_A", "value": 95.5}]
        mock_result.summary = "상위 5개 라인"
        mock_result.chart_config = {"type": "bar"}
        mock_result.insights = ["LINE_A가 1위"]
        mock_result.metadata = {"total": 5}

        mock_service.analyze_rank = AsyncMock(return_value=mock_result)
        mock_get_service.return_value = mock_service

        agent = BIPlannerAgent()

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.is_running.return_value = False
            mock_loop.return_value.run_until_complete.return_value = mock_result

            result = agent._analyze_rank(
                tenant_id=str(uuid4()),
                metric="defect_rate",
                dimension="line_code",
                limit=5,
                order="desc",
                time_range_days=7,
            )

        assert result["success"] is True
        assert result["analysis_type"] == "rank"
        assert "data" in result

    @patch("app.agents.bi_planner.get_bi_service")
    def test_analyze_rank_error(self, mock_get_service):
        """RANK 분석 에러"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_get_service.side_effect = Exception("Service error")

        agent = BIPlannerAgent()
        result = agent._analyze_rank(
            tenant_id=str(uuid4()),
            metric="defect_rate",
            dimension="line_code",
        )

        assert result["success"] is False
        assert result["analysis_type"] == "rank"
        assert "error" in result


class TestAnalyzePredict:
    """_analyze_predict 메서드 테스트"""

    @patch("app.agents.bi_planner.get_bi_service")
    def test_analyze_predict_success(self, mock_get_service):
        """PREDICT 분석 성공"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_service = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"date": "2024-01-01", "value": 100, "predicted": 105}]
        mock_result.summary = "7일 예측"
        mock_result.chart_config = {"type": "line"}
        mock_result.insights = ["상승 추세"]
        mock_result.metadata = {"method": "moving_average"}

        mock_service.analyze_predict = AsyncMock(return_value=mock_result)
        mock_get_service.return_value = mock_service

        agent = BIPlannerAgent()

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.is_running.return_value = False
            mock_loop.return_value.run_until_complete.return_value = mock_result

            result = agent._analyze_predict(
                tenant_id=str(uuid4()),
                metric="defect_rate",
            )

        assert result["success"] is True
        assert result["analysis_type"] == "predict"

    @patch("app.agents.bi_planner.get_bi_service")
    def test_analyze_predict_error(self, mock_get_service):
        """PREDICT 분석 에러"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_get_service.side_effect = Exception("Prediction failed")

        agent = BIPlannerAgent()
        result = agent._analyze_predict(
            tenant_id=str(uuid4()),
            metric="defect_rate",
        )

        assert result["success"] is False
        assert result["analysis_type"] == "predict"


class TestAnalyzeWhatIf:
    """_analyze_what_if 메서드 테스트"""

    @patch("app.agents.bi_planner.get_bi_service")
    def test_analyze_what_if_success(self, mock_get_service):
        """WHAT_IF 분석 성공"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_service = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"scenario": "baseline", "value": 2.5}]
        mock_result.summary = "온도 5도 상승 시뮬레이션"
        mock_result.chart_config = {"type": "bar"}
        mock_result.insights = ["불량률 0.5% 증가 예상"]
        mock_result.metadata = {"baseline": 2.5}

        mock_service.analyze_what_if = AsyncMock(return_value=mock_result)
        mock_get_service.return_value = mock_service

        agent = BIPlannerAgent()

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.is_running.return_value = False
            mock_loop.return_value.run_until_complete.return_value = mock_result

            result = agent._analyze_what_if(
                tenant_id=str(uuid4()),
                metric="defect_rate",
                dimension="temperature",
                baseline_value=2.5,
                scenario_changes={"temperature": 5},
            )

        assert result["success"] is True
        assert result["analysis_type"] == "what_if"

    @patch("app.agents.bi_planner.get_bi_service")
    def test_analyze_what_if_error(self, mock_get_service):
        """WHAT_IF 분석 에러"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_get_service.side_effect = Exception("Simulation failed")

        agent = BIPlannerAgent()
        result = agent._analyze_what_if(
            tenant_id=str(uuid4()),
            metric="defect_rate",
            dimension="temperature",
            baseline_value=2.5,
            scenario_changes={"temperature": 5},
        )

        assert result["success"] is False
        assert result["analysis_type"] == "what_if"


class TestRefineChart:
    """_refine_chart 메서드 테스트"""

    @patch("anthropic.Anthropic")
    @patch("app.config.settings")
    def test_refine_chart_success(self, mock_settings, mock_anthropic):
        """차트 수정 성공"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_settings.anthropic_api_key = "test-key"

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = json.dumps({
            "refined_config": {"type": "bar", "title": "월별 생산량"},
            "changes_made": ["차트 유형을 막대 차트로 변경", "제목 변경"]
        })
        mock_response.content = [mock_block]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        agent = BIPlannerAgent()
        original_config = {
            "type": "line",
            "data": [{"month": "1월", "value": 100}],
            "title": "생산량"
        }

        result = agent._refine_chart(
            original_config=original_config,
            instruction="막대 차트로 바꿔줘",
            preserve_data=True,
        )

        assert result["success"] is True
        assert "refined_config" in result
        assert "changes_made" in result
        # preserve_data=True이므로 데이터가 유지되어야 함
        assert result["refined_config"]["data"] == original_config["data"]

    @patch("anthropic.Anthropic")
    @patch("app.config.settings")
    def test_refine_chart_error(self, mock_settings, mock_anthropic):
        """차트 수정 에러"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_settings.anthropic_api_key = "test-key"
        mock_anthropic.side_effect = Exception("API error")

        agent = BIPlannerAgent()

        result = agent._refine_chart(
            original_config={"type": "line"},
            instruction="막대 차트로 바꿔줘",
        )

        assert result["success"] is False
        assert "error" in result

    @patch("anthropic.Anthropic")
    @patch("app.config.settings")
    def test_refine_chart_invalid_response(self, mock_settings, mock_anthropic):
        """유효하지 않은 응답 처리"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_settings.anthropic_api_key = "test-key"

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = "Invalid response without JSON"
        mock_response.content = [mock_block]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        agent = BIPlannerAgent()

        result = agent._refine_chart(
            original_config={"type": "line"},
            instruction="막대 차트로 바꿔줘",
        )

        assert result["success"] is False


class TestGenerateInsight:
    """_generate_insight 메서드 테스트"""

    @patch("anthropic.Anthropic")
    @patch("app.config.settings")
    def test_generate_insight_success(self, mock_settings, mock_anthropic):
        """인사이트 생성 성공"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_settings.anthropic_api_key = "test-key"

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = json.dumps({
            "title": "생산 효율 분석",
            "summary": "전반적인 생산 효율이 양호합니다.",
            "facts": [
                {
                    "metric_name": "생산량",
                    "current_value": 1000,
                    "change_percent": 5.0,
                    "trend": "up",
                    "period": "24시간",
                    "unit": "개"
                }
            ],
            "reasoning": {
                "analysis": "생산량이 5% 증가했습니다.",
                "contributing_factors": ["장비 가동률 향상"],
                "confidence": 0.85
            },
            "actions": [
                {
                    "priority": "medium",
                    "action": "현 수준 유지",
                    "expected_impact": "안정적인 생산"
                }
            ]
        })
        mock_response.content = [mock_block]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        agent = BIPlannerAgent()
        data = [
            {"timestamp": "2024-01-01", "production": 1000, "defects": 10},
        ]

        result = agent._generate_insight(
            data=data,
            time_range="24h",
        )

        assert result["success"] is True
        assert "insight" in result
        assert "title" in result["insight"]
        assert "facts" in result["insight"]
        assert "actions" in result["insight"]

    @patch("anthropic.Anthropic")
    @patch("app.config.settings")
    def test_generate_insight_with_chart_config(self, mock_settings, mock_anthropic):
        """차트 설정 포함 인사이트 생성"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_settings.anthropic_api_key = "test-key"

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = json.dumps({
            "title": "테스트",
            "summary": "테스트 요약",
            "facts": [],
            "reasoning": {"analysis": "분석", "contributing_factors": [], "confidence": 0.8},
            "actions": []
        })
        mock_response.content = [mock_block]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        agent = BIPlannerAgent()

        result = agent._generate_insight(
            data=[{"value": 100}],
            chart_config={"type": "line", "analysis_goal": "추세 분석"},
            focus_metrics=["temperature", "humidity"],
        )

        assert result["success"] is True

    @patch("anthropic.Anthropic")
    @patch("app.config.settings")
    def test_generate_insight_error(self, mock_settings, mock_anthropic):
        """인사이트 생성 에러"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_settings.anthropic_api_key = "test-key"
        mock_anthropic.side_effect = Exception("API error")

        agent = BIPlannerAgent()

        result = agent._generate_insight(data=[{"value": 100}])

        assert result["success"] is False
        assert "error" in result
        # 에러 시에도 기본 insight 구조 반환
        assert "insight" in result


class TestManageStatCards:
    """_manage_stat_cards 메서드 테스트"""

    @patch("app.database.SessionLocal")
    @patch("app.services.stat_card_service.StatCardService")
    def test_manage_stat_cards_list(self, mock_service_class, mock_session):
        """카드 목록 조회"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_db = MagicMock()
        mock_session.return_value = mock_db

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_card = MagicMock()
        mock_card.config.config_id = uuid4()
        mock_card.value.title = "테스트 카드"
        mock_card.config.source_type = "kpi"
        mock_card.value.value = 100
        mock_card.value.formatted_value = "100%"
        mock_card.value.status = "normal"
        mock_card.config.display_order = 1

        mock_result = MagicMock()
        mock_result.cards = [mock_card]
        mock_result.total = 1

        mock_service.get_card_values = AsyncMock(return_value=mock_result)

        agent = BIPlannerAgent()

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.is_running.return_value = False
            mock_loop.return_value.run_until_complete.return_value = mock_result

            result = agent._manage_stat_cards(
                action="list",
                tenant_id=str(uuid4()),
                user_id=str(uuid4()),
            )

        assert result["success"] is True
        assert result["action"] == "list"
        assert "cards" in result

    @patch("app.database.SessionLocal")
    @patch("app.services.stat_card_service.StatCardService")
    def test_manage_stat_cards_add_kpi(self, mock_service_class, mock_session):
        """KPI 카드 추가"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_db = MagicMock()
        mock_session.return_value = mock_db

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_created = MagicMock()
        mock_created.config_id = uuid4()
        mock_service.create_config.return_value = mock_created

        agent = BIPlannerAgent()
        result = agent._manage_stat_cards(
            action="add_kpi",
            tenant_id=str(uuid4()),
            user_id=str(uuid4()),
            kpi_code="defect_rate",
            title="불량률",
            unit="%",
        )

        assert result["success"] is True
        assert result["action"] == "add_kpi"
        assert result["kpi_code"] == "defect_rate"

    @patch("app.database.SessionLocal")
    @patch("app.services.stat_card_service.StatCardService")
    def test_manage_stat_cards_add_kpi_missing_code(self, mock_service_class, mock_session):
        """KPI 코드 누락"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_db = MagicMock()
        mock_session.return_value = mock_db

        agent = BIPlannerAgent()
        result = agent._manage_stat_cards(
            action="add_kpi",
            tenant_id=str(uuid4()),
            user_id=str(uuid4()),
        )

        assert result["success"] is False
        assert "kpi_code" in result["error"]

    @patch("app.database.SessionLocal")
    @patch("app.services.stat_card_service.StatCardService")
    def test_manage_stat_cards_add_db_query(self, mock_service_class, mock_session):
        """DB 쿼리 카드 추가"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_db = MagicMock()
        mock_session.return_value = mock_db

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_created = MagicMock()
        mock_created.config_id = uuid4()
        mock_service.create_config.return_value = mock_created

        agent = BIPlannerAgent()
        result = agent._manage_stat_cards(
            action="add_db_query",
            tenant_id=str(uuid4()),
            user_id=str(uuid4()),
            table_name="fact_daily_production",
            column_name="defect_rate",
            aggregation="avg",
        )

        assert result["success"] is True
        assert result["action"] == "add_db_query"

    @patch("app.database.SessionLocal")
    @patch("app.services.stat_card_service.StatCardService")
    def test_manage_stat_cards_add_db_query_missing_params(self, mock_service_class, mock_session):
        """DB 쿼리 카드 필수 파라미터 누락"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_db = MagicMock()
        mock_session.return_value = mock_db

        agent = BIPlannerAgent()
        result = agent._manage_stat_cards(
            action="add_db_query",
            tenant_id=str(uuid4()),
            user_id=str(uuid4()),
            table_name="fact_daily_production",
            # column_name, aggregation 누락
        )

        assert result["success"] is False

    @patch("app.database.SessionLocal")
    @patch("app.services.stat_card_service.StatCardService")
    def test_manage_stat_cards_add_mcp(self, mock_service_class, mock_session):
        """MCP 도구 카드 추가"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_db = MagicMock()
        mock_session.return_value = mock_db

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_created = MagicMock()
        mock_created.config_id = uuid4()
        mock_service.create_config.return_value = mock_created

        agent = BIPlannerAgent()
        result = agent._manage_stat_cards(
            action="add_mcp",
            tenant_id=str(uuid4()),
            user_id=str(uuid4()),
            mcp_server_id=str(uuid4()),
            mcp_tool_name="get_oee",
        )

        assert result["success"] is True
        assert result["action"] == "add_mcp"

    @patch("app.database.SessionLocal")
    @patch("app.services.stat_card_service.StatCardService")
    def test_manage_stat_cards_add_mcp_missing_params(self, mock_service_class, mock_session):
        """MCP 도구 카드 필수 파라미터 누락"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_db = MagicMock()
        mock_session.return_value = mock_db

        agent = BIPlannerAgent()
        result = agent._manage_stat_cards(
            action="add_mcp",
            tenant_id=str(uuid4()),
            user_id=str(uuid4()),
            # mcp_server_id, mcp_tool_name 누락
        )

        assert result["success"] is False

    @patch("app.database.SessionLocal")
    @patch("app.services.stat_card_service.StatCardService")
    def test_manage_stat_cards_remove(self, mock_service_class, mock_session):
        """카드 삭제"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_db = MagicMock()
        mock_session.return_value = mock_db

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.delete_config.return_value = True

        agent = BIPlannerAgent()
        card_id = str(uuid4())
        result = agent._manage_stat_cards(
            action="remove",
            tenant_id=str(uuid4()),
            user_id=str(uuid4()),
            card_id=card_id,
        )

        assert result["success"] is True
        assert result["action"] == "remove"
        assert result["deleted_id"] == card_id

    @patch("app.database.SessionLocal")
    @patch("app.services.stat_card_service.StatCardService")
    def test_manage_stat_cards_remove_not_found(self, mock_service_class, mock_session):
        """삭제할 카드 없음"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_db = MagicMock()
        mock_session.return_value = mock_db

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.delete_config.return_value = False

        agent = BIPlannerAgent()
        result = agent._manage_stat_cards(
            action="remove",
            tenant_id=str(uuid4()),
            user_id=str(uuid4()),
            card_id=str(uuid4()),
        )

        assert result["success"] is False

    @patch("app.database.SessionLocal")
    @patch("app.services.stat_card_service.StatCardService")
    def test_manage_stat_cards_remove_missing_id(self, mock_service_class, mock_session):
        """삭제할 카드 ID 누락"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_db = MagicMock()
        mock_session.return_value = mock_db

        agent = BIPlannerAgent()
        result = agent._manage_stat_cards(
            action="remove",
            tenant_id=str(uuid4()),
            user_id=str(uuid4()),
        )

        assert result["success"] is False
        assert "card_id" in result["error"]

    @patch("app.database.SessionLocal")
    @patch("app.services.stat_card_service.StatCardService")
    def test_manage_stat_cards_reorder(self, mock_service_class, mock_session):
        """카드 순서 변경"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_db = MagicMock()
        mock_session.return_value = mock_db

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        agent = BIPlannerAgent()
        card_ids = [str(uuid4()), str(uuid4()), str(uuid4())]
        result = agent._manage_stat_cards(
            action="reorder",
            tenant_id=str(uuid4()),
            user_id=str(uuid4()),
            card_ids=card_ids,
        )

        assert result["success"] is True
        assert result["action"] == "reorder"
        assert result["new_order"] == card_ids

    @patch("app.database.SessionLocal")
    @patch("app.services.stat_card_service.StatCardService")
    def test_manage_stat_cards_reorder_missing_ids(self, mock_service_class, mock_session):
        """순서 변경할 카드 ID 목록 누락"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_db = MagicMock()
        mock_session.return_value = mock_db

        agent = BIPlannerAgent()
        result = agent._manage_stat_cards(
            action="reorder",
            tenant_id=str(uuid4()),
            user_id=str(uuid4()),
        )

        assert result["success"] is False
        assert "card_ids" in result["error"]

    @patch("app.database.SessionLocal")
    def test_manage_stat_cards_unknown_action(self, mock_session):
        """알 수 없는 액션"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_db = MagicMock()
        mock_session.return_value = mock_db

        agent = BIPlannerAgent()
        result = agent._manage_stat_cards(
            action="unknown_action",
            tenant_id=str(uuid4()),
            user_id=str(uuid4()),
        )

        assert result["success"] is False
        assert "Unknown action" in result["error"]

    def test_manage_stat_cards_exception(self):
        """예외 발생 - 잘못된 UUID"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()
        result = agent._manage_stat_cards(
            action="list",
            tenant_id="invalid-uuid",
            user_id=str(uuid4()),
        )

        assert result["success"] is False
        assert "error" in result


class TestExecuteToolDispatch:
    """execute_tool 디스패치 테스트"""

    def test_execute_tool_get_table_schema(self):
        """get_table_schema 도구 실행"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()

        with patch.object(agent, "_get_table_schema") as mock_method:
            mock_method.return_value = {"success": True}

            agent.execute_tool("get_table_schema", {
                "table_name": "sensor_data",
                "schema": "core"
            })

            mock_method.assert_called_once_with(
                table_name="sensor_data",
                schema="core"
            )

    def test_execute_tool_execute_safe_sql(self):
        """execute_safe_sql 도구 실행"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()

        with patch.object(agent, "_execute_safe_sql") as mock_method:
            mock_method.return_value = {"success": True}

            agent.execute_tool("execute_safe_sql", {
                "sql_query": "SELECT * FROM table WHERE tenant_id = :tid",
                "params": {"tid": "123"}
            })

            mock_method.assert_called_once()

    def test_execute_tool_generate_chart_config(self):
        """generate_chart_config 도구 실행"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()

        with patch.object(agent, "_generate_chart_config") as mock_method:
            mock_method.return_value = {"success": True}

            agent.execute_tool("generate_chart_config", {
                "data": [{"x": 1, "y": 2}],
                "chart_type": "line",
                "analysis_goal": "테스트"
            })

            mock_method.assert_called_once()

    def test_execute_tool_analyze_rank(self):
        """analyze_rank 도구 실행"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()

        with patch.object(agent, "_analyze_rank") as mock_method:
            mock_method.return_value = {"success": True}

            agent.execute_tool("analyze_rank", {
                "tenant_id": str(uuid4()),
                "metric": "defect_rate",
                "dimension": "line_code"
            })

            mock_method.assert_called_once()

    def test_execute_tool_analyze_predict(self):
        """analyze_predict 도구 실행"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()

        with patch.object(agent, "_analyze_predict") as mock_method:
            mock_method.return_value = {"success": True}

            agent.execute_tool("analyze_predict", {
                "tenant_id": str(uuid4()),
                "metric": "defect_rate"
            })

            mock_method.assert_called_once()

    def test_execute_tool_analyze_what_if(self):
        """analyze_what_if 도구 실행"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()

        with patch.object(agent, "_analyze_what_if") as mock_method:
            mock_method.return_value = {"success": True}

            agent.execute_tool("analyze_what_if", {
                "tenant_id": str(uuid4()),
                "metric": "defect_rate",
                "dimension": "temperature",
                "baseline_value": 2.5,
                "scenario_changes": {"temperature": 5}
            })

            mock_method.assert_called_once()

    def test_execute_tool_refine_chart(self):
        """refine_chart 도구 실행"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()

        with patch.object(agent, "_refine_chart") as mock_method:
            mock_method.return_value = {"success": True}

            agent.execute_tool("refine_chart", {
                "original_config": {"type": "line"},
                "instruction": "막대 차트로 변경"
            })

            mock_method.assert_called_once()

    def test_execute_tool_generate_insight(self):
        """generate_insight 도구 실행"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()

        with patch.object(agent, "_generate_insight") as mock_method:
            mock_method.return_value = {"success": True}

            agent.execute_tool("generate_insight", {
                "data": [{"value": 100}]
            })

            mock_method.assert_called_once()

    def test_execute_tool_manage_stat_cards(self):
        """manage_stat_cards 도구 실행"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()

        with patch.object(agent, "_manage_stat_cards") as mock_method:
            mock_method.return_value = {"success": True}

            agent.execute_tool("manage_stat_cards", {
                "action": "list",
                "tenant_id": str(uuid4()),
                "user_id": str(uuid4())
            })

            mock_method.assert_called_once()
