"""
BI Planner Agent
데이터 분석 및 차트 생성 (Text-to-SQL)
"""
from typing import Any, Dict, List
import logging
from pathlib import Path
import json

from .base_agent import BaseAgent
from app.tools.db import get_table_schema, execute_safe_sql

logger = logging.getLogger(__name__)


class BIPlannerAgent(BaseAgent):
    """
    BI Planner Agent
    - Text-to-SQL: 자연어를 SQL 쿼리로 변환
    - 데이터 분석: 센서 데이터, 생산 데이터, 품질 데이터 분석
    - 시각화 설계: 분석 결과를 차트로 표현
    """

    def __init__(self):
        super().__init__(
            name="BIPlannerAgent",
            model="claude-sonnet-4-5-20250929",
            max_tokens=4096,
        )

    def get_system_prompt(self) -> str:
        """
        시스템 프롬프트 로드
        """
        prompt_path = Path(__file__).parent.parent / "prompts" / "bi_planner.md"
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"Prompt file not found: {prompt_path}, using default")
            return "You are a BI Planner Agent for TriFlow AI."

    def get_tools(self) -> List[Dict[str, Any]]:
        """
        BI Planner Agent의 Tool 정의
        """
        return [
            {
                "name": "get_table_schema",
                "description": "데이터베이스 테이블 스키마를 조회합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "조회할 테이블 이름 (예: sensor_data, judgment_executions)",
                        },
                        "schema": {
                            "type": "string",
                            "description": "스키마 이름 (기본값: core)",
                            "enum": ["core", "bi", "rag", "audit"],
                            "default": "core",
                        },
                    },
                    "required": ["table_name"],
                },
            },
            {
                "name": "execute_safe_sql",
                "description": "안전한 SQL 쿼리를 실행합니다 (SELECT만 허용). CRITICAL: tenant_id 필터 필수!",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "sql_query": {
                            "type": "string",
                            "description": "실행할 SQL 쿼리 (SELECT 문만 허용). 반드시 tenant_id 필터 포함 필요. 파라미터는 :param_name 형식 사용.",
                        },
                        "params": {
                            "type": "object",
                            "description": "쿼리 파라미터 (SQL Injection 방지용)",
                        },
                    },
                    "required": ["sql_query"],
                },
            },
            {
                "name": "generate_chart_config",
                "description": "분석 결과를 시각화할 차트 설정을 생성합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "array",
                            "description": "차트에 표시할 데이터 (JSON 배열)",
                        },
                        "chart_type": {
                            "type": "string",
                            "description": "차트 유형",
                            "enum": ["line", "bar", "pie", "area", "scatter", "table"],
                        },
                        "analysis_goal": {
                            "type": "string",
                            "description": "분석 목적 (예: 추이 분석, 비교, 분포)",
                        },
                        "x_axis": {
                            "type": "string",
                            "description": "X축 데이터 키 (line, bar, area, scatter에서 필수)",
                        },
                        "y_axis": {
                            "type": "string",
                            "description": "Y축 데이터 키 (line, bar, area, scatter에서 필수)",
                        },
                        "group_by": {
                            "type": "string",
                            "description": "그룹화 기준 (선택)",
                        },
                    },
                    "required": ["data", "chart_type", "analysis_goal"],
                },
            },
        ]

    def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """
        Tool 실행
        """
        if tool_name == "get_table_schema":
            return self._get_table_schema(
                table_name=tool_input["table_name"],
                schema=tool_input.get("schema", "core"),
            )

        elif tool_name == "execute_safe_sql":
            return self._execute_safe_sql(
                sql_query=tool_input["sql_query"],
                params=tool_input.get("params"),
            )

        elif tool_name == "generate_chart_config":
            return self._generate_chart_config(
                data=tool_input["data"],
                chart_type=tool_input["chart_type"],
                analysis_goal=tool_input["analysis_goal"],
                x_axis=tool_input.get("x_axis"),
                y_axis=tool_input.get("y_axis"),
                group_by=tool_input.get("group_by"),
            )

        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    def _get_table_schema(
        self,
        table_name: str,
        schema: str = "core",
    ) -> Dict[str, Any]:
        """
        테이블 스키마 조회
        """
        try:
            schema_info = get_table_schema(schema, table_name)

            logger.info(f"Retrieved schema for {schema}.{table_name}: {len(schema_info['columns'])} columns")

            return {
                "success": True,
                "schema": schema,
                "table": table_name,
                "columns": schema_info["columns"],
            }

        except Exception as e:
            logger.error(f"Error getting table schema: {e}")
            return {
                "success": False,
                "error": str(e),
                "columns": [],
            }

    def _execute_safe_sql(
        self,
        sql_query: str,
        params: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        안전한 SQL 쿼리 실행
        """
        try:
            # tenant_id 필터 체크 (보안)
            if "tenant_id" not in sql_query.lower():
                logger.warning("SQL query without tenant_id filter - rejecting for security")
                return {
                    "success": False,
                    "error": "tenant_id filter is required for all queries (multi-tenant security)",
                    "data": [],
                }

            # SQL 실행
            results = execute_safe_sql(sql_query, params or {})

            logger.info(f"Executed SQL query: {len(results)} rows returned")

            return {
                "success": True,
                "row_count": len(results),
                "data": results,
            }

        except ValueError as e:
            # 허용되지 않는 SQL (SELECT 외)
            logger.error(f"Invalid SQL query: {e}")
            return {
                "success": False,
                "error": f"Only SELECT queries are allowed: {str(e)}",
                "data": [],
            }

        except Exception as e:
            # 기타 실행 에러
            logger.error(f"SQL execution error: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": [],
            }

    def _generate_chart_config(
        self,
        data: List[Dict[str, Any]],
        chart_type: str,
        analysis_goal: str,
        x_axis: str = None,
        y_axis: str = None,
        group_by: str = None,
    ) -> Dict[str, Any]:
        """
        차트 설정 생성 (Recharts 호환)
        """
        try:
            # 데이터 검증
            if not data or len(data) == 0:
                return {
                    "success": False,
                    "error": "No data provided for chart",
                }

            # 차트 타입별 설정 생성
            config = {
                "type": chart_type,
                "data": data,
                "analysis_goal": analysis_goal,
            }

            if chart_type == "line":
                config.update({
                    "xAxis": {"dataKey": x_axis or "date", "label": x_axis or "Date"},
                    "yAxis": {"label": y_axis or "Value"},
                    "lines": self._extract_numeric_keys(data, exclude=[x_axis]),
                })

            elif chart_type == "bar":
                config.update({
                    "xAxis": {"dataKey": x_axis or "category", "label": x_axis or "Category"},
                    "yAxis": {"label": y_axis or "Value"},
                    "bars": self._extract_numeric_keys(data, exclude=[x_axis]),
                })

            elif chart_type == "pie":
                config.update({
                    "nameKey": x_axis or "name",
                    "dataKey": y_axis or "value",
                })

            elif chart_type == "area":
                config.update({
                    "xAxis": {"dataKey": x_axis or "date", "label": x_axis or "Date"},
                    "yAxis": {"label": y_axis or "Value"},
                    "areas": self._extract_numeric_keys(data, exclude=[x_axis]),
                })

            elif chart_type == "scatter":
                config.update({
                    "xAxis": {"dataKey": x_axis, "label": x_axis},
                    "yAxis": {"dataKey": y_axis, "label": y_axis},
                })

            elif chart_type == "table":
                config.update({
                    "columns": list(data[0].keys()) if data else [],
                })

            logger.info(f"Generated chart config: {chart_type}, {len(data)} data points")

            return {
                "success": True,
                "config": config,
            }

        except Exception as e:
            logger.error(f"Error generating chart config: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def _extract_numeric_keys(
        self,
        data: List[Dict[str, Any]],
        exclude: List[str] = None,
    ) -> List[str]:
        """
        데이터에서 숫자 타입 컬럼 추출 (차트 시리즈용)
        """
        if not data:
            return []

        exclude = exclude or []
        first_row = data[0]
        numeric_keys = []

        for key, value in first_row.items():
            if key in exclude:
                continue
            if isinstance(value, (int, float)):
                numeric_keys.append(key)

        return numeric_keys
