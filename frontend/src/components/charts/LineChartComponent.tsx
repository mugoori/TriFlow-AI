import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { LineChartConfig, CHART_COLORS, DEFAULT_CHART_STYLE } from '@/types/chart';

interface LineChartComponentProps {
  config: LineChartConfig;
}

export function LineChartComponent({ config }: LineChartComponentProps) {
  const { data, xAxis, yAxis, lines } = config;

  return (
    <div className="w-full h-[400px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={DEFAULT_CHART_STYLE.margin}>
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
          {lines.map((line, index) => (
            <Line
              key={line.dataKey}
              type="monotone"
              dataKey={line.dataKey}
              stroke={line.stroke || CHART_COLORS[index % CHART_COLORS.length]}
              name={line.name || line.dataKey}
              strokeWidth={2}
              dot={{ r: 4 }}
              activeDot={{ r: 6 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
