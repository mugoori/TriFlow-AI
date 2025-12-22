"""
BI Correlation Analyzer - 연관 분석 엔진

달성률, 불량률, 비가동 시간 등의 이상 징후를 감지하고
자동으로 원인 분석을 수행합니다.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import logging

logger = logging.getLogger(__name__)


def _convert_decimal(value: Any) -> Any:
    """Decimal을 float로 변환"""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: _convert_decimal(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_convert_decimal(v) for v in value]
    return value


@dataclass
class AnalysisTrigger:
    """분석 트리거 조건"""

    trigger_type: str  # 'low_achievement', 'high_defect', 'sudden_drop', 'high_downtime'
    severity: str  # 'warning', 'critical'
    affected_line: str
    metric_name: str
    metric_value: float
    threshold_value: float
    message: str


class CorrelationAnalyzer:
    """
    연관 분석 엔진

    이상 징후 감지 시 자동으로 원인 분석을 수행:
    - 달성률 저조 → 비가동 원인 분석
    - 불량률 급증 → 불량 유형 및 파라미터 분석
    - 급격한 변동 → 변화 원인 분석
    """

    def __init__(self, db: AsyncSession, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id

    # =====================================================
    # 1. 트리거 조건 감지
    # =====================================================
    def detect_triggers(
        self,
        production_data: list[dict],
        comparison_data: dict,
        thresholds: dict,
    ) -> list[AnalysisTrigger]:
        """
        생산 데이터에서 분석이 필요한 이상 징후 감지

        Args:
            production_data: 라인별 생산 현황
            comparison_data: 전일/전주 대비 데이터
            thresholds: KPI 기준값

        Returns:
            감지된 트리거 목록
        """
        triggers = []

        # 달성률 기준값
        ach_green = thresholds.get("achievement_rate", {}).get("green", 95.0)
        ach_yellow = thresholds.get("achievement_rate", {}).get("yellow", 80.0)

        # 불량률 기준값
        def_green = thresholds.get("defect_rate", {}).get("green", 2.0)
        def_yellow = thresholds.get("defect_rate", {}).get("yellow", 3.0)

        # 비가동 기준값 (분)
        dt_green = thresholds.get("downtime_minutes", {}).get("green", 30.0)
        dt_yellow = thresholds.get("downtime_minutes", {}).get("yellow", 60.0)

        for line in production_data:
            line_code = line.get("line_code", "Unknown")
            achievement = line.get("achievement_rate", 0)
            defect_rate = line.get("defect_rate", 0)
            downtime = line.get("downtime_min", 0)

            # 1. 달성률 저조
            if achievement < ach_yellow:
                severity = "critical" if achievement < ach_yellow * 0.8 else "warning"
                triggers.append(
                    AnalysisTrigger(
                        trigger_type="low_achievement",
                        severity=severity,
                        affected_line=line_code,
                        metric_name="달성률",
                        metric_value=achievement,
                        threshold_value=ach_yellow,
                        message=f"{line_code} 라인 달성률 {achievement}% (목표 {ach_yellow}% 미달)",
                    )
                )

            # 2. 불량률 초과
            if defect_rate > def_yellow:
                severity = "critical" if defect_rate > def_yellow * 1.5 else "warning"
                triggers.append(
                    AnalysisTrigger(
                        trigger_type="high_defect",
                        severity=severity,
                        affected_line=line_code,
                        metric_name="불량률",
                        metric_value=defect_rate,
                        threshold_value=def_yellow,
                        message=f"{line_code} 라인 불량률 {defect_rate}% (기준 {def_yellow}% 초과)",
                    )
                )

            # 3. 비가동 시간 초과
            if downtime > dt_yellow:
                severity = "critical" if downtime > dt_yellow * 1.5 else "warning"
                triggers.append(
                    AnalysisTrigger(
                        trigger_type="high_downtime",
                        severity=severity,
                        affected_line=line_code,
                        metric_name="비가동 시간",
                        metric_value=downtime,
                        threshold_value=dt_yellow,
                        message=f"{line_code} 라인 비가동 {downtime}분 (기준 {dt_yellow}분 초과)",
                    )
                )

        # 4. 전일 대비 급격한 하락 (10% 이상)
        if comparison_data and "by_line" in comparison_data:
            for line_code, comp in comparison_data["by_line"].items():
                vs_yesterday = comp.get("vs_yesterday_pct", 0)
                if vs_yesterday < -10:
                    triggers.append(
                        AnalysisTrigger(
                            trigger_type="sudden_drop",
                            severity="warning" if vs_yesterday > -20 else "critical",
                            affected_line=line_code,
                            metric_name="전일 대비",
                            metric_value=vs_yesterday,
                            threshold_value=-10,
                            message=f"{line_code} 라인 전일 대비 {vs_yesterday}% 감소",
                        )
                    )

        return triggers

    # =====================================================
    # 2. 비가동 원인 분석
    # =====================================================
    async def analyze_downtime_causes(
        self,
        line_code: str,
        target_date: Optional[date] = None,
        limit: int = 5,
    ) -> dict:
        """
        특정 라인의 비가동 원인 Top N 분석

        Args:
            line_code: 분석 대상 라인
            target_date: 분석 날짜
            limit: 상위 N개

        Returns:
            비가동 원인 분석 결과
        """
        if target_date is None:
            target_date = date.today()

        # 비가동 유형별 집계
        query = text("""
            SELECT
                f.event_type,
                SUM(f.event_count) as event_count,
                SUM(f.total_duration_minutes) as total_min,
                AVG(f.avg_duration_minutes) as avg_min,
                e.equipment_code,
                e.name as equipment_name
            FROM bi.fact_equipment_event f
            JOIN bi.dim_equipment e
                ON f.tenant_id = e.tenant_id
                AND f.equipment_code = e.equipment_code
            WHERE f.tenant_id = :tenant_id
              AND f.date = :target_date
              AND e.line_code = :line_code
            GROUP BY f.event_type, e.equipment_code, e.name
            ORDER BY total_min DESC
            LIMIT :limit
        """)

        result = await self.db.execute(
            query,
            {
                "tenant_id": str(self.tenant_id),
                "target_date": target_date,
                "line_code": line_code,
                "limit": limit,
            },
        )
        rows = result.fetchall()

        causes = []
        total_downtime = 0

        for row in rows:
            causes.append({
                "event_type": row.event_type,
                "event_type_label": self._get_event_type_label(row.event_type),
                "equipment_code": row.equipment_code,
                "equipment_name": row.equipment_name,
                "event_count": row.event_count,
                "total_min": _convert_decimal(row.total_min),
                "avg_min": _convert_decimal(row.avg_min),
            })
            total_downtime += row.total_min or 0

        # 비율 계산
        for cause in causes:
            if total_downtime > 0:
                cause["percentage"] = round(100 * cause["total_min"] / float(total_downtime), 1)
            else:
                cause["percentage"] = 0

        return {
            "line_code": line_code,
            "date": target_date.isoformat(),
            "total_downtime_min": float(total_downtime),
            "causes": causes,
            "analysis_summary": self._summarize_downtime_causes(causes),
        }

    def _get_event_type_label(self, event_type: str) -> str:
        """이벤트 유형 라벨"""
        labels = {
            "alarm": "알람/경보",
            "breakdown": "고장/장애",
            "maintenance": "정비/PM",
            "setup": "셋업/품종 교체",
            "idle": "대기/공회전",
        }
        return labels.get(event_type, event_type)

    def _summarize_downtime_causes(self, causes: list[dict]) -> str:
        """비가동 원인 요약 생성"""
        if not causes:
            return "비가동 데이터가 없습니다."

        top_cause = causes[0]
        summary = f"주요 비가동 원인: {top_cause['event_type_label']}"
        summary += f" ({top_cause['equipment_name']}, {top_cause['total_min']}분, {top_cause['percentage']}%)"

        if len(causes) > 1:
            second = causes[1]
            summary += f". 2위: {second['event_type_label']} ({second['total_min']}분)"

        return summary

    # =====================================================
    # 3. 불량 원인 분석
    # =====================================================
    async def analyze_defect_distribution(
        self,
        line_code: str,
        target_date: Optional[date] = None,
        limit: int = 5,
    ) -> dict:
        """
        특정 라인의 불량 유형 분포 분석

        Args:
            line_code: 분석 대상 라인
            target_date: 분석 날짜
            limit: 상위 N개

        Returns:
            불량 유형 분석 결과
        """
        if target_date is None:
            target_date = date.today()

        query = text("""
            SELECT
                f.defect_type,
                SUM(f.defect_qty) as total_qty,
                SUM(f.defect_cost) as total_cost,
                COUNT(DISTINCT f.product_code) as product_count,
                ARRAY_AGG(DISTINCT f.root_cause) FILTER (WHERE f.root_cause IS NOT NULL) as root_causes,
                ARRAY_AGG(DISTINCT p.name) FILTER (WHERE p.name IS NOT NULL) as product_names
            FROM bi.fact_daily_defect f
            LEFT JOIN bi.dim_product p
                ON f.tenant_id = p.tenant_id AND f.product_code = p.product_code
            WHERE f.tenant_id = :tenant_id
              AND f.date = :target_date
              AND f.line_code = :line_code
            GROUP BY f.defect_type
            ORDER BY total_qty DESC
            LIMIT :limit
        """)

        result = await self.db.execute(
            query,
            {
                "tenant_id": str(self.tenant_id),
                "target_date": target_date,
                "line_code": line_code,
                "limit": limit,
            },
        )
        rows = result.fetchall()

        defects = []
        total_defect = 0

        for row in rows:
            defects.append({
                "defect_type": row.defect_type,
                "total_qty": _convert_decimal(row.total_qty),
                "total_cost": _convert_decimal(row.total_cost),
                "product_count": row.product_count,
                "root_causes": row.root_causes or [],
                "product_names": (row.product_names or [])[:3],  # 최대 3개
            })
            total_defect += row.total_qty or 0

        # 비율 계산
        for defect in defects:
            if total_defect > 0:
                defect["percentage"] = round(100 * defect["total_qty"] / float(total_defect), 1)
            else:
                defect["percentage"] = 0

        return {
            "line_code": line_code,
            "date": target_date.isoformat(),
            "total_defect_qty": float(total_defect),
            "defect_types": defects,
            "analysis_summary": self._summarize_defect_distribution(defects),
        }

    def _summarize_defect_distribution(self, defects: list[dict]) -> str:
        """불량 유형 요약 생성"""
        if not defects:
            return "불량 데이터가 없습니다."

        top_defect = defects[0]
        summary = f"주요 불량 유형: {top_defect['defect_type']} ({top_defect['total_qty']}EA, {top_defect['percentage']}%)"

        if top_defect.get("root_causes"):
            summary += f". 원인: {', '.join(top_defect['root_causes'][:2])}"

        return summary

    # =====================================================
    # 4. 변동 원인 분석
    # =====================================================
    async def analyze_change_causes(
        self,
        line_code: str,
        target_date: Optional[date] = None,
    ) -> dict:
        """
        전일 대비 급격한 변동 원인 분석

        Args:
            line_code: 분석 대상 라인
            target_date: 기준 날짜

        Returns:
            변동 원인 분석 결과
        """
        if target_date is None:
            target_date = date.today()

        yesterday = target_date - timedelta(days=1)

        # 오늘 vs 어제 비교
        query = text("""
            WITH today AS (
                SELECT
                    SUM(total_qty) as total_qty,
                    SUM(good_qty) as good_qty,
                    SUM(defect_qty) as defect_qty,
                    SUM(downtime_minutes) as downtime_min,
                    SUM(runtime_minutes) as runtime_min
                FROM bi.fact_daily_production
                WHERE tenant_id = :tenant_id
                  AND date = :today
                  AND line_code = :line_code
            ),
            yesterday AS (
                SELECT
                    SUM(total_qty) as total_qty,
                    SUM(good_qty) as good_qty,
                    SUM(defect_qty) as defect_qty,
                    SUM(downtime_minutes) as downtime_min,
                    SUM(runtime_minutes) as runtime_min
                FROM bi.fact_daily_production
                WHERE tenant_id = :tenant_id
                  AND date = :yesterday
                  AND line_code = :line_code
            )
            SELECT
                COALESCE(t.total_qty, 0) as today_qty,
                COALESCE(y.total_qty, 0) as yesterday_qty,
                COALESCE(t.downtime_min, 0) as today_downtime,
                COALESCE(y.downtime_min, 0) as yesterday_downtime,
                COALESCE(t.runtime_min, 0) as today_runtime,
                COALESCE(y.runtime_min, 0) as yesterday_runtime,
                COALESCE(t.defect_qty, 0) as today_defect,
                COALESCE(y.defect_qty, 0) as yesterday_defect
            FROM today t, yesterday y
        """)

        result = await self.db.execute(
            query,
            {
                "tenant_id": str(self.tenant_id),
                "today": target_date,
                "yesterday": yesterday,
                "line_code": line_code,
            },
        )
        row = result.fetchone()

        if not row:
            return {
                "line_code": line_code,
                "analysis_summary": "비교 데이터가 부족합니다.",
            }

        today_qty = float(row.today_qty or 0)
        yesterday_qty = float(row.yesterday_qty or 0)
        qty_change = (
            round(100 * (today_qty - yesterday_qty) / yesterday_qty, 1)
            if yesterday_qty > 0 else 0
        )

        today_downtime = float(row.today_downtime or 0)
        yesterday_downtime = float(row.yesterday_downtime or 0)
        downtime_change = today_downtime - yesterday_downtime

        today_defect = float(row.today_defect or 0)
        yesterday_defect = float(row.yesterday_defect or 0)
        defect_change = today_defect - yesterday_defect

        # 변동 원인 추론
        causes = []
        if downtime_change > 30:
            causes.append(f"비가동 시간 증가 (+{downtime_change:.0f}분)")
        if defect_change > 10:
            causes.append(f"불량 증가 (+{defect_change:.0f}EA)")

        return {
            "line_code": line_code,
            "date": target_date.isoformat(),
            "yesterday_date": yesterday.isoformat(),
            "metrics": {
                "qty_change_pct": qty_change,
                "today_qty": today_qty,
                "yesterday_qty": yesterday_qty,
                "downtime_change_min": downtime_change,
                "defect_change": defect_change,
            },
            "possible_causes": causes,
            "analysis_summary": self._summarize_change_causes(qty_change, causes),
        }

    def _summarize_change_causes(self, qty_change: float, causes: list[str]) -> str:
        """변동 원인 요약 생성"""
        direction = "감소" if qty_change < 0 else "증가"
        summary = f"전일 대비 생산량 {abs(qty_change)}% {direction}"

        if causes:
            summary += f". 주요 원인: {', '.join(causes)}"
        else:
            summary += ". 특이사항 없음"

        return summary

    # =====================================================
    # 5. 종합 연관 분석 실행
    # =====================================================
    async def run_correlation_analysis(
        self,
        production_data: list[dict],
        comparison_data: dict,
        thresholds: dict,
        target_date: Optional[date] = None,
    ) -> dict:
        """
        트리거 감지 및 연관 분석 종합 실행

        Args:
            production_data: 라인별 생산 현황
            comparison_data: 전일/전주 대비 데이터
            thresholds: KPI 기준값
            target_date: 분석 대상 날짜

        Returns:
            종합 분석 결과
        """
        if target_date is None:
            target_date = date.today()

        # 1. 트리거 감지
        triggers = self.detect_triggers(production_data, comparison_data, thresholds)

        if not triggers:
            return {
                "has_issues": False,
                "triggers": [],
                "analysis_results": {},
                "summary": "모든 지표가 정상 범위 내에 있습니다.",
            }

        # 2. 트리거별 상세 분석
        analysis_results = {}

        for trigger in triggers:
            line_code = trigger.affected_line

            if trigger.trigger_type == "low_achievement" or trigger.trigger_type == "high_downtime":
                # 비가동 원인 분석
                if line_code not in analysis_results:
                    analysis_results[line_code] = {}
                if "downtime_analysis" not in analysis_results[line_code]:
                    analysis_results[line_code]["downtime_analysis"] = (
                        await self.analyze_downtime_causes(line_code, target_date)
                    )

            elif trigger.trigger_type == "high_defect":
                # 불량 분석
                if line_code not in analysis_results:
                    analysis_results[line_code] = {}
                if "defect_analysis" not in analysis_results[line_code]:
                    analysis_results[line_code]["defect_analysis"] = (
                        await self.analyze_defect_distribution(line_code, target_date)
                    )

            elif trigger.trigger_type == "sudden_drop":
                # 변동 원인 분석
                if line_code not in analysis_results:
                    analysis_results[line_code] = {}
                if "change_analysis" not in analysis_results[line_code]:
                    analysis_results[line_code]["change_analysis"] = (
                        await self.analyze_change_causes(line_code, target_date)
                    )

        # 3. 전체 요약 생성
        critical_count = sum(1 for t in triggers if t.severity == "critical")
        warning_count = sum(1 for t in triggers if t.severity == "warning")

        summary_parts = []
        if critical_count > 0:
            summary_parts.append(f"🚨 긴급 {critical_count}건")
        if warning_count > 0:
            summary_parts.append(f"⚠️ 주의 {warning_count}건")

        return {
            "has_issues": True,
            "triggers": [
                {
                    "type": t.trigger_type,
                    "severity": t.severity,
                    "line_code": t.affected_line,
                    "metric_name": t.metric_name,
                    "metric_value": t.metric_value,
                    "threshold_value": t.threshold_value,
                    "message": t.message,
                }
                for t in triggers
            ],
            "analysis_results": analysis_results,
            "summary": f"이상 징후 감지: {', '.join(summary_parts)}",
            "critical_count": critical_count,
            "warning_count": warning_count,
        }
