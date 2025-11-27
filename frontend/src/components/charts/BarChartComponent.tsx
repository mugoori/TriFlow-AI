import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { BarChartConfig, CHART_COLORS, DEFAULT_CHART_STYLE } from '@/types/chart';

interface BarChartComponentProps {
  config: BarChartConfig;
}

export function BarChartComponent({ config }: BarChartComponentProps) {
  const { data, xAxis, yAxis, bars } = config;

  return (
    <div className="w-full h-[400px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={DEFAULT_CHART_STYLE.margin}>
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
          {bars.map((bar, index) => (
            <Bar
              key={bar.dataKey}
              dataKey={bar.dataKey}
              fill={bar.fill || CHART_COLORS[index % CHART_COLORS.length]}
              name={bar.name || bar.dataKey}
              radius={[4, 4, 0, 0]}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
