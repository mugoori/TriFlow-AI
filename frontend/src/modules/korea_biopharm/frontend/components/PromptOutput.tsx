import { useState } from 'react';
import { useAppStore } from '../store/appStore';
import { copyToClipboard, generateRecipe } from '../services/api';

export default function PromptOutput() {
  const {
    generatedPrompt,
    productInfo,
    ingredientRequirements,
    constraints,
    searchResults,
    setCurrentStep,
    setRecipeResult,
    setIsLoading,
    setError
  } = useAppStore();

  const [copied, setCopied] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [isPromptExpanded, setIsPromptExpanded] = useState(false);

  if (!generatedPrompt) {
    return <div className="text-center py-10 text-gray-500">생성된 프롬프트가 없습니다.</div>;
  }

  const handleCopy = async () => {
    const success = await copyToClipboard(generatedPrompt);
    if (success) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleGenerateRecipe = async () => {
    if (!productInfo) {
      setError('제품 정보가 없습니다.');
      return;
    }

    setGenerating(true);
    setIsLoading(true);
    setError(null);

    try {
      const result = await generateRecipe({
        product_info: productInfo,
        ingredient_requirements: ingredientRequirements,
        constraints: constraints,
        similar_products_api: searchResults?.api_results || []
      });

      setRecipeResult(result);
      setCurrentStep('result');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'AI 배합비 생성 중 오류가 발생했습니다.');
    } finally {
      setGenerating(false);
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* 프롬프트 카드 (접기/펼치기) */}
      <div className="card">
        <button
          onClick={() => setIsPromptExpanded(!isPromptExpanded)}
          className="w-full flex items-center justify-between mb-4 cursor-pointer hover:opacity-80 transition-opacity"
        >
          <h2 className="card-header mb-0 flex items-center gap-2">
            <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            생성된 프롬프트
          </h2>
          <div className="flex items-center gap-2">
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleCopy();
              }}
              className={`
                flex items-center gap-2 px-4 py-2 rounded-lg transition-all duration-200
                ${copied
                  ? 'bg-green-100 text-green-700'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }
              `}
            >
              {copied ? (
                <>
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  복사됨!
                </>
              ) : (
                <>
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                  </svg>
                  복사
                </>
              )}
            </button>
            <svg
              className={`w-5 h-5 text-gray-500 transition-transform duration-200 ${isPromptExpanded ? 'rotate-180' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </button>

        {/* 프롬프트 내용 (펼쳐진 경우만 표시) */}
        {isPromptExpanded && (
          <div className="bg-gray-50 rounded-lg p-4 max-h-[500px] overflow-y-auto">
            <pre className="whitespace-pre-wrap text-sm text-gray-800 font-mono leading-relaxed">
              {generatedPrompt}
            </pre>
          </div>
        )}
      </div>

      {/* AI 자동 생성 안내 */}
      <div className="card bg-gradient-to-r from-purple-50 to-blue-50 border-purple-200">
        <div className="flex items-start gap-4">
          <div className="flex-shrink-0">
            <svg className="w-12 h-12 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <div className="flex-1">
            <h3 className="font-bold text-lg text-purple-900 mb-2">AI 자동 배합비 생성</h3>
            <p className="text-purple-800 mb-4">
              TriFlow의 Claude API를 사용하여 자동으로 3가지 배합비 옵션을 생성합니다.
              내부 DB 검색과 공공 API 데이터를 모두 활용합니다.
            </p>
            <button
              onClick={handleGenerateRecipe}
              disabled={generating}
              className={`
                px-6 py-3 rounded-lg font-medium transition-all duration-200
                flex items-center gap-2
                ${generating
                  ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  : 'bg-purple-600 text-white hover:bg-purple-700 shadow-lg hover:shadow-xl'
                }
              `}
            >
              {generating ? (
                <>
                  <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  AI 배합비 생성 중...
                </>
              ) : (
                <>
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  AI 배합비 자동 생성
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* 버튼 */}
      <div className="flex items-center justify-between">
        <button onClick={() => setCurrentStep('search')} className="btn-secondary">
          이전 단계
        </button>
        <button onClick={() => setCurrentStep('result')} className="btn-secondary">
          수동으로 결과 기록
          <svg className="w-5 h-5 ml-2 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>
    </div>
  );
}
