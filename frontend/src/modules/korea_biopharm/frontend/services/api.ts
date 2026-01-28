import type {
  PromptRequest,
  PromptResponse,
  RecipeMetadata,
  SearchResult,
  SimilarProductAPI,
  HistoricalRecipe,
  Feedback
} from '../types';

const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000') + '/api/v1/korea-biopharm';

// 공통 fetch 헬퍼
async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  // TriFlow 인증 토큰 가져오기
  const token = localStorage.getItem('triflow_access_token');

  // 헤더 병합 (options.headers가 있어도 Authorization 유지)
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    ...(options?.headers || {}),
  };

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
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

// AI 배합비 자동 생성
export async function generateAndExecuteRecipe(
  data: PromptRequest
): Promise<any> {
  return fetchAPI('/prompt/generate-recipe', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// AI 배합비 자동 생성 (타입 안전)
import type {
  RecipeGenerationResponse,
  AIGeneratedRecipeCreate,
  AIGeneratedRecipe,
  RecipeFeedbackCreate,
  RecipeFeedback,
  UnifiedRecipeListResponse
} from '../types';

export async function generateRecipe(
  data: PromptRequest
): Promise<RecipeGenerationResponse> {
  return fetchAPI<RecipeGenerationResponse>('/prompt/generate-recipe', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// =====================
// AI 생성 레시피 API
// =====================

// AI 레시피 저장
export async function saveAIRecipe(
  recipe: AIGeneratedRecipeCreate
): Promise<AIGeneratedRecipe> {
  return fetchAPI<AIGeneratedRecipe>('/recipes/ai-generated', {
    method: 'POST',
    body: JSON.stringify(recipe),
  });
}

// AI 레시피 목록 조회
export async function getAIRecipes(
  page = 1,
  pageSize = 20,
  status?: string,
  sourceType?: string
): Promise<{ recipes: AIGeneratedRecipe[]; total_count: number; page: number; page_size: number }> {
  const params = new URLSearchParams({
    page: page.toString(),
    page_size: pageSize.toString(),
  });
  if (status) params.append('status', status);
  if (sourceType) params.append('source_type', sourceType);
  return fetchAPI(`/recipes/ai-generated?${params}`);
}

// AI 레시피 상세 조회
export async function getAIRecipe(recipeId: string): Promise<AIGeneratedRecipe> {
  return fetchAPI<AIGeneratedRecipe>(`/recipes/ai-generated/${recipeId}`);
}

// AI 레시피 삭제
export async function deleteAIRecipe(recipeId: string): Promise<{ message: string; recipe_id: string }> {
  return fetchAPI(`/recipes/ai-generated/${recipeId}`, {
    method: 'DELETE',
  });
}

// AI 레시피 상태 변경
export async function updateAIRecipeStatus(
  recipeId: string,
  status: string
): Promise<AIGeneratedRecipe> {
  return fetchAPI<AIGeneratedRecipe>(`/recipes/ai-generated/${recipeId}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  });
}

// =====================
// 레시피 피드백 API
// =====================

// 피드백 저장 (AI 레시피용)
export async function saveAIRecipeFeedback(
  recipeId: string,
  feedback: RecipeFeedbackCreate
): Promise<RecipeFeedback> {
  return fetchAPI<RecipeFeedback>(`/recipes/ai-generated/${recipeId}/feedback`, {
    method: 'POST',
    body: JSON.stringify(feedback),
  });
}

// 피드백 조회 (AI 레시피용)
export async function getAIRecipeFeedback(recipeId: string): Promise<RecipeFeedback[]> {
  return fetchAPI<RecipeFeedback[]>(`/recipes/ai-generated/${recipeId}/feedback`);
}

// =====================
// 통합 레시피 API
// =====================

// 통합 레시피 목록 조회
export async function getUnifiedRecipes(
  page = 1,
  pageSize = 20,
  options?: {
    sourceType?: string;
    status?: string;
    formulationType?: string;
    query?: string;
  }
): Promise<UnifiedRecipeListResponse> {
  const params = new URLSearchParams({
    page: page.toString(),
    page_size: pageSize.toString(),
  });
  if (options?.sourceType) params.append('source_type', options.sourceType);
  if (options?.status) params.append('status', options.status);
  if (options?.formulationType) params.append('formulation_type', options.formulationType);
  if (options?.query) params.append('q', options.query);
  return fetchAPI<UnifiedRecipeListResponse>(`/recipes/unified?${params}`);
}
