"""
BI Planner Agent
데이터 분석 및 차트 생성 (Text-to-SQL)

V2 Phase 2 확장:
- RANK 분석 (상위/하위 N개, 백분위)
- PREDICT 분석 (이동평균, 선형회귀)
- WHAT_IF 시뮬레이션

V2 Phase 3 확장 (GenBI):
- refine_chart: 차트 수정 (Refinement Loop)
- generate_insight: AI 인사이트 생성 (Executive Summary)
"""
from typing import Any, Dict, List
import json
import logging
from pathlib import Path
from uuid import UUID

from .base_agent import BaseAgent
from app.tools.db import get_table_schema, execute_safe_sql
from app.services.bi_service import get_bi_service, TimeGranularity

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
        # 도메인 레지스트리
        from app.services.domain_registry import get_domain_registry
        self.domain_registry = get_domain_registry()

    def get_system_prompt(self, context: dict = None) -> str:
        """
        시스템 프롬프트 로드 + 도메인 스키마 동적 생성 + 컨텍스트 힌트
        """
        # 기본 프롬프트 로드
        prompt_path = Path(__file__).parent.parent / "prompts" / "bi_planner.md"
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                base_prompt = f.read()
        except FileNotFoundError:
            logger.warning(f"Prompt file not found: {prompt_path}, using default")
            base_prompt = "You are a BI Planner Agent for TriFlow AI."

        # 컨텍스트 힌트 생성
        context_hint = ""
        if context:
            current_tab = context.get('current_tab')
            schema_hint = context.get('schema_hint')

            if current_tab == 'korea_biopharm' or schema_hint == 'korea_biopharm':
                context_hint = """
## 🎯 CURRENT CONTEXT: 한국바이오팜 (Korea Biopharm)

사용자는 현재 **한국바이오팜 탭**에 있습니다!

**자동 스키마 선택**:
- 제품, 레시피, 성분, 원료, 배합 관련 질문 → **korea_biopharm 스키마** 우선 사용
- 주요 테이블:
  * `recipe_metadata` - 레시피 메타데이터
  * `historical_recipes` - 배합 상세
  * `ingredient` - 원료 정보

**중요 규칙**:
1. 비타민, 제품명, 회사명 등 → korea_biopharm 스키마
2. 온도, 압력, LINE_A 등 → core 스키마 (센서 데이터)
3. 의심스러우면 korea_biopharm 우선!

---
"""

        # 도메인 스키마 정보 동적 생성 (에러 발생 시 기본 프롬프트만 사용)
        try:
            domain_schemas = self.domain_registry.generate_schema_docs()

            # 도메인 키워드 트리거 생성
            trigger_section = f"""
## 🔥 DOMAIN KEYWORD TRIGGERS 🔥

사용자가 다음 키워드를 언급하면 해당 모듈 스키마 사용:

{self._generate_keyword_table()}

**중요**: 이 키워드들은 제조 센서 데이터(LINE_A, 온도, 압력)와 무관합니다!

---
"""

            # 최종 프롬프트 조합
            return f"{context_hint}{trigger_section}\n{base_prompt}\n\n{domain_schemas}"
        except Exception as e:
            logger.error(f"Failed to generate dynamic prompt, using base prompt only: {e}")
            return f"{context_hint}{base_prompt}"

    def _generate_keyword_table(self) -> str:
        """도메인 키워드 테이블 생성"""
        if not self.domain_registry.domains:
            return "(등록된 도메인 없음)"

        rows = []
        for domain in self.domain_registry.domains.values():
            keywords_str = ", ".join(domain.keywords[:5])
            if len(domain.keywords) > 5:
                keywords_str += f" (외 {len(domain.keywords) - 5}개)"

            rows.append(f"- **{domain.name}**: {keywords_str} → `{domain.schema_name}` 스키마")

        return "\n".join(rows)

    def get_tools(self) -> List[Dict[str, Any]]:
        """
        BI Planner Agent의 Tool 정의 (동적 스키마 enum)
        """
        # 동적 스키마 목록 생성 (에러 발생 시 기본 스키마만 사용)
        try:
            allowed_schemas = self.domain_registry.get_all_schemas()
        except Exception as e:
            logger.error(f"Failed to get dynamic schemas, using defaults: {e}")
            allowed_schemas = ["core", "bi", "rag", "audit", "korea_biopharm"]

        return [
            {
                "name": "get_table_schema",
                "description": "데이터베이스 테이블 스키마를 조회합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "조회할 테이블 이름 (예: sensor_data, judgment_executions, recipe_metadata, historical_recipes)",
                        },
                        "schema": {
                            "type": "string",
                            "description": "스키마 이름 (기본값: core)",
                            "enum": allowed_schemas,  # 동적 생성!
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
            # V2 Phase 2: RANK 분석
            {
                "name": "analyze_rank",
                "description": "RANK 분석: 상위/하위 N개 항목을 분석합니다. 불량률, 생산량, 온도 등의 순위를 차원별로 분석할 때 사용합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "tenant_id": {
                            "type": "string",
                            "description": "테넌트 ID (UUID)",
                        },
                        "metric": {
                            "type": "string",
                            "description": "분석 지표",
                            "enum": [
                                "defect_rate", "production_count", "defect_count",
                                "avg_confidence", "avg_execution_time",
                                "avg_temperature", "max_temperature", "min_temperature",
                                "avg_value", "sum_value"
                            ],
                        },
                        "dimension": {
                            "type": "string",
                            "description": "그룹화 차원 (예: line_code, sensor_type, shift, ruleset_id)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "반환할 항목 수 (기본 5)",
                            "default": 5,
                        },
                        "order": {
                            "type": "string",
                            "description": "정렬 순서: desc=상위, asc=하위",
                            "enum": ["desc", "asc"],
                            "default": "desc",
                        },
                        "time_range_days": {
                            "type": "integer",
                            "description": "분석 기간 (일, 기본 7)",
                            "default": 7,
                        },
                    },
                    "required": ["tenant_id", "metric", "dimension"],
                },
            },
            # V2 Phase 2: PREDICT 분석
            {
                "name": "analyze_predict",
                "description": "PREDICT 분석: 시계열 예측을 수행합니다. 이동평균 또는 선형회귀 기반으로 미래 값을 예측합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "tenant_id": {
                            "type": "string",
                            "description": "테넌트 ID (UUID)",
                        },
                        "metric": {
                            "type": "string",
                            "description": "예측 지표",
                            "enum": [
                                "defect_rate", "production_count",
                                "avg_temperature", "avg_value"
                            ],
                        },
                        "dimension": {
                            "type": "string",
                            "description": "그룹화 차원 (선택)",
                        },
                        "time_range_days": {
                            "type": "integer",
                            "description": "학습 데이터 기간 (기본 30일)",
                            "default": 30,
                        },
                        "forecast_periods": {
                            "type": "integer",
                            "description": "예측 기간 (기본 7일)",
                            "default": 7,
                        },
                        "method": {
                            "type": "string",
                            "description": "예측 방법",
                            "enum": ["moving_average", "linear_regression"],
                            "default": "moving_average",
                        },
                        "granularity": {
                            "type": "string",
                            "description": "시간 단위",
                            "enum": ["minute", "hour", "day", "week", "month"],
                            "default": "day",
                        },
                    },
                    "required": ["tenant_id", "metric"],
                },
            },
            # V2 Phase 2: WHAT_IF 시뮬레이션
            {
                "name": "analyze_what_if",
                "description": "WHAT_IF 시뮬레이션: 가정 기반 영향 분석을 수행합니다. '온도가 5도 올라가면 불량률이 어떻게 될까?' 같은 시나리오 분석에 사용합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "tenant_id": {
                            "type": "string",
                            "description": "테넌트 ID (UUID)",
                        },
                        "metric": {
                            "type": "string",
                            "description": "분석 대상 메트릭 (예: defect_rate)",
                        },
                        "dimension": {
                            "type": "string",
                            "description": "변경 차원",
                        },
                        "baseline_value": {
                            "type": "number",
                            "description": "현재 기준값 (예: 현재 불량률 2.5)",
                        },
                        "scenario_changes": {
                            "type": "object",
                            "description": "변경 시나리오 (예: {\"temperature\": 5, \"pressure\": -10})",
                            "additionalProperties": {
                                "type": "number"
                            },
                        },
                        "time_range_days": {
                            "type": "integer",
                            "description": "기준 데이터 기간 (기본 30일)",
                            "default": 30,
                        },
                    },
                    "required": ["tenant_id", "metric", "dimension", "baseline_value", "scenario_changes"],
                },
            },
            # V2 Phase 3 (GenBI): Chart Refinement
            {
                "name": "refine_chart",
                "description": "기존 차트를 사용자 지시에 따라 수정합니다. 차트 유형 변경(막대→라인), 색상 변경, 제목 수정, 축 레이블 변경 등에 사용합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "original_config": {
                            "type": "object",
                            "description": "원본 차트 설정 (ChartConfig JSON)",
                        },
                        "instruction": {
                            "type": "string",
                            "description": "수정 지시 (예: '막대 차트로 바꿔줘', '제목을 월별 생산량으로 변경')",
                        },
                        "preserve_data": {
                            "type": "boolean",
                            "description": "데이터 유지 여부 (기본 true)",
                            "default": True,
                        },
                    },
                    "required": ["original_config", "instruction"],
                },
            },
            # V2 Phase 3 (GenBI): AI Insight Generation
            {
                "name": "generate_insight",
                "description": "차트/데이터에 대한 AI 인사이트를 생성합니다. AWS QuickSight GenBI 스타일의 Fact/Reasoning/Action 구조로 Executive Summary를 생성합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "array",
                            "description": "분석할 데이터 (JSON 배열)",
                        },
                        "chart_config": {
                            "type": "object",
                            "description": "관련 차트 설정 (선택)",
                        },
                        "focus_metrics": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "집중 분석할 메트릭 이름 목록",
                        },
                        "time_range": {
                            "type": "string",
                            "description": "분석 기간 (예: '24h', '7d')",
                        },
                    },
                    "required": ["data"],
                },
            },
            # StatCard 관리 도구
            {
                "name": "manage_stat_cards",
                "description": "대시보드 StatCard를 관리합니다. KPI, DB 쿼리, MCP 도구 기반 카드를 추가/삭제/재정렬할 수 있습니다. 사용 예: 'OEE 카드 추가해줘', '불량률 카드 삭제해줘', '현재 카드 목록 보여줘'",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": "수행할 액션",
                            "enum": ["add_kpi", "add_db_query", "add_mcp", "remove", "list", "reorder"],
                        },
                        "tenant_id": {
                            "type": "string",
                            "description": "테넌트 ID (UUID)",
                        },
                        "user_id": {
                            "type": "string",
                            "description": "사용자 ID (UUID)",
                        },
                        # add_kpi용
                        "kpi_code": {
                            "type": "string",
                            "description": "KPI 코드 (add_kpi 액션에서 사용). 예: defect_rate, oee, yield_rate, downtime",
                        },
                        # add_db_query용
                        "table_name": {
                            "type": "string",
                            "description": "테이블명 (add_db_query). 예: fact_daily_production",
                        },
                        "column_name": {
                            "type": "string",
                            "description": "컬럼명 (add_db_query). 예: defect_rate, production_count",
                        },
                        "aggregation": {
                            "type": "string",
                            "description": "집계 함수 (add_db_query)",
                            "enum": ["sum", "avg", "min", "max", "count", "last"],
                        },
                        # add_mcp용
                        "mcp_server_id": {
                            "type": "string",
                            "description": "MCP 서버 ID (add_mcp 액션에서 사용)",
                        },
                        "mcp_tool_name": {
                            "type": "string",
                            "description": "MCP 도구 이름 (add_mcp 액션에서 사용)",
                        },
                        # remove용
                        "card_id": {
                            "type": "string",
                            "description": "삭제할 카드 ID (remove 액션에서 사용)",
                        },
                        # reorder용
                        "card_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "순서대로 정렬된 카드 ID 목록 (reorder 액션에서 사용)",
                        },
                        # 공통 표시 설정
                        "title": {
                            "type": "string",
                            "description": "커스텀 카드 제목 (선택)",
                        },
                        "unit": {
                            "type": "string",
                            "description": "커스텀 단위 (선택). 예: %, 건, 개",
                        },
                        "icon": {
                            "type": "string",
                            "description": "아이콘 이름 (선택). 예: BarChart3, AlertTriangle, Activity",
                        },
                    },
                    "required": ["action", "tenant_id", "user_id"],
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

        # V2 Phase 2: RANK 분석
        elif tool_name == "analyze_rank":
            return self._analyze_rank(
                tenant_id=tool_input["tenant_id"],
                metric=tool_input["metric"],
                dimension=tool_input["dimension"],
                limit=tool_input.get("limit", 5),
                order=tool_input.get("order", "desc"),
                time_range_days=tool_input.get("time_range_days", 7),
            )

        # V2 Phase 2: PREDICT 분석
        elif tool_name == "analyze_predict":
            return self._analyze_predict(
                tenant_id=tool_input["tenant_id"],
                metric=tool_input["metric"],
                dimension=tool_input.get("dimension"),
                time_range_days=tool_input.get("time_range_days", 30),
                forecast_periods=tool_input.get("forecast_periods", 7),
                method=tool_input.get("method", "moving_average"),
                granularity=tool_input.get("granularity", "day"),
            )

        # V2 Phase 2: WHAT_IF 시뮬레이션
        elif tool_name == "analyze_what_if":
            return self._analyze_what_if(
                tenant_id=tool_input["tenant_id"],
                metric=tool_input["metric"],
                dimension=tool_input["dimension"],
                baseline_value=tool_input["baseline_value"],
                scenario_changes=tool_input["scenario_changes"],
                time_range_days=tool_input.get("time_range_days", 30),
            )

        # V2 Phase 3 (GenBI): Chart Refinement
        elif tool_name == "refine_chart":
            return self._refine_chart(
                original_config=tool_input["original_config"],
                instruction=tool_input["instruction"],
                preserve_data=tool_input.get("preserve_data", True),
            )

        # V2 Phase 3 (GenBI): AI Insight Generation
        elif tool_name == "generate_insight":
            return self._generate_insight(
                data=tool_input["data"],
                chart_config=tool_input.get("chart_config"),
                focus_metrics=tool_input.get("focus_metrics"),
                time_range=tool_input.get("time_range"),
            )

        # StatCard 관리
        elif tool_name == "manage_stat_cards":
            return self._manage_stat_cards(
                action=tool_input["action"],
                tenant_id=tool_input["tenant_id"],
                user_id=tool_input["user_id"],
                kpi_code=tool_input.get("kpi_code"),
                table_name=tool_input.get("table_name"),
                column_name=tool_input.get("column_name"),
                aggregation=tool_input.get("aggregation"),
                mcp_server_id=tool_input.get("mcp_server_id"),
                mcp_tool_name=tool_input.get("mcp_tool_name"),
                card_id=tool_input.get("card_id"),
                card_ids=tool_input.get("card_ids"),
                title=tool_input.get("title"),
                unit=tool_input.get("unit"),
                icon=tool_input.get("icon"),
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

    # =========================================
    # V2 Phase 2: Advanced Analysis Methods
    # =========================================

    def _analyze_rank(
        self,
        tenant_id: str,
        metric: str,
        dimension: str,
        limit: int = 5,
        order: str = "desc",
        time_range_days: int = 7,
    ) -> Dict[str, Any]:
        """
        RANK 분석 실행 (BIService 위임)
        """
        import asyncio

        try:
            bi_service = get_bi_service()
            tenant_uuid = UUID(tenant_id)

            # 동기 컨텍스트에서 비동기 함수 호출
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 이미 실행 중인 이벤트 루프 내에서는 새로운 태스크 생성
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        bi_service.analyze_rank(
                            tenant_id=tenant_uuid,
                            metric=metric,
                            dimension=dimension,
                            limit=limit,
                            order=order,
                            time_range_days=time_range_days,
                        )
                    )
                    result = future.result()
            else:
                result = loop.run_until_complete(
                    bi_service.analyze_rank(
                        tenant_id=tenant_uuid,
                        metric=metric,
                        dimension=dimension,
                        limit=limit,
                        order=order,
                        time_range_days=time_range_days,
                    )
                )

            logger.info(f"RANK analysis completed: {len(result.data)} items")

            return {
                "success": True,
                "analysis_type": "rank",
                "data": result.data,
                "summary": result.summary,
                "chart_config": result.chart_config,
                "insights": result.insights,
                "metadata": result.metadata,
            }

        except Exception as e:
            logger.error(f"RANK analysis error: {e}")
            return {
                "success": False,
                "error": str(e),
                "analysis_type": "rank",
            }

    def _analyze_predict(
        self,
        tenant_id: str,
        metric: str,
        dimension: str = None,
        time_range_days: int = 30,
        forecast_periods: int = 7,
        method: str = "moving_average",
        granularity: str = "day",
    ) -> Dict[str, Any]:
        """
        PREDICT 분석 실행 (BIService 위임)
        """
        import asyncio

        try:
            bi_service = get_bi_service()
            tenant_uuid = UUID(tenant_id)
            granularity_enum = TimeGranularity(granularity)

            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        bi_service.analyze_predict(
                            tenant_id=tenant_uuid,
                            metric=metric,
                            dimension=dimension,
                            time_range_days=time_range_days,
                            forecast_periods=forecast_periods,
                            method=method,
                            granularity=granularity_enum,
                        )
                    )
                    result = future.result()
            else:
                result = loop.run_until_complete(
                    bi_service.analyze_predict(
                        tenant_id=tenant_uuid,
                        metric=metric,
                        dimension=dimension,
                        time_range_days=time_range_days,
                        forecast_periods=forecast_periods,
                        method=method,
                        granularity=granularity_enum,
                    )
                )

            logger.info(f"PREDICT analysis completed: method={method}, periods={forecast_periods}")

            return {
                "success": True,
                "analysis_type": "predict",
                "data": result.data,
                "summary": result.summary,
                "chart_config": result.chart_config,
                "insights": result.insights,
                "metadata": result.metadata,
            }

        except Exception as e:
            logger.error(f"PREDICT analysis error: {e}")
            return {
                "success": False,
                "error": str(e),
                "analysis_type": "predict",
            }

    def _analyze_what_if(
        self,
        tenant_id: str,
        metric: str,
        dimension: str,
        baseline_value: float,
        scenario_changes: Dict[str, float],
        time_range_days: int = 30,
    ) -> Dict[str, Any]:
        """
        WHAT_IF 시뮬레이션 실행 (BIService 위임)
        """
        import asyncio

        try:
            bi_service = get_bi_service()
            tenant_uuid = UUID(tenant_id)

            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        bi_service.analyze_what_if(
                            tenant_id=tenant_uuid,
                            metric=metric,
                            dimension=dimension,
                            baseline_value=baseline_value,
                            scenario_changes=scenario_changes,
                            time_range_days=time_range_days,
                        )
                    )
                    result = future.result()
            else:
                result = loop.run_until_complete(
                    bi_service.analyze_what_if(
                        tenant_id=tenant_uuid,
                        metric=metric,
                        dimension=dimension,
                        baseline_value=baseline_value,
                        scenario_changes=scenario_changes,
                        time_range_days=time_range_days,
                    )
                )

            logger.info(f"WHAT_IF analysis completed: baseline={baseline_value}, changes={scenario_changes}")

            return {
                "success": True,
                "analysis_type": "what_if",
                "data": result.data,
                "summary": result.summary,
                "chart_config": result.chart_config,
                "insights": result.insights,
                "metadata": result.metadata,
            }

        except Exception as e:
            logger.error(f"WHAT_IF analysis error: {e}")
            return {
                "success": False,
                "error": str(e),
                "analysis_type": "what_if",
            }

    # =========================================
    # V2 Phase 3 (GenBI): Chart Refinement & Insight
    # =========================================

    def _refine_chart(
        self,
        original_config: Dict[str, Any],
        instruction: str,
        preserve_data: bool = True,
    ) -> Dict[str, Any]:
        """
        차트 수정 (Refinement Loop)
        LLM을 사용하여 사용자 지시에 따라 차트 설정을 수정
        """
        from anthropic import Anthropic
        from app.config import settings

        try:
            client = Anthropic(api_key=settings.anthropic_api_key)

            system_prompt = """당신은 차트 수정 전문가입니다.
사용자의 지시에 따라 차트 설정을 수정합니다.

## 차트 유형
- line: 라인 차트 (추세, 시계열)
- bar: 막대 차트 (비교, 카테고리)
- pie: 파이 차트 (비율, 구성)
- area: 영역 차트 (누적, 추세)
- scatter: 산점도 (상관관계)
- table: 테이블 (상세 데이터)

## 수정 가능 항목
- type: 차트 유형 변경
- title: 제목 변경
- xAxis.label, yAxis.label: 축 레이블 변경
- colors: 색상 변경

## 출력 형식
반드시 다음 JSON 형식으로 출력하세요:
```json
{
  "refined_config": { ... 수정된 차트 설정 ... },
  "changes_made": ["변경사항1", "변경사항2"]
}
```
"""

            user_message = f"""다음 차트 설정을 수정해주세요.

## 원본 차트 설정
```json
{json.dumps(original_config, indent=2, ensure_ascii=False)}
```

## 수정 지시
{instruction}

## 옵션
- 데이터 유지: {preserve_data}

위 지시에 따라 차트 설정을 수정하고 JSON 형식으로 출력해주세요."""

            response = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )

            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text

            # JSON 파싱
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                result = json.loads(content[json_start:json_end])

                # 데이터 유지 옵션 처리
                if preserve_data and "data" in original_config:
                    result["refined_config"]["data"] = original_config["data"]

                logger.info(f"Chart refined: {result.get('changes_made', [])}")

                return {
                    "success": True,
                    "refined_config": result.get("refined_config", original_config),
                    "changes_made": result.get("changes_made", []),
                }
            else:
                raise ValueError("No valid JSON in response")

        except Exception as e:
            logger.error(f"Chart refinement error: {e}")
            return {
                "success": False,
                "error": str(e),
                "refined_config": original_config,
                "changes_made": [],
            }

    def _generate_insight(
        self,
        data: List[Dict[str, Any]],
        chart_config: Dict[str, Any] = None,
        focus_metrics: List[str] = None,
        time_range: str = None,
    ) -> Dict[str, Any]:
        """
        AI 인사이트 생성 (Executive Summary)
        AWS QuickSight GenBI 스타일의 Fact/Reasoning/Action 구조
        """
        from anthropic import Anthropic
        from app.config import settings

        try:
            client = Anthropic(api_key=settings.anthropic_api_key)

            system_prompt = """당신은 제조 데이터 분석 전문가입니다.
주어진 데이터를 분석하여 AWS QuickSight GenBI 스타일의 Executive Summary를 생성합니다.

## 출력 형식
반드시 다음 JSON 형식으로 출력하세요:

```json
{
  "title": "인사이트 제목",
  "summary": "핵심 요약 (1-2문장)",
  "facts": [
    {
      "metric_name": "메트릭 이름",
      "current_value": 숫자,
      "change_percent": 변화율 또는 null,
      "trend": "up" | "down" | "stable",
      "period": "측정 기간",
      "unit": "단위"
    }
  ],
  "reasoning": {
    "analysis": "분석 내용 (2-3문장)",
    "contributing_factors": ["원인1", "원인2"],
    "confidence": 0.0 ~ 1.0
  },
  "actions": [
    {
      "priority": "high" | "medium" | "low",
      "action": "권장 조치",
      "expected_impact": "예상 효과"
    }
  ]
}
```

## 제조 도메인 임계값
- 온도: 70°C 초과 주의, 80°C 초과 위험
- 압력: 8 bar 초과 주의, 10 bar 초과 위험
- 생산 효율: 90% 이상 목표
"""

            data_str = json.dumps(data[:50], indent=2, ensure_ascii=False, default=str)

            user_message = f"""다음 데이터를 분석하여 Executive Summary를 생성해주세요.

## 데이터
```json
{data_str}
```

## 분석 기간
{time_range or "최근 24시간"}
"""

            if focus_metrics:
                user_message += f"\n## 집중 분석 메트릭\n{', '.join(focus_metrics)}\n"

            if chart_config:
                user_message += f"\n## 차트 정보\n유형: {chart_config.get('type', 'unknown')}\n목적: {chart_config.get('analysis_goal', 'N/A')}\n"

            response = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )

            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text

            # JSON 파싱
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                insight = json.loads(content[json_start:json_end])

                logger.info(
                    f"Insight generated: {len(insight.get('facts', []))} facts, "
                    f"{len(insight.get('actions', []))} actions"
                )

                return {
                    "success": True,
                    "insight": insight,
                }
            else:
                raise ValueError("No valid JSON in response")

        except Exception as e:
            logger.error(f"Insight generation error: {e}")
            return {
                "success": False,
                "error": str(e),
                "insight": {
                    "title": "분석 오류",
                    "summary": str(e),
                    "facts": [],
                    "reasoning": {"analysis": "분석을 완료할 수 없습니다.", "contributing_factors": [], "confidence": 0},
                    "actions": [],
                },
            }

    # =========================================
    # StatCard 관리
    # =========================================

    def _manage_stat_cards(
        self,
        action: str,
        tenant_id: str,
        user_id: str,
        kpi_code: str = None,
        table_name: str = None,
        column_name: str = None,
        aggregation: str = None,
        mcp_server_id: str = None,
        mcp_tool_name: str = None,
        card_id: str = None,
        card_ids: List[str] = None,
        title: str = None,
        unit: str = None,
        icon: str = None,
    ) -> Dict[str, Any]:
        """
        StatCard 관리 (CRUD 및 재정렬)
        """
        import asyncio
        from app.services.stat_card_service import StatCardService
        from app.database import SessionLocal
        from app.schemas.statcard import StatCardConfigCreate

        try:
            tenant_uuid = UUID(tenant_id)
            user_uuid = UUID(user_id)

            db = SessionLocal()
            try:
                service = StatCardService(db)

                if action == "list":
                    # 카드 목록 조회
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(
                                asyncio.run,
                                service.get_card_values(tenant_id=tenant_uuid, user_id=user_uuid)
                            )
                            result = future.result()
                    else:
                        result = loop.run_until_complete(
                            service.get_card_values(tenant_id=tenant_uuid, user_id=user_uuid)
                        )

                    cards_info = []
                    for card in result.cards:
                        cards_info.append({
                            "config_id": str(card.config.config_id),
                            "title": card.value.title,
                            "source_type": card.config.source_type,
                            "value": card.value.formatted_value or card.value.value,
                            "status": card.value.status,
                            "display_order": card.config.display_order,
                        })

                    logger.info(f"Listed {len(cards_info)} stat cards")

                    return {
                        "success": True,
                        "action": "list",
                        "cards": cards_info,
                        "total": result.total,
                    }

                elif action == "add_kpi":
                    if not kpi_code:
                        return {"success": False, "error": "kpi_code is required for add_kpi action"}

                    config = StatCardConfigCreate(
                        source_type="kpi",
                        kpi_code=kpi_code,
                        display_order=99,
                        is_visible=True,
                        higher_is_better=True,
                        cache_ttl_seconds=60,
                        custom_title=title,
                        custom_unit=unit,
                        custom_icon=icon,
                    )

                    created = service.create_config(tenant_id=tenant_uuid, user_id=user_uuid, config=config)

                    logger.info(f"Created KPI stat card: {kpi_code}")

                    return {
                        "success": True,
                        "action": "add_kpi",
                        "config_id": str(created.config_id),
                        "kpi_code": kpi_code,
                        "message": f"KPI '{kpi_code}' 카드가 추가되었습니다.",
                    }

                elif action == "add_db_query":
                    if not table_name or not column_name or not aggregation:
                        return {"success": False, "error": "table_name, column_name, and aggregation are required"}

                    config = StatCardConfigCreate(
                        source_type="db_query",
                        table_name=table_name,
                        column_name=column_name,
                        aggregation=aggregation,
                        display_order=99,
                        is_visible=True,
                        higher_is_better=True,
                        cache_ttl_seconds=60,
                        custom_title=title,
                        custom_unit=unit,
                        custom_icon=icon,
                    )

                    created = service.create_config(tenant_id=tenant_uuid, user_id=user_uuid, config=config)

                    logger.info(f"Created DB query stat card: {table_name}.{column_name}")

                    return {
                        "success": True,
                        "action": "add_db_query",
                        "config_id": str(created.config_id),
                        "table_name": table_name,
                        "column_name": column_name,
                        "aggregation": aggregation,
                        "message": f"DB 쿼리 카드 ({table_name}.{column_name})가 추가되었습니다.",
                    }

                elif action == "add_mcp":
                    if not mcp_server_id or not mcp_tool_name:
                        return {"success": False, "error": "mcp_server_id and mcp_tool_name are required"}

                    config = StatCardConfigCreate(
                        source_type="mcp_tool",
                        mcp_server_id=UUID(mcp_server_id),
                        mcp_tool_name=mcp_tool_name,
                        display_order=99,
                        is_visible=True,
                        higher_is_better=True,
                        cache_ttl_seconds=60,
                        custom_title=title,
                        custom_unit=unit,
                        custom_icon=icon,
                    )

                    created = service.create_config(tenant_id=tenant_uuid, user_id=user_uuid, config=config)

                    logger.info(f"Created MCP tool stat card: {mcp_tool_name}")

                    return {
                        "success": True,
                        "action": "add_mcp",
                        "config_id": str(created.config_id),
                        "mcp_tool_name": mcp_tool_name,
                        "message": f"MCP 도구 카드 ({mcp_tool_name})가 추가되었습니다.",
                    }

                elif action == "remove":
                    if not card_id:
                        return {"success": False, "error": "card_id is required for remove action"}

                    success = service.delete_config(
                        tenant_id=tenant_uuid,
                        user_id=user_uuid,
                        config_id=UUID(card_id),
                    )

                    if success:
                        logger.info(f"Deleted stat card: {card_id}")
                        return {
                            "success": True,
                            "action": "remove",
                            "deleted_id": card_id,
                            "message": "카드가 삭제되었습니다.",
                        }
                    else:
                        return {"success": False, "error": "Card not found or unauthorized"}

                elif action == "reorder":
                    if not card_ids:
                        return {"success": False, "error": "card_ids is required for reorder action"}

                    card_uuids = [UUID(cid) for cid in card_ids]
                    service.reorder_configs(tenant_id=tenant_uuid, user_id=user_uuid, config_ids=card_uuids)

                    logger.info(f"Reordered {len(card_ids)} stat cards")

                    return {
                        "success": True,
                        "action": "reorder",
                        "new_order": card_ids,
                        "message": "카드 순서가 변경되었습니다.",
                    }

                else:
                    return {"success": False, "error": f"Unknown action: {action}"}

            finally:
                db.close()

        except Exception as e:
            logger.error(f"StatCard management error: {e}")
            return {
                "success": False,
                "error": str(e),
                "action": action,
            }
