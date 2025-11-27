"""
Meta Router Agent
사용자 요청을 분석하여 적절한 Sub-Agent로 라우팅
"""
from typing import Any, Dict, List
import logging
from pathlib import Path

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class MetaRouterAgent(BaseAgent):
    """
    Meta Router Agent
    - Intent 분류
    - 슬롯 추출
    - Sub-Agent 라우팅
    """

    def __init__(self):
        super().__init__(
            name="MetaRouterAgent",
            model="claude-sonnet-4-5-20250929",
            max_tokens=2048,
        )

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
            return "You are a Meta Router Agent for TriFlow AI."

    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Meta Router Agent의 Tool 정의
        """
        return [
            {
                "name": "classify_intent",
                "description": "사용자 요청의 의도(Intent)를 분류합니다.",
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
        if tool_name == "classify_intent":
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
                "intent": "...",
                "slots": {...}
            }
        """
        routing_info = {
            "target_agent": "general",
            "processed_request": "",
            "context": {},
            "intent": None,
            "slots": {},
        }

        for tool_call in result.get("tool_calls", []):
            if tool_call["tool"] == "classify_intent":
                routing_info["intent"] = tool_call["result"].get("intent")

            elif tool_call["tool"] == "extract_slots":
                routing_info["slots"] = tool_call["result"].get("slots", {})

            elif tool_call["tool"] == "route_request":
                routing_info["target_agent"] = tool_call["result"].get("target_agent")
                routing_info["processed_request"] = tool_call["result"].get("processed_request")
                routing_info["context"] = tool_call["result"].get("context", {})

        return routing_info
