"""
BI Data Collector - Star Schema 기반 데이터 수집 레이어

bi 스키마의 DIM/FACT 테이블에서 분석용 데이터를 수집하여
AI 인사이트 생성에 필요한 컨텍스트를 구성합니다.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import logging

logger = logging.getLogger(__name__)


# =====================================================
# Default Thresholds (dim_kpi에 없으면 사용)
# =====================================================
DEFAULT_THRESHOLDS = {
    "achievement_rate": {"green": 95.0, "yellow": 80.0, "unit": "%", "higher_is_better": True},
    "defect_rate": {"green": 2.0, "yellow": 3.0, "unit": "%", "higher_is_better": False},
    "yield_rate": {"green": 97.0, "yellow": 95.0, "unit": "%", "higher_is_better": True},
    "downtime_minutes": {"green": 30.0, "yellow": 60.0, "unit": "min", "higher_is_better": False},
    "oee": {"green": 85.0, "yellow": 75.0, "unit": "%", "higher_is_better": True},
}


def _convert_decimal(value: Any) -> Any:
    """Decimal을 float로 변환"""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: _convert_decimal(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_convert_decimal(v) for v in value]
    return value


class BIDataCollector:
    """
    BI 스키마 데이터 수집기

    Star Schema 기반으로 생산, 불량, 설비 데이터를 수집하여
    AI 인사이트 생성에 필요한 컨텍스트를 구성합니다.
    """

    def __init__(self, db: AsyncSession, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id

    # =====================================================
    # 1. 라인 메타데이터 조회
    # =====================================================
    async def get_line_metadata(self) -> list[dict]:
        """
        활성화된 생산 라인 메타데이터 조회

        Returns:
            라인 코드, 이름, 일일 목표, 시간당 용량 등
        """
        query = text("""
            SELECT
                line_code,
                name,
                category,
                capacity_per_hour,
                capacity_unit,
                plant_code,
                department,
                COALESCE((attributes->>'daily_target')::int, 0) as daily_target,
                COALESCE((attributes->>'target_oee')::numeric, 85.0) as target_oee,
                attributes
            FROM bi.dim_line
            WHERE tenant_id = :tenant_id
              AND is_active = true
            ORDER BY line_code
        """)

        result = await self.db.execute(query, {"tenant_id": str(self.tenant_id)})
        rows = result.fetchall()

        return [
            {
                "line_code": row.line_code,
                "name": row.name,
                "category": row.category,
                "capacity_per_hour": _convert_decimal(row.capacity_per_hour),
                "capacity_unit": row.capacity_unit,
                "plant_code": row.plant_code,
                "department": row.department,
                "daily_target": row.daily_target,
                "target_oee": _convert_decimal(row.target_oee),
                "attributes": row.attributes,
            }
            for row in rows
        ]

    # =====================================================
    # 2. KPI Threshold 조회
    # =====================================================
    async def get_kpi_thresholds(self) -> dict[str, dict]:
        """
        테넌트별 KPI 기준값 조회

        Returns:
            KPI 코드별 green/yellow/red 기준값
        """
        query = text("""
            SELECT
                kpi_code,
                name,
                category,
                unit,
                default_target,
                green_threshold,
                yellow_threshold,
                red_threshold,
                higher_is_better
            FROM bi.dim_kpi
            WHERE tenant_id = :tenant_id
              AND is_active = true
        """)

        result = await self.db.execute(query, {"tenant_id": str(self.tenant_id)})
        rows = result.fetchall()

        # DB에서 조회된 값으로 덮어쓰기
        thresholds = {**DEFAULT_THRESHOLDS}

        for row in rows:
            thresholds[row.kpi_code] = {
                "name": row.name,
                "category": row.category,
                "unit": row.unit,
                "target": _convert_decimal(row.default_target),
                "green": _convert_decimal(row.green_threshold),
                "yellow": _convert_decimal(row.yellow_threshold),
                "red": _convert_decimal(row.red_threshold),
                "higher_is_better": row.higher_is_better,
            }

        return thresholds

    # =====================================================
    # 3. 일일 생산 현황 조회
    # =====================================================
    async def get_production_summary(
        self,
        target_date: Optional[date] = None,
        line_code: Optional[str] = None,
    ) -> list[dict]:
        """
        라인별 일일 생산 현황 집계

        Args:
            target_date: 조회 대상 날짜 (기본: 오늘)
            line_code: 특정 라인 필터 (None이면 전체)

        Returns:
            라인별 생산량, 달성률, 불량률, 비가동 시간 등
        """
        if target_date is None:
            target_date = date.today()

        params = {
            "tenant_id": str(self.tenant_id),
            "target_date": target_date,
        }

        line_filter = ""
        if line_code:
            line_filter = "AND f.line_code = :line_code"
            params["line_code"] = line_code

        query = text(f"""
            SELECT
                l.line_code,
                l.name as line_name,
                COALESCE((l.attributes->>'daily_target')::int, 0) as daily_target,
                COALESCE(SUM(f.total_qty), 0) as actual_qty,
                COALESCE(SUM(f.good_qty), 0) as good_qty,
                COALESCE(SUM(f.defect_qty), 0) as defect_qty,
                COALESCE(SUM(f.rework_qty), 0) as rework_qty,
                COALESCE(SUM(f.scrap_qty), 0) as scrap_qty,
                COALESCE(SUM(f.runtime_minutes), 0) as runtime_min,
                COALESCE(SUM(f.downtime_minutes), 0) as downtime_min,
                COALESCE(SUM(f.setup_time_minutes), 0) as setup_min,
                COALESCE(AVG(f.cycle_time_avg), 0) as avg_cycle_time,
                CASE
                    WHEN SUM(f.total_qty) > 0
                    THEN ROUND(100.0 * SUM(f.good_qty) / SUM(f.total_qty), 1)
                    ELSE 0
                END as yield_rate,
                CASE
                    WHEN SUM(f.total_qty) > 0
                    THEN ROUND(100.0 * SUM(f.defect_qty) / SUM(f.total_qty), 1)
                    ELSE 0
                END as defect_rate,
                CASE
                    WHEN COALESCE((l.attributes->>'daily_target')::int, 0) > 0
                    THEN ROUND(100.0 * COALESCE(SUM(f.total_qty), 0) / (l.attributes->>'daily_target')::int, 1)
                    ELSE 0
                END as achievement_rate
            FROM bi.dim_line l
            LEFT JOIN bi.fact_daily_production f
                ON l.tenant_id = f.tenant_id
                AND l.line_code = f.line_code
                AND f.date = :target_date
            WHERE l.tenant_id = :tenant_id
              AND l.is_active = true
              {line_filter}
            GROUP BY l.line_code, l.name, l.attributes
            ORDER BY l.line_code
        """)

        result = await self.db.execute(query, params)
        rows = result.fetchall()

        return [
            {
                "line_code": row.line_code,
                "line_name": row.line_name,
                "daily_target": row.daily_target,
                "actual_qty": _convert_decimal(row.actual_qty),
                "good_qty": _convert_decimal(row.good_qty),
                "defect_qty": _convert_decimal(row.defect_qty),
                "rework_qty": _convert_decimal(row.rework_qty),
                "scrap_qty": _convert_decimal(row.scrap_qty),
                "runtime_min": _convert_decimal(row.runtime_min),
                "downtime_min": _convert_decimal(row.downtime_min),
                "setup_min": _convert_decimal(row.setup_min),
                "avg_cycle_time": _convert_decimal(row.avg_cycle_time),
                "yield_rate": _convert_decimal(row.yield_rate),
                "defect_rate": _convert_decimal(row.defect_rate),
                "achievement_rate": _convert_decimal(row.achievement_rate),
            }
            for row in rows
        ]

    # =====================================================
    # 4. 불량 상세 조회
    # =====================================================
    async def get_defect_summary(
        self,
        target_date: Optional[date] = None,
        line_code: Optional[str] = None,
    ) -> list[dict]:
        """
        불량 유형별 현황 집계

        Args:
            target_date: 조회 대상 날짜 (기본: 오늘)
            line_code: 특정 라인 필터

        Returns:
            불량 유형별 수량, 비율, 원인 등
        """
        if target_date is None:
            target_date = date.today()

        params = {
            "tenant_id": str(self.tenant_id),
            "target_date": target_date,
        }

        line_filter = ""
        if line_code:
            line_filter = "AND f.line_code = :line_code"
            params["line_code"] = line_code

        query = text(f"""
            SELECT
                f.line_code,
                f.defect_type,
                SUM(f.defect_qty) as total_defect_qty,
                SUM(f.defect_cost) as total_defect_cost,
                COUNT(DISTINCT f.product_code) as affected_products,
                ARRAY_AGG(DISTINCT f.root_cause) FILTER (WHERE f.root_cause IS NOT NULL) as root_causes
            FROM bi.fact_daily_defect f
            WHERE f.tenant_id = :tenant_id
              AND f.date = :target_date
              {line_filter}
            GROUP BY f.line_code, f.defect_type
            ORDER BY total_defect_qty DESC
        """)

        result = await self.db.execute(query, params)
        rows = result.fetchall()

        return [
            {
                "line_code": row.line_code,
                "defect_type": row.defect_type,
                "total_defect_qty": _convert_decimal(row.total_defect_qty),
                "total_defect_cost": _convert_decimal(row.total_defect_cost),
                "affected_products": row.affected_products,
                "root_causes": row.root_causes or [],
            }
            for row in rows
        ]

    # =====================================================
    # 5. 설비 이벤트/비가동 현황 조회
    # =====================================================
    async def get_downtime_summary(
        self,
        target_date: Optional[date] = None,
        line_code: Optional[str] = None,
    ) -> list[dict]:
        """
        설비별 비가동 현황 집계

        Args:
            target_date: 조회 대상 날짜 (기본: 오늘)
            line_code: 특정 라인 필터

        Returns:
            설비별 이벤트 유형, 비가동 시간, 횟수 등
        """
        if target_date is None:
            target_date = date.today()

        params = {
            "tenant_id": str(self.tenant_id),
            "target_date": target_date,
        }

        line_filter = ""
        if line_code:
            line_filter = "AND e.line_code = :line_code"
            params["line_code"] = line_code

        query = text(f"""
            SELECT
                e.line_code,
                f.equipment_code,
                e.name as equipment_name,
                f.event_type,
                SUM(f.event_count) as total_events,
                SUM(f.total_duration_minutes) as total_duration_min,
                AVG(f.avg_duration_minutes) as avg_duration_min,
                MAX(f.max_duration_minutes) as max_duration_min,
                f.severity_distribution
            FROM bi.fact_equipment_event f
            JOIN bi.dim_equipment e
                ON f.tenant_id = e.tenant_id
                AND f.equipment_code = e.equipment_code
            WHERE f.tenant_id = :tenant_id
              AND f.date = :target_date
              {line_filter}
            GROUP BY e.line_code, f.equipment_code, e.name, f.event_type, f.severity_distribution
            ORDER BY total_duration_min DESC
        """)

        result = await self.db.execute(query, params)
        rows = result.fetchall()

        return [
            {
                "line_code": row.line_code,
                "equipment_code": row.equipment_code,
                "equipment_name": row.equipment_name,
                "event_type": row.event_type,
                "total_events": row.total_events,
                "total_duration_min": _convert_decimal(row.total_duration_min),
                "avg_duration_min": _convert_decimal(row.avg_duration_min),
                "max_duration_min": _convert_decimal(row.max_duration_min),
                "severity_distribution": row.severity_distribution,
            }
            for row in rows
        ]

    # =====================================================
    # 6. 전일/전주 대비 비교
    # =====================================================
    async def get_comparison_data(
        self,
        target_date: Optional[date] = None,
    ) -> dict:
        """
        전일/전주 대비 생산 실적 비교

        Args:
            target_date: 기준 날짜 (기본: 오늘)

        Returns:
            전일/전주 대비 변동률
        """
        if target_date is None:
            target_date = date.today()

        yesterday = target_date - timedelta(days=1)
        last_week = target_date - timedelta(days=7)

        query = text("""
            WITH today_data AS (
                SELECT
                    line_code,
                    SUM(total_qty) as total_qty,
                    SUM(good_qty) as good_qty,
                    SUM(defect_qty) as defect_qty,
                    SUM(downtime_minutes) as downtime_min
                FROM bi.fact_daily_production
                WHERE tenant_id = :tenant_id AND date = :today
                GROUP BY line_code
            ),
            yesterday_data AS (
                SELECT
                    line_code,
                    SUM(total_qty) as total_qty,
                    SUM(good_qty) as good_qty,
                    SUM(defect_qty) as defect_qty,
                    SUM(downtime_minutes) as downtime_min
                FROM bi.fact_daily_production
                WHERE tenant_id = :tenant_id AND date = :yesterday
                GROUP BY line_code
            ),
            lastweek_data AS (
                SELECT
                    line_code,
                    SUM(total_qty) as total_qty,
                    SUM(good_qty) as good_qty,
                    SUM(defect_qty) as defect_qty,
                    SUM(downtime_minutes) as downtime_min
                FROM bi.fact_daily_production
                WHERE tenant_id = :tenant_id AND date = :last_week
                GROUP BY line_code
            )
            SELECT
                COALESCE(t.line_code, y.line_code, l.line_code) as line_code,
                COALESCE(t.total_qty, 0) as today_qty,
                COALESCE(y.total_qty, 0) as yesterday_qty,
                COALESCE(l.total_qty, 0) as lastweek_qty,
                CASE WHEN COALESCE(y.total_qty, 0) > 0
                    THEN ROUND(100.0 * (COALESCE(t.total_qty, 0) - y.total_qty) / y.total_qty, 1)
                    ELSE 0
                END as vs_yesterday_pct,
                CASE WHEN COALESCE(l.total_qty, 0) > 0
                    THEN ROUND(100.0 * (COALESCE(t.total_qty, 0) - l.total_qty) / l.total_qty, 1)
                    ELSE 0
                END as vs_lastweek_pct,
                COALESCE(t.downtime_min, 0) as today_downtime,
                COALESCE(y.downtime_min, 0) as yesterday_downtime
            FROM today_data t
            FULL OUTER JOIN yesterday_data y ON t.line_code = y.line_code
            FULL OUTER JOIN lastweek_data l ON COALESCE(t.line_code, y.line_code) = l.line_code
            ORDER BY line_code
        """)

        result = await self.db.execute(
            query,
            {
                "tenant_id": str(self.tenant_id),
                "today": target_date,
                "yesterday": yesterday,
                "last_week": last_week,
            },
        )
        rows = result.fetchall()

        comparison_by_line = {}
        total_today = 0
        total_yesterday = 0
        total_lastweek = 0

        for row in rows:
            comparison_by_line[row.line_code] = {
                "today_qty": _convert_decimal(row.today_qty),
                "yesterday_qty": _convert_decimal(row.yesterday_qty),
                "lastweek_qty": _convert_decimal(row.lastweek_qty),
                "vs_yesterday_pct": _convert_decimal(row.vs_yesterday_pct),
                "vs_lastweek_pct": _convert_decimal(row.vs_lastweek_pct),
                "today_downtime": _convert_decimal(row.today_downtime),
                "yesterday_downtime": _convert_decimal(row.yesterday_downtime),
            }
            total_today += row.today_qty or 0
            total_yesterday += row.yesterday_qty or 0
            total_lastweek += row.lastweek_qty or 0

        # Decimal to float 변환
        total_today_f = float(total_today)
        total_yesterday_f = float(total_yesterday)
        total_lastweek_f = float(total_lastweek)

        return {
            "by_line": comparison_by_line,
            "total": {
                "today_qty": total_today_f,
                "yesterday_qty": total_yesterday_f,
                "lastweek_qty": total_lastweek_f,
                "vs_yesterday_pct": (
                    round(100.0 * (total_today_f - total_yesterday_f) / total_yesterday_f, 1)
                    if total_yesterday_f > 0 else 0
                ),
                "vs_lastweek_pct": (
                    round(100.0 * (total_today_f - total_lastweek_f) / total_lastweek_f, 1)
                    if total_lastweek_f > 0 else 0
                ),
            },
        }

    # =====================================================
    # 7. 7일 추이 데이터
    # =====================================================
    async def get_trend_data(
        self,
        days: int = 7,
        end_date: Optional[date] = None,
    ) -> list[dict]:
        """
        최근 N일간 일별 생산 추이

        Args:
            days: 조회 기간 (기본: 7일)
            end_date: 종료 날짜 (기본: 오늘)

        Returns:
            일별 생산량, 불량률, 비가동 시간 추이
        """
        if end_date is None:
            end_date = date.today()

        start_date = end_date - timedelta(days=days - 1)

        query = text("""
            SELECT
                f.date,
                SUM(f.total_qty) as total_qty,
                SUM(f.good_qty) as good_qty,
                SUM(f.defect_qty) as defect_qty,
                SUM(f.downtime_minutes) as downtime_min,
                CASE
                    WHEN SUM(f.total_qty) > 0
                    THEN ROUND(100.0 * SUM(f.good_qty) / SUM(f.total_qty), 1)
                    ELSE 0
                END as yield_rate,
                CASE
                    WHEN SUM(f.total_qty) > 0
                    THEN ROUND(100.0 * SUM(f.defect_qty) / SUM(f.total_qty), 1)
                    ELSE 0
                END as defect_rate
            FROM bi.fact_daily_production f
            WHERE f.tenant_id = :tenant_id
              AND f.date BETWEEN :start_date AND :end_date
            GROUP BY f.date
            ORDER BY f.date
        """)

        result = await self.db.execute(
            query,
            {
                "tenant_id": str(self.tenant_id),
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        rows = result.fetchall()

        return [
            {
                "date": row.date.isoformat(),
                "total_qty": _convert_decimal(row.total_qty),
                "good_qty": _convert_decimal(row.good_qty),
                "defect_qty": _convert_decimal(row.defect_qty),
                "downtime_min": _convert_decimal(row.downtime_min),
                "yield_rate": _convert_decimal(row.yield_rate),
                "defect_rate": _convert_decimal(row.defect_rate),
            }
            for row in rows
        ]

    # =====================================================
    # 8. 종합 컨텍스트 수집
    # =====================================================
    async def collect_insight_context(
        self,
        target_date: Optional[date] = None,
        line_code: Optional[str] = None,
        include_trends: bool = True,
    ) -> dict:
        """
        AI 인사이트 생성을 위한 종합 컨텍스트 수집

        Args:
            target_date: 기준 날짜
            line_code: 특정 라인 필터
            include_trends: 추이 데이터 포함 여부

        Returns:
            통합된 분석 컨텍스트
        """
        if target_date is None:
            target_date = date.today()

        context = {
            "target_date": target_date.isoformat(),
            "line_filter": line_code,
            "thresholds": await self.get_kpi_thresholds(),
            "line_metadata": await self.get_line_metadata(),
            "production_data": await self.get_production_summary(target_date, line_code),
            "defect_data": await self.get_defect_summary(target_date, line_code),
            "downtime_data": await self.get_downtime_summary(target_date, line_code),
            "comparison": await self.get_comparison_data(target_date),
        }

        if include_trends:
            context["trend_data"] = await self.get_trend_data(7, target_date)

        return context


class ThresholdEvaluator:
    """
    KPI Threshold 기반 상태 평가
    """

    def __init__(self, thresholds: dict[str, dict]):
        self.thresholds = thresholds

    def evaluate(self, kpi_code: str, value: float) -> str:
        """
        KPI 값을 기준값과 비교하여 상태 반환

        Args:
            kpi_code: KPI 코드 (예: 'achievement_rate')
            value: 실제 값

        Returns:
            'normal', 'warning', 'critical' 중 하나
        """
        if kpi_code not in self.thresholds:
            return "normal"

        threshold = self.thresholds[kpi_code]
        green = threshold.get("green")
        yellow = threshold.get("yellow")
        higher_is_better = threshold.get("higher_is_better", True)

        if green is None or yellow is None:
            return "normal"

        if higher_is_better:
            # 높을수록 좋은 경우 (달성률, 수율 등)
            if value >= green:
                return "normal"
            elif value >= yellow:
                return "warning"
            else:
                return "critical"
        else:
            # 낮을수록 좋은 경우 (불량률, 비가동 등)
            if value <= green:
                return "normal"
            elif value <= yellow:
                return "warning"
            else:
                return "critical"

    def get_status_emoji(self, status: str) -> str:
        """상태에 맞는 이모지 반환"""
        return {
            "normal": "✅",
            "warning": "⚠️",
            "critical": "🚨",
        }.get(status, "❓")
