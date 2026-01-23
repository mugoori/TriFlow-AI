import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { AreaChartConfig, CHART_COLORS, DEFAULT_CHART_STYLE } from '@/types/chart';
import { normalizeChartSeries } from '@/utils/chartUtils';

interface AreaChartComponentProps {
  config: AreaChartConfig;
}

export function AreaChartComponent({ config }: AreaChartComponentProps) {
  const { data, xAxis, yAxis, areas } = config;

  // areas가 문자열 배열인 경우 객체 배열로 변환 (Backend 호환성)
  const normalizedAreas = normalizeChartSeries(areas as (string | { dataKey: string; fill?: string; stroke?: string; name?: string })[]);

  return (
    <div className="w-full h-[400px] min-h-[400px]">
      <ResponsiveContainer width="100%" height="100%" minHeight={400}>
        <AreaChart data={data} margin={DEFAULT_CHART_STYLE.margin}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey={xAxis.dataKey}
            label={{ value: xAxis.label, position: 'insideBottom', offset: -5 }}
            tick={{ fontSize: DEFAULT_CHART_STYLE.fontSize }}
          />
          <YAxis
            label={{ value: yAxis.label, angle: -90, position: 'insideLeft' }}
            tick={{ fontSize: DEFAULT_CHART_STYLE.fontSize }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#fff',
              border: '1px solid #e5e7eb',
              borderRadius: '6px',
            }}
          />
          <Legend wrapperStyle={{ fontSize: DEFAULT_CHART_STYLE.fontSize }} />
          {normalizedAreas.map((area, index) => (
            <Area
              key={area.dataKey}
              type="monotone"
              dataKey={area.dataKey}
              fill={area.fill || CHART_COLORS[index % CHART_COLORS.length]}
              stroke={area.stroke || CHART_COLORS[index % CHART_COLORS.length]}
              name={area.name || area.dataKey}
              fillOpacity={0.6}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
