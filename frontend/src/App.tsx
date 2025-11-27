import { useState } from "react";
import { Sidebar, ViewType } from "./components/layout/Sidebar";
import { ChatContainer } from "./components/ChatContainer";
import { DashboardPage } from "./components/pages/DashboardPage";
import { DataPage } from "./components/pages/DataPage";
import { SettingsPage } from "./components/pages/SettingsPage";
import { PlaceholderPage } from "./components/pages/PlaceholderPage";
import { DashboardProvider } from "./contexts/DashboardContext";

const PAGE_INFO: Record<ViewType, { title: string; description: string }> = {
  chat: { title: 'AI Chat', description: '에이전트와 대화하기' },
  dashboard: { title: 'Dashboard', description: '제조 현장 실시간 모니터링' },
  workflows: { title: 'Workflows', description: '자동화 워크플로우 관리' },
  data: { title: 'Data', description: '센서 및 생산 데이터 조회' },
  settings: { title: 'Settings', description: '앱 설정 관리' },
};

const getPageTitle = (view: ViewType) => PAGE_INFO[view]?.title || view;
const getPageDescription = (view: ViewType) => PAGE_INFO[view]?.description || '';

function App() {
  const [currentView, setCurrentView] = useState<ViewType>('chat');

  const renderContent = () => {
    switch (currentView) {
      case 'chat':
        return <ChatContainer />;
      case 'dashboard':
        return <DashboardPage />;
      case 'workflows':
        return (
          <PlaceholderPage
            description="자동화 워크플로우를 생성하고 관리합니다. AI Chat에서 '워크플로우 만들어줘'라고 요청하면 Workflow Agent가 DSL을 생성합니다."
          />
        );
      case 'data':
        return <DataPage />;
      case 'settings':
        return <SettingsPage />;
      default:
        return <ChatContainer />;
    }
  };

  return (
    <DashboardProvider>
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
    </DashboardProvider>
  );
}

export default App;
