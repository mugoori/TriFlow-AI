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

// 배합비 옵션 (3가지 중 하나)
export interface RecipeOption {
  option_type: 'cost_optimized' | 'premium' | 'balanced';
  option_name: string;
  recipe_details: RecipeDetail[];
  estimated_cost: number;
  manufacturing_notes: string[];
  expected_quality: {
    score: number;
    description: string;
  };
  pros: string[];
  cons: string[];
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

// 기존 레시피 상세
export interface HistoricalRecipe {
  id: number;
  filename: string;
  data: Record<string, unknown>;
}

// 피드백
export interface Feedback {
  recipe_id: number;
  rating: number;
  comment?: string;
  created_at: string;
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
