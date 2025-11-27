import { useState } from "react";
import { Sidebar, ViewType } from "./components/layout/Sidebar";
import { ChatContainer } from "./components/ChatContainer";
import { DashboardPage } from "./components/pages/DashboardPage";
import { PlaceholderPage } from "./components/pages/PlaceholderPage";
import { DashboardProvider } from "./contexts/DashboardContext";

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
            title="Workflows"
            description="자동화 워크플로우를 생성하고 관리합니다. AI Chat에서 '워크플로우 만들어줘'라고 요청하면 Workflow Agent가 DSL을 생성합니다."
          />
        );
      case 'data':
        return (
          <PlaceholderPage
            title="Data Management"
            description="센서 데이터, 생산 데이터 등을 조회하고 관리합니다. AI Chat에서 데이터 관련 질문을 하면 BI Agent가 SQL을 생성하여 데이터를 조회합니다."
          />
        );
      case 'settings':
        return (
          <PlaceholderPage
            title="Settings"
            description="앱 설정, 테넌트 관리, API 키 설정 등을 관리합니다."
          />
        );
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
            <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-50 capitalize">
              {currentView === 'chat' ? 'AI Chat' : currentView}
            </h2>
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
