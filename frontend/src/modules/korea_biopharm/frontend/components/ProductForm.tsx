import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAppStore } from '../store/appStore';
import { getFormulationTypes, searchProducts } from '../services/api';
import IngredientAutocomplete from './IngredientAutocomplete';
import type { ProductInfo, IngredientRequirement } from '../types';

export default function ProductForm() {
  const {
    productInfo,
    ingredientRequirements,
    constraints,
    isLoading,
    setProductInfo,
    setIngredientRequirements,
    setConstraints,
    setSearchResults,
    setCurrentStep,
    setIsLoading,
    setError,
  } = useAppStore();

  // 폼 상태 (store에서 초기값 복원)
  const [productName, setProductName] = useState(productInfo?.name || '');
  const [formulationType, setFormulationType] = useState(productInfo?.formulation_type || '');
  const [targetCost, setTargetCost] = useState(productInfo?.target_cost?.toString() || '');
  const [targetWeight, setTargetWeight] = useState(productInfo?.target_weight?.toString() || '');
  const [description, setDescription] = useState(productInfo?.description || '');

  // 원료 요구사항 (store에서 복원)
  const [ingredients, setIngredients] = useState<IngredientRequirement[]>(
    ingredientRequirements.length > 0
      ? ingredientRequirements
      : [{ ingredient_name: '', is_required: true }]
  );

  // 제약 조건 (store에서 복원)
  const [maxIngredients, setMaxIngredients] = useState(constraints.max_ingredients?.toString() || '');
  const [avoidIngredients, setAvoidIngredients] = useState(constraints.avoid_ingredients?.join(', ') || '');
  const [qualityReqs, setQualityReqs] = useState(constraints.quality_requirements?.join(', ') || '');

  // 제형 타입 로드
  const { data: formulationTypes = [] } = useQuery({
    queryKey: ['formulationTypes'],
    queryFn: getFormulationTypes,
  });

  // 원료 추가
  const addIngredient = () => {
    setIngredients([...ingredients, { ingredient_name: '', is_required: false }]);
  };

  // 원료 제거
  const removeIngredient = (index: number) => {
    setIngredients(ingredients.filter((_, i) => i !== index));
  };

  // 원료 수정
  const updateIngredient = (index: number, field: keyof IngredientRequirement, value: unknown) => {
    const updated = [...ingredients];
    updated[index] = { ...updated[index], [field]: value };
    setIngredients(updated);
  };

  // 폼 제출
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!productName.trim()) {
      setError('제품명을 입력해주세요.');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      // 제품 정보 저장
      const productInfo: ProductInfo = {
        name: productName,
        formulation_type: formulationType,
        target_cost: targetCost ? parseFloat(targetCost) : undefined,
        target_weight: targetWeight ? parseFloat(targetWeight) : undefined,
        description: description || undefined,
      };
      setProductInfo(productInfo);

      // 원료 요구사항 저장
      const validIngredients = ingredients.filter((i) => i.ingredient_name.trim());
      setIngredientRequirements(validIngredients);

      // 제약 조건 저장
      setConstraints({
        max_ingredients: maxIngredients ? parseInt(maxIngredients) : undefined,
        avoid_ingredients: avoidIngredients
          ? avoidIngredients.split(',').map((s) => s.trim())
          : undefined,
        quality_requirements: qualityReqs
          ? qualityReqs.split(',').map((s) => s.trim())
          : undefined,
      });

      // 유사 제품 검색 (원료명 기반으로 검색)
      // 입력된 원료가 있으면 원료명으로 검색, 없으면 제품명으로 검색
      const searchQuery = validIngredients.length > 0
        ? validIngredients.map(i => i.ingredient_name).join(',')
        : productName;
      const results = await searchProducts(searchQuery, true, true);
      setSearchResults(results);

      setCurrentStep('search');
    } catch (err) {
      setError(err instanceof Error ? err.message : '검색 중 오류가 발생했습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* 제품 정보 */}
      <div className="card">
        <h2 className="card-header flex items-center gap-2">
          <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          제품 정보
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              제품명 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={productName}
              onChange={(e) => setProductName(e.target.value)}
              placeholder="예: 루테인 눈건강 골드"
              className="input-field"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">제형</label>
            <select
              value={formulationType}
              onChange={(e) => setFormulationType(e.target.value)}
              className="input-field"
            >
              <option value="">선택하세요</option>
              {formulationTypes.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">목표 원가 (원)</label>
            <input
              type="number"
              value={targetCost}
              onChange={(e) => setTargetCost(e.target.value)}
              placeholder="예: 500"
              className="input-field"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">목표 중량 (mg)</label>
            <input
              type="number"
              value={targetWeight}
              onChange={(e) => setTargetWeight(e.target.value)}
              placeholder="예: 1000"
              className="input-field"
            />
          </div>

          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1">제품 설명</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="제품의 특징이나 목적을 간략히 설명해주세요"
              rows={2}
              className="input-field"
            />
          </div>
        </div>
      </div>

      {/* 원료 요구사항 */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="card-header mb-0 flex items-center gap-2">
            <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
            </svg>
            원료 요구사항
          </h2>
          <button type="button" onClick={addIngredient} className="btn-secondary text-sm">
            + 원료 추가
          </button>
        </div>

        <div className="space-y-3">
          {ingredients.map((ing, index) => (
            <div key={index} className="grid grid-cols-12 items-center gap-3">
              <div className="col-span-6">
                <IngredientAutocomplete
                  value={ing.ingredient_name}
                  onChange={(value) => updateIngredient(index, 'ingredient_name', value)}
                  placeholder="원료명 검색..."
                  className="input-field"
                />
              </div>
              <div className="col-span-2">
                <input
                  type="number"
                  value={ing.min_ratio || ''}
                  onChange={(e) => updateIngredient(index, 'min_ratio', e.target.value ? parseFloat(e.target.value) : undefined)}
                  placeholder="최소%"
                  className="input-field"
                />
              </div>
              <div className="col-span-2">
                <input
                  type="number"
                  value={ing.max_ratio || ''}
                  onChange={(e) => updateIngredient(index, 'max_ratio', e.target.value ? parseFloat(e.target.value) : undefined)}
                  placeholder="최대%"
                  className="input-field"
                />
              </div>
              <div className="col-span-1 flex items-center justify-center">
                <label className="flex items-center gap-1 text-sm text-gray-700 whitespace-nowrap">
                  <input
                    type="checkbox"
                    checked={ing.is_required}
                    onChange={(e) => updateIngredient(index, 'is_required', e.target.checked)}
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  필수
                </label>
              </div>
              <div className="col-span-1 flex items-center justify-center">
                {ingredients.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeIngredient(index)}
                    className="text-red-500 hover:text-red-700 p-2"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 제약 조건 */}
      <div className="card">
        <h2 className="card-header flex items-center gap-2">
          <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
          제약 조건
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">최대 원료 수</label>
            <input
              type="number"
              value={maxIngredients}
              onChange={(e) => setMaxIngredients(e.target.value)}
              placeholder="예: 15"
              className="input-field"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">피해야 할 원료 (쉼표로 구분)</label>
            <input
              type="text"
              value={avoidIngredients}
              onChange={(e) => setAvoidIngredients(e.target.value)}
              placeholder="예: 이산화규소, 스테아린산마그네슘"
              className="input-field"
            />
          </div>

          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1">품질 요구사항 (쉼표로 구분)</label>
            <input
              type="text"
              value={qualityReqs}
              onChange={(e) => setQualityReqs(e.target.value)}
              placeholder="예: 비건 인증, 무첨가, 저칼로리"
              className="input-field"
            />
          </div>
        </div>
      </div>

      {/* 제출 버튼 */}
      <div className="flex justify-end">
        <button
          type="submit"
          disabled={isLoading}
          className={`
            px-8 py-3 text-lg font-medium rounded-lg transition-all duration-200
            flex items-center gap-2
            ${isLoading
              ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
              : 'btn-primary'
            }
          `}
        >
          {isLoading ? (
            <>
              <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              유사 제품 검색 중...
            </>
          ) : (
            <>
              유사 제품 검색
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </>
          )}
        </button>
      </div>
    </form>
  );
}
