import { useState } from 'react';
import { useAppStore } from '../store/appStore';
import { generatePrompt } from '../services/api';
import ProductDetailModal from './ProductDetailModal';
import type { SimilarProductAPI, RecipeMetadata } from '../types';

export default function SearchResults() {
  const {
    productInfo,
    ingredientRequirements,
    constraints,
    searchResults,
    setGeneratedPrompt,
    setCurrentStep,
    setIsLoading,
    setError,
  } = useAppStore();

  const [selectedInternal, setSelectedInternal] = useState<number[]>([]);
  const [selectedApi, setSelectedApi] = useState<number[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState<SimilarProductAPI | RecipeMetadata | null>(null);
  const [selectedProductType, setSelectedProductType] = useState<'api' | 'internal'>('api');

  if (!searchResults || !searchResults.internal_results || !searchResults.api_results) {
    return <div className="text-center py-10 text-gray-500">검색 결과가 없습니다.</div>;
  }

  const toggleInternal = (id: number) => {
    setSelectedInternal((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  };

  const toggleApi = (index: number) => {
    setSelectedApi((prev) =>
      prev.includes(index) ? prev.filter((i) => i !== index) : [...prev, index]
    );
  };

  const openProductDetail = (product: SimilarProductAPI | RecipeMetadata, type: 'api' | 'internal') => {
    setSelectedProduct(product);
    setSelectedProductType(type);
    setModalOpen(true);
  };

  const handleGeneratePrompt = async () => {
    if (!productInfo) return;

    setIsLoading(true);
    setError(null);

    try {
      // 선택된 API 제품만 전달
      const selectedApiProducts = selectedApi.map((i) => searchResults.api_results[i]);

      const response = await generatePrompt({
        product_info: productInfo,
        ingredient_requirements: ingredientRequirements,
        constraints: constraints,
        similar_products_api: selectedApiProducts,
      });

      setGeneratedPrompt(response.prompt);
      setCurrentStep('prompt');
    } catch (err) {
      setError(err instanceof Error ? err.message : '프롬프트 생성 중 오류가 발생했습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* 내부 DB 결과 */}
      <div className="card">
        <h2 className="card-header flex items-center gap-2">
          <svg className="w-5 h-5 text-biopharm-green" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
          </svg>
          내부 DB 유사 제품
          <span className="badge-green">{searchResults.internal_results.length}건</span>
        </h2>

        <p className="text-sm text-gray-500 mb-4">
          Claude Desktop에서 SQL MCP를 통해 상세 배합비를 조회합니다.
        </p>

        {searchResults.internal_results.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-64 overflow-y-auto">
            {searchResults.internal_results.map((item: RecipeMetadata) => (
              <label
                key={item.id}
                className={`
                  flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-all
                  ${selectedInternal.includes(item.id)
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300'
                  }
                `}
              >
                <input
                  type="checkbox"
                  checked={selectedInternal.includes(item.id)}
                  onChange={() => toggleInternal(item.id)}
                  className="mt-1 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-900 truncate">{item.product_name}</p>
                  <div className="flex items-center gap-2 mt-1 text-sm text-gray-500">
                    {item.formulation_type && (
                      <span className="badge-blue">{item.formulation_type}</span>
                    )}
                    {item.ingredient_count && (
                      <span>원료 {item.ingredient_count}종</span>
                    )}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    openProductDetail(item, 'internal');
                  }}
                  className="text-biopharm-green hover:text-biopharm-green/80 p-1"
                  title="상세 보기"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                </button>
              </label>
            ))}
          </div>
        ) : (
          <p className="text-gray-500 text-center py-4">일치하는 내부 제품이 없습니다.</p>
        )}
      </div>

      {/* 공공 API 결과 */}
      <div className="card">
        <h2 className="card-header flex items-center gap-2">
          <svg className="w-5 h-5 text-biopharm-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
          </svg>
          식품안전나라 유사 제품
          <span className="badge-blue">{searchResults.api_results.length}건</span>
        </h2>

        <p className="text-sm text-gray-500 mb-4">
          소비기한, 원료 조합 등 참고 정보를 프롬프트에 포함합니다.
        </p>

        {searchResults.api_results.length > 0 ? (
          <div className="space-y-3 max-h-80 overflow-y-auto">
            {searchResults.api_results.map((item: SimilarProductAPI, index: number) => (
              <label
                key={index}
                className={`
                  block p-4 rounded-lg border cursor-pointer transition-all
                  ${selectedApi.includes(index)
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300'
                  }
                `}
              >
                <div className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    checked={selectedApi.includes(index)}
                    onChange={() => toggleApi(index)}
                    className="mt-1 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-gray-900">{item.product_name}</p>
                      <span className="badge-purple">{item.source}</span>
                    </div>
                    <p className="text-sm text-gray-600 mt-1">{item.company_name}</p>
                    {item.raw_materials && (
                      <p className="text-sm text-gray-500 mt-2 line-clamp-2">
                        <span className="font-medium">원료: </span>
                        {item.raw_materials}
                      </p>
                    )}
                    {item.shelf_life && (
                      <p className="text-sm text-gray-500 mt-1">
                        <span className="font-medium">소비기한: </span>
                        {item.shelf_life}
                      </p>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.preventDefault();
                      openProductDetail(item, 'api');
                    }}
                    className="text-blue-600 hover:text-blue-700 p-2"
                    title="상세 보기"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                  </button>
                </div>
              </label>
            ))}
          </div>
        ) : (
          <p className="text-gray-500 text-center py-4">
            일치하는 공공 API 제품이 없습니다.
            <br />
            <span className="text-sm">(API 승인 대기 중일 수 있습니다)</span>
          </p>
        )}
      </div>

      {/* 선택 요약 및 버튼 */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-gray-600">
          선택됨: 내부 {selectedInternal.length}건, API {selectedApi.length}건
        </div>
        <div className="flex gap-3">
          <button onClick={() => setCurrentStep('input')} className="btn-secondary">
            이전 단계
          </button>
          <button onClick={handleGeneratePrompt} className="btn-primary">
            프롬프트 생성
            <svg className="w-5 h-5 ml-2 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>

      {/* 제품 상세 모달 */}
      <ProductDetailModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        product={selectedProduct}
        type={selectedProductType}
      />
    </div>
  );
}
