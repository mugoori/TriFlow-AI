import { ChartConfig } from '@/types/chart';
import { LineChartComponent } from './LineChartComponent';
import { BarChartComponent } from './BarChartComponent';
import { PieChartComponent } from './PieChartComponent';
import { AreaChartComponent } from './AreaChartComponent';
import { ScatterChartComponent } from './ScatterChartComponent';
import { TableComponent } from './TableComponent';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertCircle } from 'lucide-react';

interface ChartRendererProps {
  config: ChartConfig | null;
  error?: string;
}

/**
 * ChartRenderer
 * BI Planner Agent가 생성한 차트 설정을 받아서 적절한 차트 컴포넌트를 렌더링
 */
export function ChartRenderer({ config, error }: ChartRendererProps) {
  // Error state
  if (error) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  // No config
  if (!config) {
    return null;
  }

  // Validate config
  if (!config.type || !config.data) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          Invalid chart configuration: missing type or data
        </AlertDescription>
      </Alert>
    );
  }

  // Empty data
  if (!Array.isArray(config.data) || config.data.length === 0) {
    return (
      <Alert>
        <AlertDescription>No data available to display</AlertDescription>
      </Alert>
    );
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="text-lg font-semibold">
          {getChartTitle(config.type)}
        </CardTitle>
        {config.analysis_goal && (
          <CardDescription>{config.analysis_goal}</CardDescription>
        )}
      </CardHeader>
      <CardContent>{renderChart(config)}</CardContent>
    </Card>
  );
}

/**
 * Render appropriate chart component based on type
 */
function renderChart(config: ChartConfig): JSX.Element {
  try {
    switch (config.type) {
      case 'line':
        return <LineChartComponent config={config} />;
      case 'bar':
        return <BarChartComponent config={config} />;
      case 'pie':
        return <PieChartComponent config={config} />;
      case 'area':
        return <AreaChartComponent config={config} />;
      case 'scatter':
        return <ScatterChartComponent config={config} />;
      case 'table':
        return <TableComponent config={config} />;
      default:
        return (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              Unsupported chart type: {(config as any).type}
            </AlertDescription>
          </Alert>
        );
    }
  } catch (err) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          Failed to render chart: {err instanceof Error ? err.message : 'Unknown error'}
        </AlertDescription>
      </Alert>
    );
  }
}

/**
 * Get human-readable chart title
 */
function getChartTitle(type: string): string {
  const titles: Record<string, string> = {
    line: 'Line Chart',
    bar: 'Bar Chart',
    pie: 'Pie Chart',
    area: 'Area Chart',
    scatter: 'Scatter Plot',
    table: 'Data Table',
  };
  return titles[type] || 'Chart';
}
