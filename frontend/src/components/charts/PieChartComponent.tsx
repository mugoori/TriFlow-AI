import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import type { PieLabelRenderProps } from 'recharts';
import { PieChartConfig, CHART_COLORS } from '@/types/chart';

interface PieChartComponentProps {
  config: PieChartConfig;
}

export function PieChartComponent({ config }: PieChartComponentProps) {
  const { data, nameKey, valueKey, colors } = config;
  const chartColors = colors || CHART_COLORS;

  // 라벨 렌더링 함수
  const renderLabel = (props: PieLabelRenderProps) => {
    const name = props.name || props.payload?.name || '';
    const value = props.value || 0;
    return `${name}: ${value}`;
  };

  return (
    <div className="w-full h-[400px]">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey={valueKey}
            nameKey={nameKey}
            cx="50%"
            cy="50%"
            outerRadius={120}
            label={renderLabel}
            labelLine={{ stroke: '#94a3b8', strokeWidth: 1 }}
          >
            {data.map((_, index) => (
              <Cell
                key={`cell-${index}`}
                fill={chartColors[index % chartColors.length]}
              />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: '#fff',
              border: '1px solid #e5e7eb',
              borderRadius: '6px',
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
