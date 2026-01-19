"""
Chart Builder Service
스펙 참조: B-2-2, BI-FR-040

차트 설정 생성 서비스:
- 6가지 차트 타입: line, bar, pie, scatter, heatmap, table
- Chart.js / ECharts 호환 설정 생성
- 반응형 및 인터랙티브 옵션
"""
import logging
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ChartType(str, Enum):
    """지원 차트 타입"""
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    SCATTER = "scatter"
    HEATMAP = "heatmap"
    TABLE = "table"


class AxisConfig(BaseModel):
    """축 설정"""
    field: str
    label: str
    type: str = "category"  # category, linear, time, log
    format: Optional[str] = None  # date format, number format
    min: Optional[float] = None
    max: Optional[float] = None
    position: str = "bottom"  # bottom, top, left, right


class SeriesConfig(BaseModel):
    """시리즈 설정"""
    name: str
    field: str
    type: Optional[str] = None  # line, bar (for mixed charts)
    color: Optional[str] = None
    y_axis_id: Optional[str] = None  # for dual-axis charts
    stack: Optional[str] = None  # for stacked charts
    area: bool = False  # for area charts
    smooth: bool = False  # for smooth line


class LegendConfig(BaseModel):
    """범례 설정"""
    display: bool = True
    position: str = "top"  # top, bottom, left, right
    align: str = "center"  # start, center, end


class TooltipConfig(BaseModel):
    """툴팁 설정"""
    enabled: bool = True
    mode: str = "index"  # index, point, nearest
    intersect: bool = False
    format: Optional[Dict[str, str]] = None


class InteractionConfig(BaseModel):
    """인터랙션 설정"""
    zoom: bool = False
    pan: bool = False
    hover: bool = True
    click: bool = True


class ResponsiveConfig(BaseModel):
    """반응형 설정"""
    maintain_aspect_ratio: bool = True
    aspect_ratio: float = 2.0
    breakpoints: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class ChartConfig(BaseModel):
    """완전한 차트 설정"""
    chart_id: str
    type: ChartType
    title: str
    subtitle: Optional[str] = None
    x_axis: Optional[AxisConfig] = None
    y_axis: Optional[AxisConfig] = None
    y_axis_right: Optional[AxisConfig] = None  # for dual-axis
    series: List[SeriesConfig]
    data: List[Dict[str, Any]]
    legend: LegendConfig = Field(default_factory=LegendConfig)
    tooltip: TooltipConfig = Field(default_factory=TooltipConfig)
    interaction: InteractionConfig = Field(default_factory=InteractionConfig)
    responsive: ResponsiveConfig = Field(default_factory=ResponsiveConfig)
    annotations: List[Dict[str, Any]] = Field(default_factory=list)
    theme: str = "default"  # default, dark, light


class ChartBuilder:
    """
    Chart Builder 서비스

    데이터와 설정을 받아 Chart.js/ECharts 호환 차트 설정 생성
    """

    # 기본 색상 팔레트
    DEFAULT_COLORS = [
        "#4CAF50",  # Green
        "#2196F3",  # Blue
        "#FFC107",  # Amber
        "#F44336",  # Red
        "#9C27B0",  # Purple
        "#00BCD4",  # Cyan
        "#FF5722",  # Deep Orange
        "#795548",  # Brown
        "#607D8B",  # Blue Grey
        "#E91E63",  # Pink
    ]

    # 테마 설정
    THEMES = {
        "default": {
            "background": "#ffffff",
            "text": "#333333",
            "grid": "#e0e0e0",
            "border": "#cccccc",
        },
        "dark": {
            "background": "#1e1e1e",
            "text": "#e0e0e0",
            "grid": "#404040",
            "border": "#606060",
        },
        "light": {
            "background": "#fafafa",
            "text": "#424242",
            "grid": "#f0f0f0",
            "border": "#e0e0e0",
        },
    }

    def __init__(self):
        pass

    def build_chart(
        self,
        chart_id: str,
        chart_type: ChartType,
        data: List[Dict[str, Any]],
        x_field: str,
        y_fields: List[str],
        title: str,
        subtitle: Optional[str] = None,
        x_label: Optional[str] = None,
        y_label: Optional[str] = None,
        colors: Optional[List[str]] = None,
        theme: str = "default",
        **kwargs
    ) -> ChartConfig:
        """
        차트 설정 생성

        Args:
            chart_id: 차트 고유 ID
            chart_type: 차트 타입
            data: 차트 데이터
            x_field: X축 필드명
            y_fields: Y축 필드명 목록
            title: 차트 제목
            subtitle: 부제목
            x_label: X축 레이블
            y_label: Y축 레이블
            colors: 색상 목록
            theme: 테마
            **kwargs: 추가 옵션

        Returns:
            ChartConfig: 완전한 차트 설정
        """
        # 색상 설정
        if colors is None:
            colors = self.DEFAULT_COLORS

        # 데이터 변환 (JSON 직렬화 가능하도록)
        normalized_data = self._normalize_data(data)

        # 차트 타입별 설정 생성
        if chart_type == ChartType.LINE:
            return self._build_line_chart(
                chart_id, normalized_data, x_field, y_fields,
                title, subtitle, x_label, y_label, colors, theme, **kwargs
            )
        elif chart_type == ChartType.BAR:
            return self._build_bar_chart(
                chart_id, normalized_data, x_field, y_fields,
                title, subtitle, x_label, y_label, colors, theme, **kwargs
            )
        elif chart_type == ChartType.PIE:
            return self._build_pie_chart(
                chart_id, normalized_data, x_field, y_fields[0] if y_fields else "value",
                title, subtitle, colors, theme, **kwargs
            )
        elif chart_type == ChartType.SCATTER:
            return self._build_scatter_chart(
                chart_id, normalized_data, x_field, y_fields,
                title, subtitle, x_label, y_label, colors, theme, **kwargs
            )
        elif chart_type == ChartType.HEATMAP:
            return self._build_heatmap_chart(
                chart_id, normalized_data, x_field, y_fields,
                title, subtitle, colors, theme, **kwargs
            )
        elif chart_type == ChartType.TABLE:
            return self._build_table_chart(
                chart_id, normalized_data,
                title, subtitle, **kwargs
            )
        else:
            raise ValueError(f"Unsupported chart type: {chart_type}")

    def _normalize_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """데이터 정규화 (JSON 직렬화 가능하도록)"""
        normalized = []
        for row in data:
            new_row = {}
            for key, value in row.items():
                if isinstance(value, Decimal):
                    new_row[key] = float(value)
                elif isinstance(value, (date, datetime)):
                    new_row[key] = value.isoformat()
                else:
                    new_row[key] = value
            normalized.append(new_row)
        return normalized

    def _build_line_chart(
        self,
        chart_id: str,
        data: List[Dict[str, Any]],
        x_field: str,
        y_fields: List[str],
        title: str,
        subtitle: Optional[str],
        x_label: Optional[str],
        y_label: Optional[str],
        colors: List[str],
        theme: str,
        **kwargs
    ) -> ChartConfig:
        """라인 차트 생성"""
        series = []
        for i, field in enumerate(y_fields):
            color = colors[i % len(colors)]
            series.append(SeriesConfig(
                name=kwargs.get(f"{field}_label", field),
                field=field,
                color=color,
                smooth=kwargs.get("smooth", False),
                area=kwargs.get("area", False),
                y_axis_id=kwargs.get(f"{field}_axis_id"),
            ))

        x_axis = AxisConfig(
            field=x_field,
            label=x_label or x_field,
            type=self._infer_axis_type(data, x_field),
            position="bottom",
        )

        y_axis = AxisConfig(
            field=y_fields[0] if y_fields else "value",
            label=y_label or (y_fields[0] if y_fields else "Value"),
            type="linear",
            position="left",
        )

        # 이중 축 지원
        y_axis_right = None
        if kwargs.get("dual_axis") and len(y_fields) > 1:
            y_axis_right = AxisConfig(
                field=y_fields[1],
                label=kwargs.get(f"{y_fields[1]}_label", y_fields[1]),
                type="linear",
                position="right",
            )

        return ChartConfig(
            chart_id=chart_id,
            type=ChartType.LINE,
            title=title,
            subtitle=subtitle,
            x_axis=x_axis,
            y_axis=y_axis,
            y_axis_right=y_axis_right,
            series=series,
            data=data,
            legend=LegendConfig(
                display=len(series) > 1,
                position="top",
            ),
            tooltip=TooltipConfig(
                enabled=True,
                mode="index",
            ),
            interaction=InteractionConfig(
                zoom=kwargs.get("zoom", False),
                pan=kwargs.get("pan", False),
            ),
            theme=theme,
            annotations=kwargs.get("annotations", []),
        )

    def _build_bar_chart(
        self,
        chart_id: str,
        data: List[Dict[str, Any]],
        x_field: str,
        y_fields: List[str],
        title: str,
        subtitle: Optional[str],
        x_label: Optional[str],
        y_label: Optional[str],
        colors: List[str],
        theme: str,
        **kwargs
    ) -> ChartConfig:
        """바 차트 생성"""
        stacked = kwargs.get("stacked", False)
        horizontal = kwargs.get("horizontal", False)

        series = []
        for i, field in enumerate(y_fields):
            color = colors[i % len(colors)]
            series.append(SeriesConfig(
                name=kwargs.get(f"{field}_label", field),
                field=field,
                color=color,
                stack="default" if stacked else None,
            ))

        x_axis = AxisConfig(
            field=x_field,
            label=x_label or x_field,
            type="category",
            position="left" if horizontal else "bottom",
        )

        y_axis = AxisConfig(
            field=y_fields[0] if y_fields else "value",
            label=y_label or (y_fields[0] if y_fields else "Value"),
            type="linear",
            position="bottom" if horizontal else "left",
        )

        return ChartConfig(
            chart_id=chart_id,
            type=ChartType.BAR,
            title=title,
            subtitle=subtitle,
            x_axis=x_axis,
            y_axis=y_axis,
            series=series,
            data=data,
            legend=LegendConfig(
                display=len(series) > 1,
                position="top",
            ),
            tooltip=TooltipConfig(
                enabled=True,
                mode="index",
            ),
            theme=theme,
        )

    def _build_pie_chart(
        self,
        chart_id: str,
        data: List[Dict[str, Any]],
        label_field: str,
        value_field: str,
        title: str,
        subtitle: Optional[str],
        colors: List[str],
        theme: str,
        **kwargs
    ) -> ChartConfig:
        """파이 차트 생성"""
        kwargs.get("donut", False)

        series = [SeriesConfig(
            name=value_field,
            field=value_field,
        )]

        # 파이 차트용 데이터에 색상 추가
        for i, row in enumerate(data):
            row["_color"] = colors[i % len(colors)]

        return ChartConfig(
            chart_id=chart_id,
            type=ChartType.PIE,
            title=title,
            subtitle=subtitle,
            x_axis=AxisConfig(
                field=label_field,
                label=label_field,
                type="category",
            ),
            series=series,
            data=data,
            legend=LegendConfig(
                display=True,
                position="right",
            ),
            tooltip=TooltipConfig(
                enabled=True,
                mode="point",
            ),
            theme=theme,
        )

    def _build_scatter_chart(
        self,
        chart_id: str,
        data: List[Dict[str, Any]],
        x_field: str,
        y_fields: List[str],
        title: str,
        subtitle: Optional[str],
        x_label: Optional[str],
        y_label: Optional[str],
        colors: List[str],
        theme: str,
        **kwargs
    ) -> ChartConfig:
        """산점도 차트 생성"""
        series = []
        if len(y_fields) >= 1:
            series.append(SeriesConfig(
                name=kwargs.get("series_label", f"{x_field} vs {y_fields[0]}"),
                field=y_fields[0],
                color=colors[0],
            ))

        # 버블 차트 지원 (세 번째 필드가 크기)
        kwargs.get("size_field")

        x_axis = AxisConfig(
            field=x_field,
            label=x_label or x_field,
            type="linear",
            position="bottom",
        )

        y_axis = AxisConfig(
            field=y_fields[0] if y_fields else "value",
            label=y_label or (y_fields[0] if y_fields else "Value"),
            type="linear",
            position="left",
        )

        return ChartConfig(
            chart_id=chart_id,
            type=ChartType.SCATTER,
            title=title,
            subtitle=subtitle,
            x_axis=x_axis,
            y_axis=y_axis,
            series=series,
            data=data,
            legend=LegendConfig(
                display=len(series) > 1,
                position="top",
            ),
            tooltip=TooltipConfig(
                enabled=True,
                mode="point",
            ),
            interaction=InteractionConfig(
                zoom=True,
                pan=True,
            ),
            theme=theme,
        )

    def _build_heatmap_chart(
        self,
        chart_id: str,
        data: List[Dict[str, Any]],
        x_field: str,
        y_fields: List[str],
        title: str,
        subtitle: Optional[str],
        colors: List[str],
        theme: str,
        **kwargs
    ) -> ChartConfig:
        """히트맵 차트 생성"""
        y_field = kwargs.get("y_field", y_fields[0] if y_fields else "y")
        value_field = kwargs.get("value_field", y_fields[1] if len(y_fields) > 1 else "value")

        series = [SeriesConfig(
            name=value_field,
            field=value_field,
        )]

        x_axis = AxisConfig(
            field=x_field,
            label=kwargs.get("x_label", x_field),
            type="category",
            position="bottom",
        )

        y_axis = AxisConfig(
            field=y_field,
            label=kwargs.get("y_label", y_field),
            type="category",
            position="left",
        )

        return ChartConfig(
            chart_id=chart_id,
            type=ChartType.HEATMAP,
            title=title,
            subtitle=subtitle,
            x_axis=x_axis,
            y_axis=y_axis,
            series=series,
            data=data,
            legend=LegendConfig(
                display=False,  # 히트맵은 컬러 스케일 사용
            ),
            tooltip=TooltipConfig(
                enabled=True,
                mode="point",
            ),
            theme=theme,
        )

    def _build_table_chart(
        self,
        chart_id: str,
        data: List[Dict[str, Any]],
        title: str,
        subtitle: Optional[str],
        **kwargs
    ) -> ChartConfig:
        """테이블 차트 생성"""
        columns = kwargs.get("columns", list(data[0].keys()) if data else [])

        series = [SeriesConfig(
            name=col,
            field=col,
        ) for col in columns]

        return ChartConfig(
            chart_id=chart_id,
            type=ChartType.TABLE,
            title=title,
            subtitle=subtitle,
            series=series,
            data=data,
            legend=LegendConfig(display=False),
            tooltip=TooltipConfig(enabled=False),
            theme=kwargs.get("theme", "default"),
        )

    def _infer_axis_type(self, data: List[Dict[str, Any]], field: str) -> str:
        """데이터에서 축 타입 추론"""
        if not data:
            return "category"

        sample = data[0].get(field)
        if sample is None:
            return "category"

        if isinstance(sample, (date, datetime)) or (
            isinstance(sample, str) and len(sample) == 10 and sample[4] == "-"
        ):
            return "time"

        if isinstance(sample, (int, float, Decimal)):
            return "linear"

        return "category"

    def to_chartjs(self, config: ChartConfig) -> Dict[str, Any]:
        """
        ChartConfig를 Chart.js 형식으로 변환

        Chart.js v4 형식 출력
        """
        theme = self.THEMES.get(config.theme, self.THEMES["default"])

        # 기본 Chart.js 설정
        chartjs_config = {
            "type": self._map_chartjs_type(config.type),
            "data": self._build_chartjs_data(config),
            "options": self._build_chartjs_options(config, theme),
        }

        return chartjs_config

    def _map_chartjs_type(self, chart_type: ChartType) -> str:
        """ChartType을 Chart.js 타입으로 매핑"""
        mapping = {
            ChartType.LINE: "line",
            ChartType.BAR: "bar",
            ChartType.PIE: "pie",
            ChartType.SCATTER: "scatter",
            ChartType.HEATMAP: "matrix",  # Chart.js matrix plugin
            ChartType.TABLE: "table",  # Custom plugin
        }
        return mapping.get(chart_type, "line")

    def _build_chartjs_data(self, config: ChartConfig) -> Dict[str, Any]:
        """Chart.js 데이터 섹션 생성"""
        if config.type == ChartType.PIE:
            return self._build_chartjs_pie_data(config)
        elif config.type == ChartType.SCATTER:
            return self._build_chartjs_scatter_data(config)
        else:
            return self._build_chartjs_standard_data(config)

    def _build_chartjs_standard_data(self, config: ChartConfig) -> Dict[str, Any]:
        """표준 Chart.js 데이터 (line, bar)"""
        labels = []
        if config.x_axis:
            labels = [row.get(config.x_axis.field) for row in config.data]

        datasets = []
        for i, series in enumerate(config.series):
            dataset = {
                "label": series.name,
                "data": [row.get(series.field) for row in config.data],
                "backgroundColor": series.color or self.DEFAULT_COLORS[i % len(self.DEFAULT_COLORS)],
                "borderColor": series.color or self.DEFAULT_COLORS[i % len(self.DEFAULT_COLORS)],
            }

            if config.type == ChartType.LINE:
                dataset["fill"] = series.area
                dataset["tension"] = 0.4 if series.smooth else 0

            if series.stack:
                dataset["stack"] = series.stack

            if series.y_axis_id:
                dataset["yAxisID"] = series.y_axis_id

            datasets.append(dataset)

        return {
            "labels": labels,
            "datasets": datasets,
        }

    def _build_chartjs_pie_data(self, config: ChartConfig) -> Dict[str, Any]:
        """파이 차트 데이터"""
        labels = []
        values = []
        colors = []

        label_field = config.x_axis.field if config.x_axis else "label"
        value_field = config.series[0].field if config.series else "value"

        for row in config.data:
            labels.append(row.get(label_field))
            values.append(row.get(value_field))
            colors.append(row.get("_color", self.DEFAULT_COLORS[len(colors) % len(self.DEFAULT_COLORS)]))

        return {
            "labels": labels,
            "datasets": [{
                "data": values,
                "backgroundColor": colors,
            }],
        }

    def _build_chartjs_scatter_data(self, config: ChartConfig) -> Dict[str, Any]:
        """산점도 데이터"""
        x_field = config.x_axis.field if config.x_axis else "x"
        y_field = config.series[0].field if config.series else "y"

        data_points = []
        for row in config.data:
            data_points.append({
                "x": row.get(x_field),
                "y": row.get(y_field),
            })

        return {
            "datasets": [{
                "label": config.series[0].name if config.series else "Data",
                "data": data_points,
                "backgroundColor": config.series[0].color if config.series else self.DEFAULT_COLORS[0],
            }],
        }

    def _build_chartjs_options(self, config: ChartConfig, theme: Dict[str, str]) -> Dict[str, Any]:
        """Chart.js 옵션 섹션 생성"""
        options = {
            "responsive": True,
            "maintainAspectRatio": config.responsive.maintain_aspect_ratio,
            "plugins": {
                "title": {
                    "display": bool(config.title),
                    "text": config.title,
                    "color": theme["text"],
                },
                "subtitle": {
                    "display": bool(config.subtitle),
                    "text": config.subtitle or "",
                    "color": theme["text"],
                },
                "legend": {
                    "display": config.legend.display,
                    "position": config.legend.position,
                },
                "tooltip": {
                    "enabled": config.tooltip.enabled,
                    "mode": config.tooltip.mode,
                    "intersect": config.tooltip.intersect,
                },
            },
        }

        # 축 설정 (파이 차트 제외)
        if config.type not in [ChartType.PIE]:
            scales = {}

            if config.x_axis:
                scales["x"] = {
                    "display": True,
                    "title": {
                        "display": True,
                        "text": config.x_axis.label,
                        "color": theme["text"],
                    },
                    "type": config.x_axis.type if config.x_axis.type != "category" else "category",
                    "grid": {
                        "color": theme["grid"],
                    },
                    "ticks": {
                        "color": theme["text"],
                    },
                }

            if config.y_axis:
                scales["y"] = {
                    "display": True,
                    "position": config.y_axis.position,
                    "title": {
                        "display": True,
                        "text": config.y_axis.label,
                        "color": theme["text"],
                    },
                    "grid": {
                        "color": theme["grid"],
                    },
                    "ticks": {
                        "color": theme["text"],
                    },
                }

                if config.y_axis.min is not None:
                    scales["y"]["min"] = config.y_axis.min
                if config.y_axis.max is not None:
                    scales["y"]["max"] = config.y_axis.max

            # 이중 축
            if config.y_axis_right:
                scales["y-right"] = {
                    "display": True,
                    "position": "right",
                    "title": {
                        "display": True,
                        "text": config.y_axis_right.label,
                        "color": theme["text"],
                    },
                    "grid": {
                        "drawOnChartArea": False,
                    },
                    "ticks": {
                        "color": theme["text"],
                    },
                }

            options["scales"] = scales

        # 인터랙션 설정
        if config.interaction.zoom:
            options["plugins"]["zoom"] = {
                "zoom": {
                    "wheel": {"enabled": True},
                    "pinch": {"enabled": True},
                    "mode": "xy",
                },
                "pan": {
                    "enabled": config.interaction.pan,
                    "mode": "xy",
                },
            }

        return options

    def to_echarts(self, config: ChartConfig) -> Dict[str, Any]:
        """
        ChartConfig를 ECharts 형식으로 변환

        ECharts v5 형식 출력
        """
        theme = self.THEMES.get(config.theme, self.THEMES["default"])

        echarts_config = {
            "title": {
                "text": config.title,
                "subtext": config.subtitle or "",
                "textStyle": {"color": theme["text"]},
            },
            "tooltip": {
                "show": config.tooltip.enabled,
                "trigger": "axis" if config.type in [ChartType.LINE, ChartType.BAR] else "item",
            },
            "legend": {
                "show": config.legend.display,
                "orient": "horizontal" if config.legend.position in ["top", "bottom"] else "vertical",
                "top": config.legend.position if config.legend.position == "top" else None,
                "bottom": 10 if config.legend.position == "bottom" else None,
                "left": "center" if config.legend.align == "center" else config.legend.align,
            },
            "backgroundColor": theme["background"],
        }

        # 차트 타입별 설정
        if config.type == ChartType.LINE:
            echarts_config.update(self._build_echarts_line(config, theme))
        elif config.type == ChartType.BAR:
            echarts_config.update(self._build_echarts_bar(config, theme))
        elif config.type == ChartType.PIE:
            echarts_config.update(self._build_echarts_pie(config))
        elif config.type == ChartType.SCATTER:
            echarts_config.update(self._build_echarts_scatter(config, theme))
        elif config.type == ChartType.HEATMAP:
            echarts_config.update(self._build_echarts_heatmap(config))

        return echarts_config

    def _build_echarts_line(self, config: ChartConfig, theme: Dict[str, str]) -> Dict[str, Any]:
        """ECharts 라인 차트 설정"""
        x_data = []
        if config.x_axis:
            x_data = [row.get(config.x_axis.field) for row in config.data]

        series = []
        for i, s in enumerate(config.series):
            series.append({
                "name": s.name,
                "type": "line",
                "smooth": s.smooth,
                "areaStyle": {} if s.area else None,
                "data": [row.get(s.field) for row in config.data],
                "itemStyle": {"color": s.color or self.DEFAULT_COLORS[i % len(self.DEFAULT_COLORS)]},
            })

        return {
            "xAxis": {
                "type": "category",
                "data": x_data,
                "axisLabel": {"color": theme["text"]},
            },
            "yAxis": {
                "type": "value",
                "name": config.y_axis.label if config.y_axis else "",
                "axisLabel": {"color": theme["text"]},
            },
            "series": series,
        }

    def _build_echarts_bar(self, config: ChartConfig, theme: Dict[str, str]) -> Dict[str, Any]:
        """ECharts 바 차트 설정"""
        x_data = []
        if config.x_axis:
            x_data = [row.get(config.x_axis.field) for row in config.data]

        series = []
        for i, s in enumerate(config.series):
            series.append({
                "name": s.name,
                "type": "bar",
                "stack": s.stack,
                "data": [row.get(s.field) for row in config.data],
                "itemStyle": {"color": s.color or self.DEFAULT_COLORS[i % len(self.DEFAULT_COLORS)]},
            })

        return {
            "xAxis": {
                "type": "category",
                "data": x_data,
                "axisLabel": {"color": theme["text"]},
            },
            "yAxis": {
                "type": "value",
                "name": config.y_axis.label if config.y_axis else "",
                "axisLabel": {"color": theme["text"]},
            },
            "series": series,
        }

    def _build_echarts_pie(self, config: ChartConfig) -> Dict[str, Any]:
        """ECharts 파이 차트 설정"""
        label_field = config.x_axis.field if config.x_axis else "label"
        value_field = config.series[0].field if config.series else "value"

        data = []
        for i, row in enumerate(config.data):
            data.append({
                "name": row.get(label_field),
                "value": row.get(value_field),
                "itemStyle": {"color": row.get("_color", self.DEFAULT_COLORS[i % len(self.DEFAULT_COLORS)])},
            })

        return {
            "series": [{
                "name": config.title,
                "type": "pie",
                "radius": "50%",
                "data": data,
                "emphasis": {
                    "itemStyle": {
                        "shadowBlur": 10,
                        "shadowOffsetX": 0,
                        "shadowColor": "rgba(0, 0, 0, 0.5)",
                    },
                },
            }],
        }

    def _build_echarts_scatter(self, config: ChartConfig, theme: Dict[str, str]) -> Dict[str, Any]:
        """ECharts 산점도 설정"""
        x_field = config.x_axis.field if config.x_axis else "x"
        y_field = config.series[0].field if config.series else "y"

        data = [[row.get(x_field), row.get(y_field)] for row in config.data]

        return {
            "xAxis": {
                "type": "value",
                "name": config.x_axis.label if config.x_axis else "",
                "axisLabel": {"color": theme["text"]},
            },
            "yAxis": {
                "type": "value",
                "name": config.y_axis.label if config.y_axis else "",
                "axisLabel": {"color": theme["text"]},
            },
            "series": [{
                "type": "scatter",
                "data": data,
                "itemStyle": {"color": config.series[0].color if config.series else self.DEFAULT_COLORS[0]},
            }],
        }

    def _build_echarts_heatmap(self, config: ChartConfig) -> Dict[str, Any]:
        """ECharts 히트맵 설정"""
        x_field = config.x_axis.field if config.x_axis else "x"
        y_field = config.y_axis.field if config.y_axis else "y"
        value_field = config.series[0].field if config.series else "value"

        # 고유값 추출
        x_values = sorted(set(row.get(x_field) for row in config.data))
        y_values = sorted(set(row.get(y_field) for row in config.data))

        data = []
        for row in config.data:
            x_idx = x_values.index(row.get(x_field))
            y_idx = y_values.index(row.get(y_field))
            data.append([x_idx, y_idx, row.get(value_field)])

        values = [d[2] for d in data if d[2] is not None]
        min_val = min(values) if values else 0
        max_val = max(values) if values else 100

        return {
            "xAxis": {
                "type": "category",
                "data": x_values,
            },
            "yAxis": {
                "type": "category",
                "data": y_values,
            },
            "visualMap": {
                "min": min_val,
                "max": max_val,
                "calculable": True,
                "orient": "horizontal",
                "left": "center",
                "bottom": "15%",
            },
            "series": [{
                "type": "heatmap",
                "data": data,
                "label": {"show": True},
                "emphasis": {
                    "itemStyle": {"shadowBlur": 10, "shadowColor": "rgba(0, 0, 0, 0.5)"},
                },
            }],
        }


# 전역 인스턴스
_chart_builder: Optional[ChartBuilder] = None


def get_chart_builder() -> ChartBuilder:
    """ChartBuilder 싱글톤 인스턴스 반환"""
    global _chart_builder
    if _chart_builder is None:
        _chart_builder = ChartBuilder()
    return _chart_builder
