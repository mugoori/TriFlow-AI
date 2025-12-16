-- =====================================================
-- Migration 012: RAG & AAS Schema Reset
-- 구버전 RAG 테이블 삭제 및 스펙 B-3-3 기반 새 스키마 적용
-- =====================================================

-- =====================================================
-- 1. 구버전 테이블 삭제
-- =====================================================
DROP TABLE IF EXISTS rag.embeddings CASCADE;
DROP TABLE IF EXISTS rag.documents CASCADE;
DROP TABLE IF EXISTS rag.knowledge_base CASCADE;

-- 구버전 함수가 있다면 삭제
DROP FUNCTION IF EXISTS rag.search_documents CASCADE;
DROP FUNCTION IF EXISTS rag.get_document_chunks CASCADE;

-- =====================================================
-- 2. pgvector 확장 활성화
-- =====================================================
CREATE EXTENSION IF NOT EXISTS vector;

-- =====================================================
-- 3. 스키마 생성 (이미 존재하면 무시)
-- =====================================================
CREATE SCHEMA IF NOT EXISTS rag;
CREATE SCHEMA IF NOT EXISTS aas;

-- =====================================================
-- 4. RAG Documents (문서 청크)
-- =====================================================
DROP TABLE IF EXISTS rag.rag_documents CASCADE;
CREATE TABLE rag.rag_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,

    -- 문서 소스 정보
    source_type TEXT NOT NULL CHECK (source_type IN ('manual', 'sop', 'wiki', 'faq', 'judgment_log', 'feedback', 'external_doc')),
    source_id TEXT NOT NULL,
    parent_id UUID REFERENCES rag.rag_documents(id) ON DELETE SET NULL,

    -- 문서 구조
    title TEXT NOT NULL,
    section TEXT,
    subsection TEXT,

    -- 청크 정보
    chunk_index INT NOT NULL,
    chunk_total INT NOT NULL,

    -- 텍스트 콘텐츠
    text TEXT NOT NULL,
    text_hash TEXT NOT NULL,
    word_count INT NOT NULL,
    char_count INT NOT NULL,
    language TEXT NOT NULL DEFAULT 'ko',

    -- 메타데이터
    metadata JSONB NOT NULL DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',

    -- 상태 및 버전
    is_active BOOLEAN NOT NULL DEFAULT true,
    version INT NOT NULL DEFAULT 1,

    -- 타임스탬프
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- 유니크 제약
    UNIQUE (tenant_id, source_type, source_id, chunk_index, version)
);

-- RAG Documents 인덱스
CREATE INDEX idx_rag_docs_tenant_active ON rag.rag_documents (tenant_id, is_active) WHERE is_active = true;
CREATE INDEX idx_rag_docs_source ON rag.rag_documents (source_type, source_id);
CREATE INDEX idx_rag_docs_tags ON rag.rag_documents USING GIN (tags);
CREATE INDEX idx_rag_docs_metadata ON rag.rag_documents USING GIN (metadata);
CREATE INDEX idx_rag_docs_text_search ON rag.rag_documents USING GIN (to_tsvector('korean', text));

COMMENT ON TABLE rag.rag_documents IS 'RAG 문서 청크 (벡터 검색용)';
COMMENT ON COLUMN rag.rag_documents.chunk_index IS '청크 순서 (0부터 시작)';
COMMENT ON COLUMN rag.rag_documents.text_hash IS 'SHA256(text) - 중복 제거용';

-- =====================================================
-- 5. RAG Document Versions (문서 버전 이력)
-- =====================================================
DROP TABLE IF EXISTS rag.rag_document_versions CASCADE;
CREATE TABLE rag.rag_document_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES rag.rag_documents(id) ON DELETE CASCADE,

    version INT NOT NULL,
    change_type TEXT NOT NULL CHECK (change_type IN ('create', 'update', 'delete', 'restore')),
    changed_by UUID REFERENCES core.users(user_id) ON DELETE SET NULL,
    change_summary TEXT,
    diff JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (document_id, version)
);

CREATE INDEX idx_rag_doc_versions_document ON rag.rag_document_versions (document_id, version DESC);

COMMENT ON TABLE rag.rag_document_versions IS 'RAG 문서 버전 이력';

-- =====================================================
-- 6. RAG Embeddings (임베딩 벡터 - pgvector)
-- =====================================================
DROP TABLE IF EXISTS rag.rag_embeddings CASCADE;
CREATE TABLE rag.rag_embeddings (
    doc_id UUID PRIMARY KEY REFERENCES rag.rag_documents(id) ON DELETE CASCADE,
    embedding vector(1536) NOT NULL,  -- OpenAI text-embedding-3-small
    model TEXT NOT NULL DEFAULT 'text-embedding-3-small',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 벡터 인덱스 (IVFFlat - 중소규모 데이터)
CREATE INDEX idx_rag_embeddings_vector ON rag.rag_embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

COMMENT ON TABLE rag.rag_embeddings IS '문서 임베딩 벡터 (pgvector)';
COMMENT ON COLUMN rag.rag_embeddings.embedding IS 'OpenAI text-embedding-3-small (1536 차원)';

-- =====================================================
-- 7. Embedding Jobs (임베딩 생성 작업)
-- =====================================================
DROP TABLE IF EXISTS rag.embedding_jobs CASCADE;
CREATE TABLE rag.embedding_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,

    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    document_count INT NOT NULL,
    embeddings_generated INT NOT NULL DEFAULT 0,

    model TEXT NOT NULL,
    total_tokens INT,
    cost_estimate_usd NUMERIC(10, 6),

    error_message TEXT,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    duration_seconds INT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_embedding_jobs_tenant ON rag.embedding_jobs (tenant_id, created_at DESC);
CREATE INDEX idx_embedding_jobs_status ON rag.embedding_jobs (status) WHERE status IN ('pending', 'running');

COMMENT ON TABLE rag.embedding_jobs IS '임베딩 생성 배치 작업';

-- =====================================================
-- 8. Memories (AI 에이전트 장단기 메모리)
-- =====================================================
DROP TABLE IF EXISTS rag.memories CASCADE;
CREATE TABLE rag.memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,

    type TEXT NOT NULL CHECK (type IN ('short_term', 'long_term', 'episodic', 'semantic', 'procedural')),
    key TEXT NOT NULL,
    value JSONB NOT NULL,

    importance FLOAT NOT NULL DEFAULT 0.5 CHECK (importance >= 0 AND importance <= 1),
    access_count INT NOT NULL DEFAULT 0,
    last_accessed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,

    context JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (tenant_id, type, key)
);

CREATE INDEX idx_memories_tenant_type ON rag.memories (tenant_id, type);
CREATE INDEX idx_memories_expires ON rag.memories (expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX idx_memories_importance ON rag.memories (importance DESC);

COMMENT ON TABLE rag.memories IS 'AI 에이전트 장단기 메모리';
COMMENT ON COLUMN rag.memories.type IS 'short_term: 단기(1일), long_term: 장기(영구), episodic: 에피소드, semantic: 지식, procedural: 절차';

-- =====================================================
-- 9. AAS Assets (자산 정의)
-- =====================================================
DROP TABLE IF EXISTS aas.aas_source_mappings CASCADE;
DROP TABLE IF EXISTS aas.aas_elements CASCADE;
DROP TABLE IF EXISTS aas.aas_submodels CASCADE;
DROP TABLE IF EXISTS aas.aas_assets CASCADE;

CREATE TABLE aas.aas_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,

    asset_id TEXT NOT NULL,
    asset_type TEXT NOT NULL CHECK (asset_type IN ('line', 'equipment', 'product', 'process', 'system')),
    ref_code TEXT NOT NULL,

    name TEXT NOT NULL,
    description TEXT,
    manufacturer TEXT,
    model TEXT,
    serial_number TEXT,

    metadata JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT true,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (tenant_id, asset_id)
);

CREATE INDEX idx_aas_assets_tenant ON aas.aas_assets (tenant_id);
CREATE INDEX idx_aas_assets_ref ON aas.aas_assets (ref_code);
CREATE INDEX idx_aas_assets_type ON aas.aas_assets (asset_type);

COMMENT ON TABLE aas.aas_assets IS 'AAS 자산 정의 (IEC 63278-1)';
COMMENT ON COLUMN aas.aas_assets.ref_code IS '실제 시스템 코드 (line_code, equipment_code 등)';

-- =====================================================
-- 10. AAS Submodels (서브모델)
-- =====================================================
CREATE TABLE aas.aas_submodels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id UUID NOT NULL REFERENCES aas.aas_assets(id) ON DELETE CASCADE,

    submodel_id TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('production', 'quality', 'maintenance', 'energy', 'cost', 'technical_data')),
    description TEXT,
    semantic_id TEXT,

    metadata JSONB NOT NULL DEFAULT '{}',

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (asset_id, submodel_id)
);

CREATE INDEX idx_aas_submodels_asset ON aas.aas_submodels (asset_id);
CREATE INDEX idx_aas_submodels_category ON aas.aas_submodels (category);

COMMENT ON TABLE aas.aas_submodels IS 'AAS 서브모델 (자산의 다양한 측면)';
COMMENT ON COLUMN aas.aas_submodels.semantic_id IS 'IEC CDD 또는 ECLASS 참조';

-- =====================================================
-- 11. AAS Elements (요소)
-- =====================================================
CREATE TABLE aas.aas_elements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submodel_id UUID NOT NULL REFERENCES aas.aas_submodels(id) ON DELETE CASCADE,

    element_id TEXT NOT NULL,
    name TEXT NOT NULL,
    datatype TEXT NOT NULL CHECK (datatype IN ('int', 'float', 'string', 'boolean', 'datetime', 'json')),
    unit TEXT,
    description TEXT,

    min_value NUMERIC,
    max_value NUMERIC,
    enum_values TEXT[],

    metadata JSONB NOT NULL DEFAULT '{}',

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (submodel_id, element_id)
);

CREATE INDEX idx_aas_elements_submodel ON aas.aas_elements (submodel_id);

COMMENT ON TABLE aas.aas_elements IS 'AAS 요소 (데이터 포인트)';

-- =====================================================
-- 12. AAS Source Mappings (소스 매핑)
-- =====================================================
CREATE TABLE aas.aas_source_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    element_id UUID NOT NULL REFERENCES aas.aas_elements(id) ON DELETE CASCADE,

    source_type TEXT NOT NULL CHECK (source_type IN ('postgres_table', 'postgres_view', 'api_endpoint', 'mcp_tool', 'calculation')),
    source_table TEXT,
    source_column TEXT,
    filter_expr TEXT,
    aggregation TEXT CHECK (aggregation IS NULL OR aggregation IN ('sum', 'avg', 'min', 'max', 'count', 'last', 'first')),
    transform_expr TEXT,

    cache_ttl_seconds INT DEFAULT 60,
    description TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_aas_mappings_element ON aas.aas_source_mappings (element_id);
CREATE INDEX idx_aas_mappings_tenant ON aas.aas_source_mappings (tenant_id);

COMMENT ON TABLE aas.aas_source_mappings IS 'AAS 요소의 데이터 소스 매핑';
COMMENT ON COLUMN aas.aas_source_mappings.filter_expr IS 'WHERE 절 (예: line_code = :line AND date = :date)';
COMMENT ON COLUMN aas.aas_source_mappings.transform_expr IS 'SQL 표현식 (예: value * 100)';

-- =====================================================
-- 13. RAG 검색 함수
-- =====================================================

-- 벡터 유사도 검색 함수
CREATE OR REPLACE FUNCTION rag.search_rag_documents(
    p_tenant_id UUID,
    p_query_embedding vector(1536),
    p_limit INT DEFAULT 5,
    p_filters JSONB DEFAULT '{}'
) RETURNS TABLE (
    doc_id UUID,
    title TEXT,
    section TEXT,
    text TEXT,
    similarity FLOAT,
    metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.title,
        d.section,
        d.text,
        1 - (e.embedding <=> p_query_embedding) AS similarity,
        d.metadata
    FROM rag.rag_embeddings e
    JOIN rag.rag_documents d ON e.doc_id = d.id
    WHERE d.tenant_id = p_tenant_id
      AND d.is_active = true
      AND (p_filters = '{}' OR d.metadata @> p_filters)
    ORDER BY e.embedding <=> p_query_embedding
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION rag.search_rag_documents IS '벡터 유사도 기반 RAG 문서 검색';

-- 하이브리드 검색 함수 (벡터 + 키워드)
CREATE OR REPLACE FUNCTION rag.hybrid_search_rag(
    p_tenant_id UUID,
    p_query_text TEXT,
    p_query_embedding vector(1536),
    p_limit INT DEFAULT 5,
    p_vector_weight FLOAT DEFAULT 0.7
) RETURNS TABLE (
    doc_id UUID,
    title TEXT,
    text TEXT,
    combined_score FLOAT
) AS $$
BEGIN
    RETURN QUERY
    WITH vector_results AS (
        SELECT
            d.id,
            d.title,
            d.text,
            1 - (e.embedding <=> p_query_embedding) AS vector_score
        FROM rag.rag_embeddings e
        JOIN rag.rag_documents d ON e.doc_id = d.id
        WHERE d.tenant_id = p_tenant_id AND d.is_active = true
        ORDER BY e.embedding <=> p_query_embedding
        LIMIT 20
    ),
    keyword_results AS (
        SELECT
            id,
            title,
            text,
            ts_rank(to_tsvector('korean', text), plainto_tsquery('korean', p_query_text)) AS keyword_score
        FROM rag.rag_documents
        WHERE tenant_id = p_tenant_id
          AND is_active = true
          AND to_tsvector('korean', text) @@ plainto_tsquery('korean', p_query_text)
        ORDER BY keyword_score DESC
        LIMIT 20
    )
    SELECT
        COALESCE(v.id, k.id),
        COALESCE(v.title, k.title),
        COALESCE(v.text, k.text),
        COALESCE(v.vector_score, 0) * p_vector_weight +
        COALESCE(k.keyword_score, 0) * (1 - p_vector_weight) AS combined_score
    FROM vector_results v
    FULL OUTER JOIN keyword_results k ON v.id = k.id
    ORDER BY combined_score DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION rag.hybrid_search_rag IS '하이브리드 검색 (벡터 + 키워드)';

-- =====================================================
-- 14. AAS 조회 뷰
-- =====================================================

-- AAS 전체 구조 뷰
CREATE OR REPLACE VIEW aas.v_aas_structure AS
SELECT
    aa.tenant_id,
    aa.asset_id,
    aa.asset_type,
    aa.ref_code,
    aa.name AS asset_name,
    asub.submodel_id,
    asub.name AS submodel_name,
    asub.category AS submodel_category,
    ae.element_id,
    ae.name AS element_name,
    ae.datatype,
    ae.unit,
    asm.source_table,
    asm.source_column,
    asm.aggregation
FROM aas.aas_assets aa
JOIN aas.aas_submodels asub ON aa.id = asub.asset_id
JOIN aas.aas_elements ae ON asub.id = ae.submodel_id
LEFT JOIN aas.aas_source_mappings asm ON ae.id = asm.element_id;

COMMENT ON VIEW aas.v_aas_structure IS 'AAS 전체 구조 (Asset -> Submodel -> Element -> Mapping)';

-- =====================================================
-- 15. 업데이트 트리거
-- =====================================================

-- updated_at 자동 업데이트 트리거 함수 (이미 존재할 수 있음)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- RAG Documents 트리거
DROP TRIGGER IF EXISTS trigger_rag_documents_updated_at ON rag.rag_documents;
CREATE TRIGGER trigger_rag_documents_updated_at
    BEFORE UPDATE ON rag.rag_documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Memories 트리거
DROP TRIGGER IF EXISTS trigger_memories_updated_at ON rag.memories;
CREATE TRIGGER trigger_memories_updated_at
    BEFORE UPDATE ON rag.memories
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- AAS Assets 트리거
DROP TRIGGER IF EXISTS trigger_aas_assets_updated_at ON aas.aas_assets;
CREATE TRIGGER trigger_aas_assets_updated_at
    BEFORE UPDATE ON aas.aas_assets
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- AAS Source Mappings 트리거
DROP TRIGGER IF EXISTS trigger_aas_source_mappings_updated_at ON aas.aas_source_mappings;
CREATE TRIGGER trigger_aas_source_mappings_updated_at
    BEFORE UPDATE ON aas.aas_source_mappings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- 16. 마이그레이션 완료 기록
-- =====================================================
INSERT INTO core.schema_migrations (version, description, executed_at)
VALUES ('012', 'RAG & AAS Schema Reset (구버전 삭제 + 스펙 B-3-3 적용)', now())
ON CONFLICT (version) DO UPDATE SET executed_at = now();

-- =====================================================
-- 완료 메시지
-- =====================================================
DO $$
BEGIN
    RAISE NOTICE 'Migration 012 완료: RAG & AAS 스키마 리셋';
    RAISE NOTICE '- 구버전 테이블 삭제됨: rag.documents, rag.embeddings, rag.knowledge_base';
    RAISE NOTICE '- 새 RAG 테이블: rag_documents, rag_document_versions, rag_embeddings, embedding_jobs, memories';
    RAISE NOTICE '- 새 AAS 테이블: aas_assets, aas_submodels, aas_elements, aas_source_mappings';
    RAISE NOTICE '- 검색 함수: search_rag_documents, hybrid_search_rag';
    RAISE NOTICE '- 뷰: v_aas_structure';
END $$;
