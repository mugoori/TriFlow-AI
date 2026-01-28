from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import datetime

# Recipe 관련
class RecipeMetadata(BaseModel):
    id: int
    filename: str
    product_name: Optional[str]
    company_name: Optional[str]
    formulation_type: Optional[str]
    created_date: Optional[str]
    ingredient_count: int

class RecipeIngredient(BaseModel):
    ingredient: str
    ratio: float

class RecipeDetail(BaseModel):
    metadata: RecipeMetadata
    ingredients: List[RecipeIngredient]

# 공공API 유사제품
class SimilarProductAPI(BaseModel):
    product_name: str
    company_name: Optional[str] = ""
    raw_materials: Optional[str] = ""
    shelf_life: Optional[str] = ""
    formulation_type: Optional[str] = ""
    functional_ingredients: Optional[str] = ""
    other_ingredients: Optional[str] = ""
    functionality: Optional[str] = ""
    intake_method: Optional[str] = ""
    report_no: Optional[str] = ""
    caution: Optional[str] = ""
    standard: Optional[str] = ""
    source: Optional[str] = "식품안전나라"
    match_count: Optional[int] = 0

# 제품 정보
class ProductInfo(BaseModel):
    name: str
    formulation_type: str
    target_cost: Optional[int] = None
    target_weight: Optional[float] = None
    description: Optional[str] = ""

# 원료 요구사항
class IngredientRequirement(BaseModel):
    ingredient_name: str
    min_ratio: Optional[float] = None
    max_ratio: Optional[float] = None
    is_required: bool = True
    notes: Optional[str] = ""

# 제약 조건
class Constraints(BaseModel):
    max_ingredients: Optional[int] = None
    avoid_ingredients: Optional[List[str]] = []
    regulatory_requirements: Optional[List[str]] = []
    quality_requirements: Optional[List[str]] = []

# 프롬프트 생성 요청 (프론트엔드 구조에 맞춤)
class PromptRequest(BaseModel):
    product_info: ProductInfo
    ingredient_requirements: List[IngredientRequirement] = []
    constraints: Constraints = Constraints()
    similar_products_api: Optional[List[SimilarProductAPI]] = []

# 프롬프트 생성 응답
class PromptResponse(BaseModel):
    prompt: str
    similar_products_count: Optional[int] = 0
    generated_at: datetime

# 검색 결과
class SearchResult(BaseModel):
    products: List[RecipeMetadata]
    total_count: int
    page: int
    page_size: int


# ===================================
# AI 생성 레시피 관련 스키마
# ===================================

class AIRecipeIngredient(BaseModel):
    """AI 생성 레시피의 원료 항목"""
    no: int
    name: str
    ratio: float
    role: Optional[str] = ""


class AIGeneratedRecipeCreate(BaseModel):
    """AI 레시피 저장 요청"""
    product_name: str
    formulation_type: Optional[str] = None
    option_type: str  # 'cost_optimized', 'premium', 'balanced', 'custom'
    title: Optional[str] = None
    ingredients: List[AIRecipeIngredient]
    total_ratio: Optional[float] = None
    estimated_cost: Optional[str] = None
    notes: Optional[str] = None
    quality: Optional[str] = None
    summary: Optional[str] = None
    source_type: str = "ai_generated"
    source_reference: Optional[str] = None
    external_id: Optional[str] = None


class AIGeneratedRecipeResponse(BaseModel):
    """AI 생성 레시피 응답"""
    recipe_id: str
    tenant_id: str
    product_name: str
    formulation_type: Optional[str]
    option_type: str
    title: Optional[str]
    ingredients: List[AIRecipeIngredient]
    total_ratio: Optional[float]
    estimated_cost: Optional[str]
    notes: Optional[str]
    quality: Optional[str]
    summary: Optional[str]
    source_type: str
    source_reference: Optional[str]
    external_id: Optional[str]
    status: str
    version: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RecipeFeedbackCreate(BaseModel):
    """레시피 피드백 생성 요청"""
    rating: int  # 1-5
    comment: Optional[str] = None
    feedback_type: Optional[str] = None  # 'quality', 'cost', 'ingredient', 'general'


class RecipeFeedbackResponse(BaseModel):
    """레시피 피드백 응답"""
    feedback_id: str
    recipe_id: str
    rating: int
    comment: Optional[str]
    feedback_type: Optional[str]
    created_at: datetime


class UnifiedRecipe(BaseModel):
    """통합 레시피 (기존 DB + AI 생성)"""
    recipe_id: str
    tenant_id: str
    product_name: str
    formulation_type: Optional[str]
    option_type: str
    ingredient_count: int
    source_type: str  # 'db_existing', 'ai_generated', 'mes_imported', 'erp_imported'
    source_reference: Optional[str]
    status: str
    created_at: Optional[datetime]
    created_by: Optional[str]


class UnifiedRecipeListResponse(BaseModel):
    """통합 레시피 목록 응답"""
    recipes: List[UnifiedRecipe]
    total_count: int
    page: int
    page_size: int
