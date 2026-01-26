"""
Agent Orchestrator Service
에이전트 체인 오케스트레이션 - MetaRouter → Sub-Agent 자동 연결
"""
import logging
from typing import Any, Dict, List, Optional

from app.agents import (
    MetaRouterAgent,
    JudgmentAgent,
    WorkflowPlannerAgent,
    BIPlannerAgent,
    LearningAgent,
)

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """
    에이전트 오케스트레이터

    사용자 요청을 MetaRouter로 분류한 후,
    적절한 Sub-Agent를 자동으로 호출하여 응답을 생성합니다.

    지원 에이전트:
        - judgment: 센서 데이터 분석 + Rhai 룰 엔진
        - workflow: 워크플로우 DSL 생성
        - bi: Text-to-SQL + 차트 생성
        - learning: 피드백 분석 + 규칙 제안
        - general: 일반 응답 (MetaRouter 직접 응답)
    """

    def __init__(self):
        """에이전트 인스턴스 초기화 (싱글톤 패턴)"""
        self.meta_router = MetaRouterAgent()
        self.agents = {
            "judgment": JudgmentAgent(),
            "workflow": WorkflowPlannerAgent(),
            "bi": BIPlannerAgent(),
            "learning": LearningAgent(),
        }
        # 세션별 pending_parameters 저장 (하이브리드 파라미터 수집용)
        # 키: session_id, 값: {"parameters": [...], "workflow_context": {...}}
        self._pending_parameters: Dict[str, Dict[str, Any]] = {}
        logger.info("AgentOrchestrator initialized with 5 agents")

    def get_agent_status(self) -> Dict[str, Any]:
        """모든 에이전트 상태 조회"""
        status = {
            "meta_router": {
                "name": self.meta_router.name,
                "model": self.meta_router.model,
                "available": True,
            }
        }

        for name, agent in self.agents.items():
            status[name] = {
                "name": agent.name,
                "model": agent.model,
                "available": True,
            }

        return status

    def process(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
        user_role: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        사용자 요청 처리 (전체 파이프라인)

        Args:
            message: 사용자 메시지
            context: 추가 컨텍스트 (선택)
            tenant_id: 테넌트 ID (선택)
            user_role: 사용자 역할 (권한 체크용, 선택)

        Returns:
            {
                "response": "최종 응답",
                "agent_name": "실행된 에이전트 이름",
                "tool_calls": [...],
                "iterations": 반복 횟수,
                "routing_info": {...}
            }
        """
        context = context or {}
        if tenant_id:
            context["tenant_id"] = tenant_id

        logger.info(f"[Orchestrator] Processing: {message[:100]}...")

        # Step 1: 하이브리드 라우팅 (규칙 기반 우선 → LLM fallback)
        routing_info = self._route_hybrid(message, context, user_role)
        target_agent = routing_info.get("target_agent", "general")

        logger.info(
            f"[Orchestrator] Routed to: {target_agent} "
            f"(source: {routing_info.get('context', {}).get('classification_source', 'unknown')})"
        )

        # Step 2: 권한 에러 처리
        if target_agent == "error":
            error_msg = routing_info.get("error", "권한이 부족합니다.")
            logger.warning(f"[Orchestrator] Permission denied: {error_msg}")
            return self._format_response(
                result={"response": error_msg},
                agent_name="MetaRouterAgent",
                routing_info=routing_info,
                model=self.meta_router.get_model(context),
            )

        # Step 3: Sub-Agent 실행
        if target_agent in self.agents:
            return self._execute_sub_agent(
                target_agent=target_agent,
                message=routing_info.get("processed_request", message),
                context=context,
                routing_info=routing_info,
                original_message=message,
            )

        # Step 4: general인 경우 기본 응답 생성
        general_response = self._generate_general_response(message, routing_info)
        return self._format_response(
            result={"response": general_response},
            agent_name="MetaRouterAgent",
            routing_info=routing_info,
            model=self.meta_router.get_model(context),
        )

    def _route_hybrid(
        self,
        message: str,
        context: Dict[str, Any],
        user_role: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        하이브리드 라우팅 (규칙 기반 우선 → LLM fallback)

        1차: 규칙 기반 분류 시도 (IntentClassifier)
        2차: 규칙 매칭 실패 시 LLM 분류 (MetaRouter)

        Args:
            message: 사용자 메시지
            context: 컨텍스트
            user_role: 사용자 역할 (권한 체크용)

        Returns:
            라우팅 정보 (권한 부족 시 error 필드 포함)
        """
        # Role을 Enum으로 변환 (user_role이 문자열인 경우)
        from app.services.rbac_service import Role

        role_enum = None
        if user_role:
            try:
                role_enum = Role(user_role)
            except ValueError:
                logger.warning(f"Invalid user_role: {user_role}, defaulting to None")

        # MetaRouter의 route_with_hybrid 사용 (권한 체크 포함)
        routing_info = self.meta_router.route_with_hybrid(
            user_input=message,
            llm_result=None,
            user_role=role_enum,
            context=context,
        )

        # LLM fallback이 필요한 경우 (규칙 매칭 실패)
        if not routing_info.get("v7_intent") and routing_info.get("context", {}).get("classification_source") == "fallback":
            logger.info(f"[Orchestrator] LLM routing fallback for: {message[:30]}...")
            llm_result = self.meta_router.run(
                user_message=message,
                context=context,
            )
            routing_info = self.meta_router.route_with_hybrid(
                user_input=message,
                llm_result=llm_result,
                user_role=role_enum,
                context=context,
            )

        return routing_info

    def _route(
        self,
        message: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """MetaRouter로 라우팅 (레거시, 하위 호환성)"""
        return self.meta_router.run(
            user_message=message,
            context=context,
        )

    def _execute_sub_agent(
        self,
        target_agent: str,
        message: str,
        context: Dict[str, Any],
        routing_info: Dict[str, Any],
        original_message: str,
    ) -> Dict[str, Any]:
        """Sub-Agent 실행 (하이브리드 파라미터 수집 지원)"""
        agent = self.agents[target_agent]

        # 세션 ID 추출 (없으면 기본값 사용)
        session_id = context.get("session_id", "default")

        # 1. Pending parameters가 있고, 사용자가 답변했다면 파싱
        if session_id in self._pending_parameters:
            parsed_params = self._parse_user_parameters(session_id, original_message)
            if parsed_params:
                context["parsed_parameters"] = parsed_params
                logger.info(f"[Orchestrator] Parsed parameters: {parsed_params}")

        # 컨텍스트 병합 (원본 + 라우팅 컨텍스트)
        merged_context = {
            **context,
            **routing_info.get("context", {}),
            "slots": routing_info.get("slots", {}),
        }

        # 에이전트별 특수 처리
        tool_choice = self._get_tool_choice(target_agent, original_message)

        # 복잡한 워크플로우는 iteration이 더 필요 (되묻기 + DSL 생성)
        max_iter = 10 if target_agent == "workflow" else 5

        logger.info(f"[Orchestrator] Executing {agent.name} (max_iterations={max_iter})")

        result = agent.run(
            user_message=message,
            context=merged_context,
            max_iterations=max_iter,
            tool_choice=tool_choice,
        )

        # 2. 결과가 parameter_request Tool 호출인지 확인
        if self._is_parameter_request(result):
            used_model = agent.get_model(merged_context)
            return self._handle_parameter_request(session_id, result, agent.name, routing_info, model=used_model)

        # 3. AI가 Tool 없이 텍스트로 되묻기를 생성한 경우 감지
        # (예: "다음 정보를 알려주세요:\n1. **Slack 채널**: ...")
        if target_agent == "workflow" and not result.get("tool_calls"):
            text_params = self._detect_text_parameter_request(result.get("response", ""))
            if text_params:
                # 텍스트에서 추출한 파라미터 목록을 세션에 저장
                self._pending_parameters[session_id] = {
                    "parameters": text_params,
                    "workflow_context": None,
                }
                logger.info(
                    f"[Orchestrator] Detected text parameter request, stored {len(text_params)} params for session {session_id}"
                )

        # 4. 일반 응답
        # 사용된 모델 정보 가져오기
        used_model = agent.get_model(merged_context)
        logger.info(f"[Orchestrator] Agent {agent.name} used model: {used_model}")
        return self._format_response(
            result=result,
            agent_name=agent.name,
            routing_info=routing_info,
            model=used_model,
        )

    def _generate_general_response(
        self,
        message: str,
        routing_info: Dict[str, Any],
    ) -> str:
        """
        일반 의도(general)에 대한 기본 응답 생성

        Args:
            message: 사용자 메시지
            routing_info: 라우팅 정보

        Returns:
            친화적인 기본 응답 문자열
        """
        msg_lower = message.lower().strip()

        # 인사말 패턴
        greetings = ["안녕", "하이", "헬로", "hello", "hi", "반가", "좋은 아침", "좋은 저녁"]
        if any(g in msg_lower for g in greetings):
            return (
                "안녕하세요! TriFlow AI입니다. 무엇을 도와드릴까요?\n\n"
                "**사용 가능한 기능:**\n"
                "- 센서 데이터 조회 및 분석\n"
                "- 워크플로우 생성\n"
                "- 데이터 시각화 (BI)\n"
                "- 규칙 학습 및 개선"
            )

        # 감사 패턴
        thanks_words = ["고마워", "감사", "thanks", "thank you", "땡큐", "ㄱㅅ", "고맙"]
        if any(t in msg_lower for t in thanks_words):
            return "천만에요! 다른 도움이 필요하시면 말씀해주세요."

        # 작별 인사 패턴
        bye_words = ["잘가", "바이", "bye", "안녕히", "다음에", "나중에", "수고"]
        if any(b in msg_lower for b in bye_words):
            return "안녕히 가세요! 다음에 또 찾아주세요."

        # 도움말 패턴
        help_words = ["도움", "help", "기능", "할 수 있", "뭘 해", "사용법"]
        if any(h in msg_lower for h in help_words):
            return (
                "TriFlow AI는 제조 현장의 데이터를 분석하고 자동화하는 AI 어시스턴트입니다.\n\n"
                "**주요 기능:**\n"
                "1. **센서 데이터 분석** - \"LINE_A 온도 데이터 조회해줘\"\n"
                "2. **워크플로우 생성** - \"온도 이상 시 알림 워크플로우 만들어줘\"\n"
                "3. **데이터 시각화** - \"이번 주 생산량 차트 보여줘\"\n"
                "4. **규칙 학습** - \"최근 알람 패턴 분석해줘\""
            )

        # 자기소개 패턴
        intro_words = ["누구", "소개", "너는", "정체"]
        if any(i in msg_lower for i in intro_words):
            return (
                "저는 **TriFlow AI**입니다. 제조 현장의 스마트 팩토리 데이터를 분석하고 "
                "자동화를 지원하는 AI 어시스턴트입니다.\n\n"
                "센서 데이터 조회, 워크플로우 자동화, 데이터 시각화 등을 도와드릴 수 있습니다."
            )

        # 긍정 확인 패턴 (짧은 단독 응답)
        positive_words = ["응", "어", "네", "예", "그래", "ok", "ㅇㅋ", "좋아", "알겠어", "웅", "넵"]
        if msg_lower in positive_words or (len(msg_lower) <= 4 and any(p == msg_lower for p in positive_words)):
            return "네, 알겠습니다! 추가로 도움이 필요하시면 말씀해주세요."

        # 부정 확인 패턴 (짧은 단독 응답)
        negative_words = ["아니", "아뇨", "no", "놉", "ㄴㄴ", "아니요", "아니야"]
        if msg_lower in negative_words or (len(msg_lower) <= 4 and any(n == msg_lower for n in negative_words)):
            return "알겠습니다. 다른 질문이 있으시면 말씀해주세요."

        # 범위 외 질문 패턴 (날씨, 시간 등)
        offtopic_words = ["날씨", "시간", "weather", "time", "몇시", "몇 시"]
        data_words = ["데이터", "센서", "생산", "워크플로우", "차트"]
        if any(o in msg_lower for o in offtopic_words) and not any(d in msg_lower for d in data_words):
            return (
                "죄송합니다, 저는 제조 현장 데이터 분석 전문 AI라서 "
                "일반 정보는 제공하기 어렵습니다.\n\n"
                "**제가 도와드릴 수 있는 것:**\n"
                "- 센서 데이터 조회 및 분석\n"
                "- 워크플로우 생성\n"
                "- 생산 데이터 시각화"
            )

        # 기본 응답 (특수문자 처리)
        safe_message = message.replace("'", "").replace('"', "")[:50]
        return (
            f"'{safe_message}'에 대해 더 구체적으로 알려주시면 도움드릴 수 있습니다.\n\n"
            "예시:\n"
            "- \"LINE_A 온도 데이터 보여줘\"\n"
            "- \"워크플로우 만들어줘\"\n"
            "- \"이번 달 생산량 차트\""
        )

    def _get_tool_choice(
        self,
        target_agent: str,
        message: str,
    ) -> Optional[Dict[str, Any]]:
        """에이전트별 tool_choice 결정"""
        msg_lower = message.lower()

        # Workflow: 반드시 Tool을 호출하도록 강제
        # - 파라미터 누락 시: request_parameters
        # - 파라미터 완비 시: create_workflow 또는 create_complex_workflow
        if target_agent == "workflow":
            # 복잡한 워크플로우 패턴 감지
            complex_patterns = [
                "이면 ", "면 ", "일 때", "경우",  # 조건 분기
                "그리고", "그러면", "또한", "동시에",  # 다중 액션
                "80도", "90도", "이상이면", "넘으면",  # 다단계 조건 예시
                "if ", "else", "and ", "or ",  # 영문 조건
            ]
            # 복잡 패턴이 2개 이상 매칭되면 complex_workflow 강제
            match_count = sum(1 for p in complex_patterns if p in msg_lower)
            if match_count >= 2:
                return {"type": "tool", "name": "create_complex_workflow"}
            # 그 외: AI가 Tool을 자율 선택하되 반드시 Tool 호출 필요
            # "any"는 Anthropic API에서 "반드시 하나의 tool을 호출해야 함"을 의미
            return {"type": "any"}

        # Learning: 룰셋 생성 요청 감지
        if target_agent == "learning":
            ruleset_keywords = [
                "룰셋", "규칙 만들", "규칙 생성", "판단 규칙",
                "경고", "위험", "임계", "threshold",
                "ruleset", "create rule",
            ]
            if any(kw in msg_lower for kw in ruleset_keywords):
                return {"type": "tool", "name": "create_ruleset"}

        # BI: 데이터 질의 시 반드시 Tool 호출 강제
        if target_agent == "bi":
            # 데이터 질의 키워드 (자연어 패턴 포함)
            data_query_keywords = [
                # 한국어 동사형 패턴
                "알려", "보여", "찾아", "검색", "조회",
                "몇 개", "몇 건", "목록", "리스트",
                # 분석 관련
                "분석", "차트", "그래프", "추이", "데이터", "통계", "트렌드",
                # 센서/생산 데이터
                "센서", "온도", "압력", "생산", "불량",
                # 한국바이오팜 도메인
                "레시피", "제품", "원료", "배합", "비타민", "제형",
                # 영문
                "analyze", "show", "chart", "graph", "data", "trend",
            ]
            if any(kw in msg_lower for kw in data_query_keywords):
                logger.info("[Orchestrator] BI data query detected - forcing tool usage")
                return {"type": "any"}  # 반드시 Tool 호출

        return None

    def _is_parameter_request(self, result: Dict[str, Any]) -> bool:
        """결과가 파라미터 요청인지 확인"""
        for tc in result.get("tool_calls", []):
            if tc.get("tool") == "request_parameters":
                tool_result = tc.get("result", {})
                if isinstance(tool_result, dict) and tool_result.get("type") == "parameter_request":
                    return True
        return False

    def _handle_parameter_request(
        self,
        session_id: str,
        result: Dict[str, Any],
        agent_name: str,
        routing_info: Dict[str, Any],
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """파라미터 요청 처리 - 세션에 저장하고 되묻기 메시지 반환"""
        for tc in result.get("tool_calls", []):
            if tc.get("tool") == "request_parameters":
                tool_result = tc.get("result", {})
                if isinstance(tool_result, dict) and tool_result.get("type") == "parameter_request":
                    params = tool_result.get("parameters", [])
                    workflow_context = tool_result.get("workflow_context")

                    # 세션에 저장
                    self._pending_parameters[session_id] = {
                        "parameters": params,
                        "workflow_context": workflow_context,
                    }

                    logger.info(
                        f"[Orchestrator] Stored {len(params)} pending parameters for session {session_id}"
                    )

                    # 되묻기 메시지 반환
                    message = tool_result.get("message", "추가 정보가 필요합니다.")
                    return self._format_response(
                        result={"response": message},
                        agent_name=agent_name,
                        routing_info=routing_info,
                        model=model,
                    )

        return self._format_response(result, agent_name, routing_info, model=model)

    def _parse_user_parameters(
        self,
        session_id: str,
        user_message: str,
    ) -> Optional[Dict[str, str]]:
        """
        사용자 답변에서 파라미터 파싱 (백엔드 로직)

        사용자가 쉼표로 구분하여 답변한 경우:
        - "prod-alerts, EQ_001, LINE_B"
        - 순서대로 pending_parameters의 key에 매핑

        Args:
            session_id: 세션 ID
            user_message: 사용자 답변 메시지

        Returns:
            파싱된 파라미터 딕셔너리 또는 None
        """
        pending = self._pending_parameters.get(session_id)
        if not pending:
            return None

        params_info = pending.get("parameters", [])
        if not params_info:
            return None

        # 쉼표로 분리
        values = [v.strip() for v in user_message.split(",")]

        # 순서대로 매핑
        result = {}
        for i, param_info in enumerate(params_info):
            if i < len(values):
                key = param_info["key"]
                value = values[i]

                # 채널 앞에 # 추가 (없는 경우)
                if key == "channel" and value and not value.startswith("#"):
                    value = f"#{value}"

                result[key] = value
                logger.info(f"[Orchestrator] Mapped param: {key} = '{value}'")

        # 사용 후 삭제
        del self._pending_parameters[session_id]
        logger.info(f"[Orchestrator] Cleared pending parameters for session {session_id}")

        return result if result else None

    def _detect_text_parameter_request(
        self,
        response_text: str,
    ) -> Optional[List[Dict[str, str]]]:
        """
        AI가 Tool 없이 텍스트로 되묻기를 생성한 경우 파라미터 목록 추출

        패턴 감지:
        - "다음 정보를 알려주세요:" 또는 유사 패턴
        - 번호 매겨진 항목 (1. **라벨**: 설명)

        Returns:
            파라미터 목록 [{"key": ..., "label": ...}] 또는 None
        """
        import re

        # 되묻기 패턴 감지
        ask_patterns = [
            r"다음 정보를 알려주세요",
            r"다음 항목을 알려주세요",
            r"아래 정보가 필요합니다",
            r"Please provide the following",
        ]

        is_asking = any(re.search(p, response_text, re.IGNORECASE) for p in ask_patterns)
        if not is_asking:
            return None

        # 번호 매겨진 항목에서 라벨 추출
        # 패턴: "1. **Slack 채널**:" 또는 "2. **장비 ID**:" 등
        item_pattern = r'\d+\.\s*\*\*([^*]+)\*\*'
        matches = re.findall(item_pattern, response_text)

        if not matches:
            return None

        # 라벨을 key로 변환
        label_to_key = {
            "Slack 채널": "channel",
            "슬랙 채널": "channel",
            "채널": "channel",
            "장비 ID": "equipment_id",
            "장비": "equipment_id",
            "생산 라인": "line_code",
            "생산 라인 코드": "line_code",
            "라인 코드": "line_code",
            "라인": "line_code",
            "이메일": "to",
            "수신자": "to",
            "전화번호": "phone",
            "센서": "sensor_id",
            "센서 ID": "sensor_id",
            "임계값": "threshold",
            "테이블": "table",
            "파일명": "filename",
            "URL": "url",
            "스케줄": "cron",
        }

        params = []
        for label in matches:
            label_clean = label.strip()
            # 라벨에서 key 추출 (매핑 테이블 사용 또는 소문자 변환)
            key = label_to_key.get(label_clean)
            if not key:
                # 매핑에 없으면 라벨을 snake_case로 변환
                key = label_clean.lower().replace(" ", "_").replace("-", "_")

            params.append({"key": key, "label": label_clean})

        logger.info(f"[Orchestrator] Extracted {len(params)} params from text: {params}")
        return params if params else None

    def _format_response(
        self,
        result: Dict[str, Any],
        agent_name: str,
        routing_info: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """응답 포맷팅"""
        logger.debug(f"[Orchestrator] _format_response called with model={model}")
        # BIPlannerAgent 등에서 구조화된 response_data 추출
        response_data = self._extract_response_data(result, agent_name)

        return {
            "response": result.get("response", ""),
            "agent_name": agent_name,
            "model": model,
            "tool_calls": [
                {
                    "tool": tc["tool"],
                    "input": tc["input"],
                    "result": tc["result"],
                }
                for tc in result.get("tool_calls", [])
            ],
            "iterations": result.get("iterations", 1),
            "routing_info": routing_info,
            "response_data": response_data,
        }

    def _extract_response_data(
        self,
        result: Dict[str, Any],
        agent_name: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Agent 결과에서 구조화된 response_data 추출

        BIPlannerAgent의 경우:
        - generate_insight Tool 결과에서 인사이트 데이터 추출
        - execute_safe_sql Tool 결과에서 table_data 추출
        - generate_chart_config Tool 결과에서 차트 설정 추출
        """
        logger.info(f"[Orchestrator] _extract_response_data called: agent_name={agent_name}")

        # BIPlannerAgent만 처리
        if "BIPlanner" not in agent_name:
            logger.info("[Orchestrator] Skipping - not BIPlannerAgent")
            return None

        tool_calls = result.get("tool_calls", [])
        logger.info(f"[Orchestrator] tool_calls count: {len(tool_calls)}")
        if not tool_calls:
            return None

        response_data: Dict[str, Any] = {}

        for tc in tool_calls:
            tool_name = tc.get("tool", "")
            tool_result = tc.get("result", {})
            logger.info(f"[Orchestrator] Processing: tool={tool_name}, result_type={type(tool_result)}, success={tool_result.get('success') if isinstance(tool_result, dict) else 'N/A'}")

            if not isinstance(tool_result, dict):
                continue

            # generate_insight: 인사이트 데이터
            if tool_name == "generate_insight":
                if tool_result.get("success"):
                    insight = tool_result.get("insight", {})
                    response_data.update({
                        "title": insight.get("title"),
                        "summary": insight.get("summary"),
                        "facts": insight.get("facts", []),
                        "reasoning": insight.get("reasoning", {}),
                        "actions": insight.get("actions", []),
                        "insight_id": tool_result.get("insight_id"),
                    })
                    logger.info(f"[Orchestrator] Extracted insight: {insight.get('title')}")

            # execute_safe_sql: 테이블 데이터
            elif tool_name == "execute_safe_sql":
                if tool_result.get("success"):
                    response_data["table_data"] = {
                        "columns": tool_result.get("columns", []),
                        "rows": tool_result.get("rows", []),
                        "row_count": tool_result.get("row_count", 0),
                    }
                    logger.info(f"[Orchestrator] Extracted table_data: {tool_result.get('row_count')} rows")

            # generate_chart_config: 차트 설정
            elif tool_name == "generate_chart_config":
                if tool_result.get("success"):
                    # 결과에서 config 또는 chart_config 키 사용
                    chart_config = tool_result.get("config") or tool_result.get("chart_config", {})
                    if chart_config:
                        if "charts" not in response_data:
                            response_data["charts"] = []
                        response_data["charts"].append(chart_config)
                        logger.info(f"[Orchestrator] Extracted chart_config: {chart_config.get('type')}")

        if response_data:
            logger.info(f"[Orchestrator] Final response_data keys: {list(response_data.keys())}")

        return response_data if response_data else None

    def execute_direct(
        self,
        agent_name: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        특정 에이전트 직접 실행 (MetaRouter 우회)

        Args:
            agent_name: 실행할 에이전트 이름 (judgment, workflow, bi, learning)
            message: 사용자 메시지
            context: 추가 컨텍스트

        Returns:
            에이전트 응답
        """
        if agent_name not in self.agents:
            raise ValueError(f"Unknown agent: {agent_name}")

        agent = self.agents[agent_name]
        context = context or {}

        logger.info(f"[Orchestrator] Direct execution: {agent.name}")

        result = agent.run(
            user_message=message,
            context=context,
        )

        used_model = agent.get_model(context)
        return self._format_response(
            result=result,
            agent_name=agent.name,
            model=used_model,
        )


# 전역 인스턴스 (싱글톤)
orchestrator = AgentOrchestrator()
