"""
Workflow Planner Agent
자동화 워크플로우 생성 및 관리
"""
from typing import Any, Dict, List
import logging
import json
from pathlib import Path
from uuid import uuid4

from .base_agent import BaseAgent
from ..models.core import Workflow
from ..database import get_db_context

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
        create_workflow만 사용하여 워크플로우 생성에 집중
        """
        return [
            {
                "name": "create_workflow",
                "description": "워크플로우를 DB에 저장합니다. 사용자의 자연어 요청을 기반으로 워크플로우를 생성합니다. 예: '온도가 80도 넘으면 슬랙 알림' → 자동 워크플로우 생성",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "워크플로우 이름 (한글 가능, 예: '온도 경고 워크플로우')",
                        },
                        "description": {
                            "type": "string",
                            "description": "워크플로우 설명",
                        },
                        "trigger_type": {
                            "type": "string",
                            "enum": ["event", "schedule", "manual"],
                            "description": "트리거 유형: event(이벤트 기반), schedule(스케줄), manual(수동)",
                        },
                        "event_type": {
                            "type": "string",
                            "enum": ["sensor_alert", "defect_detected", "threshold_exceeded", "line_stopped", "maintenance_due"],
                            "description": "이벤트 타입 (trigger_type이 event일 때 사용)",
                        },
                        "condition_sensor_type": {
                            "type": "string",
                            "enum": ["temperature", "pressure", "humidity", "vibration", "flow_rate", "defect_rate"],
                            "description": "조건에 사용할 센서/데이터 타입",
                        },
                        "condition_operator": {
                            "type": "string",
                            "enum": [">", "<", ">=", "<=", "==", "!="],
                            "description": "비교 연산자",
                        },
                        "condition_value": {
                            "type": "number",
                            "description": "조건 임계값 (숫자)",
                        },
                        "action_type": {
                            "type": "string",
                            "enum": ["send_slack_notification", "send_email", "send_sms", "log_event", "stop_production_line", "trigger_maintenance"],
                            "description": "실행할 액션 유형",
                        },
                        "action_channel": {
                            "type": "string",
                            "description": "알림 채널 (Slack 채널명, 이메일 주소 등)",
                        },
                        "action_message": {
                            "type": "string",
                            "description": "알림/로그 메시지",
                        },
                    },
                    "required": ["name", "trigger_type", "condition_sensor_type", "condition_operator", "condition_value", "action_type"],
                },
            },
        ]

    def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """
        Tool 실행 - create_workflow 전용
        """
        if tool_name == "create_workflow":
            return self._create_workflow(
                name=tool_input["name"],
                description=tool_input.get("description"),
                trigger_type=tool_input["trigger_type"],
                event_type=tool_input.get("event_type"),
                condition_sensor_type=tool_input["condition_sensor_type"],
                condition_operator=tool_input["condition_operator"],
                condition_value=tool_input["condition_value"],
                action_type=tool_input["action_type"],
                action_channel=tool_input.get("action_channel"),
                action_message=tool_input.get("action_message"),
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

    def _create_workflow(
        self,
        name: str,
        trigger_type: str,
        condition_sensor_type: str,
        condition_operator: str,
        condition_value: float,
        action_type: str,
        description: str | None = None,
        event_type: str | None = None,
        action_channel: str | None = None,
        action_message: str | None = None,
    ) -> Dict[str, Any]:
        """
        구조화된 파라미터를 받아 워크플로우 DSL을 생성하고 DB에 저장
        """
        try:
            # 센서 타입별 한글 이름
            sensor_names = {
                "temperature": "온도",
                "pressure": "압력",
                "humidity": "습도",
                "vibration": "진동",
                "flow_rate": "유량",
                "defect_rate": "불량률",
            }
            sensor_name_kr = sensor_names.get(condition_sensor_type, condition_sensor_type)

            # 액션 타입별 기본 설정
            action_configs = {
                "send_slack_notification": {
                    "action": "send_slack_notification",
                    "parameters": {
                        "channel": action_channel or "#alerts",
                        "message": action_message or f"{sensor_name_kr} 이상 감지: {condition_operator} {condition_value}",
                    },
                },
                "send_email": {
                    "action": "send_email",
                    "parameters": {
                        "to": action_channel or "admin@example.com",
                        "subject": f"[경고] {sensor_name_kr} 이상",
                        "body": action_message or f"{sensor_name_kr}가 임계값을 초과했습니다.",
                    },
                },
                "send_sms": {
                    "action": "send_sms",
                    "parameters": {
                        "phone": action_channel or "",
                        "message": action_message or f"{sensor_name_kr} 경고",
                    },
                },
                "log_event": {
                    "action": "log_event",
                    "parameters": {
                        "event_type": "sensor_alert",
                        "details": {
                            "sensor_type": condition_sensor_type,
                            "condition": f"{condition_operator} {condition_value}",
                            "message": action_message or f"{sensor_name_kr} 이상",
                        },
                    },
                },
                "stop_production_line": {
                    "action": "stop_production_line",
                    "parameters": {
                        "line_code": action_channel or "LINE_A",
                        "reason": action_message or f"{sensor_name_kr} 임계값 초과로 자동 중지",
                    },
                },
                "trigger_maintenance": {
                    "action": "trigger_maintenance",
                    "parameters": {
                        "equipment_id": action_channel or "EQ_001",
                        "priority": "high",
                    },
                },
            }

            # Workflow DSL 생성
            workflow_dsl = {
                "name": name,
                "description": description or f"{sensor_name_kr} {condition_operator} {condition_value} 시 {action_type}",
                "trigger": {
                    "type": trigger_type,
                    "config": {
                        "event_type": event_type or "threshold_exceeded",
                    },
                },
                "nodes": [
                    {
                        "id": "node_1",
                        "type": "condition",
                        "config": {
                            "condition": f"{condition_sensor_type} {condition_operator} {condition_value}",
                        },
                        "next": ["node_2"],
                    },
                    {
                        "id": "node_2",
                        "type": "action",
                        "config": action_configs.get(action_type, action_configs["log_event"]),
                        "next": [],
                    },
                ],
            }

            workflow_id = str(uuid4())

            with get_db_context() as db:
                # 기본 테넌트 조회
                from ..models.core import Tenant
                default_tenant = db.query(Tenant).filter(Tenant.name == "Default").first()
                if not default_tenant:
                    return {
                        "success": False,
                        "error": "Default tenant not found",
                    }

                workflow = Workflow(
                    workflow_id=workflow_id,
                    tenant_id=default_tenant.tenant_id,
                    name=name,
                    description=description or workflow_dsl["description"],
                    dsl_definition=workflow_dsl,
                    version="1.0.0",
                    is_active=True,
                )
                db.add(workflow)
                db.commit()
                db.refresh(workflow)

                logger.info(f"Created workflow: {workflow_id} - {name}")

                return {
                    "success": True,
                    "workflow_id": workflow_id,
                    "name": name,
                    "description": workflow.description,
                    "trigger_type": trigger_type,
                    "condition": f"{sensor_name_kr} {condition_operator} {condition_value}",
                    "action": action_type,
                    "message": f"워크플로우 '{name}'이(가) 성공적으로 생성되었습니다. Workflows 탭에서 확인하세요.",
                }

        except Exception as e:
            logger.error(f"Error creating workflow: {e}")
            return {
                "success": False,
                "error": str(e),
            }
