-- ===================================
-- TriFlow AI - RAG Schema 테이블
-- ===================================

SET search_path TO rag, public;

-- 문서 메타데이터
CREATE TABLE IF NOT EXISTS documents (
    document_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    document_type VARCHAR(100),  -- MANUAL, PROCEDURE, LOG, etc.
    source_url TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 벡터 임베딩 (pgvector)
CREATE TABLE IF NOT EXISTS embeddings (
    embedding_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL,
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    embedding vector(1536) NOT NULL,  -- OpenAI text-embedding-3-small (1536 차원)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 지식 베이스 항목
CREATE TABLE IF NOT EXISTS knowledge_base (
    kb_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    category VARCHAR(100) NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    confidence FLOAT DEFAULT 1.0,
    source_documents UUID[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스
CREATE INDEX idx_documents_tenant ON documents(tenant_id);
CREATE INDEX idx_documents_type ON documents(document_type);
CREATE INDEX idx_embeddings_document ON embeddings(document_id);
CREATE INDEX idx_embeddings_vector ON embeddings USING ivfflat (embedding vector_cosine_ops);  -- 벡터 유사도 검색
CREATE INDEX idx_knowledge_base_tenant_category ON knowledge_base(tenant_id, category);

-- 코멘트
COMMENT ON TABLE documents IS 'RAG 문서 메타데이터';
COMMENT ON TABLE embeddings IS '벡터 임베딩 (pgvector)';
COMMENT ON TABLE knowledge_base IS '지식 베이스 Q&A';
