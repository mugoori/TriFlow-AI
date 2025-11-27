import { MessageSquare, BarChart3, Settings, Database, Workflow } from 'lucide-react';
import { cn } from '@/lib/utils';

export type ViewType = 'chat' | 'dashboard' | 'workflows' | 'data' | 'settings';

interface SidebarProps {
  currentView: ViewType;
  onViewChange: (view: ViewType) => void;
}

interface NavItem {
  id: ViewType;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  description: string;
}

const navItems: NavItem[] = [
  {
    id: 'chat',
    label: 'AI Chat',
    icon: MessageSquare,
    description: 'AI 에이전트와 대화',
  },
  {
    id: 'dashboard',
    label: 'Dashboard',
    icon: BarChart3,
    description: '데이터 시각화',
  },
  {
    id: 'workflows',
    label: 'Workflows',
    icon: Workflow,
    description: '자동화 워크플로우',
  },
  {
    id: 'data',
    label: 'Data',
    icon: Database,
    description: '데이터 관리',
  },
  {
    id: 'settings',
    label: 'Settings',
    icon: Settings,
    description: '설정',
  },
];

export function Sidebar({ currentView, onViewChange }: SidebarProps) {
  return (
    <aside className="w-64 bg-slate-900 text-white flex flex-col h-full">
      {/* Logo */}
      <div className="p-4 border-b border-slate-700">
        <h1 className="text-xl font-bold flex items-center gap-2">
          <img src="/logo.png" alt="TriFlow AI" className="w-6 h-6" />
          TriFlow AI
        </h1>
        <p className="text-xs text-slate-400 mt-1">Manufacturing AI Engine</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentView === item.id;

          return (
            <button
              key={item.id}
              onClick={() => onViewChange(item.id)}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors text-left',
                isActive
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-300 hover:bg-slate-800 hover:text-white'
              )}
            >
              <Icon className="w-5 h-5 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="font-medium text-sm">{item.label}</div>
                <div className={cn(
                  'text-xs truncate',
                  isActive ? 'text-blue-200' : 'text-slate-500'
                )}>
                  {item.description}
                </div>
              </div>
            </button>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-slate-700">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <div className="w-2 h-2 rounded-full bg-green-500"></div>
          <span>Backend Connected</span>
        </div>
        <div className="text-xs text-slate-600 mt-1">v0.1.0</div>
      </div>
    </aside>
  );
}
