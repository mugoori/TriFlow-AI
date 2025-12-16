"""
BI Service 테스트 (V2 Phase 2)
================================
- RANK 분석 테스트
- PREDICT 분석 테스트
- WHAT_IF 시뮬레이션 테스트
- 차트 추천 테스트
"""
import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from app.services.bi_service import (
    AnalysisType,
    ChartType,
    TimeGranularity,
    AnalysisPlan,
    AnalysisResult,
    get_bi_service,
    reset_bi_service,
)


# =========================================
# Fixtures
# =========================================

@pytest.fixture
def bi_service():
    """BIService 인스턴스"""
    reset_bi_service()
    return get_bi_service()


@pytest.fixture
def tenant_id():
    """테스트용 테넌트 ID"""
    return uuid4()


@pytest.fixture
def mock_time_series_data():
    """Mock 시계열 데이터"""
    base_date = datetime.now() - timedelta(days=30)
    return [
        {
            "date": (base_date + timedelta(days=i)).strftime("%Y-%m-%d"),
            "defect_rate": 2.0 + (i * 0.1) + ((-1) ** i * 0.3),  # 증가 추세 + 노이즈
            "is_forecast": False,
        }
        for i in range(30)
    ]


@pytest.fixture
def mock_rank_data():
    """Mock RANK 데이터"""
    return [
        {"rank": 1, "line_code": "LINE_A", "defect_rate": 5.2, "total_count": 1000},
        {"rank": 2, "line_code": "LINE_B", "defect_rate": 4.1, "total_count": 950},
        {"rank": 3, "line_code": "LINE_C", "defect_rate": 3.5, "total_count": 1100},
        {"rank": 4, "line_code": "LINE_D", "defect_rate": 2.8, "total_count": 900},
        {"rank": 5, "line_code": "LINE_E", "defect_rate": 2.1, "total_count": 1050},
    ]


# =========================================
# Unit Tests: BIService Methods
# =========================================

class TestBIServicePercentileCalculation:
    """백분위 계산 테스트"""

    def test_calculate_percentiles_basic(self, bi_service, mock_rank_data):
        """기본 백분위 계산"""
        result = bi_service._calculate_percentiles(mock_rank_data, "defect_rate")

        assert len(result) == 5
        # 모든 항목에 percentile 필드가 추가되어야 함
        for item in result:
            assert "percentile" in item
            assert 0 <= item["percentile"] <= 100

    def test_calculate_percentiles_highest(self, bi_service, mock_rank_data):
        """최고값 백분위는 100%에 가까워야 함"""
        result = bi_service._calculate_percentiles(mock_rank_data, "defect_rate")

        # defect_rate가 가장 높은 LINE_A
        line_a = next(r for r in result if r["line_code"] == "LINE_A")
        assert line_a["percentile"] == 100.0

    def test_calculate_percentiles_lowest(self, bi_service, mock_rank_data):
        """최저값 백분위는 20%에 가까워야 함 (5개 중 1개)"""
        result = bi_service._calculate_percentiles(mock_rank_data, "defect_rate")

        # defect_rate가 가장 낮은 LINE_E
        line_e = next(r for r in result if r["line_code"] == "LINE_E")
        assert line_e["percentile"] == 20.0

    def test_calculate_percentiles_empty(self, bi_service):
        """빈 데이터 처리"""
        result = bi_service._calculate_percentiles([], "defect_rate")
        assert result == []


class TestBIServiceRankSummary:
    """RANK 분석 요약 테스트"""

    def test_rank_summary_basic(self, bi_service, mock_rank_data):
        """기본 요약 통계"""
        summary = bi_service._calculate_rank_summary(mock_rank_data, "defect_rate", "desc")

        assert summary["total_items"] == 5
        assert summary["top_value"] == 5.2
        assert summary["bottom_value"] == 2.1
        assert summary["analysis_direction"] == "highest"
        assert summary["top_item"]["line_code"] == "LINE_A"

    def test_rank_summary_empty(self, bi_service):
        """빈 데이터 요약"""
        summary = bi_service._calculate_rank_summary([], "defect_rate", "desc")
        assert summary["total_items"] == 0


class TestBIServiceRankInsights:
    """RANK 분석 인사이트 테스트"""

    def test_rank_insights_top(self, bi_service, mock_rank_data):
        """상위 항목 인사이트 생성"""
        # 백분위 추가
        data_with_percentile = bi_service._calculate_percentiles(mock_rank_data, "defect_rate")
        insights = bi_service._generate_rank_insights(
            data_with_percentile, "defect_rate", "line_code", "desc"
        )

        assert len(insights) >= 1
        assert "LINE_A" in insights[0]
        assert "높은" in insights[0]

    def test_rank_insights_empty(self, bi_service):
        """빈 데이터 인사이트"""
        insights = bi_service._generate_rank_insights([], "defect_rate", "line_code", "desc")
        assert "데이터가 없습니다" in insights[0]


class TestBIServicePredictMovingAverage:
    """이동평균 예측 테스트"""

    def test_moving_average_basic(self, bi_service, mock_time_series_data):
        """기본 이동평균 예측"""
        forecast_data, model_info = bi_service._predict_moving_average(
            mock_time_series_data, "defect_rate", forecast_periods=7
        )

        assert len(forecast_data) == 7
        assert model_info["model"] == "moving_average"
        assert model_info["window"] == 7
        assert "base_value" in model_info

        # 모든 예측값에 is_forecast=True
        for item in forecast_data:
            assert item["is_forecast"] is True
            assert "date" in item
            assert "defect_rate" in item

    def test_moving_average_short_data(self, bi_service):
        """짧은 데이터 이동평균"""
        short_data = [
            {"date": "2024-01-01", "defect_rate": 2.5, "is_forecast": False},
            {"date": "2024-01-02", "defect_rate": 2.7, "is_forecast": False},
        ]
        forecast_data, model_info = bi_service._predict_moving_average(
            short_data, "defect_rate", forecast_periods=3, window=7
        )

        # 데이터가 window보다 작으면 window 조정
        assert model_info["window"] == 2
        assert len(forecast_data) == 3


class TestBIServicePredictLinearRegression:
    """선형회귀 예측 테스트"""

    def test_linear_regression_increasing(self, bi_service, mock_time_series_data):
        """증가 추세 선형회귀"""
        forecast_data, model_info = bi_service._predict_linear_regression(
            mock_time_series_data, "defect_rate", forecast_periods=7
        )

        assert len(forecast_data) == 7
        assert model_info["model"] == "linear_regression"
        assert "slope" in model_info
        assert "intercept" in model_info
        assert "r_squared" in model_info
        assert model_info["trend"] == "increasing"  # mock 데이터는 증가 추세

    def test_linear_regression_r_squared(self, bi_service, mock_time_series_data):
        """R² 값 범위 확인"""
        _, model_info = bi_service._predict_linear_regression(
            mock_time_series_data, "defect_rate", forecast_periods=7
        )

        assert 0 <= model_info["r_squared"] <= 1

    def test_linear_regression_single_point(self, bi_service):
        """단일 데이터 처리 (fallback to moving average)"""
        single_data = [{"date": "2024-01-01", "defect_rate": 2.5, "is_forecast": False}]
        forecast_data, model_info = bi_service._predict_linear_regression(
            single_data, "defect_rate", forecast_periods=3
        )

        # 데이터가 2개 미만이면 이동평균으로 fallback
        assert model_info["model"] == "moving_average"


class TestBIServiceWhatIfImpact:
    """What-If 영향 계산 테스트"""

    def test_scenario_impact_single_factor(self, bi_service):
        """단일 요인 영향"""
        baseline = 2.5
        changes = {"temperature": 5}
        correlations = {"temperature": 0.6}

        impact = bi_service._calculate_scenario_impact(baseline, changes, correlations)

        assert "projected_value" in impact
        assert "total_change" in impact
        assert "change_percent" in impact
        assert len(impact["impact_breakdown"]) == 1

    def test_scenario_impact_multiple_factors(self, bi_service):
        """다중 요인 영향"""
        baseline = 2.5
        changes = {"temperature": 5, "pressure": -10, "vibration": 2}
        correlations = {"temperature": 0.6, "pressure": 0.4, "vibration": 0.7}

        impact = bi_service._calculate_scenario_impact(baseline, changes, correlations)

        assert len(impact["impact_breakdown"]) == 3
        # 각 요인별 영향 확인
        temp_impact = next(i for i in impact["impact_breakdown"] if i["factor"] == "temperature")
        assert temp_impact["change"] == 5
        assert temp_impact["correlation"] == 0.6

    def test_scenario_impact_no_negative(self, bi_service):
        """예측값은 음수가 되지 않음"""
        baseline = 1.0
        changes = {"temperature": -100}  # 큰 감소
        correlations = {"temperature": 0.9}

        impact = bi_service._calculate_scenario_impact(baseline, changes, correlations)

        assert impact["projected_value"] >= 0


class TestBIServiceChartRecommendation:
    """차트 추천 테스트"""

    def test_recommend_chart_trend(self, bi_service):
        """TREND 분석 차트 추천"""
        chart = bi_service.recommend_chart_type(
            AnalysisType.TREND,
            {"row_count": 30, "has_time_series": True, "dimension_count": 1}
        )
        assert chart == ChartType.LINE

    def test_recommend_chart_rank(self, bi_service):
        """RANK 분석 차트 추천"""
        chart = bi_service.recommend_chart_type(
            AnalysisType.RANK,
            {"row_count": 5, "has_time_series": False, "dimension_count": 1}
        )
        assert chart == ChartType.BAR

    def test_recommend_chart_predict(self, bi_service):
        """PREDICT 분석 차트 추천"""
        chart = bi_service.recommend_chart_type(
            AnalysisType.PREDICT,
            {"row_count": 37, "has_time_series": True, "dimension_count": 1}
        )
        assert chart == ChartType.LINE

    def test_recommend_chart_what_if(self, bi_service):
        """WHAT_IF 분석 차트 추천"""
        chart = bi_service.recommend_chart_type(
            AnalysisType.WHAT_IF,
            {"row_count": 2, "has_time_series": False, "dimension_count": 2}
        )
        assert chart == ChartType.BAR

    def test_recommend_chart_large_data(self, bi_service):
        """대량 데이터는 테이블 추천"""
        chart = bi_service.recommend_chart_type(
            AnalysisType.COMPARE,
            {"row_count": 100, "has_time_series": False, "dimension_count": 1}
        )
        assert chart == ChartType.TABLE

    def test_recommend_chart_multidimensional(self, bi_service):
        """다차원 데이터는 산점도 추천"""
        chart = bi_service.recommend_chart_type(
            AnalysisType.COMPARE,
            {"row_count": 20, "has_time_series": False, "dimension_count": 3}
        )
        assert chart == ChartType.SCATTER


class TestBIServicePredictChartConfig:
    """예측 차트 설정 테스트"""

    def test_predict_chart_config(self, bi_service, mock_time_series_data):
        """예측 차트 설정 생성"""
        forecast_data = [
            {"date": "2024-12-01", "defect_rate": 3.0, "is_forecast": True},
            {"date": "2024-12-02", "defect_rate": 3.1, "is_forecast": True},
        ]
        config = bi_service._build_predict_chart_config(
            mock_time_series_data, forecast_data, "defect_rate"
        )

        assert config["type"] == "line"
        assert "xAxis" in config
        assert "yAxis" in config
        assert "reference_line" in config


class TestBIServicePredictInsights:
    """예측 인사이트 테스트"""

    def test_predict_insights_increasing(self, bi_service, mock_time_series_data):
        """증가 추세 인사이트"""
        forecast_data = [
            {"date": "2024-12-01", "defect_rate": 5.5, "is_forecast": True},  # 마지막 과거값보다 높음
        ]
        model_info = {"model": "linear_regression", "trend": "increasing", "r_squared": 0.85}

        insights = bi_service._generate_predict_insights(
            mock_time_series_data, forecast_data, "defect_rate", model_info
        )

        assert len(insights) >= 1
        # 증가 관련 인사이트
        assert any("증가" in i or "상승" in i for i in insights)


# =========================================
# Integration Tests
# =========================================

class TestBIServiceRankSQL:
    """RANK SQL 생성 테스트"""

    def test_build_rank_sql_defect_rate(self, bi_service, tenant_id):
        """불량률 RANK SQL"""
        sql, params = bi_service._build_rank_sql(
            tenant_id=tenant_id,
            metric="defect_rate",
            dimension="line_code",
            limit=5,
            order="desc",
            time_range_days=7,
            filters=None,
        )

        assert "SELECT" in sql
        assert "tenant_id" in sql
        assert "line_code" in sql
        assert "defect_rate" in sql
        assert "ROW_NUMBER()" in sql
        assert str(tenant_id) == params["tenant_id"]

    def test_build_rank_sql_sensor_metric(self, bi_service, tenant_id):
        """센서 메트릭 RANK SQL"""
        sql, params = bi_service._build_rank_sql(
            tenant_id=tenant_id,
            metric="avg_temperature",
            dimension="sensor_type",
            limit=10,
            order="asc",
            time_range_days=30,
            filters=None,
        )

        assert "sensor_data" in sql  # 센서 데이터 테이블 사용
        assert "ASC" in sql  # 하위 순위


# =========================================
# Singleton Tests
# =========================================

class TestBIServiceSingleton:
    """싱글톤 패턴 테스트"""

    def test_singleton_same_instance(self):
        """동일 인스턴스 반환"""
        reset_bi_service()
        service1 = get_bi_service()
        service2 = get_bi_service()

        assert service1 is service2

    def test_singleton_reset(self):
        """리셋 후 새 인스턴스"""
        service1 = get_bi_service()
        reset_bi_service()
        service2 = get_bi_service()

        assert service1 is not service2


# =========================================
# Data Classes Tests
# =========================================

class TestDataClasses:
    """데이터 클래스 테스트"""

    def test_analysis_plan_defaults(self):
        """AnalysisPlan 기본값"""
        plan = AnalysisPlan(
            query_text="불량률 순위",
            analysis_type=AnalysisType.RANK,
            metrics=[{"name": "defect_rate", "aggregation": "avg"}],
            dimensions=["line_code"],
            filters=[],
            time_range={"days": 7},
        )

        assert plan.granularity == TimeGranularity.DAY
        assert plan.chart_type == ChartType.LINE
        assert plan.rank_limit == 5
        assert plan.rank_order == "desc"

    def test_analysis_result_structure(self):
        """AnalysisResult 구조"""
        result = AnalysisResult(
            analysis_type=AnalysisType.RANK,
            data=[{"line_code": "A", "defect_rate": 5.0}],
            summary={"total_items": 1},
            chart_config={"type": "bar"},
            insights=["LINE_A has highest defect rate"],
        )

        assert result.analysis_type == AnalysisType.RANK
        assert len(result.data) == 1
        assert result.metadata == {}  # 기본값


# =========================================
# Enum Tests
# =========================================

class TestEnums:
    """Enum 테스트"""

    def test_analysis_type_values(self):
        """AnalysisType 값"""
        assert AnalysisType.CHECK.value == "check"
        assert AnalysisType.RANK.value == "rank"
        assert AnalysisType.PREDICT.value == "predict"
        assert AnalysisType.WHAT_IF.value == "what_if"

    def test_chart_type_values(self):
        """ChartType 값"""
        assert ChartType.LINE.value == "line"
        assert ChartType.BAR.value == "bar"
        assert ChartType.GAUGE.value == "gauge"

    def test_time_granularity_values(self):
        """TimeGranularity 값"""
        assert TimeGranularity.MINUTE.value == "minute"
        assert TimeGranularity.HOUR.value == "hour"
        assert TimeGranularity.DAY.value == "day"
        assert TimeGranularity.WEEK.value == "week"
        assert TimeGranularity.MONTH.value == "month"
