"""
Judgment Agent
센서 데이터 분석 및 룰 기반 판단 수행
"""
from typing import Any, Dict, List
from datetime import datetime, timedelta
from uuid import UUID
import logging
from pathlib import Path

from sqlalchemy.orm import Session

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
