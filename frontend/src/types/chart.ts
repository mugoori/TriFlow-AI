/**
 * Chart Type Definitions
 * BI Planner Agent가 생성하는 차트 설정의 TypeScript 타입
 */

export type ChartType = 'line' | 'bar' | 'pie' | 'area' | 'scatter' | 'table';

/**
 * 기본 차트 설정
 */
export interface BaseChartConfig {
  type: ChartType;
  data: any[];
  analysis_goal?: string;
}

/**
 * Line Chart 설정
 */
export interface LineChartConfig extends BaseChartConfig {
  type: 'line';
  xAxis: {
    dataKey: string;
    label?: string;
  };
  yAxis: {
    label?: string;
  };
  lines: Array<{
    dataKey: string;
    stroke?: string;
    name?: string;
  }>;
}

/**
 * Bar Chart 설정
 */
export interface BarChartConfig extends BaseChartConfig {
  type: 'bar';
  xAxis: {
    dataKey: string;
    label?: string;
  };
  yAxis: {
    label?: string;
  };
  bars: Array<{
    dataKey: string;
    fill?: string;
    name?: string;
  }>;
}

/**
 * Pie Chart 설정
 */
export interface PieChartConfig extends BaseChartConfig {
  type: 'pie';
  nameKey: string;
  valueKey: string;
  colors?: string[];
}

/**
 * Area Chart 설정
 */
export interface AreaChartConfig extends BaseChartConfig {
  type: 'area';
  xAxis: {
    dataKey: string;
    label?: string;
  };
  yAxis: {
    label?: string;
  };
  areas: Array<{
    dataKey: string;
    fill?: string;
    stroke?: string;
    name?: string;
  }>;
}

/**
 * Scatter Chart 설정
 */
export interface ScatterChartConfig extends BaseChartConfig {
  type: 'scatter';
  xAxis: {
    dataKey: string;
    label?: string;
  };
  yAxis: {
    dataKey: string;
    label?: string;
  };
  name?: string;
  fill?: string;
}

/**
 * Table 설정
 */
export interface TableConfig extends BaseChartConfig {
  type: 'table';
  columns?: Array<{
    key: string;
    label: string;
    width?: string;
  }>;
}

/**
 * 모든 차트 설정 Union Type
 */
export type ChartConfig =
  | LineChartConfig
  | BarChartConfig
  | PieChartConfig
  | AreaChartConfig
  | ScatterChartConfig
  | TableConfig;

/**
 * 기본 차트 색상 팔레트
 */
export const CHART_COLORS = [
  '#8884d8', // Blue
  '#82ca9d', // Green
  '#ffc658', // Yellow
  '#ff7c7c', // Red
  '#8dd1e1', // Cyan
  '#d084d0', // Purple
  '#ffb347', // Orange
  '#a4de6c', // Light Green
];

/**
 * 차트 기본 스타일
 */
export const DEFAULT_CHART_STYLE = {
  margin: { top: 20, right: 30, left: 20, bottom: 20 },
  fontSize: 12,
  fontFamily: 'Inter, system-ui, sans-serif',
};
