import { useState, useEffect } from 'react';
import type { SimilarProductAPI, RecipeMetadata } from '../types';

interface ProductDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  product: SimilarProductAPI | RecipeMetadata | null;
  type: 'api' | 'internal';
  recipeDetails?: Array<{ ingredient_name: string; ratio: number; amount?: number }>;
}

export default function ProductDetailModal({
  isOpen,
  onClose,
  product,
  type,
  recipeDetails,
}: ProductDetailModalProps) {
  const [loading, setLoading] = useState(false);
  const [details, setDetails] = useState<Array<{ ingredient_name: string; ratio: number; amount?: number }> | null>(null);

  useEffect(() => {
    if (isOpen && type === 'internal' && product && 'id' in product) {
      loadInternalDetails(product.id);
    } else if (recipeDetails) {
      setDetails(recipeDetails);
    }
  }, [isOpen, type, product, recipeDetails]);

  const loadInternalDetails = async (id: number) => {
    setLoading(true);
    try {
      const response = await fetch(`/api/recipes/${id}`);
      if (response.ok) {
        const data = await response.json();
        setDetails(data.details || []);
      }
    } catch (error) {
      console.error('상세 정보 로드 실패:', error);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen || !product) return null;

  const isApiProduct = type === 'api';
  const apiProduct = isApiProduct ? (product as SimilarProductAPI) : null;
  const internalProduct = !isApiProduct ? (product as RecipeMetadata) : null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative bg-white rounded-xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-hidden">
          {/* Header */}
          <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-gray-900">
                {isApiProduct ? apiProduct?.product_name : internalProduct?.product_name}
              </h2>
              <p className="text-sm text-gray-500">
                {isApiProduct ? apiProduct?.company_name : internalProduct?.company_name || '한국바이오팜'}
              </p>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-100 rounded-full transition-colors"
            >
              <svg className="w-6 h-6 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Content */}
          <div className="p-6 overflow-y-auto max-h-[calc(90vh-80px)]">
            {isApiProduct && apiProduct ? (
              // API 제품 상세 정보
              <div className="space-y-6">
                {/* 기본 정보 */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-gray-50 p-4 rounded-lg">
                    <p className="text-sm text-gray-500 mb-1">제형</p>
                    <p className="font-medium">{apiProduct.formulation_type || '-'}</p>
                  </div>
                  <div className="bg-gray-50 p-4 rounded-lg">
                    <p className="text-sm text-gray-500 mb-1">소비기한</p>
                    <p className="font-medium">{apiProduct.shelf_life || '-'}</p>
                  </div>
                </div>

                {/* 원재료 */}
                <div className="bg-blue-50 p-4 rounded-lg">
                  <h3 className="font-semibold text-blue-900 mb-2 flex items-center gap-2">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                    </svg>
                    원재료명
                  </h3>
                  <p className="text-sm text-gray-700 leading-relaxed">
                    {apiProduct.raw_materials || '-'}
                  </p>
                </div>

                {/* 기능성 원료 */}
                {apiProduct.functional_ingredients && (
                  <div className="bg-green-50 p-4 rounded-lg">
                    <h3 className="font-semibold text-green-900 mb-2 flex items-center gap-2">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      기능성 원료
                    </h3>
                    <p className="text-sm text-gray-700 leading-relaxed">
                      {apiProduct.functional_ingredients}
                    </p>
                  </div>
                )}

                {/* 기타 원료 */}
                {apiProduct.other_ingredients && (
                  <div className="bg-gray-50 p-4 rounded-lg">
                    <h3 className="font-semibold text-gray-700 mb-2">기타 원료</h3>
                    <p className="text-sm text-gray-600 leading-relaxed">
                      {apiProduct.other_ingredients}
                    </p>
                  </div>
                )}

                {/* 기능성 */}
                {apiProduct.functionality && (
                  <div className="bg-purple-50 p-4 rounded-lg">
                    <h3 className="font-semibold text-purple-900 mb-2 flex items-center gap-2">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                      주된 기능성
                    </h3>
                    <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">
                      {apiProduct.functionality}
                    </p>
                  </div>
                )}

                {/* 섭취 방법 */}
                {apiProduct.intake_method && (
                  <div className="bg-orange-50 p-4 rounded-lg">
                    <h3 className="font-semibold text-orange-900 mb-2">섭취 방법</h3>
                    <p className="text-sm text-gray-700">{apiProduct.intake_method}</p>
                  </div>
                )}

                {/* 주의사항 */}
                {apiProduct.caution && (
                  <div className="bg-red-50 p-4 rounded-lg">
                    <h3 className="font-semibold text-red-900 mb-2 flex items-center gap-2">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                      </svg>
                      섭취 시 주의사항
                    </h3>
                    <p className="text-sm text-gray-700 whitespace-pre-line">{apiProduct.caution}</p>
                  </div>
                )}

                {/* 품목제조번호 */}
                {apiProduct.report_no && (
                  <div className="text-xs text-gray-400 pt-2 border-t">
                    품목제조번호: {apiProduct.report_no}
                  </div>
                )}
              </div>
            ) : (
              // 내부 DB 제품 상세 정보
              <div className="space-y-6">
                {/* 기본 정보 */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-gray-50 p-4 rounded-lg">
                    <p className="text-sm text-gray-500 mb-1">제형</p>
                    <p className="font-medium">{internalProduct?.formulation_type || '-'}</p>
                  </div>
                  <div className="bg-gray-50 p-4 rounded-lg">
                    <p className="text-sm text-gray-500 mb-1">원료 수</p>
                    <p className="font-medium">{internalProduct?.ingredient_count || '-'}종</p>
                  </div>
                </div>

                {/* 배합비 상세 */}
                <div className="bg-biopharm-green/10 p-4 rounded-lg">
                  <h3 className="font-semibold text-biopharm-green mb-4 flex items-center gap-2">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                    </svg>
                    배합비 상세
                  </h3>

                  {loading ? (
                    <div className="flex items-center justify-center py-8">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-biopharm-green"></div>
                      <span className="ml-3 text-gray-500">로딩 중...</span>
                    </div>
                  ) : details && details.length > 0 ? (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="bg-biopharm-green/20">
                            <th className="text-left py-2 px-3 font-medium">원료명</th>
                            <th className="text-right py-2 px-3 font-medium">배합비 (%)</th>
                            <th className="text-right py-2 px-3 font-medium">함량 (mg)</th>
                          </tr>
                        </thead>
                        <tbody>
                          {details.map((item, index) => (
                            <tr key={index} className="border-b border-gray-200 last:border-0">
                              <td className="py-2 px-3">{item.ingredient_name}</td>
                              <td className="text-right py-2 px-3">{item.ratio?.toFixed(2) || '-'}</td>
                              <td className="text-right py-2 px-3">{item.amount?.toFixed(2) || '-'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="text-center py-8 text-gray-500">
                      <p>상세 배합비 정보는 Claude Desktop에서</p>
                      <p>SQL MCP를 통해 조회할 수 있습니다.</p>
                      <p className="mt-2 text-sm text-gray-400">
                        파일명: {internalProduct?.filename}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="sticky bottom-0 bg-gray-50 border-t border-gray-200 px-6 py-4 flex justify-end gap-3">
            <button
              onClick={onClose}
              className="btn-secondary"
            >
              닫기
            </button>
            {isApiProduct && (
              <button
                onClick={() => {
                  // 프롬프트에 이 제품 정보 포함 기능 (향후 구현)
                  onClose();
                }}
                className="btn-primary"
              >
                프롬프트에 반영
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
