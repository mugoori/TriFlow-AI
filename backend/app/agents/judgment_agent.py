"""
Judgment Agent
센서 데이터 분석 및 룰 기반 판단 수행
"""
from typing import Any, Dict, List
from datetime import datetime, timedelta
from uuid import UUID
import logging
from pathlib import Path


from .base_agent import BaseAgent
from app.database import get_db_context
from app.models.core import SensorData, Ruleset
from app.tools.rhai import RhaiEngine
from app.services.rag_service import get_rag_service
from app.services.judgment_policy import (
    get_hybrid_judgment_service,
    JudgmentPolicy,
    JudgmentResult,
)
from app.services.judgment_cache import get_judgment_cache

logger = logging.getLogger(__name__)


class JudgmentAgent(BaseAgent):
    """
    Judgment Agent
    - 센서 데이터 조회 및 분석
    - Rhai 룰 엔진 실행
    - RAG 지식 검색
    - 하이브리드 판단 정책 (스펙 B-6)
    """

    def __init__(self):
        super().__init__(
            name="JudgmentAgent",
            max_tokens=4096,
        )  # model은 get_model()에서 동적으로 조회
        self.rhai_engine = RhaiEngine()
        self.hybrid_service = get_hybrid_judgment_service()
        self.judgment_cache = get_judgment_cache()

    def get_system_prompt(self) -> str:
        """
        시스템 프롬프트 로드
        """
        prompt_path = Path(__file__).parent.parent / "prompts" / "judgment_agent.md"
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"Prompt file not found: {prompt_path}, using default")
            return "You are a Judgment Agent for TriFlow AI."

    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Judgment Agent의 Tool 정의
        """
        return [
            {
                "name": "fetch_sensor_history",
                "description": "센서 데이터 이력을 조회합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "sensor_type": {
                            "type": "string",
                            "description": "센서 타입 (예: temperature, pressure)",
                        },
                        "line_code": {
                            "type": "string",
                            "description": "라인 코드",
                        },
                        "hours": {
                            "type": "integer",
                            "description": "조회할 시간 범위 (시간 단위, 기본: 24)",
                            "default": 24,
                        },
                        "limit": {
                            "type": "integer",
                            "description": "최대 반환 레코드 수 (기본: 100)",
                            "default": 100,
                        },
                    },
                    "required": ["sensor_type", "line_code"],
                },
            },
            {
                "name": "run_rhai_engine",
                "description": "Rhai 룰 엔진을 실행하여 판단을 수행합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "ruleset_id": {
                            "type": "string",
                            "description": "실행할 Ruleset ID (UUID)",
                        },
                        "input_data": {
                            "type": "object",
                            "description": "룰에 전달할 입력 데이터",
                        },
                    },
                    "required": ["ruleset_id", "input_data"],
                },
            },
            {
                "name": "query_rag_knowledge",
                "description": "RAG 시스템에서 관련 지식을 검색합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "검색 쿼리",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "반환할 문서 수 (기본: 3)",
                            "default": 3,
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "get_line_status",
                "description": "특정 생산 라인의 현재 상태를 종합적으로 조회하고 판단합니다. 온도, 압력, 습도 등 모든 센서 데이터를 확인하고 정상/경고/위험 상태를 판단합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "line_code": {
                            "type": "string",
                            "description": "라인 코드 (예: LINE_A, LINE_B, LINE_C, LINE_D)",
                        },
                    },
                    "required": ["line_code"],
                },
            },
            {
                "name": "get_available_lines",
                "description": "사용 가능한 생산 라인 목록을 조회합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "create_ruleset",
                "description": "사용자의 자연어 요청을 Rhai 스크립트로 변환하여 새로운 규칙(Ruleset)을 생성합니다. 예: '온도가 80도 넘으면 알림 보내줘' → Rhai 스크립트 자동 생성",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "규칙 이름 (한글 가능, 예: '온도 경고 규칙')",
                        },
                        "description": {
                            "type": "string",
                            "description": "규칙 설명",
                        },
                        "condition_type": {
                            "type": "string",
                            "enum": ["threshold", "range", "comparison", "complex"],
                            "description": "조건 유형: threshold(임계값 초과/미만), range(범위), comparison(비교), complex(복합)",
                        },
                        "sensor_type": {
                            "type": "string",
                            "description": "대상 센서 타입 (temperature, pressure, humidity, vibration, flow_rate)",
                        },
                        "operator": {
                            "type": "string",
                            "enum": [">", "<", ">=", "<=", "==", "!="],
                            "description": "비교 연산자",
                        },
                        "threshold_value": {
                            "type": "number",
                            "description": "임계값 (숫자)",
                        },
                        "threshold_value_2": {
                            "type": "number",
                            "description": "두 번째 임계값 (범위 조건에서 사용)",
                        },
                        "action_type": {
                            "type": "string",
                            "enum": ["alert", "warning", "log", "stop_line", "notify"],
                            "description": "조건 충족 시 동작 유형",
                        },
                        "action_message": {
                            "type": "string",
                            "description": "알림/로그 메시지",
                        },
                    },
                    "required": ["name", "condition_type", "sensor_type", "operator", "threshold_value", "action_type"],
                },
            },
            {
                "name": "hybrid_judgment",
                "description": "하이브리드 정책을 사용하여 센서 데이터를 판단합니다. 룰과 LLM을 조합하여 더 정확한 판단을 수행합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "ruleset_id": {
                            "type": "string",
                            "description": "사용할 Ruleset ID (UUID)",
                        },
                        "input_data": {
                            "type": "object",
                            "description": "판단할 센서 데이터 (예: {temperature: 85, pressure: 120})",
                        },
                        "policy": {
                            "type": "string",
                            "enum": ["rule_only", "llm_only", "hybrid_weighted", "escalate"],
                            "description": "판단 정책 (기본: hybrid_weighted)",
                            "default": "hybrid_weighted",
                        },
                        "context": {
                            "type": "object",
                            "description": "추가 컨텍스트 정보 (라인 코드, 시간대 등)",
                        },
                    },
                    "required": ["ruleset_id", "input_data"],
                },
            },
            {
                "name": "get_judgment_cache_stats",
                "description": "판단 캐시 통계를 조회합니다 (캐시 히트율, 항목 수 등).",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]

    def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """
        Tool 실행
        """
        if tool_name == "fetch_sensor_history":
            return self._fetch_sensor_history(
                sensor_type=tool_input["sensor_type"],
                line_code=tool_input["line_code"],
                hours=tool_input.get("hours", 24),
                limit=tool_input.get("limit", 100),
            )

        elif tool_name == "run_rhai_engine":
            return self._run_rhai_engine(
                ruleset_id=tool_input["ruleset_id"],
                input_data=tool_input["input_data"],
            )

        elif tool_name == "query_rag_knowledge":
            return self._query_rag_knowledge(
                query=tool_input["query"],
                top_k=tool_input.get("top_k", 3),
            )

        elif tool_name == "get_line_status":
            return self._get_line_status(
                line_code=tool_input["line_code"],
            )

        elif tool_name == "get_available_lines":
            return self._get_available_lines()

        elif tool_name == "create_ruleset":
            return self._create_ruleset(
                name=tool_input["name"],
                description=tool_input.get("description"),
                condition_type=tool_input["condition_type"],
                sensor_type=tool_input["sensor_type"],
                operator=tool_input["operator"],
                threshold_value=tool_input["threshold_value"],
                threshold_value_2=tool_input.get("threshold_value_2"),
                action_type=tool_input["action_type"],
                action_message=tool_input.get("action_message"),
            )

        elif tool_name == "hybrid_judgment":
            return self._hybrid_judgment(
                ruleset_id=tool_input["ruleset_id"],
                input_data=tool_input["input_data"],
                policy=tool_input.get("policy", "hybrid_weighted"),
                context=tool_input.get("context"),
            )

        elif tool_name == "get_judgment_cache_stats":
            return self._get_judgment_cache_stats()

        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    def _fetch_sensor_history(
        self,
        sensor_type: str,
        line_code: str,
        hours: int = 24,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        센서 데이터 이력 조회
        """
        try:
            with get_db_context() as db:
                cutoff_time = datetime.utcnow() - timedelta(hours=hours)

                query = db.query(SensorData).filter(
                    SensorData.sensor_type == sensor_type,
                    SensorData.line_code == line_code,
                    SensorData.recorded_at >= cutoff_time,
                ).order_by(SensorData.recorded_at.desc()).limit(limit)

                results = query.all()

                data = [
                    {
                        "sensor_id": str(r.sensor_id),
                        "sensor_type": r.sensor_type,
                        "line_code": r.line_code,
                        "value": r.value,
                        "unit": r.unit,
                        "recorded_at": r.recorded_at.isoformat(),
                        "metadata": r.sensor_metadata,
                    }
                    for r in results
                ]

                logger.info(
                    f"Fetched {len(data)} sensor records for {sensor_type} on {line_code}"
                )

                return {
                    "success": True,
                    "count": len(data),
                    "data": data,
                    "query": {
                        "sensor_type": sensor_type,
                        "line_code": line_code,
                        "hours": hours,
                    },
                }

        except Exception as e:
            logger.error(f"Error fetching sensor history: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": [],
            }

    def _run_rhai_engine(
        self,
        ruleset_id: str,
        input_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Rhai 룰 엔진 실행
        """
        try:
            with get_db_context() as db:
                ruleset = db.query(Ruleset).filter(
                    Ruleset.ruleset_id == UUID(ruleset_id)
                ).first()

                if not ruleset:
                    return {
                        "success": False,
                        "error": f"Ruleset {ruleset_id} not found",
                    }

                if not ruleset.is_active:
                    return {
                        "success": False,
                        "error": f"Ruleset {ruleset_id} is inactive",
                    }

                # Rhai 엔진 실행
                result = self.rhai_engine.execute(
                    script=ruleset.rhai_script,
                    context=input_data,
                )

                logger.info(f"Rhai engine executed for ruleset {ruleset_id}")

                return {
                    "success": True,
                    "ruleset_id": ruleset_id,
                    "ruleset_name": ruleset.name,
                    "result": result,
                }

        except Exception as e:
            logger.error(f"Error running Rhai engine: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def _query_rag_knowledge(
        self,
        query: str,
        top_k: int = 3,
        tenant_id: UUID = None,
    ) -> Dict[str, Any]:
        """
        RAG 지식 검색 (pgvector 기반)
        """
        logger.info(f"RAG query: {query}")

        # tenant_id가 없으면 기본 테넌트 사용
        if tenant_id is None:
            # 기본 테넌트 ID (실제로는 컨텍스트에서 가져와야 함)
            from uuid import UUID as UUIDType
            tenant_id = UUIDType("446e39b3-455e-4ca9-817a-4913921eb41d")

        try:
            import asyncio
            rag_service = get_rag_service()

            # 동기 컨텍스트에서 비동기 호출
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 이미 이벤트 루프가 실행 중인 경우
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        rag_service.search(tenant_id, query, top_k=top_k)
                    )
                    result = future.result()
            else:
                result = asyncio.run(rag_service.search(tenant_id, query, top_k=top_k))

            if result["success"] and result["results"]:
                documents = [
                    {
                        "id": doc["document_id"],
                        "content": doc["chunk_text"],
                        "title": doc["title"],
                        "relevance": doc["similarity"],
                    }
                    for doc in result["results"]
                ]
                return {
                    "success": True,
                    "query": query,
                    "documents": documents,
                    "count": len(documents),
                }
            else:
                # RAG 결과가 없으면 기본 응답
                logger.info("No RAG results found, returning defaults")
                return {
                    "success": True,
                    "query": query,
                    "documents": [
                        {
                            "id": "default1",
                            "content": "정상 온도 범위는 20-25도입니다.",
                            "title": "기본 매뉴얼",
                            "relevance": 0.5,
                        },
                    ],
                    "note": "No matching documents found, using defaults",
                }

        except Exception as e:
            logger.error(f"RAG query error: {e}")
            # 에러 시 기본 응답
            return {
                "success": True,
                "query": query,
                "documents": [
                    {
                        "id": "fallback",
                        "content": "시스템 매뉴얼을 참조하세요.",
                        "title": "Fallback",
                        "relevance": 0.3,
                    },
                ],
                "error": str(e),
            }

    def _get_line_status(self, line_code: str) -> Dict[str, Any]:
        """
        특정 라인의 종합 상태 조회 및 판단
        """
        try:
            from sqlalchemy import func

            with get_db_context() as db:
                # 최근 1시간 데이터 기준
                cutoff_time = datetime.utcnow() - timedelta(hours=1)

                # 센서 타입별 최신 평균값 조회
                sensor_types = ['temperature', 'pressure', 'humidity', 'vibration', 'flow_rate']
                sensor_data = {}

                for sensor_type in sensor_types:
                    result = db.query(
                        func.avg(SensorData.value).label('avg_value'),
                        func.max(SensorData.value).label('max_value'),
                        func.min(SensorData.value).label('min_value'),
                        func.count(SensorData.sensor_id).label('count'),
                    ).filter(
                        SensorData.line_code == line_code,
                        SensorData.sensor_type == sensor_type,
                        SensorData.recorded_at >= cutoff_time,
                    ).first()

                    if result and result.count > 0:
                        sensor_data[sensor_type] = {
                            "avg": round(result.avg_value, 2) if result.avg_value else None,
                            "max": round(result.max_value, 2) if result.max_value else None,
                            "min": round(result.min_value, 2) if result.min_value else None,
                            "readings": result.count,
                        }

                if not sensor_data:
                    return {
                        "success": False,
                        "line_code": line_code,
                        "error": f"No sensor data found for {line_code} in the last hour",
                    }

                # 룰 엔진으로 판단 수행
                input_for_rules = {
                    "temperature": sensor_data.get("temperature", {}).get("avg", 0),
                    "pressure": sensor_data.get("pressure", {}).get("avg", 0),
                    "humidity": sensor_data.get("humidity", {}).get("avg", 0),
                }

                judgment_result = self.rhai_engine.execute(
                    script="// Auto judgment",
                    context={"input": input_for_rules},
                )

                # 상태 요약
                overall_status = judgment_result.get("status", "UNKNOWN")
                checks = judgment_result.get("checks", [])

                logger.info(f"Line status check for {line_code}: {overall_status}")

                return {
                    "success": True,
                    "line_code": line_code,
                    "timestamp": datetime.utcnow().isoformat(),
                    "overall_status": overall_status,
                    "confidence": judgment_result.get("confidence", 0.9),
                    "sensor_summary": sensor_data,
                    "checks": checks,
                    "recommendation": self._get_recommendation(overall_status, checks),
                }

        except Exception as e:
            logger.error(f"Error getting line status: {e}")
            return {
                "success": False,
                "line_code": line_code,
                "error": str(e),
            }

    def _get_available_lines(self) -> Dict[str, Any]:
        """
        사용 가능한 라인 목록 조회
        """
        try:
            from sqlalchemy import distinct

            with get_db_context() as db:
                # DB에서 실제 라인 목록 조회
                lines = db.query(distinct(SensorData.line_code)).all()
                line_list = [row[0] for row in lines if row[0]]

                if not line_list:
                    # 기본값
                    line_list = ["LINE_A", "LINE_B", "LINE_C", "LINE_D"]

                return {
                    "success": True,
                    "lines": sorted(line_list),
                    "count": len(line_list),
                }

        except Exception as e:
            logger.error(f"Error getting available lines: {e}")
            return {
                "success": False,
                "error": str(e),
                "lines": ["LINE_A", "LINE_B", "LINE_C", "LINE_D"],  # fallback
            }

    def _get_recommendation(self, status: str, checks: List[Dict]) -> str:
        """
        상태에 따른 추천 조치 생성
        """
        if status == "CRITICAL":
            issues = [c["message"] for c in checks if c.get("status") in ["CRITICAL", "HIGH"]]
            return f"즉시 점검 필요: {'; '.join(issues)}"
        elif status == "WARNING":
            issues = [c["message"] for c in checks if c.get("status") in ["WARNING", "HIGH", "LOW"]]
            return f"주의 관찰 필요: {'; '.join(issues)}"
        else:
            return "모든 센서가 정상 범위입니다. 특별한 조치가 필요하지 않습니다."

    def _create_ruleset(
        self,
        name: str,
        condition_type: str,
        sensor_type: str,
        operator: str,
        threshold_value: float,
        action_type: str,
        description: str = None,
        threshold_value_2: float = None,
        action_message: str = None,
    ) -> Dict[str, Any]:
        """
        자연어 요청을 기반으로 Rhai 스크립트를 생성하고 Ruleset을 DB에 저장
        """
        try:
            # Rhai 스크립트 생성
            rhai_script = self._generate_rhai_script(
                condition_type=condition_type,
                sensor_type=sensor_type,
                operator=operator,
                threshold_value=threshold_value,
                threshold_value_2=threshold_value_2,
                action_type=action_type,
                action_message=action_message or f"{sensor_type} 이상 감지",
            )

            # DB에 Ruleset 저장
            with get_db_context() as db:
                from uuid import uuid4

                new_ruleset = Ruleset(
                    ruleset_id=uuid4(),
                    name=name,
                    description=description or f"{sensor_type} {operator} {threshold_value} 조건 규칙",
                    rhai_script=rhai_script,
                    version="1.0.0",
                    is_active=False,  # 사용자가 테스트 후 활성화
                )

                db.add(new_ruleset)
                db.commit()
                db.refresh(new_ruleset)

                logger.info(f"Created ruleset: {new_ruleset.ruleset_id} - {name}")

                return {
                    "success": True,
                    "ruleset_id": str(new_ruleset.ruleset_id),
                    "name": name,
                    "description": new_ruleset.description,
                    "rhai_script": rhai_script,
                    "is_active": False,
                    "message": f"규칙 '{name}'이 생성되었습니다. Rulesets 탭에서 테스트 후 활성화하세요.",
                }

        except Exception as e:
            logger.error(f"Error creating ruleset: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def _generate_rhai_script(
        self,
        condition_type: str,
        sensor_type: str,
        operator: str,
        threshold_value: float,
        threshold_value_2: float = None,
        action_type: str = "alert",
        action_message: str = "조건 충족",
    ) -> str:
        """
        조건 정보를 기반으로 Rhai 스크립트 생성
        """
        # 센서 타입별 한글 이름
        sensor_names = {
            "temperature": "온도",
            "pressure": "압력",
            "humidity": "습도",
            "vibration": "진동",
            "flow_rate": "유량",
        }
        sensor_name_kr = sensor_names.get(sensor_type, sensor_type)

        # 액션 타입별 결과
        action_results = {
            "alert": f'"alert", message: "{action_message}", severity: "high"',
            "warning": f'"warning", message: "{action_message}", severity: "medium"',
            "log": f'"log", message: "{action_message}", severity: "low"',
            "stop_line": f'"stop_line", message: "{action_message}", severity: "critical"',
            "notify": f'"notify", message: "{action_message}", severity: "medium"',
        }
        action_result = action_results.get(action_type, action_results["alert"])

        # 조건 유형별 스크립트 생성
        if condition_type == "threshold":
            # 단순 임계값 조건
            script = f'''// {sensor_name_kr} 임계값 체크 규칙
// 자동 생성됨 - AI Chat

let value = input.{sensor_type};
let threshold = {threshold_value};

if value {operator} threshold {{
    #{{
        action: {action_result}
    }}
}} else {{
    #{{
        action: "none",
        message: "{sensor_name_kr} 정상 범위",
        value: value
    }}
}}
'''
        elif condition_type == "range":
            # 범위 조건 (threshold_value ~ threshold_value_2)
            min_val = min(threshold_value, threshold_value_2 or threshold_value)
            max_val = max(threshold_value, threshold_value_2 or threshold_value)
            script = f'''// {sensor_name_kr} 범위 체크 규칙
// 자동 생성됨 - AI Chat

let value = input.{sensor_type};
let min_threshold = {min_val};
let max_threshold = {max_val};

if value < min_threshold || value > max_threshold {{
    #{{
        action: {action_result}
    }}
}} else {{
    #{{
        action: "none",
        message: "{sensor_name_kr} 정상 범위 ({min_val} ~ {max_val})",
        value: value
    }}
}}
'''
        else:
            # 기본: 단순 비교
            script = f'''// {sensor_name_kr} 체크 규칙
// 자동 생성됨 - AI Chat

let value = input.{sensor_type};

if value {operator} {threshold_value} {{
    #{{
        action: {action_result}
    }}
}} else {{
    #{{
        action: "none",
        message: "{sensor_name_kr} 정상",
        value: value
    }}
}}
'''

        return script

    def _hybrid_judgment(
        self,
        ruleset_id: str,
        input_data: Dict[str, Any],
        policy: str = "hybrid_weighted",
        context: Dict[str, Any] = None,
        tenant_id: UUID = None,
    ) -> Dict[str, Any]:
        """
        하이브리드 정책 판단 실행

        정책:
        - rule_only: 룰만 사용 (속도 우선)
        - llm_only: LLM만 사용 (유연성 우선)
        - hybrid_weighted: 룰 + LLM 가중 조합 (기본)
        - escalate: 룰 우선, 불확실 시 LLM으로 에스컬레이션
        """
        import asyncio

        # tenant_id 기본값
        if tenant_id is None:
            from uuid import UUID as UUIDType
            tenant_id = UUIDType("446e39b3-455e-4ca9-817a-4913921eb41d")

        # 정책 매핑
        policy_map = {
            "rule_only": JudgmentPolicy.RULE_ONLY,
            "llm_only": JudgmentPolicy.LLM_ONLY,
            "hybrid_weighted": JudgmentPolicy.HYBRID_WEIGHTED,
            "escalate": JudgmentPolicy.ESCALATE,
        }
        judgment_policy = policy_map.get(policy, JudgmentPolicy.HYBRID_WEIGHTED)

        try:
            # 동기 컨텍스트에서 비동기 호출
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.hybrid_service.execute(
                            tenant_id=tenant_id,
                            ruleset_id=UUID(ruleset_id),
                            input_data=input_data,
                            policy=judgment_policy,
                            context=context,
                        )
                    )
                    result = future.result()
            else:
                result = asyncio.run(
                    self.hybrid_service.execute(
                        tenant_id=tenant_id,
                        ruleset_id=UUID(ruleset_id),
                        input_data=input_data,
                        policy=judgment_policy,
                        context=context,
                    )
                )

            logger.info(
                f"Hybrid judgment completed: {result.decision} "
                f"(confidence: {result.confidence}, source: {result.source})"
            )

            return {
                "success": True,
                "decision": result.decision,
                "confidence": result.confidence,
                "source": result.source,
                "policy_used": result.policy_used.value,
                "cached": result.cached,
                "execution_time_ms": result.execution_time_ms,
                "details": result.details,
                "recommendation": self._get_recommendation_from_result(result),
            }

        except Exception as e:
            logger.error(f"Hybrid judgment error: {e}")
            return {
                "success": False,
                "error": str(e),
                "decision": "UNKNOWN",
                "confidence": 0.0,
            }

    def _get_judgment_cache_stats(self, tenant_id: UUID = None) -> Dict[str, Any]:
        """
        판단 캐시 통계 조회
        """
        import asyncio

        if tenant_id is None:
            from uuid import UUID as UUIDType
            tenant_id = UUIDType("446e39b3-455e-4ca9-817a-4913921eb41d")

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.judgment_cache.get_stats(tenant_id)
                    )
                    stats = future.result()
            else:
                stats = asyncio.run(self.judgment_cache.get_stats(tenant_id))

            return {
                "success": True,
                "stats": stats,
            }

        except Exception as e:
            logger.error(f"Cache stats error: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def _get_recommendation_from_result(self, result: JudgmentResult) -> str:
        """
        판단 결과에서 추천 조치 생성
        """
        decision = result.decision
        confidence = result.confidence

        if decision == "CRITICAL":
            if confidence >= 0.8:
                return "즉시 점검이 필요합니다. 생산 라인 정지를 고려하세요."
            else:
                return "위험 상황으로 판단되나 추가 확인이 필요합니다."
        elif decision == "WARNING":
            if confidence >= 0.8:
                return "주의가 필요합니다. 센서 데이터를 계속 모니터링하세요."
            else:
                return "경고 수준으로 보이나 추가 데이터 확인을 권장합니다."
        elif decision == "OK":
            return "정상 상태입니다. 특별한 조치가 필요하지 않습니다."
        else:
            return "판단을 내리기 어렵습니다. 수동 확인이 필요합니다."
