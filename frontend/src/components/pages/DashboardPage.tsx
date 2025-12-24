/**
 * DashboardPage
 * AWS QuickSight GenBI 동일 기능 통합 대시보드 페이지
 *
 * 3대 핵심 기능:
 * 1. AI Dashboard Authoring (차트 생성 + Refinement Loop)
 * 2. Executive Summary (Fact/Reasoning/Action 인사이트)
 * 3. Data Stories (내러티브 보고서)
 */

import { useEffect, useState, useRef } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  BarChart3, TrendingUp, AlertTriangle, X, LayoutDashboard, RefreshCw,
  Thermometer, Gauge, Droplets, Activity, Loader2, Sparkles, BookOpen,
  ChevronDown, ChevronUp, MessageSquare, Save, FolderOpen, Trash2, Check,
  MoreVertical, Edit2,
} from 'lucide-react';
import { useDashboard } from '@/contexts/DashboardContext';
import { useAuth } from '@/contexts/AuthContext';
import { ChartRenderer } from '@/components/charts';
import { InsightPanel, StoryList, StoryViewer, BIChatPanel, DynamicStatCard, AddStatCardButton, StatCardSkeleton, StatCardConfigModal } from '@/components/bi';
import { useToast } from '@/components/ui/Toast';
import { useStatCards } from '@/contexts/StatCardContext';
import { sensorService, SensorSummaryItem, SensorDataItem } from '@/services/sensorService';
import { biService } from '@/services/biService';
import type { DataStory, AIInsight, Dashboard, DashboardLayoutComponent, PinnedInsight } from '@/types/bi';
import type { ChartConfig } from '@/types/chart';

interface DashboardStats {
  totalReadings: number;
  avgTemperature: number;
  avgPressure: number;
  avgHumidity: number;
  activeLines: number;
  alerts: number;
}

export function DashboardPage() {
  const { isAuthenticated } = useAuth();
  const { savedCharts, removeChart, loadCharts, clearCharts } = useDashboard();
  const { cards, loading: statCardsLoading, deleteCard, refreshValues } = useStatCards();
  const toast = useToast();
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

  // GenBI 상태
  const [showInsightPanel, setShowInsightPanel] = useState(false);
  const [showStoryPanel, setShowStoryPanel] = useState(false);
  const [showChatPanel, setShowChatPanel] = useState(false);
  const [selectedStory, setSelectedStory] = useState<DataStory | null>(null);
  const [insightPanelCollapsed, setInsightPanelCollapsed] = useState(false);
  const [pinnedInsights, setPinnedInsights] = useState<PinnedInsight[]>([]);
  const [pinnedInsightIds, setPinnedInsightIds] = useState<string[]>([]);

  // 대시보드 저장/로드 상태
  const [dashboards, setDashboards] = useState<Dashboard[]>([]);
  const [selectedDashboardId, setSelectedDashboardId] = useState<string | null>(null);
  const [showDashboardMenu, setShowDashboardMenu] = useState(false);
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [newDashboardName, setNewDashboardName] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  // StatCard 모달 상태
  const [showStatCardModal, setShowStatCardModal] = useState(false);
  const [editingStatCardId, setEditingStatCardId] = useState<string | null>(null);

  // 기본 카드 숨김 상태
  const [hiddenDefaultCards, setHiddenDefaultCards] = useState<string[]>([]);

  // 중복 요청 방지용 ref
  const isInitializedRef = useRef(false);
  const fetchingRef = useRef(false);

  // StatCard 편집 핸들러
  const handleEditStatCard = (configId: string) => {
    setEditingStatCardId(configId);
    setShowStatCardModal(true);
  };

  // StatCard 삭제 핸들러
  const handleDeleteStatCard = async (configId: string) => {
    const confirmed = await toast.confirm({
      title: '카드 삭제',
      message: '이 카드를 삭제하시겠습니까?',
      confirmText: '삭제',
      cancelText: '취소',
      variant: 'danger',
    });
    if (confirmed) {
      try {
        await deleteCard(configId);
        toast.success('카드가 삭제되었습니다.');
      } catch (err) {
        console.error('Failed to delete stat card:', err);
        toast.error('카드 삭제에 실패했습니다.');
      }
    }
  };

  // 기본 카드 편집 핸들러 (모달 열기)
  const handleEditDefaultCard = (cardId: string) => {
    // 기본 카드 편집 시 새 카드 생성 모달을 열어 같은 타입의 카드를 만들 수 있게 함
    setEditingStatCardId(null);
    setShowStatCardModal(true);
  };

  // 기본 카드 삭제 핸들러
  const handleDeleteDefaultCard = async (cardId: string) => {
    const confirmed = await toast.confirm({
      title: '카드 숨기기',
      message: '이 기본 카드를 숨기시겠습니까? 새 카드를 추가하여 대체할 수 있습니다.',
      confirmText: '숨기기',
      cancelText: '취소',
      variant: 'warning',
    });
    if (confirmed) {
      setHiddenDefaultCards(prev => [...prev, cardId]);
      toast.success('카드가 숨겨졌습니다.');
    }
  };

  // 편집 중인 StatCard 설정 찾기
  const editingStatCardConfig = editingStatCardId
    ? cards.find((c) => c.config.config_id === editingStatCardId)?.config
    : undefined;

  const fetchDashboardData = async () => {
    // 이미 요청 중이면 중복 요청 방지
    if (fetchingRef.current) return;
    fetchingRef.current = true;

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
      fetchingRef.current = false;
    }
  };

  // 핀된 인사이트 로드
  const loadPinnedInsights = async () => {
    try {
      console.log('[DashboardPage] Loading pinned insights...');
      const response = await biService.getPinnedInsights();
      console.log('[DashboardPage] Pinned insights loaded:', response.pinned_insights.length);
      setPinnedInsights(response.pinned_insights);
      setPinnedInsightIds(response.pinned_insights.map(p => p.insight_id));
    } catch (err) {
      console.error('Failed to load pinned insights:', err);
    }
  };

  // 인사이트 Pin (API 호출은 BIChatPanel/InsightPanel에서 수행, 여기서는 목록 갱신)
  const handlePinInsight = (insightId: string) => {
    console.log('[DashboardPage] handlePinInsight - refreshing pinned insights:', insightId);
    // 목록 갱신 (API에서 최신 데이터 가져오기)
    loadPinnedInsights();
  };

  // 인사이트 Unpin (API 호출은 BIChatPanel/InsightPanel에서 수행, 여기서는 목록 갱신)
  const handleUnpinInsight = (insightId: string) => {
    console.log('[DashboardPage] handleUnpinInsight - refreshing pinned insights:', insightId);
    // 즉시 UI에서 제거
    setPinnedInsights(prev => prev.filter(p => p.insight_id !== insightId));
    setPinnedInsightIds(prev => prev.filter(id => id !== insightId));
  };

  // 채팅에서 인사이트 생성 시 콜백
  const handleInsightGenerated = (insight: AIInsight) => {
    // 인사이트가 생성되면 인사이트 패널을 열 수 있음
    console.log('New insight generated:', insight.title);
  };

  // 대시보드 목록 로드
  const loadDashboards = async () => {
    try {
      const response = await biService.getDashboards();
      // API가 배열을 직접 반환하거나 { dashboards: [] } 형태로 반환할 수 있음
      const dashboardList = Array.isArray(response) ? response : (response.dashboards || []);
      setDashboards(dashboardList);
    } catch (err) {
      console.error('Failed to load dashboards:', err);
      setDashboards([]); // 오류 시 빈 배열로 설정
    }
  };

  // 대시보드 저장
  const handleSaveDashboard = async () => {
    if (!newDashboardName.trim()) return;

    setIsSaving(true);
    try {
      // 현재 고정된 차트들을 layout components로 변환
      const components: DashboardLayoutComponent[] = savedCharts.map((chart, index) => ({
        id: chart.id,
        type: 'chart' as const,
        position: {
          x: (index % 2) * 6,
          y: Math.floor(index / 2) * 4,
          w: 6,
          h: 4,
        },
        config: {
          chartConfig: chart.config,
          title: chart.title,
          savedAt: chart.savedAt,
        },
      }));

      const dashboard = await biService.createDashboard({
        name: newDashboardName,
        description: `${savedCharts.length}개 차트 포함`,
        layout: { components },
        is_public: false,
      });

      setDashboards(prev => [...prev, dashboard]);
      setSelectedDashboardId(dashboard.id);
      setShowSaveModal(false);
      setNewDashboardName('');
    } catch (err) {
      console.error('Failed to save dashboard:', err);
      setError('대시보드 저장에 실패했습니다');
    } finally {
      setIsSaving(false);
    }
  };

  // 대시보드 로드
  const handleLoadDashboard = async (dashboardId: string) => {
    try {
      const dashboard = await biService.getDashboard(dashboardId);
      setSelectedDashboardId(dashboardId);

      // 기존 차트 제거
      clearCharts();

      // layout에서 차트 복원
      if (dashboard.layout?.components) {
        const charts = dashboard.layout.components
          .filter(comp => comp.type === 'chart' && comp.config?.chartConfig)
          .map(comp => ({
            id: comp.id,
            title: (comp.config?.title as string) || 'Untitled',
            config: comp.config?.chartConfig as ChartConfig,
            savedAt: new Date((comp.config?.savedAt as string) || new Date().toISOString()),
          }));
        loadCharts(charts);
      }

      setShowDashboardMenu(false);
    } catch (err) {
      console.error('Failed to load dashboard:', err);
      setError('대시보드 로드에 실패했습니다');
    }
  };

  // 대시보드 삭제
  const handleDeleteDashboard = async (dashboardId: string) => {
    try {
      await biService.deleteDashboard(dashboardId);
      setDashboards(prev => prev.filter(d => d.id !== dashboardId));
      if (selectedDashboardId === dashboardId) {
        setSelectedDashboardId(null);
      }
    } catch (err) {
      console.error('Failed to delete dashboard:', err);
      setError('대시보드 삭제에 실패했습니다');
    }
  };

  useEffect(() => {
    // 인증 완료 후에만 API 호출
    if (!isAuthenticated) return;

    // React Strict Mode 중복 실행 방지
    if (isInitializedRef.current) return;
    isInitializedRef.current = true;

    fetchDashboardData();
    loadPinnedInsights();
    loadDashboards();
    // 30초마다 자동 갱신
    const interval = setInterval(fetchDashboardData, 30000);
    return () => {
      clearInterval(interval);
      // cleanup 시에는 다시 초기화 허용하지 않음 (언마운트 후 재마운트 시에만)
    };
  }, [isAuthenticated]);

  return (
    <div className="h-full overflow-y-auto">
      <div className="p-6 space-y-6">
        {/* Header with GenBI buttons */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div>
              <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-50">Dashboard</h2>
              {lastUpdated && (
                <p className="text-sm text-slate-500">
                  마지막 업데이트: {lastUpdated.toLocaleTimeString('ko-KR')}
                </p>
              )}
            </div>
            {/* 대시보드 선택 드롭다운 */}
            <div className="relative">
              <button
                onClick={() => setShowDashboardMenu(!showDashboardMenu)}
                className="flex items-center gap-2 px-3 py-2 bg-slate-600 text-white rounded-lg hover:bg-slate-700 dark:bg-slate-500 dark:hover:bg-slate-600 transition-colors shadow-sm"
              >
                <FolderOpen className="w-4 h-4" />
                <span className="text-sm font-medium">
                  {selectedDashboardId
                    ? dashboards.find(d => d.id === selectedDashboardId)?.name || '대시보드'
                    : '대시보드 선택'}
                </span>
                <ChevronDown className="w-4 h-4" />
              </button>
              {showDashboardMenu && (
                <div className="absolute top-full left-0 mt-1 w-64 bg-white dark:bg-slate-800 rounded-lg shadow-lg border dark:border-slate-700 z-50">
                  <div className="p-2">
                    {dashboards.length === 0 ? (
                      <p className="text-sm text-slate-500 px-3 py-2">저장된 대시보드가 없습니다</p>
                    ) : (
                      dashboards.map(dashboard => (
                        <div
                          key={dashboard.id}
                          className="flex items-center justify-between px-3 py-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-md group"
                        >
                          <button
                            onClick={() => handleLoadDashboard(dashboard.id)}
                            className="flex-1 text-left text-sm"
                          >
                            <span className="font-medium">{dashboard.name}</span>
                            {selectedDashboardId === dashboard.id && (
                              <Check className="w-4 h-4 inline ml-2 text-green-500" />
                            )}
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteDashboard(dashboard.id);
                            }}
                            className="p-1 opacity-0 group-hover:opacity-100 hover:bg-red-100 dark:hover:bg-red-900/30 rounded"
                          >
                            <Trash2 className="w-4 h-4 text-red-500" />
                          </button>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>
            {/* 저장 버튼 */}
            <button
              onClick={() => setShowSaveModal(true)}
              disabled={savedCharts.length === 0}
              className="flex items-center gap-2 px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Save className="w-4 h-4" />
              저장
            </button>
          </div>
          <div className="flex items-center gap-2">
            {/* AI 채팅 버튼 */}
            <button
              onClick={() => setShowChatPanel(!showChatPanel)}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-colors ${
                showChatPanel
                  ? 'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-green-50 dark:hover:bg-green-900/30'
              }`}
            >
              <MessageSquare className="w-4 h-4" />
              AI 채팅
            </button>
            {/* AI 인사이트 토글 버튼 */}
            <button
              onClick={() => setShowInsightPanel(!showInsightPanel)}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-colors ${
                showInsightPanel
                  ? 'bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-purple-50 dark:hover:bg-purple-900/30'
              }`}
            >
              <Sparkles className="w-4 h-4" />
              AI 인사이트
            </button>
            {/* 스토리 버튼 */}
            <button
              onClick={() => setShowStoryPanel(!showStoryPanel)}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-colors ${
                showStoryPanel
                  ? 'bg-indigo-100 dark:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-indigo-50 dark:hover:bg-indigo-900/30'
              }`}
            >
              <BookOpen className="w-4 h-4" />
              스토리
            </button>
            {/* 새로고침 버튼 */}
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

        {/* AI Executive Summary Section (GenBI) */}
        {showInsightPanel && (
          <Card className="border-purple-200 dark:border-purple-800">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2 text-purple-700 dark:text-purple-300">
                  <Sparkles className="w-5 h-5" />
                  AI Executive Summary
                </CardTitle>
                <button
                  onClick={() => setInsightPanelCollapsed(!insightPanelCollapsed)}
                  className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  {insightPanelCollapsed ? (
                    <ChevronDown className="w-5 h-5" />
                  ) : (
                    <ChevronUp className="w-5 h-5" />
                  )}
                </button>
              </div>
            </CardHeader>
            {!insightPanelCollapsed && (
              <CardContent>
                <InsightPanel
                  sourceType="dashboard"
                  pinnedInsightIds={pinnedInsightIds}
                  onPinInsight={handlePinInsight}
                  onUnpinInsight={handleUnpinInsight}
                />
              </CardContent>
            )}
          </Card>
        )}

        {/* Dynamic Stats Grid - DB 기반 동적 StatCard */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {statCardsLoading ? (
            // 로딩 중 스켈레톤
            <>
              <StatCardSkeleton />
              <StatCardSkeleton />
              <StatCardSkeleton />
              <StatCardSkeleton />
            </>
          ) : cards.length > 0 ? (
            // DB에서 설정된 동적 카드
            <>
              {cards.map((card) => (
                <DynamicStatCard
                  key={card.config.config_id}
                  card={card}
                  onEdit={handleEditStatCard}
                  onDelete={handleDeleteStatCard}
                  onRefresh={() => refreshValues()}
                  showActions={true}
                />
              ))}
              {/* 카드 추가 버튼 (6개 미만일 때만) */}
              {cards.length < 6 && (
                <AddStatCardButton onClick={() => {
                  setEditingStatCardId(null);
                  setShowStatCardModal(true);
                }} />
              )}
            </>
          ) : (
            // 카드가 없을 때 - 기본 센서 통계 표시 + 카드 추가 유도
            <>
              {!hiddenDefaultCards.includes('temp') && (
                <LegacyStatCard
                  cardId="temp"
                  title="평균 온도"
                  value={isLoading ? '-' : stats.avgTemperature.toFixed(1)}
                  unit="°C"
                  subtitle={`${stats.activeLines}개 라인`}
                  icon={Thermometer}
                  iconBgColor="bg-orange-100 dark:bg-orange-900"
                  iconColor="text-orange-600 dark:text-orange-400"
                  onEdit={handleEditDefaultCard}
                  onDelete={handleDeleteDefaultCard}
                />
              )}
              {!hiddenDefaultCards.includes('pressure') && (
                <LegacyStatCard
                  cardId="pressure"
                  title="평균 압력"
                  value={isLoading ? '-' : stats.avgPressure.toFixed(2)}
                  unit="bar"
                  subtitle="최근 24시간"
                  icon={Gauge}
                  iconBgColor="bg-blue-100 dark:bg-blue-900"
                  iconColor="text-blue-600 dark:text-blue-400"
                  onEdit={handleEditDefaultCard}
                  onDelete={handleDeleteDefaultCard}
                />
              )}
              {!hiddenDefaultCards.includes('humidity') && (
                <LegacyStatCard
                  cardId="humidity"
                  title="평균 습도"
                  value={isLoading ? '-' : stats.avgHumidity.toFixed(1)}
                  unit="%"
                  subtitle="최근 24시간"
                  icon={Droplets}
                  iconBgColor="bg-cyan-100 dark:bg-cyan-900"
                  iconColor="text-cyan-600 dark:text-cyan-400"
                  onEdit={handleEditDefaultCard}
                  onDelete={handleDeleteDefaultCard}
                />
              )}
              <AddStatCardButton onClick={() => {
                setEditingStatCardId(null);
                setShowStatCardModal(true);
              }} />
            </>
          )}
        </div>

        {/* StatCard 설정 모달 */}
        <StatCardConfigModal
          isOpen={showStatCardModal}
          onClose={() => {
            setShowStatCardModal(false);
            setEditingStatCardId(null);
          }}
          editConfig={editingStatCardConfig}
        />

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

        {/* 고정된 인사이트 섹션 (AI Chat에서 Pin한 인사이트) */}
        {pinnedInsights.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-4">
              <Sparkles className="w-5 h-5 text-purple-600 dark:text-purple-400" />
              <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-50">
                고정된 인사이트
              </h3>
              <span className="text-sm text-slate-500">({pinnedInsights.length}개)</span>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {pinnedInsights.map((pinned) => (
                <Card key={pinned.pin_id} className="border-purple-200 dark:border-purple-800">
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <CardTitle className="text-base flex items-center gap-2">
                          <Sparkles className="w-4 h-4 text-purple-500" />
                          {pinned.insight.title}
                        </CardTitle>
                        <CardDescription className="text-xs mt-1">
                          {new Date(pinned.insight.generated_at).toLocaleString('ko-KR')}
                        </CardDescription>
                      </div>
                      <button
                        onClick={async () => {
                          try {
                            await biService.unpinInsight(pinned.insight_id);
                            handleUnpinInsight(pinned.insight_id);
                          } catch (err) {
                            console.error('Failed to unpin insight:', err);
                          }
                        }}
                        className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                        title="인사이트 고정 해제"
                      >
                        <X className="w-4 h-4 text-slate-400 hover:text-red-500" />
                      </button>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-slate-600 dark:text-slate-400 mb-3">
                      {pinned.insight.summary}
                    </p>
                    {/* Facts */}
                    {pinned.insight.facts && pinned.insight.facts.length > 0 && (
                      <div className="space-y-2">
                        <p className="text-xs font-medium text-slate-500 uppercase">주요 지표</p>
                        <div className="flex flex-wrap gap-2">
                          {pinned.insight.facts.slice(0, 3).map((fact, idx) => (
                            <div
                              key={idx}
                              className="px-2 py-1 bg-slate-100 dark:bg-slate-800 rounded text-xs"
                            >
                              <span className="text-slate-500">{fact.metric_name}: </span>
                              <span className="font-medium">{fact.current_value}</span>
                              {fact.change_percent !== undefined && (
                                <span className={`ml-1 ${fact.change_percent >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                  ({fact.change_percent >= 0 ? '+' : ''}{fact.change_percent}%)
                                </span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {/* Actions */}
                    {pinned.insight.actions && pinned.insight.actions.length > 0 && (
                      <div className="mt-3 pt-3 border-t dark:border-slate-700">
                        <p className="text-xs font-medium text-slate-500 uppercase mb-2">권장 조치</p>
                        <ul className="text-xs text-slate-600 dark:text-slate-400 space-y-1">
                          {pinned.insight.actions.slice(0, 2).map((action, idx) => (
                            <li key={idx} className="flex items-start gap-2">
                              <span className={`inline-block px-1 rounded text-white text-[10px] ${
                                action.priority === 'high' ? 'bg-red-500' :
                                action.priority === 'medium' ? 'bg-yellow-500' : 'bg-green-500'
                              }`}>
                                {action.priority === 'high' ? '긴급' : action.priority === 'medium' ? '권장' : '참고'}
                              </span>
                              <span>{action.action}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
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

      {/* Chat Panel (Slide-in from right) */}
      {showChatPanel && (
        <div className="fixed inset-0 z-50 flex">
          {/* Backdrop */}
          <div
            className="flex-1 bg-black/50"
            onClick={() => setShowChatPanel(false)}
          />
          {/* Panel */}
          <div className="w-full max-w-xl bg-white dark:bg-slate-900 shadow-xl overflow-hidden flex flex-col">
            <BIChatPanel
              contextType="dashboard"
              onInsightGenerated={handleInsightGenerated}
              onPinInsight={handlePinInsight}
              onUnpinInsight={handleUnpinInsight}
              onCardAction={(action, kpiCode, success) => {
                if (success) {
                  // 카드 추가/삭제 성공 시 StatCard 목록 새로고침
                  refreshValues();
                  toast.success(
                    action === 'add' ? '카드가 추가되었습니다' : '카드가 삭제되었습니다',
                    { duration: 2000 }
                  );
                }
              }}
            />
          </div>
        </div>
      )}

      {/* Story Panel (Slide-in from right) */}
      {showStoryPanel && (
        <div className="fixed inset-0 z-50 flex">
          {/* Backdrop */}
          <div
            className="flex-1 bg-black/50"
            onClick={() => {
              setShowStoryPanel(false);
              setSelectedStory(null);
            }}
          />
          {/* Panel */}
          <div className="w-full max-w-2xl bg-white dark:bg-slate-900 shadow-xl overflow-hidden flex flex-col">
            {selectedStory ? (
              <StoryViewer
                story={selectedStory}
                onClose={() => setSelectedStory(null)}
              />
            ) : (
              <div className="flex-1 overflow-y-auto p-6">
                <StoryList
                  onSelectStory={(story) => setSelectedStory(story)}
                />
              </div>
            )}
          </div>
        </div>
      )}

      {/* Save Dashboard Modal */}
      {showSaveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setShowSaveModal(false)}
          />
          {/* Modal */}
          <div className="relative w-full max-w-md bg-white dark:bg-slate-800 rounded-lg shadow-xl p-6">
            <h3 className="text-lg font-semibold mb-4">대시보드 저장</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  대시보드 이름
                </label>
                <input
                  type="text"
                  value={newDashboardName}
                  onChange={(e) => setNewDashboardName(e.target.value)}
                  placeholder="예: 생산라인 모니터링"
                  className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  autoFocus
                />
              </div>
              <p className="text-sm text-slate-500">
                {savedCharts.length}개의 차트가 저장됩니다
              </p>
              <div className="flex justify-end gap-2">
                <button
                  onClick={() => {
                    setShowSaveModal(false);
                    setNewDashboardName('');
                  }}
                  className="px-4 py-2 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
                >
                  취소
                </button>
                <button
                  onClick={handleSaveDashboard}
                  disabled={!newDashboardName.trim() || isSaving}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {isSaving ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Save className="w-4 h-4" />
                  )}
                  저장
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * LegacyStatCard - 기본 센서 통계용 (DB 카드가 없을 때 폴백)
 */
interface LegacyStatCardProps {
  title: string;
  value: string;
  unit: string;
  subtitle: string;
  icon: React.ComponentType<{ className?: string }>;
  iconBgColor: string;
  iconColor: string;
  cardId: string;
  onEdit?: (cardId: string) => void;
  onDelete?: (cardId: string) => void;
}

function LegacyStatCard({ title, value, unit, subtitle, icon: Icon, iconBgColor, iconColor, cardId, onEdit, onDelete }: LegacyStatCardProps) {
  const [showMenu, setShowMenu] = useState(false);

  return (
    <Card className="relative group">
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

        {/* 액션 메뉴 */}
        <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <div className="relative">
            <button
              onClick={() => setShowMenu(!showMenu)}
              className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              <MoreVertical className="w-4 h-4 text-slate-400" />
            </button>

            {showMenu && (
              <>
                {/* Backdrop */}
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setShowMenu(false)}
                />
                {/* Menu */}
                <div className="absolute right-0 top-6 z-20 bg-white dark:bg-slate-800 rounded-lg shadow-lg border border-slate-200 dark:border-slate-700 py-1 min-w-[120px]">
                  {onEdit && (
                    <button
                      onClick={() => {
                        setShowMenu(false);
                        onEdit(cardId);
                      }}
                      className="w-full px-3 py-2 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-700 flex items-center gap-2"
                    >
                      <Edit2 className="w-4 h-4" />
                      편집
                    </button>
                  )}
                  {onDelete && (
                    <button
                      onClick={() => {
                        setShowMenu(false);
                        onDelete(cardId);
                      }}
                      className="w-full px-3 py-2 text-left text-sm text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 flex items-center gap-2"
                    >
                      <Trash2 className="w-4 h-4" />
                      삭제
                    </button>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
