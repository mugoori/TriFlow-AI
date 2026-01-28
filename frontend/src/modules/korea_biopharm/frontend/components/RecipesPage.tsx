import { useState, useEffect } from 'react';
import { getUnifiedRecipes, getAIRecipe, getRecipeDetail, deleteAIRecipe, updateAIRecipeStatus } from '../services/api';
import type {
  UnifiedRecipe,
  RecipeIngredient,
  AIRecipeDetail,
  SelectedRecipeDetail
} from '../types';

interface RecipesPageProps {
  onBack?: () => void;
}

export default function RecipesPage({ onBack }: RecipesPageProps) {
  const [recipes, setRecipes] = useState<UnifiedRecipe[]>([]);
  const [selectedRecipe, setSelectedRecipe] = useState<SelectedRecipeDetail>(null);
  const [selectedUnifiedId, setSelectedUnifiedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [pageSize] = useState(20);

  // Delete confirmation toast
  const [deleteConfirm, setDeleteConfirm] = useState<{ show: boolean; recipeId: string | null }>({
    show: false,
    recipeId: null,
  });
  const [deleting, setDeleting] = useState(false);

  // Filters
  const [sourceFilter, setSourceFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');

  const loadRecipes = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getUnifiedRecipes(page, pageSize, {
        sourceType: sourceFilter || undefined,
        status: statusFilter || undefined,
        query: searchQuery || undefined,
      });
      setRecipes(result.recipes);
      setTotalCount(result.total_count);
    } catch (err) {
      setError(err instanceof Error ? err.message : '레시피 목록을 불러오는데 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRecipes();
  }, [page, sourceFilter, statusFilter]);

  const handleSearch = () => {
    setPage(1);
    loadRecipes();
  };

  const handleSelectRecipe = async (recipe: UnifiedRecipe) => {
    setDetailLoading(true);
    setSelectedUnifiedId(recipe.recipe_id);
    setError(null);

    try {
      if (recipe.source_type === 'ai_generated') {
        // AI 생성 레시피 상세 조회
        const detail = await getAIRecipe(recipe.recipe_id);
        setSelectedRecipe({ ...detail, type: 'ai_generated' });
      } else {
        // 기존 DB 레시피 상세 조회
        const recipeId = parseInt(recipe.recipe_id, 10);
        const detail = await getRecipeDetail(recipeId);
        setSelectedRecipe({
          type: 'historical',
          metadata: detail.metadata ?? {
            id: recipeId,
            filename: '',
            product_name: recipe.product_name,
            formulation_type: recipe.formulation_type,
          },
          details: detail.details ?? [],
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '상세 정보를 불러오는데 실패했습니다.');
      setSelectedRecipe(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleDelete = (recipeId: string) => {
    setDeleteConfirm({ show: true, recipeId });
  };

  const confirmDelete = async () => {
    if (!deleteConfirm.recipeId) return;

    setDeleting(true);
    try {
      await deleteAIRecipe(deleteConfirm.recipeId);
      setSelectedRecipe(null);
      setSelectedUnifiedId(null);
      setDeleteConfirm({ show: false, recipeId: null });
      loadRecipes();
    } catch (err) {
      setError(err instanceof Error ? err.message : '삭제에 실패했습니다.');
    } finally {
      setDeleting(false);
    }
  };

  const cancelDelete = () => {
    setDeleteConfirm({ show: false, recipeId: null });
  };

  const handleStatusChange = async (recipeId: string, newStatus: string) => {
    try {
      await updateAIRecipeStatus(recipeId, newStatus);
      if (selectedRecipe && selectedRecipe.type === 'ai_generated' && selectedRecipe.recipe_id === recipeId) {
        setSelectedRecipe({ ...selectedRecipe, status: newStatus });
      }
      loadRecipes();
    } catch (err) {
      setError(err instanceof Error ? err.message : '상태 변경에 실패했습니다.');
    }
  };

  const getSourceBadge = (sourceType: string) => {
    switch (sourceType) {
      case 'db_existing':
        return <span className="px-2 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-700">DB</span>;
      case 'ai_generated':
        return <span className="px-2 py-1 text-xs font-medium rounded-full bg-blue-100 text-blue-700">AI</span>;
      case 'mes_imported':
        return <span className="px-2 py-1 text-xs font-medium rounded-full bg-green-100 text-green-700">MES</span>;
      case 'erp_imported':
        return <span className="px-2 py-1 text-xs font-medium rounded-full bg-purple-100 text-purple-700">ERP</span>;
      default:
        return <span className="px-2 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-500">{sourceType}</span>;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'draft':
        return <span className="px-2 py-1 text-xs font-medium rounded-full bg-yellow-100 text-yellow-700">초안</span>;
      case 'approved':
        return <span className="px-2 py-1 text-xs font-medium rounded-full bg-green-100 text-green-700">승인됨</span>;
      case 'production':
        return <span className="px-2 py-1 text-xs font-medium rounded-full bg-blue-100 text-blue-700">생산중</span>;
      case 'archived':
        return <span className="px-2 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-500">보관됨</span>;
      default:
        return <span className="px-2 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-500">{status}</span>;
    }
  };

  const totalPages = Math.ceil(totalCount / pageSize);

  // 상세 정보 렌더링
  const renderRecipeDetail = () => {
    if (detailLoading) {
      return (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-biopharm-green"></div>
        </div>
      );
    }

    if (!selectedRecipe) {
      return (
        <div className="text-center py-12 text-gray-500">
          <svg className="w-12 h-12 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
          </svg>
          <p>레시피를 선택하세요</p>
          <p className="text-sm mt-1">레시피의 상세 배합비 정보를 확인할 수 있습니다.</p>
        </div>
      );
    }

    if (selectedRecipe.type === 'historical') {
      // 기존 DB 레시피 상세 표시
      const { metadata, details } = selectedRecipe;
      return (
        <div className="space-y-6">
          {/* Basic Info */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              {getSourceBadge('db_existing')}
              {getStatusBadge('approved')}
            </div>
            <h4 className="text-lg font-bold text-gray-900">{metadata.product_name}</h4>
            {metadata.company_name && (
              <p className="text-gray-600">{metadata.company_name}</p>
            )}
            <p className="text-sm text-gray-500 mt-1">
              제형: {metadata.formulation_type || '-'} | 원료 {metadata.ingredient_count || details.length}종
            </p>
          </div>

          {/* Ingredients Table */}
          <div>
            <h5 className="font-medium text-gray-700 mb-2">배합비</h5>
            <div className="overflow-x-auto border rounded-lg">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">No</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">원료명</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-gray-500">비율 (%)</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {details.map((ing, idx) => (
                    <tr key={idx}>
                      <td className="px-3 py-2 text-sm text-gray-900">{idx + 1}</td>
                      <td className="px-3 py-2 text-sm font-medium text-gray-900">{ing.ingredient_name}</td>
                      <td className="px-3 py-2 text-sm text-right text-gray-900">{ing.ratio.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="bg-gray-50">
                  <tr>
                    <td colSpan={2} className="px-3 py-2 text-sm font-medium text-gray-700">합계</td>
                    <td className="px-3 py-2 text-sm font-medium text-right text-gray-700">
                      {details.reduce((sum, ing) => sum + ing.ratio, 0).toFixed(2)}%
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>

          {/* Meta Info */}
          <div className="text-xs text-gray-400 pt-4 border-t">
            <p>파일명: {metadata.filename}</p>
            {metadata.created_date && (
              <p>등록일: {new Date(metadata.created_date).toLocaleDateString('ko-KR')}</p>
            )}
          </div>
        </div>
      );
    }

    // AI 생성 레시피 상세 표시
    const recipe = selectedRecipe as AIRecipeDetail;
    return (
      <div className="space-y-6">
        {/* Basic Info */}
        <div>
          <div className="flex items-center gap-2 mb-2">
            {getSourceBadge(recipe.source_type)}
            {getStatusBadge(recipe.status)}
          </div>
          <h4 className="text-lg font-bold text-gray-900">{recipe.product_name}</h4>
          {recipe.title && <p className="text-gray-600">{recipe.title}</p>}
          <p className="text-sm text-gray-500 mt-1">
            제형: {recipe.formulation_type || '-'}
          </p>
        </div>

        {/* Ingredients Table */}
        <div>
          <h5 className="font-medium text-gray-700 mb-2">배합비</h5>
          <div className="overflow-x-auto border rounded-lg">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">No</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">원료명</th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-gray-500">비율 (%)</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">역할</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {(recipe.ingredients as RecipeIngredient[]).map((ing, idx) => (
                  <tr key={idx}>
                    <td className="px-3 py-2 text-sm">{ing.no}</td>
                    <td className="px-3 py-2 text-sm font-medium">{ing.name}</td>
                    <td className="px-3 py-2 text-sm text-right">{ing.ratio.toFixed(2)}</td>
                    <td className="px-3 py-2 text-sm text-gray-600">{ing.role}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="bg-gray-50">
                <tr>
                  <td colSpan={3} className="px-3 py-2 text-sm font-medium text-gray-700">합계</td>
                  <td className="px-3 py-2 text-sm font-medium text-right text-gray-700">
                    {recipe.total_ratio?.toFixed(2) || (recipe.ingredients as RecipeIngredient[]).reduce((sum, ing) => sum + ing.ratio, 0).toFixed(2)}%
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>

        {/* Additional Info */}
        {recipe.estimated_cost && (
          <div>
            <h5 className="font-medium text-gray-700 mb-1">예상 원가</h5>
            <p className="text-gray-900">{recipe.estimated_cost}</p>
          </div>
        )}

        {recipe.notes && (
          <div>
            <h5 className="font-medium text-gray-700 mb-1">주의사항</h5>
            <p className="text-gray-900 text-sm whitespace-pre-wrap">{recipe.notes}</p>
          </div>
        )}

        {recipe.summary && (
          <div>
            <h5 className="font-medium text-gray-700 mb-1">요약</h5>
            <p className="text-gray-900 text-sm whitespace-pre-wrap">{recipe.summary}</p>
          </div>
        )}

        {/* Status Change (AI only) */}
        <div className="border-t pt-4">
          <h5 className="font-medium text-gray-700 mb-2">상태 변경</h5>
          <div className="flex flex-wrap gap-2">
            {['draft', 'approved', 'production', 'archived'].map((status) => (
              <button
                key={status}
                onClick={() => handleStatusChange(recipe.recipe_id, status)}
                disabled={recipe.status === status}
                className={`
                  px-3 py-1 text-sm rounded-lg border transition-colors
                  ${recipe.status === status
                    ? 'bg-biopharm-green text-white border-biopharm-green'
                    : 'border-gray-300 hover:border-biopharm-green hover:text-biopharm-green'}
                `}
              >
                {status === 'draft' && '초안'}
                {status === 'approved' && '승인'}
                {status === 'production' && '생산'}
                {status === 'archived' && '보관'}
              </button>
            ))}
          </div>
        </div>

        {/* Actions (AI only) */}
        <div className="flex gap-2 pt-4 border-t">
          <button
            onClick={() => handleDelete(recipe.recipe_id)}
            className="btn-secondary text-red-600 hover:bg-red-50 flex-1"
          >
            <svg className="w-4 h-4 mr-2 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
            삭제
          </button>
        </div>

        {/* Meta Info */}
        <div className="text-xs text-gray-400 pt-4 border-t">
          <p>생성일: {new Date(recipe.created_at).toLocaleString('ko-KR')}</p>
          <p>수정일: {new Date(recipe.updated_at).toLocaleString('ko-KR')}</p>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          {onBack && (
            <button onClick={onBack} className="p-2 hover:bg-gray-100 rounded-lg">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
          )}
          <h2 className="text-xl font-bold text-gray-900">내 레시피</h2>
        </div>
        <button onClick={loadRecipes} className="btn-secondary flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          새로고침
        </button>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex flex-wrap gap-4">
          {/* 검색 */}
          <div className="flex-1 min-w-[200px]">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="제품명 검색..."
              className="input-field"
            />
          </div>

          {/* 소스 필터 */}
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="input-field w-40"
          >
            <option value="">전체 소스</option>
            <option value="db_existing">기존 DB</option>
            <option value="ai_generated">AI 생성</option>
            <option value="mes_imported">MES 연동</option>
            <option value="erp_imported">ERP 연동</option>
          </select>

          {/* 상태 필터 */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="input-field w-36"
          >
            <option value="">전체 상태</option>
            <option value="draft">초안</option>
            <option value="approved">승인됨</option>
            <option value="production">생산중</option>
            <option value="archived">보관됨</option>
          </select>

          <button onClick={handleSearch} className="btn-primary">
            검색
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
          {error}
          <button onClick={() => setError(null)} className="ml-2 text-red-500 hover:text-red-700">
            닫기
          </button>
        </div>
      )}

      {/* Content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recipe List */}
        <div className="card">
          <h3 className="font-semibold text-gray-700 mb-4">
            레시피 목록 ({totalCount}건)
          </h3>

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-biopharm-green"></div>
              <span className="ml-3 text-gray-500">로딩 중...</span>
            </div>
          ) : recipes.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <svg className="w-12 h-12 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p>레시피가 없습니다.</p>
              <p className="text-sm mt-1">새 배합비를 생성해보세요!</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-[600px] overflow-y-auto">
              {recipes.map((recipe) => (
                <button
                  key={recipe.recipe_id}
                  onClick={() => handleSelectRecipe(recipe)}
                  className={`
                    w-full text-left p-4 rounded-lg border transition-all
                    ${selectedUnifiedId === recipe.recipe_id
                      ? 'border-biopharm-green bg-biopharm-green/5'
                      : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'}
                  `}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        {getSourceBadge(recipe.source_type)}
                        {getStatusBadge(recipe.status)}
                      </div>
                      <h4 className="font-medium text-gray-900">{recipe.product_name}</h4>
                      <p className="text-sm text-gray-500 mt-1">
                        {recipe.formulation_type || '-'} | {recipe.ingredient_count}종
                      </p>
                    </div>
                    <div className="text-xs text-gray-400">
                      {recipe.created_at
                        ? new Date(recipe.created_at).toLocaleDateString('ko-KR')
                        : '-'}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-4 pt-4 border-t">
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1}
                className="p-2 rounded hover:bg-gray-100 disabled:opacity-50"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
              <span className="text-sm text-gray-600">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage(Math.min(totalPages, page + 1))}
                disabled={page === totalPages}
                className="p-2 rounded hover:bg-gray-100 disabled:opacity-50"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          )}
        </div>

        {/* Recipe Detail */}
        <div className="card">
          <h3 className="font-semibold text-gray-700 mb-4">상세 정보</h3>
          {renderRecipeDetail()}
        </div>
      </div>

      {/* Delete Confirmation Toast */}
      {deleteConfirm.show && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 animate-in slide-in-from-bottom-4 fade-in duration-200">
          <div className="bg-white rounded-xl shadow-2xl border border-gray-200 p-4 flex items-center gap-4 min-w-[320px]">
            <div className="flex-shrink-0 w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
              <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-900">레시피를 삭제할까요?</p>
              <p className="text-xs text-gray-500 mt-0.5">삭제된 레시피는 복구할 수 없습니다.</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={cancelDelete}
                disabled={deleting}
                className="px-3 py-1.5 text-sm font-medium text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors"
              >
                취소
              </button>
              <button
                onClick={confirmDelete}
                disabled={deleting}
                className="px-3 py-1.5 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors disabled:opacity-50 flex items-center gap-1"
              >
                {deleting ? (
                  <>
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    삭제 중...
                  </>
                ) : (
                  '삭제'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
