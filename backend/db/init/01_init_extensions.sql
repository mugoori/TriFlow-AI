-- ===================================
-- TriFlow AI - PostgreSQL 확장 설치
-- ===================================

-- pgvector: 벡터 임베딩 저장 및 검색
CREATE EXTENSION IF NOT EXISTS vector;

-- uuid-ossp: UUID 생성
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- pg_trgm: 텍스트 유사도 검색
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- pg_stat_statements: 쿼리 성능 모니터링
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
