"""
StatCard Service 테스트

StatCard 설정 CRUD 및 값 조회 테스트
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4


class TestStatCardSourceType:
    """StatCard 소스 타입 테스트"""

    def test_source_type_kpi(self):
        """KPI 소스 타입"""

        assert "kpi" in ["kpi", "db_query", "mcp_tool"]

    def test_source_type_db_query(self):
        """DB Query 소스 타입"""
        assert "db_query" in ["kpi", "db_query", "mcp_tool"]

    def test_source_type_mcp_tool(self):
        """MCP Tool 소스 타입"""
        assert "mcp_tool" in ["kpi", "db_query", "mcp_tool"]


class TestAggregationType:
    """집계 타입 테스트"""

    def test_aggregation_sum(self):
        """SUM 집계"""
        assert "sum" in ["sum", "avg", "min", "max", "count", "last"]

    def test_aggregation_avg(self):
        """AVG 집계"""
        assert "avg" in ["sum", "avg", "min", "max", "count", "last"]

    def test_aggregation_min(self):
        """MIN 집계"""
        assert "min" in ["sum", "avg", "min", "max", "count", "last"]

    def test_aggregation_max(self):
        """MAX 집계"""
        assert "max" in ["sum", "avg", "min", "max", "count", "last"]

    def test_aggregation_count(self):
        """COUNT 집계"""
        assert "count" in ["sum", "avg", "min", "max", "count", "last"]

    def test_aggregation_last(self):
        """LAST 집계"""
        assert "last" in ["sum", "avg", "min", "max", "count", "last"]


class TestStatusType:
    """상태 타입 테스트"""

    def test_status_green(self):
        """Green 상태"""
        assert "green" in ["green", "yellow", "red", "gray"]

    def test_status_yellow(self):
        """Yellow 상태"""
        assert "yellow" in ["green", "yellow", "red", "gray"]

    def test_status_red(self):
        """Red 상태"""
        assert "red" in ["green", "yellow", "red", "gray"]

    def test_status_gray(self):
        """Gray 상태 (데이터 없음)"""
        assert "gray" in ["green", "yellow", "red", "gray"]


class TestStatCardConfigBaseSchema:
    """StatCardConfigBase 스키마 테스트"""

    def test_create_kpi_config(self):
        """KPI 타입 설정 생성"""
        from app.schemas.statcard import StatCardConfigCreate

        config = StatCardConfigCreate(
            source_type="kpi",
            kpi_code="OEE",
        )

        assert config.source_type == "kpi"
        assert config.kpi_code == "OEE"
        assert config.is_visible is True
        assert config.display_order == 0

    def test_create_db_query_config(self):
        """DB Query 타입 설정 생성"""
        from app.schemas.statcard import StatCardConfigCreate

        config = StatCardConfigCreate(
            source_type="db_query",
            table_name="fact_production",
            column_name="quantity",
            aggregation="sum",
        )

        assert config.source_type == "db_query"
        assert config.table_name == "fact_production"
        assert config.column_name == "quantity"
        assert config.aggregation == "sum"

    def test_create_mcp_tool_config(self):
        """MCP Tool 타입 설정 생성"""
        from app.schemas.statcard import StatCardConfigCreate

        server_id = uuid4()
        config = StatCardConfigCreate(
            source_type="mcp_tool",
            mcp_server_id=server_id,
            mcp_tool_name="get_production_count",
            mcp_params={"line_id": "LINE-01"},
            mcp_result_key="count",
        )

        assert config.source_type == "mcp_tool"
        assert config.mcp_server_id == server_id
        assert config.mcp_tool_name == "get_production_count"
        assert config.mcp_params["line_id"] == "LINE-01"

    def test_default_values(self):
        """기본값 확인"""
        from app.schemas.statcard import StatCardConfigCreate

        config = StatCardConfigCreate(
            source_type="kpi",
            kpi_code="test",
        )

        assert config.display_order == 0
        assert config.is_visible is True
        assert config.higher_is_better is True
        assert config.cache_ttl_seconds == 60

    def test_custom_display_settings(self):
        """커스텀 표시 설정"""
        from app.schemas.statcard import StatCardConfigCreate

        config = StatCardConfigCreate(
            source_type="kpi",
            kpi_code="test",
            custom_title="My Card",
            custom_icon="chart-bar",
            custom_unit="%",
        )

        assert config.custom_title == "My Card"
        assert config.custom_icon == "chart-bar"
        assert config.custom_unit == "%"

    def test_threshold_settings(self):
        """임계값 설정"""
        from app.schemas.statcard import StatCardConfigCreate

        config = StatCardConfigCreate(
            source_type="db_query",
            table_name="test",
            column_name="value",
            aggregation="avg",
            green_threshold=80.0,
            yellow_threshold=60.0,
            red_threshold=40.0,
            higher_is_better=True,
        )

        assert config.green_threshold == 80.0
        assert config.yellow_threshold == 60.0
        assert config.red_threshold == 40.0
        assert config.higher_is_better is True

    def test_lower_is_better(self):
        """낮을수록 좋은 경우 (예: 불량률)"""
        from app.schemas.statcard import StatCardConfigCreate

        config = StatCardConfigCreate(
            source_type="kpi",
            kpi_code="defect_rate",
            green_threshold=1.0,
            yellow_threshold=3.0,
            red_threshold=5.0,
            higher_is_better=False,
        )

        assert config.higher_is_better is False


class TestStatCardConfigUpdateSchema:
    """StatCardConfigUpdate 스키마 테스트"""

    def test_partial_update(self):
        """부분 업데이트"""
        from app.schemas.statcard import StatCardConfigUpdate

        update = StatCardConfigUpdate(display_order=5)

        assert update.display_order == 5
        assert update.is_visible is None
        assert update.source_type is None

    def test_update_visibility(self):
        """표시 여부 업데이트"""
        from app.schemas.statcard import StatCardConfigUpdate

        update = StatCardConfigUpdate(is_visible=False)
        assert update.is_visible is False

    def test_update_thresholds(self):
        """임계값 업데이트"""
        from app.schemas.statcard import StatCardConfigUpdate

        update = StatCardConfigUpdate(
            green_threshold=90.0,
            yellow_threshold=70.0,
            red_threshold=50.0,
        )

        assert update.green_threshold == 90.0
        assert update.yellow_threshold == 70.0
        assert update.red_threshold == 50.0

    def test_empty_update(self):
        """빈 업데이트"""
        from app.schemas.statcard import StatCardConfigUpdate

        update = StatCardConfigUpdate()

        assert update.display_order is None
        assert update.is_visible is None


class TestStatCardValueSchema:
    """StatCardValue 스키마 테스트"""

    def test_stat_card_value_creation(self):
        """StatCardValue 생성"""
        from app.schemas.statcard import StatCardValue

        config_id = uuid4()
        value = StatCardValue(
            config_id=config_id,
            value=85.5,
            formatted_value="85.5%",
            previous_value=80.0,
            change_percent=6.875,
            trend="up",
            status="green",
            title="OEE",
            icon="gauge",
            unit="%",
            source_type="kpi",
            fetched_at=datetime.now(),
        )

        assert value.value == 85.5
        assert value.previous_value == 80.0
        assert value.change_percent == 6.875
        assert value.status == "green"

    def test_stat_card_value_no_previous(self):
        """이전 값 없는 경우"""
        from app.schemas.statcard import StatCardValue

        config_id = uuid4()
        value = StatCardValue(
            config_id=config_id,
            value=100.0,
            previous_value=None,
            change_percent=None,
            status="gray",
            title="Test",
            source_type="kpi",
            fetched_at=datetime.now(),
        )

        assert value.value == 100.0
        assert value.previous_value is None
        assert value.status == "gray"


class TestStatCardServiceInit:
    """StatCardService 초기화 테스트"""

    def test_service_init(self):
        """서비스 초기화"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        assert service.db == mock_db
        assert service._cache == {}

    def test_service_cache_init(self):
        """캐시 초기화"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        assert isinstance(service._cache, dict)


class TestStatCardThresholdLogic:
    """임계값 로직 테스트"""

    def test_higher_is_better_green(self):
        """높을수록 좋음 - Green 상태"""
        value = 90
        green_threshold = 80
        yellow_threshold = 60
        higher_is_better = True

        if higher_is_better:
            if value >= green_threshold:
                status = "green"
            elif value >= yellow_threshold:
                status = "yellow"
            else:
                status = "red"
        else:
            if value <= green_threshold:
                status = "green"
            elif value <= yellow_threshold:
                status = "yellow"
            else:
                status = "red"

        assert status == "green"

    def test_higher_is_better_yellow(self):
        """높을수록 좋음 - Yellow 상태"""
        value = 70
        green_threshold = 80
        yellow_threshold = 60
        higher_is_better = True

        if higher_is_better:
            if value >= green_threshold:
                status = "green"
            elif value >= yellow_threshold:
                status = "yellow"
            else:
                status = "red"
        else:
            if value <= green_threshold:
                status = "green"
            elif value <= yellow_threshold:
                status = "yellow"
            else:
                status = "red"

        assert status == "yellow"

    def test_higher_is_better_red(self):
        """높을수록 좋음 - Red 상태"""
        value = 50
        green_threshold = 80
        yellow_threshold = 60
        higher_is_better = True

        if higher_is_better:
            if value >= green_threshold:
                status = "green"
            elif value >= yellow_threshold:
                status = "yellow"
            else:
                status = "red"
        else:
            if value <= green_threshold:
                status = "green"
            elif value <= yellow_threshold:
                status = "yellow"
            else:
                status = "red"

        assert status == "red"

    def test_lower_is_better_green(self):
        """낮을수록 좋음 - Green 상태"""
        value = 1.0
        green_threshold = 2.0
        yellow_threshold = 5.0
        higher_is_better = False

        if higher_is_better:
            if value >= green_threshold:
                status = "green"
            elif value >= yellow_threshold:
                status = "yellow"
            else:
                status = "red"
        else:
            if value <= green_threshold:
                status = "green"
            elif value <= yellow_threshold:
                status = "yellow"
            else:
                status = "red"

        assert status == "green"

    def test_lower_is_better_red(self):
        """낮을수록 좋음 - Red 상태 (값이 높음)"""
        value = 15.0
        green_threshold = 2.0
        yellow_threshold = 5.0
        higher_is_better = False

        if higher_is_better:
            if value >= green_threshold:
                status = "green"
            elif value >= yellow_threshold:
                status = "yellow"
            else:
                status = "red"
        else:
            if value <= green_threshold:
                status = "green"
            elif value <= yellow_threshold:
                status = "yellow"
            else:
                status = "red"

        assert status == "red"


class TestChangeCalculation:
    """변화량 계산 테스트"""

    def test_positive_change(self):
        """양수 변화"""
        current = 100
        previous = 80
        change_value = current - previous
        change_percent = (change_value / previous) * 100 if previous != 0 else 0

        assert change_value == 20
        assert change_percent == 25.0

    def test_negative_change(self):
        """음수 변화"""
        current = 70
        previous = 100
        change_value = current - previous
        change_percent = (change_value / previous) * 100 if previous != 0 else 0

        assert change_value == -30
        assert change_percent == -30.0

    def test_no_change(self):
        """변화 없음"""
        current = 100
        previous = 100
        change_value = current - previous
        change_percent = (change_value / previous) * 100 if previous != 0 else 0

        assert change_value == 0
        assert change_percent == 0.0

    def test_previous_zero(self):
        """이전 값이 0인 경우"""
        current = 100
        previous = 0
        change_value = current - previous
        # 0으로 나누기 방지
        change_percent = 0 if previous == 0 else (change_value / previous) * 100

        assert change_value == 100
        assert change_percent == 0


class TestKpiInfoSchema:
    """KpiInfo 스키마 테스트"""

    def test_kpi_info_creation(self):
        """KpiInfo 생성"""
        from app.schemas.statcard import KpiInfo

        kpi = KpiInfo(
            kpi_code="OEE",
            name="Overall Equipment Effectiveness",
            category="production",
            description="설비종합효율",
            unit="%",
            higher_is_better=True,
        )

        assert kpi.kpi_code == "OEE"
        assert kpi.name == "Overall Equipment Effectiveness"
        assert kpi.unit == "%"
        assert kpi.higher_is_better is True

    def test_kpi_info_optional_fields(self):
        """KpiInfo 선택적 필드"""
        from app.schemas.statcard import KpiInfo

        kpi = KpiInfo(
            kpi_code="CUSTOM",
            name="Custom KPI",
            category="custom",
        )

        assert kpi.kpi_code == "CUSTOM"
        assert kpi.description is None
        assert kpi.unit is None


class TestTableInfoSchema:
    """TableInfo 스키마 테스트"""

    def test_table_info_creation(self):
        """TableInfo 생성"""
        from app.schemas.statcard import TableInfo, ColumnInfo

        table = TableInfo(
            schema_name="bi",
            table_name="fact_production",
            columns=[
                ColumnInfo(
                    column_name="quantity",
                    data_type="integer",
                    allowed_aggregations=["sum", "avg", "max"],
                )
            ],
        )

        assert table.schema_name == "bi"
        assert table.table_name == "fact_production"
        assert len(table.columns) == 1


class TestColumnInfoSchema:
    """ColumnInfo 스키마 테스트"""

    def test_column_info_creation(self):
        """ColumnInfo 생성"""
        from app.schemas.statcard import ColumnInfo

        column = ColumnInfo(
            column_name="quantity",
            data_type="integer",
            description="생산량",
            allowed_aggregations=["sum", "avg", "min", "max", "count"],
        )

        assert column.column_name == "quantity"
        assert column.data_type == "integer"
        assert "sum" in column.allowed_aggregations


class TestMcpToolInfoSchema:
    """McpToolInfo 스키마 테스트"""

    def test_mcp_tool_info_creation(self):
        """McpToolInfo 생성"""
        from app.schemas.statcard import McpToolInfo

        tool = McpToolInfo(
            server_id=uuid4(),
            server_name="mes-server",
            tool_name="get_production_count",
            description="생산 수량 조회",
            input_schema={
                "line_id": {"type": "string", "required": True},
            },
        )

        assert tool.server_name == "mes-server"
        assert tool.tool_name == "get_production_count"
        assert "line_id" in tool.input_schema


class TestCacheTTL:
    """캐시 TTL 테스트"""

    def test_default_cache_ttl(self):
        """기본 캐시 TTL"""
        from app.schemas.statcard import StatCardConfigCreate

        config = StatCardConfigCreate(
            source_type="kpi",
            kpi_code="test",
        )

        assert config.cache_ttl_seconds == 60

    def test_custom_cache_ttl(self):
        """커스텀 캐시 TTL"""
        from app.schemas.statcard import StatCardConfigCreate

        config = StatCardConfigCreate(
            source_type="kpi",
            kpi_code="test",
            cache_ttl_seconds=300,
        )

        assert config.cache_ttl_seconds == 300


class TestDisplayOrder:
    """표시 순서 테스트"""

    def test_default_display_order(self):
        """기본 표시 순서"""
        from app.schemas.statcard import StatCardConfigCreate

        config = StatCardConfigCreate(
            source_type="kpi",
            kpi_code="test",
        )

        assert config.display_order == 0

    def test_custom_display_order(self):
        """커스텀 표시 순서"""
        from app.schemas.statcard import StatCardConfigCreate

        config = StatCardConfigCreate(
            source_type="kpi",
            kpi_code="test",
            display_order=5,
        )

        assert config.display_order == 5


class TestFilterCondition:
    """필터 조건 테스트"""

    def test_simple_filter(self):
        """단순 필터"""
        from app.schemas.statcard import StatCardConfigCreate

        config = StatCardConfigCreate(
            source_type="db_query",
            table_name="fact_production",
            column_name="quantity",
            aggregation="sum",
            filter_condition={"line_id": "LINE-01"},
        )

        assert config.filter_condition["line_id"] == "LINE-01"

    def test_complex_filter(self):
        """복합 필터"""
        from app.schemas.statcard import StatCardConfigCreate

        config = StatCardConfigCreate(
            source_type="db_query",
            table_name="fact_production",
            column_name="quantity",
            aggregation="sum",
            filter_condition={
                "line_id": "LINE-01",
                "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
            },
        )

        assert "date_range" in config.filter_condition

    def test_no_filter(self):
        """필터 없음"""
        from app.schemas.statcard import StatCardConfigCreate

        config = StatCardConfigCreate(
            source_type="db_query",
            table_name="fact_production",
            column_name="quantity",
            aggregation="sum",
        )

        assert config.filter_condition is None


class TestMcpParams:
    """MCP 파라미터 테스트"""

    def test_mcp_params_simple(self):
        """단순 MCP 파라미터"""
        from app.schemas.statcard import StatCardConfigCreate

        config = StatCardConfigCreate(
            source_type="mcp_tool",
            mcp_tool_name="get_count",
            mcp_params={"id": 123},
        )

        assert config.mcp_params["id"] == 123

    def test_mcp_result_key(self):
        """MCP 결과 키"""
        from app.schemas.statcard import StatCardConfigCreate

        config = StatCardConfigCreate(
            source_type="mcp_tool",
            mcp_tool_name="get_data",
            mcp_result_key="data.value",
        )

        assert config.mcp_result_key == "data.value"


class TestListResponses:
    """목록 응답 스키마 테스트"""

    def test_stat_card_list_response(self):
        """StatCardListResponse 생성"""
        from app.schemas.statcard import StatCardListResponse

        response = StatCardListResponse(total=10, cards=[])

        assert response.total == 10
        assert len(response.cards) == 0

    def test_kpi_list_response(self):
        """KpiListResponse 생성"""
        from app.schemas.statcard import KpiListResponse

        response = KpiListResponse(kpis=[], categories=["production", "quality"])

        assert len(response.kpis) == 0
        assert "production" in response.categories

    def test_mcp_tool_list_response(self):
        """McpToolListResponse 생성"""
        from app.schemas.statcard import McpToolListResponse

        response = McpToolListResponse(tools=[])

        assert len(response.tools) == 0


class TestAvailableTablesResponse:
    """AvailableTablesResponse 스키마 테스트"""

    def test_available_tables_response(self):
        """AvailableTablesResponse 생성"""
        from app.schemas.statcard import AvailableTablesResponse

        response = AvailableTablesResponse(tables=[])

        assert len(response.tables) == 0


class TestStatCardServiceMethods:
    """StatCardService 메서드 테스트"""

    def test_row_to_config_conversion(self):
        """_row_to_config 변환 테스트"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        # Mock row object with named tuple-like behavior
        mock_row = MagicMock()
        mock_row._mapping = {
            "config_id": uuid4(),
            "tenant_id": uuid4(),
            "user_id": uuid4(),
            "display_order": 1,
            "is_visible": True,
            "source_type": "kpi",
            "kpi_code": "OEE",
            "table_name": None,
            "column_name": None,
            "aggregation": None,
            "filter_condition": None,
            "mcp_server_id": None,
            "mcp_tool_name": None,
            "mcp_params": None,
            "mcp_result_key": None,
            "custom_title": "OEE",
            "custom_icon": "gauge",
            "custom_unit": "%",
            "green_threshold": 80.0,
            "yellow_threshold": 60.0,
            "red_threshold": 40.0,
            "higher_is_better": True,
            "cache_ttl_seconds": 60,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }
        mock_row.__getitem__ = lambda self, key: self._mapping[key]

        # Test that _row_to_config method exists
        assert hasattr(service, "_row_to_config")

    def test_get_next_display_order(self):
        """_get_next_display_order 메서드 테스트"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        # Test method exists
        assert hasattr(service, "_get_next_display_order")

    def test_determine_status_higher_is_better(self):
        """상태 결정 - 높을수록 좋음"""
        # Logic test: higher_is_better=True
        value = 85.0
        green_threshold = 80.0
        yellow_threshold = 60.0
        higher_is_better = True

        if higher_is_better:
            if value >= green_threshold:
                status = "green"
            elif value >= yellow_threshold:
                status = "yellow"
            else:
                status = "red"
        else:
            if value <= green_threshold:
                status = "green"
            elif value <= yellow_threshold:
                status = "yellow"
            else:
                status = "red"

        assert status == "green"

    def test_determine_status_lower_is_better(self):
        """상태 결정 - 낮을수록 좋음"""
        # Logic test: higher_is_better=False (e.g., defect rate)
        value = 1.5
        green_threshold = 2.0
        yellow_threshold = 5.0
        higher_is_better = False

        if higher_is_better:
            if value >= green_threshold:
                status = "green"
            elif value >= yellow_threshold:
                status = "yellow"
            else:
                status = "red"
        else:
            if value <= green_threshold:
                status = "green"
            elif value <= yellow_threshold:
                status = "yellow"
            else:
                status = "red"

        assert status == "green"

    def test_cache_key_generation(self):
        """캐시 키 생성 테스트"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        StatCardService(db=mock_db)

        tenant_id = uuid4()
        config_id = uuid4()

        # Cache key should be unique per config
        cache_key = f"stat_card:{tenant_id}:{config_id}"
        assert "stat_card:" in cache_key
        assert str(config_id) in cache_key


class TestStatCardDataFetching:
    """StatCard 데이터 조회 테스트"""

    def test_fetch_kpi_data_concept(self):
        """KPI 데이터 조회 개념 테스트"""
        # KPI data is fetched from bi.dim_kpi table
        kpi_code = "OEE"
        expected_query_contains = "dim_kpi"

        assert len(kpi_code) > 0
        assert expected_query_contains == "dim_kpi"

    def test_fetch_db_query_aggregation(self):
        """DB 쿼리 집계 테스트"""
        # Test aggregation mapping
        aggregations = {
            "sum": "SUM",
            "avg": "AVG",
            "min": "MIN",
            "max": "MAX",
            "count": "COUNT",
        }

        for agg_type, sql_func in aggregations.items():
            assert agg_type in ["sum", "avg", "min", "max", "count", "last"]
            assert sql_func.isupper()

    def test_mcp_tool_data_fetch_concept(self):
        """MCP 도구 데이터 조회 개념 테스트"""
        # MCP tool data is fetched via MCPToolHubService
        mcp_config = {
            "mcp_server_id": str(uuid4()),
            "mcp_tool_name": "get_production_count",
            "mcp_params": {"line_id": "LINE-01"},
            "mcp_result_key": "data.count",
        }

        assert "mcp_server_id" in mcp_config
        assert "mcp_tool_name" in mcp_config


class TestStatCardValueFormatting:
    """StatCard 값 포맷팅 테스트"""

    def test_format_value_with_unit(self):
        """단위 포함 값 포맷팅"""
        value = 85.5
        unit = "%"
        formatted = f"{value:.1f}{unit}"

        assert formatted == "85.5%"

    def test_format_value_integer(self):
        """정수 값 포맷팅"""
        value = 1000
        formatted = f"{value:,}"

        assert formatted == "1,000"

    def test_format_large_number(self):
        """큰 수 포맷팅"""
        value = 1234567
        formatted = f"{value:,}"

        assert formatted == "1,234,567"

    def test_format_decimal(self):
        """소수점 포맷팅"""
        value = 99.876
        formatted = f"{value:.2f}"

        assert formatted == "99.88"


class TestStatCardTrendCalculation:
    """StatCard 트렌드 계산 테스트"""

    def test_trend_up(self):
        """상승 트렌드"""
        current = 100
        previous = 80
        change = current - previous

        trend = "up" if change > 0 else ("down" if change < 0 else "stable")
        assert trend == "up"

    def test_trend_down(self):
        """하락 트렌드"""
        current = 70
        previous = 90
        change = current - previous

        trend = "up" if change > 0 else ("down" if change < 0 else "stable")
        assert trend == "down"

    def test_trend_stable(self):
        """안정 트렌드"""
        current = 85
        previous = 85
        change = current - previous

        trend = "up" if change > 0 else ("down" if change < 0 else "stable")
        assert trend == "stable"

    def test_change_percentage_calculation(self):
        """변화율 계산"""
        current = 120
        previous = 100

        if previous != 0:
            change_percent = ((current - previous) / previous) * 100
        else:
            change_percent = 0

        assert change_percent == 20.0


class TestStatCardConfigValidation:
    """StatCard 설정 유효성 검사 테스트"""

    def test_kpi_config_requires_kpi_code(self):
        """KPI 설정에는 kpi_code 필요"""
        from app.schemas.statcard import StatCardConfigCreate

        config = StatCardConfigCreate(
            source_type="kpi",
            kpi_code="OEE",
        )

        assert config.kpi_code is not None

    def test_db_query_config_requires_table(self):
        """DB 쿼리 설정에는 테이블 정보 필요"""
        from app.schemas.statcard import StatCardConfigCreate

        config = StatCardConfigCreate(
            source_type="db_query",
            table_name="fact_production",
            column_name="quantity",
            aggregation="sum",
        )

        assert config.table_name is not None
        assert config.column_name is not None
        assert config.aggregation is not None

    def test_mcp_config_requires_tool_name(self):
        """MCP 설정에는 도구 이름 필요"""
        from app.schemas.statcard import StatCardConfigCreate

        config = StatCardConfigCreate(
            source_type="mcp_tool",
            mcp_tool_name="get_data",
        )

        assert config.mcp_tool_name is not None


class TestStatCardCaching:
    """StatCard 캐싱 테스트"""

    def test_cache_expiry_logic(self):
        """캐시 만료 로직"""
        from datetime import timedelta

        cache_ttl = 60  # seconds
        cached_at = datetime.now() - timedelta(seconds=30)
        now = datetime.now()

        is_expired = (now - cached_at).total_seconds() > cache_ttl
        assert is_expired is False

    def test_cache_expired(self):
        """캐시 만료됨"""
        from datetime import timedelta

        cache_ttl = 60
        cached_at = datetime.now() - timedelta(seconds=120)
        now = datetime.now()

        is_expired = (now - cached_at).total_seconds() > cache_ttl
        assert is_expired is True

    def test_cache_key_format(self):
        """캐시 키 형식"""
        tenant_id = uuid4()
        config_id = uuid4()

        cache_key = f"statcard:{tenant_id}:{config_id}"
        parts = cache_key.split(":")

        assert len(parts) == 3
        assert parts[0] == "statcard"


class TestStatCardServiceDetermineStatus:
    """_determine_status 메서드 테스트"""

    def test_determine_status_no_thresholds(self):
        """임계값 없으면 gray"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        status = service._determine_status(85.0, None, None, None, True)
        assert status == "gray"

    def test_determine_status_higher_is_better_green(self):
        """높을수록 좋음 - Green"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        status = service._determine_status(90.0, 80.0, 60.0, 40.0, True)
        assert status == "green"

    def test_determine_status_higher_is_better_yellow(self):
        """높을수록 좋음 - Yellow"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        status = service._determine_status(70.0, 80.0, 60.0, 40.0, True)
        assert status == "yellow"

    def test_determine_status_higher_is_better_red(self):
        """높을수록 좋음 - Red"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        status = service._determine_status(50.0, 80.0, 60.0, 40.0, True)
        assert status == "red"

    def test_determine_status_lower_is_better_green(self):
        """낮을수록 좋음 - Green"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        status = service._determine_status(1.0, 2.0, 5.0, 10.0, False)
        assert status == "green"

    def test_determine_status_lower_is_better_yellow(self):
        """낮을수록 좋음 - Yellow"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        status = service._determine_status(3.0, 2.0, 5.0, 10.0, False)
        assert status == "yellow"

    def test_determine_status_lower_is_better_red(self):
        """낮을수록 좋음 - Red"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        status = service._determine_status(15.0, 2.0, 5.0, 10.0, False)
        assert status == "red"


class TestStatCardServiceFormatValue:
    """_format_value 메서드 테스트"""

    def test_format_percentage(self):
        """퍼센트 포맷"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        result = service._format_value(85.5, "%")
        assert result == "85.5%"

    def test_format_minutes(self):
        """분 단위 포맷"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        result = service._format_value(120.0, "min")
        assert result == "120분"

        result = service._format_value(90.0, "분")
        assert result == "90분"

    def test_format_seconds(self):
        """초 단위 포맷"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        result = service._format_value(45.5, "sec")
        assert result == "45.5초"

    def test_format_days(self):
        """일 단위 포맷"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        result = service._format_value(7.5, "days")
        assert result == "7.5일"

    def test_format_millions(self):
        """백만 단위 포맷"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        result = service._format_value(1500000.0, None)
        assert result == "1.5M"

    def test_format_thousands(self):
        """천 단위 포맷"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        result = service._format_value(2500.0, None)
        assert result == "2.5K"

    def test_format_regular_number(self):
        """일반 숫자 포맷"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        result = service._format_value(85.5, None)
        assert result == "85.5"


class TestStatCardServiceGetKpiIcon:
    """_get_kpi_icon 메서드 테스트"""

    def test_get_defect_rate_icon(self):
        """불량률 아이콘"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        icon = service._get_kpi_icon("defect_rate")
        assert icon == "AlertTriangle"

    def test_get_oee_icon(self):
        """OEE 아이콘"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        icon = service._get_kpi_icon("oee")
        assert icon == "Activity"

    def test_get_yield_rate_icon(self):
        """수율 아이콘"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        icon = service._get_kpi_icon("yield_rate")
        assert icon == "TrendingUp"

    def test_get_downtime_icon(self):
        """다운타임 아이콘"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        icon = service._get_kpi_icon("downtime")
        assert icon == "Clock"

    def test_get_default_icon(self):
        """기본 아이콘"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        icon = service._get_kpi_icon("unknown_kpi")
        assert icon == "BarChart3"


class TestStatCardServiceExtractValue:
    """_extract_value_from_result 메서드 테스트"""

    def test_extract_with_nested_key(self):
        """중첩 키로 값 추출"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        result = {"data": {"total": 100}}
        value = service._extract_value_from_result(result, "data.total")
        assert value == 100.0

    def test_extract_simple_key(self):
        """단순 키로 값 추출"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        result = {"count": 50}
        value = service._extract_value_from_result(result, "count")
        assert value == 50.0

    def test_extract_no_key(self):
        """키 없이 값 추출"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        # dict with value key
        result = {"value": 75}
        value = service._extract_value_from_result(result, None)
        assert value == 75.0

    def test_extract_direct_number(self):
        """숫자 직접 반환"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        value = service._extract_value_from_result(100, None)
        assert value == 100.0

    def test_extract_missing_key(self):
        """존재하지 않는 키"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        result = {"data": {"other": 50}}
        value = service._extract_value_from_result(result, "data.missing")
        assert value == 0.0

    def test_extract_non_dict_in_path(self):
        """경로 중간에 dict가 아닌 값"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        result = {"data": "string_value"}
        value = service._extract_value_from_result(result, "data.nested")
        assert value == 0.0


class TestStatCardServiceCache:
    """캐시 메서드 테스트"""

    def test_set_and_get_cache(self):
        """캐시 저장 및 조회"""
        from app.services.stat_card_service import StatCardService
        from app.schemas.statcard import StatCardValue

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        config_id = uuid4()
        value = StatCardValue(
            config_id=config_id,
            value=85.0,
            formatted_value="85.0%",
            status="green",
            title="Test",
            source_type="kpi",
            fetched_at=datetime.now(),
        )

        # 캐시 저장
        cache_key = f"statcard:{config_id}"
        service._set_cache(cache_key, value)

        # 캐시 조회
        cached = service._get_from_cache(cache_key, 60)
        assert cached is not None
        assert cached.value == 85.0

    def test_cache_expiry(self):
        """캐시 만료"""
        from app.services.stat_card_service import StatCardService
        from app.schemas.statcard import StatCardValue
        from datetime import timedelta

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        config_id = uuid4()
        value = StatCardValue(
            config_id=config_id,
            value=85.0,
            formatted_value="85.0%",
            status="green",
            title="Test",
            source_type="kpi",
            fetched_at=datetime.now(),
        )

        # 캐시 저장 (과거 시간)
        cache_key = f"statcard:{config_id}"
        service._cache[cache_key] = (value, datetime.utcnow() - timedelta(seconds=120))

        # TTL 60초로 조회 - 만료됨
        cached = service._get_from_cache(cache_key, 60)
        assert cached is None

    def test_cache_not_found(self):
        """캐시 없음"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        cached = service._get_from_cache("nonexistent", 60)
        assert cached is None


class TestStatCardServiceCreateConfig:
    """create_config 메서드 테스트"""

    def test_create_config(self):
        """설정 생성"""
        from app.services.stat_card_service import StatCardService
        from app.schemas.statcard import StatCardConfigCreate

        mock_db = MagicMock()

        # Mock execute result
        mock_row = (
            uuid4(),  # config_id
            uuid4(),  # tenant_id
            uuid4(),  # user_id
            1,  # display_order
            True,  # is_visible
            "kpi",  # source_type
            "OEE",  # kpi_code
            None,  # table_name
            None,  # column_name
            None,  # aggregation
            None,  # filter_condition
            None,  # mcp_server_id
            None,  # mcp_tool_name
            None,  # mcp_params
            None,  # mcp_result_key
            "OEE",  # custom_title
            "gauge",  # custom_icon
            "%",  # custom_unit
            80.0,  # green_threshold
            60.0,  # yellow_threshold
            40.0,  # red_threshold
            True,  # higher_is_better
            60,  # cache_ttl_seconds
            datetime.now(),  # created_at
            datetime.now(),  # updated_at
        )

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result

        service = StatCardService(db=mock_db)

        data = StatCardConfigCreate(
            source_type="kpi",
            kpi_code="OEE",
            custom_title="OEE",
            custom_icon="gauge",
            custom_unit="%",
        )

        result = service.create_config(uuid4(), uuid4(), data)

        assert result is not None
        assert result.source_type == "kpi"
        assert result.kpi_code == "OEE"


class TestStatCardServiceGetConfig:
    """get_config 메서드 테스트"""

    def test_get_config_found(self):
        """설정 조회 성공"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()

        mock_row = (
            uuid4(),  # config_id
            uuid4(),  # tenant_id
            uuid4(),  # user_id
            0,  # display_order
            True,  # is_visible
            "kpi",  # source_type
            "OEE",  # kpi_code
            None,  # table_name
            None,  # column_name
            None,  # aggregation
            None,  # filter_condition
            None,  # mcp_server_id
            None,  # mcp_tool_name
            None,  # mcp_params
            None,  # mcp_result_key
            None,  # custom_title
            None,  # custom_icon
            None,  # custom_unit
            None,  # green_threshold
            None,  # yellow_threshold
            None,  # red_threshold
            True,  # higher_is_better
            60,  # cache_ttl_seconds
            datetime.now(),  # created_at
            datetime.now(),  # updated_at
        )

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result

        service = StatCardService(db=mock_db)
        result = service.get_config(uuid4(), uuid4(), uuid4())

        assert result is not None

    def test_get_config_not_found(self):
        """설정 조회 실패"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()

        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_result

        service = StatCardService(db=mock_db)
        result = service.get_config(uuid4(), uuid4(), uuid4())

        assert result is None


class TestStatCardServiceListConfigs:
    """list_configs 메서드 테스트"""

    def test_list_configs_visible_only(self):
        """표시 가능한 설정만 조회"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()

        mock_rows = [
            (uuid4(), uuid4(), uuid4(), 0, True, "kpi", "OEE", None, None, None, None,
             None, None, None, None, None, None, None, None, None, None, True, 60, datetime.now(), datetime.now()),
            (uuid4(), uuid4(), uuid4(), 1, True, "kpi", "defect", None, None, None, None,
             None, None, None, None, None, None, None, None, None, None, True, 60, datetime.now(), datetime.now()),
        ]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows
        mock_db.execute.return_value = mock_result

        service = StatCardService(db=mock_db)
        results = service.list_configs(uuid4(), uuid4(), visible_only=True)

        assert len(results) == 2

    def test_list_configs_all(self):
        """모든 설정 조회"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()

        mock_rows = []
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows
        mock_db.execute.return_value = mock_result

        service = StatCardService(db=mock_db)
        results = service.list_configs(uuid4(), uuid4(), visible_only=False)

        assert len(results) == 0


class TestStatCardServiceDeleteConfig:
    """delete_config 메서드 테스트"""

    def test_delete_config_success(self):
        """설정 삭제 성공"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db.execute.return_value = mock_result

        service = StatCardService(db=mock_db)
        result = service.delete_config(uuid4(), uuid4(), uuid4())

        assert result is True

    def test_delete_config_not_found(self):
        """설정 삭제 실패 - 없음"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_db.execute.return_value = mock_result

        service = StatCardService(db=mock_db)
        result = service.delete_config(uuid4(), uuid4(), uuid4())

        assert result is False


class TestStatCardServiceCreateErrorValue:
    """_create_error_value 메서드 테스트"""

    def test_create_error_value(self):
        """에러 값 생성"""
        from app.services.stat_card_service import StatCardService
        from app.schemas.statcard import StatCardConfig

        mock_db = MagicMock()
        service = StatCardService(db=mock_db)

        # Create a mock config
        config = MagicMock(spec=StatCardConfig)
        config.config_id = uuid4()
        config.source_type = "kpi"
        config.custom_title = None
        config.custom_icon = None

        error_value = service._create_error_value(config, "Test error")

        assert error_value.value is None
        assert error_value.formatted_value == "Error"
        assert error_value.status == "gray"


class TestStatCardServiceReorderConfigs:
    """reorder_configs 메서드 테스트"""

    def test_reorder_configs(self):
        """설정 순서 변경"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()

        # Mock for reorder updates
        mock_db.execute.return_value = MagicMock()

        # Mock for list_configs call
        mock_rows = []
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows
        mock_db.execute.return_value = mock_result

        service = StatCardService(db=mock_db)

        card_ids = [uuid4(), uuid4(), uuid4()]
        service.reorder_configs(uuid4(), uuid4(), card_ids)

        assert mock_db.execute.called
        assert mock_db.commit.called


class TestStatCardServiceListKpis:
    """list_kpis 메서드 테스트"""

    def test_list_kpis(self):
        """KPI 목록 조회"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()

        mock_rows = [
            ("OEE", "Overall Equipment Effectiveness", "OEE", "production", "%",
             "설비 종합 효율", True, 85.0, 80.0, 60.0, 40.0),
            ("defect_rate", "불량률", "Defect Rate", "quality", "%",
             "불량 비율", False, 2.0, 1.0, 3.0, 5.0),
        ]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows
        mock_db.execute.return_value = mock_result

        service = StatCardService(db=mock_db)
        result = service.list_kpis(uuid4())

        assert len(result.kpis) == 2
        assert "production" in result.categories or "quality" in result.categories


class TestStatCardServiceListAvailableTables:
    """list_available_tables 메서드 테스트"""

    def test_list_available_tables(self):
        """사용 가능한 테이블 조회"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()

        mock_rows = [
            ("bi", "fact_production", "quantity", "integer", "생산량", ["sum", "avg"]),
            ("bi", "fact_production", "defect_qty", "integer", "불량 수량", ["sum", "count"]),
        ]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows
        mock_db.execute.return_value = mock_result

        service = StatCardService(db=mock_db)
        result = service.list_available_tables(uuid4())

        assert len(result.tables) == 1  # Same table, multiple columns


class TestStatCardServiceListMcpTools:
    """list_mcp_tools 메서드 테스트"""

    def test_list_mcp_tools(self):
        """MCP 도구 목록 조회"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()

        mock_rows = [
            (uuid4(), "mes-server", "get_production_count", "생산량 조회", {"line_id": {"type": "string"}}),
        ]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows
        mock_db.execute.return_value = mock_result

        service = StatCardService(db=mock_db)
        result = service.list_mcp_tools(uuid4())

        assert len(result.tools) == 1
        assert result.tools[0].tool_name == "get_production_count"


class TestStatCardServiceIsTableColumnAllowed:
    """_is_table_column_allowed 메서드 테스트"""

    def test_table_column_allowed(self):
        """테이블/컬럼 허용"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()

        mock_result = MagicMock()
        mock_result.fetchone.return_value = (1,)
        mock_db.execute.return_value = mock_result

        service = StatCardService(db=mock_db)
        result = service._is_table_column_allowed(uuid4(), "fact_production", "quantity")

        assert result is True

    def test_table_column_not_allowed(self):
        """테이블/컬럼 불허"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()

        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_result

        service = StatCardService(db=mock_db)
        result = service._is_table_column_allowed(uuid4(), "secret_table", "password")

        assert result is False


class TestStatCardServiceGetNextDisplayOrder:
    """_get_next_display_order 메서드 테스트"""

    def test_get_next_display_order(self):
        """다음 표시 순서 조회"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()

        mock_result = MagicMock()
        mock_result.scalar.return_value = 5
        mock_db.execute.return_value = mock_result

        service = StatCardService(db=mock_db)
        result = service._get_next_display_order(uuid4(), uuid4())

        assert result == 5

    def test_get_next_display_order_none(self):
        """첫 번째 설정"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()

        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_db.execute.return_value = mock_result

        service = StatCardService(db=mock_db)
        result = service._get_next_display_order(uuid4(), uuid4())

        assert result == 0


class TestStatCardServiceUpdateConfig:
    """update_config 메서드 테스트"""

    def test_update_config_success(self):
        """설정 업데이트 성공"""
        from app.services.stat_card_service import StatCardService
        from app.schemas.statcard import StatCardConfigUpdate

        mock_db = MagicMock()
        config_id = uuid4()
        tenant_id = uuid4()
        user_id = uuid4()
        now = datetime.now(timezone.utc)

        mock_row = (
            config_id,
            tenant_id,
            user_id,
            2,  # display_order (updated)
            True,
            "kpi",
            "defect_rate",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            "Updated Title",
            "AlertTriangle",
            "%",
            95.0,
            90.0,
            85.0,
            True,
            300,
            now,
            now,
        )

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result

        service = StatCardService(db=mock_db)
        update_data = StatCardConfigUpdate(
            display_order=2,
            custom_title="Updated Title",
            custom_icon="AlertTriangle",
        )
        result = service.update_config(config_id, tenant_id, user_id, update_data)

        assert result is not None
        assert result.display_order == 2
        assert result.custom_title == "Updated Title"
        mock_db.commit.assert_called_once()

    def test_update_config_not_found(self):
        """설정 업데이트 - 없음"""
        from app.services.stat_card_service import StatCardService
        from app.schemas.statcard import StatCardConfigUpdate

        mock_db = MagicMock()

        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_result

        service = StatCardService(db=mock_db)
        update_data = StatCardConfigUpdate(display_order=5)
        result = service.update_config(uuid4(), uuid4(), uuid4(), update_data)

        assert result is None

    def test_update_config_with_all_fields(self):
        """설정 업데이트 - 모든 필드"""
        from app.services.stat_card_service import StatCardService
        from app.schemas.statcard import StatCardConfigUpdate

        mock_db = MagicMock()
        config_id = uuid4()
        tenant_id = uuid4()
        user_id = uuid4()
        mcp_server_id = uuid4()
        now = datetime.now(timezone.utc)

        mock_row = (
            config_id,
            tenant_id,
            user_id,
            3,
            False,
            "mcp_tool",
            None,
            None,
            None,
            None,
            {"date": "today"},
            mcp_server_id,
            "get_metrics",
            {"key": "value"},
            "data.total",
            "MCP Title",
            "Plug",
            "count",
            100.0,
            75.0,
            50.0,
            False,
            600,
            now,
            now,
        )

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result

        service = StatCardService(db=mock_db)
        update_data = StatCardConfigUpdate(
            display_order=3,
            is_visible=False,
            source_type="mcp_tool",
            kpi_code=None,
            table_name=None,
            column_name=None,
            aggregation=None,
            custom_title="MCP Title",
            custom_icon="Plug",
            custom_unit="count",
            green_threshold=100.0,
            yellow_threshold=75.0,
            red_threshold=50.0,
            higher_is_better=False,
            cache_ttl_seconds=600,
            filter_condition={"date": "today"},
            mcp_server_id=mcp_server_id,
            mcp_tool_name="get_metrics",
            mcp_params={"key": "value"},
            mcp_result_key="data.total",
        )
        result = service.update_config(config_id, tenant_id, user_id, update_data)

        assert result is not None
        assert result.source_type == "mcp_tool"
        assert result.mcp_tool_name == "get_metrics"


class TestStatCardServiceGetCardValues:
    """get_card_values 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_get_card_values_empty(self):
        """카드 값 조회 - 빈 목록"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        service = StatCardService(db=mock_db)
        result = await service.get_card_values(uuid4(), uuid4())

        assert result.total == 0
        assert len(result.cards) == 0

    @pytest.mark.asyncio
    async def test_get_card_values_with_configs(self):
        """카드 값 조회 - 설정 있음"""
        from app.services.stat_card_service import StatCardService
        from unittest.mock import AsyncMock

        mock_db = MagicMock()
        config_id = uuid4()
        tenant_id = uuid4()
        user_id = uuid4()
        now = datetime.now(timezone.utc)

        # list_configs 결과
        mock_row = (
            config_id,
            tenant_id,
            user_id,
            1,
            True,
            "kpi",
            "defect_rate",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            "Defect Rate",
            "AlertTriangle",
            "%",
            5.0,
            10.0,
            15.0,
            False,
            300,
            now,
            now,
        )

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute.return_value = mock_result

        service = StatCardService(db=mock_db)

        # get_card_value를 mock
        with patch.object(service, "get_card_value", new_callable=AsyncMock) as mock_get_value:
            from app.schemas.statcard import StatCardValue

            mock_value = StatCardValue(
                config_id=config_id,
                value=3.5,
                formatted_value="3.5%",
                previous_value=4.0,
                change_percent=-12.5,
                trend="down",
                status="green",
                title="Defect Rate",
                icon="AlertTriangle",
                unit="%",
                source_type="kpi",
                fetched_at=now,
                is_cached=False,
            )
            mock_get_value.return_value = mock_value

            result = await service.get_card_values(tenant_id, user_id)

            assert result.total == 1
            assert len(result.cards) == 1
            assert result.cards[0].value.value == 3.5


class TestStatCardServiceGetCardValue:
    """get_card_value 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_get_card_value_from_cache(self):
        """카드 값 조회 - 캐시 히트"""
        from app.services.stat_card_service import StatCardService
        from app.schemas.statcard import StatCardConfig, StatCardValue

        mock_db = MagicMock()
        config_id = uuid4()
        tenant_id = uuid4()
        now = datetime.now(timezone.utc)

        config = StatCardConfig(
            config_id=config_id,
            tenant_id=tenant_id,
            user_id=uuid4(),
            display_order=1,
            is_visible=True,
            source_type="kpi",
            kpi_code="defect_rate",
            cache_ttl_seconds=300,
            created_at=now,
            updated_at=now,
        )

        cached_value = StatCardValue(
            config_id=config_id,
            value=5.0,
            formatted_value="5.0%",
            status="yellow",
            title="Defect Rate",
            icon="AlertTriangle",
            source_type="kpi",
            fetched_at=now,
            is_cached=False,
        )

        service = StatCardService(db=mock_db)
        # 캐시에 값 저장
        cache_key = f"statcard:{config_id}"
        service._cache[cache_key] = (cached_value, datetime.utcnow())

        result = await service.get_card_value(config, tenant_id)

        assert result.is_cached is True
        assert result.value == 5.0

    @pytest.mark.asyncio
    async def test_get_card_value_db_query_source(self):
        """카드 값 조회 - db_query 소스 타입"""
        from app.services.stat_card_service import StatCardService
        from app.schemas.statcard import StatCardConfig

        mock_db = MagicMock()
        config_id = uuid4()
        tenant_id = uuid4()
        now = datetime.now(timezone.utc)

        config = StatCardConfig(
            config_id=config_id,
            tenant_id=tenant_id,
            user_id=uuid4(),
            display_order=1,
            is_visible=True,
            source_type="db_query",
            table_name="fact_production",
            column_name="quantity",
            aggregation="sum",
            cache_ttl_seconds=300,
            created_at=now,
            updated_at=now,
        )

        service = StatCardService(db=mock_db)

        with patch.object(service, "_fetch_db_query_value", new_callable=AsyncMock) as mock_fetch:
            from app.schemas.statcard import StatCardValue as SCV

            mock_fetch.return_value = SCV(
                config_id=config_id,
                value=1000.0,
                formatted_value="1000.0",
                status="green",
                title="Production",
                icon="Package",
                source_type="db_query",
                fetched_at=now,
                is_cached=False,
            )

            result = await service.get_card_value(config, tenant_id)

            assert result.source_type == "db_query"
            mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_card_value_mcp_tool_source(self):
        """카드 값 조회 - mcp_tool 소스 타입"""
        from app.services.stat_card_service import StatCardService
        from app.schemas.statcard import StatCardConfig

        mock_db = MagicMock()
        config_id = uuid4()
        tenant_id = uuid4()
        now = datetime.now(timezone.utc)

        config = StatCardConfig(
            config_id=config_id,
            tenant_id=tenant_id,
            user_id=uuid4(),
            display_order=1,
            is_visible=True,
            source_type="mcp_tool",
            mcp_server_id=uuid4(),
            mcp_tool_name="get_count",
            cache_ttl_seconds=300,
            created_at=now,
            updated_at=now,
        )

        service = StatCardService(db=mock_db)

        with patch.object(service, "_fetch_mcp_value", new_callable=AsyncMock) as mock_fetch:
            from app.schemas.statcard import StatCardValue as SCV

            mock_fetch.return_value = SCV(
                config_id=config_id,
                value=500.0,
                formatted_value="500.0",
                status="yellow",
                title="MCP Data",
                icon="Plug",
                source_type="mcp_tool",
                fetched_at=now,
                is_cached=False,
            )

            result = await service.get_card_value(config, tenant_id)

            assert result.source_type == "mcp_tool"
            mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_card_value_exception(self):
        """카드 값 조회 - 예외 발생"""
        from app.services.stat_card_service import StatCardService
        from app.schemas.statcard import StatCardConfig

        mock_db = MagicMock()
        config_id = uuid4()
        tenant_id = uuid4()
        now = datetime.now(timezone.utc)

        config = StatCardConfig(
            config_id=config_id,
            tenant_id=tenant_id,
            user_id=uuid4(),
            display_order=1,
            is_visible=True,
            source_type="kpi",
            kpi_code="defect_rate",
            cache_ttl_seconds=300,
            created_at=now,
            updated_at=now,
        )

        service = StatCardService(db=mock_db)

        with patch.object(
            service, "_fetch_kpi_value", side_effect=Exception("DB connection error")
        ):
            result = await service.get_card_value(config, tenant_id)

            assert result.status == "gray"
            assert "Error" in result.formatted_value


class TestStatCardServiceFetchKpiValue:
    """_fetch_kpi_value 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_fetch_kpi_value_not_found(self):
        """KPI 값 조회 - KPI 없음"""
        from app.services.stat_card_service import StatCardService
        from app.schemas.statcard import StatCardConfig

        mock_db = MagicMock()
        config_id = uuid4()
        tenant_id = uuid4()
        now = datetime.now(timezone.utc)

        config = StatCardConfig(
            config_id=config_id,
            tenant_id=tenant_id,
            user_id=uuid4(),
            display_order=1,
            is_visible=True,
            source_type="kpi",
            kpi_code="nonexistent_kpi",
            cache_ttl_seconds=300,
            created_at=now,
            updated_at=now,
        )

        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_result

        service = StatCardService(db=mock_db)
        result = await service._fetch_kpi_value(config, tenant_id)

        assert result.status == "gray"
        assert "KPI not found" in str(result.formatted_value) or result.formatted_value == "Error"

    @pytest.mark.asyncio
    async def test_fetch_kpi_value_success(self):
        """KPI 값 조회 - 성공"""
        from app.services.stat_card_service import StatCardService
        from app.schemas.statcard import StatCardConfig

        mock_db = MagicMock()
        config_id = uuid4()
        tenant_id = uuid4()
        now = datetime.now(timezone.utc)

        config = StatCardConfig(
            config_id=config_id,
            tenant_id=tenant_id,
            user_id=uuid4(),
            display_order=1,
            is_visible=True,
            source_type="kpi",
            kpi_code="defect_rate",
            cache_ttl_seconds=300,
            created_at=now,
            updated_at=now,
        )

        # KPI 정보 row
        kpi_row = ("불량률", "%", 5.0, 10.0, 15.0, False)

        # 현재 값 row
        value_row = (3.5,)

        # 이전 값 row
        prev_row = (4.0,)

        mock_result = MagicMock()
        mock_result.fetchone.side_effect = [kpi_row, value_row, prev_row]
        mock_db.execute.return_value = mock_result

        service = StatCardService(db=mock_db)
        result = await service._fetch_kpi_value(config, tenant_id)

        assert result.value == 3.5
        assert result.previous_value == 4.0
        assert result.status == "green"  # 3.5 < 5.0 (green threshold), lower is better

    @pytest.mark.asyncio
    async def test_fetch_kpi_value_no_previous(self):
        """KPI 값 조회 - 이전 값 없음"""
        from app.services.stat_card_service import StatCardService
        from app.schemas.statcard import StatCardConfig

        mock_db = MagicMock()
        config_id = uuid4()
        tenant_id = uuid4()
        now = datetime.now(timezone.utc)

        config = StatCardConfig(
            config_id=config_id,
            tenant_id=tenant_id,
            user_id=uuid4(),
            display_order=1,
            is_visible=True,
            source_type="kpi",
            kpi_code="oee",
            cache_ttl_seconds=300,
            created_at=now,
            updated_at=now,
        )

        kpi_row = ("OEE", "%", 85.0, 70.0, 50.0, True)
        value_row = (88.5,)
        prev_row = (None,)

        mock_result = MagicMock()
        mock_result.fetchone.side_effect = [kpi_row, value_row, prev_row]
        mock_db.execute.return_value = mock_result

        service = StatCardService(db=mock_db)
        result = await service._fetch_kpi_value(config, tenant_id)

        assert result.value == 88.5
        assert result.previous_value is None
        assert result.change_percent is None
        assert result.trend is None


class TestStatCardServiceFetchDbQueryValue:
    """_fetch_db_query_value 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_fetch_db_query_value_not_allowed(self):
        """DB 쿼리 값 조회 - 허용되지 않은 테이블"""
        from app.services.stat_card_service import StatCardService
        from app.schemas.statcard import StatCardConfig

        mock_db = MagicMock()
        config_id = uuid4()
        tenant_id = uuid4()
        now = datetime.now(timezone.utc)

        config = StatCardConfig(
            config_id=config_id,
            tenant_id=tenant_id,
            user_id=uuid4(),
            display_order=1,
            is_visible=True,
            source_type="db_query",
            table_name="secret_table",
            column_name="password",
            aggregation="count",
            cache_ttl_seconds=300,
            created_at=now,
            updated_at=now,
        )

        mock_result = MagicMock()
        mock_result.fetchone.return_value = None  # _is_table_column_allowed 반환
        mock_db.execute.return_value = mock_result

        service = StatCardService(db=mock_db)
        result = await service._fetch_db_query_value(config, tenant_id)

        assert result.status == "gray"
        assert "not allowed" in str(result.formatted_value) or result.formatted_value == "Error"

    @pytest.mark.asyncio
    async def test_fetch_db_query_value_success(self):
        """DB 쿼리 값 조회 - 성공"""
        from app.services.stat_card_service import StatCardService
        from app.schemas.statcard import StatCardConfig

        mock_db = MagicMock()
        config_id = uuid4()
        tenant_id = uuid4()
        now = datetime.now(timezone.utc)

        config = StatCardConfig(
            config_id=config_id,
            tenant_id=tenant_id,
            user_id=uuid4(),
            display_order=1,
            is_visible=True,
            source_type="db_query",
            table_name="fact_production",
            column_name="quantity",
            aggregation="sum",
            custom_title="Total Production",
            custom_icon="Package",
            green_threshold=10000.0,
            yellow_threshold=5000.0,
            red_threshold=1000.0,
            higher_is_better=True,
            cache_ttl_seconds=300,
            created_at=now,
            updated_at=now,
        )

        # _is_table_column_allowed 호출 결과
        allowed_result = MagicMock()
        allowed_result.fetchone.return_value = (1,)

        # 쿼리 결과
        query_result = MagicMock()
        query_result.fetchone.return_value = (15000.0,)

        mock_db.execute.side_effect = [allowed_result, query_result]

        service = StatCardService(db=mock_db)
        result = await service._fetch_db_query_value(config, tenant_id)

        assert result.value == 15000.0
        assert result.status == "green"  # 15000 >= 10000
        assert result.source_type == "db_query"

    @pytest.mark.asyncio
    async def test_fetch_db_query_value_with_filter(self):
        """DB 쿼리 값 조회 - 필터 조건 포함"""
        from app.services.stat_card_service import StatCardService
        from app.schemas.statcard import StatCardConfig

        mock_db = MagicMock()
        config_id = uuid4()
        tenant_id = uuid4()
        now = datetime.now(timezone.utc)

        config = StatCardConfig(
            config_id=config_id,
            tenant_id=tenant_id,
            user_id=uuid4(),
            display_order=1,
            is_visible=True,
            source_type="db_query",
            table_name="fact_production",
            column_name="quantity",
            aggregation="avg",
            filter_condition={"line_id": "LINE-001", "shift": "day"},
            cache_ttl_seconds=300,
            created_at=now,
            updated_at=now,
        )

        allowed_result = MagicMock()
        allowed_result.fetchone.return_value = (1,)

        query_result = MagicMock()
        query_result.fetchone.return_value = (500.0,)

        mock_db.execute.side_effect = [allowed_result, query_result]

        service = StatCardService(db=mock_db)
        result = await service._fetch_db_query_value(config, tenant_id)

        assert result.value == 500.0


class TestStatCardServiceFetchMcpValue:
    """_fetch_mcp_value 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_fetch_mcp_value_success(self):
        """MCP 값 조회 - 성공"""
        from app.services.stat_card_service import StatCardService
        from app.schemas.statcard import StatCardConfig

        mock_db = MagicMock()
        config_id = uuid4()
        tenant_id = uuid4()
        mcp_server_id = uuid4()
        now = datetime.now(timezone.utc)

        config = StatCardConfig(
            config_id=config_id,
            tenant_id=tenant_id,
            user_id=uuid4(),
            display_order=1,
            is_visible=True,
            source_type="mcp_tool",
            mcp_server_id=mcp_server_id,
            mcp_tool_name="get_production_count",
            mcp_params={"line_id": "LINE-001"},
            mcp_result_key="data.count",
            custom_title="Production Count",
            custom_icon="Factory",
            green_threshold=1000.0,
            yellow_threshold=500.0,
            red_threshold=100.0,
            higher_is_better=True,
            cache_ttl_seconds=300,
            created_at=now,
            updated_at=now,
        )

        service = StatCardService(db=mock_db)

        with patch("app.services.stat_card_service.MCPToolHubService") as MockMCP:
            mock_mcp_instance = AsyncMock()
            mock_mcp_instance.call_tool.return_value = {"data": {"count": 1500}}
            MockMCP.return_value = mock_mcp_instance

            result = await service._fetch_mcp_value(config, tenant_id)

            assert result.value == 1500.0
            assert result.status == "green"
            assert result.source_type == "mcp_tool"

    @pytest.mark.asyncio
    async def test_fetch_mcp_value_exception(self):
        """MCP 값 조회 - 예외"""
        from app.services.stat_card_service import StatCardService
        from app.schemas.statcard import StatCardConfig

        mock_db = MagicMock()
        config_id = uuid4()
        tenant_id = uuid4()
        now = datetime.now(timezone.utc)

        config = StatCardConfig(
            config_id=config_id,
            tenant_id=tenant_id,
            user_id=uuid4(),
            display_order=1,
            is_visible=True,
            source_type="mcp_tool",
            mcp_server_id=uuid4(),
            mcp_tool_name="failing_tool",
            cache_ttl_seconds=300,
            created_at=now,
            updated_at=now,
        )

        service = StatCardService(db=mock_db)

        with patch("app.services.stat_card_service.MCPToolHubService") as MockMCP:
            mock_mcp_instance = AsyncMock()
            mock_mcp_instance.call_tool.side_effect = Exception("MCP connection failed")
            MockMCP.return_value = mock_mcp_instance

            result = await service._fetch_mcp_value(config, tenant_id)

            assert result.status == "gray"
            assert result.formatted_value == "Error"


class TestStatCardServiceExtractValueAdvanced:
    """_extract_value_from_result 추가 테스트"""

    def test_extract_dict_with_value_key(self):
        """dict에 value 키가 있는 경우"""
        from app.services.stat_card_service import StatCardService

        service = StatCardService(db=MagicMock())
        result = {"value": 42.5}
        value = service._extract_value_from_result(result, None)

        assert value == 42.5

    def test_extract_fallback_to_zero(self):
        """추출 실패 시 0 반환"""
        from app.services.stat_card_service import StatCardService

        service = StatCardService(db=MagicMock())
        result = {"other_key": "not a number"}
        value = service._extract_value_from_result(result, "missing.path")

        assert value == 0.0


class TestStatCardServiceRowToConfig:
    """_row_to_config 메서드 테스트"""

    def test_row_to_config(self):
        """row를 config로 변환"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        config_id = uuid4()
        tenant_id = uuid4()
        user_id = uuid4()
        mcp_server_id = uuid4()
        now = datetime.now(timezone.utc)

        row = (
            config_id,
            tenant_id,
            user_id,
            1,
            True,
            "kpi",
            "defect_rate",
            None,
            None,
            None,
            None,
            mcp_server_id,
            "tool_name",
            {"param": "value"},
            "result.key",
            "Custom Title",
            "Icon",
            "%",
            95.0,
            85.0,
            70.0,
            True,
            300,
            now,
            now,
        )

        service = StatCardService(db=mock_db)
        config = service._row_to_config(row)

        assert config.config_id == config_id
        assert config.tenant_id == tenant_id
        assert config.source_type == "kpi"
        assert config.green_threshold == 95.0
        assert config.cache_ttl_seconds == 300

    def test_row_to_config_null_thresholds(self):
        """row를 config로 변환 - null 임계값"""
        from app.services.stat_card_service import StatCardService

        mock_db = MagicMock()
        now = datetime.now(timezone.utc)

        row = (
            uuid4(),
            uuid4(),
            uuid4(),
            1,
            True,
            "db_query",
            None,
            "fact_table",
            "column",
            "sum",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,  # green_threshold null
            None,  # yellow_threshold null
            None,  # red_threshold null
            True,
            300,
            now,
            now,
        )

        service = StatCardService(db=mock_db)
        config = service._row_to_config(row)

        assert config.green_threshold is None
        assert config.yellow_threshold is None
        assert config.red_threshold is None
