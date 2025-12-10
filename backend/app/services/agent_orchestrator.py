"""
Agent Orchestrator Service
에이전트 체인 오케스트레이션 - MetaRouter → Sub-Agent 자동 연결
"""
import logging
from typing import Any, Dict, Optional

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
    ) -> Dict[str, Any]:
        """
        사용자 요청 처리 (전체 파이프라인)

        Args:
            message: 사용자 메시지
            context: 추가 컨텍스트 (선택)
            tenant_id: 테넌트 ID (선택)

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
        routing_info = self._route_hybrid(message, context)
        target_agent = routing_info.get("target_agent", "general")

        logger.info(
            f"[Orchestrator] Routed to: {target_agent} "
            f"(source: {routing_info.get('context', {}).get('classification_source', 'unknown')})"
        )

        # Step 2: Sub-Agent 실행
        if target_agent in self.agents:
            return self._execute_sub_agent(
                target_agent=target_agent,
                message=routing_info.get("processed_request", message),
                context=context,
                routing_info=routing_info,
                original_message=message,
            )

        # Step 3: general인 경우 MetaRouter 응답 반환
        return self._format_response(
            result=routing_info,
            agent_name="MetaRouterAgent",
            routing_info=routing_info,
        )

    def _route_hybrid(
        self,
        message: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        하이브리드 라우팅 (규칙 기반 우선 → LLM fallback)

        1차: 규칙 기반 분류 시도 (IntentClassifier)
        2차: 규칙 매칭 실패 시 LLM 분류 (MetaRouter)
        """
        # 1차: 규칙 기반 분류 시도
        rule_result = self.meta_router.classify_with_rules(message)

        if rule_result and rule_result.confidence >= 0.9:
            # 규칙 기반 분류 성공
            logger.info(
                f"[Orchestrator] Rule-based routing: {message[:30]}... → {rule_result.intent}"
            )
            return {
                "target_agent": rule_result.intent,
                "processed_request": message,
                "context": {
                    "classification_source": "rule_engine",
                    "matched_pattern": rule_result.matched_pattern,
                    "confidence": rule_result.confidence,
                },
                "intent": rule_result.intent,
                "slots": {},
            }

        # 2차: LLM 분류 (규칙 매칭 실패)
        logger.info(f"[Orchestrator] LLM routing fallback for: {message[:30]}...")
        llm_result = self.meta_router.run(
            user_message=message,
            context=context,
        )
        routing_info = self.meta_router.parse_routing_result(llm_result)
        routing_info["context"] = routing_info.get("context", {})
        routing_info["context"]["classification_source"] = "llm"

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
        """Sub-Agent 실행"""
        agent = self.agents[target_agent]

        # 컨텍스트 병합 (원본 + 라우팅 컨텍스트)
        merged_context = {
            **context,
            **routing_info.get("context", {}),
            "slots": routing_info.get("slots", {}),
        }

        # 에이전트별 특수 처리
        tool_choice = self._get_tool_choice(target_agent, original_message)

        logger.info(f"[Orchestrator] Executing {agent.name}")

        result = agent.run(
            user_message=message,
            context=merged_context,
            max_iterations=5,
            tool_choice=tool_choice,
        )

        return self._format_response(
            result=result,
            agent_name=agent.name,
            routing_info=routing_info,
        )

    def _get_tool_choice(
        self,
        target_agent: str,
        message: str,
    ) -> Optional[Dict[str, Any]]:
        """에이전트별 tool_choice 결정"""
        msg_lower = message.lower()

        # Workflow: 워크플로우 생성 강제
        if target_agent == "workflow":
            return {"type": "tool", "name": "create_workflow"}

        # Learning: 룰셋 생성 요청 감지
        if target_agent == "learning":
            ruleset_keywords = [
                "룰셋", "규칙 만들", "규칙 생성", "판단 규칙",
                "경고", "위험", "임계", "threshold",
                "ruleset", "create rule",
            ]
            if any(kw in msg_lower for kw in ruleset_keywords):
                return {"type": "tool", "name": "create_ruleset"}

        return None

    def _format_response(
        self,
        result: Dict[str, Any],
        agent_name: str,
        routing_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """응답 포맷팅"""
        return {
            "response": result.get("response", ""),
            "agent_name": agent_name,
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
        }

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

        return self._format_response(
            result=result,
            agent_name=agent.name,
        )


# 전역 인스턴스 (싱글톤)
orchestrator = AgentOrchestrator()
