import type {
  PromptRequest,
  PromptResponse,
  RecipeMetadata,
  SearchResult,
  SimilarProductAPI,
  HistoricalRecipe,
  Feedback
} from '../types';

const API_BASE = '/api';

// 공통 fetch 헬퍼
async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
    },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP error! status: ${response.status}`);
  }

  return response.json();
}

// =====================
// 레시피 관련 API
// =====================

// 모든 레시피 메타데이터 조회
export async function getAllRecipes(
  skip = 0,
  limit = 100,
  formulationType?: string
): Promise<RecipeMetadata[]> {
  const params = new URLSearchParams({
    skip: skip.toString(),
    limit: limit.toString(),
  });
  if (formulationType) {
    params.append('formulation_type', formulationType);
  }
  return fetchAPI<RecipeMetadata[]>(`/recipes?${params}`);
}

// 특정 레시피 상세 조회
export async function getRecipeDetail(recipeId: number): Promise<HistoricalRecipe> {
  return fetchAPI<HistoricalRecipe>(`/recipes/${recipeId}`);
}

// 제형 타입 목록 조회
export async function getFormulationTypes(): Promise<string[]> {
  const data = await fetchAPI<{ formulation_type: string; count: number }[]>('/recipes/types');
  return data.map(item => item.formulation_type);
}

// =====================
// 원료 관련 API
// =====================

// 모든 원료 목록 조회
export async function getAllMaterials(): Promise<string[]> {
  return fetchAPI<string[]>('/ingredients/materials');
}

// 원료 검색 (자동완성용)
export async function searchMaterials(query: string): Promise<string[]> {
  if (!query || query.length < 1) return [];
  const params = new URLSearchParams({ q: query });
  return fetchAPI<string[]>(`/ingredients/search?${params}`);
}

// 원료로 레시피 검색
export async function searchByIngredients(ingredients: string[]): Promise<RecipeMetadata[]> {
  return fetchAPI<RecipeMetadata[]>('/ingredients/search', {
    method: 'POST',
    body: JSON.stringify({ ingredients }),
  });
}

// =====================
// 검색 API (내부 + 외부)
// =====================

// 통합 검색 (내부 DB + 공공 API)
export async function searchProducts(
  query: string,
  searchInternal = true,
  searchApi = true
): Promise<SearchResult> {
  const params = new URLSearchParams({
    query,
    search_internal: searchInternal.toString(),
    search_api: searchApi.toString(),
  });
  return fetchAPI<SearchResult>(`/search?${params}`);
}

// 공공 API만 검색
export async function searchFoodSafetyAPI(productName: string): Promise<SimilarProductAPI[]> {
  const params = new URLSearchParams({ product_name: productName });
  return fetchAPI<SimilarProductAPI[]>(`/search/foodsafety?${params}`);
}

// =====================
// 프롬프트 생성 API
// =====================

// 프롬프트 생성
export async function generatePrompt(request: PromptRequest): Promise<PromptResponse> {
  return fetchAPI<PromptResponse>('/prompt/generate', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

// =====================
// 피드백 API
// =====================

// 피드백 저장
export async function saveFeedback(feedback: Omit<Feedback, 'created_at'>): Promise<{ success: boolean }> {
  return fetchAPI('/feedback', {
    method: 'POST',
    body: JSON.stringify(feedback),
  });
}

// =====================
// 유틸리티
// =====================

// 클립보드에 복사
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (err) {
    console.error('Failed to copy to clipboard:', err);
    return false;
  }
}
