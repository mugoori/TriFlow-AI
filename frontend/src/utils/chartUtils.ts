/**
 * 차트 유틸리티 함수
 * Recharts 차트 컴포넌트용 공통 헬퍼 함수
 */

export interface ChartSeriesConfig {
  dataKey: string;
  name?: string;
  fill?: string;
  stroke?: string;
}

/**
 * 차트 시리즈 설정을 정규화
 * 문자열 배열 또는 객체 배열을 통일된 형식으로 변환
 */
export function normalizeChartSeries<T extends ChartSeriesConfig>(
  series: (string | T)[]
): T[] {
  return series.map((item) =>
    typeof item === 'string'
      ? ({ dataKey: item, name: item } as T)
      : item
  );
}

export default { normalizeChartSeries };
