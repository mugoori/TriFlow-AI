import { useAppStore } from './store/appStore';
import Header from './components/Header';
import StepIndicator from './components/StepIndicator';
import ProductForm from './components/ProductForm';
import SearchResults from './components/SearchResults';
import PromptOutput from './components/PromptOutput';
import RecipeViewer from './components/RecipeViewer';

function App() {
  const { currentStep, error, setError } = useAppStore();

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />

      <main className="max-w-6xl mx-auto px-4 py-8">
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
      </main>

      {/* 푸터 */}
      <footer className="mt-auto py-6 text-center text-gray-500 text-sm">
        <p>한국바이오팜 AI 배합비 추천 시스템 v1.0</p>
        <p className="mt-1">솔루션트리 &copy; 2024</p>
      </footer>
    </div>
  );
}

export default App;
