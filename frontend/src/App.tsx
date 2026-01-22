import { useState, useEffect, useCallback, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Sidebar, ViewType } from "./components/layout/Sidebar";
import { ChatContainer } from "./components/ChatContainer";
import DashboardPage from "./components/pages/DashboardPage";
import DataPage from "./components/pages/DataPage";
import WorkflowsPage from "./components/pages/WorkflowsPage";
import RulesetsPage from "./components/pages/RulesetsPage";
import ExperimentsPage from "./components/pages/ExperimentsPage";
import LearningPage from "./components/pages/LearningPage";
import SettingsPage from "./components/pages/SettingsPage";
import { LoginPage } from "./components/pages/LoginPage";
import { DashboardProvider } from "./contexts/DashboardContext";
import { ChatProvider } from "./contexts/ChatContext";
import { AuthProvider } from "./contexts/AuthContext";
import { TenantConfigProvider } from "./contexts/TenantConfigContext";
import { StatCardProvider } from "./contexts/StatCardContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { ToastProvider } from "./components/ui/Toast";
import { getPageComponent } from "./modules/_imports";

const PAGE_INFO: Record<ViewType, { title: string; description: string }> = {
  chat: { title: 'AI Chat', description: '에이전트와 대화하기' },
  dashboard: { title: 'Dashboard', description: '제조 현장 실시간 모니터링' },
  workflows: { title: 'Workflows', description: '자동화 워크플로우 관리' },
  rulesets: { title: 'Rules & Judgment', description: 'Rhai 규칙 관리 및 판단 실행' },
  experiments: { title: 'A/B Tests', description: '규칙 변형 실험 관리' },
  learning: { title: 'Learning', description: '피드백 분석 및 AI 제안 검토' },
  data: { title: 'Data', description: '센서 및 생산 데이터 조회' },
  settings: { title: 'Settings', description: '앱 설정 관리' },
  korea_biopharm: { title: '한국바이오팜', description: '바이오 제약 배합 관리' },
};

const getPageTitle = (view: ViewType) => PAGE_INFO[view]?.title || view;
const getPageDescription = (view: ViewType) => PAGE_INFO[view]?.description || '';

/**
 * 메인 레이아웃 (인증된 사용자용)
 */
function MainLayout() {
  const [currentView, setCurrentView] = useState<ViewType>('chat');
  const [highlightRulesetId, setHighlightRulesetId] = useState<string | null>(null);

  // navigate-to-rulesets 이벤트 리스너
  const handleNavigateToRulesets = useCallback((event: CustomEvent<{ rulesetId: string }>) => {
    setHighlightRulesetId(event.detail.rulesetId);
    setCurrentView('rulesets');
    // 5초 후 하이라이트 해제
    setTimeout(() => setHighlightRulesetId(null), 5000);
  }, []);

  // navigate-to-tab 이벤트 리스너 (ChatMessage에서 탭 링크 클릭 시)
  const handleNavigateToTab = useCallback((event: CustomEvent<{ tab: string }>) => {
    const tabName = event.detail.tab as ViewType;
    const validTabs: ViewType[] = ['chat', 'dashboard', 'workflows', 'rulesets', 'experiments', 'learning', 'data', 'settings'];
    if (validTabs.includes(tabName)) {
      setCurrentView(tabName);
    }
  }, []);

  useEffect(() => {
    window.addEventListener('navigate-to-rulesets', handleNavigateToRulesets as EventListener);
    window.addEventListener('navigate-to-tab', handleNavigateToTab as EventListener);
    return () => {
      window.removeEventListener('navigate-to-rulesets', handleNavigateToRulesets as EventListener);
      window.removeEventListener('navigate-to-tab', handleNavigateToTab as EventListener);
    };
  }, [handleNavigateToRulesets, handleNavigateToTab]);

  const renderContent = () => {
    switch (currentView) {
      case 'chat':
        return <ChatContainer />;
      case 'dashboard':
        return <DashboardPage />;
      case 'workflows':
        return <WorkflowsPage />;
      case 'rulesets':
        return <RulesetsPage highlightRulesetId={highlightRulesetId} />;
      case 'experiments':
        return <ExperimentsPage />;
      case 'learning':
        return <LearningPage />;
      case 'data':
        return <DataPage />;
      case 'settings':
        return <SettingsPage />;
      default: {
        // 동적 모듈 페이지 로드
        const DynamicPage = getPageComponent(currentView);
        if (DynamicPage) {
          return (
            <Suspense fallback={<div className="p-6">Loading...</div>}>
              <DynamicPage />
            </Suspense>
          );
        }
        return <ChatContainer />;
      }
    }
  };

  return (
    <ChatProvider>
      <DashboardProvider>
        <StatCardProvider>
        <div className="flex h-screen bg-slate-50 dark:bg-slate-900">
        {/* Sidebar */}
        <Sidebar currentView={currentView} onViewChange={setCurrentView} />

        {/* Main Content */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {/* Top Bar */}
          <header className="h-14 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 flex items-center px-6">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-50">
              {getPageTitle(currentView)}
            </h2>
            <span className="ml-3 text-sm text-slate-500 dark:text-slate-400">
              {getPageDescription(currentView)}
            </span>
          </header>

          {/* Content Area */}
          <div className="flex-1 overflow-hidden">
            {renderContent()}
          </div>
        </main>
        </div>
        </StatCardProvider>
      </DashboardProvider>
    </ChatProvider>
  );
}

/**
 * 앱 루트 컴포넌트
 */
function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            {/* 로그인 페이지 (Public) */}
            <Route path="/login" element={<LoginPage />} />

            {/* 메인 앱 (Protected) */}
            <Route
              path="/*"
              element={
                <ProtectedRoute>
                  <TenantConfigProvider>
                    <MainLayout />
                  </TenantConfigProvider>
                </ProtectedRoute>
              }
            />

            {/* 기본 리다이렉트 */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </AuthProvider>
  );
}

export default App;
