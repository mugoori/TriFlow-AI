/**
 * DashboardPage
 * 고정된 차트들을 표시하는 대시보드 페이지
 */

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { BarChart3, TrendingUp, AlertTriangle, CheckCircle, X, LayoutDashboard } from 'lucide-react';
import { useDashboard } from '@/contexts/DashboardContext';
import { ChartRenderer } from '@/components/charts';

export function DashboardPage() {
  const { savedCharts, removeChart } = useDashboard();

  return (
    <div className="h-full overflow-y-auto">
      <div className="p-6 space-y-6">
        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="생산량"
            value="1,234"
            unit="units"
            change="+12.5%"
            changeType="positive"
            icon={TrendingUp}
          />
          <StatCard
            title="불량률"
            value="2.3"
            unit="%"
            change="-0.5%"
            changeType="positive"
            icon={CheckCircle}
          />
          <StatCard
            title="가동률"
            value="94.2"
            unit="%"
            change="+2.1%"
            changeType="positive"
            icon={BarChart3}
          />
          <StatCard
            title="알림"
            value="3"
            unit="건"
            change="+2"
            changeType="negative"
            icon={AlertTriangle}
          />
        </div>

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

        {/* 기본 차트 플레이스홀더 (고정된 차트가 없을 때 안내용) */}
        {savedCharts.length === 0 && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>생산 추이</CardTitle>
                <CardDescription>최근 7일간 생산량 변화</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-64 flex items-center justify-center bg-slate-100 dark:bg-slate-800 rounded-lg">
                  <p className="text-slate-500 text-center px-4">
                    AI Chat에서 "최근 생산량 차트 보여줘"라고 요청하세요
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>센서 현황</CardTitle>
                <CardDescription>실시간 센서 데이터</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-64 flex items-center justify-center bg-slate-100 dark:bg-slate-800 rounded-lg">
                  <p className="text-slate-500 text-center px-4">
                    AI Chat에서 "센서 데이터 분석해줘"라고 요청하세요
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Recent Activity */}
        <Card>
          <CardHeader>
            <CardTitle>최근 활동</CardTitle>
            <CardDescription>AI 에이전트 처리 내역</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <ActivityItem
                time="2분 전"
                action="BI Agent"
                description="센서 데이터 쿼리 실행 완료"
              />
              <ActivityItem
                time="5분 전"
                action="Workflow Agent"
                description="알림 워크플로우 생성"
              />
              <ActivityItem
                time="12분 전"
                action="Judgment Agent"
                description="온도 임계값 초과 판단"
              />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

interface StatCardProps {
  title: string;
  value: string;
  unit: string;
  change: string;
  changeType: 'positive' | 'negative';
  icon: React.ComponentType<{ className?: string }>;
}

function StatCard({ title, value, unit, change, changeType, icon: Icon }: StatCardProps) {
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
            <p className={`text-sm mt-1 ${
              changeType === 'positive' ? 'text-green-600' : 'text-red-600'
            }`}>
              {change}
            </p>
          </div>
          <div className="p-3 bg-blue-100 dark:bg-blue-900 rounded-lg">
            <Icon className="w-6 h-6 text-blue-600 dark:text-blue-400" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

interface ActivityItemProps {
  time: string;
  action: string;
  description: string;
}

function ActivityItem({ time, action, description }: ActivityItemProps) {
  return (
    <div className="flex items-center gap-4 p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
      <div className="w-2 h-2 rounded-full bg-blue-500"></div>
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm">{action}</span>
          <span className="text-xs text-slate-500">{time}</span>
        </div>
        <p className="text-sm text-slate-600 dark:text-slate-400">{description}</p>
      </div>
    </div>
  );
}
