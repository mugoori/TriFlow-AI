import { useState } from 'react';
import { useAppStore } from '../store/appStore';
import { saveFeedback } from '../services/api';

export default function RecipeViewer() {
  const { productInfo, setCurrentStep, reset, setError } = useAppStore();

  const [selectedOption, setSelectedOption] = useState<'cost' | 'premium' | 'balanced' | null>(null);
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState('');
  const [saved, setSaved] = useState(false);

  const handleSave = async () => {
    if (!selectedOption || rating === 0) {
      setError('옵션과 평점을 선택해주세요.');
      return;
    }

    try {
      await saveFeedback({
        recipe_id: 0, // 실제로는 생성된 레시피 ID
        rating,
        comment: comment || undefined,
      });
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : '저장 중 오류가 발생했습니다.');
    }
  };

  const handleNewRecipe = () => {
    reset();
  };

  return (
    <div className="space-y-6">
      {/* 결과 요약 */}
      <div className="card">
        <h2 className="card-header flex items-center gap-2">
          <svg className="w-5 h-5 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          배합비 결과 기록
        </h2>

        <div className="bg-gray-50 rounded-lg p-4 mb-6">
          <p className="text-gray-700">
            <span className="font-medium">제품명:</span> {productInfo?.name || '-'}
          </p>
          {productInfo?.formulation_type && (
            <p className="text-gray-700 mt-1">
              <span className="font-medium">제형:</span> {productInfo.formulation_type}
            </p>
          )}
        </div>

        {/* 옵션 선택 */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-3">
            선택한 배합비 옵션
          </label>
          <div className="grid grid-cols-3 gap-3">
            {[
              { id: 'cost', label: '원가 최적화', color: 'green' },
              { id: 'premium', label: '프리미엄', color: 'purple' },
              { id: 'balanced', label: '균형', color: 'blue' },
            ].map((option) => (
              <button
                key={option.id}
                onClick={() => setSelectedOption(option.id as 'cost' | 'premium' | 'balanced')}
                className={`
                  p-4 rounded-lg border-2 transition-all duration-200
                  ${selectedOption === option.id
                    ? option.color === 'green'
                      ? 'border-green-500 bg-green-50'
                      : option.color === 'purple'
                      ? 'border-purple-500 bg-purple-50'
                      : 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300'
                  }
                `}
              >
                <span
                  className={`
                    font-medium
                    ${selectedOption === option.id
                      ? option.color === 'green'
                        ? 'text-green-700'
                        : option.color === 'purple'
                        ? 'text-purple-700'
                        : 'text-blue-700'
                      : 'text-gray-700'
                    }
                  `}
                >
                  {option.label}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* 평점 */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-3">
            배합비 품질 평가
          </label>
          <div className="flex items-center gap-2">
            {[1, 2, 3, 4, 5].map((star) => (
              <button
                key={star}
                onClick={() => setRating(star)}
                className="focus:outline-none"
              >
                <svg
                  className={`w-8 h-8 transition-colors ${
                    star <= rating ? 'text-yellow-400' : 'text-gray-300'
                  }`}
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                </svg>
              </button>
            ))}
            <span className="ml-2 text-sm text-gray-500">
              {rating > 0 ? `${rating}점` : '평점을 선택하세요'}
            </span>
          </div>
        </div>

        {/* 코멘트 */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            추가 의견 (선택)
          </label>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="배합비에 대한 추가 의견이나 개선점을 기록하세요"
            rows={3}
            className="input-field"
          />
        </div>

        {/* 저장 버튼 */}
        {saved ? (
          <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-center">
            <svg className="w-12 h-12 text-green-500 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-green-700 font-medium">피드백이 저장되었습니다!</p>
          </div>
        ) : (
          <button onClick={handleSave} className="btn-primary w-full py-3">
            <svg className="w-5 h-5 mr-2 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
            </svg>
            결과 저장하기
          </button>
        )}
      </div>

      {/* 다음 단계 */}
      <div className="flex items-center justify-between">
        <button onClick={() => setCurrentStep('prompt')} className="btn-secondary">
          이전 단계
        </button>
        <button onClick={handleNewRecipe} className="btn-primary">
          <svg className="w-5 h-5 mr-2 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          새 배합비 추천받기
        </button>
      </div>
    </div>
  );
}
