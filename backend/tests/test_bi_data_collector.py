"""
BI Data Collector 테스트
bi_data_collector.py의 데이터 수집 레이어 테스트
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import date
from decimal import Decimal
from uuid import uuid4


# ========== 유틸리티 함수 테스트 ==========


class TestConvertDecimal:
    """Decimal 변환 함수 테스트"""

    def test_convert_decimal_value(self):
        """Decimal 값 변환"""
        from app.services.bi_data_collector import _convert_decimal

        result = _convert_decimal(Decimal("123.456"))
        assert isinstance(result, float)
        assert result == 123.456

    def test_convert_decimal_in_dict(self):
        """딕셔너리 내 Decimal 변환"""
        from app.services.bi_data_collector import _convert_decimal

        data = {"amount": Decimal("100.50"), "name": "test"}
        result = _convert_decimal(data)

        assert result["amount"] == 100.50
        assert result["name"] == "test"

    def test_convert_decimal_in_list(self):
        """리스트 내 Decimal 변환"""
        from app.services.bi_data_collector import _convert_decimal

        data = [Decimal("1.1"), Decimal("2.2"), "text"]
        result = _convert_decimal(data)

        assert result[0] == 1.1
        assert result[1] == 2.2
        assert result[2] == "text"

    def test_convert_decimal_non_decimal(self):
        """Decimal이 아닌 값은 그대로"""
        from app.services.bi_data_collector import _convert_decimal

        assert _convert_decimal(42) == 42
        assert _convert_decimal("string") == "string"
        assert _convert_decimal(None) is None


# ========== DEFAULT_THRESHOLDS 테스트 ==========


class TestDefaultThresholds:
    """기본 임계값 설정 테스트"""

    def test_default_thresholds_structure(self):
        """기본 임계값 구조"""
        from app.services.bi_data_collector import DEFAULT_THRESHOLDS

        assert "achievement_rate" in DEFAULT_THRESHOLDS
        assert "defect_rate" in DEFAULT_THRESHOLDS
        assert "yield_rate" in DEFAULT_THRESHOLDS
        assert "downtime_minutes" in DEFAULT_THRESHOLDS
        assert "oee" in DEFAULT_THRESHOLDS

    def test_default_thresholds_values(self):
        """기본 임계값 값"""
        from app.services.bi_data_collector import DEFAULT_THRESHOLDS

        ach = DEFAULT_THRESHOLDS["achievement_rate"]
        assert ach["green"] == 95.0
        assert ach["yellow"] == 80.0
        assert ach["higher_is_better"] is True

        defect = DEFAULT_THRESHOLDS["defect_rate"]
        assert defect["green"] == 2.0
        assert defect["yellow"] == 3.0
        assert defect["higher_is_better"] is False


# ========== BIDataCollector 초기화 테스트 ==========


class TestBIDataCollectorInit:
    """BIDataCollector 초기화 테스트"""

    def test_init(self):
        """초기화"""
        from app.services.bi_data_collector import BIDataCollector

        mock_db = MagicMock()
        tenant_id = uuid4()

        collector = BIDataCollector(db=mock_db, tenant_id=tenant_id)

        assert collector.db == mock_db
        assert collector.tenant_id == tenant_id


# ========== 라인 메타데이터 조회 테스트 ==========


class TestGetLineMetadata:
    """get_line_metadata 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_get_line_metadata_success(self):
        """라인 메타데이터 조회 성공"""
        from app.services.bi_data_collector import BIDataCollector

        mock_db = AsyncMock()

        mock_row = MagicMock()
        mock_row.line_code = "LINE-A"
        mock_row.name = "라인 A"
        mock_row.category = "assembly"
        mock_row.capacity_per_hour = Decimal("100.0")
        mock_row.capacity_unit = "EA"
        mock_row.plant_code = "PLANT1"
        mock_row.department = "생산1팀"
        mock_row.daily_target = 800
        mock_row.target_oee = Decimal("85.0")
        mock_row.attributes = {"shift": 2}

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute = AsyncMock(return_value=mock_result)

        collector = BIDataCollector(db=mock_db, tenant_id=uuid4())

        result = await collector.get_line_metadata()

        assert len(result) == 1
        assert result[0]["line_code"] == "LINE-A"
        assert result[0]["name"] == "라인 A"
        assert result[0]["capacity_per_hour"] == 100.0

    @pytest.mark.asyncio
    async def test_get_line_metadata_empty(self):
        """라인 메타데이터 없음"""
        from app.services.bi_data_collector import BIDataCollector

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        collector = BIDataCollector(db=mock_db, tenant_id=uuid4())

        result = await collector.get_line_metadata()

        assert len(result) == 0


# ========== KPI Threshold 조회 테스트 ==========


class TestGetKpiThresholds:
    """get_kpi_thresholds 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_get_kpi_thresholds_default(self):
        """기본 임계값 반환"""
        from app.services.bi_data_collector import BIDataCollector, DEFAULT_THRESHOLDS

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        collector = BIDataCollector(db=mock_db, tenant_id=uuid4())

        result = await collector.get_kpi_thresholds()

        # 기본값이 반환되어야 함
        assert "achievement_rate" in result
        assert result["achievement_rate"]["green"] == DEFAULT_THRESHOLDS["achievement_rate"]["green"]

    @pytest.mark.asyncio
    async def test_get_kpi_thresholds_custom(self):
        """커스텀 임계값 반환"""
        from app.services.bi_data_collector import BIDataCollector

        mock_db = AsyncMock()

        mock_row = MagicMock()
        mock_row.kpi_code = "custom_kpi"
        mock_row.name = "커스텀 KPI"
        mock_row.category = "production"
        mock_row.unit = "%"
        mock_row.default_target = Decimal("90.0")
        mock_row.green_threshold = Decimal("92.0")
        mock_row.yellow_threshold = Decimal("85.0")
        mock_row.red_threshold = Decimal("70.0")
        mock_row.higher_is_better = True

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute = AsyncMock(return_value=mock_result)

        collector = BIDataCollector(db=mock_db, tenant_id=uuid4())

        result = await collector.get_kpi_thresholds()

        assert "custom_kpi" in result
        assert result["custom_kpi"]["name"] == "커스텀 KPI"
        assert result["custom_kpi"]["green"] == 92.0


# ========== 생산 현황 조회 테스트 ==========


class TestGetProductionSummary:
    """get_production_summary 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_get_production_summary_success(self):
        """생산 현황 조회 성공"""
        from app.services.bi_data_collector import BIDataCollector

        mock_db = AsyncMock()

        mock_row = MagicMock()
        mock_row.line_code = "LINE-A"
        mock_row.line_name = "라인 A"
        mock_row.daily_target = 1000
        mock_row.actual_qty = Decimal("950")
        mock_row.good_qty = Decimal("930")
        mock_row.defect_qty = Decimal("20")
        mock_row.rework_qty = Decimal("10")
        mock_row.scrap_qty = Decimal("10")
        mock_row.runtime_min = Decimal("450")
        mock_row.downtime_min = Decimal("30")
        mock_row.setup_min = Decimal("20")
        mock_row.avg_cycle_time = Decimal("28.5")
        mock_row.yield_rate = Decimal("97.9")
        mock_row.defect_rate = Decimal("2.1")
        mock_row.achievement_rate = Decimal("95.0")

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute = AsyncMock(return_value=mock_result)

        collector = BIDataCollector(db=mock_db, tenant_id=uuid4())

        result = await collector.get_production_summary(date(2024, 1, 15))

        assert len(result) == 1
        assert result[0]["line_code"] == "LINE-A"
        assert result[0]["actual_qty"] == 950.0
        assert result[0]["achievement_rate"] == 95.0

    @pytest.mark.asyncio
    async def test_get_production_summary_with_line_filter(self):
        """라인 필터로 생산 현황 조회"""
        from app.services.bi_data_collector import BIDataCollector

        mock_db = AsyncMock()

        mock_row = MagicMock()
        mock_row.line_code = "LINE-B"
        mock_row.line_name = "라인 B"
        mock_row.daily_target = 800
        mock_row.actual_qty = Decimal("750")
        mock_row.good_qty = Decimal("740")
        mock_row.defect_qty = Decimal("10")
        mock_row.rework_qty = Decimal("5")
        mock_row.scrap_qty = Decimal("5")
        mock_row.runtime_min = Decimal("420")
        mock_row.downtime_min = Decimal("60")
        mock_row.setup_min = Decimal("15")
        mock_row.avg_cycle_time = Decimal("30.0")
        mock_row.yield_rate = Decimal("98.7")
        mock_row.defect_rate = Decimal("1.3")
        mock_row.achievement_rate = Decimal("93.8")

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute = AsyncMock(return_value=mock_result)

        collector = BIDataCollector(db=mock_db, tenant_id=uuid4())

        result = await collector.get_production_summary(line_code="LINE-B")

        assert len(result) == 1
        assert result[0]["line_code"] == "LINE-B"


# ========== 불량 현황 조회 테스트 ==========


class TestGetDefectSummary:
    """get_defect_summary 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_get_defect_summary_success(self):
        """불량 현황 조회 성공"""
        from app.services.bi_data_collector import BIDataCollector

        mock_db = AsyncMock()

        mock_row = MagicMock()
        mock_row.line_code = "LINE-A"
        mock_row.defect_type = "외관불량"
        mock_row.total_defect_qty = Decimal("50")
        mock_row.total_defect_cost = Decimal("25000")
        mock_row.affected_products = 3
        mock_row.root_causes = ["작업자 실수", "원자재 불량"]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute = AsyncMock(return_value=mock_result)

        collector = BIDataCollector(db=mock_db, tenant_id=uuid4())

        result = await collector.get_defect_summary(date(2024, 1, 15))

        assert len(result) == 1
        assert result[0]["defect_type"] == "외관불량"
        assert result[0]["total_defect_qty"] == 50.0
        assert len(result[0]["root_causes"]) == 2

    @pytest.mark.asyncio
    async def test_get_defect_summary_no_root_causes(self):
        """원인 없는 불량 현황"""
        from app.services.bi_data_collector import BIDataCollector

        mock_db = AsyncMock()

        mock_row = MagicMock()
        mock_row.line_code = "LINE-A"
        mock_row.defect_type = "치수불량"
        mock_row.total_defect_qty = Decimal("20")
        mock_row.total_defect_cost = Decimal("10000")
        mock_row.affected_products = 1
        mock_row.root_causes = None

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute = AsyncMock(return_value=mock_result)

        collector = BIDataCollector(db=mock_db, tenant_id=uuid4())

        result = await collector.get_defect_summary()

        assert result[0]["root_causes"] == []


# ========== 비가동 현황 조회 테스트 ==========


class TestGetDowntimeSummary:
    """get_downtime_summary 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_get_downtime_summary_success(self):
        """비가동 현황 조회 성공"""
        from app.services.bi_data_collector import BIDataCollector

        mock_db = AsyncMock()

        mock_row = MagicMock()
        mock_row.line_code = "LINE-A"
        mock_row.equipment_code = "EQ001"
        mock_row.equipment_name = "설비1"
        mock_row.event_type = "breakdown"
        mock_row.total_events = 3
        mock_row.total_duration_min = Decimal("90")
        mock_row.avg_duration_min = Decimal("30")
        mock_row.max_duration_min = Decimal("45")
        mock_row.severity_distribution = {"critical": 1, "warning": 2}

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute = AsyncMock(return_value=mock_result)

        collector = BIDataCollector(db=mock_db, tenant_id=uuid4())

        result = await collector.get_downtime_summary(date(2024, 1, 15))

        assert len(result) == 1
        assert result[0]["equipment_code"] == "EQ001"
        assert result[0]["total_duration_min"] == 90.0
        assert result[0]["event_type"] == "breakdown"


# ========== 비교 데이터 조회 테스트 ==========


class TestGetComparisonData:
    """get_comparison_data 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_get_comparison_data_success(self):
        """비교 데이터 조회 성공"""
        from app.services.bi_data_collector import BIDataCollector

        mock_db = AsyncMock()

        mock_row = MagicMock()
        mock_row.line_code = "LINE-A"
        mock_row.today_qty = Decimal("1000")
        mock_row.yesterday_qty = Decimal("900")
        mock_row.lastweek_qty = Decimal("950")
        mock_row.vs_yesterday_pct = Decimal("11.1")
        mock_row.vs_lastweek_pct = Decimal("5.3")
        mock_row.today_downtime = Decimal("30")
        mock_row.yesterday_downtime = Decimal("45")

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute = AsyncMock(return_value=mock_result)

        collector = BIDataCollector(db=mock_db, tenant_id=uuid4())

        result = await collector.get_comparison_data(date(2024, 1, 15))

        assert "by_line" in result
        assert "total" in result
        assert "LINE-A" in result["by_line"]
        assert result["by_line"]["LINE-A"]["vs_yesterday_pct"] == 11.1

    @pytest.mark.asyncio
    async def test_get_comparison_data_empty(self):
        """비교 데이터 없음"""
        from app.services.bi_data_collector import BIDataCollector

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        collector = BIDataCollector(db=mock_db, tenant_id=uuid4())

        result = await collector.get_comparison_data()

        assert result["by_line"] == {}
        assert result["total"]["today_qty"] == 0


# ========== 추이 데이터 조회 테스트 ==========


class TestGetTrendData:
    """get_trend_data 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_get_trend_data_success(self):
        """추이 데이터 조회 성공"""
        from app.services.bi_data_collector import BIDataCollector

        mock_db = AsyncMock()

        mock_rows = []
        for i in range(7):
            row = MagicMock()
            row.date = date(2024, 1, 9 + i)
            row.total_qty = Decimal("1000") + i * 10
            row.good_qty = Decimal("980") + i * 10
            row.defect_qty = Decimal("20")
            row.downtime_min = Decimal("30")
            row.yield_rate = Decimal("98.0")
            row.defect_rate = Decimal("2.0")
            mock_rows.append(row)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows
        mock_db.execute = AsyncMock(return_value=mock_result)

        collector = BIDataCollector(db=mock_db, tenant_id=uuid4())

        result = await collector.get_trend_data(days=7, end_date=date(2024, 1, 15))

        assert len(result) == 7
        assert result[0]["date"] == "2024-01-09"
        assert result[6]["date"] == "2024-01-15"


# ========== 종합 컨텍스트 수집 테스트 ==========


class TestCollectInsightContext:
    """collect_insight_context 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_collect_insight_context_full(self):
        """전체 컨텍스트 수집"""
        from app.services.bi_data_collector import BIDataCollector

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        collector = BIDataCollector(db=mock_db, tenant_id=uuid4())

        result = await collector.collect_insight_context(
            target_date=date(2024, 1, 15),
            include_trends=True
        )

        assert "target_date" in result
        assert result["target_date"] == "2024-01-15"
        assert "thresholds" in result
        assert "line_metadata" in result
        assert "production_data" in result
        assert "defect_data" in result
        assert "downtime_data" in result
        assert "comparison" in result
        assert "trend_data" in result

    @pytest.mark.asyncio
    async def test_collect_insight_context_without_trends(self):
        """추이 데이터 제외 컨텍스트 수집"""
        from app.services.bi_data_collector import BIDataCollector

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        collector = BIDataCollector(db=mock_db, tenant_id=uuid4())

        result = await collector.collect_insight_context(
            target_date=date(2024, 1, 15),
            include_trends=False
        )

        assert "trend_data" not in result

    @pytest.mark.asyncio
    async def test_collect_insight_context_with_line_filter(self):
        """라인 필터로 컨텍스트 수집"""
        from app.services.bi_data_collector import BIDataCollector

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        collector = BIDataCollector(db=mock_db, tenant_id=uuid4())

        result = await collector.collect_insight_context(
            line_code="LINE-A",
            include_trends=False
        )

        assert result["line_filter"] == "LINE-A"


# ========== ThresholdEvaluator 테스트 ==========


class TestThresholdEvaluatorInit:
    """ThresholdEvaluator 초기화 테스트"""

    def test_init(self):
        """초기화"""
        from app.services.bi_data_collector import ThresholdEvaluator

        thresholds = {"achievement_rate": {"green": 95.0, "yellow": 80.0}}
        evaluator = ThresholdEvaluator(thresholds)

        assert evaluator.thresholds == thresholds


class TestThresholdEvaluatorEvaluate:
    """ThresholdEvaluator.evaluate 메서드 테스트"""

    @pytest.fixture
    def evaluator(self):
        from app.services.bi_data_collector import ThresholdEvaluator

        thresholds = {
            "achievement_rate": {"green": 95.0, "yellow": 80.0, "higher_is_better": True},
            "defect_rate": {"green": 2.0, "yellow": 3.0, "higher_is_better": False},
        }
        return ThresholdEvaluator(thresholds)

    def test_evaluate_normal_higher_is_better(self, evaluator):
        """정상 상태 - 높을수록 좋음"""
        assert evaluator.evaluate("achievement_rate", 98.0) == "normal"

    def test_evaluate_warning_higher_is_better(self, evaluator):
        """경고 상태 - 높을수록 좋음"""
        assert evaluator.evaluate("achievement_rate", 85.0) == "warning"

    def test_evaluate_critical_higher_is_better(self, evaluator):
        """위험 상태 - 높을수록 좋음"""
        assert evaluator.evaluate("achievement_rate", 70.0) == "critical"

    def test_evaluate_normal_lower_is_better(self, evaluator):
        """정상 상태 - 낮을수록 좋음"""
        assert evaluator.evaluate("defect_rate", 1.5) == "normal"

    def test_evaluate_warning_lower_is_better(self, evaluator):
        """경고 상태 - 낮을수록 좋음"""
        assert evaluator.evaluate("defect_rate", 2.5) == "warning"

    def test_evaluate_critical_lower_is_better(self, evaluator):
        """위험 상태 - 낮을수록 좋음"""
        assert evaluator.evaluate("defect_rate", 4.0) == "critical"

    def test_evaluate_unknown_kpi(self, evaluator):
        """알 수 없는 KPI"""
        assert evaluator.evaluate("unknown_kpi", 50.0) == "normal"

    def test_evaluate_missing_thresholds(self):
        """임계값 없는 KPI"""
        from app.services.bi_data_collector import ThresholdEvaluator

        evaluator = ThresholdEvaluator({"partial": {"green": None, "yellow": None}})
        assert evaluator.evaluate("partial", 50.0) == "normal"

    def test_evaluate_boundary_values_higher_is_better(self, evaluator):
        """경계값 테스트 - 높을수록 좋음"""
        assert evaluator.evaluate("achievement_rate", 95.0) == "normal"  # == green
        assert evaluator.evaluate("achievement_rate", 80.0) == "warning"  # == yellow

    def test_evaluate_boundary_values_lower_is_better(self, evaluator):
        """경계값 테스트 - 낮을수록 좋음"""
        assert evaluator.evaluate("defect_rate", 2.0) == "normal"  # == green
        assert evaluator.evaluate("defect_rate", 3.0) == "warning"  # == yellow


class TestThresholdEvaluatorGetStatusEmoji:
    """ThresholdEvaluator.get_status_emoji 메서드 테스트"""

    @pytest.fixture
    def evaluator(self):
        from app.services.bi_data_collector import ThresholdEvaluator
        return ThresholdEvaluator({})

    def test_get_status_emoji_normal(self, evaluator):
        """정상 이모지"""
        assert evaluator.get_status_emoji("normal") == "✅"

    def test_get_status_emoji_warning(self, evaluator):
        """경고 이모지"""
        assert evaluator.get_status_emoji("warning") == "⚠️"

    def test_get_status_emoji_critical(self, evaluator):
        """위험 이모지"""
        assert evaluator.get_status_emoji("critical") == "🚨"

    def test_get_status_emoji_unknown(self, evaluator):
        """알 수 없는 상태 이모지"""
        assert evaluator.get_status_emoji("unknown") == "❓"
