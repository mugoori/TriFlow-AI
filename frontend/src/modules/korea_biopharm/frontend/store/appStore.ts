import { create } from 'zustand';
import type {
  ProductInfo,
  IngredientRequirement,
  Constraints,
  SearchResult,
  RecipeGenerationResponse,
} from '../types';

type Step = 'input' | 'search' | 'prompt' | 'result';

interface AppStore {
  // 현재 단계
  currentStep: Step;
  setCurrentStep: (step: Step) => void;

  // 제품 정보
  productInfo: ProductInfo | null;
  setProductInfo: (info: ProductInfo) => void;

  // 원료 요구사항
  ingredientRequirements: IngredientRequirement[];
  setIngredientRequirements: (reqs: IngredientRequirement[]) => void;
  addIngredientRequirement: (req: IngredientRequirement) => void;
  removeIngredientRequirement: (index: number) => void;

  // 제약 조건
  constraints: Constraints;
  setConstraints: (constraints: Constraints) => void;

  // 검색 결과
  searchResults: SearchResult | null;
  setSearchResults: (results: SearchResult) => void;

  // 생성된 프롬프트
  generatedPrompt: string | null;
  setGeneratedPrompt: (prompt: string) => void;

  // AI 배합비 생성 결과
  recipeResult: RecipeGenerationResponse | null;
  setRecipeResult: (result: RecipeGenerationResponse) => void;

  // 로딩/에러 상태
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
  error: string | null;
  setError: (error: string | null) => void;

  // 초기화
  reset: () => void;
}

const initialState = {
  currentStep: 'input' as Step,
  productInfo: null,
  ingredientRequirements: [],
  constraints: {},
  searchResults: null,
  generatedPrompt: null,
  recipeResult: null,
  isLoading: false,
  error: null,
};

export const useAppStore = create<AppStore>((set) => ({
  ...initialState,

  setCurrentStep: (step) => set({ currentStep: step, error: null }),

  setProductInfo: (info) => set({ productInfo: info }),

  setIngredientRequirements: (reqs) => set({ ingredientRequirements: reqs }),

  addIngredientRequirement: (req) =>
    set((state) => ({
      ingredientRequirements: [...state.ingredientRequirements, req],
    })),

  removeIngredientRequirement: (index) =>
    set((state) => ({
      ingredientRequirements: state.ingredientRequirements.filter((_, i) => i !== index),
    })),

  setConstraints: (constraints) => set({ constraints }),

  setSearchResults: (results) => set({ searchResults: results }),

  setGeneratedPrompt: (prompt) => set({ generatedPrompt: prompt }),

  setRecipeResult: (result) => set({ recipeResult: result }),

  setIsLoading: (loading) => set({ isLoading: loading }),

  setError: (error) => {
    // 디버깅: 비정상 타입 감지
    if (error !== null && typeof error !== 'string') {
      console.warn('[DEBUG] setError received non-string:', error, 'Type:', typeof error);
    }
    // 문자열이 아닌 값은 무시하고 null로 처리
    set({ error: typeof error === 'string' || error === null ? error : null });
  },

  reset: () => set(initialState),
}));
