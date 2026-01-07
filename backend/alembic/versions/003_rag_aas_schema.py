# -*- coding: utf-8 -*-
"""003 RAG & AAS Schema

Revision ID: 003_rag_aas
Revises: 002_bi_analytics
Create Date: 2025-12-26

RAG & AAS Schema (based on B-3-3 spec)
- Create rag, aas schemas
- Enable pgvector extension
- RAG tables (rag_documents, rag_embeddings, rag_document_versions, embedding_jobs)
- Memory tables (memories)
- AAS tables (aas_assets, aas_submodels, aas_elements, aas_source_mappings)
- Search functions (search_rag_documents, hybrid_search_rag, get_aas_element_value)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003_rag_aas'
down_revision: Union[str, None] = '002_bi_analytics'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================
    # Create Schemas and Extensions
    # ============================================
    op.execute("CREATE SCHEMA IF NOT EXISTS rag")
    op.execute("CREATE SCHEMA IF NOT EXISTS aas")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ============================================
    # 1. RAG Document Tables
    # ============================================

    # rag_documents table (RAG document chunks)
    op.execute("""
        CREATE TABLE rag.rag_documents (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES core.tenants(tenant_id),
            source_type text NOT NULL CHECK (source_type IN ('manual','sop','wiki','faq','judgment_log','feedback','external_doc')),
            source_id text NOT NULL,
            parent_id uuid REFERENCES rag.rag_documents(id),
            title text NOT NULL,
            section text,
            subsection text,
            chunk_index int NOT NULL,
            chunk_total int NOT NULL,
            text text NOT NULL,
            text_hash text NOT NULL,
            word_count int NOT NULL,
            char_count int NOT NULL,
            language text NOT NULL DEFAULT 'ko',
            metadata jsonb NOT NULL DEFAULT '{}',
            tags text[] DEFAULT '{}',
            is_active boolean NOT NULL DEFAULT true,
            version int NOT NULL DEFAULT 1,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, source_type, source_id, chunk_index, version)
        )
    """)
    op.execute("CREATE INDEX idx_rag_docs_tenant_active ON rag.rag_documents (tenant_id, is_active) WHERE is_active = true")
    op.execute("CREATE INDEX idx_rag_docs_source ON rag.rag_documents (source_type, source_id)")
    op.execute("CREATE INDEX idx_rag_docs_tags ON rag.rag_documents USING GIN (tags)")
    op.execute("CREATE INDEX idx_rag_docs_metadata ON rag.rag_documents USING GIN (metadata)")
    op.execute("CREATE INDEX idx_rag_docs_text_search ON rag.rag_documents USING GIN (to_tsvector('korean', text))")
    op.execute("COMMENT ON TABLE rag.rag_documents IS 'RAG Document Chunks (for vector search)'")

    # rag_document_versions table (document version history)
    op.execute("""
        CREATE TABLE rag.rag_document_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id uuid NOT NULL REFERENCES rag.rag_documents(id) ON DELETE CASCADE,
            version int NOT NULL,
            change_type text NOT NULL CHECK (change_type IN ('create','update','delete','restore')),
            changed_by uuid REFERENCES core.users(user_id),
            change_summary text,
            diff jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (document_id, version)
        )
    """)
    op.execute("CREATE INDEX idx_rag_doc_versions_document ON rag.rag_document_versions (document_id, version DESC)")
    op.execute("COMMENT ON TABLE rag.rag_document_versions IS 'RAG Document Version History'")

    # ============================================
    # 2. RAG Embedding Tables
    # ============================================

    # rag_embeddings table (embedding vectors)
    op.execute("""
        CREATE TABLE rag.rag_embeddings (
            doc_id uuid PRIMARY KEY REFERENCES rag.rag_documents(id) ON DELETE CASCADE,
            embedding vector(1536) NOT NULL,
            model text NOT NULL DEFAULT 'text-embedding-3-small',
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    # IVFFlat vector index
    op.execute("""
        CREATE INDEX idx_rag_embeddings_vector ON rag.rag_embeddings
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)
    op.execute("COMMENT ON TABLE rag.rag_embeddings IS 'Document Embedding Vectors (pgvector)'")
    op.execute("COMMENT ON COLUMN rag.rag_embeddings.embedding IS 'OpenAI text-embedding-3-small (1536 dimensions)'")

    # embedding_jobs table (embedding generation jobs)
    op.execute("""
        CREATE TABLE rag.embedding_jobs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES core.tenants(tenant_id),
            status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','completed','failed')),
            document_count int NOT NULL,
            embeddings_generated int NOT NULL DEFAULT 0,
            model text NOT NULL,
            total_tokens int,
            cost_estimate_usd numeric(10,6),
            error_message text,
            started_at timestamptz,
            ended_at timestamptz,
            duration_seconds int,
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX idx_embedding_jobs_tenant ON rag.embedding_jobs (tenant_id, created_at DESC)")
    op.execute("CREATE INDEX idx_embedding_jobs_status ON rag.embedding_jobs (status) WHERE status IN ('pending','running')")
    op.execute("COMMENT ON TABLE rag.embedding_jobs IS 'Embedding Generation Batch Jobs'")

    # ============================================
    # 3. Memory Tables
    # ============================================

    # memories table (short-term and long-term memory)
    op.execute("""
        CREATE TABLE rag.memories (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES core.tenants(tenant_id),
            type text NOT NULL CHECK (type IN ('short_term','long_term','episodic','semantic','procedural')),
            key text NOT NULL,
            value jsonb NOT NULL,
            importance float NOT NULL DEFAULT 0.5 CHECK (importance >= 0 AND importance <= 1),
            access_count int NOT NULL DEFAULT 0,
            last_accessed_at timestamptz,
            expires_at timestamptz,
            context jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, type, key)
        )
    """)
    op.execute("CREATE INDEX idx_memories_tenant_type ON rag.memories (tenant_id, type)")
    op.execute("CREATE INDEX idx_memories_expires ON rag.memories (expires_at) WHERE expires_at IS NOT NULL")
    op.execute("CREATE INDEX idx_memories_importance ON rag.memories (importance DESC)")
    op.execute("COMMENT ON TABLE rag.memories IS 'AI Agent Short-term and Long-term Memory'")
    op.execute("COMMENT ON COLUMN rag.memories.type IS 'short_term: 1day, long_term: permanent, episodic: episode, semantic: knowledge, procedural: procedure'")

    # ============================================
    # 4. AAS Tables
    # ============================================

    # aas_assets table (assets)
    op.execute("""
        CREATE TABLE aas.aas_assets (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES core.tenants(tenant_id),
            asset_id text NOT NULL,
            asset_type text NOT NULL CHECK (asset_type IN ('line','equipment','product','process','system')),
            ref_code text NOT NULL,
            name text NOT NULL,
            description text,
            manufacturer text,
            model text,
            serial_number text,
            metadata jsonb NOT NULL DEFAULT '{}',
            is_active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, asset_id)
        )
    """)
    op.execute("CREATE INDEX idx_aas_assets_tenant ON aas.aas_assets (tenant_id)")
    op.execute("CREATE INDEX idx_aas_assets_ref ON aas.aas_assets (ref_code)")
    op.execute("CREATE INDEX idx_aas_assets_type ON aas.aas_assets (asset_type)")
    op.execute("COMMENT ON TABLE aas.aas_assets IS 'AAS Asset Definition (IEC 63278-1)'")
    op.execute("COMMENT ON COLUMN aas.aas_assets.ref_code IS 'Actual system code (line_code, equipment_code, etc.)'")

    # aas_submodels table (submodels)
    op.execute("""
        CREATE TABLE aas.aas_submodels (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            asset_id uuid NOT NULL REFERENCES aas.aas_assets(id) ON DELETE CASCADE,
            submodel_id text NOT NULL,
            name text NOT NULL,
            category text NOT NULL CHECK (category IN ('production','quality','maintenance','energy','cost','technical_data')),
            description text,
            semantic_id text,
            metadata jsonb NOT NULL DEFAULT '{}',
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (asset_id, submodel_id)
        )
    """)
    op.execute("CREATE INDEX idx_aas_submodels_asset ON aas.aas_submodels (asset_id)")
    op.execute("CREATE INDEX idx_aas_submodels_category ON aas.aas_submodels (category)")
    op.execute("COMMENT ON TABLE aas.aas_submodels IS 'AAS Submodels (various aspects of assets)'")
    op.execute("COMMENT ON COLUMN aas.aas_submodels.semantic_id IS 'IEC CDD or ECLASS reference'")

    # aas_elements table (elements)
    op.execute("""
        CREATE TABLE aas.aas_elements (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            submodel_id uuid NOT NULL REFERENCES aas.aas_submodels(id) ON DELETE CASCADE,
            element_id text NOT NULL,
            name text NOT NULL,
            datatype text NOT NULL CHECK (datatype IN ('int','float','string','boolean','datetime','json')),
            unit text,
            description text,
            min_value numeric,
            max_value numeric,
            enum_values text[],
            metadata jsonb NOT NULL DEFAULT '{}',
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (submodel_id, element_id)
        )
    """)
    op.execute("CREATE INDEX idx_aas_elements_submodel ON aas.aas_elements (submodel_id)")
    op.execute("COMMENT ON TABLE aas.aas_elements IS 'AAS Elements (data points)'")

    # aas_source_mappings table (source mappings)
    op.execute("""
        CREATE TABLE aas.aas_source_mappings (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES core.tenants(tenant_id),
            element_id uuid NOT NULL REFERENCES aas.aas_elements(id) ON DELETE CASCADE,
            source_type text NOT NULL CHECK (source_type IN ('postgres_table','postgres_view','api_endpoint','mcp_tool','calculation')),
            source_table text,
            source_column text,
            filter_expr text,
            aggregation text CHECK (aggregation IN ('sum','avg','min','max','count','last','first')),
            transform_expr text,
            cache_ttl_seconds int DEFAULT 60,
            description text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX idx_aas_mappings_element ON aas.aas_source_mappings (element_id)")
    op.execute("CREATE INDEX idx_aas_mappings_tenant ON aas.aas_source_mappings (tenant_id)")
    op.execute("COMMENT ON TABLE aas.aas_source_mappings IS 'AAS Element Data Source Mappings'")
    op.execute("COMMENT ON COLUMN aas.aas_source_mappings.filter_expr IS 'WHERE clause (e.g., line_code = {line} AND date = {date})'")
    op.execute("COMMENT ON COLUMN aas.aas_source_mappings.transform_expr IS 'SQL expression (e.g., value * 100)'")

    # ============================================
    # 5. AAS Views
    # ============================================

    # v_aas_structure view (AAS full structure)
    op.execute("""
        CREATE VIEW aas.v_aas_structure AS
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
        LEFT JOIN aas.aas_source_mappings asm ON ae.id = asm.element_id
    """)
    op.execute("COMMENT ON VIEW aas.v_aas_structure IS 'AAS Full Structure (Asset -> Submodel -> Element -> Mapping)'")

    # ============================================
    # 6. RAG Search Functions
    # ============================================

    # search_rag_documents function (vector search)
    op.execute("""
        CREATE OR REPLACE FUNCTION rag.search_rag_documents(
            p_tenant_id uuid,
            p_query_embedding vector(1536),
            p_limit int DEFAULT 5,
            p_filters jsonb DEFAULT '{}'
        ) RETURNS TABLE (
            doc_id uuid,
            title text,
            section text,
            text text,
            similarity float,
            metadata jsonb
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
        $$ LANGUAGE plpgsql
    """)

    # hybrid_search_rag function (hybrid search)
    op.execute("""
        CREATE OR REPLACE FUNCTION rag.hybrid_search_rag(
            p_tenant_id uuid,
            p_query_text text,
            p_query_embedding vector(1536),
            p_limit int DEFAULT 5,
            p_vector_weight float DEFAULT 0.7
        ) RETURNS TABLE (
            doc_id uuid,
            title text,
            text text,
            combined_score float
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
        $$ LANGUAGE plpgsql
    """)

    # ============================================
    # 7. AAS Data Query Functions
    # ============================================

    # get_aas_element_value function
    # Note: Using raw connection to avoid SQLAlchemy bind parameter interpretation
    # Using %%s to escape percent signs for Python, and {line}/{date} instead of :line/:date
    op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION aas.get_aas_element_value(
            p_tenant_id uuid,
            p_asset_ref_code text,
            p_element_id text,
            p_params jsonb DEFAULT '{}'
        ) RETURNS jsonb AS $$
        DECLARE
            v_mapping record;
            v_query text;
            v_result jsonb;
        BEGIN
            -- Get mapping info
            SELECT
                asm.source_type,
                asm.source_table,
                asm.source_column,
                asm.filter_expr,
                asm.aggregation,
                asm.transform_expr
            INTO v_mapping
            FROM aas.aas_source_mappings asm
            JOIN aas.aas_elements ae ON asm.element_id = ae.id
            JOIN aas.aas_submodels asub ON ae.submodel_id = asub.id
            JOIN aas.aas_assets aa ON asub.asset_id = aa.id
            WHERE asm.tenant_id = p_tenant_id
                AND aa.ref_code = p_asset_ref_code
                AND ae.element_id = p_element_id;

            IF NOT FOUND THEN
                RETURN jsonb_build_object('error', 'mapping not found');
            END IF;

            -- Build dynamic query (postgres_table, postgres_view)
            IF v_mapping.source_type IN ('postgres_table', 'postgres_view') THEN
                v_query := format(
                    'SELECT %%s(%%s) FROM %%s WHERE %%s',
                    COALESCE(v_mapping.aggregation, 'AVG'),
                    v_mapping.source_column,
                    v_mapping.source_table,
                    replace(v_mapping.filter_expr, '{line}', quote_literal(p_asset_ref_code))
                );

                -- Parameter substitution
                IF p_params ? 'date' THEN
                    v_query := replace(v_query, '{date}', quote_literal(p_params->>'date'));
                END IF;

                EXECUTE v_query INTO v_result;
                RETURN jsonb_build_object('value', v_result);

            ELSIF v_mapping.source_type = 'calculation' THEN
                RETURN jsonb_build_object('error', 'calculation not implemented');
            ELSE
                RETURN jsonb_build_object('error', 'unsupported source type');
            END IF;
        END;
        $$ LANGUAGE plpgsql
    """))

    # get_aas_submodel_values function
    op.execute("""
        CREATE OR REPLACE FUNCTION aas.get_aas_submodel_values(
            p_tenant_id uuid,
            p_asset_ref_code text,
            p_submodel_id text,
            p_params jsonb DEFAULT '{}'
        ) RETURNS jsonb AS $$
        DECLARE
            v_element record;
            v_result jsonb := '{}';
            v_value jsonb;
        BEGIN
            FOR v_element IN
                SELECT ae.element_id, ae.name
                FROM aas.aas_elements ae
                JOIN aas.aas_submodels asub ON ae.submodel_id = asub.id
                JOIN aas.aas_assets aa ON asub.asset_id = aa.id
                WHERE aa.tenant_id = p_tenant_id
                    AND aa.ref_code = p_asset_ref_code
                    AND asub.submodel_id = p_submodel_id
            LOOP
                v_value := aas.get_aas_element_value(
                    p_tenant_id,
                    p_asset_ref_code,
                    v_element.element_id,
                    p_params
                );

                v_result := v_result || jsonb_build_object(
                    v_element.element_id,
                    jsonb_build_object(
                        'name', v_element.name,
                        'value', v_value->'value'
                    )
                );
            END LOOP;

            RETURN v_result;
        END;
        $$ LANGUAGE plpgsql
    """)


def downgrade() -> None:
    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS aas.get_aas_submodel_values(uuid, text, text, jsonb)")
    op.execute("DROP FUNCTION IF EXISTS aas.get_aas_element_value(uuid, text, text, jsonb)")
    op.execute("DROP FUNCTION IF EXISTS rag.hybrid_search_rag(uuid, text, vector, int, float)")
    op.execute("DROP FUNCTION IF EXISTS rag.search_rag_documents(uuid, vector, int, jsonb)")

    # Drop views
    op.execute("DROP VIEW IF EXISTS aas.v_aas_structure")

    # Drop AAS tables
    op.execute("DROP TABLE IF EXISTS aas.aas_source_mappings CASCADE")
    op.execute("DROP TABLE IF EXISTS aas.aas_elements CASCADE")
    op.execute("DROP TABLE IF EXISTS aas.aas_submodels CASCADE")
    op.execute("DROP TABLE IF EXISTS aas.aas_assets CASCADE")

    # Drop RAG tables
    op.execute("DROP TABLE IF EXISTS rag.memories CASCADE")
    op.execute("DROP TABLE IF EXISTS rag.embedding_jobs CASCADE")
    op.execute("DROP TABLE IF EXISTS rag.rag_embeddings CASCADE")
    op.execute("DROP TABLE IF EXISTS rag.rag_document_versions CASCADE")
    op.execute("DROP TABLE IF EXISTS rag.rag_documents CASCADE")

    # Drop schemas
    op.execute("DROP SCHEMA IF EXISTS aas CASCADE")
    op.execute("DROP SCHEMA IF EXISTS rag CASCADE")

    # Note: We don't drop the vector extension as it might be used by other schemas
