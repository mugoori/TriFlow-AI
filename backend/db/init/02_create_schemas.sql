-- ===================================
-- TriFlow AI - 스키마 생성
-- ===================================

-- Core Schema: Rules, Workflows, Sensors
CREATE SCHEMA IF NOT EXISTS core;

-- BI Schema: Reports, Dashboards, Datasets
CREATE SCHEMA IF NOT EXISTS bi;

-- RAG Schema: Documents, Embeddings, Knowledge Base
CREATE SCHEMA IF NOT EXISTS rag;

-- Audit Schema: Logs, Feedback, Traceability
CREATE SCHEMA IF NOT EXISTS audit;

-- 기본 검색 경로 설정
ALTER DATABASE triflow_ai SET search_path TO core, bi, rag, audit, public;
