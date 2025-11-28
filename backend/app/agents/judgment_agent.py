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

logger = logging.getLogger(__name__)


class JudgmentAgent(BaseAgent):
    """
    Judgment Agent
    - 센서 데이터 조회 및 분석
    - Rhai 룰 엔진 실행
    - RAG 지식 검색
    """

    def __init__(self):
        super().__init__(
            name="JudgmentAgent",
            model="claude-sonnet-4-5-20250929",
            max_tokens=4096,
        )
        self.rhai_engine = RhaiEngine()

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
    ) -> Dict[str, Any]:
        """
        RAG 지식 검색
        MVP: 간단한 플레이스홀더 구현
        V1에서 pgvector 기반 실제 구현 예정
        """
        logger.info(f"RAG query (placeholder): {query}")

        # TODO: 실제 RAG 구현 (pgvector + embedding)
        # 현재는 더미 데이터 반환
        dummy_docs = [
            {
                "id": "doc1",
                "content": "정상 온도 범위는 20-25도입니다.",
                "relevance": 0.95,
            },
            {
                "id": "doc2",
                "content": "압력이 100 PSI를 초과하면 경고를 발생시킵니다.",
                "relevance": 0.87,
            },
            {
                "id": "doc3",
                "content": "센서 보정은 매주 월요일에 수행합니다.",
                "relevance": 0.72,
            },
        ]

        return {
            "success": True,
            "query": query,
            "documents": dummy_docs[:top_k],
            "note": "MVP: Placeholder implementation. Real RAG coming in V1.",
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
