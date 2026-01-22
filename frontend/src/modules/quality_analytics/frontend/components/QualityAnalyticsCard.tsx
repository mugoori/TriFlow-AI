/**
 * 품질 분석 - Example Component
 */

interface QualityAnalyticsCardProps {
  title: string;
  value: string | number;
}

export function QualityAnalyticsCard({ title, value }: QualityAnalyticsCardProps) {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-sm font-medium text-gray-500">{title}</h3>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
    </div>
  );
}
