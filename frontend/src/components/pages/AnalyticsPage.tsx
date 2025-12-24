/**
 * AnalyticsPage
 * 생산 분석 페이지 - OEE, 불량 추이, 생산 실적, 재고 분석
 */

import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  BarChart3, TrendingUp, Target, Package, Loader2, RefreshCw,
  AlertTriangle, Calendar, ChevronDown,
} from 'lucide-react';
import { biService } from '@/services/biService';
import type {
  ProductionResponse,
  DefectTrendResponse,
  OEEResponse,
  InventoryResponse,
  AnalyticsParams,
} from '@/types/bi';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, PieChart, Pie, Cell,
} from 'recharts';

type TabType = 'production' | 'defect' | 'oee' | 'inventory';

const COLORS = ['#8884d8', '#82ca9d', '#ffc658', '#ff7c7c', '#8dd1e1'];

export function AnalyticsPage() {
  const { isAuthenticated } = useAuth();
  const [activeTab, setActiveTab] = useState<TabType>('production');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 필터 상태
  const [dateRange, setDateRange] = useState<'7d' | '30d' | '90d'>('30d');
  const [selectedLine, setSelectedLine] = useState<string>('all');

  // 데이터 상태
  const [productionData, setProductionData] = useState<ProductionResponse | null>(null);
  const [defectData, setDefectData] = useState<DefectTrendResponse | null>(null);
  const [oeeData, setOeeData] = useState<OEEResponse | null>(null);
  const [inventoryData, setInventoryData] = useState<InventoryResponse | null>(null);

  const getParams = (): AnalyticsParams => {
    const now = new Date();
    const startDate = new Date();

    switch (dateRange) {
      case '7d':
        startDate.setDate(now.getDate() - 7);
        break;
      case '30d':
        startDate.setDate(now.getDate() - 30);
        break;
      case '90d':
        startDate.setDate(now.getDate() - 90);
        break;
    }

    return {
      start_date: startDate.toISOString().split('T')[0],
      end_date: now.toISOString().split('T')[0],
      line_code: selectedLine === 'all' ? undefined : selectedLine,
    };
  };

  const fetchData = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const params = getParams();

      switch (activeTab) {
        case 'production':
          setProductionData(await biService.getProductionAnalytics(params));
          break;
        case 'defect':
          setDefectData(await biService.getDefectTrend(params));
          break;
        case 'oee':
          setOeeData(await biService.getOEEAnalytics(params));
          break;
        case 'inventory':
          setInventoryData(await biService.getInventoryAnalytics(params));
          break;
      }
    } catch (err) {
      console.error('Failed to fetch analytics:', err);
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!isAuthenticated) return;
    fetchData();
  }, [isAuthenticated, activeTab, dateRange, selectedLine]);

  const tabs = [
    { id: 'production' as const, label: '생산 실적', icon: BarChart3 },
    { id: 'defect' as const, label: '불량 추이', icon: TrendingUp },
    { id: 'oee' as const, label: 'OEE', icon: Target },
    { id: 'inventory' as const, label: '재고', icon: Package },
  ];

  return (
    <div className="h-full overflow-y-auto">
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-50">분석</h2>
            <p className="text-sm text-slate-500">생산 현황 및 품질 분석</p>
          </div>
          <button
            onClick={fetchData}
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

        {/* Tab Navigation */}
        <div className="flex gap-2 border-b dark:border-slate-700">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-3 border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Filters */}
        <div className="flex gap-4">
          <div className="relative">
            <select
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value as '7d' | '30d' | '90d')}
              className="appearance-none pl-10 pr-8 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="7d">최근 7일</option>
              <option value="30d">최근 30일</option>
              <option value="90d">최근 90일</option>
            </select>
            <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          </div>
          <div className="relative">
            <select
              value={selectedLine}
              onChange={(e) => setSelectedLine(e.target.value)}
              className="appearance-none pl-4 pr-8 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">전체 라인</option>
              <option value="LINE_A">LINE_A</option>
              <option value="LINE_B">LINE_B</option>
              <option value="LINE_C">LINE_C</option>
              <option value="LINE_D">LINE_D</option>
            </select>
            <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          </div>
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

        {/* Content */}
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
          </div>
        ) : (
          <>
            {activeTab === 'production' && productionData && (
              <ProductionTab data={productionData} />
            )}
            {activeTab === 'defect' && defectData && (
              <DefectTab data={defectData} />
            )}
            {activeTab === 'oee' && oeeData && (
              <OEETab data={oeeData} />
            )}
            {activeTab === 'inventory' && inventoryData && (
              <InventoryTab data={inventoryData} />
            )}
          </>
        )}
      </div>
    </div>
  );
}

// Production Tab Component
function ProductionTab({ data }: { data: ProductionResponse }) {
  // 일별 데이터 집계
  const dailyData = data.data.reduce((acc, item) => {
    const existing = acc.find(d => d.date === item.date);
    if (existing) {
      existing.production += item.total_qty;
      existing.defects += item.defect_qty;
    } else {
      acc.push({ date: item.date, production: item.total_qty, defects: item.defect_qty });
    }
    return acc;
  }, [] as Array<{ date: string; production: number; defects: number }>);

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <SummaryCard
          title="총 생산량"
          value={data.summary.total_production.toLocaleString()}
          unit="개"
          icon={BarChart3}
          color="blue"
        />
        <SummaryCard
          title="총 불량"
          value={data.summary.total_defects.toLocaleString()}
          unit="개"
          icon={AlertTriangle}
          color={data.summary.total_defects > 0 ? 'red' : 'green'}
        />
        <SummaryCard
          title="평균 양품률"
          value={data.summary.avg_yield_rate.toFixed(1)}
          unit="%"
          icon={TrendingUp}
          color={data.summary.avg_yield_rate >= 95 ? 'green' : 'red'}
        />
        <SummaryCard
          title="평균 가동률"
          value={data.summary.avg_availability.toFixed(1)}
          unit="%"
          icon={Target}
          color={data.summary.avg_availability >= 80 ? 'green' : 'yellow'}
        />
      </div>

      {/* Production Chart */}
      <Card>
        <CardHeader>
          <CardTitle>일별 생산 현황</CardTitle>
          <CardDescription>일자별 생산량 및 불량 추이</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={dailyData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="production" name="생산량" fill="#8884d8" />
                <Bar dataKey="defects" name="불량" fill="#ff7c7c" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// Defect Tab Component
function DefectTab({ data }: { data: DefectTrendResponse }) {
  // 일별 불량률 추이 데이터
  const trendData = data.data.reduce((acc, item) => {
    const existing = acc.find(d => d.date === item.date);
    if (existing) {
      existing.total_qty += item.total_qty;
      existing.defect_qty += item.defect_qty;
      existing.defect_rate = (existing.defect_qty / existing.total_qty) * 100;
    } else {
      acc.push({
        date: item.date,
        total_qty: item.total_qty,
        defect_qty: item.defect_qty,
        defect_rate: item.defect_rate,
      });
    }
    return acc;
  }, [] as Array<{ date: string; total_qty: number; defect_qty: number; defect_rate: number }>);

  // 불량 유형별 집계
  const defectByType = data.data.reduce((acc, item) => {
    if (item.top_defect_types) {
      item.top_defect_types.forEach(dt => {
        const existing = acc.find(d => d.type === dt.type);
        if (existing) {
          existing.qty += dt.qty;
        } else {
          acc.push({ type: dt.type, qty: dt.qty });
        }
      });
    }
    return acc;
  }, [] as Array<{ type: string; qty: number }>);

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <SummaryCard
          title="평균 불량률"
          value={data.avg_defect_rate.toFixed(2)}
          unit="%"
          icon={TrendingUp}
          color={data.avg_defect_rate < 2 ? 'green' : data.avg_defect_rate < 5 ? 'yellow' : 'red'}
        />
        <SummaryCard
          title="총 데이터"
          value={data.total.toString()}
          unit="건"
          icon={BarChart3}
          color="blue"
        />
        <SummaryCard
          title="불량 유형"
          value={defectByType.length.toString()}
          unit="종류"
          icon={AlertTriangle}
          color="yellow"
        />
      </div>

      {/* Trend Chart */}
      <Card>
        <CardHeader>
          <CardTitle>불량률 추이</CardTitle>
          <CardDescription>일자별 불량률 변화</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis domain={[0, 'auto']} />
                <Tooltip formatter={(value: number) => `${value.toFixed(2)}%`} />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="defect_rate"
                  name="불량률"
                  stroke="#ff7c7c"
                  strokeWidth={2}
                  dot={{ fill: '#ff7c7c' }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Defect by Type */}
      {defectByType.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>불량 유형별 분포</CardTitle>
            <CardDescription>유형별 불량 건수</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={defectByType}
                    dataKey="qty"
                    nameKey="type"
                    cx="50%"
                    cy="50%"
                    outerRadius={100}
                    label={({ name, percent }) => `${name} (${((percent || 0) * 100).toFixed(1)}%)`}
                  >
                    {defectByType.map((_, index: number) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// OEE Tab Component
function OEETab({ data }: { data: OEEResponse }) {
  // 라인별 데이터 집계
  const byLineData = data.data.reduce((acc, item) => {
    const existing = acc.find(d => d.line_code === item.line_code);
    if (existing) {
      existing.count += 1;
      existing.availability = (existing.availability * (existing.count - 1) + item.availability) / existing.count;
      existing.performance = (existing.performance * (existing.count - 1) + item.performance) / existing.count;
      existing.quality = (existing.quality * (existing.count - 1) + item.quality) / existing.count;
      existing.oee = (existing.oee * (existing.count - 1) + item.oee) / existing.count;
    } else {
      acc.push({
        line_code: item.line_code,
        availability: item.availability,
        performance: item.performance,
        quality: item.quality,
        oee: item.oee,
        count: 1,
      });
    }
    return acc;
  }, [] as Array<{ line_code: string; availability: number; performance: number; quality: number; oee: number; count: number }>);

  // 일별 추이 데이터
  const trendData = data.data.reduce((acc, item) => {
    const existing = acc.find(d => d.date === item.date);
    if (existing) {
      existing.count += 1;
      existing.availability = (existing.availability * (existing.count - 1) + item.availability) / existing.count;
      existing.performance = (existing.performance * (existing.count - 1) + item.performance) / existing.count;
      existing.quality = (existing.quality * (existing.count - 1) + item.quality) / existing.count;
      existing.oee = (existing.oee * (existing.count - 1) + item.oee) / existing.count;
    } else {
      acc.push({
        date: item.date,
        availability: item.availability,
        performance: item.performance,
        quality: item.quality,
        oee: item.oee,
        count: 1,
      });
    }
    return acc;
  }, [] as Array<{ date: string; availability: number; performance: number; quality: number; oee: number; count: number }>);

  return (
    <div className="space-y-6">
      {/* OEE Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <SummaryCard
          title="평균 OEE"
          value={data.avg_oee.toFixed(1)}
          unit="%"
          icon={Target}
          color={data.avg_oee >= 85 ? 'green' : data.avg_oee >= 60 ? 'yellow' : 'red'}
        />
        <SummaryCard
          title="평균 가용성"
          value={data.avg_availability.toFixed(1)}
          unit="%"
          icon={Target}
          color={data.avg_availability >= 90 ? 'green' : 'yellow'}
        />
        <SummaryCard
          title="평균 성능"
          value={data.avg_performance.toFixed(1)}
          unit="%"
          icon={Target}
          color={data.avg_performance >= 95 ? 'green' : 'yellow'}
        />
        <SummaryCard
          title="평균 품질"
          value={data.avg_quality.toFixed(1)}
          unit="%"
          icon={Target}
          color={data.avg_quality >= 99 ? 'green' : 'yellow'}
        />
      </div>

      {/* OEE by Line Chart */}
      <Card>
        <CardHeader>
          <CardTitle>라인별 OEE</CardTitle>
          <CardDescription>생산 라인별 OEE 비교</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={byLineData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" domain={[0, 100]} />
                <YAxis dataKey="line_code" type="category" width={80} />
                <Tooltip formatter={(value: number) => `${value.toFixed(1)}%`} />
                <Legend />
                <Bar dataKey="oee" name="OEE" fill="#8884d8" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* OEE Trend */}
      <Card>
        <CardHeader>
          <CardTitle>OEE 추이</CardTitle>
          <CardDescription>일자별 OEE 변화</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis domain={[0, 100]} />
                <Tooltip formatter={(value: number) => `${value.toFixed(1)}%`} />
                <Legend />
                <Line type="monotone" dataKey="oee" name="OEE" stroke="#8884d8" strokeWidth={2} />
                <Line type="monotone" dataKey="availability" name="가용성" stroke="#82ca9d" strokeWidth={1} strokeDasharray="5 5" />
                <Line type="monotone" dataKey="performance" name="성능" stroke="#ffc658" strokeWidth={1} strokeDasharray="5 5" />
                <Line type="monotone" dataKey="quality" name="품질" stroke="#ff7c7c" strokeWidth={1} strokeDasharray="5 5" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// Inventory Tab Component
function InventoryTab({ data }: { data: InventoryResponse }) {
  // 총 재고량 계산
  const totalQuantity = data.data.reduce((sum, item) => sum + item.stock_qty, 0);

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <SummaryCard
          title="총 재고량"
          value={totalQuantity.toLocaleString()}
          unit="개"
          icon={Package}
          color="blue"
        />
        <SummaryCard
          title="재고 금액"
          value={(data.summary.total_stock_value / 1000000).toFixed(1)}
          unit="백만원"
          icon={Package}
          color="green"
        />
        <SummaryCard
          title="부족 품목"
          value={data.summary.low_stock_items.toString()}
          unit="건"
          icon={AlertTriangle}
          color={data.summary.low_stock_items > 0 ? 'red' : 'green'}
        />
        <SummaryCard
          title="긴급 품목"
          value={data.summary.critical_items.toString()}
          unit="건"
          icon={AlertTriangle}
          color={data.summary.critical_items > 0 ? 'red' : 'green'}
        />
      </div>

      {/* Inventory Table */}
      <Card>
        <CardHeader>
          <CardTitle>품목별 재고 현황</CardTitle>
          <CardDescription>주요 품목 재고 상태 (총 {data.total}건)</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b dark:border-slate-700">
                  <th className="text-left py-3 px-4 text-slate-600 dark:text-slate-400">품목코드</th>
                  <th className="text-left py-3 px-4 text-slate-600 dark:text-slate-400">품목명</th>
                  <th className="text-right py-3 px-4 text-slate-600 dark:text-slate-400">현재고</th>
                  <th className="text-right py-3 px-4 text-slate-600 dark:text-slate-400">안전재고</th>
                  <th className="text-right py-3 px-4 text-slate-600 dark:text-slate-400">상태</th>
                </tr>
              </thead>
              <tbody>
                {data.data.map((item, index) => (
                  <tr key={`${item.product_code}-${index}`} className="border-b dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/50">
                    <td className="py-3 px-4 font-mono">{item.product_code}</td>
                    <td className="py-3 px-4">{item.product_name || '-'}</td>
                    <td className="py-3 px-4 text-right">{item.stock_qty.toLocaleString()}</td>
                    <td className="py-3 px-4 text-right">{item.safety_stock_qty.toLocaleString()}</td>
                    <td className="py-3 px-4 text-right">
                      <span
                        className={`px-2 py-1 rounded-full text-xs font-medium ${
                          item.stock_status === 'normal'
                            ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                            : item.stock_status === 'low'
                            ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
                            : item.stock_status === 'critical'
                            ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                            : 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                        }`}
                      >
                        {item.stock_status === 'normal' ? '정상' : item.stock_status === 'low' ? '부족' : item.stock_status === 'critical' ? '긴급' : '과잉'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// Summary Card Component
interface SummaryCardProps {
  title: string;
  value: string;
  unit: string;
  icon: React.ComponentType<{ className?: string }>;
  color: 'blue' | 'green' | 'yellow' | 'red';
}

function SummaryCard({ title, value, unit, icon: Icon, color }: SummaryCardProps) {
  const colorClasses = {
    blue: 'bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-400',
    green: 'bg-green-100 dark:bg-green-900 text-green-600 dark:text-green-400',
    yellow: 'bg-yellow-100 dark:bg-yellow-900 text-yellow-600 dark:text-yellow-400',
    red: 'bg-red-100 dark:bg-red-900 text-red-600 dark:text-red-400',
  };

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
          </div>
          <div className={`p-3 rounded-lg ${colorClasses[color]}`}>
            <Icon className="w-6 h-6" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
