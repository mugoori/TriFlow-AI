/**
 * DataPage
 * 데이터 관리 페이지 - 센서, ERP/MES, RAG 데이터 통합 관리
 */

import { useState } from 'react';
import { Database, Factory, BookOpen } from 'lucide-react';
import { SensorDataTab } from '@/components/data/SensorDataTab';
import { ErpMesDataTab } from '@/components/data/ErpMesDataTab';
import { RagDocumentsTab } from '@/components/data/RagDocumentsTab';

type TabType = 'sensors' | 'erp-mes' | 'rag';

interface Tab {
  id: TabType;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const tabs: Tab[] = [
  { id: 'sensors', label: '센서 데이터', icon: Database },
  { id: 'erp-mes', label: 'ERP/MES', icon: Factory },
  { id: 'rag', label: '지식 베이스', icon: BookOpen },
];

export default function DataPage() {
  const [activeTab, setActiveTab] = useState<TabType>('sensors');

  return (
    <div className="h-full overflow-y-auto">
      <div className="p-6 space-y-6">
        {/* 탭 네비게이션 */}
        <div className="border-b border-slate-200 dark:border-slate-700">
          <nav className="flex gap-1" aria-label="Tabs">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;

              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`
                    flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors
                    ${
                      isActive
                        ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400'
                        : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300 dark:text-slate-400 dark:hover:text-slate-300'
                    }
                  `}
                >
                  <Icon className="w-4 h-4" />
                  {tab.label}
                </button>
              );
            })}
          </nav>
        </div>

        {/* 탭 콘텐츠 */}
        <div>
          {activeTab === 'sensors' && <SensorDataTab />}
          {activeTab === 'erp-mes' && <ErpMesDataTab />}
          {activeTab === 'rag' && <RagDocumentsTab />}
        </div>
      </div>
    </div>
  );
}
