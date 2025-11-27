"""
Workflow Planner Agent
자동화 워크플로우 생성 및 관리
"""
from typing import Any, Dict, List
import logging
from pathlib import Path
import json

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class WorkflowPlannerAgent(BaseAgent):
    """
    Workflow Planner Agent
    - 자연어 요청을 Workflow DSL로 변환
    - 워크플로우 노드 검증
    - 액션 카탈로그 검색
    """

    def __init__(self):
        super().__init__(
            name="WorkflowPlannerAgent",
            model="claude-sonnet-4-5-20250929",
            max_tokens=4096,
        )
        # Action catalog 로드
        self.action_catalog = self._load_action_catalog()

    def get_system_prompt(self) -> str:
        """
        시스템 프롬프트 로드
        """
        prompt_path = Path(__file__).parent.parent / "prompts" / "workflow_planner.md"
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"Prompt file not found: {prompt_path}, using default")
            return "You are a Workflow Planner Agent for TriFlow AI."

    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Workflow Planner Agent의 Tool 정의
        """
        return [
            {
                "name": "search_action_catalog",
                "description": "사용 가능한 액션 목록을 검색합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "검색 쿼리 (예: '알림', '데이터 저장', '센서 제어')",
                        },
                        "category": {
                            "type": "string",
                            "description": "액션 카테고리 (notification, data, control, analysis)",
                            "enum": ["notification", "data", "control", "analysis", "all"],
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "generate_workflow_dsl",
                "description": "자연어 요청을 Workflow DSL로 변환합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "user_request": {
                            "type": "string",
                            "description": "사용자의 자연어 요청",
                        },
                        "available_actions": {
                            "type": "array",
                            "description": "사용 가능한 액션 리스트",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["user_request", "available_actions"],
                },
            },
            {
                "name": "validate_node_schema",
                "description": "생성된 워크플로우 노드의 스키마를 검증합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "workflow_dsl": {
                            "type": "object",
                            "description": "검증할 Workflow DSL",
                        },
                    },
                    "required": ["workflow_dsl"],
                },
            },
        ]

    def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """
        Tool 실행
        """
        if tool_name == "search_action_catalog":
            return self._search_action_catalog(
                query=tool_input["query"],
                category=tool_input.get("category", "all"),
            )

        elif tool_name == "generate_workflow_dsl":
            return self._generate_workflow_dsl(
                user_request=tool_input["user_request"],
                available_actions=tool_input["available_actions"],
            )

        elif tool_name == "validate_node_schema":
            return self._validate_node_schema(
                workflow_dsl=tool_input["workflow_dsl"],
            )

        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    def _load_action_catalog(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        액션 카탈로그 로드
        MVP: 하드코딩된 액션 목록
        V1: DB에서 동적으로 로드
        """
        return {
            "notification": [
                {
                    "name": "send_slack_notification",
                    "description": "Slack 채널에 알림을 전송합니다",
                    "parameters": {
                        "channel": "string (슬랙 채널명)",
                        "message": "string (메시지 내용)",
                        "mention": "string (멘션할 사용자, 선택)",
                    },
                },
                {
                    "name": "send_email",
                    "description": "이메일을 전송합니다",
                    "parameters": {
                        "to": "string (수신자 이메일)",
                        "subject": "string (제목)",
                        "body": "string (본문)",
                    },
                },
                {
                    "name": "send_sms",
                    "description": "SMS 문자를 전송합니다",
                    "parameters": {
                        "phone": "string (전화번호)",
                        "message": "string (메시지 내용)",
                    },
                },
            ],
            "data": [
                {
                    "name": "save_to_database",
                    "description": "데이터를 데이터베이스에 저장합니다",
                    "parameters": {
                        "table": "string (테이블명)",
                        "data": "object (저장할 데이터)",
                    },
                },
                {
                    "name": "export_to_csv",
                    "description": "데이터를 CSV 파일로 내보냅니다",
                    "parameters": {
                        "data": "array (내보낼 데이터)",
                        "filename": "string (파일명)",
                    },
                },
                {
                    "name": "log_event",
                    "description": "이벤트를 로그에 기록합니다",
                    "parameters": {
                        "event_type": "string (이벤트 타입)",
                        "details": "object (상세 정보)",
                    },
                },
            ],
            "control": [
                {
                    "name": "stop_production_line",
                    "description": "생산 라인을 중지합니다",
                    "parameters": {
                        "line_code": "string (라인 코드)",
                        "reason": "string (중지 사유)",
                    },
                },
                {
                    "name": "adjust_sensor_threshold",
                    "description": "센서 임계값을 조정합니다",
                    "parameters": {
                        "sensor_id": "string (센서 ID)",
                        "threshold": "number (새 임계값)",
                    },
                },
                {
                    "name": "trigger_maintenance",
                    "description": "유지보수 작업을 트리거합니다",
                    "parameters": {
                        "equipment_id": "string (장비 ID)",
                        "priority": "string (우선순위: low, medium, high)",
                    },
                },
            ],
            "analysis": [
                {
                    "name": "calculate_defect_rate",
                    "description": "불량률을 계산합니다",
                    "parameters": {
                        "line_code": "string (라인 코드)",
                        "time_range": "string (시간 범위)",
                    },
                },
                {
                    "name": "analyze_sensor_trend",
                    "description": "센서 데이터 추세를 분석합니다",
                    "parameters": {
                        "sensor_type": "string (센서 타입)",
                        "hours": "number (분석 기간, 시간 단위)",
                    },
                },
                {
                    "name": "predict_equipment_failure",
                    "description": "장비 고장을 예측합니다",
                    "parameters": {
                        "equipment_id": "string (장비 ID)",
                        "sensor_data": "array (센서 데이터)",
                    },
                },
            ],
        }

    def _search_action_catalog(
        self,
        query: str,
        category: str = "all",
    ) -> Dict[str, Any]:
        """
        액션 카탈로그 검색
        """
        try:
            results = []
            query_lower = query.lower()

            # 카테고리 필터링
            if category == "all":
                catalogs = self.action_catalog
            else:
                catalogs = {category: self.action_catalog.get(category, [])}

            # 검색
            for cat_name, actions in catalogs.items():
                for action in actions:
                    # 이름 또는 설명에서 검색
                    if (query_lower in action["name"].lower() or
                        query_lower in action["description"].lower()):
                        results.append({
                            **action,
                            "category": cat_name,
                        })

            logger.info(f"Found {len(results)} actions for query: {query}")

            return {
                "success": True,
                "query": query,
                "category": category,
                "count": len(results),
                "actions": results,
            }

        except Exception as e:
            logger.error(f"Error searching action catalog: {e}")
            return {
                "success": False,
                "error": str(e),
                "actions": [],
            }

    def _generate_workflow_dsl(
        self,
        user_request: str,
        available_actions: List[str],
    ) -> Dict[str, Any]:
        """
        Workflow DSL 생성
        MVP: 간단한 템플릿 기반 생성
        V1: LLM 기반 동적 생성
        """
        try:
            # MVP: 템플릿 기반 워크플로우 생성
            # 실제로는 LLM이 사용자 요청을 분석하여 DSL을 생성

            logger.info(f"Generating workflow DSL for: {user_request}")

            # 예시 DSL 반환
            workflow_dsl = {
                "name": "Auto-generated Workflow",
                "description": f"Generated from user request: {user_request}",
                "trigger": {
                    "type": "event",
                    "config": {
                        "event_type": "sensor_alert",
                    },
                },
                "nodes": [
                    {
                        "id": "node_1",
                        "type": "condition",
                        "config": {
                            "condition": "defect_rate > 0.05",
                        },
                        "next": ["node_2"],
                    },
                    {
                        "id": "node_2",
                        "type": "action",
                        "config": {
                            "action": available_actions[0] if available_actions else "log_event",
                            "parameters": {
                                "message": "Automated workflow triggered",
                            },
                        },
                        "next": [],
                    },
                ],
            }

            return {
                "success": True,
                "workflow_dsl": workflow_dsl,
                "note": "MVP: Template-based generation. LLM-based generation coming in V1.",
            }

        except Exception as e:
            logger.error(f"Error generating workflow DSL: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def _validate_node_schema(
        self,
        workflow_dsl: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        워크플로우 스키마 검증
        """
        try:
            errors = []

            # 필수 필드 검증
            if "name" not in workflow_dsl:
                errors.append("Missing required field: name")
            if "trigger" not in workflow_dsl:
                errors.append("Missing required field: trigger")
            if "nodes" not in workflow_dsl:
                errors.append("Missing required field: nodes")

            # 트리거 검증
            if "trigger" in workflow_dsl:
                trigger = workflow_dsl["trigger"]
                if "type" not in trigger:
                    errors.append("Missing trigger.type")
                elif trigger["type"] not in ["event", "schedule", "manual"]:
                    errors.append(f"Invalid trigger type: {trigger['type']}")

            # 노드 검증
            if "nodes" in workflow_dsl:
                nodes = workflow_dsl["nodes"]
                if not isinstance(nodes, list):
                    errors.append("nodes must be an array")
                else:
                    for i, node in enumerate(nodes):
                        if "id" not in node:
                            errors.append(f"Node {i}: Missing id")
                        if "type" not in node:
                            errors.append(f"Node {i}: Missing type")
                        if "config" not in node:
                            errors.append(f"Node {i}: Missing config")

            is_valid = len(errors) == 0

            logger.info(f"Workflow validation: valid={is_valid}, errors={len(errors)}")

            return {
                "success": True,
                "valid": is_valid,
                "errors": errors,
            }

        except Exception as e:
            logger.error(f"Error validating workflow schema: {e}")
            return {
                "success": False,
                "valid": False,
                "error": str(e),
            }
