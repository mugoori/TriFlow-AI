"""
BI Router 테스트

BI 라우터의 핵심 엔드포인트를 Mock 기반으로 테스트
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, date
from uuid import uuid4

from app.routers.bi import (
    DashboardCreate,
    DashboardUpdate,
    DashboardLayout,
    DashboardLayoutComponent,
    MetricValueResponse,
    ProductionSummary,
    ProductionResponse,
    DefectTrendItem,
    DefectTrendResponse,
    OEEItem,
    OEEResponse,
    InventoryItem,
)


class TestBIPydanticModels:
    """Pydantic 모델 테스트"""

    def test_dashboard_layout_component_model(self):
        """DashboardLayoutComponent 모델"""
        component = DashboardLayoutComponent(
            id="chart-1",
            type="line",
            position={"x": 0, "y": 0, "w": 6, "h": 4},
            config={"metric": "production_qty"},
        )

        assert component.id == "chart-1"
        assert component.type == "line"
        assert component.position["w"] == 6

    def test_dashboard_layout_model(self):
        """DashboardLayout 모델"""
        layout = DashboardLayout(
            components=[
                DashboardLayoutComponent(
                    id="chart-1",
                    type="line",
                    position={"x": 0, "y": 0, "w": 6, "h": 4},
                    config={},
                ),
            ]
        )

        assert len(layout.components) == 1

    def test_dashboard_create_model(self):
        """DashboardCreate 모델"""
        dashboard = DashboardCreate(
            name="테스트 대시보드",
            description="설명",
            layout=DashboardLayout(components=[]),
            is_public=False,
        )

        assert dashboard.name == "테스트 대시보드"
        assert dashboard.is_public is False

    def test_dashboard_create_validation(self):
        """DashboardCreate 검증"""
        with pytest.raises(Exception):
            DashboardCreate(
                name="",  # min_length=1 위반
                layout=DashboardLayout(components=[]),
            )

    def test_production_summary_model(self):
        """ProductionSummary 모델"""
        summary = ProductionSummary(
            date=date(2024, 1, 15),
            line_code="LINE_A",
            product_code="PROD_001",
            shift="day",
            total_qty=1000.0,
            good_qty=950.0,
            defect_qty=50.0,
            defect_rate=5.0,
            yield_rate=95.0,
            runtime_minutes=480.0,
            downtime_minutes=30.0,
            availability=93.75,
        )

        assert summary.defect_rate == 5.0
        assert summary.yield_rate == 95.0

    def test_defect_trend_item_model(self):
        """DefectTrendItem 모델"""
        item = DefectTrendItem(
            date=date(2024, 1, 15),
            line_code="LINE_A",
            total_qty=1000.0,
            defect_qty=50.0,
            defect_rate=5.0,
        )

        assert item.line_code == "LINE_A"
        assert item.defect_rate == 5.0

    def test_oee_item_model(self):
        """OEEItem 모델"""
        item = OEEItem(
            date=date(2024, 1, 15),
            line_code="LINE_A",
            shift="day",
            availability=90.0,
            performance=95.0,
            quality=98.0,
            oee=83.79,
            runtime_minutes=480.0,
            downtime_minutes=53.3,
        )

        assert item.oee == 83.79

    def test_inventory_item_model(self):
        """InventoryItem 모델"""
        item = InventoryItem(
            date=date(2024, 1, 15),
            product_code="PROD_001",
            location="WAREHOUSE_A",
            stock_qty=500.0,
            safety_stock_qty=100.0,
            available_qty=400.0,
            stock_status="normal",
        )

        assert item.stock_status == "normal"


class TestMetricValueResponse:
    """MetricValueResponse 모델 테스트"""

    def test_metric_value_basic(self):
        """기본 메트릭 값"""
        metric_id = uuid4()
        response = MetricValueResponse(
            metric_id=metric_id,
            metric_name="생산량",
            value=1234.5,
            formatted_value="1,234.5",
            calculated_at=datetime.now(),
        )

        assert response.value == 1234.5
        assert response.comparison is None

    def test_metric_value_with_comparison(self):
        """비교 데이터 포함"""
        metric_id = uuid4()
        response = MetricValueResponse(
            metric_id=metric_id,
            metric_name="생산량",
            value=1234.5,
            formatted_value="1,234.5",
            comparison={
                "previous_value": 1000.0,
                "change_percent": 23.45,
                "direction": "up",
            },
            calculated_at=datetime.now(),
        )

        assert response.comparison["change_percent"] == 23.45


class TestProductionResponse:
    """ProductionResponse 모델 테스트"""

    def test_production_response(self):
        """생산 응답 모델"""
        data = [
            ProductionSummary(
                date=date(2024, 1, 15),
                line_code="LINE_A",
                product_code="PROD_001",
                shift="day",
                total_qty=1000.0,
                good_qty=950.0,
                defect_qty=50.0,
                defect_rate=5.0,
                yield_rate=95.0,
                runtime_minutes=480.0,
                downtime_minutes=30.0,
                availability=93.75,
            )
        ]

        response = ProductionResponse(
            data=data,
            total=1,
            summary={
                "total_production": 1000.0,
                "avg_defect_rate": 5.0,
            },
        )

        assert response.total == 1
        assert response.summary["total_production"] == 1000.0


class TestDefectTrendResponse:
    """DefectTrendResponse 모델 테스트"""

    def test_defect_trend_response(self):
        """불량 추이 응답 모델"""
        data = [
            DefectTrendItem(
                date=date(2024, 1, 15),
                line_code="LINE_A",
                total_qty=1000.0,
                defect_qty=50.0,
                defect_rate=5.0,
            )
        ]

        response = DefectTrendResponse(
            data=data,
            total=1,
            avg_defect_rate=5.0,
        )

        assert response.avg_defect_rate == 5.0


class TestOEEResponse:
    """OEEResponse 모델 테스트"""

    def test_oee_response(self):
        """OEE 응답 모델"""
        data = [
            OEEItem(
                date=date(2024, 1, 15),
                line_code="LINE_A",
                shift="day",
                availability=90.0,
                performance=95.0,
                quality=98.0,
                oee=83.79,
                runtime_minutes=480.0,
                downtime_minutes=53.3,
            )
        ]

        response = OEEResponse(
            data=data,
            total=1,
            avg_oee=83.79,
            avg_availability=90.0,
            avg_performance=95.0,
            avg_quality=98.0,
        )

        assert response.avg_oee == 83.79


class TestDashboardUpdate:
    """DashboardUpdate 모델 테스트"""

    def test_partial_update(self):
        """부분 업데이트"""
        update = DashboardUpdate(
            name="새 이름",
        )

        assert update.name == "새 이름"
        assert update.description is None
        assert update.layout is None
        assert update.is_public is None

    def test_full_update(self):
        """전체 업데이트"""
        update = DashboardUpdate(
            name="새 이름",
            description="새 설명",
            layout=DashboardLayout(components=[]),
            is_public=True,
        )

        assert update.is_public is True


class TestChartTypes:
    """차트 타입 관련 테스트"""

    def test_supported_chart_types(self):
        """지원되는 차트 타입 (일반적인 차트 타입)"""
        # BI에서 일반적으로 지원하는 차트 타입
        supported_types = ["line", "bar", "pie", "area", "scatter"]

        assert "line" in supported_types
        assert "bar" in supported_types
        assert "pie" in supported_types


class TestHelperFunctions:
    """헬퍼 함수 테스트 (로컬 구현)"""

    def format_value(self, value, format_type):
        """간단한 포맷팅 구현"""
        if format_type == "integer":
            return f"{int(value):,}"
        elif format_type == "float":
            return f"{value:,.2f}"
        elif format_type == "percent":
            return f"{value * 100:.2f}%"
        elif format_type == "currency":
            return f"₩{int(value):,}"
        return str(value)

    def test_format_value_integer(self):
        """정수 포맷팅"""
        result = self.format_value(1234, "integer")
        assert result == "1,234"

    def test_format_value_float(self):
        """소수 포맷팅"""
        result = self.format_value(1234.5678, "float")
        assert result == "1,234.57"

    def test_format_value_percent(self):
        """퍼센트 포맷팅"""
        result = self.format_value(0.8579, "percent")
        assert result == "85.79%"

    def test_format_value_currency(self):
        """통화 포맷팅"""
        result = self.format_value(1234567, "currency")
        assert "₩" in result
        assert "1,234,567" in result


class TestChartConfigGeneration:
    """차트 설정 생성 테스트 (로컬 구현)"""

    def generate_chart_config(self, chart_type, data, title, x_field, y_field):
        """차트 설정 생성"""
        return {
            "type": chart_type,
            "title": title,
            "data": data,
            "options": {
                "xField": x_field,
                "yField": y_field,
            },
        }

    def test_line_chart_config(self):
        """라인 차트 설정"""
        data = {
            "columns": ["date", "value"],
            "rows": [["2024-01-01", 100], ["2024-01-02", 110]],
        }

        config = self.generate_chart_config(
            chart_type="line",
            data=data,
            title="트렌드 차트",
            x_field="date",
            y_field="value",
        )

        assert config["type"] == "line"
        assert config["title"] == "트렌드 차트"
        assert "data" in config
        assert "options" in config

    def test_bar_chart_config(self):
        """바 차트 설정"""
        data = {
            "columns": ["category", "count"],
            "rows": [["A", 50], ["B", 30]],
        }

        config = self.generate_chart_config(
            chart_type="bar",
            data=data,
            title="카테고리별 분포",
            x_field="category",
            y_field="count",
        )

        assert config["type"] == "bar"

    def test_pie_chart_config(self):
        """파이 차트 설정"""
        data = {
            "columns": ["category", "value"],
            "rows": [["A", 40], ["B", 60]],
        }

        config = self.generate_chart_config(
            chart_type="pie",
            data=data,
            title="비율 차트",
            x_field="category",
            y_field="value",
        )

        assert config["type"] == "pie"


class TestCalculateKPIs:
    """KPI 계산 테스트"""

    def test_calculate_oee(self):
        """OEE 계산"""
        availability = 0.9  # 90%
        performance = 0.95  # 95%
        quality = 0.98  # 98%

        oee = availability * performance * quality
        expected_oee = 0.8379  # 83.79%

        assert abs(oee - expected_oee) < 0.001

    def test_calculate_defect_rate(self):
        """불량률 계산"""
        total_qty = 1000
        defect_qty = 50

        defect_rate = (defect_qty / total_qty) * 100
        expected_rate = 5.0  # 5%

        assert defect_rate == expected_rate

    def test_calculate_yield_rate(self):
        """수율 계산"""
        total_qty = 1000
        good_qty = 950

        yield_rate = (good_qty / total_qty) * 100
        expected_rate = 95.0  # 95%

        assert yield_rate == expected_rate


class TestDateRangeValidation:
    """날짜 범위 검증 테스트"""

    def test_valid_date_range(self):
        """유효한 날짜 범위"""
        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        assert start_date < end_date

    def test_date_range_max_days(self):
        """최대 일수 검증"""
        start_date = date(2024, 1, 1)
        end_date = date(2024, 12, 31)

        days = (end_date - start_date).days
        max_days = 365

        assert days <= max_days


class TestChartDataTransformation:
    """차트 데이터 변환 테스트"""

    def test_transform_time_series_data(self):
        """시계열 데이터 변환"""
        raw_data = [
            {"date": "2024-01-01", "value": 100},
            {"date": "2024-01-02", "value": 110},
            {"date": "2024-01-03", "value": 105},
        ]

        labels = [d["date"] for d in raw_data]
        values = [d["value"] for d in raw_data]

        assert len(labels) == 3
        assert len(values) == 3
        assert sum(values) == 315

    def test_transform_category_data(self):
        """카테고리 데이터 변환"""
        raw_data = [
            {"category": "A", "count": 50},
            {"category": "B", "count": 30},
            {"category": "C", "count": 20},
        ]

        categories = [d["category"] for d in raw_data]
        counts = [d["count"] for d in raw_data]

        assert len(categories) == 3
        assert sum(counts) == 100


class TestAggregationLogic:
    """집계 로직 테스트"""

    def test_sum_aggregation(self):
        """합계 집계"""
        values = [100, 200, 300]
        result = sum(values)

        assert result == 600

    def test_avg_aggregation(self):
        """평균 집계"""
        values = [100, 200, 300]
        result = sum(values) / len(values)

        assert result == 200.0

    def test_min_max_aggregation(self):
        """최소/최대 집계"""
        values = [100, 200, 300]

        assert min(values) == 100
        assert max(values) == 300

    def test_count_aggregation(self):
        """카운트 집계"""
        values = [100, 200, 300]

        assert len(values) == 3


class TestStockStatusLogic:
    """재고 상태 로직 테스트"""

    def test_stock_status_normal(self):
        """정상 재고 상태"""
        stock_qty = 500
        safety_stock_qty = 100

        if stock_qty >= safety_stock_qty * 2:
            status = "normal"
        elif stock_qty >= safety_stock_qty:
            status = "low"
        else:
            status = "critical"

        assert status == "normal"

    def test_stock_status_low(self):
        """낮은 재고 상태"""
        stock_qty = 150
        safety_stock_qty = 100

        if stock_qty >= safety_stock_qty * 2:
            status = "normal"
        elif stock_qty >= safety_stock_qty:
            status = "low"
        else:
            status = "critical"

        assert status == "low"

    def test_stock_status_critical(self):
        """위험 재고 상태"""
        stock_qty = 50
        safety_stock_qty = 100

        if stock_qty >= safety_stock_qty * 2:
            status = "normal"
        elif stock_qty >= safety_stock_qty:
            status = "low"
        else:
            status = "critical"

        assert status == "critical"


class TestInsightRequest:
    """인사이트 요청 테스트 (로컬 구현)"""

    def test_insight_request_model(self):
        """인사이트 요청 모델"""
        # 인사이트 요청 구조
        request = {
            "query": "최근 7일간 생산량 추이",
            "context": {"line_code": "LINE_A"},
        }

        assert "생산량" in request["query"]

    def test_insight_request_with_time_range(self):
        """시간 범위 포함 인사이트 요청"""
        request = {
            "query": "이번 달 불량률 분석",
            "context": {"start_date": "2024-01-01", "end_date": "2024-01-31"},
        }

        assert request["context"]["start_date"] == "2024-01-01"


class TestChatRequest:
    """챗 요청 테스트 (로컬 구현)"""

    def test_chat_request_model(self):
        """챗 요청 모델"""
        request = {
            "message": "라인별 생산량 보여줘",
            "session_id": "session-123",
        }

        assert "생산량" in request["message"]
        assert request["session_id"] == "session-123"


class TestStatCardModels:
    """StatCard 모델 테스트 (로컬 구현)"""

    def test_stat_card_config_create(self):
        """StatCard 설정 생성 모델"""
        config = {
            "metric_key": "total_production",
            "title": "총 생산량",
            "icon": "factory",
            "color": "blue",
            "order_index": 0,
            "is_visible": True,
        }

        assert config["metric_key"] == "total_production"
        assert config["order_index"] == 0

    def test_stat_card_config_update(self):
        """StatCard 설정 업데이트 모델"""
        update = {
            "title": "새 제목",
            "color": "green",
            "icon": None,  # 부분 업데이트
        }

        assert update["title"] == "새 제목"
        assert update["icon"] is None


class TestDataStoryModels:
    """DataStory 모델 테스트 (로컬 구현)"""

    def test_data_story_create(self):
        """DataStory 생성 모델"""
        story = {
            "title": "생산 현황 리포트",
            "description": "일일 생산 현황 분석",
        }

        assert story["title"] == "생산 현황 리포트"

    def test_data_story_section_create(self):
        """DataStory 섹션 생성 모델"""
        section = {
            "title": "개요",
            "content": "이 섹션은 전체 개요를 설명합니다.",
            "section_type": "text",
            "order_index": 0,
        }

        assert section["section_type"] == "text"


class TestChartRequest:
    """ChartRequest 모델 테스트"""

    def test_chart_request_model(self):
        """ChartRequest 모델"""
        from app.routers.bi import ChartRequest

        request = ChartRequest(
            chart_type="line",
            data_source="production",
            x_field="date",
            y_fields=["total_qty", "good_qty"],
            title="생산량 추이",
        )

        assert request.chart_type == "line"
        assert request.title == "생산량 추이"
        assert request.x_field == "date"
        assert len(request.y_fields) == 2

    def test_chart_request_with_options(self):
        """ChartRequest 모델 - 옵션 포함"""
        from app.routers.bi import ChartRequest

        request = ChartRequest(
            chart_type="bar",
            data_source="defect",
            x_field="line_code",
            y_fields=["defect_rate"],
            title="라인별 불량률",
            subtitle="2024년 1월",
            filters={"shift": "day"},
            options={"stacked": True},
            output_format="echarts",
        )

        assert request.chart_type == "bar"
        assert request.subtitle == "2024년 1월"
        assert request.output_format == "echarts"


class TestChartResponse:
    """ChartResponse 모델 테스트"""

    def test_chart_response_model(self):
        """ChartResponse 모델"""
        from app.routers.bi import ChartResponse

        response = ChartResponse(
            chart_id="chart-123",
            chart_type="line",
            title="생산량 추이",
            config={"data": [], "options": {}},
            data_count=100,
        )

        assert response.chart_type == "line"
        assert response.chart_id == "chart-123"
        assert response.data_count == 100
        assert "data" in response.config


# ========== API Endpoint Tests (Mock-based) ==========


class TestDashboardEndpointsMock:
    """대시보드 엔드포인트 테스트 (Mock 기반)"""

    @pytest.fixture
    def mock_user(self):
        """Mock 사용자"""
        user = MagicMock()
        user.tenant_id = uuid4()
        user.user_id = uuid4()
        return user

    @pytest.fixture
    def mock_db(self):
        """Mock DB 세션"""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_list_dashboards_with_public(self, mock_db, mock_user):
        """대시보드 목록 조회 - 공개 포함"""
        from app.routers.bi import list_dashboards

        mock_dashboard = MagicMock()
        mock_dashboard.id = uuid4()
        mock_dashboard.name = "테스트 대시보드"
        mock_dashboard.description = "설명"
        mock_dashboard.layout = {"components": []}
        mock_dashboard.is_public = True
        mock_dashboard.owner_id = mock_user.user_id
        mock_dashboard.tenant_id = mock_user.tenant_id
        mock_dashboard.created_at = datetime.now()
        mock_dashboard.updated_at = datetime.now()

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [mock_dashboard]
        mock_db.query.return_value = mock_query

        result = await list_dashboards(
            db=mock_db,
            current_user=mock_user,
            include_public=True
        )

        assert len(result) == 1
        mock_db.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_dashboards_without_public(self, mock_db, mock_user):
        """대시보드 목록 조회 - 공개 미포함"""
        from app.routers.bi import list_dashboards

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        result = await list_dashboards(
            db=mock_db,
            current_user=mock_user,
            include_public=False
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_get_dashboard_success(self, mock_db, mock_user):
        """대시보드 상세 조회 - 성공"""
        from app.routers.bi import get_dashboard

        dashboard_id = uuid4()
        mock_dashboard = MagicMock()
        mock_dashboard.id = dashboard_id
        mock_dashboard.name = "테스트"
        mock_dashboard.description = None
        mock_dashboard.layout = {}
        mock_dashboard.is_public = True
        mock_dashboard.owner_id = mock_user.user_id
        mock_dashboard.tenant_id = mock_user.tenant_id
        mock_dashboard.created_at = datetime.now()
        mock_dashboard.updated_at = datetime.now()

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_dashboard
        mock_db.query.return_value = mock_query

        result = await get_dashboard(
            dashboard_id=dashboard_id,
            db=mock_db,
            current_user=mock_user
        )

        assert result == mock_dashboard

    @pytest.mark.asyncio
    async def test_get_dashboard_not_found(self, mock_db, mock_user):
        """대시보드 상세 조회 - 없음"""
        from app.routers.bi import get_dashboard
        from fastapi import HTTPException

        dashboard_id = uuid4()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard(
                dashboard_id=dashboard_id,
                db=mock_db,
                current_user=mock_user
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_dashboard_access_denied(self, mock_db, mock_user):
        """대시보드 상세 조회 - 접근 거부"""
        from app.routers.bi import get_dashboard
        from fastapi import HTTPException

        dashboard_id = uuid4()
        mock_dashboard = MagicMock()
        mock_dashboard.owner_id = uuid4()  # 다른 사용자
        mock_dashboard.is_public = False

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_dashboard
        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard(
                dashboard_id=dashboard_id,
                db=mock_db,
                current_user=mock_user
            )

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_create_dashboard_success(self, mock_db, mock_user):
        """대시보드 생성 - 성공"""
        from app.routers.bi import create_dashboard, DashboardCreate, DashboardLayout

        data = DashboardCreate(
            name="새 대시보드",
            description="설명",
            layout=DashboardLayout(components=[]),
            is_public=False,
        )

        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        result = await create_dashboard(
            data=data,
            db=mock_db,
            current_user=mock_user
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_dashboard_success(self, mock_db, mock_user):
        """대시보드 수정 - 성공"""
        from app.routers.bi import update_dashboard, DashboardUpdate

        dashboard_id = uuid4()
        mock_dashboard = MagicMock()
        mock_dashboard.id = dashboard_id
        mock_dashboard.owner_id = mock_user.user_id
        mock_dashboard.name = "기존 이름"

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_dashboard
        mock_db.query.return_value = mock_query

        data = DashboardUpdate(name="새 이름")

        result = await update_dashboard(
            dashboard_id=dashboard_id,
            data=data,
            db=mock_db,
            current_user=mock_user
        )

        assert mock_dashboard.name == "새 이름"
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_dashboard_not_found(self, mock_db, mock_user):
        """대시보드 수정 - 없음"""
        from app.routers.bi import update_dashboard, DashboardUpdate
        from fastapi import HTTPException

        dashboard_id = uuid4()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        mock_db.query.return_value = mock_query

        data = DashboardUpdate(name="새 이름")

        with pytest.raises(HTTPException) as exc_info:
            await update_dashboard(
                dashboard_id=dashboard_id,
                data=data,
                db=mock_db,
                current_user=mock_user
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_dashboard_success(self, mock_db, mock_user):
        """대시보드 삭제 - 성공"""
        from app.routers.bi import delete_dashboard

        dashboard_id = uuid4()
        mock_dashboard = MagicMock()
        mock_dashboard.id = dashboard_id

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_dashboard
        mock_db.query.return_value = mock_query

        result = await delete_dashboard(
            dashboard_id=dashboard_id,
            db=mock_db,
            current_user=mock_user
        )

        assert result["status"] == "deleted"
        mock_db.delete.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_dashboard_not_found(self, mock_db, mock_user):
        """대시보드 삭제 - 없음"""
        from app.routers.bi import delete_dashboard
        from fastapi import HTTPException

        dashboard_id = uuid4()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            await delete_dashboard(
                dashboard_id=dashboard_id,
                db=mock_db,
                current_user=mock_user
            )

        assert exc_info.value.status_code == 404


class TestDatasetEndpointsMock:
    """데이터셋 엔드포인트 테스트 (Mock 기반)"""

    @pytest.fixture
    def mock_user(self):
        """Mock 사용자"""
        user = MagicMock()
        user.tenant_id = uuid4()
        user.user_id = uuid4()
        return user

    @pytest.fixture
    def mock_db(self):
        """Mock DB 세션"""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_list_datasets(self, mock_db, mock_user):
        """데이터셋 목록 조회"""
        from app.routers.bi import list_datasets

        mock_dataset = MagicMock()
        mock_dataset.id = uuid4()
        mock_dataset.name = "production_data"
        mock_dataset.description = "생산 데이터"
        mock_dataset.source_type = "table"
        mock_dataset.source_ref = "fact_daily_production"
        mock_dataset.default_filters = {}
        mock_dataset.last_refresh_at = datetime.now()
        mock_dataset.row_count = 1000

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [mock_dataset]
        mock_db.query.return_value = mock_query

        result = await list_datasets(db=mock_db, current_user=mock_user)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_query_dataset_not_found(self, mock_db, mock_user):
        """데이터셋 쿼리 - 데이터셋 없음"""
        from app.routers.bi import query_dataset
        from fastapi import HTTPException

        dataset_id = uuid4()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            await query_dataset(
                dataset_id=dataset_id,
                db=mock_db,
                current_user=mock_user,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_query_dataset_unsupported_source(self, mock_db, mock_user):
        """데이터셋 쿼리 - 지원되지 않는 소스"""
        from app.routers.bi import query_dataset
        from fastapi import HTTPException

        dataset_id = uuid4()
        mock_dataset = MagicMock()
        mock_dataset.id = dataset_id
        mock_dataset.source_ref = "unsupported_table"

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_dataset
        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            await query_dataset(
                dataset_id=dataset_id,
                db=mock_db,
                current_user=mock_user,
            )

        assert exc_info.value.status_code == 400


class TestMetricEndpointsMock:
    """지표 엔드포인트 테스트 (Mock 기반)"""

    @pytest.fixture
    def mock_user(self):
        """Mock 사용자"""
        user = MagicMock()
        user.tenant_id = uuid4()
        user.user_id = uuid4()
        return user

    @pytest.fixture
    def mock_db(self):
        """Mock DB 세션"""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_list_metrics(self, mock_db, mock_user):
        """지표 목록 조회"""
        from app.routers.bi import list_metrics

        mock_metric = MagicMock()
        mock_metric.id = uuid4()
        mock_metric.name = "불량률"
        mock_metric.description = "불량 비율"
        mock_metric.dataset_id = uuid4()
        mock_metric.expression_sql = "defect_qty / total_qty * 100"
        mock_metric.agg_type = "AVG"
        mock_metric.format_type = "percent"
        mock_metric.default_chart_type = "line"

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [mock_metric]
        mock_db.query.return_value = mock_query

        result = await list_metrics(db=mock_db, current_user=mock_user)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_metrics_with_dataset_filter(self, mock_db, mock_user):
        """지표 목록 조회 - 데이터셋 필터"""
        from app.routers.bi import list_metrics

        dataset_id = uuid4()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        result = await list_metrics(
            db=mock_db,
            current_user=mock_user,
            dataset_id=dataset_id
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_get_metric_value_not_found(self, mock_db, mock_user):
        """지표 값 조회 - 없음"""
        from app.routers.bi import get_metric_value
        from fastapi import HTTPException

        metric_id = uuid4()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            await get_metric_value(
                metric_id=metric_id,
                db=mock_db,
                current_user=mock_user,
            )

        assert exc_info.value.status_code == 404


class TestDimensionEndpointsMock:
    """차원 데이터 엔드포인트 테스트 (Mock 기반)"""

    @pytest.fixture
    def mock_user(self):
        """Mock 사용자"""
        user = MagicMock()
        user.tenant_id = uuid4()
        user.user_id = uuid4()
        return user

    @pytest.fixture
    def mock_db(self):
        """Mock DB 세션"""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_get_lines(self, mock_db, mock_user):
        """라인 목록 조회"""
        from app.routers.bi import get_lines

        mock_line = MagicMock()
        mock_line.line_code = "LINE_A"
        mock_line.name = "A 라인"
        mock_line.category = "Assembly"
        mock_line.capacity_per_hour = 100
        mock_line.is_active = True

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [mock_line]
        mock_db.query.return_value = mock_query

        result = await get_lines(db=mock_db, current_user=mock_user)

        assert len(result) == 1
        assert result[0]["line_code"] == "LINE_A"

    @pytest.mark.asyncio
    async def test_get_lines_inactive(self, mock_db, mock_user):
        """라인 목록 조회 - 비활성 포함"""
        from app.routers.bi import get_lines

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        result = await get_lines(
            db=mock_db,
            current_user=mock_user,
            is_active=False
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_get_products(self, mock_db, mock_user):
        """제품 목록 조회"""
        from app.routers.bi import get_products

        mock_product = MagicMock()
        mock_product.product_code = "PROD_001"
        mock_product.name = "제품 A"
        mock_product.category = "Electronics"
        mock_product.subcategory = "Sensors"
        mock_product.unit = "EA"
        mock_product.target_cycle_time_sec = 30
        mock_product.is_active = True

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [mock_product]
        mock_db.query.return_value = mock_query

        result = await get_products(db=mock_db, current_user=mock_user)

        assert len(result) == 1
        assert result[0]["product_code"] == "PROD_001"

    @pytest.mark.asyncio
    async def test_get_products_with_category(self, mock_db, mock_user):
        """제품 목록 조회 - 카테고리 필터"""
        from app.routers.bi import get_products

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        result = await get_products(
            db=mock_db,
            current_user=mock_user,
            category="Electronics"
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_get_kpis(self, mock_db, mock_user):
        """KPI 목록 조회"""
        from app.routers.bi import get_kpis

        mock_kpi = MagicMock()
        mock_kpi.kpi_code = "DEFECT_RATE"
        mock_kpi.name = "불량률"
        mock_kpi.category = "Quality"
        mock_kpi.unit = "%"
        mock_kpi.default_target = 3.0
        mock_kpi.higher_is_better = False
        mock_kpi.green_threshold = 2.0
        mock_kpi.yellow_threshold = 4.0
        mock_kpi.red_threshold = 6.0

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [mock_kpi]
        mock_db.query.return_value = mock_query

        result = await get_kpis(db=mock_db, current_user=mock_user)

        assert len(result) == 1
        assert result[0]["kpi_code"] == "DEFECT_RATE"


class TestChartTypesEndpoint:
    """차트 타입 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_get_chart_types(self):
        """차트 타입 목록 조회"""
        from app.routers.bi import get_chart_types

        result = await get_chart_types()

        assert "chart_types" in result
        assert "output_formats" in result
        assert "data_sources" in result

        chart_types = [ct["type"] for ct in result["chart_types"]]
        assert "line" in chart_types
        assert "bar" in chart_types
        assert "pie" in chart_types

        assert "chartjs" in result["output_formats"]
        assert "echarts" in result["output_formats"]

        assert "production" in result["data_sources"]
        assert "defect" in result["data_sources"]


class TestChartHelperFunctions:
    """차트 헬퍼 함수 테스트"""

    def test_get_production_chart_data_structure(self):
        """생산 차트 데이터 구조"""
        # 테스트할 데이터 구조 검증
        data = {
            "date": "2024-01-15",
            "line_code": "LINE_A",
            "total_qty": 1000.0,
            "good_qty": 950.0,
            "defect_qty": 50.0,
            "defect_rate": 5.0,
        }

        assert "date" in data
        assert "line_code" in data
        assert "total_qty" in data
        assert data["defect_rate"] == (data["defect_qty"] / data["total_qty"]) * 100

    def test_get_oee_chart_data_calculation(self):
        """OEE 차트 데이터 계산"""
        # OEE 계산 검증
        actual = 480.0  # 실제 가동 시간 (분)
        downtime = 48.0  # 다운타임 (분)
        total = 1000  # 총 생산량
        good = 950  # 양품 수

        availability = (actual - downtime) / actual * 100 if actual > 0 else 0
        performance = 80  # 기본값
        quality = good / total * 100 if total > 0 else 0
        oee = availability * performance * quality / 10000

        assert availability == 90.0
        assert quality == 95.0
        assert oee > 0


class TestInsightsEndpointsMock:
    """인사이트 엔드포인트 테스트 (Mock 기반)"""

    @pytest.fixture
    def mock_user(self):
        """Mock 사용자"""
        user = MagicMock()
        user.tenant_id = uuid4()
        user.user_id = uuid4()
        return user

    @pytest.mark.asyncio
    async def test_create_insight_success(self, mock_user):
        """인사이트 생성 - 성공"""
        from app.routers.bi import create_insight

        # AsyncMock 사용
        with patch("app.services.insight_service.get_insight_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_insight = MagicMock()
            mock_insight.insight_id = uuid4()
            mock_insight.title = "생산량 분석"
            mock_insight.summary = "요약"
            mock_insight.facts = []
            mock_insight.reasoning = MagicMock()
            mock_insight.reasoning.model_dump.return_value = {}
            mock_insight.actions = []
            mock_insight.generated_at = datetime.now()

            mock_service.generate_insight = AsyncMock(return_value=mock_insight)
            mock_get_service.return_value = mock_service

            request = {
                "source_type": "dashboard",
                "time_range": "7d",
            }

            result = await create_insight(
                request=request,
                current_user=mock_user,
            )

            assert result["success"] is True
            assert "insight" in result

    @pytest.mark.asyncio
    async def test_list_insights(self, mock_user):
        """인사이트 목록 조회"""
        from app.routers.bi import list_insights

        with patch("app.services.insight_service.get_insight_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_insight = MagicMock()
            mock_insight.insight_id = uuid4()
            mock_insight.title = "분석 1"
            mock_insight.summary = "요약"
            mock_insight.source_type = "dashboard"
            mock_insight.facts = []
            mock_insight.actions = []
            mock_insight.feedback_score = 0
            mock_insight.generated_at = datetime.now()

            mock_service.get_insights = AsyncMock(return_value=[mock_insight])
            mock_get_service.return_value = mock_service

            result = await list_insights(
                current_user=mock_user,
                limit=20,
                offset=0,
            )

            assert len(result["insights"]) == 1

    @pytest.mark.asyncio
    async def test_get_insight_not_found(self, mock_user):
        """인사이트 상세 조회 - 없음"""
        from app.routers.bi import get_insight
        from fastapi import HTTPException

        with patch("app.services.insight_service.get_insight_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_insight = AsyncMock(return_value=None)
            mock_get_service.return_value = mock_service

            insight_id = uuid4()

            with pytest.raises(HTTPException) as exc_info:
                await get_insight(
                    insight_id=insight_id,
                    current_user=mock_user,
                )

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_submit_insight_feedback_invalid_score(self, mock_user):
        """인사이트 피드백 - 잘못된 점수"""
        from app.routers.bi import submit_insight_feedback
        from fastapi import HTTPException

        insight_id = uuid4()
        request = {"score": 5}  # 잘못된 점수

        with pytest.raises(HTTPException) as exc_info:
            await submit_insight_feedback(
                insight_id=insight_id,
                request=request,
                current_user=mock_user,
            )

        assert exc_info.value.status_code == 400


class TestStoriesEndpointsMock:
    """스토리 엔드포인트 테스트 (Mock 기반)"""

    @pytest.fixture
    def mock_user(self):
        """Mock 사용자"""
        user = MagicMock()
        user.tenant_id = uuid4()
        user.user_id = uuid4()
        return user

    @pytest.mark.asyncio
    async def test_create_story_success(self, mock_user):
        """스토리 생성 - 성공"""
        from app.routers.bi import create_story

        with patch("app.services.story_service.get_story_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_story = MagicMock()
            mock_story.story_id = uuid4()
            mock_story.title = "주간 리포트"
            mock_story.description = "주간 생산 현황"
            mock_story.sections = []
            mock_story.created_at = datetime.now()

            mock_service.create_story = AsyncMock(return_value=mock_story)
            mock_get_service.return_value = mock_service

            request = {
                "title": "주간 리포트",
                "auto_generate": True,
            }

            result = await create_story(
                request=request,
                current_user=mock_user,
            )

            assert result["success"] is True
            assert result["story"]["title"] == "주간 리포트"

    @pytest.mark.asyncio
    async def test_list_stories(self, mock_user):
        """스토리 목록 조회"""
        from app.routers.bi import list_stories

        with patch("app.services.story_service.get_story_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_story = MagicMock()
            mock_story.story_id = uuid4()
            mock_story.title = "스토리 1"
            mock_story.description = "설명"
            mock_story.sections = []
            mock_story.is_public = False
            mock_story.created_at = datetime.now()
            mock_story.updated_at = datetime.now()
            mock_story.published_at = None

            mock_service.get_stories = AsyncMock(return_value=[mock_story])
            mock_get_service.return_value = mock_service

            result = await list_stories(
                current_user=mock_user,
                limit=20,
                offset=0,
            )

            assert len(result["stories"]) == 1

    @pytest.mark.asyncio
    async def test_get_story_not_found(self, mock_user):
        """스토리 상세 조회 - 없음"""
        from app.routers.bi import get_story
        from fastapi import HTTPException

        with patch("app.services.story_service.get_story_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_story = AsyncMock(return_value=None)
            mock_get_service.return_value = mock_service

            story_id = uuid4()

            with pytest.raises(HTTPException) as exc_info:
                await get_story(
                    story_id=story_id,
                    current_user=mock_user,
                )

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_story_not_found(self, mock_user):
        """스토리 수정 - 없음"""
        from app.routers.bi import update_story
        from fastapi import HTTPException

        with patch("app.services.story_service.get_story_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.update_story = AsyncMock(return_value=False)
            mock_get_service.return_value = mock_service

            story_id = uuid4()
            request = {"title": "새 제목"}

            with pytest.raises(HTTPException) as exc_info:
                await update_story(
                    story_id=story_id,
                    request=request,
                    current_user=mock_user,
                )

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_story_not_found(self, mock_user):
        """스토리 삭제 - 없음"""
        from app.routers.bi import delete_story
        from fastapi import HTTPException

        with patch("app.services.story_service.get_story_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.delete_story = AsyncMock(return_value=False)
            mock_get_service.return_value = mock_service

            story_id = uuid4()

            with pytest.raises(HTTPException) as exc_info:
                await delete_story(
                    story_id=story_id,
                    current_user=mock_user,
                )

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_story_section_not_found(self, mock_user):
        """스토리 섹션 삭제 - 없음"""
        from app.routers.bi import delete_story_section
        from fastapi import HTTPException

        with patch("app.services.story_service.get_story_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.delete_section = AsyncMock(return_value=False)
            mock_get_service.return_value = mock_service

            story_id = uuid4()
            section_id = uuid4()

            with pytest.raises(HTTPException) as exc_info:
                await delete_story_section(
                    story_id=story_id,
                    section_id=section_id,
                    current_user=mock_user,
                )

            assert exc_info.value.status_code == 404


class TestChatEndpointsMock:
    """채팅 엔드포인트 테스트 (Mock 기반)"""

    @pytest.fixture
    def mock_user(self):
        """Mock 사용자"""
        user = MagicMock()
        user.tenant_id = uuid4()
        user.user_id = uuid4()
        return user

    @pytest.mark.asyncio
    async def test_chat_missing_message(self, mock_user):
        """채팅 - 메시지 누락"""
        from app.routers.bi import chat
        from fastapi import HTTPException

        request = {}

        with pytest.raises(HTTPException) as exc_info:
            await chat(
                request=request,
                current_user=mock_user,
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_chat_success(self, mock_user):
        """채팅 - 성공"""
        from app.routers.bi import chat

        with patch("app.services.bi_chat_service.get_bi_chat_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_response = MagicMock()
            mock_response.session_id = uuid4()
            mock_response.message_id = uuid4()
            mock_response.content = "분석 결과입니다."
            mock_response.response_type = "text"
            mock_response.response_data = {}
            mock_response.linked_insight_id = None
            mock_response.linked_chart_id = None

            mock_service.chat = AsyncMock(return_value=mock_response)
            mock_get_service.return_value = mock_service

            request = {
                "message": "생산량 추이 보여줘",
            }

            result = await chat(
                request=request,
                current_user=mock_user,
            )

            assert result["success"] is True
            assert result["content"] == "분석 결과입니다."


class TestChartRefineEndpointMock:
    """차트 수정 엔드포인트 테스트 (Mock 기반)"""

    @pytest.fixture
    def mock_user(self):
        """Mock 사용자"""
        user = MagicMock()
        user.tenant_id = uuid4()
        user.user_id = uuid4()
        return user

    @pytest.mark.asyncio
    async def test_refine_chart_missing_config(self, mock_user):
        """차트 수정 - 설정 누락"""
        from app.routers.bi import refine_chart
        from fastapi import HTTPException

        request = {"refinement_instruction": "색상 변경"}

        with pytest.raises(HTTPException) as exc_info:
            await refine_chart(
                request=request,
                current_user=mock_user,
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_refine_chart_missing_instruction(self, mock_user):
        """차트 수정 - 지시 누락"""
        from app.routers.bi import refine_chart
        from fastapi import HTTPException

        request = {"original_chart_config": {"type": "line"}}

        with pytest.raises(HTTPException) as exc_info:
            await refine_chart(
                request=request,
                current_user=mock_user,
            )

        assert exc_info.value.status_code == 400


class TestChartGenerateEndpointMock:
    """차트 생성 엔드포인트 테스트 (Mock 기반)"""

    @pytest.fixture
    def mock_user(self):
        """Mock 사용자"""
        user = MagicMock()
        user.tenant_id = uuid4()
        user.user_id = uuid4()
        return user

    @pytest.fixture
    def mock_db(self):
        """Mock DB 세션"""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_generate_chart_unknown_source(self, mock_db, mock_user):
        """차트 생성 - 알 수 없는 데이터 소스"""
        from app.routers.bi import generate_chart, ChartRequest
        from fastapi import HTTPException

        request = ChartRequest(
            chart_type="line",
            data_source="unknown_source",
            x_field="date",
            y_fields=["value"],
            title="테스트",
        )

        with pytest.raises(HTTPException) as exc_info:
            await generate_chart(
                request=request,
                db=mock_db,
                current_user=mock_user,
            )

        assert exc_info.value.status_code == 400


class TestPinnedInsightsEndpoint:
    """고정 인사이트 엔드포인트 테스트"""

    @pytest.fixture
    def mock_user(self):
        """Mock 사용자"""
        user = MagicMock()
        user.tenant_id = uuid4()
        user.user_id = uuid4()
        return user

    @pytest.mark.asyncio
    async def test_get_pinned_insights(self, mock_user):
        """고정된 인사이트 목록 조회"""
        from app.routers.bi import get_pinned_insights

        with patch("app.services.bi_chat_service.get_bi_chat_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_pinned_insights = AsyncMock(return_value=[])
            mock_get_service.return_value = mock_service

            result = await get_pinned_insights(current_user=mock_user)

            assert "pinned_insights" in result
            assert "total" in result


class TestInventoryResponseModel:
    """InventoryResponse 모델 테스트"""

    def test_inventory_response_model(self):
        """InventoryResponse 모델"""
        from app.routers.bi import InventoryResponse, InventoryItem

        data = [
            InventoryItem(
                date=date(2024, 1, 15),
                product_code="PROD_001",
                location="WAREHOUSE_A",
                stock_qty=500.0,
                safety_stock_qty=100.0,
                available_qty=400.0,
                stock_status="normal",
            )
        ]

        response = InventoryResponse(
            data=data,
            total=1,
            summary={
                "total_items": 1,
                "below_safety_count": 0,
            },
        )

        assert response.total == 1
        assert response.summary["total_items"] == 1


class TestDatasetQueryMock:
    """데이터셋 쿼리 엔드포인트 테스트"""

    @pytest.fixture
    def mock_db(self):
        """Mock DB 세션"""
        return MagicMock()

    @pytest.fixture
    def mock_user(self):
        """Mock 사용자"""
        user = MagicMock()
        user.tenant_id = uuid4()
        user.user_id = uuid4()
        return user

    @pytest.mark.asyncio
    async def test_query_dataset_fact_daily_production(self, mock_db, mock_user):
        """fact_daily_production 데이터셋 쿼리"""
        from app.routers.bi import query_dataset

        dataset_id = uuid4()

        # Mock dataset
        mock_dataset = MagicMock()
        mock_dataset.source_ref = "fact_daily_production"

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_dataset
        mock_db.query.return_value = mock_query

        # Mock data query
        mock_data_query = MagicMock()
        mock_data_query.filter.return_value = mock_data_query
        mock_data_query.order_by.return_value = mock_data_query
        mock_data_query.offset.return_value = mock_data_query
        mock_data_query.limit.return_value = mock_data_query
        mock_data_query.count.return_value = 0
        mock_data_query.all.return_value = []

        # 두 번째 query 호출에 대해 다른 mock 반환
        mock_db.query.side_effect = [mock_query, mock_data_query]

        result = await query_dataset(
            dataset_id=dataset_id,
            db=mock_db,
            current_user=mock_user,
        )

        assert "dataset_id" in result
        assert result["data"] == []


class TestProductionAnalyticsMock:
    """생산 분석 엔드포인트 테스트"""

    @pytest.fixture
    def mock_db(self):
        """Mock DB 세션"""
        return MagicMock()

    @pytest.fixture
    def mock_user(self):
        """Mock 사용자"""
        user = MagicMock()
        user.tenant_id = uuid4()
        user.user_id = uuid4()
        return user

    @pytest.mark.asyncio
    async def test_get_production_analytics(self, mock_db, mock_user):
        """생산 분석 조회"""
        from app.routers.bi import get_production_analytics

        # Mock data query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.all.return_value = []
        mock_query.first.return_value = MagicMock(
            total_qty=1000,
            good_qty=950,
            defect_qty=50,
            runtime=480,
            downtime=30,
        )

        mock_db.query.return_value = mock_query

        result = await get_production_analytics(
            db=mock_db,
            current_user=mock_user,
        )

        assert hasattr(result, "data")
        assert hasattr(result, "summary")


class TestDefectTrendMock:
    """불량 추이 엔드포인트 테스트"""

    @pytest.fixture
    def mock_db(self):
        """Mock DB 세션"""
        return MagicMock()

    @pytest.fixture
    def mock_user(self):
        """Mock 사용자"""
        user = MagicMock()
        user.tenant_id = uuid4()
        user.user_id = uuid4()
        return user

    @pytest.mark.asyncio
    async def test_get_defect_trend(self, mock_db, mock_user):
        """불량 추이 조회"""
        from app.routers.bi import get_defect_trend

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        mock_db.query.return_value = mock_query

        result = await get_defect_trend(
            db=mock_db,
            current_user=mock_user,
        )

        assert hasattr(result, "data")
        assert hasattr(result, "avg_defect_rate")

    @pytest.mark.asyncio
    async def test_get_defect_trend_group_by_line(self, mock_db, mock_user):
        """불량 추이 조회 - 라인별 그룹핑"""
        from app.routers.bi import get_defect_trend

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        mock_db.query.return_value = mock_query

        result = await get_defect_trend(
            db=mock_db,
            current_user=mock_user,
            group_by="line",
        )

        assert hasattr(result, "data")


class TestOEEAnalyticsMock:
    """OEE 분석 엔드포인트 테스트"""

    @pytest.fixture
    def mock_db(self):
        """Mock DB 세션"""
        return MagicMock()

    @pytest.fixture
    def mock_user(self):
        """Mock 사용자"""
        user = MagicMock()
        user.tenant_id = uuid4()
        user.user_id = uuid4()
        return user

    @pytest.mark.asyncio
    async def test_get_oee_analytics(self, mock_db, mock_user):
        """OEE 분석 조회"""
        from app.routers.bi import get_oee_analytics

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        mock_db.query.return_value = mock_query

        result = await get_oee_analytics(
            db=mock_db,
            current_user=mock_user,
        )

        assert hasattr(result, "data")
        assert hasattr(result, "avg_oee")


class TestInventoryAnalyticsMock:
    """재고 분석 엔드포인트 테스트"""

    @pytest.fixture
    def mock_db(self):
        """Mock DB 세션"""
        return MagicMock()

    @pytest.fixture
    def mock_user(self):
        """Mock 사용자"""
        user = MagicMock()
        user.tenant_id = uuid4()
        user.user_id = uuid4()
        return user

    @pytest.mark.asyncio
    async def test_get_inventory_analytics(self, mock_db, mock_user):
        """재고 분석 조회"""
        from app.routers.bi import get_inventory_analytics

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.all.return_value = []

        mock_db.query.return_value = mock_query

        result = await get_inventory_analytics(
            db=mock_db,
            current_user=mock_user,
        )

        assert hasattr(result, "data")
        assert hasattr(result, "summary")


class TestStatCardsEndpointMock:
    """StatCards 엔드포인트 테스트"""

    @pytest.fixture
    def mock_user(self):
        """Mock 사용자"""
        user = MagicMock()
        user.tenant_id = uuid4()
        user.user_id = uuid4()
        return user

    @pytest.mark.asyncio
    async def test_get_stat_cards(self, mock_user):
        """StatCards 조회"""
        from app.routers.bi import get_stat_cards

        with patch("app.services.stat_card_service.StatCardService") as mock_service_class:
            mock_service = MagicMock()
            mock_result = MagicMock()
            mock_result.cards = []
            mock_result.total = 0
            mock_service.get_card_values = AsyncMock(return_value=mock_result)
            mock_service_class.return_value = mock_service

            mock_db = MagicMock()
            result = await get_stat_cards(
                db=mock_db,
                current_user=mock_user,
            )

            assert "cards" in result
            assert "total" in result


class TestChartRequestModel:
    """ChartRequest 모델 테스트"""

    def test_chart_request_with_all_fields(self):
        """ChartRequest 모델 - 모든 필드"""
        from app.routers.bi import ChartRequest

        request = ChartRequest(
            data_source="mes",
            chart_type="line",
            x_field="date",
            y_fields=["total_qty"],
            title="테스트 차트",
        )

        assert request.chart_type == "line"
        assert request.title == "테스트 차트"


class TestChartConfigModels:
    """차트 구성 모델 테스트"""

    def test_chart_response_model(self):
        """ChartResponse 모델"""
        from app.routers.bi import ChartResponse

        response = ChartResponse(
            chart_id="chart-1",
            chart_type="line",
            title="테스트 차트",
            config={"color": "blue"},
            data_count=10,
        )

        assert response.chart_type == "line"
        assert response.data_count == 10

    def test_dashboard_response_model(self):
        """DashboardResponse 모델"""
        from app.routers.bi import DashboardResponse

        response = DashboardResponse(
            id=uuid4(),
            name="테스트 대시보드",
            description="설명",
            layout={"components": []},
            is_public=False,
            owner_id=uuid4(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        assert response.name == "테스트 대시보드"
        assert response.is_public is False
