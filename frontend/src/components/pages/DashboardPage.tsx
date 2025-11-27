/**
 * DashboardPage
 * 실제 센서 데이터 API 연동 대시보드 페이지
 */

import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  BarChart3, TrendingUp, AlertTriangle, X, LayoutDashboard, RefreshCw,
  Thermometer, Gauge, Droplets, Activity, Loader2
} from 'lucide-react';
import { useDashboard } from '@/contexts/DashboardContext';
import { ChartRenderer } from '@/components/charts';
import { sensorService, SensorSummaryItem, SensorDataItem } from '@/services/sensorService';

interface DashboardStats {
  totalReadings: number;
  avgTemperature: number;
  avgPressure: number;
  avgHumidity: number;
  activeLines: number;
  alerts: number;
}

export function DashboardPage() {
  const { savedCharts, removeChart } = useDashboard();
  const [stats, setStats] = useState<DashboardStats>({
    totalReadings: 0,
    avgTemperature: 0,
    avgPressure: 0,
    avgHumidity: 0,
    activeLines: 0,
    alerts: 0,
  });
  const [lineSummary, setLineSummary] = useState<SensorSummaryItem[]>([]);
  const [recentData, setRecentData] = useState<SensorDataItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchDashboardData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      // 병렬로 API 호출
      const [summaryRes, dataRes] = await Promise.all([
        sensorService.getSummary(),
        sensorService.getData({ page_size: 10 }),
      ]);

      // 라인별 요약 데이터
      setLineSummary(summaryRes.summary);
      setRecentData(dataRes.data);

      // 통계 계산
      if (summaryRes.summary.length > 0) {
        const totalReadings = summaryRes.summary.reduce((sum, line) => sum + line.total_readings, 0);
        const validTemps = summaryRes.summary.filter(line => line.avg_temperature != null);
        const validPress = summaryRes.summary.filter(line => line.avg_pressure != null);
        const validHum = summaryRes.summary.filter(line => line.avg_humidity != null);

        const avgTemp = validTemps.length > 0
          ? validTemps.reduce((sum, line) => sum + (line.avg_temperature || 0), 0) / validTemps.length
          : 0;
        const avgPres = validPress.length > 0
          ? validPress.reduce((sum, line) => sum + (line.avg_pressure || 0), 0) / validPress.length
          : 0;
        const avgHum = validHum.length > 0
          ? validHum.reduce((sum, line) => sum + (line.avg_humidity || 0), 0) / validHum.length
          : 0;

        // 임계값 초과 알림 계산 (온도 > 70 또는 압력 > 8)
        const alertCount = summaryRes.summary.filter(
          line => (line.avg_temperature && line.avg_temperature > 70) || (line.avg_pressure && line.avg_pressure > 8)
        ).length;

        setStats({
          totalReadings,
          avgTemperature: Math.round(avgTemp * 10) / 10,
          avgPressure: Math.round(avgPres * 100) / 100,
          avgHumidity: Math.round(avgHum * 10) / 10,
          activeLines: summaryRes.summary.length,
          alerts: alertCount,
        });
      }

      setLastUpdated(new Date());
    } catch (err) {
      console.error('Dashboard data fetch failed:', err);
      setError(err instanceof Error ? err.message : 'Failed to load dashboard data');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    // 30초마다 자동 갱신
    const interval = setInterval(fetchDashboardData, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="h-full overflow-y-auto">
      <div className="p-6 space-y-6">
        {/* Header with refresh button */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-50">Dashboard</h2>
            {lastUpdated && (
              <p className="text-sm text-slate-500">
                마지막 업데이트: {lastUpdated.toLocaleTimeString('ko-KR')}
              </p>
            )}
          </div>
          <button
            onClick={fetchDashboardData}
            disabled={isLoading}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4" />
            )}
            새로고침
          </button>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
            <div className="flex items-center gap-2 text-red-600 dark:text-red-400">
              <AlertTriangle className="w-5 h-5" />
              <span>{error}</span>
            </div>
          </div>
        )}

        {/* Stats Grid - 실제 센서 데이터 */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="평균 온도"
            value={isLoading ? '-' : stats.avgTemperature.toFixed(1)}
            unit="°C"
            subtitle={`${stats.activeLines}개 라인`}
            icon={Thermometer}
            iconBgColor="bg-orange-100 dark:bg-orange-900"
            iconColor="text-orange-600 dark:text-orange-400"
          />
          <StatCard
            title="평균 압력"
            value={isLoading ? '-' : stats.avgPressure.toFixed(2)}
            unit="bar"
            subtitle="최근 24시간"
            icon={Gauge}
            iconBgColor="bg-blue-100 dark:bg-blue-900"
            iconColor="text-blue-600 dark:text-blue-400"
          />
          <StatCard
            title="평균 습도"
            value={isLoading ? '-' : stats.avgHumidity.toFixed(1)}
            unit="%"
            subtitle="최근 24시간"
            icon={Droplets}
            iconBgColor="bg-cyan-100 dark:bg-cyan-900"
            iconColor="text-cyan-600 dark:text-cyan-400"
          />
          <StatCard
            title="센서 데이터"
            value={isLoading ? '-' : stats.totalReadings.toLocaleString()}
            unit="건"
            subtitle={stats.alerts > 0 ? `${stats.alerts}건 임계값 초과` : '정상'}
            icon={stats.alerts > 0 ? AlertTriangle : Activity}
            iconBgColor={stats.alerts > 0 ? "bg-red-100 dark:bg-red-900" : "bg-green-100 dark:bg-green-900"}
            iconColor={stats.alerts > 0 ? "text-red-600 dark:text-red-400" : "text-green-600 dark:text-green-400"}
          />
        </div>

        {/* 라인별 센서 현황 */}
        {lineSummary.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="w-5 h-5" />
                라인별 센서 현황
              </CardTitle>
              <CardDescription>최근 24시간 평균값</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {lineSummary.map((line) => (
                  <div
                    key={line.line_code}
                    className="p-4 bg-slate-50 dark:bg-slate-800 rounded-lg"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <span className="font-semibold text-slate-900 dark:text-slate-50">
                        {line.line_code}
                      </span>
                      <span className="text-xs text-slate-500">
                        {line.total_readings.toLocaleString()} readings
                      </span>
                    </div>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-slate-600 dark:text-slate-400">온도</span>
                        <span className={`font-medium ${
                          (line.avg_temperature || 0) > 70 ? 'text-red-600' : 'text-slate-900 dark:text-slate-50'
                        }`}>
                          {line.avg_temperature?.toFixed(1) ?? '-'} °C
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-600 dark:text-slate-400">압력</span>
                        <span className={`font-medium ${
                          (line.avg_pressure || 0) > 8 ? 'text-red-600' : 'text-slate-900 dark:text-slate-50'
                        }`}>
                          {line.avg_pressure?.toFixed(2) ?? '-'} bar
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-600 dark:text-slate-400">습도</span>
                        <span className="font-medium text-slate-900 dark:text-slate-50">
                          {line.avg_humidity?.toFixed(1) ?? '-'} %
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* 고정된 차트 섹션 */}
        <div>
          <div className="flex items-center gap-2 mb-4">
            <LayoutDashboard className="w-5 h-5 text-slate-600 dark:text-slate-400" />
            <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-50">
              고정된 차트
            </h3>
            <span className="text-sm text-slate-500">({savedCharts.length}개)</span>
          </div>

          {savedCharts.length === 0 ? (
            <Card>
              <CardContent className="py-12">
                <div className="text-center text-slate-500">
                  <LayoutDashboard className="w-12 h-12 mx-auto mb-4 opacity-50" />
                  <p className="text-lg font-medium mb-2">고정된 차트가 없습니다</p>
                  <p className="text-sm">
                    AI Chat에서 차트를 생성한 후 "대시보드에 고정" 버튼을 클릭하세요
                  </p>
                </div>
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {savedCharts.map((chart) => (
                <Card key={chart.id}>
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle className="text-base">{chart.title}</CardTitle>
                        <CardDescription className="text-xs">
                          {new Date(chart.savedAt).toLocaleString('ko-KR')}
                        </CardDescription>
                      </div>
                      <button
                        onClick={() => removeChart(chart.id)}
                        className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                        title="차트 삭제"
                      >
                        <X className="w-4 h-4 text-slate-400 hover:text-red-500" />
                      </button>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <ChartRenderer config={chart.config} />
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>

        {/* 최근 센서 데이터 */}
        {recentData.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="w-5 h-5" />
                최근 센서 데이터
              </CardTitle>
              <CardDescription>최근 10건의 센서 측정값</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b dark:border-slate-700">
                      <th className="text-left py-2 px-3 text-slate-600 dark:text-slate-400">시간</th>
                      <th className="text-left py-2 px-3 text-slate-600 dark:text-slate-400">라인</th>
                      <th className="text-left py-2 px-3 text-slate-600 dark:text-slate-400">센서</th>
                      <th className="text-right py-2 px-3 text-slate-600 dark:text-slate-400">값</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentData.map((item) => (
                      <tr key={item.sensor_id} className="border-b dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/50">
                        <td className="py-2 px-3 text-slate-500">
                          {new Date(item.recorded_at).toLocaleTimeString('ko-KR')}
                        </td>
                        <td className="py-2 px-3 font-medium">{item.line_code}</td>
                        <td className="py-2 px-3">{item.sensor_type}</td>
                        <td className="py-2 px-3 text-right font-mono">
                          {item.value.toFixed(2)} {item.unit || ''}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

interface StatCardProps {
  title: string;
  value: string;
  unit: string;
  subtitle: string;
  icon: React.ComponentType<{ className?: string }>;
  iconBgColor: string;
  iconColor: string;
}

function StatCard({ title, value, unit, subtitle, icon: Icon, iconBgColor, iconColor }: StatCardProps) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-slate-600 dark:text-slate-400">{title}</p>
            <div className="flex items-baseline gap-1 mt-1">
              <span className="text-2xl font-bold">{value}</span>
              <span className="text-sm text-slate-500">{unit}</span>
            </div>
            <p className="text-xs text-slate-500 mt-1">{subtitle}</p>
          </div>
          <div className={`p-3 ${iconBgColor} rounded-lg`}>
            <Icon className={`w-6 h-6 ${iconColor}`} />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
