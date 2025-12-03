"""
에이전트 테스트 모듈
MetaRouterAgent, JudgmentAgent, WorkflowPlannerAgent, BIPlannerAgent, LearningAgent 테스트
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from typing import Any, Dict, List
from uuid import uuid4
from datetime import datetime

from anthropic.types import Message, TextBlock, ToolUseBlock


class TestMetaRouterAgent:
    """MetaRouterAgent 테스트"""

    @patch("app.agents.base_agent.Anthropic")
    def test_meta_router_init(self, mock_anthropic):
        """MetaRouterAgent 초기화"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()

        assert agent.name == "MetaRouterAgent"
        assert agent.model == "claude-sonnet-4-5-20250929"

    @patch("app.agents.base_agent.Anthropic")
    def test_get_system_prompt(self, mock_anthropic):
        """시스템 프롬프트 반환"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()
        prompt = agent.get_system_prompt()

        assert isinstance(prompt, str)
        assert len(prompt) > 0

    @patch("app.agents.base_agent.Anthropic")
    def test_get_tools(self, mock_anthropic):
        """도구 정의 반환"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()
        tools = agent.get_tools()

        assert isinstance(tools, list)
        assert len(tools) >= 3

        tool_names = [t["name"] for t in tools]
        assert "classify_intent" in tool_names
        assert "extract_slots" in tool_names
        assert "route_request" in tool_names

    @patch("app.agents.base_agent.Anthropic")
    def test_execute_tool_classify_intent(self, mock_anthropic):
        """classify_intent 도구 실행"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()
        result = agent.execute_tool("classify_intent", {
            "intent": "judgment",
            "confidence": 0.95,
            "reasoning": "센서 데이터 분석 요청"
        })

        assert result["success"] is True
        assert result["intent"] == "judgment"

    @patch("app.agents.base_agent.Anthropic")
    def test_execute_tool_extract_slots(self, mock_anthropic):
        """extract_slots 도구 실행"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()
        result = agent.execute_tool("extract_slots", {
            "slots": {
                "sensor_type": "temperature",
                "line_code": "LINE_A"
            }
        })

        assert result["success"] is True
        assert "slots" in result

    @patch("app.agents.base_agent.Anthropic")
    def test_execute_tool_route_request(self, mock_anthropic):
        """route_request 도구 실행"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()
        result = agent.execute_tool("route_request", {
            "target_agent": "JudgmentAgent",
            "message": "센서 데이터 분석 요청"
        })

        assert result["success"] is True
        assert result["target_agent"] == "JudgmentAgent"

    @patch("app.agents.base_agent.Anthropic")
    def test_execute_unknown_tool(self, mock_anthropic):
        """알 수 없는 도구 실행"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()

        with pytest.raises(ValueError) as exc_info:
            agent.execute_tool("unknown_tool", {})

        assert "Unknown tool" in str(exc_info.value)

    @patch("app.agents.base_agent.Anthropic")
    def test_parse_routing_result(self, mock_anthropic):
        """라우팅 결과 파싱"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()

        # 도구 호출 포함 결과 (result 키 포함)
        tool_calls = [
            {
                "tool": "classify_intent",
                "input": {"intent": "bi", "confidence": 0.9},
                "result": {"success": True, "intent": "bi", "confidence": 0.9}
            },
            {
                "tool": "route_request",
                "input": {"target_agent": "BIPlannerAgent", "message": "Test"},
                "result": {"success": True, "target_agent": "BIPlannerAgent", "processed_request": "Test"}
            }
        ]

        result = agent.parse_routing_result({
            "response": "라우팅 완료",
            "tool_calls": tool_calls
        })

        assert result["intent"] == "bi"
        assert result["target_agent"] == "BIPlannerAgent"

    @patch("app.agents.base_agent.Anthropic")
    def test_parse_routing_result_empty(self, mock_anthropic):
        """도구 호출 없는 라우팅 결과 파싱"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()

        result = agent.parse_routing_result({
            "response": "도구 호출 없음",
            "tool_calls": []
        })

        # 빈 tool_calls일 때 기본값 반환
        assert result["intent"] is None
        assert result["target_agent"] == "general"

    @patch("app.agents.base_agent.Anthropic")
    def test_run_routing_flow(self, mock_anthropic):
        """전체 라우팅 흐름 테스트"""
        from app.agents.meta_router import MetaRouterAgent

        # Mock 응답: 도구 호출 후 최종 응답
        mock_tool_response = MagicMock(spec=Message)
        mock_tool_response.stop_reason = "tool_use"
        mock_tool_response.content = [
            ToolUseBlock(
                type="tool_use",
                id="tool_1",
                name="classify_intent",
                input={"intent": "workflow", "confidence": 0.92, "reasoning": "워크플로우 요청"}
            )
        ]

        mock_final_response = MagicMock(spec=Message)
        mock_final_response.stop_reason = "end_turn"
        mock_final_response.content = [
            TextBlock(type="text", text="워크플로우 에이전트로 라우팅합니다.")
        ]

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [mock_tool_response, mock_final_response]
        mock_anthropic.return_value = mock_client

        agent = MetaRouterAgent()
        result = agent.run("워크플로우 만들어줘")

        assert len(result["tool_calls"]) >= 1


class TestJudgmentAgent:
    """JudgmentAgent 테스트"""

    @patch("app.agents.base_agent.Anthropic")
    def test_judgment_agent_init(self, mock_anthropic):
        """JudgmentAgent 초기화"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()

        assert agent.name == "JudgmentAgent"
        assert agent.rhai_engine is not None

    @patch("app.agents.base_agent.Anthropic")
    def test_get_tools(self, mock_anthropic):
        """도구 정의 반환"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()
        tools = agent.get_tools()

        tool_names = [t["name"] for t in tools]
        assert "fetch_sensor_history" in tool_names
        assert "run_rhai_engine" in tool_names
        assert "query_rag_knowledge" in tool_names
        assert "get_line_status" in tool_names
        assert "get_available_lines" in tool_names

    @patch("app.agents.base_agent.Anthropic")
    @patch("app.agents.judgment_agent.get_db_context")
    def test_fetch_sensor_history(self, mock_db_context, mock_anthropic):
        """센서 히스토리 조회"""
        from app.agents.judgment_agent import JudgmentAgent

        # Mock DB
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        agent = JudgmentAgent()
        result = agent.execute_tool("fetch_sensor_history", {
            "sensor_type": "temperature",
            "line_code": "LINE_A",
            "hours": 24,
            "limit": 100
        })

        assert result["success"] is True
        assert "data" in result

    @patch("app.agents.base_agent.Anthropic")
    def test_query_rag_knowledge(self, mock_anthropic):
        """RAG 지식 검색 (플레이스홀더)"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()
        result = agent.execute_tool("query_rag_knowledge", {
            "query": "온도 임계값",
            "top_k": 3
        })

        assert result["success"] is True
        assert "documents" in result
        assert "note" in result  # MVP placeholder note

    @patch("app.agents.base_agent.Anthropic")
    @patch("app.agents.judgment_agent.get_db_context")
    def test_get_available_lines(self, mock_db_context, mock_anthropic):
        """가용 라인 목록 조회"""
        from app.agents.judgment_agent import JudgmentAgent

        # Mock DB - 빈 결과
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        agent = JudgmentAgent()
        result = agent.execute_tool("get_available_lines", {})

        assert result["success"] is True
        assert "lines" in result
        # 기본값 반환
        assert len(result["lines"]) == 4

    @patch("app.agents.base_agent.Anthropic")
    def test_get_recommendation(self, mock_anthropic):
        """추천 생성"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()

        # CRITICAL 상태
        rec = agent._get_recommendation("CRITICAL", [
            {"status": "CRITICAL", "message": "온도 이상"}
        ])
        assert "즉시 점검" in rec

        # WARNING 상태
        rec = agent._get_recommendation("WARNING", [
            {"status": "WARNING", "message": "압력 주의"}
        ])
        assert "주의 관찰" in rec

        # NORMAL 상태
        rec = agent._get_recommendation("NORMAL", [])
        assert "정상" in rec

    @patch("app.agents.base_agent.Anthropic")
    def test_generate_rhai_script_threshold(self, mock_anthropic):
        """Rhai 스크립트 생성 - 임계값 조건"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()
        script = agent._generate_rhai_script(
            condition_type="threshold",
            sensor_type="temperature",
            operator=">",
            threshold_value=80.0,
            action_type="alert",
            action_message="온도 경고"
        )

        assert "temperature" in script
        assert "80" in script
        assert "alert" in script

    @patch("app.agents.base_agent.Anthropic")
    def test_generate_rhai_script_range(self, mock_anthropic):
        """Rhai 스크립트 생성 - 범위 조건"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()
        script = agent._generate_rhai_script(
            condition_type="range",
            sensor_type="humidity",
            operator=">",
            threshold_value=30.0,
            threshold_value_2=70.0,
            action_type="warning"
        )

        assert "humidity" in script
        assert "30" in script
        assert "70" in script


class TestWorkflowPlannerAgent:
    """WorkflowPlannerAgent 테스트"""

    @patch("app.agents.base_agent.Anthropic")
    def test_init(self, mock_anthropic):
        """초기화"""
        from app.agents.workflow_planner import WorkflowPlannerAgent

        agent = WorkflowPlannerAgent()

        assert agent.name == "WorkflowPlannerAgent"
        assert agent.action_catalog is not None

    @patch("app.agents.base_agent.Anthropic")
    def test_get_tools(self, mock_anthropic):
        """도구 정의"""
        from app.agents.workflow_planner import WorkflowPlannerAgent

        agent = WorkflowPlannerAgent()
        tools = agent.get_tools()

        tool_names = [t["name"] for t in tools]
        assert "create_workflow" in tool_names

    @patch("app.agents.base_agent.Anthropic")
    def test_load_action_catalog(self, mock_anthropic):
        """액션 카탈로그 로드"""
        from app.agents.workflow_planner import WorkflowPlannerAgent

        agent = WorkflowPlannerAgent()
        catalog = agent._load_action_catalog()

        assert "notification" in catalog
        assert "data" in catalog
        assert "control" in catalog
        assert "analysis" in catalog

    @patch("app.agents.base_agent.Anthropic")
    def test_search_action_catalog(self, mock_anthropic):
        """액션 카탈로그 검색"""
        from app.agents.workflow_planner import WorkflowPlannerAgent

        agent = WorkflowPlannerAgent()

        # slack 검색
        result = agent._search_action_catalog("slack")
        assert result["success"] is True
        assert len(result["actions"]) > 0

        # 전체 카테고리 검색
        result = agent._search_action_catalog("", category="notification")
        assert result["success"] is True

    @patch("app.agents.base_agent.Anthropic")
    def test_generate_workflow_dsl(self, mock_anthropic):
        """워크플로우 DSL 생성"""
        from app.agents.workflow_planner import WorkflowPlannerAgent

        agent = WorkflowPlannerAgent()
        result = agent._generate_workflow_dsl(
            "온도가 80도 넘으면 알림",
            ["send_slack_notification"]
        )

        assert result["success"] is True
        assert "workflow_dsl" in result
        assert "name" in result["workflow_dsl"]
        assert "trigger" in result["workflow_dsl"]
        assert "nodes" in result["workflow_dsl"]

    @patch("app.agents.base_agent.Anthropic")
    def test_validate_node_schema_valid(self, mock_anthropic):
        """워크플로우 스키마 검증 - 유효"""
        from app.agents.workflow_planner import WorkflowPlannerAgent

        agent = WorkflowPlannerAgent()
        dsl = {
            "name": "Test Workflow",
            "trigger": {"type": "event", "config": {}},
            "nodes": [
                {"id": "node_1", "type": "condition", "config": {}}
            ]
        }

        result = agent._validate_node_schema(dsl)
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    @patch("app.agents.base_agent.Anthropic")
    def test_validate_node_schema_invalid(self, mock_anthropic):
        """워크플로우 스키마 검증 - 무효"""
        from app.agents.workflow_planner import WorkflowPlannerAgent

        agent = WorkflowPlannerAgent()

        # 필수 필드 누락
        dsl = {"name": "Test"}
        result = agent._validate_node_schema(dsl)
        assert result["valid"] is False
        assert len(result["errors"]) > 0

        # 잘못된 트리거 타입
        dsl = {
            "name": "Test",
            "trigger": {"type": "invalid"},
            "nodes": []
        }
        result = agent._validate_node_schema(dsl)
        assert result["valid"] is False


class TestBIPlannerAgent:
    """BIPlannerAgent 테스트"""

    @patch("app.agents.base_agent.Anthropic")
    def test_init(self, mock_anthropic):
        """초기화"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()
        assert agent.name == "BIPlannerAgent"

    @patch("app.agents.base_agent.Anthropic")
    def test_get_tools(self, mock_anthropic):
        """도구 정의"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()
        tools = agent.get_tools()

        tool_names = [t["name"] for t in tools]
        assert "get_table_schema" in tool_names
        assert "execute_safe_sql" in tool_names
        assert "generate_chart_config" in tool_names

    @patch("app.agents.base_agent.Anthropic")
    @patch("app.agents.bi_planner.get_table_schema")
    def test_get_table_schema(self, mock_get_schema, mock_anthropic):
        """테이블 스키마 조회"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_get_schema.return_value = {
            "columns": [
                {"name": "id", "type": "uuid"},
                {"name": "value", "type": "float"}
            ]
        }

        agent = BIPlannerAgent()
        result = agent.execute_tool("get_table_schema", {
            "table_name": "sensor_data",
            "schema": "core"
        })

        assert result["success"] is True
        assert "columns" in result

    @patch("app.agents.base_agent.Anthropic")
    def test_execute_safe_sql_without_tenant_id(self, mock_anthropic):
        """tenant_id 없는 SQL 거부"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()
        result = agent.execute_tool("execute_safe_sql", {
            "sql_query": "SELECT * FROM sensor_data"
        })

        assert result["success"] is False
        assert "tenant_id" in result["error"]

    @patch("app.agents.base_agent.Anthropic")
    @patch("app.agents.bi_planner.execute_safe_sql")
    def test_execute_safe_sql_with_tenant_id(self, mock_exec_sql, mock_anthropic):
        """tenant_id 포함 SQL 실행"""
        from app.agents.bi_planner import BIPlannerAgent

        mock_exec_sql.return_value = [
            {"id": "1", "value": 25.5}
        ]

        agent = BIPlannerAgent()
        result = agent.execute_tool("execute_safe_sql", {
            "sql_query": "SELECT * FROM sensor_data WHERE tenant_id = :tid",
            "params": {"tid": "test-tenant"}
        })

        assert result["success"] is True
        assert result["row_count"] == 1

    @patch("app.agents.base_agent.Anthropic")
    def test_generate_chart_config_line(self, mock_anthropic):
        """라인 차트 설정 생성"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()
        data = [
            {"date": "2024-01-01", "value": 10},
            {"date": "2024-01-02", "value": 20}
        ]

        result = agent.execute_tool("generate_chart_config", {
            "data": data,
            "chart_type": "line",
            "analysis_goal": "추이 분석",
            "x_axis": "date",
            "y_axis": "value"
        })

        assert result["success"] is True
        assert result["config"]["type"] == "line"
        assert result["config"]["xAxis"]["dataKey"] == "date"

    @patch("app.agents.base_agent.Anthropic")
    def test_generate_chart_config_bar(self, mock_anthropic):
        """바 차트 설정 생성"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()
        data = [
            {"category": "A", "count": 100},
            {"category": "B", "count": 200}
        ]

        result = agent.execute_tool("generate_chart_config", {
            "data": data,
            "chart_type": "bar",
            "analysis_goal": "비교 분석",
            "x_axis": "category"
        })

        assert result["success"] is True
        assert result["config"]["type"] == "bar"

    @patch("app.agents.base_agent.Anthropic")
    def test_generate_chart_config_pie(self, mock_anthropic):
        """파이 차트 설정 생성"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()
        data = [
            {"name": "Normal", "value": 80},
            {"name": "Warning", "value": 15},
            {"name": "Critical", "value": 5}
        ]

        result = agent.execute_tool("generate_chart_config", {
            "data": data,
            "chart_type": "pie",
            "analysis_goal": "분포 분석"
        })

        assert result["success"] is True
        assert result["config"]["type"] == "pie"

    @patch("app.agents.base_agent.Anthropic")
    def test_generate_chart_config_empty_data(self, mock_anthropic):
        """빈 데이터 차트 생성 실패"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()
        result = agent.execute_tool("generate_chart_config", {
            "data": [],
            "chart_type": "line",
            "analysis_goal": "test"
        })

        assert result["success"] is False

    @patch("app.agents.base_agent.Anthropic")
    def test_extract_numeric_keys(self, mock_anthropic):
        """숫자 타입 키 추출"""
        from app.agents.bi_planner import BIPlannerAgent

        agent = BIPlannerAgent()
        data = [
            {"date": "2024-01-01", "value": 10, "count": 5, "name": "test"}
        ]

        keys = agent._extract_numeric_keys(data, exclude=["date"])
        assert "value" in keys
        assert "count" in keys
        assert "name" not in keys
        assert "date" not in keys


class TestLearningAgent:
    """LearningAgent 테스트"""

    @patch("app.agents.base_agent.Anthropic")
    def test_init(self, mock_anthropic):
        """초기화"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        assert agent.name == "LearningAgent"

    @patch("app.agents.base_agent.Anthropic")
    def test_get_tools(self, mock_anthropic):
        """도구 정의"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        tools = agent.get_tools()

        tool_names = [t["name"] for t in tools]
        assert "analyze_feedback_logs" in tool_names
        assert "propose_new_rule" in tool_names
        assert "run_zwave_simulation" in tool_names
        assert "get_rule_performance" in tool_names

    @patch("app.agents.base_agent.Anthropic")
    @patch("app.agents.learning_agent.get_db_context")
    def test_analyze_feedback_logs_empty(self, mock_db_context, mock_anthropic):
        """피드백 로그 분석 - 빈 결과"""
        from app.agents.learning_agent import LearningAgent

        # Mock DB - 빈 결과
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        agent = LearningAgent()
        result = agent.execute_tool("analyze_feedback_logs", {
            "feedback_type": "all",
            "days": 7
        })

        assert result["success"] is True
        assert result["total_feedbacks"] == 0

    @patch("app.agents.base_agent.Anthropic")
    def test_extract_patterns(self, mock_anthropic):
        """피드백 패턴 추출"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()

        # Mock 피드백 데이터 - len(word) > 3 조건을 충족하는 키워드 사용
        mock_feedback1 = MagicMock()
        mock_feedback1.feedback_text = "temperature high temperature abnormal temperature warning"
        mock_feedback1.feedback_type = "negative"
        mock_feedback1.corrected_output = None

        mock_feedback2 = MagicMock()
        mock_feedback2.feedback_text = "temperature issue found"
        mock_feedback2.feedback_type = "negative"
        mock_feedback2.corrected_output = None

        mock_feedback3 = MagicMock()
        mock_feedback3.feedback_text = "temperature normal"
        mock_feedback3.feedback_type = "positive"
        mock_feedback3.corrected_output = None

        feedbacks = [mock_feedback1, mock_feedback2, mock_feedback3]
        patterns = agent._extract_patterns(feedbacks, min_occurrences=2)

        # 'temperature' 키워드가 패턴으로 추출되어야 함 (5회 등장)
        keyword_patterns = [p for p in patterns if p["type"] == "keyword"]
        assert len(keyword_patterns) > 0

        # temperature가 패턴에 포함되어야 함
        temp_pattern = [p for p in keyword_patterns if p["value"] == "temperature"]
        assert len(temp_pattern) > 0

    @patch("app.agents.base_agent.Anthropic")
    def test_generate_recommendations(self, mock_anthropic):
        """추천 생성"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()

        patterns = [
            {"type": "keyword", "value": "온도", "occurrences": 5},
            {"type": "correction", "value": "field_change:status", "occurrences": 3}
        ]

        recommendations = agent._generate_recommendations(patterns)
        assert len(recommendations) > 0
        assert "온도" in recommendations[0]

    @patch("app.agents.base_agent.Anthropic")
    def test_run_zwave_simulation(self, mock_anthropic):
        """Z-Wave 시뮬레이션 실행"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        result = agent.execute_tool("run_zwave_simulation", {
            "rule_script": "// test script",
            "scenario": "random",
            "iterations": 10
        })

        assert result["success"] is True
        assert "accuracy" in result
        assert result["iterations"] == 10

    @patch("app.agents.base_agent.Anthropic")
    def test_generate_simulation_data(self, mock_anthropic):
        """시뮬레이션 데이터 생성"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()

        # Normal 시나리오
        data = agent._generate_simulation_data("normal")
        assert 20 <= data["temperature"] <= 70
        assert 2 <= data["pressure"] <= 8

        # Warning 시나리오
        data = agent._generate_simulation_data("warning")
        assert 70 <= data["temperature"] <= 85

        # Critical 시나리오
        data = agent._generate_simulation_data("critical")
        assert 85 <= data["temperature"] <= 120

    @patch("app.agents.base_agent.Anthropic")
    def test_evaluate_rule(self, mock_anthropic):
        """규칙 평가"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()

        # NORMAL 케이스
        result = agent._evaluate_rule("test", {"temperature": 50, "pressure": 5})
        assert result["status"] == "NORMAL"

        # WARNING 케이스
        result = agent._evaluate_rule("test", {"temperature": 75, "pressure": 5})
        assert result["status"] == "WARNING"

        # CRITICAL 케이스
        result = agent._evaluate_rule("test", {"temperature": 85, "pressure": 5})
        assert result["status"] == "CRITICAL"

    @patch("app.agents.base_agent.Anthropic")
    def test_get_expected_outcome(self, mock_anthropic):
        """기대 결과 반환"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()

        assert agent._get_expected_outcome({"temperature": 50}) == "NORMAL"
        assert agent._get_expected_outcome({"temperature": 75}) == "WARNING"
        assert agent._get_expected_outcome({"temperature": 85}) == "CRITICAL"
        assert agent._get_expected_outcome({"pressure": 15}) == "CRITICAL"

    @patch("app.agents.base_agent.Anthropic")
    def test_get_simulation_recommendation(self, mock_anthropic):
        """시뮬레이션 추천"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()

        assert "배포를 권장" in agent._get_simulation_recommendation(0.98)
        assert "양호" in agent._get_simulation_recommendation(0.88)
        assert "낮습니다" in agent._get_simulation_recommendation(0.72)
        assert "재설계" in agent._get_simulation_recommendation(0.50)

    @patch("app.agents.base_agent.Anthropic")
    def test_parse_condition_temperature(self, mock_anthropic):
        """조건 파싱 - 온도"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()

        code = agent._parse_condition("온도가 80도 초과하면")
        assert "temperature" in code
        assert "80" in code
        assert "WARNING" in code

    @patch("app.agents.base_agent.Anthropic")
    def test_parse_condition_pressure(self, mock_anthropic):
        """조건 파싱 - 압력"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()

        code = agent._parse_condition("압력이 100을 넘으면")
        assert "pressure" in code
        assert "100" in code

    @patch("app.agents.base_agent.Anthropic")
    def test_parse_action_notification(self, mock_anthropic):
        """액션 파싱 - 알림"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()

        code = agent._parse_action("슬랙 알림 보내기")
        assert "notification" in code
        assert "slack" in code

    @patch("app.agents.base_agent.Anthropic")
    def test_parse_action_stop(self, mock_anthropic):
        """액션 파싱 - 라인 중지"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()

        code = agent._parse_action("생산 라인 중지")
        assert "control" in code
        assert "stop_line" in code
