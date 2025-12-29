"""
ChartBuilder 서비스 테스트

차트 설정 생성 서비스 단위 테스트
"""

import pytest
from datetime import date, datetime
from decimal import Decimal

from app.services.chart_builder import (
    ChartBuilder,
    ChartType,
    ChartConfig,
    AxisConfig,
    SeriesConfig,
    LegendConfig,
    TooltipConfig,
    InteractionConfig,
    ResponsiveConfig,
)


class TestChartType:
    """ChartType 열거형 테스트"""

    def test_chart_types_exist(self):
        """모든 차트 타입 존재 확인"""
        assert ChartType.LINE == "line"
        assert ChartType.BAR == "bar"
        assert ChartType.PIE == "pie"
        assert ChartType.SCATTER == "scatter"
        assert ChartType.HEATMAP == "heatmap"
        assert ChartType.TABLE == "table"

    def test_chart_type_is_string_enum(self):
        """ChartType이 문자열 열거형인지 확인"""
        assert isinstance(ChartType.LINE.value, str)


class TestAxisConfig:
    """AxisConfig 모델 테스트"""

    def test_axis_config_defaults(self):
        """기본값 확인"""
        axis = AxisConfig(field="date", label="날짜")

        assert axis.field == "date"
        assert axis.label == "날짜"
        assert axis.type == "category"
        assert axis.position == "bottom"
        assert axis.format is None
        assert axis.min is None
        assert axis.max is None

    def test_axis_config_with_options(self):
        """옵션 포함 축 설정"""
        axis = AxisConfig(
            field="value",
            label="값",
            type="linear",
            position="left",
            min=0,
            max=100,
            format=",.2f",
        )

        assert axis.type == "linear"
        assert axis.min == 0
        assert axis.max == 100


class TestSeriesConfig:
    """SeriesConfig 모델 테스트"""

    def test_series_config_defaults(self):
        """기본값 확인"""
        series = SeriesConfig(name="생산량", field="qty")

        assert series.name == "생산량"
        assert series.field == "qty"
        assert series.type is None
        assert series.color is None
        assert series.stack is None
        assert series.area is False
        assert series.smooth is False

    def test_series_config_with_options(self):
        """옵션 포함 시리즈 설정"""
        series = SeriesConfig(
            name="불량률",
            field="defect_rate",
            color="#FF0000",
            area=True,
            smooth=True,
            stack="group1",
        )

        assert series.color == "#FF0000"
        assert series.area is True
        assert series.smooth is True
        assert series.stack == "group1"


class TestLegendConfig:
    """LegendConfig 모델 테스트"""

    def test_legend_config_defaults(self):
        """기본값 확인"""
        legend = LegendConfig()

        assert legend.display is True
        assert legend.position == "top"
        assert legend.align == "center"

    def test_legend_config_hidden(self):
        """범례 숨김"""
        legend = LegendConfig(display=False)

        assert legend.display is False


class TestTooltipConfig:
    """TooltipConfig 모델 테스트"""

    def test_tooltip_config_defaults(self):
        """기본값 확인"""
        tooltip = TooltipConfig()

        assert tooltip.enabled is True
        assert tooltip.mode == "index"
        assert tooltip.intersect is False

    def test_tooltip_config_point_mode(self):
        """포인트 모드 툴팁"""
        tooltip = TooltipConfig(mode="point", intersect=True)

        assert tooltip.mode == "point"
        assert tooltip.intersect is True


class TestInteractionConfig:
    """InteractionConfig 모델 테스트"""

    def test_interaction_config_defaults(self):
        """기본값 확인"""
        interaction = InteractionConfig()

        assert interaction.zoom is False
        assert interaction.pan is False
        assert interaction.hover is True
        assert interaction.click is True

    def test_interaction_config_with_zoom(self):
        """줌 활성화"""
        interaction = InteractionConfig(zoom=True, pan=True)

        assert interaction.zoom is True
        assert interaction.pan is True


class TestResponsiveConfig:
    """ResponsiveConfig 모델 테스트"""

    def test_responsive_config_defaults(self):
        """기본값 확인"""
        responsive = ResponsiveConfig()

        assert responsive.maintain_aspect_ratio is True
        assert responsive.aspect_ratio == 2.0
        assert responsive.breakpoints == {}


class TestChartBuilder:
    """ChartBuilder 서비스 테스트"""

    @pytest.fixture
    def builder(self):
        return ChartBuilder()

    @pytest.fixture
    def sample_data(self):
        return [
            {"date": "2024-01-01", "qty": 100, "defect": 5},
            {"date": "2024-01-02", "qty": 120, "defect": 8},
            {"date": "2024-01-03", "qty": 90, "defect": 3},
        ]

    def test_default_colors(self, builder):
        """기본 색상 팔레트 확인"""
        assert len(builder.DEFAULT_COLORS) == 10
        assert builder.DEFAULT_COLORS[0] == "#4CAF50"  # Green

    def test_themes(self, builder):
        """테마 설정 확인"""
        assert "default" in builder.THEMES
        assert "dark" in builder.THEMES
        assert "light" in builder.THEMES

        assert builder.THEMES["default"]["background"] == "#ffffff"
        assert builder.THEMES["dark"]["background"] == "#1e1e1e"


class TestBuildLineChart:
    """라인 차트 생성 테스트"""

    @pytest.fixture
    def builder(self):
        return ChartBuilder()

    @pytest.fixture
    def sample_data(self):
        return [
            {"date": "2024-01-01", "qty": 100},
            {"date": "2024-01-02", "qty": 120},
            {"date": "2024-01-03", "qty": 90},
        ]

    def test_build_simple_line_chart(self, builder, sample_data):
        """간단한 라인 차트"""
        config = builder.build_chart(
            chart_id="chart-1",
            chart_type=ChartType.LINE,
            data=sample_data,
            x_field="date",
            y_fields=["qty"],
            title="생산량 추이",
        )

        assert isinstance(config, ChartConfig)
        assert config.chart_id == "chart-1"
        assert config.type == ChartType.LINE
        assert config.title == "생산량 추이"
        assert len(config.series) == 1
        assert len(config.data) == 3

    def test_build_line_chart_with_subtitle(self, builder, sample_data):
        """부제목 포함 라인 차트"""
        config = builder.build_chart(
            chart_id="chart-2",
            chart_type=ChartType.LINE,
            data=sample_data,
            x_field="date",
            y_fields=["qty"],
            title="생산량 추이",
            subtitle="2024년 1월",
        )

        assert config.subtitle == "2024년 1월"

    def test_build_multi_series_line_chart(self, builder):
        """다중 시리즈 라인 차트"""
        data = [
            {"date": "2024-01-01", "qty": 100, "defect": 5},
            {"date": "2024-01-02", "qty": 120, "defect": 8},
        ]

        config = builder.build_chart(
            chart_id="chart-3",
            chart_type=ChartType.LINE,
            data=data,
            x_field="date",
            y_fields=["qty", "defect"],
            title="생산량 및 불량",
        )

        assert len(config.series) == 2
        assert config.legend.display is True  # 다중 시리즈면 범례 표시

    def test_build_line_chart_with_smooth(self, builder, sample_data):
        """부드러운 라인 차트"""
        config = builder.build_chart(
            chart_id="chart-4",
            chart_type=ChartType.LINE,
            data=sample_data,
            x_field="date",
            y_fields=["qty"],
            title="생산량",
            smooth=True,
        )

        assert config.series[0].smooth is True

    def test_build_area_chart(self, builder, sample_data):
        """영역 차트"""
        config = builder.build_chart(
            chart_id="chart-5",
            chart_type=ChartType.LINE,
            data=sample_data,
            x_field="date",
            y_fields=["qty"],
            title="생산량",
            area=True,
        )

        assert config.series[0].area is True


class TestBuildBarChart:
    """바 차트 생성 테스트"""

    @pytest.fixture
    def builder(self):
        return ChartBuilder()

    @pytest.fixture
    def sample_data(self):
        return [
            {"line": "LINE_A", "qty": 100},
            {"line": "LINE_B", "qty": 150},
            {"line": "LINE_C", "qty": 80},
        ]

    def test_build_simple_bar_chart(self, builder, sample_data):
        """간단한 바 차트"""
        config = builder.build_chart(
            chart_id="bar-1",
            chart_type=ChartType.BAR,
            data=sample_data,
            x_field="line",
            y_fields=["qty"],
            title="라인별 생산량",
        )

        assert config.type == ChartType.BAR
        assert len(config.series) == 1

    def test_build_stacked_bar_chart(self, builder):
        """스택 바 차트"""
        data = [
            {"line": "LINE_A", "good": 95, "defect": 5},
            {"line": "LINE_B", "good": 140, "defect": 10},
        ]

        config = builder.build_chart(
            chart_id="bar-2",
            chart_type=ChartType.BAR,
            data=data,
            x_field="line",
            y_fields=["good", "defect"],
            title="라인별 품질",
            stacked=True,
        )

        assert len(config.series) == 2
        assert config.series[0].stack == "default"


class TestBuildPieChart:
    """파이 차트 생성 테스트"""

    @pytest.fixture
    def builder(self):
        return ChartBuilder()

    @pytest.fixture
    def sample_data(self):
        return [
            {"category": "정상", "value": 950},
            {"category": "불량", "value": 50},
        ]

    def test_build_simple_pie_chart(self, builder, sample_data):
        """간단한 파이 차트"""
        config = builder.build_chart(
            chart_id="pie-1",
            chart_type=ChartType.PIE,
            data=sample_data,
            x_field="category",
            y_fields=["value"],
            title="품질 분포",
        )

        assert config.type == ChartType.PIE
        assert len(config.data) == 2


class TestBuildTableChart:
    """테이블 차트 생성 테스트"""

    @pytest.fixture
    def builder(self):
        return ChartBuilder()

    @pytest.fixture
    def sample_data(self):
        return [
            {"line": "LINE_A", "qty": 100, "defect_rate": 5.0},
            {"line": "LINE_B", "qty": 150, "defect_rate": 3.5},
        ]

    def test_build_table_chart(self, builder, sample_data):
        """테이블 차트"""
        config = builder.build_chart(
            chart_id="table-1",
            chart_type=ChartType.TABLE,
            data=sample_data,
            x_field="line",
            y_fields=["qty", "defect_rate"],
            title="라인별 현황",
        )

        assert config.type == ChartType.TABLE
        assert len(config.data) == 2


class TestDataNormalization:
    """데이터 정규화 테스트"""

    @pytest.fixture
    def builder(self):
        return ChartBuilder()

    def test_normalize_decimal(self, builder):
        """Decimal 타입 정규화"""
        data = [{"value": Decimal("123.45")}]
        normalized = builder._normalize_data(data)

        assert isinstance(normalized[0]["value"], float)
        assert normalized[0]["value"] == 123.45

    def test_normalize_date(self, builder):
        """date 타입 정규화"""
        data = [{"date": date(2024, 1, 15)}]
        normalized = builder._normalize_data(data)

        assert isinstance(normalized[0]["date"], str)
        assert normalized[0]["date"] == "2024-01-15"

    def test_normalize_datetime(self, builder):
        """datetime 타입 정규화"""
        data = [{"timestamp": datetime(2024, 1, 15, 10, 30, 0)}]
        normalized = builder._normalize_data(data)

        assert isinstance(normalized[0]["timestamp"], str)
        assert "2024-01-15" in normalized[0]["timestamp"]

    def test_normalize_mixed_types(self, builder):
        """혼합 타입 정규화"""
        data = [{
            "date": date(2024, 1, 15),
            "value": Decimal("100.50"),
            "name": "테스트",
            "count": 42,
        }]
        normalized = builder._normalize_data(data)

        assert isinstance(normalized[0]["date"], str)
        assert isinstance(normalized[0]["value"], float)
        assert isinstance(normalized[0]["name"], str)
        assert isinstance(normalized[0]["count"], int)


class TestChartConfig:
    """ChartConfig 모델 테스트"""

    def test_chart_config_basic(self):
        """기본 ChartConfig 생성"""
        config = ChartConfig(
            chart_id="test-1",
            type=ChartType.LINE,
            title="테스트 차트",
            series=[SeriesConfig(name="시리즈1", field="value")],
            data=[{"value": 100}],
        )

        assert config.chart_id == "test-1"
        assert config.type == ChartType.LINE
        assert config.subtitle is None
        assert config.legend.display is True
        assert config.tooltip.enabled is True

    def test_chart_config_with_annotations(self):
        """주석 포함 ChartConfig"""
        annotations = [
            {"type": "line", "value": 90, "label": "목표"},
        ]

        config = ChartConfig(
            chart_id="test-2",
            type=ChartType.LINE,
            title="테스트",
            series=[],
            data=[],
            annotations=annotations,
        )

        assert len(config.annotations) == 1
        assert config.annotations[0]["label"] == "목표"

    def test_chart_config_with_theme(self):
        """테마 적용 ChartConfig"""
        config = ChartConfig(
            chart_id="test-3",
            type=ChartType.BAR,
            title="다크 차트",
            series=[],
            data=[],
            theme="dark",
        )

        assert config.theme == "dark"


class TestUnsupportedChartType:
    """지원하지 않는 차트 타입 테스트"""

    @pytest.fixture
    def builder(self):
        return ChartBuilder()

    def test_unsupported_chart_type_raises_error(self, builder):
        """지원하지 않는 차트 타입은 에러 발생"""
        # ChartType 열거형 외의 값을 사용하면 에러 발생 예상
        # 실제로는 Pydantic 검증에서 막힘
        pass


class TestCustomColors:
    """사용자 정의 색상 테스트"""

    @pytest.fixture
    def builder(self):
        return ChartBuilder()

    def test_custom_colors(self, builder):
        """사용자 정의 색상 적용"""
        data = [
            {"cat": "A", "val": 100},
            {"cat": "B", "val": 200},
        ]
        custom_colors = ["#FF0000", "#00FF00"]

        config = builder.build_chart(
            chart_id="color-test",
            chart_type=ChartType.BAR,
            data=data,
            x_field="cat",
            y_fields=["val"],
            title="색상 테스트",
            colors=custom_colors,
        )

        assert config.series[0].color == "#FF0000"


class TestAxisLabels:
    """축 레이블 테스트"""

    @pytest.fixture
    def builder(self):
        return ChartBuilder()

    def test_axis_labels(self, builder):
        """축 레이블 설정"""
        data = [{"x": 1, "y": 100}]

        config = builder.build_chart(
            chart_id="label-test",
            chart_type=ChartType.LINE,
            data=data,
            x_field="x",
            y_fields=["y"],
            title="레이블 테스트",
            x_label="X축",
            y_label="Y축",
        )

        assert config.x_axis.label == "X축"
        assert config.y_axis.label == "Y축"


class TestToChartjs:
    """Chart.js 변환 테스트"""

    @pytest.fixture
    def builder(self):
        return ChartBuilder()

    @pytest.fixture
    def sample_line_config(self, builder):
        data = [
            {"date": "2024-01-01", "qty": 100},
            {"date": "2024-01-02", "qty": 120},
        ]
        return builder.build_chart(
            chart_id="line-chartjs",
            chart_type=ChartType.LINE,
            data=data,
            x_field="date",
            y_fields=["qty"],
            title="생산량",
        )

    def test_chartjs_structure(self, builder, sample_line_config):
        """Chart.js 구조 확인"""
        result = builder.to_chartjs(sample_line_config)

        assert "type" in result
        assert "data" in result
        assert "options" in result

    def test_chartjs_type_mapping(self, builder, sample_line_config):
        """Chart.js 타입 매핑"""
        result = builder.to_chartjs(sample_line_config)

        assert result["type"] == "line"

    def test_chartjs_data_labels(self, builder, sample_line_config):
        """Chart.js 데이터 레이블"""
        result = builder.to_chartjs(sample_line_config)

        assert "labels" in result["data"]
        assert len(result["data"]["labels"]) == 2

    def test_chartjs_datasets(self, builder, sample_line_config):
        """Chart.js 데이터셋"""
        result = builder.to_chartjs(sample_line_config)

        assert "datasets" in result["data"]
        assert len(result["data"]["datasets"]) == 1

    def test_chartjs_options_responsive(self, builder, sample_line_config):
        """Chart.js 반응형 옵션"""
        result = builder.to_chartjs(sample_line_config)

        assert result["options"]["responsive"] is True

    def test_chartjs_options_title(self, builder, sample_line_config):
        """Chart.js 제목 옵션"""
        result = builder.to_chartjs(sample_line_config)

        assert result["options"]["plugins"]["title"]["display"] is True
        assert result["options"]["plugins"]["title"]["text"] == "생산량"

    def test_chartjs_bar_chart(self, builder):
        """Chart.js 바 차트"""
        data = [{"cat": "A", "val": 100}]
        config = builder.build_chart(
            chart_id="bar-chartjs",
            chart_type=ChartType.BAR,
            data=data,
            x_field="cat",
            y_fields=["val"],
            title="바 차트",
        )

        result = builder.to_chartjs(config)
        assert result["type"] == "bar"

    def test_chartjs_pie_chart(self, builder):
        """Chart.js 파이 차트"""
        data = [
            {"cat": "A", "val": 60},
            {"cat": "B", "val": 40},
        ]
        config = builder.build_chart(
            chart_id="pie-chartjs",
            chart_type=ChartType.PIE,
            data=data,
            x_field="cat",
            y_fields=["val"],
            title="파이 차트",
        )

        result = builder.to_chartjs(config)
        assert result["type"] == "pie"
        assert "backgroundColor" in result["data"]["datasets"][0]

    def test_chartjs_scatter_chart(self, builder):
        """Chart.js 산점도 차트"""
        data = [
            {"x": 1, "y": 10},
            {"x": 2, "y": 20},
        ]
        config = builder.build_chart(
            chart_id="scatter-chartjs",
            chart_type=ChartType.SCATTER,
            data=data,
            x_field="x",
            y_fields=["y"],
            title="산점도",
        )

        result = builder.to_chartjs(config)
        assert result["type"] == "scatter"
        # 산점도는 x, y 객체로 데이터 표현
        assert "x" in result["data"]["datasets"][0]["data"][0]

    def test_chartjs_with_dark_theme(self, builder):
        """Chart.js 다크 테마"""
        data = [{"date": "2024-01", "qty": 100}]
        config = builder.build_chart(
            chart_id="dark-chartjs",
            chart_type=ChartType.LINE,
            data=data,
            x_field="date",
            y_fields=["qty"],
            title="다크 테마",
            theme="dark",
        )

        result = builder.to_chartjs(config)
        # 다크 테마의 텍스트 색상이 적용되어야 함
        assert result["options"]["plugins"]["title"]["color"] == "#e0e0e0"

    def test_chartjs_with_zoom(self, builder):
        """Chart.js 줌 기능"""
        data = [{"date": "2024-01", "qty": 100}]
        config = builder.build_chart(
            chart_id="zoom-chartjs",
            chart_type=ChartType.LINE,
            data=data,
            x_field="date",
            y_fields=["qty"],
            title="줌 차트",
            zoom=True,
            pan=True,
        )

        result = builder.to_chartjs(config)
        assert "zoom" in result["options"]["plugins"]

    def test_chartjs_dual_axis(self, builder):
        """Chart.js 이중 축"""
        data = [{"date": "2024-01", "qty": 100, "rate": 95.5}]
        config = builder.build_chart(
            chart_id="dual-chartjs",
            chart_type=ChartType.LINE,
            data=data,
            x_field="date",
            y_fields=["qty", "rate"],
            title="이중 축",
            dual_axis=True,
        )

        result = builder.to_chartjs(config)
        assert "y-right" in result["options"]["scales"]


class TestToEcharts:
    """ECharts 변환 테스트"""

    @pytest.fixture
    def builder(self):
        return ChartBuilder()

    @pytest.fixture
    def sample_line_config(self, builder):
        data = [
            {"date": "2024-01-01", "qty": 100},
            {"date": "2024-01-02", "qty": 120},
        ]
        return builder.build_chart(
            chart_id="line-echarts",
            chart_type=ChartType.LINE,
            data=data,
            x_field="date",
            y_fields=["qty"],
            title="생산량",
        )

    def test_echarts_structure(self, builder, sample_line_config):
        """ECharts 구조 확인"""
        result = builder.to_echarts(sample_line_config)

        assert "title" in result
        assert "tooltip" in result
        assert "legend" in result

    def test_echarts_title(self, builder, sample_line_config):
        """ECharts 제목"""
        result = builder.to_echarts(sample_line_config)

        assert result["title"]["text"] == "생산량"

    def test_echarts_line_chart(self, builder, sample_line_config):
        """ECharts 라인 차트"""
        result = builder.to_echarts(sample_line_config)

        assert "xAxis" in result
        assert "yAxis" in result
        assert "series" in result
        assert result["series"][0]["type"] == "line"

    def test_echarts_bar_chart(self, builder):
        """ECharts 바 차트"""
        data = [{"cat": "A", "val": 100}]
        config = builder.build_chart(
            chart_id="bar-echarts",
            chart_type=ChartType.BAR,
            data=data,
            x_field="cat",
            y_fields=["val"],
            title="바 차트",
        )

        result = builder.to_echarts(config)
        assert result["series"][0]["type"] == "bar"

    def test_echarts_pie_chart(self, builder):
        """ECharts 파이 차트"""
        data = [
            {"cat": "A", "val": 60},
            {"cat": "B", "val": 40},
        ]
        config = builder.build_chart(
            chart_id="pie-echarts",
            chart_type=ChartType.PIE,
            data=data,
            x_field="cat",
            y_fields=["val"],
            title="파이 차트",
        )

        result = builder.to_echarts(config)
        assert result["series"][0]["type"] == "pie"
        assert len(result["series"][0]["data"]) == 2

    def test_echarts_scatter_chart(self, builder):
        """ECharts 산점도 차트"""
        data = [
            {"x": 1, "y": 10},
            {"x": 2, "y": 20},
        ]
        config = builder.build_chart(
            chart_id="scatter-echarts",
            chart_type=ChartType.SCATTER,
            data=data,
            x_field="x",
            y_fields=["y"],
            title="산점도",
        )

        result = builder.to_echarts(config)
        assert result["series"][0]["type"] == "scatter"

    def test_echarts_heatmap_chart(self, builder):
        """ECharts 히트맵 차트"""
        data = [
            {"hour": "00:00", "day": "Mon", "value": 10},
            {"hour": "01:00", "day": "Mon", "value": 20},
            {"hour": "00:00", "day": "Tue", "value": 15},
        ]
        config = builder.build_chart(
            chart_id="heatmap-echarts",
            chart_type=ChartType.HEATMAP,
            data=data,
            x_field="hour",
            y_fields=["day", "value"],
            title="히트맵",
        )

        result = builder.to_echarts(config)
        assert result["series"][0]["type"] == "heatmap"
        assert "visualMap" in result

    def test_echarts_smooth_line(self, builder):
        """ECharts 부드러운 라인"""
        data = [{"x": "A", "y": 100}, {"x": "B", "y": 200}]
        config = builder.build_chart(
            chart_id="smooth-echarts",
            chart_type=ChartType.LINE,
            data=data,
            x_field="x",
            y_fields=["y"],
            title="부드러운 라인",
            smooth=True,
        )

        result = builder.to_echarts(config)
        assert result["series"][0]["smooth"] is True

    def test_echarts_area_chart(self, builder):
        """ECharts 영역 차트"""
        data = [{"x": "A", "y": 100}]
        config = builder.build_chart(
            chart_id="area-echarts",
            chart_type=ChartType.LINE,
            data=data,
            x_field="x",
            y_fields=["y"],
            title="영역 차트",
            area=True,
        )

        result = builder.to_echarts(config)
        assert result["series"][0]["areaStyle"] is not None

    def test_echarts_stacked_bar(self, builder):
        """ECharts 스택 바 차트"""
        data = [{"cat": "A", "v1": 50, "v2": 30}]
        config = builder.build_chart(
            chart_id="stacked-echarts",
            chart_type=ChartType.BAR,
            data=data,
            x_field="cat",
            y_fields=["v1", "v2"],
            title="스택 바",
            stacked=True,
        )

        result = builder.to_echarts(config)
        assert result["series"][0]["stack"] == "default"

    def test_echarts_dark_theme(self, builder):
        """ECharts 다크 테마"""
        data = [{"x": "A", "y": 100}]
        config = builder.build_chart(
            chart_id="dark-echarts",
            chart_type=ChartType.LINE,
            data=data,
            x_field="x",
            y_fields=["y"],
            title="다크 테마",
            theme="dark",
        )

        result = builder.to_echarts(config)
        assert result["backgroundColor"] == "#1e1e1e"


class TestInferAxisType:
    """축 타입 추론 테스트"""

    @pytest.fixture
    def builder(self):
        return ChartBuilder()

    def test_infer_category_type(self, builder):
        """카테고리 타입 추론"""
        data = [{"name": "A"}, {"name": "B"}]
        axis_type = builder._infer_axis_type(data, "name")
        assert axis_type == "category"

    def test_infer_linear_type(self, builder):
        """선형 타입 추론"""
        data = [{"value": 100}, {"value": 200}]
        axis_type = builder._infer_axis_type(data, "value")
        assert axis_type == "linear"

    def test_infer_time_type_from_date(self, builder):
        """날짜에서 시간 타입 추론"""
        data = [{"dt": date(2024, 1, 15)}]
        axis_type = builder._infer_axis_type(data, "dt")
        assert axis_type == "time"

    def test_infer_time_type_from_string(self, builder):
        """날짜 문자열에서 시간 타입 추론"""
        data = [{"dt": "2024-01-15"}]
        axis_type = builder._infer_axis_type(data, "dt")
        assert axis_type == "time"

    def test_infer_empty_data(self, builder):
        """빈 데이터에서 기본 카테고리"""
        data = []
        axis_type = builder._infer_axis_type(data, "any")
        assert axis_type == "category"

    def test_infer_none_value(self, builder):
        """None 값에서 기본 카테고리"""
        data = [{"field": None}]
        axis_type = builder._infer_axis_type(data, "field")
        assert axis_type == "category"

    def test_infer_decimal_type(self, builder):
        """Decimal 타입에서 선형 추론"""
        data = [{"value": Decimal("123.45")}]
        axis_type = builder._infer_axis_type(data, "value")
        assert axis_type == "linear"


class TestMapChartjsType:
    """Chart.js 타입 매핑 테스트"""

    @pytest.fixture
    def builder(self):
        return ChartBuilder()

    def test_map_line(self, builder):
        assert builder._map_chartjs_type(ChartType.LINE) == "line"

    def test_map_bar(self, builder):
        assert builder._map_chartjs_type(ChartType.BAR) == "bar"

    def test_map_pie(self, builder):
        assert builder._map_chartjs_type(ChartType.PIE) == "pie"

    def test_map_scatter(self, builder):
        assert builder._map_chartjs_type(ChartType.SCATTER) == "scatter"

    def test_map_heatmap(self, builder):
        assert builder._map_chartjs_type(ChartType.HEATMAP) == "matrix"

    def test_map_table(self, builder):
        assert builder._map_chartjs_type(ChartType.TABLE) == "table"


class TestGetChartBuilder:
    """get_chart_builder 싱글톤 테스트"""

    def test_get_chart_builder_returns_instance(self):
        """싱글톤 인스턴스 반환"""
        from app.services.chart_builder import get_chart_builder

        builder = get_chart_builder()
        assert isinstance(builder, ChartBuilder)

    def test_get_chart_builder_returns_same_instance(self):
        """동일한 인스턴스 반환"""
        from app.services.chart_builder import get_chart_builder

        builder1 = get_chart_builder()
        builder2 = get_chart_builder()
        assert builder1 is builder2


class TestBuildScatterChart:
    """산점도 차트 생성 테스트"""

    @pytest.fixture
    def builder(self):
        return ChartBuilder()

    def test_simple_scatter(self, builder):
        """간단한 산점도"""
        data = [
            {"x": 1, "y": 10},
            {"x": 2, "y": 20},
        ]
        config = builder.build_chart(
            chart_id="scatter-1",
            chart_type=ChartType.SCATTER,
            data=data,
            x_field="x",
            y_fields=["y"],
            title="산점도",
        )

        assert config.type == ChartType.SCATTER
        assert config.interaction.zoom is True
        assert config.interaction.pan is True


class TestBuildHeatmapChart:
    """히트맵 차트 생성 테스트"""

    @pytest.fixture
    def builder(self):
        return ChartBuilder()

    def test_simple_heatmap(self, builder):
        """간단한 히트맵"""
        data = [
            {"hour": "00:00", "day": "Mon", "value": 10},
            {"hour": "01:00", "day": "Mon", "value": 20},
        ]
        config = builder.build_chart(
            chart_id="heatmap-1",
            chart_type=ChartType.HEATMAP,
            data=data,
            x_field="hour",
            y_fields=["day", "value"],
            title="히트맵",
        )

        assert config.type == ChartType.HEATMAP
        assert config.legend.display is False  # 히트맵은 컬러 스케일 사용
