"""
Meta Router Agent (V7)
사용자 요청을 분석하여 적절한 Sub-Agent로 라우팅

V7 Intent 체계 지원:
- 14개 V7 Intent 분류
- Route Target 기반 라우팅
- Legacy Intent 하위호환

하이브리드 분류 방식:
1. 규칙 기반 분류 (IntentClassifier) - 명확한 패턴
2. LLM 분류 (기존 방식) - 애매한 경우 fallback
"""
from typing import Any, Dict, List, Optional
import logging
from pathlib import Path

from .base_agent import BaseAgent
from .intent_classifier import IntentClassifier, V7IntentClassifier, ClassificationResult
from .routing_rules import (
    RouteTarget,
    get_all_v7_intents,
)
from app.services.intent_role_mapper import check_intent_permission, get_required_role
from app.services.rbac_service import Role

logger = logging.getLogger(__name__)


class MetaRouterAgent(BaseAgent):
    """
    Meta Router Agent (V7)
    - V7 Intent 분류 (하이브리드: 규칙 기반 + LLM)
    - 슬롯 추출
    - Route Target 기반 Sub-Agent 라우팅
    """

    def __init__(self):
        super().__init__(
            name="MetaRouterAgent",
            model="claude-sonnet-4-5-20250929",
            max_tokens=2048,
        )
        # V7 분류기 초기화
        self.v7_intent_classifier = V7IntentClassifier()
        # Legacy 호환 분류기
        self.intent_classifier = IntentClassifier()

    def get_system_prompt(self) -> str:
        """
        시스템 프롬프트 로드 (prompts/meta_router.md에서)
        """
        prompt_path = Path(__file__).parent.parent / "prompts" / "meta_router.md"
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"Prompt file not found: {prompt_path}, using default")
            return "You are a Meta Router Agent for TriFlow AI with V7 Intent classification."

    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Meta Router Agent의 Tool 정의 (V7 Intent 지원)
        """
        return [
            {
                "name": "classify_v7_intent",
                "description": "사용자 요청의 V7 Intent를 분류합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "v7_intent": {
                            "type": "string",
                            "enum": get_all_v7_intents(),
                            "description": "V7 Intent (14개 중 하나)",
                        },
                        "route_to": {
                            "type": "string",
                            "enum": [rt.value for rt in RouteTarget],
                            "description": "라우팅 대상",
                        },
                        "legacy_intent": {
                            "type": "string",
                            "enum": [
                                "judgment",
                                "workflow",
                                "bi",
                                "learning",
                                "general",
                            ],
                            "description": "Legacy Intent (하위호환)",
                        },
                        "confidence": {
                            "type": "number",
                            "description": "분류 신뢰도 (0.0 ~ 1.0)",
                        },
                        "reason": {
                            "type": "string",
                            "description": "분류 이유",
                        },
                    },
                    "required": ["v7_intent", "route_to", "confidence", "reason"],
                },
            },
            {
                "name": "classify_intent",
                "description": "사용자 요청의 의도(Intent)를 분류합니다 (Legacy).",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "intent": {
                            "type": "string",
                            "enum": [
                                "judgment",
                                "workflow",
                                "bi",
                                "learning",
                                "general",
                            ],
                            "description": "분류된 Intent",
                        },
                        "confidence": {
                            "type": "number",
                            "description": "분류 신뢰도 (0.0 ~ 1.0)",
                        },
                        "reason": {
                            "type": "string",
                            "description": "분류 이유",
                        },
                    },
                    "required": ["intent", "confidence", "reason"],
                },
            },
            {
                "name": "extract_slots",
                "description": "요청에서 필요한 정보(슬롯)를 추출합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "slots": {
                            "type": "object",
                            "description": "추출된 슬롯 정보 (key-value 쌍)",
                        },
                    },
                    "required": ["slots"],
                },
            },
            {
                "name": "route_request",
                "description": "요청을 적절한 Sub-Agent로 라우팅합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "target_agent": {
                            "type": "string",
                            "enum": [
                                "judgment",
                                "workflow",
                                "bi",
                                "learning",
                                "general",
                            ],
                            "description": "라우팅할 대상 Agent",
                        },
                        "processed_request": {
                            "type": "string",
                            "description": "Agent에 전달할 처리된 요청",
                        },
                        "context": {
                            "type": "object",
                            "description": "추가 컨텍스트 정보",
                        },
                    },
                    "required": ["target_agent", "processed_request"],
                },
            },
        ]

    def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """
        Tool 실행
        Meta Router는 Tool 실행 시 단순히 결과를 반환
        실제 라우팅 로직은 run() 메서드에서 처리
        """
        if tool_name == "classify_v7_intent":
            logger.info(f"V7 Intent classified: {tool_input.get('v7_intent')} → {tool_input.get('route_to')}")
            return {
                "success": True,
                "v7_intent": tool_input.get("v7_intent"),
                "route_to": tool_input.get("route_to"),
                "legacy_intent": tool_input.get("legacy_intent"),
                "confidence": tool_input.get("confidence"),
                "reason": tool_input.get("reason"),
            }

        elif tool_name == "classify_intent":
            logger.info(f"Intent classified: {tool_input.get('intent')}")
            return {
                "success": True,
                "intent": tool_input.get("intent"),
                "confidence": tool_input.get("confidence"),
                "reason": tool_input.get("reason"),
            }

        elif tool_name == "extract_slots":
            logger.info(f"Slots extracted: {tool_input.get('slots')}")
            return {
                "success": True,
                "slots": tool_input.get("slots", {}),
            }

        elif tool_name == "route_request":
            logger.info(f"Routing to agent: {tool_input.get('target_agent')}")
            return {
                "success": True,
                "target_agent": tool_input.get("target_agent"),
                "processed_request": tool_input.get("processed_request"),
                "context": tool_input.get("context", {}),
            }

        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    def parse_routing_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Agent 실행 결과에서 라우팅 정보 추출

        Args:
            result: BaseAgent.run()의 결과

        Returns:
            {
                "target_agent": "agent_name",
                "processed_request": "...",
                "context": {...},
                "v7_intent": "...",
                "route_to": "...",
                "legacy_intent": "...",
                "slots": {...}
            }
        """
        routing_info = {
            "target_agent": "general",
            "processed_request": "",
            "context": {},
            "v7_intent": None,
            "route_to": None,
            "legacy_intent": None,
            "intent": None,  # Legacy 호환
            "slots": {},
        }

        for tool_call in result.get("tool_calls", []):
            if tool_call["tool"] == "classify_v7_intent":
                routing_info["v7_intent"] = tool_call["result"].get("v7_intent")
                routing_info["route_to"] = tool_call["result"].get("route_to")
                routing_info["legacy_intent"] = tool_call["result"].get("legacy_intent")
                # Legacy 호환
                routing_info["intent"] = routing_info["legacy_intent"]

            elif tool_call["tool"] == "classify_intent":
                routing_info["intent"] = tool_call["result"].get("intent")
                # V7 Intent가 없으면 Legacy Intent 사용
                if not routing_info["v7_intent"]:
                    routing_info["legacy_intent"] = routing_info["intent"]

            elif tool_call["tool"] == "extract_slots":
                routing_info["slots"] = tool_call["result"].get("slots", {})

            elif tool_call["tool"] == "route_request":
                routing_info["target_agent"] = tool_call["result"].get("target_agent")
                routing_info["processed_request"] = tool_call["result"].get("processed_request")
                routing_info["context"] = tool_call["result"].get("context", {})

        return routing_info

    def classify_with_rules(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[ClassificationResult]:
        """
        규칙 기반 V7 분류 시도

        Args:
            user_input: 사용자 입력 텍스트
            context: 컨텍스트 (tenant_id, db 포함)

        Returns:
            ClassificationResult: 규칙 매칭 시
            None: 규칙으로 분류 불가 (LLM 필요)
        """
        return self.v7_intent_classifier.classify(user_input, context=context)

    def route_with_hybrid(
        self,
        user_input: str,
        llm_result: Optional[Dict[str, Any]] = None,
        user_role: Optional[Role] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        하이브리드 라우팅 (V7 규칙 우선, LLM fallback)

        Args:
            user_input: 사용자 입력 텍스트
            llm_result: LLM 분류 결과 (이미 호출한 경우)
            user_role: 사용자 역할 (권한 체크용, None이면 체크 생략)
            context: 컨텍스트 (tenant_id, db 포함)

        Returns:
            라우팅 정보 딕셔너리 (V7 Intent 포함)
            권한 부족 시 error 필드 포함
        """
        # 1차: V7 규칙 기반 분류 시도
        rule_result = self.classify_with_rules(user_input, context=context)

        if rule_result and rule_result.confidence >= 0.9:
            logger.info(
                f"[V7 Hybrid Router] Rule-based: '{user_input[:30]}...' → {rule_result.v7_intent} "
                f"(route: {rule_result.route_to}, confidence: {rule_result.confidence})"
            )

            # 권한 체크 (user_role이 제공된 경우)
            if user_role and not check_intent_permission(rule_result.v7_intent, user_role):
                required_role = get_required_role(rule_result.v7_intent)
                error_msg = (
                    f"권한 부족: '{rule_result.v7_intent}' Intent는 "
                    f"{required_role.name} 이상의 권한이 필요합니다."
                )
                logger.warning(
                    f"[V7 Hybrid Router] Permission denied: user_role={user_role.name}, "
                    f"intent={rule_result.v7_intent}, required={required_role.name}"
                )
                return {
                    "target_agent": "error",
                    "processed_request": user_input,
                    "context": {
                        "classification_source": "v7_rule_engine",
                        "permission_denied": True,
                    },
                    "v7_intent": rule_result.v7_intent,
                    "route_to": rule_result.route_to,
                    "legacy_intent": rule_result.legacy_intent,
                    "intent": rule_result.legacy_intent,
                    "slots": rule_result.slots,
                    "error": error_msg,
                    "required_role": required_role.name,
                    "user_role": user_role.name,
                }

            return {
                "target_agent": rule_result.legacy_intent,
                "processed_request": user_input,
                "context": {
                    "classification_source": "v7_rule_engine",
                    "matched_pattern": rule_result.matched_pattern,
                    "confidence": rule_result.confidence,
                },
                "v7_intent": rule_result.v7_intent,
                "route_to": rule_result.route_to,
                "legacy_intent": rule_result.legacy_intent,
                "intent": rule_result.legacy_intent,  # Legacy 호환
                "slots": rule_result.slots,
            }

        # 명확화 필요 여부 확인
        clarify_question = self.v7_intent_classifier.should_clarify(user_input)
        if clarify_question:
            logger.info(f"[V7 Hybrid Router] Clarification needed: '{user_input[:30]}...'")
            return {
                "target_agent": "general",
                "processed_request": user_input,
                "context": {
                    "classification_source": "clarify",
                    "ask_back": clarify_question,
                },
                "v7_intent": "CLARIFY",
                "route_to": "ASK_BACK",
                "legacy_intent": "general",
                "intent": "general",
                "slots": {},
                "ask_back": clarify_question,
            }

        # 2차: LLM 분류 (규칙 매칭 실패 시)
        if llm_result:
            routing_info = self.parse_routing_result(llm_result)
            routing_info["context"]["classification_source"] = "llm"
            logger.info(
                f"[V7 Hybrid Router] LLM-based: '{user_input[:30]}...' → "
                f"v7={routing_info.get('v7_intent')}, legacy={routing_info['target_agent']}"
            )

            # 권한 체크 (user_role이 제공되고 v7_intent가 있는 경우)
            if user_role and routing_info.get("v7_intent"):
                v7_intent = routing_info["v7_intent"]
                if not check_intent_permission(v7_intent, user_role):
                    required_role = get_required_role(v7_intent)
                    error_msg = (
                        f"권한 부족: '{v7_intent}' Intent는 "
                        f"{required_role.name} 이상의 권한이 필요합니다."
                    )
                    logger.warning(
                        f"[V7 Hybrid Router] Permission denied (LLM): user_role={user_role.name}, "
                        f"intent={v7_intent}, required={required_role.name}"
                    )
                    routing_info["target_agent"] = "error"
                    routing_info["error"] = error_msg
                    routing_info["required_role"] = required_role.name
                    routing_info["user_role"] = user_role.name
                    routing_info["context"]["permission_denied"] = True

            return routing_info

        # LLM 결과가 없으면 기본값 반환
        logger.warning(f"[V7 Hybrid Router] No classification for: '{user_input[:30]}...'")
        return {
            "target_agent": "general",
            "processed_request": user_input,
            "context": {"classification_source": "fallback"},
            "v7_intent": "SYSTEM",
            "route_to": "DIRECT_RESPONSE",
            "legacy_intent": "general",
            "intent": "general",
            "slots": {},
        }

    def get_classification_debug(self, user_input: str) -> Dict[str, Any]:
        """
        분류 디버그 정보 (개발/테스트용)
        """
        return self.v7_intent_classifier.get_classification_debug(user_input)

    # =========================================
    # Route Target → Agent 매핑
    # =========================================
    @staticmethod
    def route_target_to_agent(route_to: str) -> str:
        """
        Route Target을 실제 Agent 이름으로 변환

        Args:
            route_to: Route Target (예: "DATA_LAYER", "JUDGMENT_ENGINE")

        Returns:
            Agent 이름 (예: "judgment", "bi")
        """
        mapping = {
            "DATA_LAYER": "judgment",
            "JUDGMENT_ENGINE": "judgment",
            "RULE_ENGINE": "learning",
            "BI_GUIDE": "bi",
            "WORKFLOW_GUIDE": "workflow",
            "CONTEXT_DEPENDENT": "general",
            "ASK_BACK": "general",
            "DIRECT_RESPONSE": "general",
        }
        return mapping.get(route_to, "general")
