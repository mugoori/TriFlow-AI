"""
TriFlow AI - BI Service
========================
B-2-2 스펙 기반 BI 분석 서비스

기능:
- RANK 분석: 상위/하위 N개, 백분위
- PREDICT 분석: 이동평균, 선형회귀
- WHAT_IF 시뮬레이션: 가정 기반 분석
- 차트 추천: 분석 유형별 최적 차트 추천
"""
import logging
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import text

from app.database import get_db_context
from app.utils.decorators import handle_service_errors
from app.services.redis_client import get_redis_client

logger = logging.getLogger(__name__)


# =========================================
# Enums & Data Classes
# =========================================

class AnalysisType(str, Enum):
    """분석 유형"""
    CHECK = "check"          # 현재 상태 조회
    TREND = "trend"          # 추이 분석
    COMPARE = "compare"      # 비교 분석
    RANK = "rank"            # 순위 분석
    PREDICT = "predict"      # 예측 분석
    WHAT_IF = "what_if"      # What-If 시뮬레이션


class ChartType(str, Enum):
    """차트 유형"""
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    AREA = "area"
    SCATTER = "scatter"
    TABLE = "table"
    GAUGE = "gauge"


class TimeGranularity(str, Enum):
    """시간 단위"""
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


@dataclass
class AnalysisPlan:
    """분석 계획"""
    query_text: str
    analysis_type: AnalysisType
    metrics: List[Dict[str, str]]  # [{"name": "production_count", "aggregation": "sum"}]
    dimensions: List[str]
    filters: List[Dict[str, Any]]
    time_range: Dict[str, Any]
    granularity: TimeGranularity = TimeGranularity.DAY
    chart_type: ChartType = ChartType.LINE
    confidence: float = 0.8
    # RANK 전용
    rank_limit: int = 5
    rank_order: str = "desc"  # "asc" or "desc"
    # PREDICT 전용
    forecast_periods: int = 7
    # WHAT_IF 전용
    what_if_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryResult:
    """쿼리 결과"""
    query_id: str
    sql: str
    columns: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    execution_time_ms: int


@dataclass
class AnalysisResult:
    """분석 결과"""
    analysis_type: AnalysisType
    data: List[Dict[str, Any]]
    summary: Dict[str, Any]
    chart_config: Dict[str, Any]
    insights: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PredictionResult:
    """예측 결과"""
    historical_data: List[Dict[str, Any]]
    forecast_data: List[Dict[str, Any]]
    model_info: Dict[str, Any]  # 사용된 모델, 정확도 등
    confidence_interval: Optional[Dict[str, Any]] = None


@dataclass
class WhatIfResult:
    """What-If 시뮬레이션 결과"""
    baseline: Dict[str, Any]
    scenario: Dict[str, Any]
    comparison: Dict[str, Any]
    impact_analysis: List[str]


# =========================================
# BI Service
# =========================================

class BIService:
    """
    BI 분석 서비스

    주요 기능:
    - RANK 분석 (상위/하위 N개)
    - PREDICT 분석 (이동평균, 선형회귀)
    - WHAT_IF 시뮬레이션
    - 차트 추천
    - Redis 캐싱 (TTL 600초)
    """

    # 캐시 TTL (초)
    CACHE_TTL = 600  # 10분

    def __init__(self):
        pass

    def _generate_cache_key(self, analysis_type: str, params: Dict[str, Any]) -> str:
        """
        캐시 키 생성

        Args:
            analysis_type: 분석 유형 (rank, predict, what_if)
            params: 분석 파라미터

        Returns:
            캐시 키 (해시)
        """
        # 파라미터를 정렬된 JSON으로 변환
        sorted_params = json.dumps(params, sort_keys=True)

        # 해시 생성
        hash_obj = hashlib.md5(sorted_params.encode())
        cache_hash = hash_obj.hexdigest()

        return f"bi:cache:{analysis_type}:{cache_hash}"

    async def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        캐시에서 결과 조회

        Args:
            cache_key: 캐시 키

        Returns:
            캐시된 결과 또는 None
        """
        try:
            redis = await get_redis_client()
            cached = await redis.get(cache_key)

            if cached:
                logger.info(f"Cache HIT: {cache_key}")
                return json.loads(cached)

            logger.debug(f"Cache MISS: {cache_key}")
            return None

        except Exception as e:
            logger.warning(f"Cache read failed: {e}")
            return None

    async def _set_cached_result(
        self,
        cache_key: str,
        result: Dict[str, Any],
        ttl: int = None
    ):
        """
        결과를 캐시에 저장

        Args:
            cache_key: 캐시 키
            result: 저장할 결과
            ttl: TTL (초, 기본 600초)
        """
        try:
            redis = await get_redis_client()
            ttl = ttl or self.CACHE_TTL

            # 결과에 캐시 메타데이터 추가
            result_with_meta = {
                **result,
                "from_cache": False,
                "cached_at": datetime.utcnow().isoformat(),
            }

            await redis.setex(
                cache_key,
                ttl,
                json.dumps(result_with_meta)
            )

            logger.info(f"Cache SET: {cache_key} (TTL: {ttl}s)")

        except Exception as e:
            logger.warning(f"Cache write failed: {e}")

    # =========================================
    # RANK 분석
    # =========================================

    async def analyze_rank(
        self,
        tenant_id: UUID,
        metric: str,
        dimension: str,
        limit: int = 5,
        order: str = "desc",
        time_range_days: int = 7,
        filters: Optional[Dict[str, Any]] = None,
    ) -> AnalysisResult:
        """
        RANK 분석: 상위/하위 N개 항목 분석 (캐싱 지원)

        Args:
            tenant_id: 테넌트 ID
            metric: 분석 지표 (예: "defect_rate", "production_count", "avg_temperature")
            dimension: 그룹화 차원 (예: "line_code", "sensor_type", "shift")
            limit: 반환할 항목 수 (기본 5)
            order: 정렬 순서 ("desc" = 상위, "asc" = 하위)
            time_range_days: 분석 기간 (일)
            filters: 추가 필터

        Returns:
            AnalysisResult (캐시된 경우 from_cache=True)
        """
        # 캐시 키 생성
        cache_params = {
            "tenant_id": str(tenant_id),
            "metric": metric,
            "dimension": dimension,
            "limit": limit,
            "order": order,
            "time_range_days": time_range_days,
            "filters": filters or {},
        }
        cache_key = self._generate_cache_key("rank", cache_params)

        # 캐시 조회
        cached_result = await self._get_cached_result(cache_key)
        if cached_result:
            cached_result["from_cache"] = True
            return cached_result

        logger.info(
            f"RANK analysis (NO CACHE): metric={metric}, dimension={dimension}, "
            f"limit={limit}, order={order}"
        )

        # SQL 생성 및 실행
        sql, params = self._build_rank_sql(
            tenant_id=tenant_id,
            metric=metric,
            dimension=dimension,
            limit=limit,
            order=order,
            time_range_days=time_range_days,
            filters=filters,
        )

        rows = await self._execute_sql(sql, params)

        # 백분위 계산
        rows_with_percentile = self._calculate_percentiles(rows, metric)

        # 요약 통계
        summary = self._calculate_rank_summary(rows_with_percentile, metric, order)

        # 차트 설정
        chart_config = self._build_rank_chart_config(
            data=rows_with_percentile,
            metric=metric,
            dimension=dimension,
            order=order,
        )

        # 인사이트 생성
        insights = self._generate_rank_insights(
            data=rows_with_percentile,
            metric=metric,
            dimension=dimension,
            order=order,
        )

        result = AnalysisResult(
            analysis_type=AnalysisType.RANK,
            data=rows_with_percentile,
            summary=summary,
            chart_config=chart_config,
            insights=insights,
            metadata={
                "metric": metric,
                "dimension": dimension,
                "limit": limit,
                "order": order,
                "time_range_days": time_range_days,
            },
        )

        # 캐시 저장
        await self._set_cached_result(cache_key, result.__dict__)

        return result

    def _build_rank_sql(
        self,
        tenant_id: UUID,
        metric: str,
        dimension: str,
        limit: int,
        order: str,
        time_range_days: int,
        filters: Optional[Dict[str, Any]],
    ) -> Tuple[str, Dict[str, Any]]:
        """RANK 분석용 SQL 생성"""
        # 메트릭별 SQL 표현식
        metric_expressions = {
            "defect_rate": """
                ROUND(
                    100.0 * SUM(CASE WHEN (output_data->>'is_defect')::boolean = true THEN 1 ELSE 0 END)
                    / NULLIF(COUNT(*), 0),
                    2
                )
            """,
            "production_count": "COUNT(*)",
            "defect_count": "SUM(CASE WHEN (output_data->>'is_defect')::boolean = true THEN 1 ELSE 0 END)",
            "avg_confidence": "ROUND(AVG(confidence)::numeric, 3)",
            "avg_execution_time": "ROUND(AVG(execution_time_ms)::numeric, 2)",
            "avg_temperature": "ROUND(AVG(value)::numeric, 2)",
            "max_temperature": "MAX(value)",
            "min_temperature": "MIN(value)",
            "avg_value": "ROUND(AVG(value)::numeric, 2)",
            "sum_value": "SUM(value)",
        }

        # 테이블 결정
        if metric in ["avg_temperature", "max_temperature", "min_temperature", "avg_value", "sum_value"]:
            table = "core.sensor_data"
            time_column = "recorded_at"
        else:
            table = "core.judgment_executions"
            time_column = "executed_at"

        metric_expr = metric_expressions.get(metric, "COUNT(*)")
        order_dir = "DESC" if order == "desc" else "ASC"

        sql = f"""
            WITH ranked_data AS (
                SELECT
                    {dimension},
                    {metric_expr} AS {metric},
                    COUNT(*) AS total_count,
                    ROW_NUMBER() OVER (ORDER BY {metric_expr} {order_dir}) AS rank
                FROM {table}
                WHERE
                    tenant_id = :tenant_id
                    AND {time_column} >= NOW() - INTERVAL '{time_range_days} days'
                GROUP BY {dimension}
            )
            SELECT
                rank,
                {dimension},
                {metric},
                total_count
            FROM ranked_data
            ORDER BY rank
            LIMIT :limit
        """

        params = {
            "tenant_id": str(tenant_id),
            "limit": limit,
        }

        return sql, params

    def _calculate_percentiles(
        self,
        rows: List[Dict[str, Any]],
        metric: str,
    ) -> List[Dict[str, Any]]:
        """백분위 계산"""
        if not rows:
            return []

        # 메트릭 값 추출
        values = [float(r.get(metric, 0) or 0) for r in rows]

        if not values:
            return rows

        # numpy 없이 백분위 계산
        sorted_values = sorted(values)
        n = len(sorted_values)

        result = []
        for row in rows:
            value = float(row.get(metric, 0) or 0)
            # 백분위 계산: 현재 값보다 작거나 같은 값의 비율
            rank_below = sum(1 for v in sorted_values if v <= value)
            percentile = round((rank_below / n) * 100, 1)

            result.append({
                **row,
                "percentile": percentile,
            })

        return result

    def _calculate_rank_summary(
        self,
        data: List[Dict[str, Any]],
        metric: str,
        order: str,
    ) -> Dict[str, Any]:
        """RANK 분석 요약 통계"""
        if not data:
            return {"total_items": 0}

        values = [float(r.get(metric, 0) or 0) for r in data]

        return {
            "total_items": len(data),
            "top_value": max(values) if values else 0,
            "bottom_value": min(values) if values else 0,
            "average": round(sum(values) / len(values), 2) if values else 0,
            "range": round(max(values) - min(values), 2) if values else 0,
            "top_item": data[0] if data else None,
            "analysis_direction": "highest" if order == "desc" else "lowest",
        }

    def _build_rank_chart_config(
        self,
        data: List[Dict[str, Any]],
        metric: str,
        dimension: str,
        order: str,
    ) -> Dict[str, Any]:
        """RANK 분석 차트 설정"""
        return {
            "type": "bar",
            "data": data,
            "xAxis": {"dataKey": dimension, "label": dimension},
            "yAxis": {"label": metric},
            "bars": [{"dataKey": metric, "fill": "#8884d8", "name": metric}],
            "layout": "vertical",  # 수평 막대 차트
            "analysis_goal": f"{'상위' if order == 'desc' else '하위'} {len(data)}개 {dimension}별 {metric} 분석",
        }

    def _generate_rank_insights(
        self,
        data: List[Dict[str, Any]],
        metric: str,
        dimension: str,
        order: str,
    ) -> List[str]:
        """RANK 분석 인사이트 생성"""
        if not data:
            return ["분석할 데이터가 없습니다."]

        insights = []
        direction = "높은" if order == "desc" else "낮은"

        # 1위 항목
        top_item = data[0]
        insights.append(
            f"가장 {direction} {metric}을 보이는 {dimension}은 "
            f"'{top_item.get(dimension)}'입니다 ({metric}: {top_item.get(metric)})"
        )

        # 상위/하위 비교
        if len(data) >= 2:
            first_value = float(top_item.get(metric, 0) or 0)
            second_value = float(data[1].get(metric, 0) or 0)
            if second_value > 0:
                ratio = round((first_value / second_value - 1) * 100, 1)
                insights.append(
                    f"1위와 2위 간 차이는 {abs(ratio):.1f}%입니다."
                )

        # 백분위 기반 인사이트
        if data[0].get("percentile", 0) >= 90:
            insights.append(
                f"'{data[0].get(dimension)}'는 상위 {100 - data[0].get('percentile', 0):.0f}%에 해당합니다."
            )

        return insights

    # =========================================
    # PREDICT 분석
    # =========================================

    async def analyze_predict(
        self,
        tenant_id: UUID,
        metric: str,
        dimension: Optional[str] = None,
        time_range_days: int = 30,
        forecast_periods: int = 7,
        method: str = "moving_average",  # "moving_average", "linear_regression"
        granularity: TimeGranularity = TimeGranularity.DAY,
    ) -> AnalysisResult:
        """
        PREDICT 분석: 시계열 예측

        Args:
            tenant_id: 테넌트 ID
            metric: 예측 지표
            dimension: 그룹화 차원 (선택)
            time_range_days: 학습 데이터 기간
            forecast_periods: 예측 기간
            method: 예측 방법 ("moving_average", "linear_regression")
            granularity: 시간 단위

        Returns:
            AnalysisResult
        """
        logger.info(
            f"PREDICT analysis: metric={metric}, method={method}, "
            f"forecast_periods={forecast_periods}"
        )

        # 과거 데이터 조회
        historical_data = await self._fetch_time_series_data(
            tenant_id=tenant_id,
            metric=metric,
            dimension=dimension,
            time_range_days=time_range_days,
            granularity=granularity,
        )

        if not historical_data:
            return AnalysisResult(
                analysis_type=AnalysisType.PREDICT,
                data=[],
                summary={"error": "데이터 부족"},
                chart_config={},
                insights=["예측에 필요한 과거 데이터가 부족합니다."],
            )

        # 예측 수행
        if method == "moving_average":
            forecast_data, model_info = self._predict_moving_average(
                historical_data, metric, forecast_periods
            )
        else:  # linear_regression
            forecast_data, model_info = self._predict_linear_regression(
                historical_data, metric, forecast_periods
            )

        # 데이터 병합 (과거 + 예측)
        combined_data = historical_data + forecast_data

        # 차트 설정
        chart_config = self._build_predict_chart_config(
            historical_data=historical_data,
            forecast_data=forecast_data,
            metric=metric,
        )

        # 요약
        summary = {
            "historical_periods": len(historical_data),
            "forecast_periods": len(forecast_data),
            "method": method,
            **model_info,
        }

        # 인사이트
        insights = self._generate_predict_insights(
            historical_data=historical_data,
            forecast_data=forecast_data,
            metric=metric,
            model_info=model_info,
        )

        return AnalysisResult(
            analysis_type=AnalysisType.PREDICT,
            data=combined_data,
            summary=summary,
            chart_config=chart_config,
            insights=insights,
            metadata={
                "metric": metric,
                "method": method,
                "forecast_periods": forecast_periods,
                "granularity": granularity.value,
            },
        )

    async def _fetch_time_series_data(
        self,
        tenant_id: UUID,
        metric: str,
        dimension: Optional[str],
        time_range_days: int,
        granularity: TimeGranularity,
    ) -> List[Dict[str, Any]]:
        """시계열 데이터 조회"""
        # 메트릭별 SQL
        metric_expressions = {
            "defect_rate": """
                ROUND(
                    100.0 * SUM(CASE WHEN (output_data->>'is_defect')::boolean = true THEN 1 ELSE 0 END)
                    / NULLIF(COUNT(*), 0),
                    2
                )
            """,
            "production_count": "COUNT(*)",
            "avg_temperature": "ROUND(AVG(value)::numeric, 2)",
            "avg_value": "ROUND(AVG(value)::numeric, 2)",
        }

        # 테이블 결정
        if metric in ["avg_temperature", "avg_value"]:
            table = "core.sensor_data"
            time_column = "recorded_at"
        else:
            table = "core.judgment_executions"
            time_column = "executed_at"

        metric_expr = metric_expressions.get(metric, "COUNT(*)")

        sql = f"""
            SELECT
                DATE_TRUNC('{granularity.value}', {time_column}) AS date,
                {metric_expr} AS {metric}
            FROM {table}
            WHERE
                tenant_id = :tenant_id
                AND {time_column} >= NOW() - INTERVAL '{time_range_days} days'
            GROUP BY DATE_TRUNC('{granularity.value}', {time_column})
            ORDER BY date
        """

        rows = await self._execute_sql(sql, {"tenant_id": str(tenant_id)})

        # datetime을 문자열로 변환
        result = []
        for row in rows:
            date_val = row.get("date")
            if hasattr(date_val, "strftime"):
                date_str = date_val.strftime("%Y-%m-%d")
            else:
                date_str = str(date_val)

            result.append({
                "date": date_str,
                metric: float(row.get(metric, 0) or 0),
                "is_forecast": False,
            })

        return result

    def _predict_moving_average(
        self,
        historical_data: List[Dict[str, Any]],
        metric: str,
        forecast_periods: int,
        window: int = 7,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """이동평균 기반 예측"""
        values = [d.get(metric, 0) for d in historical_data]

        if len(values) < window:
            window = max(1, len(values))

        # 마지막 window 기간의 이동평균
        recent_values = values[-window:]
        moving_avg = sum(recent_values) / len(recent_values)

        # 예측 데이터 생성
        last_date = historical_data[-1]["date"] if historical_data else datetime.now().strftime("%Y-%m-%d")
        forecast_data = []

        for i in range(1, forecast_periods + 1):
            # 날짜 계산
            if isinstance(last_date, str):
                base_date = datetime.strptime(last_date, "%Y-%m-%d")
            else:
                base_date = last_date

            forecast_date = base_date + timedelta(days=i)

            # 약간의 변동 추가 (현실적인 예측)
            variation = moving_avg * 0.05 * ((-1) ** i)  # ±5% 변동
            forecast_value = round(moving_avg + variation, 2)

            forecast_data.append({
                "date": forecast_date.strftime("%Y-%m-%d"),
                metric: forecast_value,
                "is_forecast": True,
            })

        model_info = {
            "model": "moving_average",
            "window": window,
            "base_value": round(moving_avg, 2),
        }

        return forecast_data, model_info

    def _predict_linear_regression(
        self,
        historical_data: List[Dict[str, Any]],
        metric: str,
        forecast_periods: int,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """선형회귀 기반 예측"""
        n = len(historical_data)
        if n < 2:
            return self._predict_moving_average(historical_data, metric, forecast_periods)

        # X: 시간 인덱스, Y: 메트릭 값
        x = list(range(n))
        y = [d.get(metric, 0) for d in historical_data]

        # 선형회귀 계수 계산 (최소제곱법)
        x_mean = sum(x) / n
        y_mean = sum(y) / n

        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            slope = 0
        else:
            slope = numerator / denominator

        intercept = y_mean - slope * x_mean

        # R² 계산
        ss_res = sum((y[i] - (slope * x[i] + intercept)) ** 2 for i in range(n))
        ss_tot = sum((y[i] - y_mean) ** 2 for i in range(n))
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        # 예측 데이터 생성
        last_date = historical_data[-1]["date"]
        forecast_data = []

        for i in range(1, forecast_periods + 1):
            future_x = n + i - 1
            forecast_value = round(slope * future_x + intercept, 2)

            # 음수 방지
            forecast_value = max(0, forecast_value)

            if isinstance(last_date, str):
                base_date = datetime.strptime(last_date, "%Y-%m-%d")
            else:
                base_date = last_date

            forecast_date = base_date + timedelta(days=i)

            forecast_data.append({
                "date": forecast_date.strftime("%Y-%m-%d"),
                metric: forecast_value,
                "is_forecast": True,
            })

        model_info = {
            "model": "linear_regression",
            "slope": round(slope, 4),
            "intercept": round(intercept, 2),
            "r_squared": round(r_squared, 4),
            "trend": "increasing" if slope > 0 else "decreasing" if slope < 0 else "stable",
        }

        return forecast_data, model_info

    def _build_predict_chart_config(
        self,
        historical_data: List[Dict[str, Any]],
        forecast_data: List[Dict[str, Any]],
        metric: str,
    ) -> Dict[str, Any]:
        """예측 차트 설정"""
        return {
            "type": "line",
            "data": historical_data + forecast_data,
            "xAxis": {"dataKey": "date", "label": "날짜"},
            "yAxis": {"label": metric},
            "lines": [
                {"dataKey": metric, "stroke": "#8884d8", "name": "실제값"},
            ],
            "areas": [
                {
                    "dataKey": metric,
                    "fill": "#82ca9d",
                    "fillOpacity": 0.3,
                    "condition": "is_forecast",
                    "name": "예측값",
                }
            ],
            "reference_line": {
                "x": historical_data[-1]["date"] if historical_data else None,
                "label": "예측 시작",
            },
            "analysis_goal": f"{metric} 시계열 예측",
        }

    def _generate_predict_insights(
        self,
        historical_data: List[Dict[str, Any]],
        forecast_data: List[Dict[str, Any]],
        metric: str,
        model_info: Dict[str, Any],
    ) -> List[str]:
        """예측 인사이트 생성"""
        insights = []

        if not historical_data or not forecast_data:
            return ["예측 데이터가 부족합니다."]

        # 현재값 vs 예측값 비교
        current_value = historical_data[-1].get(metric, 0)
        final_forecast = forecast_data[-1].get(metric, 0)

        change_pct = ((final_forecast - current_value) / current_value * 100) if current_value else 0

        if change_pct > 5:
            insights.append(f"{metric}이 향후 {len(forecast_data)}일간 약 {change_pct:.1f}% 증가할 것으로 예측됩니다.")
        elif change_pct < -5:
            insights.append(f"{metric}이 향후 {len(forecast_data)}일간 약 {abs(change_pct):.1f}% 감소할 것으로 예측됩니다.")
        else:
            insights.append(f"{metric}이 향후 {len(forecast_data)}일간 현재 수준을 유지할 것으로 예측됩니다.")

        # 모델 정보
        if model_info.get("model") == "linear_regression":
            trend = model_info.get("trend", "stable")
            r_squared = model_info.get("r_squared", 0)
            trend_kr = {"increasing": "상승", "decreasing": "하락", "stable": "안정"}
            insights.append(f"추세: {trend_kr.get(trend, '안정')} (R²={r_squared:.2f})")

        return insights

    # =========================================
    # WHAT_IF 분석
    # =========================================

    async def analyze_what_if(
        self,
        tenant_id: UUID,
        metric: str,
        dimension: str,
        baseline_value: float,
        scenario_changes: Dict[str, float],  # {"temperature": +5, "production_count": -10}
        time_range_days: int = 30,
    ) -> AnalysisResult:
        """
        WHAT_IF 시뮬레이션: 가정 기반 영향 분석

        Args:
            tenant_id: 테넌트 ID
            metric: 분석 대상 메트릭 (예: "defect_rate")
            dimension: 변경 차원
            baseline_value: 기준 값
            scenario_changes: 변경 시나리오 {"factor": change_amount}
            time_range_days: 기준 데이터 기간

        Returns:
            AnalysisResult
        """
        logger.info(
            f"WHAT_IF analysis: metric={metric}, baseline={baseline_value}, "
            f"changes={scenario_changes}"
        )

        # 과거 데이터 기반 상관관계 분석
        correlation_data = await self._analyze_correlations(
            tenant_id=tenant_id,
            target_metric=metric,
            factors=list(scenario_changes.keys()),
            time_range_days=time_range_days,
        )

        # 시나리오별 영향 계산
        baseline = {"metric": metric, "value": baseline_value}
        scenario_impact = self._calculate_scenario_impact(
            baseline_value=baseline_value,
            scenario_changes=scenario_changes,
            correlations=correlation_data,
        )

        # 비교 데이터
        comparison = {
            "baseline_value": baseline_value,
            "scenario_value": scenario_impact["projected_value"],
            "change_amount": scenario_impact["total_change"],
            "change_percent": scenario_impact["change_percent"],
        }

        # 차트 설정
        chart_config = self._build_what_if_chart_config(
            baseline=baseline,
            scenario_impact=scenario_impact,
            scenario_changes=scenario_changes,
        )

        # 인사이트
        insights = self._generate_what_if_insights(
            metric=metric,
            baseline_value=baseline_value,
            scenario_impact=scenario_impact,
            scenario_changes=scenario_changes,
        )

        return AnalysisResult(
            analysis_type=AnalysisType.WHAT_IF,
            data=[
                {"type": "baseline", **baseline},
                {"type": "scenario", **scenario_impact},
            ],
            summary={
                "baseline": baseline,
                "scenario": scenario_impact,
                "comparison": comparison,
            },
            chart_config=chart_config,
            insights=insights,
            metadata={
                "metric": metric,
                "scenario_changes": scenario_changes,
                "correlations": correlation_data,
            },
        )

    async def _analyze_correlations(
        self,
        tenant_id: UUID,
        target_metric: str,
        factors: List[str],
        time_range_days: int,
    ) -> Dict[str, float]:
        """상관관계 분석 (간단한 규칙 기반)"""
        # 실제로는 DB에서 데이터를 조회하여 상관계수 계산
        # 여기서는 제조 도메인의 일반적인 상관관계를 사용

        default_correlations = {
            # temperature 영향
            ("defect_rate", "temperature"): 0.6,  # 온도 상승 → 불량률 증가
            ("production_count", "temperature"): -0.2,  # 온도 상승 → 생산량 감소

            # production_count 영향
            ("defect_rate", "production_count"): 0.3,  # 생산량 증가 → 불량률 증가 (과부하)

            # pressure 영향
            ("defect_rate", "pressure"): 0.4,
            ("production_count", "pressure"): -0.15,

            # vibration 영향
            ("defect_rate", "vibration"): 0.7,  # 진동 → 불량 강한 상관
        }

        correlations = {}
        for factor in factors:
            key = (target_metric, factor)
            correlations[factor] = default_correlations.get(key, 0.1)

        return correlations

    def _calculate_scenario_impact(
        self,
        baseline_value: float,
        scenario_changes: Dict[str, float],
        correlations: Dict[str, float],
    ) -> Dict[str, Any]:
        """시나리오 영향 계산"""
        total_change = 0
        impact_breakdown = []

        for factor, change_amount in scenario_changes.items():
            correlation = correlations.get(factor, 0.1)

            # 영향 계산: 변화량 * 상관계수 * 기준값의 비율
            impact = change_amount * correlation * (baseline_value / 100)
            total_change += impact

            impact_breakdown.append({
                "factor": factor,
                "change": change_amount,
                "correlation": correlation,
                "impact": round(impact, 2),
            })

        projected_value = max(0, baseline_value + total_change)
        change_percent = (total_change / baseline_value * 100) if baseline_value else 0

        return {
            "metric": "projected_value",
            "value": round(projected_value, 2),
            "projected_value": round(projected_value, 2),
            "total_change": round(total_change, 2),
            "change_percent": round(change_percent, 2),
            "impact_breakdown": impact_breakdown,
        }

    def _build_what_if_chart_config(
        self,
        baseline: Dict[str, Any],
        scenario_impact: Dict[str, Any],
        scenario_changes: Dict[str, float],
    ) -> Dict[str, Any]:
        """What-If 차트 설정"""
        # Bar 차트로 비교
        comparison_data = [
            {"category": "현재", "value": baseline["value"]},
            {"category": "시나리오", "value": scenario_impact["projected_value"]},
        ]

        # 영향 요인별 데이터
        impact_data = scenario_impact.get("impact_breakdown", [])

        return {
            "type": "composed",
            "charts": [
                {
                    "type": "bar",
                    "data": comparison_data,
                    "xAxis": {"dataKey": "category"},
                    "yAxis": {"label": baseline["metric"]},
                    "bars": [{"dataKey": "value", "fill": "#8884d8"}],
                    "title": "기준값 vs 시나리오",
                },
                {
                    "type": "bar",
                    "data": impact_data,
                    "xAxis": {"dataKey": "factor"},
                    "yAxis": {"label": "영향도"},
                    "bars": [{"dataKey": "impact", "fill": "#82ca9d"}],
                    "title": "요인별 영향",
                },
            ],
            "analysis_goal": "What-If 시뮬레이션",
        }

    def _generate_what_if_insights(
        self,
        metric: str,
        baseline_value: float,
        scenario_impact: Dict[str, Any],
        scenario_changes: Dict[str, float],
    ) -> List[str]:
        """What-If 인사이트 생성"""
        insights = []

        projected = scenario_impact["projected_value"]
        change_pct = scenario_impact["change_percent"]

        # 전체 영향
        if change_pct > 0:
            insights.append(
                f"시나리오 적용 시 {metric}이 현재 {baseline_value}에서 "
                f"{projected}로 {change_pct:.1f}% 증가할 것으로 예상됩니다."
            )
        elif change_pct < 0:
            insights.append(
                f"시나리오 적용 시 {metric}이 현재 {baseline_value}에서 "
                f"{projected}로 {abs(change_pct):.1f}% 감소할 것으로 예상됩니다."
            )
        else:
            insights.append(f"시나리오 적용 시 {metric}에 큰 변화가 없을 것으로 예상됩니다.")

        # 가장 영향력 있는 요인
        impact_breakdown = scenario_impact.get("impact_breakdown", [])
        if impact_breakdown:
            sorted_impacts = sorted(impact_breakdown, key=lambda x: abs(x["impact"]), reverse=True)
            top_factor = sorted_impacts[0]
            insights.append(
                f"가장 큰 영향을 미치는 요인은 '{top_factor['factor']}'입니다 "
                f"(영향: {top_factor['impact']:+.2f})"
            )

        return insights

    # =========================================
    # 차트 추천
    # =========================================

    def recommend_chart_type(
        self,
        analysis_type: AnalysisType,
        data_characteristics: Dict[str, Any],
    ) -> ChartType:
        """
        분석 유형과 데이터 특성에 따른 차트 추천

        Args:
            analysis_type: 분석 유형
            data_characteristics: 데이터 특성
                - row_count: 데이터 행 수
                - dimension_count: 차원 수
                - has_time_series: 시계열 여부
                - value_range: 값 범위

        Returns:
            추천 ChartType
        """
        row_count = data_characteristics.get("row_count", 0)
        has_time_series = data_characteristics.get("has_time_series", False)
        dimension_count = data_characteristics.get("dimension_count", 1)

        # 분석 유형별 기본 추천
        type_chart_map = {
            AnalysisType.CHECK: ChartType.GAUGE,
            AnalysisType.TREND: ChartType.LINE,
            AnalysisType.COMPARE: ChartType.BAR,
            AnalysisType.RANK: ChartType.BAR,
            AnalysisType.PREDICT: ChartType.LINE,
            AnalysisType.WHAT_IF: ChartType.BAR,
        }

        base_chart = type_chart_map.get(analysis_type, ChartType.TABLE)

        # 데이터 특성에 따른 조정
        if row_count > 50 and not has_time_series:
            return ChartType.TABLE  # 많은 데이터는 테이블

        if has_time_series and analysis_type in [AnalysisType.TREND, AnalysisType.PREDICT]:
            return ChartType.AREA if dimension_count > 1 else ChartType.LINE

        if dimension_count >= 3:
            return ChartType.SCATTER  # 다차원은 산점도

        return base_chart

    # =========================================
    # 유틸리티
    # =========================================

    @handle_service_errors(resource="SQL query", operation="execute")
    async def _execute_sql(
        self,
        sql: str,
        params: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """SQL 실행 (Decorator로 에러 처리)"""
        async with get_db_context() as db:
            result = await db.execute(text(sql), params)
            rows = result.fetchall()

            # Row를 딕셔너리로 변환
            columns = result.keys()
            return [dict(zip(columns, row)) for row in rows]


# =========================================
# Singleton
# =========================================

_bi_service: Optional[BIService] = None


def get_bi_service() -> BIService:
    """BI Service 싱글톤 반환"""
    global _bi_service
    if _bi_service is None:
        _bi_service = BIService()
    return _bi_service


def reset_bi_service():
    """테스트용: BI Service 리셋"""
    global _bi_service
    _bi_service = None
