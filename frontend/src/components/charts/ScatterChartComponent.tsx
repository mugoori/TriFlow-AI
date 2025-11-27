import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ZAxis,
} from 'recharts';
import { ScatterChartConfig, CHART_COLORS, DEFAULT_CHART_STYLE } from '@/types/chart';

interface ScatterChartComponentProps {
  config: ScatterChartConfig;
}

export function ScatterChartComponent({ config }: ScatterChartComponentProps) {
  const { data, xAxis, yAxis, fill, name } = config;

  return (
    <div className="w-full h-[400px]">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={DEFAULT_CHART_STYLE.margin}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            type="number"
            dataKey={xAxis.dataKey}
            name={xAxis.label || xAxis.dataKey}
            label={{ value: xAxis.label, position: 'insideBottom', offset: -5 }}
            tick={{ fontSize: DEFAULT_CHART_STYLE.fontSize }}
          />
          <YAxis
            type="number"
            dataKey={yAxis.dataKey}
            name={yAxis.label || yAxis.dataKey}
            label={{ value: yAxis.label, angle: -90, position: 'insideLeft' }}
            tick={{ fontSize: DEFAULT_CHART_STYLE.fontSize }}
          />
          <ZAxis range={[60, 400]} />
          <Tooltip
            cursor={{ strokeDasharray: '3 3' }}
            contentStyle={{
              backgroundColor: '#fff',
              border: '1px solid #e5e7eb',
              borderRadius: '6px',
            }}
          />
          <Scatter
            name={name || 'Data'}
            data={data}
            fill={fill || CHART_COLORS[0]}
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
