"""
StatCard Service
대시보드 StatCard 설정 및 값 조회 서비스

데이터 소스 유형별 값 조회:
- kpi: bi.dim_kpi + fact_daily_production에서 조회
- db_query: 동적 SQL 쿼리 실행
- mcp_tool: MCPToolHub를 통한 외부 시스템 연동
"""

import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db_context
from app.schemas.statcard import (
    AggregationType,
    ColumnInfo,
    KpiInfo,
    KpiListResponse,
    McpToolInfo,
    McpToolListResponse,
    StatCardConfig,
    StatCardConfigCreate,
    StatCardConfigUpdate,
    StatCardListResponse,
    StatCardValue,
    StatCardWithValue,
    StatusType,
    TableInfo,
    AvailableTablesResponse,
)
from app.services.mcp_toolhub import MCPToolHubService

logger = logging.getLogger(__name__)


class StatCardService:
    """StatCard 관리 및 데이터 조회 서비스"""

    def __init__(self, db: Session):
        self.db = db
        self._cache: Dict[str, Tuple[Any, datetime]] = {}

    # =====================================================
    # StatCard 설정 CRUD
    # =====================================================

    def create_config(
        self,
        tenant_id: UUID,
        user_id: UUID,
        data: StatCardConfigCreate,
    ) -> StatCardConfig:
        """StatCard 설정 생성"""
        # 다음 display_order 계산
        next_order = self._get_next_display_order(tenant_id, user_id)

        query = text("""
            INSERT INTO bi.stat_card_configs (
                tenant_id, user_id, display_order, is_visible,
                source_type, kpi_code,
                table_name, column_name, aggregation, filter_condition,
                mcp_server_id, mcp_tool_name, mcp_params, mcp_result_key,
                custom_title, custom_icon, custom_unit,
                green_threshold, yellow_threshold, red_threshold, higher_is_better,
                cache_ttl_seconds
            )
            VALUES (
                :tenant_id, :user_id, :display_order, :is_visible,
                :source_type, :kpi_code,
                :table_name, :column_name, :aggregation, :filter_condition,
                :mcp_server_id, :mcp_tool_name, :mcp_params, :mcp_result_key,
                :custom_title, :custom_icon, :custom_unit,
                :green_threshold, :yellow_threshold, :red_threshold, :higher_is_better,
                :cache_ttl_seconds
            )
            RETURNING config_id, tenant_id, user_id, display_order, is_visible,
                      source_type, kpi_code,
                      table_name, column_name, aggregation, filter_condition,
                      mcp_server_id, mcp_tool_name, mcp_params, mcp_result_key,
                      custom_title, custom_icon, custom_unit,
                      green_threshold, yellow_threshold, red_threshold, higher_is_better,
                      cache_ttl_seconds, created_at, updated_at
        """)

        result = self.db.execute(
            query,
            {
                "tenant_id": str(tenant_id),
                "user_id": str(user_id),
                "display_order": data.display_order if data.display_order > 0 else next_order,
                "is_visible": data.is_visible,
                "source_type": data.source_type,
                "kpi_code": data.kpi_code,
                "table_name": data.table_name,
                "column_name": data.column_name,
                "aggregation": data.aggregation,
                "filter_condition": json.dumps(data.filter_condition) if data.filter_condition else None,
                "mcp_server_id": str(data.mcp_server_id) if data.mcp_server_id else None,
                "mcp_tool_name": data.mcp_tool_name,
                "mcp_params": json.dumps(data.mcp_params) if data.mcp_params else None,
                "mcp_result_key": data.mcp_result_key,
                "custom_title": data.custom_title,
                "custom_icon": data.custom_icon,
                "custom_unit": data.custom_unit,
                "green_threshold": data.green_threshold,
                "yellow_threshold": data.yellow_threshold,
                "red_threshold": data.red_threshold,
                "higher_is_better": data.higher_is_better,
                "cache_ttl_seconds": data.cache_ttl_seconds,
            },
        )
        self.db.commit()

        row = result.fetchone()
        return self._row_to_config(row)

    def get_config(
        self,
        config_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
    ) -> Optional[StatCardConfig]:
        """StatCard 설정 조회"""
        query = text("""
            SELECT config_id, tenant_id, user_id, display_order, is_visible,
                   source_type, kpi_code,
                   table_name, column_name, aggregation, filter_condition,
                   mcp_server_id, mcp_tool_name, mcp_params, mcp_result_key,
                   custom_title, custom_icon, custom_unit,
                   green_threshold, yellow_threshold, red_threshold, higher_is_better,
                   cache_ttl_seconds, created_at, updated_at
            FROM bi.stat_card_configs
            WHERE config_id = :config_id AND tenant_id = :tenant_id AND user_id = :user_id
        """)

        result = self.db.execute(
            query,
            {
                "config_id": str(config_id),
                "tenant_id": str(tenant_id),
                "user_id": str(user_id),
            },
        )
        row = result.fetchone()

        if not row:
            return None

        return self._row_to_config(row)

    def list_configs(
        self,
        tenant_id: UUID,
        user_id: UUID,
        visible_only: bool = True,
    ) -> List[StatCardConfig]:
        """사용자의 StatCard 설정 목록 조회"""
        conditions = ["tenant_id = :tenant_id", "user_id = :user_id"]
        if visible_only:
            conditions.append("is_visible = true")

        where_clause = " AND ".join(conditions)

        query = text(f"""
            SELECT config_id, tenant_id, user_id, display_order, is_visible,
                   source_type, kpi_code,
                   table_name, column_name, aggregation, filter_condition,
                   mcp_server_id, mcp_tool_name, mcp_params, mcp_result_key,
                   custom_title, custom_icon, custom_unit,
                   green_threshold, yellow_threshold, red_threshold, higher_is_better,
                   cache_ttl_seconds, created_at, updated_at
            FROM bi.stat_card_configs
            WHERE {where_clause}
            ORDER BY display_order ASC
        """)

        result = self.db.execute(
            query,
            {"tenant_id": str(tenant_id), "user_id": str(user_id)},
        )
        rows = result.fetchall()

        return [self._row_to_config(row) for row in rows]

    def update_config(
        self,
        config_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        data: StatCardConfigUpdate,
    ) -> Optional[StatCardConfig]:
        """StatCard 설정 수정"""
        updates = ["updated_at = now()"]
        params: Dict[str, Any] = {
            "config_id": str(config_id),
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
        }

        # 동적 UPDATE 필드 구성
        update_fields = [
            ("display_order", data.display_order),
            ("is_visible", data.is_visible),
            ("source_type", data.source_type),
            ("kpi_code", data.kpi_code),
            ("table_name", data.table_name),
            ("column_name", data.column_name),
            ("aggregation", data.aggregation),
            ("custom_title", data.custom_title),
            ("custom_icon", data.custom_icon),
            ("custom_unit", data.custom_unit),
            ("green_threshold", data.green_threshold),
            ("yellow_threshold", data.yellow_threshold),
            ("red_threshold", data.red_threshold),
            ("higher_is_better", data.higher_is_better),
            ("cache_ttl_seconds", data.cache_ttl_seconds),
        ]

        for field_name, value in update_fields:
            if value is not None:
                updates.append(f"{field_name} = :{field_name}")
                params[field_name] = value

        # JSON 필드
        if data.filter_condition is not None:
            updates.append("filter_condition = :filter_condition")
            params["filter_condition"] = json.dumps(data.filter_condition)

        if data.mcp_server_id is not None:
            updates.append("mcp_server_id = :mcp_server_id")
            params["mcp_server_id"] = str(data.mcp_server_id)

        if data.mcp_tool_name is not None:
            updates.append("mcp_tool_name = :mcp_tool_name")
            params["mcp_tool_name"] = data.mcp_tool_name

        if data.mcp_params is not None:
            updates.append("mcp_params = :mcp_params")
            params["mcp_params"] = json.dumps(data.mcp_params)

        if data.mcp_result_key is not None:
            updates.append("mcp_result_key = :mcp_result_key")
            params["mcp_result_key"] = data.mcp_result_key

        update_clause = ", ".join(updates)

        query = text(f"""
            UPDATE bi.stat_card_configs
            SET {update_clause}
            WHERE config_id = :config_id AND tenant_id = :tenant_id AND user_id = :user_id
            RETURNING config_id, tenant_id, user_id, display_order, is_visible,
                      source_type, kpi_code,
                      table_name, column_name, aggregation, filter_condition,
                      mcp_server_id, mcp_tool_name, mcp_params, mcp_result_key,
                      custom_title, custom_icon, custom_unit,
                      green_threshold, yellow_threshold, red_threshold, higher_is_better,
                      cache_ttl_seconds, created_at, updated_at
        """)

        result = self.db.execute(query, params)
        self.db.commit()

        row = result.fetchone()
        if not row:
            return None

        return self._row_to_config(row)

    def delete_config(
        self,
        config_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
    ) -> bool:
        """StatCard 설정 삭제"""
        query = text("""
            DELETE FROM bi.stat_card_configs
            WHERE config_id = :config_id AND tenant_id = :tenant_id AND user_id = :user_id
        """)

        result = self.db.execute(
            query,
            {
                "config_id": str(config_id),
                "tenant_id": str(tenant_id),
                "user_id": str(user_id),
            },
        )
        self.db.commit()

        return result.rowcount > 0

    def reorder_configs(
        self,
        tenant_id: UUID,
        user_id: UUID,
        card_ids: List[UUID],
    ) -> List[StatCardConfig]:
        """StatCard 순서 변경"""
        for i, card_id in enumerate(card_ids):
            query = text("""
                UPDATE bi.stat_card_configs
                SET display_order = :order, updated_at = now()
                WHERE config_id = :config_id AND tenant_id = :tenant_id AND user_id = :user_id
            """)
            self.db.execute(
                query,
                {
                    "order": i,
                    "config_id": str(card_id),
                    "tenant_id": str(tenant_id),
                    "user_id": str(user_id),
                },
            )

        self.db.commit()
        return self.list_configs(tenant_id, user_id, visible_only=False)

    # =====================================================
    # 값 조회
    # =====================================================

    async def get_card_values(
        self,
        tenant_id: UUID,
        user_id: UUID,
    ) -> StatCardListResponse:
        """사용자의 모든 StatCard 설정 + 현재 값 조회"""
        configs = self.list_configs(tenant_id, user_id, visible_only=True)

        cards = []
        for config in configs:
            value = await self.get_card_value(config, tenant_id)
            cards.append(StatCardWithValue(config=config, value=value))

        return StatCardListResponse(cards=cards, total=len(cards))

    async def get_card_value(
        self,
        config: StatCardConfig,
        tenant_id: UUID,
    ) -> StatCardValue:
        """개별 StatCard 값 조회"""
        # 캐시 확인
        cache_key = f"statcard:{config.config_id}"
        cached = self._get_from_cache(cache_key, config.cache_ttl_seconds)
        if cached:
            cached.is_cached = True
            return cached

        # 소스 유형별 값 조회
        try:
            if config.source_type == "kpi":
                value = await self._fetch_kpi_value(config, tenant_id)
            elif config.source_type == "db_query":
                value = await self._fetch_db_query_value(config, tenant_id)
            elif config.source_type == "mcp_tool":
                value = await self._fetch_mcp_value(config, tenant_id)
            else:
                value = self._create_error_value(config, "Unknown source type")
        except Exception as e:
            logger.error(f"Failed to fetch StatCard value: {e}")
            value = self._create_error_value(config, str(e))

        # 캐시 저장
        self._set_cache(cache_key, value)

        return value

    async def _fetch_kpi_value(
        self,
        config: StatCardConfig,
        tenant_id: UUID,
    ) -> StatCardValue:
        """KPI 소스에서 값 조회"""
        # dim_kpi에서 KPI 정보 조회
        kpi_query = text("""
            SELECT name, unit, green_threshold, yellow_threshold, red_threshold, higher_is_better
            FROM bi.dim_kpi
            WHERE tenant_id = :tenant_id AND kpi_code = :kpi_code AND is_active = true
        """)
        kpi_result = self.db.execute(
            kpi_query,
            {"tenant_id": str(tenant_id), "kpi_code": config.kpi_code},
        )
        kpi_row = kpi_result.fetchone()

        if not kpi_row:
            return self._create_error_value(config, f"KPI not found: {config.kpi_code}")

        kpi_name, unit, green_th, yellow_th, red_th, higher_is_better = kpi_row

        # fact 테이블에서 최신 값 조회
        value_query = text("""
            SELECT
                CASE :kpi_code
                    WHEN 'defect_rate' THEN
                        COALESCE(SUM(defect_qty) / NULLIF(SUM(total_qty), 0) * 100, 0)
                    WHEN 'oee' THEN
                        COALESCE(AVG(
                            (runtime_minutes / NULLIF(runtime_minutes + downtime_minutes + setup_time_minutes, 0)) * 100
                        ), 0)
                    WHEN 'yield_rate' THEN
                        COALESCE(SUM(good_qty) / NULLIF(SUM(total_qty), 0) * 100, 0)
                    WHEN 'downtime' THEN
                        COALESCE(AVG(downtime_minutes), 0)
                    ELSE 0
                END as value
            FROM bi.fact_daily_production
            WHERE tenant_id = :tenant_id AND date >= CURRENT_DATE - INTERVAL '7 days'
        """)
        value_result = self.db.execute(
            value_query,
            {"tenant_id": str(tenant_id), "kpi_code": config.kpi_code},
        )
        value_row = value_result.fetchone()
        current_value = float(value_row[0]) if value_row and value_row[0] else 0.0

        # 이전 기간 값 조회 (전주)
        prev_query = text("""
            SELECT
                CASE :kpi_code
                    WHEN 'defect_rate' THEN
                        COALESCE(SUM(defect_qty) / NULLIF(SUM(total_qty), 0) * 100, 0)
                    WHEN 'oee' THEN
                        COALESCE(AVG(
                            (runtime_minutes / NULLIF(runtime_minutes + downtime_minutes + setup_time_minutes, 0)) * 100
                        ), 0)
                    WHEN 'yield_rate' THEN
                        COALESCE(SUM(good_qty) / NULLIF(SUM(total_qty), 0) * 100, 0)
                    WHEN 'downtime' THEN
                        COALESCE(AVG(downtime_minutes), 0)
                    ELSE 0
                END as value
            FROM bi.fact_daily_production
            WHERE tenant_id = :tenant_id
                AND date >= CURRENT_DATE - INTERVAL '14 days'
                AND date < CURRENT_DATE - INTERVAL '7 days'
        """)
        prev_result = self.db.execute(
            prev_query,
            {"tenant_id": str(tenant_id), "kpi_code": config.kpi_code},
        )
        prev_row = prev_result.fetchone()
        prev_value = float(prev_row[0]) if prev_row and prev_row[0] else None

        # 상태 결정
        status = self._determine_status(
            current_value,
            float(green_th) if green_th else None,
            float(yellow_th) if yellow_th else None,
            float(red_th) if red_th else None,
            higher_is_better,
        )

        # 변화율 계산
        change_percent = None
        trend = None
        if prev_value and prev_value != 0:
            change_percent = ((current_value - prev_value) / prev_value) * 100
            if abs(change_percent) < 1:
                trend = "stable"
            elif change_percent > 0:
                trend = "up" if higher_is_better else "down"
            else:
                trend = "down" if higher_is_better else "up"

        # 기간 정보 계산
        today = datetime.utcnow().date()
        period_end = today
        period_start = today - timedelta(days=7)

        return StatCardValue(
            config_id=config.config_id,
            value=current_value,
            formatted_value=self._format_value(current_value, unit),
            previous_value=prev_value,
            change_percent=change_percent,
            trend=trend,
            status=status,
            title=config.custom_title or kpi_name,
            icon=config.custom_icon or self._get_kpi_icon(config.kpi_code),
            unit=config.custom_unit or unit,
            period_start=datetime.combine(period_start, datetime.min.time()),
            period_end=datetime.combine(period_end, datetime.min.time()),
            period_label="최근 7일",
            comparison_label="vs 전주",
            source_type="kpi",
            fetched_at=datetime.utcnow(),
            is_cached=False,
        )

    async def _fetch_db_query_value(
        self,
        config: StatCardConfig,
        tenant_id: UUID,
    ) -> StatCardValue:
        """DB 쿼리 소스에서 값 조회"""
        # 화이트리스트 검증
        allowed = self._is_table_column_allowed(
            tenant_id,
            config.table_name,
            config.column_name,
        )
        if not allowed:
            return self._create_error_value(
                config,
                f"Table/column not allowed: {config.table_name}.{config.column_name}",
            )

        # 집계 함수 매핑
        agg_map = {
            "sum": "SUM",
            "avg": "AVG",
            "min": "MIN",
            "max": "MAX",
            "count": "COUNT",
            "last": "MAX",  # last는 MAX로 대체 (날짜 기준 최신)
        }
        agg_func = agg_map.get(config.aggregation, "AVG")

        # 쿼리 생성 (안전하게)
        schema_table = f"bi.{config.table_name}"
        query_sql = f"""
            SELECT {agg_func}({config.column_name}) as value
            FROM {schema_table}
            WHERE tenant_id = :tenant_id
        """

        # 필터 조건 추가
        params: Dict[str, Any] = {"tenant_id": str(tenant_id)}
        if config.filter_condition:
            for key, val in config.filter_condition.items():
                safe_key = key.replace(".", "_")
                query_sql += f" AND {key} = :{safe_key}"
                params[safe_key] = val

        result = self.db.execute(text(query_sql), params)
        row = result.fetchone()
        current_value = float(row[0]) if row and row[0] else 0.0

        # 상태 결정
        status = self._determine_status(
            current_value,
            float(config.green_threshold) if config.green_threshold else None,
            float(config.yellow_threshold) if config.yellow_threshold else None,
            float(config.red_threshold) if config.red_threshold else None,
            config.higher_is_better,
        )

        return StatCardValue(
            config_id=config.config_id,
            value=current_value,
            formatted_value=self._format_value(current_value, config.custom_unit),
            previous_value=None,
            change_percent=None,
            trend=None,
            status=status,
            title=config.custom_title or f"{config.table_name}.{config.column_name}",
            icon=config.custom_icon or "Database",
            unit=config.custom_unit,
            period_label="DB 쿼리",
            source_type="db_query",
            fetched_at=datetime.utcnow(),
            is_cached=False,
        )

    async def _fetch_mcp_value(
        self,
        config: StatCardConfig,
        tenant_id: UUID,
    ) -> StatCardValue:
        """MCP 도구 소스에서 값 조회"""
        try:
            mcp_service = MCPToolHubService(self.db)
            result = await mcp_service.call_tool(
                server_id=config.mcp_server_id,
                tenant_id=tenant_id,
                tool_name=config.mcp_tool_name,
                params=config.mcp_params or {},
            )

            # 결과에서 값 추출
            current_value = self._extract_value_from_result(
                result,
                config.mcp_result_key,
            )

            status = self._determine_status(
                current_value,
                float(config.green_threshold) if config.green_threshold else None,
                float(config.yellow_threshold) if config.yellow_threshold else None,
                float(config.red_threshold) if config.red_threshold else None,
                config.higher_is_better,
            )

            return StatCardValue(
                config_id=config.config_id,
                value=current_value,
                formatted_value=self._format_value(current_value, config.custom_unit),
                previous_value=None,
                change_percent=None,
                trend=None,
                status=status,
                title=config.custom_title or config.mcp_tool_name,
                icon=config.custom_icon or "Plug",
                unit=config.custom_unit,
                period_label="MCP 연동",
                source_type="mcp_tool",
                fetched_at=datetime.utcnow(),
                is_cached=False,
            )
        except Exception as e:
            logger.error(f"MCP tool call failed: {e}")
            return self._create_error_value(config, f"MCP call failed: {str(e)}")

    # =====================================================
    # KPI 목록 조회
    # =====================================================

    def list_kpis(self, tenant_id: UUID) -> KpiListResponse:
        """사용 가능한 KPI 목록 조회"""
        query = text("""
            SELECT kpi_code, name, name_en, category, unit, description,
                   higher_is_better, default_target, green_threshold, yellow_threshold, red_threshold
            FROM bi.dim_kpi
            WHERE tenant_id = :tenant_id AND is_active = true
            ORDER BY category, kpi_code
        """)

        result = self.db.execute(query, {"tenant_id": str(tenant_id)})
        rows = result.fetchall()

        kpis = []
        categories = set()
        for row in rows:
            kpis.append(
                KpiInfo(
                    kpi_code=row[0],
                    name=row[1],
                    name_en=row[2],
                    category=row[3],
                    unit=row[4],
                    description=row[5],
                    higher_is_better=row[6],
                    default_target=float(row[7]) if row[7] else None,
                    green_threshold=float(row[8]) if row[8] else None,
                    yellow_threshold=float(row[9]) if row[9] else None,
                    red_threshold=float(row[10]) if row[10] else None,
                )
            )
            categories.add(row[3])

        return KpiListResponse(kpis=kpis, categories=sorted(categories))

    # =====================================================
    # 사용 가능한 테이블/컬럼 조회
    # =====================================================

    def list_available_tables(self, tenant_id: UUID) -> AvailableTablesResponse:
        """StatCard DB 쿼리에서 사용 가능한 테이블/컬럼 목록"""
        query = text("""
            SELECT schema_name, table_name, column_name, data_type, description, allowed_aggregations
            FROM bi.allowed_stat_card_tables
            WHERE tenant_id = :tenant_id AND is_active = true
            ORDER BY schema_name, table_name, column_name
        """)

        result = self.db.execute(query, {"tenant_id": str(tenant_id)})
        rows = result.fetchall()

        # 테이블별로 그룹화
        tables_map: Dict[str, TableInfo] = {}
        for row in rows:
            schema_name, table_name, column_name, data_type, desc, aggs = row
            key = f"{schema_name}.{table_name}"

            if key not in tables_map:
                tables_map[key] = TableInfo(
                    schema_name=schema_name,
                    table_name=table_name,
                    columns=[],
                )

            tables_map[key].columns.append(
                ColumnInfo(
                    column_name=column_name,
                    data_type=data_type,
                    description=desc,
                    allowed_aggregations=aggs or ["sum", "avg", "min", "max", "count", "last"],
                )
            )

        return AvailableTablesResponse(tables=list(tables_map.values()))

    # =====================================================
    # MCP 도구 목록 조회
    # =====================================================

    def list_mcp_tools(self, tenant_id: UUID) -> McpToolListResponse:
        """사용 가능한 MCP 도구 목록"""
        query = text("""
            SELECT s.id as server_id, s.name as server_name,
                   t.tool_name, t.description, t.input_schema
            FROM core.mcp_servers s
            JOIN core.mcp_tools t ON s.id = t.mcp_server_id
            WHERE s.tenant_id = :tenant_id
                AND s.status = 'active'
                AND t.is_enabled = true
            ORDER BY s.name, t.tool_name
        """)

        result = self.db.execute(query, {"tenant_id": str(tenant_id)})
        rows = result.fetchall()

        tools = []
        for row in rows:
            tools.append(
                McpToolInfo(
                    server_id=row[0],
                    server_name=row[1],
                    tool_name=row[2],
                    description=row[3],
                    input_schema=row[4],
                )
            )

        return McpToolListResponse(tools=tools)

    # =====================================================
    # 헬퍼 메서드
    # =====================================================

    def _get_next_display_order(self, tenant_id: UUID, user_id: UUID) -> int:
        """다음 display_order 계산"""
        query = text("""
            SELECT COALESCE(MAX(display_order), -1) + 1
            FROM bi.stat_card_configs
            WHERE tenant_id = :tenant_id AND user_id = :user_id
        """)
        result = self.db.execute(
            query,
            {"tenant_id": str(tenant_id), "user_id": str(user_id)},
        )
        return result.scalar() or 0

    def _is_table_column_allowed(
        self,
        tenant_id: UUID,
        table_name: str,
        column_name: str,
    ) -> bool:
        """테이블/컬럼 화이트리스트 검증"""
        query = text("""
            SELECT 1 FROM bi.allowed_stat_card_tables
            WHERE tenant_id = :tenant_id
                AND table_name = :table_name
                AND column_name = :column_name
                AND is_active = true
        """)
        result = self.db.execute(
            query,
            {
                "tenant_id": str(tenant_id),
                "table_name": table_name,
                "column_name": column_name,
            },
        )
        return result.fetchone() is not None

    def _determine_status(
        self,
        value: float,
        green_th: Optional[float],
        yellow_th: Optional[float],
        red_th: Optional[float],
        higher_is_better: bool,
    ) -> StatusType:
        """임계값 기준으로 상태 결정"""
        if green_th is None and yellow_th is None and red_th is None:
            return "gray"

        if higher_is_better:
            # 높을수록 좋음 (예: OEE)
            if green_th and value >= green_th:
                return "green"
            if yellow_th and value >= yellow_th:
                return "yellow"
            return "red"
        else:
            # 낮을수록 좋음 (예: 불량률)
            if green_th and value <= green_th:
                return "green"
            if yellow_th and value <= yellow_th:
                return "yellow"
            return "red"

    def _format_value(self, value: float, unit: Optional[str]) -> str:
        """값 포맷팅"""
        if unit == "%":
            return f"{value:.1f}%"
        elif unit in ("min", "분"):
            return f"{value:.0f}분"
        elif unit in ("sec", "초"):
            return f"{value:.1f}초"
        elif unit in ("days", "일"):
            return f"{value:.1f}일"
        elif value >= 1000000:
            return f"{value/1000000:.1f}M"
        elif value >= 1000:
            return f"{value/1000:.1f}K"
        else:
            return f"{value:.1f}"

    def _get_kpi_icon(self, kpi_code: str) -> str:
        """KPI별 기본 아이콘"""
        icon_map = {
            "defect_rate": "AlertTriangle",
            "oee": "Activity",
            "yield_rate": "TrendingUp",
            "downtime": "Clock",
            "cycle_time": "Timer",
            "inventory_days": "Package",
        }
        return icon_map.get(kpi_code, "BarChart3")

    def _extract_value_from_result(
        self,
        result: Any,
        result_key: Optional[str],
    ) -> float:
        """MCP 결과에서 값 추출"""
        if result_key:
            # 점 표기법으로 중첩 접근 (예: "data.total")
            keys = result_key.split(".")
            current = result
            for key in keys:
                if isinstance(current, dict):
                    current = current.get(key)
                else:
                    return 0.0
            return float(current) if current else 0.0
        elif isinstance(result, (int, float)):
            return float(result)
        elif isinstance(result, dict) and "value" in result:
            return float(result["value"])
        return 0.0

    def _create_error_value(
        self,
        config: StatCardConfig,
        error_message: str,
    ) -> StatCardValue:
        """에러 상태의 StatCardValue 생성"""
        return StatCardValue(
            config_id=config.config_id,
            value=None,
            formatted_value="Error",
            previous_value=None,
            change_percent=None,
            trend=None,
            status="gray",
            title=config.custom_title or "Error",
            icon=config.custom_icon or "AlertCircle",
            unit=None,
            source_type=config.source_type,
            fetched_at=datetime.utcnow(),
            is_cached=False,
        )

    def _get_from_cache(
        self,
        key: str,
        ttl_seconds: int,
    ) -> Optional[StatCardValue]:
        """캐시에서 값 조회"""
        if key in self._cache:
            value, cached_at = self._cache[key]
            if datetime.utcnow() - cached_at < timedelta(seconds=ttl_seconds):
                return value
            del self._cache[key]
        return None

    def _set_cache(self, key: str, value: StatCardValue) -> None:
        """캐시에 값 저장"""
        self._cache[key] = (value, datetime.utcnow())

    def _row_to_config(self, row) -> StatCardConfig:
        """DB row를 StatCardConfig로 변환"""
        return StatCardConfig(
            config_id=row[0],
            tenant_id=row[1],
            user_id=row[2],
            display_order=row[3],
            is_visible=row[4],
            source_type=row[5],
            kpi_code=row[6],
            table_name=row[7],
            column_name=row[8],
            aggregation=row[9],
            filter_condition=row[10],
            mcp_server_id=row[11],
            mcp_tool_name=row[12],
            mcp_params=row[13],
            mcp_result_key=row[14],
            custom_title=row[15],
            custom_icon=row[16],
            custom_unit=row[17],
            green_threshold=float(row[18]) if row[18] else None,
            yellow_threshold=float(row[19]) if row[19] else None,
            red_threshold=float(row[20]) if row[20] else None,
            higher_is_better=row[21],
            cache_ttl_seconds=row[22],
            created_at=row[23],
            updated_at=row[24],
        )
