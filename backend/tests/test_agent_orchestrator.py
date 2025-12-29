"""
TriFlow AI - Agent Orchestrator Tests
=====================================
Tests for app/services/agent_orchestrator.py
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestAgentOrchestratorInit:
    """AgentOrchestrator 초기화 테스트"""

    def test_orchestrator_init(self):
        """Orchestrator 초기화"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        assert orchestrator is not None
        assert orchestrator.meta_router is not None
        assert orchestrator.agents is not None

    def test_orchestrator_agents_dict(self):
        """에이전트 딕셔너리 확인"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        assert isinstance(orchestrator.agents, dict)
        # 주요 에이전트 확인 (general은 별도 처리됨)
        expected_agents = ["judgment", "bi", "workflow", "learning"]
        for agent_name in expected_agents:
            assert agent_name in orchestrator.agents

    def test_get_agent_status(self):
        """에이전트 상태 조회"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()
        status = orchestrator.get_agent_status()

        assert isinstance(status, dict)
        assert "meta_router" in status
        # 각 에이전트 상태 확인
        assert "judgment" in status
        assert "bi" in status
        assert "workflow" in status
        assert "learning" in status


class TestGenerateGeneralResponse:
    """_generate_general_response 테스트"""

    def test_greeting_response(self):
        """인사말 응답"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result = orchestrator._generate_general_response("안녕하세요", {})

        assert isinstance(result, str)
        assert len(result) > 0

    def test_greeting_variations(self):
        """다양한 인사말"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        greetings = ["안녕", "하이", "반가워", "hello", "hi"]
        for greeting in greetings:
            result = orchestrator._generate_general_response(greeting, {})
            assert isinstance(result, str)

    def test_thanks_response(self):
        """감사 응답"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result = orchestrator._generate_general_response("고마워", {})

        assert isinstance(result, str)

    def test_goodbye_response(self):
        """작별 응답"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result = orchestrator._generate_general_response("잘가", {})

        assert isinstance(result, str)

    def test_help_response(self):
        """도움말 응답"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result = orchestrator._generate_general_response("도움말", {})

        assert isinstance(result, str)

    def test_intro_response(self):
        """자기소개 응답"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result = orchestrator._generate_general_response("넌 누구야?", {})

        assert isinstance(result, str)

    def test_unknown_input_response(self):
        """알 수 없는 입력"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result = orchestrator._generate_general_response("xyz abc 123", {})

        assert isinstance(result, str)

    def test_positive_response(self):
        """긍정 확인 응답"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result = orchestrator._generate_general_response("네", {})
        assert isinstance(result, str)

    def test_negative_response(self):
        """부정 확인 응답"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result = orchestrator._generate_general_response("아니요", {})
        assert isinstance(result, str)

    def test_offtopic_response(self):
        """범위 외 질문 응답"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result = orchestrator._generate_general_response("오늘 날씨 어때?", {})
        assert isinstance(result, str)


class TestGetToolChoice:
    """_get_tool_choice 테스트"""

    def test_tool_choice_for_judgment(self):
        """판단 에이전트 도구 선택"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result = orchestrator._get_tool_choice("judgment", "LINE_A 온도 판단해줘")

        assert result is None or isinstance(result, (str, dict))

    def test_tool_choice_for_bi(self):
        """BI 에이전트 도구 선택 - 분석 요청"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result = orchestrator._get_tool_choice("bi", "이번 달 생산량 분석해줘")

        # 분석 키워드가 있으면 tool 호출 강제
        assert result == {"type": "any"}

    def test_tool_choice_for_workflow(self):
        """워크플로우 에이전트 도구 선택"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result = orchestrator._get_tool_choice("workflow", "알림 워크플로우 만들어줘")

        assert result == {"type": "any"}

    def test_tool_choice_for_workflow_complex(self):
        """복잡 워크플로우 도구 선택"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        # 복잡 패턴 2개 이상
        result = orchestrator._get_tool_choice("workflow", "온도가 80도 이상이면 알림 보내고, 그리고 90도 넘으면 긴급 알림")

        assert result == {"type": "tool", "name": "create_complex_workflow"}

    def test_tool_choice_for_learning(self):
        """러닝 에이전트 도구 선택 - 룰셋 생성"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result = orchestrator._get_tool_choice("learning", "룰셋 생성해줘")

        assert result == {"type": "tool", "name": "create_ruleset"}

    def test_tool_choice_no_match(self):
        """매칭 없는 경우"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result = orchestrator._get_tool_choice("judgment", "일반 질문")

        assert result is None


class TestIsParameterRequest:
    """_is_parameter_request 테스트"""

    def test_parameter_request_detection(self):
        """파라미터 요청 감지 - True 케이스"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        # request_parameters tool call이 있는 결과
        result = {
            "tool_calls": [
                {
                    "tool": "request_parameters",
                    "result": {
                        "type": "parameter_request",
                        "parameters": [{"key": "channel", "label": "채널"}],
                    },
                }
            ]
        }

        assert orchestrator._is_parameter_request(result) is True

    def test_non_parameter_request(self):
        """파라미터 요청이 아닌 경우"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result = {"tool_calls": [], "response": "응답"}

        assert orchestrator._is_parameter_request(result) is False

    def test_parameter_request_wrong_type(self):
        """파라미터 요청 - type이 다른 경우"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result = {
            "tool_calls": [
                {
                    "tool": "request_parameters",
                    "result": {"type": "other_type"},
                }
            ]
        }

        assert orchestrator._is_parameter_request(result) is False


class TestHandleParameterRequest:
    """_handle_parameter_request 테스트"""

    def test_handle_parameter_request_basic(self):
        """기본 파라미터 요청 처리"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result = {
            "tool_calls": [
                {
                    "tool": "request_parameters",
                    "result": {
                        "type": "parameter_request",
                        "parameters": [{"key": "channel", "label": "채널"}],
                        "message": "채널을 알려주세요",
                        "workflow_context": {"name": "test"},
                    },
                }
            ]
        }

        response = orchestrator._handle_parameter_request(
            "test-session",
            result,
            "WorkflowPlannerAgent",
            {"target_agent": "workflow"},
        )

        assert response is not None
        assert "response" in response
        # 세션에 파라미터가 저장되었는지 확인
        assert "test-session" in orchestrator._pending_parameters


class TestParseUserParameters:
    """_parse_user_parameters 테스트"""

    def test_parse_simple_values(self):
        """단순 값 파싱"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        # 세션에 파라미터 설정
        orchestrator._pending_parameters["test-session"] = {
            "parameters": [
                {"key": "channel", "label": "채널"},
                {"key": "threshold", "label": "임계값"},
            ],
            "workflow_context": None,
        }

        result = orchestrator._parse_user_parameters("test-session", "alerts, 80")

        assert result is not None
        assert result["channel"] == "#alerts"
        assert result["threshold"] == "80"
        # 사용 후 삭제 확인
        assert "test-session" not in orchestrator._pending_parameters

    def test_parse_no_pending_params(self):
        """대기 파라미터 없는 경우"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result = orchestrator._parse_user_parameters("non-existent", "test")

        assert result is None

    def test_parse_empty_params_list(self):
        """빈 파라미터 목록"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        orchestrator._pending_parameters["test-session"] = {
            "parameters": [],
            "workflow_context": None,
        }

        result = orchestrator._parse_user_parameters("test-session", "test")

        assert result is None


class TestDetectTextParameterRequest:
    """_detect_text_parameter_request 테스트"""

    def test_detect_text_params(self):
        """텍스트에서 파라미터 감지"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        text = """다음 정보를 알려주세요:
        1. **Slack 채널**: 알림을 받을 채널
        2. **장비 ID**: 모니터링할 장비
        """

        result = orchestrator._detect_text_parameter_request(text)

        assert result is not None
        assert len(result) == 2
        assert result[0]["key"] == "channel"
        assert result[1]["key"] == "equipment_id"

    def test_detect_no_params(self):
        """파라미터 없는 경우"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result = orchestrator._detect_text_parameter_request("안녕하세요")

        assert result is None

    def test_detect_no_ask_pattern(self):
        """되묻기 패턴 없는 경우"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        text = """1. **Slack 채널**: 테스트"""

        result = orchestrator._detect_text_parameter_request(text)

        # 되묻기 패턴이 없으면 None
        assert result is None


class TestFormatResponse:
    """_format_response 테스트"""

    def test_format_response_basic(self):
        """기본 응답 포맷"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result_input = {"response": "테스트 응답", "tool_calls": []}
        result = orchestrator._format_response(result_input, "JudgmentAgent")

        assert isinstance(result, dict)
        assert "response" in result
        assert result["agent_name"] == "JudgmentAgent"
        assert "tool_calls" in result
        assert "iterations" in result

    def test_format_response_with_tool_calls(self):
        """tool_calls 포함 응답 포맷"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result_input = {
            "response": "분석 완료",
            "tool_calls": [
                {
                    "tool": "execute_safe_sql",
                    "input": {"query": "SELECT *"},
                    "result": {"success": True},
                }
            ],
            "iterations": 2,
        }
        result = orchestrator._format_response(
            result_input,
            "BIPlannerAgent",
            routing_info={"target_agent": "bi"}
        )

        assert isinstance(result, dict)
        assert len(result["tool_calls"]) == 1
        assert result["iterations"] == 2
        assert result["routing_info"]["target_agent"] == "bi"

    def test_format_response_with_routing_info(self):
        """라우팅 정보 포함 응답"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result_input = {"response": "워크플로우 생성됨"}
        routing_info = {"target_agent": "workflow", "v7_intent": "WORKFLOW_CREATE"}

        result = orchestrator._format_response(
            result_input,
            "WorkflowPlannerAgent",
            routing_info=routing_info
        )

        assert result["routing_info"] == routing_info


class TestExtractResponseData:
    """_extract_response_data 테스트"""

    def test_extract_non_bi_agent(self):
        """BI 에이전트가 아닌 경우"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result = orchestrator._extract_response_data(
            {"tool_calls": []},
            "JudgmentAgent"
        )

        assert result is None

    def test_extract_bi_agent_no_tool_calls(self):
        """BI 에이전트 - tool_calls 없음"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result = orchestrator._extract_response_data(
            {"response": "테스트"},
            "BIPlannerAgent"
        )

        assert result is None

    def test_extract_bi_agent_insight(self):
        """BI 에이전트 - 인사이트 추출"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result_input = {
            "tool_calls": [
                {
                    "tool": "generate_insight",
                    "result": {
                        "success": True,
                        "insight": {
                            "title": "생산량 분석",
                            "summary": "이번 달 생산량이 10% 증가",
                            "facts": ["fact1"],
                            "reasoning": {},
                            "actions": [],
                        },
                        "insight_id": "insight-123",
                    },
                }
            ]
        }

        result = orchestrator._extract_response_data(result_input, "BIPlannerAgent")

        assert result is not None
        assert result["title"] == "생산량 분석"
        assert result["insight_id"] == "insight-123"

    def test_extract_bi_agent_table_data(self):
        """BI 에이전트 - 테이블 데이터 추출"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result_input = {
            "tool_calls": [
                {
                    "tool": "execute_safe_sql",
                    "result": {
                        "success": True,
                        "columns": ["date", "value"],
                        "rows": [["2024-01-01", 100]],
                        "row_count": 1,
                    },
                }
            ]
        }

        result = orchestrator._extract_response_data(result_input, "BIPlannerAgent")

        assert result is not None
        assert "table_data" in result
        assert result["table_data"]["row_count"] == 1

    def test_extract_bi_agent_chart_config(self):
        """BI 에이전트 - 차트 설정 추출"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result_input = {
            "tool_calls": [
                {
                    "tool": "generate_chart_config",
                    "result": {
                        "success": True,
                        "config": {"type": "line", "data": {}},
                    },
                }
            ]
        }

        result = orchestrator._extract_response_data(result_input, "BIPlannerAgent")

        assert result is not None
        assert "charts" in result
        assert result["charts"][0]["type"] == "line"


class TestRouteHybrid:
    """_route_hybrid 테스트"""

    def test_route_hybrid_judgment(self):
        """판단 요청 하이브리드 라우팅 - 규칙 기반"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        # 명확한 패턴으로 규칙 기반 라우팅 테스트
        result = orchestrator._route_hybrid("LINE_A 온도 상태 판단해줘", {})

        assert isinstance(result, dict)
        assert "target_agent" in result

    def test_route_hybrid_bi(self):
        """BI 요청 하이브리드 라우팅"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result = orchestrator._route_hybrid("이번 달 생산량 분석해줘", {})

        assert isinstance(result, dict)
        assert "target_agent" in result

    def test_route_hybrid_workflow(self):
        """워크플로우 요청 라우팅"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result = orchestrator._route_hybrid("온도 알림 워크플로우 만들어줘", {})

        assert isinstance(result, dict)
        assert "target_agent" in result


class TestRoute:
    """_route 테스트 (레거시)"""

    def test_route_simple(self):
        """단순 라우팅"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result = orchestrator._route("LINE_A 상태 확인", {})

        assert isinstance(result, dict)

    def test_route_with_context(self):
        """컨텍스트 포함 라우팅"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result = orchestrator._route(
            "상태 확인",
            context={"line_code": "LINE_A"}
        )

        assert isinstance(result, dict)


class TestExecuteSubAgent:
    """_execute_sub_agent 테스트"""

    def test_execute_judgment_agent(self):
        """판단 에이전트 실행"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        with patch.object(
            orchestrator.agents["judgment"],
            "run"
        ) as mock_run:
            mock_run.return_value = {"response": "정상", "tool_calls": []}

            result = orchestrator._execute_sub_agent(
                target_agent="judgment",
                message="LINE_A 온도 상태",
                context={},
                routing_info={"target_agent": "judgment"},
                original_message="LINE_A 온도 상태 판단해줘",
            )

            assert result is not None
            assert "response" in result

    def test_execute_bi_agent(self):
        """BI 에이전트 실행"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        with patch.object(
            orchestrator.agents["bi"],
            "run"
        ) as mock_run:
            mock_run.return_value = {"response": "분석 완료", "tool_calls": []}

            result = orchestrator._execute_sub_agent(
                target_agent="bi",
                message="생산량 분석",
                context={},
                routing_info={"target_agent": "bi"},
                original_message="생산량 분석해줘",
            )

            assert result is not None

    def test_execute_workflow_agent(self):
        """워크플로우 에이전트 실행"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        with patch.object(
            orchestrator.agents["workflow"],
            "run"
        ) as mock_run:
            mock_run.return_value = {"response": "워크플로우 생성됨", "tool_calls": []}

            result = orchestrator._execute_sub_agent(
                target_agent="workflow",
                message="알림 워크플로우",
                context={},
                routing_info={"target_agent": "workflow"},
                original_message="알림 워크플로우 만들어줘",
            )

            assert result is not None

    def test_execute_with_parsed_params(self):
        """파싱된 파라미터 포함 실행"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        # 세션에 pending params 설정
        orchestrator._pending_parameters["test-session"] = {
            "parameters": [{"key": "channel", "label": "채널"}],
            "workflow_context": None,
        }

        with patch.object(
            orchestrator.agents["workflow"],
            "run"
        ) as mock_run:
            mock_run.return_value = {"response": "완료", "tool_calls": []}

            result = orchestrator._execute_sub_agent(
                target_agent="workflow",
                message="테스트",
                context={"session_id": "test-session"},
                routing_info={"target_agent": "workflow"},
                original_message="alerts",
            )

            assert result is not None


class TestProcess:
    """process 메서드 테스트"""

    def test_process_greeting(self):
        """인사말 처리"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result = orchestrator.process("안녕하세요")

        assert result is not None
        assert isinstance(result, dict)
        assert "response" in result

    def test_process_with_tenant_id(self):
        """테넌트 ID 포함 처리"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        result = orchestrator.process(
            "안녕하세요",
            tenant_id="tenant-123"
        )

        assert result is not None

    def test_process_to_sub_agent(self):
        """서브 에이전트로 라우팅"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        with patch.object(
            orchestrator,
            "_execute_sub_agent"
        ) as mock_execute:
            mock_execute.return_value = {
                "response": "분석 완료",
                "agent_name": "BIPlannerAgent",
                "tool_calls": [],
            }

            # 규칙 기반 라우팅이 bi로 가도록
            with patch.object(
                orchestrator,
                "_route_hybrid"
            ) as mock_route:
                mock_route.return_value = {"target_agent": "bi", "processed_request": "분석"}

                result = orchestrator.process("이번 달 생산량 분석해줘")

                assert result is not None


class TestAgentSelection:
    """에이전트 선택 로직 테스트"""

    def test_get_agent_by_name(self):
        """이름으로 에이전트 조회"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        judgment_agent = orchestrator.agents.get("judgment")
        bi_agent = orchestrator.agents.get("bi")
        workflow_agent = orchestrator.agents.get("workflow")
        learning_agent = orchestrator.agents.get("learning")

        assert judgment_agent is not None
        assert bi_agent is not None
        assert workflow_agent is not None
        assert learning_agent is not None

    def test_agent_names(self):
        """에이전트 이름 확인"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        for name, agent in orchestrator.agents.items():
            assert hasattr(agent, "name")


class TestPendingParameters:
    """pending parameters 관리 테스트"""

    def test_pending_parameters_storage(self):
        """pending parameters 저장"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        orchestrator._pending_parameters["session-1"] = {
            "parameters": [{"key": "channel", "label": "채널"}],
            "workflow_context": {"name": "test"},
        }

        assert "session-1" in orchestrator._pending_parameters
        assert len(orchestrator._pending_parameters["session-1"]["parameters"]) == 1

    def test_pending_parameters_cleanup(self):
        """pending parameters 정리"""
        from app.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        orchestrator._pending_parameters["session-1"] = {
            "parameters": [{"key": "channel", "label": "채널"}],
            "workflow_context": None,
        }

        # 파싱 후 삭제 확인
        orchestrator._parse_user_parameters("session-1", "alerts")

        assert "session-1" not in orchestrator._pending_parameters
