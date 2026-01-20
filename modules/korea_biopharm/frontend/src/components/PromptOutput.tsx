import { useState } from 'react';
import { useAppStore } from '../store/appStore';
import { copyToClipboard } from '../services/api';

export default function PromptOutput() {
  const { generatedPrompt, setCurrentStep } = useAppStore();
  const [copied, setCopied] = useState(false);

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

  return (
    <div className="space-y-6">
      {/* 프롬프트 카드 */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="card-header mb-0 flex items-center gap-2">
            <svg className="w-5 h-5 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            생성된 프롬프트
          </h2>
          <button
            onClick={handleCopy}
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
                클립보드에 복사
              </>
            )}
          </button>
        </div>

        {/* 프롬프트 내용 */}
        <div className="bg-gray-50 rounded-lg p-4 max-h-[500px] overflow-y-auto">
          <pre className="whitespace-pre-wrap text-sm text-gray-800 font-mono leading-relaxed">
            {generatedPrompt}
          </pre>
        </div>
      </div>

      {/* 사용 가이드 */}
      <div className="card bg-blue-50 border-blue-200">
        <h3 className="font-semibold text-blue-900 mb-3 flex items-center gap-2">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Claude Desktop 사용 가이드
        </h3>
        <ol className="list-decimal list-inside space-y-2 text-sm text-blue-800">
          <li>위 프롬프트를 클립보드에 복사합니다.</li>
          <li>Claude Desktop을 열고 SQL MCP가 연결되어 있는지 확인합니다.</li>
          <li>프롬프트를 붙여넣고 실행합니다.</li>
          <li>Claude가 내부 DB를 검색하여 3가지 배합비 옵션을 제안합니다.</li>
          <li>결과를 확인하고 필요시 추가 질문을 합니다.</li>
        </ol>
      </div>

      {/* 예상 출력 형식 */}
      <div className="card">
        <h3 className="card-header flex items-center gap-2">
          <svg className="w-5 h-5 text-biopharm-purple" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
          예상 출력 형식
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 border border-green-200 rounded-lg bg-green-50">
            <div className="flex items-center gap-2 mb-2">
              <span className="badge-green">옵션 1</span>
              <span className="font-medium text-green-900">원가 최적화</span>
            </div>
            <ul className="text-sm text-green-800 space-y-1">
              <li>• 배합비 상세</li>
              <li>• 예상 원가: 000원</li>
              <li>• 제조 주의사항</li>
              <li>• 예상 품질 평가</li>
            </ul>
          </div>

          <div className="p-4 border border-purple-200 rounded-lg bg-purple-50">
            <div className="flex items-center gap-2 mb-2">
              <span className="badge-purple">옵션 2</span>
              <span className="font-medium text-purple-900">프리미엄</span>
            </div>
            <ul className="text-sm text-purple-800 space-y-1">
              <li>• 배합비 상세</li>
              <li>• 예상 원가: 000원</li>
              <li>• 제조 주의사항</li>
              <li>• 예상 품질 평가</li>
            </ul>
          </div>

          <div className="p-4 border border-blue-200 rounded-lg bg-blue-50">
            <div className="flex items-center gap-2 mb-2">
              <span className="badge-blue">옵션 3</span>
              <span className="font-medium text-blue-900">균형</span>
            </div>
            <ul className="text-sm text-blue-800 space-y-1">
              <li>• 배합비 상세</li>
              <li>• 예상 원가: 000원</li>
              <li>• 제조 주의사항</li>
              <li>• 예상 품질 평가</li>
            </ul>
          </div>
        </div>
      </div>

      {/* 버튼 */}
      <div className="flex items-center justify-between">
        <button onClick={() => setCurrentStep('search')} className="btn-secondary">
          이전 단계
        </button>
        <button onClick={() => setCurrentStep('result')} className="btn-primary">
          결과 기록하기
          <svg className="w-5 h-5 ml-2 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>
    </div>
  );
}
