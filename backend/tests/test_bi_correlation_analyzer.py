"""
BI Correlation Analyzer 테스트
bi_correlation_analyzer.py의 연관 분석 엔진 테스트
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
        from app.services.bi_correlation_analyzer import _convert_decimal

        result = _convert_decimal(Decimal("123.456"))
        assert isinstance(result, float)
        assert result == 123.456

    def test_convert_decimal_in_dict(self):
        """딕셔너리 내 Decimal 변환"""
        from app.services.bi_correlation_analyzer import _convert_decimal

        data = {
            "amount": Decimal("100.50"),
            "rate": Decimal("0.05"),
            "name": "test"
        }
        result = _convert_decimal(data)

        assert result["amount"] == 100.50
        assert result["rate"] == 0.05
        assert result["name"] == "test"

    def test_convert_decimal_in_list(self):
        """리스트 내 Decimal 변환"""
        from app.services.bi_correlation_analyzer import _convert_decimal

        data = [Decimal("1.1"), Decimal("2.2"), "text"]
        result = _convert_decimal(data)

        assert result[0] == 1.1
        assert result[1] == 2.2
        assert result[2] == "text"

    def test_convert_decimal_nested(self):
        """중첩 구조 Decimal 변환"""
        from app.services.bi_correlation_analyzer import _convert_decimal

        data = {
            "items": [
                {"value": Decimal("10.0")},
                {"value": Decimal("20.0")}
            ],
            "total": Decimal("30.0")
        }
        result = _convert_decimal(data)

        assert result["items"][0]["value"] == 10.0
        assert result["items"][1]["value"] == 20.0
        assert result["total"] == 30.0

    def test_convert_decimal_non_decimal(self):
        """Decimal이 아닌 값은 그대로"""
        from app.services.bi_correlation_analyzer import _convert_decimal

        assert _convert_decimal(42) == 42
        assert _convert_decimal("string") == "string"
        assert _convert_decimal(None) is None


# ========== AnalysisTrigger 테스트 ==========


class TestAnalysisTrigger:
    """AnalysisTrigger 데이터클래스 테스트"""

    def test_trigger_creation(self):
        """트리거 생성"""
        from app.services.bi_correlation_analyzer import AnalysisTrigger

        trigger = AnalysisTrigger(
            trigger_type="low_achievement",
            severity="warning",
            affected_line="LINE-A",
            metric_name="달성률",
            metric_value=75.0,
            threshold_value=80.0,
            message="LINE-A 라인 달성률 75.0% (목표 80.0% 미달)"
        )

        assert trigger.trigger_type == "low_achievement"
        assert trigger.severity == "warning"
        assert trigger.affected_line == "LINE-A"
        assert trigger.metric_value == 75.0


# ========== CorrelationAnalyzer 초기화 테스트 ==========


class TestCorrelationAnalyzerInit:
    """CorrelationAnalyzer 초기화 테스트"""

    def test_init(self):
        """초기화"""
        from app.services.bi_correlation_analyzer import CorrelationAnalyzer

        mock_db = MagicMock()
        tenant_id = uuid4()

        analyzer = CorrelationAnalyzer(db=mock_db, tenant_id=tenant_id)

        assert analyzer.db == mock_db
        assert analyzer.tenant_id == tenant_id


# ========== 트리거 감지 테스트 ==========


class TestDetectTriggers:
    """detect_triggers 메서드 테스트"""

    @pytest.fixture
    def analyzer(self):
        from app.services.bi_correlation_analyzer import CorrelationAnalyzer
        return CorrelationAnalyzer(db=MagicMock(), tenant_id=uuid4())

    @pytest.fixture
    def default_thresholds(self):
        return {
            "achievement_rate": {"green": 95.0, "yellow": 80.0},
            "defect_rate": {"green": 2.0, "yellow": 3.0},
            "downtime_minutes": {"green": 30.0, "yellow": 60.0}
        }

    def test_detect_low_achievement_warning(self, analyzer, default_thresholds):
        """낮은 달성률 경고 감지"""
        production_data = [
            {"line_code": "LINE-A", "achievement_rate": 75.0, "defect_rate": 1.0, "downtime_min": 20}
        ]

        triggers = analyzer.detect_triggers(production_data, {}, default_thresholds)

        assert len(triggers) == 1
        assert triggers[0].trigger_type == "low_achievement"
        assert triggers[0].severity == "warning"
        assert triggers[0].affected_line == "LINE-A"

    def test_detect_low_achievement_critical(self, analyzer, default_thresholds):
        """낮은 달성률 크리티컬 감지"""
        production_data = [
            {"line_code": "LINE-A", "achievement_rate": 50.0, "defect_rate": 1.0, "downtime_min": 20}
        ]

        triggers = analyzer.detect_triggers(production_data, {}, default_thresholds)

        assert len(triggers) == 1
        assert triggers[0].trigger_type == "low_achievement"
        assert triggers[0].severity == "critical"

    def test_detect_high_defect_warning(self, analyzer, default_thresholds):
        """높은 불량률 경고 감지"""
        production_data = [
            {"line_code": "LINE-B", "achievement_rate": 90.0, "defect_rate": 4.0, "downtime_min": 20}
        ]

        triggers = analyzer.detect_triggers(production_data, {}, default_thresholds)

        assert len(triggers) == 1
        assert triggers[0].trigger_type == "high_defect"
        assert triggers[0].severity == "warning"
        assert triggers[0].affected_line == "LINE-B"

    def test_detect_high_defect_critical(self, analyzer, default_thresholds):
        """높은 불량률 크리티컬 감지"""
        production_data = [
            {"line_code": "LINE-B", "achievement_rate": 90.0, "defect_rate": 5.0, "downtime_min": 20}
        ]

        triggers = analyzer.detect_triggers(production_data, {}, default_thresholds)

        assert len(triggers) == 1
        assert triggers[0].trigger_type == "high_defect"
        assert triggers[0].severity == "critical"

    def test_detect_high_downtime_warning(self, analyzer, default_thresholds):
        """높은 비가동 시간 경고 감지"""
        production_data = [
            {"line_code": "LINE-C", "achievement_rate": 90.0, "defect_rate": 1.0, "downtime_min": 70}
        ]

        triggers = analyzer.detect_triggers(production_data, {}, default_thresholds)

        assert len(triggers) == 1
        assert triggers[0].trigger_type == "high_downtime"
        assert triggers[0].severity == "warning"

    def test_detect_high_downtime_critical(self, analyzer, default_thresholds):
        """높은 비가동 시간 크리티컬 감지"""
        production_data = [
            {"line_code": "LINE-C", "achievement_rate": 90.0, "defect_rate": 1.0, "downtime_min": 100}
        ]

        triggers = analyzer.detect_triggers(production_data, {}, default_thresholds)

        assert len(triggers) == 1
        assert triggers[0].trigger_type == "high_downtime"
        assert triggers[0].severity == "critical"

    def test_detect_sudden_drop_warning(self, analyzer, default_thresholds):
        """전일 대비 급격한 하락 감지"""
        production_data = []
        comparison_data = {
            "by_line": {
                "LINE-A": {"vs_yesterday_pct": -15}
            }
        }

        triggers = analyzer.detect_triggers(production_data, comparison_data, default_thresholds)

        assert len(triggers) == 1
        assert triggers[0].trigger_type == "sudden_drop"
        assert triggers[0].severity == "warning"

    def test_detect_sudden_drop_critical(self, analyzer, default_thresholds):
        """전일 대비 급격한 하락 크리티컬 감지"""
        production_data = []
        comparison_data = {
            "by_line": {
                "LINE-A": {"vs_yesterday_pct": -25}
            }
        }

        triggers = analyzer.detect_triggers(production_data, comparison_data, default_thresholds)

        assert len(triggers) == 1
        assert triggers[0].trigger_type == "sudden_drop"
        assert triggers[0].severity == "critical"

    def test_detect_multiple_triggers(self, analyzer, default_thresholds):
        """여러 트리거 동시 감지"""
        production_data = [
            {"line_code": "LINE-A", "achievement_rate": 60.0, "defect_rate": 5.0, "downtime_min": 100}
        ]

        triggers = analyzer.detect_triggers(production_data, {}, default_thresholds)

        assert len(triggers) == 3
        trigger_types = [t.trigger_type for t in triggers]
        assert "low_achievement" in trigger_types
        assert "high_defect" in trigger_types
        assert "high_downtime" in trigger_types

    def test_no_triggers_when_normal(self, analyzer, default_thresholds):
        """정상 상태에서 트리거 없음"""
        production_data = [
            {"line_code": "LINE-A", "achievement_rate": 98.0, "defect_rate": 1.0, "downtime_min": 20}
        ]

        triggers = analyzer.detect_triggers(production_data, {}, default_thresholds)

        assert len(triggers) == 0

    def test_handle_missing_values(self, analyzer, default_thresholds):
        """누락된 값 처리"""
        production_data = [
            {"line_code": "LINE-A"}  # achievement_rate, defect_rate, downtime_min 없음
        ]

        triggers = analyzer.detect_triggers(production_data, {}, default_thresholds)

        # 0으로 처리되어 트리거 발생 (달성률 0)
        assert any(t.trigger_type == "low_achievement" for t in triggers)


# ========== 라벨 및 요약 함수 테스트 ==========


class TestHelperMethods:
    """헬퍼 메서드 테스트"""

    @pytest.fixture
    def analyzer(self):
        from app.services.bi_correlation_analyzer import CorrelationAnalyzer
        return CorrelationAnalyzer(db=MagicMock(), tenant_id=uuid4())

    def test_get_event_type_label_known(self, analyzer):
        """알려진 이벤트 유형 라벨"""
        assert analyzer._get_event_type_label("alarm") == "알람/경보"
        assert analyzer._get_event_type_label("breakdown") == "고장/장애"
        assert analyzer._get_event_type_label("maintenance") == "정비/PM"
        assert analyzer._get_event_type_label("setup") == "셋업/품종 교체"
        assert analyzer._get_event_type_label("idle") == "대기/공회전"

    def test_get_event_type_label_unknown(self, analyzer):
        """알 수 없는 이벤트 유형 라벨"""
        assert analyzer._get_event_type_label("unknown_type") == "unknown_type"

    def test_summarize_downtime_causes_empty(self, analyzer):
        """빈 비가동 원인 요약"""
        summary = analyzer._summarize_downtime_causes([])
        assert summary == "비가동 데이터가 없습니다."

    def test_summarize_downtime_causes_single(self, analyzer):
        """단일 비가동 원인 요약"""
        causes = [{
            "event_type_label": "고장/장애",
            "equipment_name": "설비1",
            "total_min": 120,
            "percentage": 100
        }]
        summary = analyzer._summarize_downtime_causes(causes)

        assert "주요 비가동 원인: 고장/장애" in summary
        assert "설비1" in summary
        assert "120분" in summary

    def test_summarize_downtime_causes_multiple(self, analyzer):
        """다중 비가동 원인 요약"""
        causes = [
            {
                "event_type_label": "고장/장애",
                "equipment_name": "설비1",
                "total_min": 120,
                "percentage": 60
            },
            {
                "event_type_label": "정비/PM",
                "equipment_name": "설비2",
                "total_min": 80,
                "percentage": 40
            }
        ]
        summary = analyzer._summarize_downtime_causes(causes)

        assert "주요 비가동 원인: 고장/장애" in summary
        assert "2위: 정비/PM" in summary

    def test_summarize_defect_distribution_empty(self, analyzer):
        """빈 불량 분포 요약"""
        summary = analyzer._summarize_defect_distribution([])
        assert summary == "불량 데이터가 없습니다."

    def test_summarize_defect_distribution_single(self, analyzer):
        """단일 불량 유형 요약"""
        defects = [{
            "defect_type": "외관불량",
            "total_qty": 50,
            "percentage": 100,
            "root_causes": ["작업자 실수"]
        }]
        summary = analyzer._summarize_defect_distribution(defects)

        assert "주요 불량 유형: 외관불량" in summary
        assert "50EA" in summary
        assert "작업자 실수" in summary

    def test_summarize_defect_distribution_no_causes(self, analyzer):
        """원인 없는 불량 유형 요약"""
        defects = [{
            "defect_type": "치수불량",
            "total_qty": 30,
            "percentage": 100,
            "root_causes": []
        }]
        summary = analyzer._summarize_defect_distribution(defects)

        assert "주요 불량 유형: 치수불량" in summary
        assert "원인:" not in summary

    def test_summarize_change_causes_decrease(self, analyzer):
        """감소 변동 요약"""
        summary = analyzer._summarize_change_causes(-15.0, ["비가동 시간 증가 (+45분)"])

        assert "15.0% 감소" in summary
        assert "비가동 시간 증가" in summary

    def test_summarize_change_causes_increase(self, analyzer):
        """증가 변동 요약"""
        summary = analyzer._summarize_change_causes(10.0, [])

        assert "10.0% 증가" in summary
        assert "특이사항 없음" in summary


# ========== 비동기 분석 메서드 테스트 ==========


class TestAnalyzeDowntimeCauses:
    """analyze_downtime_causes 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_analyze_downtime_causes_success(self):
        """비가동 원인 분석 성공"""
        from app.services.bi_correlation_analyzer import CorrelationAnalyzer

        mock_db = AsyncMock()

        # Mock 결과
        mock_row = MagicMock()
        mock_row.event_type = "breakdown"
        mock_row.equipment_code = "EQ001"
        mock_row.equipment_name = "설비1"
        mock_row.event_count = 5
        mock_row.total_min = Decimal("120.0")
        mock_row.avg_min = Decimal("24.0")

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute = AsyncMock(return_value=mock_result)

        analyzer = CorrelationAnalyzer(db=mock_db, tenant_id=uuid4())

        result = await analyzer.analyze_downtime_causes("LINE-A", date(2024, 1, 15))

        assert result["line_code"] == "LINE-A"
        assert result["date"] == "2024-01-15"
        assert result["total_downtime_min"] == 120.0
        assert len(result["causes"]) == 1
        assert result["causes"][0]["event_type"] == "breakdown"

    @pytest.mark.asyncio
    async def test_analyze_downtime_causes_empty(self):
        """비가동 원인 없음"""
        from app.services.bi_correlation_analyzer import CorrelationAnalyzer

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        analyzer = CorrelationAnalyzer(db=mock_db, tenant_id=uuid4())

        result = await analyzer.analyze_downtime_causes("LINE-A")

        assert result["total_downtime_min"] == 0.0
        assert len(result["causes"]) == 0
        assert "비가동 데이터가 없습니다" in result["analysis_summary"]


class TestAnalyzeDefectDistribution:
    """analyze_defect_distribution 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_analyze_defect_distribution_success(self):
        """불량 분포 분석 성공"""
        from app.services.bi_correlation_analyzer import CorrelationAnalyzer

        mock_db = AsyncMock()

        mock_row = MagicMock()
        mock_row.defect_type = "외관불량"
        mock_row.total_qty = Decimal("100")
        mock_row.total_cost = Decimal("50000")
        mock_row.product_count = 3
        mock_row.root_causes = ["작업자 실수", "원자재 불량"]
        mock_row.product_names = ["제품A", "제품B"]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute = AsyncMock(return_value=mock_result)

        analyzer = CorrelationAnalyzer(db=mock_db, tenant_id=uuid4())

        result = await analyzer.analyze_defect_distribution("LINE-A", date(2024, 1, 15))

        assert result["line_code"] == "LINE-A"
        assert result["total_defect_qty"] == 100.0
        assert len(result["defect_types"]) == 1
        assert result["defect_types"][0]["defect_type"] == "외관불량"


class TestAnalyzeChangeCauses:
    """analyze_change_causes 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_analyze_change_causes_success(self):
        """변동 원인 분석 성공"""
        from app.services.bi_correlation_analyzer import CorrelationAnalyzer

        mock_db = AsyncMock()

        mock_row = MagicMock()
        mock_row.today_qty = 800
        mock_row.yesterday_qty = 1000
        mock_row.today_downtime = 90
        mock_row.yesterday_downtime = 30
        mock_row.today_runtime = 400
        mock_row.yesterday_runtime = 450
        mock_row.today_defect = 50
        mock_row.yesterday_defect = 20

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute = AsyncMock(return_value=mock_result)

        analyzer = CorrelationAnalyzer(db=mock_db, tenant_id=uuid4())

        result = await analyzer.analyze_change_causes("LINE-A", date(2024, 1, 15))

        assert result["line_code"] == "LINE-A"
        assert result["metrics"]["qty_change_pct"] == -20.0  # (800-1000)/1000 * 100
        assert "비가동 시간 증가" in result["possible_causes"][0]
        assert "불량 증가" in result["possible_causes"][1]

    @pytest.mark.asyncio
    async def test_analyze_change_causes_no_data(self):
        """데이터 없음"""
        from app.services.bi_correlation_analyzer import CorrelationAnalyzer

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        analyzer = CorrelationAnalyzer(db=mock_db, tenant_id=uuid4())

        result = await analyzer.analyze_change_causes("LINE-A")

        assert "비교 데이터가 부족" in result["analysis_summary"]


# ========== 종합 연관 분석 테스트 ==========


class TestRunCorrelationAnalysis:
    """run_correlation_analysis 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_run_no_issues(self):
        """이상 없음"""
        from app.services.bi_correlation_analyzer import CorrelationAnalyzer

        mock_db = AsyncMock()
        analyzer = CorrelationAnalyzer(db=mock_db, tenant_id=uuid4())

        production_data = [
            {"line_code": "LINE-A", "achievement_rate": 98.0, "defect_rate": 1.0, "downtime_min": 20}
        ]
        thresholds = {
            "achievement_rate": {"green": 95.0, "yellow": 80.0},
            "defect_rate": {"green": 2.0, "yellow": 3.0},
            "downtime_minutes": {"green": 30.0, "yellow": 60.0}
        }

        result = await analyzer.run_correlation_analysis(
            production_data=production_data,
            comparison_data={},
            thresholds=thresholds
        )

        assert result["has_issues"] is False
        assert len(result["triggers"]) == 0
        assert "정상 범위 내" in result["summary"]

    @pytest.mark.asyncio
    async def test_run_with_low_achievement(self):
        """달성률 저조 분석"""
        from app.services.bi_correlation_analyzer import CorrelationAnalyzer

        mock_db = AsyncMock()

        # Mock downtime analysis result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        analyzer = CorrelationAnalyzer(db=mock_db, tenant_id=uuid4())

        production_data = [
            {"line_code": "LINE-A", "achievement_rate": 70.0, "defect_rate": 1.0, "downtime_min": 20}
        ]
        thresholds = {
            "achievement_rate": {"green": 95.0, "yellow": 80.0},
            "defect_rate": {"green": 2.0, "yellow": 3.0},
            "downtime_minutes": {"green": 30.0, "yellow": 60.0}
        }

        result = await analyzer.run_correlation_analysis(
            production_data=production_data,
            comparison_data={},
            thresholds=thresholds,
            target_date=date(2024, 1, 15)
        )

        assert result["has_issues"] is True
        assert len(result["triggers"]) == 1
        assert result["triggers"][0]["type"] == "low_achievement"
        assert "LINE-A" in result["analysis_results"]
        assert "downtime_analysis" in result["analysis_results"]["LINE-A"]

    @pytest.mark.asyncio
    async def test_run_with_high_defect(self):
        """불량률 초과 분석"""
        from app.services.bi_correlation_analyzer import CorrelationAnalyzer

        mock_db = AsyncMock()

        # Mock defect analysis result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        analyzer = CorrelationAnalyzer(db=mock_db, tenant_id=uuid4())

        production_data = [
            {"line_code": "LINE-B", "achievement_rate": 95.0, "defect_rate": 5.0, "downtime_min": 20}
        ]
        thresholds = {
            "achievement_rate": {"green": 95.0, "yellow": 80.0},
            "defect_rate": {"green": 2.0, "yellow": 3.0},
            "downtime_minutes": {"green": 30.0, "yellow": 60.0}
        }

        result = await analyzer.run_correlation_analysis(
            production_data=production_data,
            comparison_data={},
            thresholds=thresholds
        )

        assert result["has_issues"] is True
        assert result["triggers"][0]["type"] == "high_defect"
        assert "defect_analysis" in result["analysis_results"]["LINE-B"]

    @pytest.mark.asyncio
    async def test_run_with_sudden_drop(self):
        """급격한 하락 분석"""
        from app.services.bi_correlation_analyzer import CorrelationAnalyzer

        mock_db = AsyncMock()

        # Mock change analysis result
        mock_row = MagicMock()
        mock_row.today_qty = 800
        mock_row.yesterday_qty = 1000
        mock_row.today_downtime = 50
        mock_row.yesterday_downtime = 50
        mock_row.today_runtime = 400
        mock_row.yesterday_runtime = 400
        mock_row.today_defect = 20
        mock_row.yesterday_defect = 20

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute = AsyncMock(return_value=mock_result)

        analyzer = CorrelationAnalyzer(db=mock_db, tenant_id=uuid4())

        production_data = []
        comparison_data = {
            "by_line": {
                "LINE-A": {"vs_yesterday_pct": -25}
            }
        }
        thresholds = {
            "achievement_rate": {"green": 95.0, "yellow": 80.0},
            "defect_rate": {"green": 2.0, "yellow": 3.0},
            "downtime_minutes": {"green": 30.0, "yellow": 60.0}
        }

        result = await analyzer.run_correlation_analysis(
            production_data=production_data,
            comparison_data=comparison_data,
            thresholds=thresholds
        )

        assert result["has_issues"] is True
        assert result["triggers"][0]["type"] == "sudden_drop"
        assert "change_analysis" in result["analysis_results"]["LINE-A"]

    @pytest.mark.asyncio
    async def test_run_summary_counts(self):
        """요약 카운트 테스트"""
        from app.services.bi_correlation_analyzer import CorrelationAnalyzer

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        analyzer = CorrelationAnalyzer(db=mock_db, tenant_id=uuid4())

        production_data = [
            {"line_code": "LINE-A", "achievement_rate": 50.0, "defect_rate": 1.0, "downtime_min": 20},
            {"line_code": "LINE-B", "achievement_rate": 75.0, "defect_rate": 1.0, "downtime_min": 20},
        ]
        thresholds = {
            "achievement_rate": {"green": 95.0, "yellow": 80.0},
            "defect_rate": {"green": 2.0, "yellow": 3.0},
            "downtime_minutes": {"green": 30.0, "yellow": 60.0}
        }

        result = await analyzer.run_correlation_analysis(
            production_data=production_data,
            comparison_data={},
            thresholds=thresholds
        )

        assert result["critical_count"] == 1  # LINE-A: 50% < 64% (80% * 0.8)
        assert result["warning_count"] == 1  # LINE-B: 75% < 80% but >= 64%
        assert "긴급" in result["summary"]
        assert "주의" in result["summary"]
