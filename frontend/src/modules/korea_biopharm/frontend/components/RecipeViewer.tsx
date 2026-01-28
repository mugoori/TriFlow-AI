import { useState } from 'react';
import { useAppStore } from '../store/appStore';
import { saveAIRecipe, saveAIRecipeFeedback } from '../services/api';
import type { RecipeOption, AIGeneratedRecipeCreate } from '../types';

export default function RecipeViewer() {
  const { productInfo, recipeResult, setCurrentStep, reset, setError } = useAppStore();

  const [selectedOption, setSelectedOption] = useState<RecipeOption | null>(null);
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState('');
  const [saved, setSaved] = useState(false);

  if (!recipeResult || !recipeResult.recipe_options || recipeResult.recipe_options.length === 0) {
    return (
      <div className="space-y-6">
        <div className="card">
          <h2 className="card-header text-red-600">배합비 생성 실패</h2>
          <p className="text-gray-700">
            {recipeResult?.error || '배합비를 생성하지 못했습니다. 다시 시도해주세요.'}
          </p>
          <div className="flex items-center justify-between mt-6">
            <button onClick={() => setCurrentStep('prompt')} className="btn-secondary">
              이전 단계
            </button>
            <button onClick={reset} className="btn-primary">
              처음부터 다시
            </button>
          </div>
        </div>
      </div>
    );
  }

  const options = recipeResult.recipe_options;

  const handleSave = async () => {
    if (!selectedOption || rating === 0) {
      setError('옵션과 평점을 선택해주세요.');
      return;
    }

    try {
      // 1. AI 레시피 저장
      const recipeData: AIGeneratedRecipeCreate = {
        product_name: productInfo?.name || '미지정 제품',
        formulation_type: productInfo?.formulation_type,
        option_type: selectedOption.option_type,
        title: selectedOption.title,
        ingredients: selectedOption.ingredients,
        total_ratio: selectedOption.total_ratio,
        estimated_cost: selectedOption.estimated_cost,
        notes: selectedOption.notes,
        quality: selectedOption.quality,
        summary: selectedOption.summary,
        source_type: 'ai_generated',
      };

      const savedRecipe = await saveAIRecipe(recipeData);

      // 2. 피드백 저장
      await saveAIRecipeFeedback(savedRecipe.recipe_id, {
        rating,
        comment: comment || undefined,
        feedback_type: 'quality',
      });

      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : '저장 중 오류가 발생했습니다.');
    }
  };

  const handleNewRecipe = () => {
    reset();
  };

  const getOptionColor = (type: string) => {
    switch (type) {
      case 'cost_optimized':
        return 'green';
      case 'premium':
        return 'purple';
      case 'balanced':
        return 'blue';
      default:
        return 'gray';
    }
  };

  const getColorClasses = (color: string, selected: boolean) => {
    if (selected) {
      switch (color) {
        case 'green':
          return 'border-green-500 bg-green-50 text-green-700';
        case 'purple':
          return 'border-purple-500 bg-purple-50 text-purple-700';
        case 'blue':
          return 'border-blue-500 bg-blue-50 text-blue-700';
        default:
          return 'border-gray-500 bg-gray-50 text-gray-700';
      }
    }
    return 'border-gray-200 hover:border-gray-300 text-gray-700';
  };

  return (
    <div className="space-y-6">
      {/* 제품 정보 요약 */}
      <div className="card">
        <h2 className="card-header flex items-center gap-2">
          <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          AI 배합비 생성 결과
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
          <p className="text-gray-600 text-sm mt-2">
            생성 시간: {new Date(recipeResult.generated_at).toLocaleString('ko-KR')}
          </p>
        </div>

        {/* 3가지 옵션 카드 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          {options.map((option) => {
            const color = getOptionColor(option.option_type);
            const isSelected = selectedOption?.option_type === option.option_type;

            return (
              <button
                key={option.option_type}
                onClick={() => setSelectedOption(option)}
                className={`
                  p-4 rounded-lg border-2 transition-all duration-200 text-left
                  ${getColorClasses(color, isSelected)}
                `}
              >
                <h3 className="font-bold text-lg mb-2">{option.title}</h3>
                <div className="space-y-1 text-sm">
                  <p>원료 수: {option.ingredients.length}종</p>
                  <p>총 배합비: {option.total_ratio.toFixed(2)}%</p>
                  {option.estimated_cost && (
                    <p className="font-medium">{option.estimated_cost}</p>
                  )}
                </div>
              </button>
            );
          })}
        </div>

        {/* 선택된 옵션 상세보기 */}
        {selectedOption && (
          <div className="border-t pt-6">
            <h3 className="font-bold text-lg mb-4">{selectedOption.title} - 배합비 상세</h3>

            {/* 배합비 테이블 */}
            <div className="overflow-x-auto mb-6">
              <table className="min-w-full divide-y divide-gray-200 border">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      No
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      원료명
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      배합비 (%)
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      역할
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {selectedOption.ingredients.map((ing, idx) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                        {ing.no}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                        {ing.name}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                        {ing.ratio.toFixed(2)}%
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600">
                        {ing.role}
                      </td>
                    </tr>
                  ))}
                  <tr className="bg-gray-50 font-bold">
                    <td className="px-4 py-3 text-sm text-gray-900" colSpan={2}>
                      합계
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900 text-right">
                      {selectedOption.total_ratio.toFixed(2)}%
                    </td>
                    <td className="px-4 py-3"></td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* 추가 정보 */}
            {selectedOption.estimated_cost && (
              <div className="mb-4">
                <h4 className="font-medium text-gray-700 mb-1">예상 원가</h4>
                <p className="text-gray-900">{selectedOption.estimated_cost}</p>
              </div>
            )}

            {selectedOption.notes && (
              <div className="mb-4">
                <h4 className="font-medium text-gray-700 mb-1">제조 시 주의사항</h4>
                <p className="text-gray-900 whitespace-pre-wrap">{selectedOption.notes}</p>
              </div>
            )}

            {selectedOption.quality && (
              <div className="mb-4">
                <h4 className="font-medium text-gray-700 mb-1">예상 품질</h4>
                <p className="text-gray-900 whitespace-pre-wrap">{selectedOption.quality}</p>
              </div>
            )}
          </div>
        )}

        {/* 평점 */}
        <div className="border-t pt-6 mb-6">
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
