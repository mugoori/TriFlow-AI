// 제품 정보
export interface ProductInfo {
  name: string;
  formulation_type: string;
  target_cost?: number;
  target_weight?: number;
  description?: string;
}

// 원료 요구사항
export interface IngredientRequirement {
  ingredient_name: string;
  min_ratio?: number;
  max_ratio?: number;
  is_required: boolean;
  notes?: string;
}

// 제약 조건
export interface Constraints {
  max_ingredients?: number;
  avoid_ingredients?: string[];
  regulatory_requirements?: string[];
  quality_requirements?: string[];
}

// 배합비 상세
export interface RecipeDetail {
  ingredient_name: string;
  ratio: number;
  amount_per_unit?: number;
  purpose?: string;
}

// 배합비 원료 (Claude 파싱 결과)
export interface RecipeIngredient {
  no: number;
  name: string;
  ratio: number;
  role: string;
}

// 배합비 옵션 (3가지 중 하나)
export interface RecipeOption {
  option_type: 'cost_optimized' | 'premium' | 'balanced';
  title: string;
  ingredients: RecipeIngredient[];
  total_ratio: number;
  estimated_cost?: string;
  notes?: string;
  quality?: string;
  summary?: string;
}

// AI 배합비 생성 응답
export interface RecipeGenerationResponse {
  recipe_options: RecipeOption[];
  raw_response?: string;
  generated_at: string;
  product_name?: string;
  formulation_type?: string;
  error?: string;
}

// 프롬프트 요청
export interface PromptRequest {
  product_info: ProductInfo;
  ingredient_requirements: IngredientRequirement[];
  constraints: Constraints;
  similar_products_api?: SimilarProductAPI[];
}

// 프롬프트 응답
export interface PromptResponse {
  prompt: string;
  similar_products_internal: RecipeMetadata[];
  similar_products_api: SimilarProductAPI[];
  generated_at: string;
}

// 레시피 메타데이터 (내부 DB)
export interface RecipeMetadata {
  id: number;
  filename: string;
  product_name: string;
  company_name?: string;
  formulation_type?: string;
  created_date?: string;
  ingredient_count?: number;
}

// 유사 제품 (공공 API)
export interface SimilarProductAPI {
  product_name: string;
  company_name: string;
  raw_materials: string;
  shelf_life?: string;
  packing_material?: string;
  source: string;
  formulation_type?: string;
  functional_ingredients?: string;
  other_ingredients?: string;
  functionality?: string;
  intake_method?: string;
  report_no?: string;
  caution?: string;
  standard?: string;
  match_count?: number;
}

// 검색 결과
export interface SearchResult {
  internal_results: RecipeMetadata[];
  api_results: SimilarProductAPI[];
  query: string;
  searched_at: string;
}

// 기존 레시피 상세 (DB에서 조회)
export interface HistoricalRecipeIngredient {
  ingredient_name: string;
  ratio: number;
  amount?: number;
  purpose?: string;
}

export interface HistoricalRecipe {
  metadata: RecipeMetadata;
  details: HistoricalRecipeIngredient[];
}

// RecipesPage 상세 보기용 통합 타입
export interface HistoricalRecipeDetail {
  type: 'historical';
  metadata: RecipeMetadata;
  details: HistoricalRecipeIngredient[];
}

export interface AIRecipeDetail extends AIGeneratedRecipe {
  type: 'ai_generated';
}

export type SelectedRecipeDetail = HistoricalRecipeDetail | AIRecipeDetail | null;

// 피드백
export interface Feedback {
  recipe_id: number;
  rating: number;
  comment?: string;
  created_at: string;
}

// ===================================
// AI 생성 레시피 관련 타입
// ===================================

// AI 생성 레시피 저장 요청
export interface AIGeneratedRecipeCreate {
  product_name: string;
  formulation_type?: string;
  option_type: string;  // 'cost_optimized', 'premium', 'balanced', 'custom'
  title?: string;
  ingredients: RecipeIngredient[];
  total_ratio?: number;
  estimated_cost?: string;
  notes?: string;
  quality?: string;
  summary?: string;
  source_type?: string;
  source_reference?: string;
  external_id?: string;
}

// AI 생성 레시피 응답
export interface AIGeneratedRecipe {
  recipe_id: string;
  tenant_id: string;
  product_name: string;
  formulation_type?: string;
  option_type: string;
  title?: string;
  ingredients: RecipeIngredient[];
  total_ratio?: number;
  estimated_cost?: string;
  notes?: string;
  quality?: string;
  summary?: string;
  source_type: string;
  source_reference?: string;
  external_id?: string;
  status: string;
  version: number;
  created_at: string;
  updated_at: string;
}

// 레시피 피드백 요청
export interface RecipeFeedbackCreate {
  rating: number;
  comment?: string;
  feedback_type?: string;
}

// 레시피 피드백 응답
export interface RecipeFeedback {
  feedback_id: string;
  recipe_id: string;
  rating: number;
  comment?: string;
  feedback_type?: string;
  created_at: string;
}

// 통합 레시피 (기존 DB + AI 생성)
export interface UnifiedRecipe {
  recipe_id: string;
  tenant_id: string;
  product_name: string;
  formulation_type?: string;
  option_type: string;
  ingredient_count: number;
  source_type: string;  // 'db_existing', 'ai_generated', 'mes_imported', 'erp_imported'
  source_reference?: string;
  status: string;
  created_at?: string;
  created_by?: string;
}

// 통합 레시피 목록 응답
export interface UnifiedRecipeListResponse {
  recipes: UnifiedRecipe[];
  total_count: number;
  page: number;
  page_size: number;
}

// API 응답 래퍼
export interface APIResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  timestamp: string;
}

// 앱 상태
export interface AppState {
  currentStep: 'input' | 'search' | 'prompt' | 'result';
  productInfo: ProductInfo | null;
  ingredientRequirements: IngredientRequirement[];
  constraints: Constraints;
  searchResults: SearchResult | null;
  generatedPrompt: string | null;
  isLoading: boolean;
  error: string | null;
}
