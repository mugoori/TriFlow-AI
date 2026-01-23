"""
Workflow Planner Agent
자동화 워크플로우 생성 및 관리 (미리보기 모드)
"""
import re
from typing import Any, Dict, List, Optional
import logging
from pathlib import Path

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

# 모든 노드 타입의 필수 파라미터 정의
# 새 노드 추가 시 이 딕셔너리에 정의하면 자동으로 검증됨
NODE_PARAMETER_REQUIREMENTS = {
    # ===== 액션 노드 =====
    "action": {
        # 알림 액션
        "send_slack_notification": {
            "required": ["channel"],
            "prompts": {"channel": "Slack 알림을 보낼 채널을 알려주세요. (예: #alerts, #production)"}
        },
        "send_email": {
            "required": ["to"],
            "prompts": {"to": "이메일 수신자를 알려주세요. (예: admin@example.com)"}
        },
        "send_sms": {
            "required": ["phone"],
            "prompts": {"phone": "SMS를 받을 전화번호를 알려주세요."}
        },
        # 제어 액션
        "stop_production_line": {
            "required": ["line_code"],
            "prompts": {"line_code": "어떤 라인을 정지할까요? (예: LINE_001, LINE_A)"}
        },
        "trigger_maintenance": {
            "required": ["equipment_id"],
            "prompts": {"equipment_id": "어떤 장비의 유지보수인가요? (예: EQ_001)"}
        },
        "adjust_sensor_threshold": {
            "required": ["sensor_id", "threshold"],
            "prompts": {
                "sensor_id": "어떤 센서의 임계값을 조정할까요?",
                "threshold": "새로운 임계값을 알려주세요."
            }
        },
        # 데이터 액션
        "save_to_database": {
            "required": ["table"],
            "prompts": {"table": "데이터를 저장할 테이블명을 알려주세요."}
        },
        "export_to_csv": {
            "required": ["filename"],
            "prompts": {"filename": "CSV 파일명을 알려주세요."}
        },
        # 외부 연동 액션
        "call_api": {
            "required": ["url"],
            "prompts": {"url": "호출할 API URL을 알려주세요."}
        },
        "webhook": {
            "required": ["url"],
            "prompts": {"url": "웹훅 URL을 알려주세요."}
        },
        # 필수 파라미터 없는 액션
        "log_event": {"required": []},
    },

    # ===== 조건/분기 노드 =====
    "condition": {
        "required": ["field", "operator", "value"],
        "prompts": {
            "field": "어떤 센서/필드를 확인할까요? (예: temperature, pressure)",
            "operator": "비교 연산자를 선택해주세요. (>, <, >=, <=, ==, !=)",
            "value": "임계값을 입력해주세요."
        }
    },
    "if_else": {
        "required": ["condition.field", "condition.operator", "condition.value"],
        "prompts": {
            "condition.field": "어떤 센서/필드를 확인할까요?",
            "condition.operator": "비교 연산자를 선택해주세요.",
            "condition.value": "임계값을 입력해주세요."
        }
    },

    # ===== 반복 노드 =====
    "loop": {
        "required": ["count"],
        "prompts": {"count": "몇 번 반복할까요?"}
    },

    # ===== 병렬 노드 =====
    "parallel": {
        "required": [],  # parallel_nodes만 있으면 됨
    },

    # ===== 트리거 =====
    "trigger": {
        "schedule": {
            "required": ["cron"],
            "prompts": {"cron": "스케줄을 입력해주세요. (예: 매일 9시 = '0 9 * * *')"}
        },
        "event": {"required": []},
        "manual": {"required": []},
    }
}


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
            max_tokens=4096,
        )  # model은 get_model()에서 동적으로 조회
        # Action catalog 로드
        self.action_catalog = self._load_action_catalog()
        # Tool 실행 시 conversation_history 접근을 위한 인스턴스 변수
        self._current_context: Optional[Dict[str, Any]] = None

    def run(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
        max_iterations: int = 5,
        tool_choice: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        에이전트 실행 (Base 클래스 오버라이드)
        context를 인스턴스 변수에 저장하여 execute_tool에서 접근 가능하게 함
        """
        # context를 인스턴스 변수에 저장 (execute_tool에서 사용)
        self._current_context = context or {}
        try:
            return super().run(user_message, context, max_iterations, tool_choice)
        finally:
            # 실행 완료 후 정리
            self._current_context = None

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
        - request_parameters: 누락된 파라미터 구조화된 요청 (백엔드 파싱)
        - create_workflow: 단순 워크플로우 (1조건 + 1액션)
        - create_complex_workflow: 복잡한 워크플로우 (다중 조건, 분기, 반복, 병렬)
        """
        return [
            {
                "name": "request_parameters",
                "description": """필수 파라미터가 누락되었을 때 사용자에게 구조화된 방식으로 되묻기 위한 Tool.

사용 시점:
- 워크플로우 생성에 필요한 파라미터(channel, line_code, equipment_id 등)가 누락된 경우
- 다중 파라미터를 한 번에 요청해야 하는 경우

중요: 이 Tool을 호출하면 백엔드가 되묻기 메시지를 생성하고,
사용자 답변을 백엔드가 정확하게 파싱하여 다음 호출 시 context.parsed_parameters로 제공합니다.

텍스트로 직접 되묻지 말고 반드시 이 Tool을 사용하세요!""",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "parameters": {
                            "type": "array",
                            "description": "요청할 파라미터 목록 (순서 중요 - 사용자 답변 파싱에 사용됨)",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "key": {
                                        "type": "string",
                                        "description": "파라미터 키 (예: channel, line_code, equipment_id)"
                                    },
                                    "label": {
                                        "type": "string",
                                        "description": "사용자에게 보여줄 라벨 (예: 'Slack 채널')"
                                    },
                                    "description": {
                                        "type": "string",
                                        "description": "파라미터 설명 (예: '알림을 보낼 채널')"
                                    },
                                    "example": {
                                        "type": "string",
                                        "description": "예시 값 (예: '#alerts, #production')"
                                    },
                                    "action_id": {
                                        "type": "string",
                                        "description": "이 파라미터가 속한 액션 노드 ID (선택)"
                                    }
                                },
                                "required": ["key", "label"]
                            }
                        },
                        "workflow_context": {
                            "type": "object",
                            "description": "워크플로우 생성에 필요한 추가 컨텍스트 (부분 DSL, 이름, 조건 등)"
                        }
                    },
                    "required": ["parameters"]
                }
            },
            {
                "name": "create_workflow",
                "description": "단순한 워크플로우를 생성합니다 (단일 조건 + 단일 액션). 예: '온도가 80도 넘으면 슬랙 알림'",
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
                        "conversation_history": {
                            "type": "array",
                            "description": "대화 기록 - AI 질문/사용자 답변 쌍을 포함하여 파라미터 추출에 사용",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "role": {"type": "string", "enum": ["user", "assistant"]},
                                    "content": {"type": "string"},
                                },
                            },
                        },
                    },
                    "required": ["name", "trigger_type", "condition_sensor_type", "condition_operator", "condition_value", "action_type"],
                },
            },
            {
                "name": "create_complex_workflow",
                "description": """복잡한 워크플로우를 생성합니다. if_else 분기, loop 반복, parallel 병렬 실행, 다중 조건/액션을 지원합니다.

예시 요청:
- "온도가 80도 이상이면 알림, 90도 이상이면 생산라인 중지"
- "모든 라인의 불량률을 검사하고 5% 초과 시 각각 알림"
- "온도와 진동을 동시에 모니터링해서 둘 다 이상이면 유지보수 트리거"

노드 타입:
- condition: 조건 평가 (순차 진행)
- action: 액션 실행
- if_else: 조건 분기 (then_nodes / else_nodes)
- loop: 반복 실행 (loop_nodes)
- parallel: 병렬 실행 (parallel_nodes)

액션 타입:
- 알림: send_slack_notification, send_email, send_sms
- 데이터: log_event, save_to_database, export_to_csv
- 제어: stop_production_line, adjust_sensor_threshold, trigger_maintenance
- 분석: calculate_metric, analyze_sensor_trend, predict_equipment_failure, execute_sql, aggregate_data, evaluate_threshold, generate_chart, format_insight""",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "워크플로우 이름",
                        },
                        "description": {
                            "type": "string",
                            "description": "워크플로우 설명",
                        },
                        "dsl": {
                            "type": "object",
                            "description": """워크플로우 DSL 구조. 형식:
{
  "trigger": {
    "type": "event|schedule|manual",
    "config": { "event_type": "...", "schedule": "..." }
  },
  "nodes": [
    {
      "id": "unique_id",
      "type": "condition|action|if_else|loop|parallel",
      "config": { ... },
      "next": ["next_node_id"],
      "then_nodes": [...],  // if_else용
      "else_nodes": [...],  // if_else용
      "loop_nodes": [...],  // loop용
      "parallel_nodes": [...] // parallel용
    }
  ]
}""",
                            "properties": {
                                "trigger": {
                                    "type": "object",
                                    "properties": {
                                        "type": {"type": "string", "enum": ["event", "schedule", "manual"]},
                                        "config": {"type": "object"},
                                    },
                                    "required": ["type"],
                                },
                                "nodes": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"},
                                            "type": {"type": "string", "enum": ["condition", "action", "if_else", "loop", "parallel"]},
                                            "config": {"type": "object"},
                                            "next": {"type": "array", "items": {"type": "string"}},
                                            "then_nodes": {"type": "array"},
                                            "else_nodes": {"type": "array"},
                                            "loop_nodes": {"type": "array"},
                                            "parallel_nodes": {"type": "array"},
                                        },
                                        "required": ["id", "type", "config"],
                                    },
                                },
                            },
                            "required": ["trigger", "nodes"],
                        },
                    },
                    "required": ["name", "dsl"],
                },
            },
        ]

    def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """
        Tool 실행
        """
        if tool_name == "request_parameters":
            return self._request_parameters(
                parameters=tool_input["parameters"],
                workflow_context=tool_input.get("workflow_context")
            )
        elif tool_name == "create_workflow":
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
        elif tool_name == "create_complex_workflow":
            # context에서 conversation_history 추출
            conversation_history = None
            if self._current_context:
                conversation_history = self._current_context.get("conversation_history")
            return self._create_complex_workflow(
                name=tool_input["name"],
                description=tool_input.get("description"),
                dsl=tool_input["dsl"],
                conversation_history=conversation_history,
            )
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    def _request_parameters(
        self,
        parameters: List[Dict[str, Any]],
        workflow_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        구조화된 파라미터 요청 반환
        백엔드(agent_orchestrator)에서 이 결과를 처리하여 되묻기 생성

        Args:
            parameters: 요청할 파라미터 목록 [{key, label, description, example, action_id}, ...]
            workflow_context: 워크플로우 생성에 필요한 추가 컨텍스트

        Returns:
            {
                "success": True,
                "type": "parameter_request",
                "parameters": [...],
                "workflow_context": {...},
                "message": "되묻기 메시지"
            }
        """
        logger.info(f"[RequestParameters] Requesting {len(parameters)} parameters")

        return {
            "success": True,
            "type": "parameter_request",
            "parameters": parameters,
            "workflow_context": workflow_context,
            "message": self._format_parameter_request(parameters)
        }

    def _format_parameter_request(self, parameters: List[Dict[str, Any]]) -> str:
        """되묻기 메시지 포맷팅"""
        lines = ["다음 정보를 알려주세요:\n"]

        for i, param in enumerate(parameters, 1):
            label = param.get("label", param["key"])
            desc = param.get("description", "")
            example = param.get("example", "")

            line = f"{i}. **{label}**"
            if desc:
                line += f": {desc}"
            if example:
                line += f" (예: {example})"
            lines.append(line)

        lines.append("\n쉼표로 구분하여 순서대로 입력해주세요.")
        lines.append("예: #my-channel, EQ_001, LINE_B")

        return "\n".join(lines)

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
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        구조화된 파라미터를 받아 워크플로우 DSL 미리보기 생성 (DB 저장 안 함)
        사용자가 프론트엔드에서 "적용" 버튼을 클릭하면 저장됨
        """
        try:
            # Placeholder 검증 - LLM이 추론한 placeholder 값 거부

            def is_placeholder(val: str | None) -> bool:
                if not val:
                    return False
                return any(p in str(val).upper() for p in ["UNKNOWN", "???", "TBD"])

            # 액션 타입별 필수 파라미터 검증
            missing_params = []
            action_requirements = NODE_PARAMETER_REQUIREMENTS.get("action", {})

            if action_type in action_requirements:
                req = action_requirements[action_type]
                required_fields = req.get("required", [])
                prompts = req.get("prompts", {})

                # channel 필수 액션들
                if "channel" in required_fields:
                    if not action_channel or is_placeholder(action_channel):
                        missing_params.append(prompts.get("channel", "알림 채널을 알려주세요."))

                # to 필수 (이메일)
                if "to" in required_fields:
                    if not action_channel or is_placeholder(action_channel):
                        missing_params.append(prompts.get("to", "수신자를 알려주세요."))

                # phone 필수 (SMS)
                if "phone" in required_fields:
                    if not action_channel or is_placeholder(action_channel):
                        missing_params.append(prompts.get("phone", "전화번호를 알려주세요."))

                # line_code 필수 (라인 정지)
                if "line_code" in required_fields:
                    if not action_channel or is_placeholder(action_channel):
                        missing_params.append(prompts.get("line_code", "라인 코드를 알려주세요."))

                # equipment_id 필수 (유지보수)
                if "equipment_id" in required_fields:
                    if not action_channel or is_placeholder(action_channel):
                        missing_params.append(prompts.get("equipment_id", "장비 ID를 알려주세요."))

            if missing_params:
                return {
                    "success": False,
                    "need_more_info": True,
                    "missing_info": missing_params,
                    "message": "워크플로우를 생성하려면 다음 정보가 필요합니다:\n\n" +
                              "\n".join(f"• {m}" for m in missing_params) +
                              "\n\n위 정보를 알려주시면 워크플로우를 생성하겠습니다."
                }
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

            # Workflow DSL 생성 (DB 저장 없이 미리보기용)
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

            # ========== 대화 기록에서 파라미터 추출 및 기본값 교체 ==========
            if conversation_history:
                # 추출 대상 파라미터 목록
                target_params = ["channel", "line_code", "equipment_id", "to", "phone"]

                # 대화 기록에서 파라미터 추출
                extracted = self._extract_parameters_from_conversation(
                    conversation_history, target_params
                )

                if extracted:
                    logger.info(f"[CreateWorkflow] Extracted params from conversation: {extracted}")

                    # 모든 노드를 순회하며 기본값 교체
                    for node in workflow_dsl.get("nodes", []):
                        if node.get("type") == "action":
                            config = node.get("config", {})
                            params = config.get("parameters", {})

                            for key, new_value in extracted.items():
                                if key in params:
                                    current_value = params[key]
                                    if self._is_default_value(key, current_value):
                                        # # 붙여주기 (채널인 경우)
                                        if key == "channel" and not str(new_value).startswith("#"):
                                            new_value = f"#{new_value}"
                                        params[key] = new_value
                                        logger.info(
                                            f"[CreateWorkflow] Replaced default: "
                                            f"{key}='{current_value}' -> '{new_value}'"
                                        )
            # ========== 파라미터 교체 로직 끝 ==========

            logger.info(f"Generated workflow preview: {name}")

            # 미리보기용 응답 반환 (DB 저장 안 함)
            return {
                "success": True,
                "preview": True,  # 미리보기 플래그
                "dsl": workflow_dsl,  # 프론트엔드에서 사용
                "name": name,
                "description": description or workflow_dsl["description"],
                "trigger_type": trigger_type,
                "condition": f"{sensor_name_kr} {condition_operator} {condition_value}",
                "action": action_type,
                "message": f"워크플로우 '{name}' 미리보기가 생성되었습니다. 확인 후 '적용' 버튼을 눌러주세요.",
            }

        except Exception as e:
            logger.error(f"Error creating workflow preview: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def _create_complex_workflow(
        self,
        name: str,
        dsl: Dict[str, Any],
        description: str | None = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        복잡한 워크플로우 미리보기 생성 (DB 저장 안 함)
        if_else, loop, parallel 등 복잡한 노드 구조 지원
        사용자가 프론트엔드에서 "적용" 버튼을 클릭하면 저장됨

        Args:
            name: 워크플로우 이름
            dsl: 워크플로우 DSL
            description: 워크플로우 설명
            conversation_history: 대화 기록 (파라미터 추출용)
        """
        try:
            # DSL 유효성 검사
            validation_result = self._validate_complex_dsl(dsl)
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": f"DSL 유효성 검사 실패: {', '.join(validation_result['errors'])}",
                }

            # 필수 파라미터 검증 - 빈 값이 있으면 되묻기, 대화 기록에서 추출한 값 적용
            is_valid, missing_prompts, updated_dsl = self._validate_workflow_parameters(
                dsl, conversation_history
            )
            if not is_valid:
                # 딕셔너리 대신 명확한 텍스트 반환 (LLM이 인식할 수 있도록)
                return (
                    "워크플로우를 생성하려면 다음 정보가 필요합니다:\n\n"
                    + "\n".join(f"• {m}" for m in missing_prompts)
                    + "\n\n위 정보를 알려주시면 워크플로우를 생성하겠습니다."
                )

            # 워크플로우 DSL 완성 (DB 저장 없이 미리보기용)
            # 대화 기록에서 추출된 파라미터가 적용된 updated_dsl 사용
            workflow_dsl = {
                "name": name,
                "description": description or f"복잡한 워크플로우: {name}",
                **updated_dsl,
            }

            # 노드 통계 계산
            node_stats = self._count_nodes(dsl.get("nodes", []))

            logger.info(f"Generated complex workflow preview: {name}")

            # 미리보기용 응답 반환 (DB 저장 안 함)
            return {
                "success": True,
                "preview": True,  # 미리보기 플래그
                "dsl": workflow_dsl,  # 프론트엔드에서 사용
                "name": name,
                "description": description or workflow_dsl["description"],
                "trigger_type": dsl.get("trigger", {}).get("type", "unknown"),
                "node_count": node_stats["total"],
                "node_types": node_stats["by_type"],
                "message": f"복잡한 워크플로우 '{name}' 미리보기가 생성되었습니다. "
                           f"총 {node_stats['total']}개의 노드가 포함되어 있습니다. "
                           f"확인 후 '적용' 버튼을 눌러주세요.",
            }

        except Exception as e:
            logger.error(f"Error creating complex workflow preview: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def _validate_complex_dsl(self, dsl: Dict[str, Any]) -> Dict[str, Any]:
        """
        복잡한 워크플로우 DSL 유효성 검사
        """
        errors = []

        # 트리거 검사
        if "trigger" not in dsl:
            errors.append("trigger 필드가 필요합니다")
        else:
            trigger = dsl["trigger"]
            if "type" not in trigger:
                errors.append("trigger.type 필드가 필요합니다")
            elif trigger["type"] not in ["event", "schedule", "manual"]:
                errors.append(f"유효하지 않은 trigger.type: {trigger['type']}")

        # 노드 검사
        if "nodes" not in dsl:
            errors.append("nodes 필드가 필요합니다")
        elif not isinstance(dsl["nodes"], list):
            errors.append("nodes는 배열이어야 합니다")
        else:
            # 재귀적으로 모든 노드 검사
            node_errors = self._validate_nodes_recursive(dsl["nodes"])
            errors.extend(node_errors)

        return {
            "valid": len(errors) == 0,
            "errors": errors,
        }

    def _validate_nodes_recursive(
        self,
        nodes: List[Dict[str, Any]],
        path: str = "nodes",
    ) -> List[str]:
        """
        노드 목록을 재귀적으로 검사
        """
        errors = []
        valid_node_types = ["condition", "action", "if_else", "loop", "parallel"]

        for i, node in enumerate(nodes):
            node_path = f"{path}[{i}]"

            # 필수 필드 검사
            if "id" not in node:
                errors.append(f"{node_path}: id 필드가 필요합니다")
            if "type" not in node:
                errors.append(f"{node_path}: type 필드가 필요합니다")
            elif node["type"] not in valid_node_types:
                errors.append(f"{node_path}: 유효하지 않은 type: {node['type']}")
            if "config" not in node:
                errors.append(f"{node_path}: config 필드가 필요합니다")

            # 노드 타입별 추가 검사
            node_type = node.get("type")
            if node_type == "if_else":
                # then_nodes는 필수
                if "then_nodes" not in node:
                    errors.append(f"{node_path}: if_else 노드에는 then_nodes가 필요합니다")
                elif isinstance(node["then_nodes"], list):
                    errors.extend(self._validate_nodes_recursive(
                        node["then_nodes"],
                        f"{node_path}.then_nodes",
                    ))
                # else_nodes는 선택
                if "else_nodes" in node and isinstance(node["else_nodes"], list):
                    errors.extend(self._validate_nodes_recursive(
                        node["else_nodes"],
                        f"{node_path}.else_nodes",
                    ))

            elif node_type == "loop":
                if "loop_nodes" not in node:
                    errors.append(f"{node_path}: loop 노드에는 loop_nodes가 필요합니다")
                elif isinstance(node["loop_nodes"], list):
                    errors.extend(self._validate_nodes_recursive(
                        node["loop_nodes"],
                        f"{node_path}.loop_nodes",
                    ))

            elif node_type == "parallel":
                if "parallel_nodes" not in node:
                    errors.append(f"{node_path}: parallel 노드에는 parallel_nodes가 필요합니다")
                elif isinstance(node["parallel_nodes"], list):
                    errors.extend(self._validate_nodes_recursive(
                        node["parallel_nodes"],
                        f"{node_path}.parallel_nodes",
                    ))

        return errors

    def _count_nodes(self, nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        노드 수를 재귀적으로 계산
        """
        total = 0
        by_type: Dict[str, int] = {}

        def count_recursive(node_list: List[Dict[str, Any]]):
            nonlocal total
            for node in node_list:
                total += 1
                node_type = node.get("type", "unknown")
                by_type[node_type] = by_type.get(node_type, 0) + 1

                # 중첩 노드 카운트
                if "then_nodes" in node:
                    count_recursive(node["then_nodes"])
                if "else_nodes" in node:
                    count_recursive(node["else_nodes"])
                if "loop_nodes" in node:
                    count_recursive(node["loop_nodes"])
                if "parallel_nodes" in node:
                    count_recursive(node["parallel_nodes"])

        count_recursive(nodes)
        return {"total": total, "by_type": by_type}

    def _is_default_value(self, param: str, value: Any) -> bool:
        """
        기본값/placeholder인지 확인

        워크플로우 DSL에서 기본값 패턴을 감지하여
        사용자가 제공한 값으로 교체해야 하는지 판단합니다.

        Args:
            param: 파라미터 이름 (예: "channel", "line_code")
            value: 현재 값

        Returns:
            기본값이면 True, 아니면 False
        """
        DEFAULT_VALUES = {
            "channel": ["#alerts", "#general", "#channel", "#알림", "#production-alerts"],
            "line_code": ["LINE_001", "LINE_1", "LINE_A", "LINE_ID"],
            "equipment_id": ["EQ_001", "EQUIPMENT_001", "EQ_ID"],
            "to": ["admin@example.com", "user@example.com", "example@email.com"],
            "phone": ["+82-10-0000-0000", "010-0000-0000", "+1-000-000-0000"],
            "message": ["알림 메시지", "Alert message", "Notification"],
        }

        if not value:
            return True

        patterns = DEFAULT_VALUES.get(param, [])
        str_value = str(value)

        # 정확히 일치하는 기본값
        if str_value in patterns:
            return True

        # 패턴 부분 일치 (예: "LINE_" 또는 "EQ_"로 시작하고 숫자로 끝나는 경우)
        import re
        if param == "line_code" and re.match(r"^LINE_\d+$", str_value):
            return True
        if param == "equipment_id" and re.match(r"^EQ_\d+$", str_value):
            return True

        return False

    def _extract_parameters_from_conversation(
        self,
        conversation_history: List[Dict[str, str]],
        pending_params: List[str]
    ) -> Dict[str, str]:
        """
        대화 기록에서 사용자 답변 파라미터 추출

        AI가 되묻기 질문을 하고, 사용자가 답변한 파라미터를 추출합니다.

        예시:
        - AI 질문: "1. Slack 채널\n2. 라인 코드"
        - 사용자 답변: "뉴-채널, 라인 B"
        - 반환: {"channel": "뉴-채널", "line_code": "라인 B"}

        Args:
            conversation_history: 대화 기록 (role, content 포함)
            pending_params: 추출할 파라미터 목록 (예: ["channel", "line_code"])

        Returns:
            추출된 파라미터 딕셔너리
        """
        if not conversation_history or not pending_params:
            return {}

        extracted = {}

        # 최근 대화에서 AI 질문과 사용자 답변 쌍 찾기 (역순으로 탐색)
        for i in range(len(conversation_history) - 1, 0, -1):
            msg = conversation_history[i]
            prev_msg = conversation_history[i - 1]

            # 사용자 메시지이고 이전이 AI 메시지인 경우
            if msg.get("role") == "user" and prev_msg.get("role") == "assistant":
                user_answer = msg.get("content", "")
                ai_question = prev_msg.get("content", "")

                # AI 질문에서 되묻기 패턴이 있는지 확인
                if self._is_reprompt_question(ai_question):
                    # 사용자 답변에서 파라미터 추출
                    extracted = self._parse_answer_to_params(
                        ai_question, user_answer, pending_params
                    )
                    if extracted:
                        logger.info(f"[ConvHistory] Extracted params: {extracted}")
                        break

        return extracted

    def _is_reprompt_question(self, ai_message: str) -> bool:
        """AI 메시지가 되묻기 질문인지 확인"""
        reprompt_patterns = [
            r"알려주세요",
            r"입력해주세요",
            r"지정해주세요",
            r"어떤.*\?",
            r"\d\.\s*\w+.*:",  # "1. 채널:" 형식
            r"채널.*정지.*라인",
            r"please.*provide",
            r"which.*channel",
            r"what.*line",
        ]
        for pattern in reprompt_patterns:
            if re.search(pattern, ai_message, re.IGNORECASE):
                return True
        return False

    def _parse_answer_to_params(
        self,
        ai_question: str,
        user_answer: str,
        pending_params: List[str]
    ) -> Dict[str, str]:
        """
        사용자 답변을 파라미터에 매핑

        Args:
            ai_question: AI의 되묻기 질문
            user_answer: 사용자 답변
            pending_params: 기대하는 파라미터 목록

        Returns:
            파라미터 매핑 딕셔너리
        """
        result = {}

        # 파라미터 패턴 - AI 질문에서 어떤 파라미터를 묻는지 식별
        PARAM_QUESTION_PATTERNS = {
            "channel": [
                r"(?:slack|슬랙).*?채널",
                r"채널.*?(?:알려|입력|지정)",
                r"which.*channel",
                r"#\w+",
            ],
            "line_code": [
                r"(?:라인|line).*?(?:코드|id|code|정지)",
                r"(?:정지|stop).*?라인",
                r"어떤.*?라인",
                r"which.*line",
            ],
            "equipment_id": [
                r"(?:장비|equipment).*?(?:id|코드)",
                r"어떤.*?장비",
                r"which.*equipment",
            ],
            "to": [
                r"(?:이메일|email).*?(?:주소|수신)",
                r"(?:받을|receive).*?(?:이메일|email)",
            ],
        }

        # AI 질문에서 요청된 파라미터 순서 파악
        requested_params = []
        for param in pending_params:
            patterns = PARAM_QUESTION_PATTERNS.get(param, [])
            for pattern in patterns:
                if re.search(pattern, ai_question, re.IGNORECASE):
                    if param not in requested_params:
                        requested_params.append(param)
                    break

        # 순서 정보가 없으면 pending_params 순서 사용
        if not requested_params:
            requested_params = list(pending_params)

        # 사용자 답변 분리 (쉼표, 줄바꿈, "그리고", "와/과")
        answer_values = re.split(r'[,\n]|(?:\s+(?:그리고|와|과|and)\s+)', user_answer)
        answer_values = [v.strip() for v in answer_values if v.strip()]

        # 번호 매기기 형식 처리 ("1. 뉴-채널", "2. 라인 B")
        clean_values = []
        for val in answer_values:
            # "1. 값" 또는 "1) 값" 형식에서 값만 추출
            match = re.match(r'^\d+[\.\)]\s*(.+)$', val)
            if match:
                clean_values.append(match.group(1).strip())
            else:
                clean_values.append(val)

        # 파라미터에 값 매핑
        for i, param in enumerate(requested_params):
            if i < len(clean_values):
                value = clean_values[i]
                # 채널 앞에 # 추가 (없는 경우)
                if param == "channel" and not value.startswith("#"):
                    value = f"#{value}"
                result[param] = value
                logger.info(f"[ParamBind] Mapped {param} = '{value}'")

        return result

    def _validate_workflow_parameters(
        self,
        dsl: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> tuple[bool, List[str], Dict[str, Any]]:
        """
        워크플로우 전체의 빈 파라미터 검증
        모든 노드(액션, 조건, 트리거)에서 필수 파라미터가 누락되면 되묻기 메시지 반환

        Args:
            dsl: 워크플로우 DSL
            conversation_history: 대화 기록 (파라미터 추출용)

        Returns:
            (is_valid, missing_prompts, updated_dsl)
            - is_valid: 모든 파라미터가 유효한지 여부
            - missing_prompts: 누락된 파라미터에 대한 되묻기 메시지
            - updated_dsl: 대화 기록에서 추출한 파라미터가 적용된 DSL
        """
        import copy
        updated_dsl = copy.deepcopy(dsl)
        missing_prompts: List[str] = []

        # 대화 기록에서 파라미터 추출 (있는 경우)
        extracted_params: Dict[str, str] = {}
        if conversation_history:
            # 모든 가능한 파라미터 타입 추출 시도
            all_params = ["channel", "line_code", "equipment_id", "to", "phone", "sensor_id"]
            extracted_params = self._extract_parameters_from_conversation(
                conversation_history, all_params
            )
            if extracted_params:
                logger.info(f"[ValidateParams] Extracted from conversation: {extracted_params}")

        # AI가 흔히 사용하는 명백한 placeholder 패턴만 (실제 사용 가능한 값 제외)
        # 주의: LINE_A, LINE_B 같은 실제 라인 코드는 여기 포함하면 안됨
        DEFAULT_VALUE_PATTERNS = {
            "channel": ["#alerts", "#general", "#channel", "#notification"],  # #production-alerts 같은 구체적 채널 허용
            "line_code": ["LINE_001", "LINE_1", "PRODUCTION_LINE"],  # LINE_A, LINE_B 등 실제 라인 코드는 허용
            "equipment_id": ["EQ_001", "EQUIPMENT_001", "MACHINE_001"],
            "to": ["admin@example.com", "user@example.com", "alert@company.com", "example@example.com"],
            "phone": ["+82-10-0000-0000", "010-0000-0000", "+1-000-000-0000", "000-0000-0000"],
            "url": ["https://example.com", "http://example.com", "https://api.example.com"],
            "table": ["data_table", "table_name"],  # sensor_data 같은 실제 테이블 이름은 허용
            "filename": ["output.csv", "data.csv", "file.csv"],
            "sensor_id": ["SENSOR_001", "SENSOR_A"],  # TEMP_001 같은 구체적 센서 ID는 허용
        }

        def is_default_value(param: str, value: Any) -> bool:
            """기본값/예시값인지 확인"""
            if not value:
                return True
            str_value = str(value).strip()
            # 패턴 목록에 있는지 확인
            patterns = DEFAULT_VALUE_PATTERNS.get(param, [])
            if str_value in patterns:
                return True
            # 일반적인 placeholder 패턴
            if any(p in str_value.upper() for p in ["UNKNOWN", "???", "TBD", "PLACEHOLDER", "EXAMPLE"]):
                return True
            return False

        # 1. 트리거 검증
        trigger = updated_dsl.get("trigger", {})
        trigger_type = trigger.get("type")
        trigger_reqs = NODE_PARAMETER_REQUIREMENTS.get("trigger", {}).get(trigger_type, {})
        for param in trigger_reqs.get("required", []):
            if not trigger.get("config", {}).get(param):
                prompt = trigger_reqs.get("prompts", {}).get(param, f"트리거의 {param}을(를) 입력해주세요.")
                missing_prompts.append(f"[트리거] {prompt}")

        # 2. 노드 검증 및 파라미터 적용 (재귀)
        def validate_and_apply_params(nodes: List[Dict[str, Any]]):
            for node in nodes:
                node_id = node.get("id", "unknown")
                node_type = node.get("type")
                config = node.get("config", {})

                if node_type == "action":
                    # 액션 타입 확인 (action_type 또는 action 키)
                    action_type = config.get("action_type") or config.get("action")
                    action_reqs = NODE_PARAMETER_REQUIREMENTS.get("action", {}).get(action_type, {})

                    # 파라미터 별칭 매핑 (LLM이 잘못된 이름 사용할 경우 대비)
                    param_aliases = {
                        "line_code": ["line", "line_id"],
                        "equipment_id": ["equipment", "eq_id"],
                        "sensor_id": ["sensor"],
                    }

                    for param in action_reqs.get("required", []):
                        # parameters 내부 또는 config 최상위에서 확인
                        param_value = config.get(param) or config.get("parameters", {}).get(param)

                        # 별칭 확인 (원래 파라미터가 없는 경우)
                        if not param_value and param in param_aliases:
                            for alias in param_aliases[param]:
                                param_value = config.get(alias) or config.get("parameters", {}).get(alias)
                                if param_value:
                                    break

                        is_default = is_default_value(param, param_value)

                        # 기본값이고 대화 기록에서 추출한 값이 있으면 적용
                        if (not param_value or is_default) and param in extracted_params:
                            new_value = extracted_params[param]
                            # parameters 딕셔너리가 있으면 거기에, 없으면 config에 적용
                            if "parameters" in config:
                                config["parameters"][param] = new_value
                            else:
                                config[param] = new_value
                            param_value = new_value
                            is_default = False
                            logger.info(f"[ValidateParams] Applied extracted param: {param}='{new_value}' to node {node_id}")

                        # 여전히 빈 값이거나 기본값 패턴인 경우 되묻기
                        if not param_value or is_default:
                            prompt = action_reqs.get("prompts", {}).get(param, f"{action_type}의 {param}을(를) 입력해주세요.")
                            missing_prompts.append(f"[{node_id}] {prompt}")

                elif node_type in ("condition", "if_else"):
                    cond_reqs = NODE_PARAMETER_REQUIREMENTS.get(node_type, {})
                    condition = config.get("condition", {})

                    # condition이 객체인 경우 (구조화된 조건)
                    if isinstance(condition, dict):
                        for param in cond_reqs.get("required", []):
                            key = param.replace("condition.", "")
                            if not condition.get(key):
                                prompt = cond_reqs.get("prompts", {}).get(param, f"조건의 {key}을(를) 입력해주세요.")
                                missing_prompts.append(f"[{node_id}] {prompt}")
                    # condition이 문자열인 경우 (예: "temperature > 80") - 이미 완성된 조건이므로 검증 불필요

                # 중첩 노드 재귀 검증
                for branch in ["then_nodes", "else_nodes", "loop_nodes", "parallel_nodes"]:
                    if node.get(branch):
                        validate_and_apply_params(node[branch])

        validate_and_apply_params(updated_dsl.get("nodes", []))

        return len(missing_prompts) == 0, missing_prompts, updated_dsl
