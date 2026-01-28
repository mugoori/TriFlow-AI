-- ===================================
-- Korea Biopharm Module - 테이블 생성
-- ===================================

-- Korea Biopharm Schema
CREATE SCHEMA IF NOT EXISTS korea_biopharm;

-- ===================================
-- 기존 레시피 데이터 테이블 (이미 존재할 수 있음)
-- ===================================

-- 레시피 메타데이터 (엑셀에서 가져온 과거 레시피)
CREATE TABLE IF NOT EXISTS korea_biopharm.recipe_metadata (
    id SERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id),
    filename VARCHAR(500),
    product_name VARCHAR(500),
    company_name VARCHAR(255) DEFAULT '한국바이오팜',
    formulation_type VARCHAR(100),
    created_date DATE,
    ingredient_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 레시피 상세 (원료별 배합비)
CREATE TABLE IF NOT EXISTS korea_biopharm.historical_recipes (
    id SERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id),
    filename VARCHAR(500),
    ingredient VARCHAR(500),
    ratio NUMERIC(10, 4),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_recipe_metadata_tenant ON korea_biopharm.recipe_metadata(tenant_id);
CREATE INDEX IF NOT EXISTS idx_recipe_metadata_product ON korea_biopharm.recipe_metadata(product_name);
CREATE INDEX IF NOT EXISTS idx_historical_recipes_tenant ON korea_biopharm.historical_recipes(tenant_id);
CREATE INDEX IF NOT EXISTS idx_historical_recipes_filename ON korea_biopharm.historical_recipes(filename);
CREATE INDEX IF NOT EXISTS idx_historical_recipes_ingredient ON korea_biopharm.historical_recipes(ingredient);

-- ===================================
-- AI 생성 레시피 테이블 (신규)
-- ===================================

-- AI 생성 레시피 저장
CREATE TABLE IF NOT EXISTS korea_biopharm.ai_generated_recipes (
    recipe_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id),
    product_name VARCHAR(500) NOT NULL,
    formulation_type VARCHAR(100),
    option_type VARCHAR(50) NOT NULL,  -- 'cost_optimized', 'premium', 'balanced', 'custom'
    title VARCHAR(255),
    ingredients JSONB NOT NULL,        -- [{no, name, ratio, role}]
    total_ratio NUMERIC(10,4),
    estimated_cost VARCHAR(100),
    notes TEXT,
    quality TEXT,
    summary TEXT,
    source_type VARCHAR(50) NOT NULL DEFAULT 'ai_generated',  -- 'ai_generated', 'mes_imported', 'erp_imported', 'manual'
    source_reference VARCHAR(255),
    external_id VARCHAR(255),
    status VARCHAR(50) DEFAULT 'draft',  -- 'draft', 'approved', 'production', 'archived'
    version INTEGER DEFAULT 1,
    parent_recipe_id UUID REFERENCES korea_biopharm.ai_generated_recipes(recipe_id),
    created_by UUID REFERENCES core.users(user_id),
    approved_by UUID REFERENCES core.users(user_id),
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 레시피 피드백
CREATE TABLE IF NOT EXISTS korea_biopharm.recipe_feedback (
    feedback_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id),
    recipe_id UUID NOT NULL REFERENCES korea_biopharm.ai_generated_recipes(recipe_id) ON DELETE CASCADE,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    comment TEXT,
    feedback_type VARCHAR(50),  -- 'quality', 'cost', 'ingredient', 'general'
    created_by UUID REFERENCES core.users(user_id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_ai_recipes_tenant ON korea_biopharm.ai_generated_recipes(tenant_id);
CREATE INDEX IF NOT EXISTS idx_ai_recipes_status ON korea_biopharm.ai_generated_recipes(status);
CREATE INDEX IF NOT EXISTS idx_ai_recipes_source ON korea_biopharm.ai_generated_recipes(source_type);
CREATE INDEX IF NOT EXISTS idx_ai_recipes_option ON korea_biopharm.ai_generated_recipes(option_type);
CREATE INDEX IF NOT EXISTS idx_ai_recipes_created ON korea_biopharm.ai_generated_recipes(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_recipe_feedback_recipe ON korea_biopharm.recipe_feedback(recipe_id);

-- ===================================
-- 통합 레시피 뷰 (기존 DB + AI 생성)
-- ===================================

-- 기존 뷰가 있으면 삭제 후 재생성
DROP VIEW IF EXISTS korea_biopharm.unified_recipes;

CREATE VIEW korea_biopharm.unified_recipes AS
SELECT
    rm.id::text AS recipe_id,
    rm.tenant_id,
    rm.product_name,
    rm.formulation_type,
    'historical' AS option_type,
    rm.ingredient_count,
    'db_existing' AS source_type,
    rm.filename AS source_reference,
    'approved' AS status,
    rm.created_date::timestamp AS created_at,
    NULL::uuid AS created_by
FROM korea_biopharm.recipe_metadata rm
UNION ALL
SELECT
    agr.recipe_id::text,
    agr.tenant_id,
    agr.product_name,
    agr.formulation_type,
    agr.option_type,
    jsonb_array_length(agr.ingredients) AS ingredient_count,
    agr.source_type,
    agr.source_reference,
    agr.status,
    agr.created_at,
    agr.created_by
FROM korea_biopharm.ai_generated_recipes agr;

-- ===================================
-- 업데이트 트리거
-- ===================================

-- updated_at 자동 업데이트 함수 (이미 존재하면 스킵)
CREATE OR REPLACE FUNCTION korea_biopharm.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- ai_generated_recipes 업데이트 트리거
DROP TRIGGER IF EXISTS update_ai_recipes_updated_at ON korea_biopharm.ai_generated_recipes;
CREATE TRIGGER update_ai_recipes_updated_at
    BEFORE UPDATE ON korea_biopharm.ai_generated_recipes
    FOR EACH ROW
    EXECUTE FUNCTION korea_biopharm.update_updated_at_column();

-- recipe_metadata 업데이트 트리거
DROP TRIGGER IF EXISTS update_recipe_metadata_updated_at ON korea_biopharm.recipe_metadata;
CREATE TRIGGER update_recipe_metadata_updated_at
    BEFORE UPDATE ON korea_biopharm.recipe_metadata
    FOR EACH ROW
    EXECUTE FUNCTION korea_biopharm.update_updated_at_column();

-- 검색 경로에 korea_biopharm 추가
ALTER DATABASE triflow_ai SET search_path TO core, bi, rag, audit, korea_biopharm, public;

COMMENT ON SCHEMA korea_biopharm IS 'Korea Biopharm 배합비 관리 모듈';
COMMENT ON TABLE korea_biopharm.ai_generated_recipes IS 'AI가 생성한 레시피 저장';
COMMENT ON TABLE korea_biopharm.recipe_feedback IS '레시피에 대한 피드백';
COMMENT ON VIEW korea_biopharm.unified_recipes IS '기존 DB 레시피 + AI 생성 레시피 통합 뷰';
