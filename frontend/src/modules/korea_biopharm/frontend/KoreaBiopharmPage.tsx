import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAppStore } from './store/appStore';
import Header from './components/Header';
import StepIndicator from './components/StepIndicator';
import ProductForm from './components/ProductForm';
import SearchResults from './components/SearchResults';
import PromptOutput from './components/PromptOutput';
import RecipeViewer from './components/RecipeViewer';
import RecipesPage from './components/RecipesPage';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 5 * 60 * 1000,
    },
  },
});

type TabType = 'create' | 'recipes';

export default function KoreaBiopharmPage() {
  return (
    <QueryClientProvider client={queryClient}>
      <KoreaBiopharmContent />
    </QueryClientProvider>
  );
}

function KoreaBiopharmContent() {
  const { currentStep, error, setError } = useAppStore();
  const [activeTab, setActiveTab] = useState<TabType>('create');

  return (
    <div className="h-full overflow-y-auto bg-gray-50">
      <div className="max-w-6xl mx-auto p-6 space-y-6">
        <Header />

        {/* 탭 네비게이션 */}
        <div className="flex border-b border-gray-200">
          <button
            onClick={() => setActiveTab('create')}
            className={`
              px-6 py-3 font-medium text-sm transition-colors border-b-2 -mb-px
              ${activeTab === 'create'
                ? 'text-biopharm-green border-biopharm-green'
                : 'text-gray-500 border-transparent hover:text-gray-700 hover:border-gray-300'}
            `}
          >
            <svg className="w-5 h-5 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            새 레시피 생성
          </button>
          <button
            onClick={() => setActiveTab('recipes')}
            className={`
              px-6 py-3 font-medium text-sm transition-colors border-b-2 -mb-px
              ${activeTab === 'recipes'
                ? 'text-biopharm-green border-biopharm-green'
                : 'text-gray-500 border-transparent hover:text-gray-700 hover:border-gray-300'}
            `}
          >
            <svg className="w-5 h-5 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            내 레시피
          </button>
        </div>

        {/* 탭 콘텐츠 */}
        {activeTab === 'create' ? (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <StepIndicator />

            {/* 에러 메시지 */}
            {error && typeof error === 'string' && (
              <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4 flex justify-between items-center">
                <span className="text-red-700">{error}</span>
                <button
                  onClick={() => setError(null)}
                  className="text-red-500 hover:text-red-700"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            )}

            {/* 단계별 컴포넌트 */}
            <div className="space-y-6">
              {currentStep === 'input' && <ProductForm />}
              {currentStep === 'search' && <SearchResults />}
              {currentStep === 'prompt' && <PromptOutput />}
              {currentStep === 'result' && <RecipeViewer />}
            </div>
          </div>
        ) : (
          <RecipesPage />
        )}

        {/* 푸터 */}
        <footer className="mt-6 text-center text-gray-600 text-sm">
          <p>한국바이오팜 AI 배합비 추천 시스템 v1.0</p>
          <p className="mt-1">솔루션트리 &copy; 2024</p>
        </footer>
      </div>
    </div>
  );
}
