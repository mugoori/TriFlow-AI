import { useState } from "react";
import { ChatContainer } from "./components/ChatContainer";
import { Button } from "./components/ui/button";

type View = 'chat' | 'tenants';

function App() {
  const [currentView, setCurrentView] = useState<View>('chat');

  return (
    <div className="flex flex-col h-screen bg-slate-50 dark:bg-slate-900">
      {/* 헤더 */}
      <header className="border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-50">
              TriFlow AI
            </h1>
            <div className="flex gap-2">
              <Button
                variant={currentView === 'chat' ? 'default' : 'outline'}
                onClick={() => setCurrentView('chat')}
              >
                Chat
              </Button>
              <Button
                variant={currentView === 'tenants' ? 'default' : 'outline'}
                onClick={() => setCurrentView('tenants')}
              >
                Tenants
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* 메인 컨텐츠 */}
      <main className="flex-1 overflow-hidden">
        {currentView === 'chat' ? (
          <ChatContainer />
        ) : (
          <div className="container mx-auto px-4 py-8">
            <p className="text-slate-600 dark:text-slate-400">
              Tenant 관리 기능은 추후 구현 예정입니다.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
