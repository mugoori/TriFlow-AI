# B-3-4. Performance & Operations

**문서 ID**: B-3-4
**버전**: 2.0
**최종 수정일**: 2025-01-26
**작성자**: AI Factory Development Team
**관련 문서**: A-2 (요구사항), B-1 (아키텍처), B-3-1/2/3 (스키마), D-1 (인프라), D-2 (모니터링)

---

## 목차
1. [개요](#1-개요)
2. [파티셔닝 전략](#2-파티셔닝-전략)
3. [인덱스 전략](#3-인덱스-전략)
4. [마이그레이션 관리](#4-마이그레이션-관리)
5. [백업 및 복구](#5-백업-및-복구)
6. [데이터 라이프사이클](#6-데이터-라이프사이클)
7. [성능 모니터링](#7-성능-모니터링)
8. [용량 계획](#8-용량-계획)
9. [운영 절차](#9-운영-절차)
10. [트러블슈팅](#10-트러블슈팅)

---

## 1. 개요

### 1.1 목적
PostgreSQL 데이터베이스의 성능 최적화, 안정적 운영, 그리고 확장 가능한 데이터 관리 전략 수립.

### 1.2 성능 목표

| 지표 | 목표 | 측정 방법 |
|------|------|-----------|
| Judgment 조회 | p95 < 500ms | pg_stat_statements |
| BI 쿼리 응답 | p95 < 2s | application logs |
| RAG 벡터 검색 | p95 < 100ms | pg_stat_statements |
| ETL 처리 시간 | 일일 < 30분 | etl_job_executions |
| 트랜잭션 처리량 | > 1000 TPS | pgbench |
| 커넥션 풀 사용률 | < 80% | pg_stat_activity |
| 디스크 I/O 대기 | p95 < 10ms | iostat |

### 1.3 용량 목표 (연간 기준)

| 항목 | 예상 규모 | 비고 |
|------|-----------|------|
| 판단 실행 이력 | 18M rows/year | 50k/day × 365 |
| 워크플로우 인스턴스 | 5M rows/year | |
| LLM 호출 로그 | 36M rows/year | 100k/day × 365 |
| RAW 데이터 | 100M rows/year | MES/ERP 통합 |
| FACT 테이블 | 10M rows/year | 일일 집계 |
| RAG 문서 | 100k chunks | 평균 500 토큰/청크 |
| 총 DB 크기 | ~500GB/year | 압축 및 파티셔닝 적용 |

---

## 2. 파티셔닝 전략

### 2.1 파티셔닝 대상 테이블

**시계열 데이터 (Range Partitioning)**:
| 테이블 | 파티션 키 | 파티션 주기 | 보관 기간 |
|--------|----------|------------|----------|
| judgment_executions | created_at | 월별 | 2년 (규제 시 연장) |
| workflow_instances | started_at | 월별 | 1년 |
| workflow_execution_logs | started_at | 월별 | 6개월 |
| llm_calls | created_at | 월별 | 6개월 |
| mcp_call_logs | created_at | 월별 | 3개월 |
| audit_logs | created_at | 월별 | 5년 |
| raw_mes_production | event_time | 월별 | 90일 (핫), 이후 콜드 |
| raw_erp_order | event_time | 월별 | 90일 |
| raw_inventory | event_time | 월별 | 90일 |
| raw_equipment_event | event_time | 월별 | 90일 |
| fact_daily_production | date | 분기별 | 2년 |
| fact_daily_defect | date | 분기별 | 2년 |
| fact_inventory_snapshot | date | 분기별 | 1년 |
| fact_equipment_event | date | 분기별 | 1년 |
| fact_hourly_production | hour_timestamp | 월별 | 3개월 |

### 2.2 파티션 생성 전략

**자동 파티션 생성 함수**:
```sql
-- 월별 파티션 자동 생성
CREATE OR REPLACE FUNCTION create_monthly_partition(
  p_table_name text,
  p_partition_column text,
  p_target_date date
) RETURNS text AS $$
DECLARE
  v_partition_name text;
  v_start_date date;
  v_end_date date;
BEGIN
  v_start_date := date_trunc('month', p_target_date);
  v_end_date := v_start_date + INTERVAL '1 month';
  v_partition_name := p_table_name || '_y' || to_char(v_start_date, 'YYYY') || 'm' || to_char(v_start_date, 'MM');

  EXECUTE format(
    'CREATE TABLE IF NOT EXISTS %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)',
    v_partition_name,
    p_table_name,
    v_start_date,
    v_end_date
  );

  RETURN v_partition_name;
END;
$$ LANGUAGE plpgsql;

-- 분기별 파티션 자동 생성
CREATE OR REPLACE FUNCTION create_quarterly_partition(
  p_table_name text,
  p_partition_column text,
  p_target_date date
) RETURNS text AS $$
DECLARE
  v_partition_name text;
  v_start_date date;
  v_end_date date;
  v_quarter int;
BEGIN
  v_quarter := EXTRACT(quarter FROM p_target_date);
  v_start_date := date_trunc('quarter', p_target_date);
  v_end_date := v_start_date + INTERVAL '3 months';
  v_partition_name := p_table_name || '_y' || to_char(v_start_date, 'YYYY') || 'q' || v_quarter;

  EXECUTE format(
    'CREATE TABLE IF NOT EXISTS %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)',
    v_partition_name,
    p_table_name,
    v_start_date,
    v_end_date
  );

  RETURN v_partition_name;
END;
$$ LANGUAGE plpgsql;
```

**배치 파티션 생성**:
```sql
-- 향후 6개월 파티션 미리 생성
DO $$
DECLARE
  v_month date;
  v_partition text;
BEGIN
  FOR i IN 0..5 LOOP
    v_month := date_trunc('month', CURRENT_DATE) + (i || ' months')::interval;

    -- judgment_executions
    v_partition := create_monthly_partition('judgment_executions', 'created_at', v_month);
    RAISE NOTICE 'Created partition: %', v_partition;

    -- workflow_instances
    v_partition := create_monthly_partition('workflow_instances', 'started_at', v_month);
    RAISE NOTICE 'Created partition: %', v_partition;

    -- llm_calls
    v_partition := create_monthly_partition('llm_calls', 'created_at', v_month);
    RAISE NOTICE 'Created partition: %', v_partition;

    -- raw_mes_production
    v_partition := create_monthly_partition('raw_mes_production', 'event_time', v_month);
    RAISE NOTICE 'Created partition: %', v_partition;
  END LOOP;
END $$;
```

### 2.3 파티션 프루닝 최적화

**좋은 쿼리 패턴**:
```sql
-- ✅ 파티션 프루닝 활성화 (파티션 키 직접 사용)
SELECT * FROM judgment_executions
WHERE tenant_id = :tenant_id
  AND created_at >= '2025-01-01'
  AND created_at < '2025-02-01';

-- ✅ 최근 7일 조회
SELECT * FROM judgment_executions
WHERE tenant_id = :tenant_id
  AND created_at >= CURRENT_DATE - INTERVAL '7 days';
```

**나쁜 쿼리 패턴**:
```sql
-- ❌ 파티션 프루닝 비활성화 (함수 사용)
SELECT * FROM judgment_executions
WHERE tenant_id = :tenant_id
  AND DATE(created_at) = '2025-01-26';

-- ❌ 파티션 키 없이 조회
SELECT * FROM judgment_executions
WHERE workflow_id = :workflow_id;
```

### 2.4 파티션 유지보수

**파티션 Detach/Drop**:
```sql
-- 90일 이상 파티션 detach (아카이빙 전)
DO $$
DECLARE
  v_partition text;
  v_cutoff_date date := CURRENT_DATE - INTERVAL '90 days';
BEGIN
  FOR v_partition IN
    SELECT tablename FROM pg_tables
    WHERE schemaname = 'public'
      AND tablename LIKE 'raw_mes_production_y%'
      AND tablename < 'raw_mes_production_y' || to_char(v_cutoff_date, 'YYYYMM')
  LOOP
    EXECUTE format('ALTER TABLE raw_mes_production DETACH PARTITION %I', v_partition);
    RAISE NOTICE 'Detached partition: %', v_partition;
  END LOOP;
END $$;

-- detach된 파티션을 Export 후 Drop
-- pg_dump -t raw_mes_production_y2024m10 > backup.sql
-- DROP TABLE raw_mes_production_y2024m10;
```

---

## 3. 인덱스 전략

### 3.1 인덱스 설계 원칙

1. **Cardinality 우선**: 높은 선택도 컬럼 우선
2. **쿼리 패턴 기반**: 자주 사용되는 WHERE/JOIN 조건
3. **복합 인덱스 순서**: `(tenant_id, created_at DESC, ...)`
4. **Partial 인덱스**: `WHERE status = 'active'`
5. **JSONB GIN 인덱스**: 검색이 필요한 JSONB 필드만
6. **정기 유지보수**: REINDEX, ANALYZE

### 3.2 인덱스 카탈로그

**Core Tables**:
```sql
-- tenants
CREATE INDEX idx_tenants_status ON tenants (status) WHERE status = 'active';

-- users
CREATE INDEX idx_users_tenant_role ON users (tenant_id, role) WHERE status = 'active';
CREATE INDEX idx_users_email ON users (email);

-- workflows
CREATE INDEX idx_workflows_tenant_active ON workflows (tenant_id, is_active) WHERE is_active = true;
CREATE INDEX idx_workflows_dsl_digest ON workflows (dsl_digest);

-- workflow_instances
CREATE INDEX idx_wf_instances_tenant_status ON workflow_instances (tenant_id, status);
CREATE INDEX idx_wf_instances_workflow_started ON workflow_instances (workflow_id, started_at DESC);
CREATE INDEX idx_wf_instances_trace ON workflow_instances (trace_id);

-- judgment_executions
CREATE INDEX idx_judgment_exec_tenant_created ON judgment_executions (tenant_id, created_at DESC);
CREATE INDEX idx_judgment_exec_workflow ON judgment_executions (workflow_id, created_at DESC);
CREATE INDEX idx_judgment_exec_result ON judgment_executions (tenant_id, result, created_at DESC);
CREATE INDEX idx_judgment_exec_trace ON judgment_executions (trace_id);
CREATE INDEX idx_judgment_exec_cache_key ON judgment_executions (cache_key) WHERE cache_hit = true;
CREATE INDEX idx_judgment_exec_input_data ON judgment_executions USING GIN (input_data);

-- rulesets
CREATE INDEX idx_rulesets_tenant_active ON rulesets (tenant_id, is_active) WHERE is_active = true;

-- rule_deployments
CREATE INDEX idx_rule_deployments_ruleset ON rule_deployments (ruleset_id, deployed_at DESC);
```

**BI/Analytics Tables**:
```sql
-- fact_daily_production
CREATE INDEX idx_fact_daily_prod_date ON fact_daily_production (tenant_id, date DESC);
CREATE INDEX idx_fact_daily_prod_line ON fact_daily_production (tenant_id, line_code, date DESC);
CREATE INDEX idx_fact_daily_prod_product ON fact_daily_production (tenant_id, product_code, date DESC);

-- fact_daily_defect
CREATE INDEX idx_fact_daily_defect_date ON fact_daily_defect (tenant_id, date DESC);
CREATE INDEX idx_fact_daily_defect_type ON fact_daily_defect (defect_type, date DESC);
```

**RAG Tables**:
```sql
-- rag_documents
CREATE INDEX idx_rag_docs_tenant_active ON rag_documents (tenant_id, is_active) WHERE is_active = true;
CREATE INDEX idx_rag_docs_tags ON rag_documents USING GIN (tags);
CREATE INDEX idx_rag_docs_text_search ON rag_documents USING GIN (to_tsvector('korean', text));

-- rag_embeddings
CREATE INDEX idx_rag_embeddings_vector ON rag_embeddings
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

### 3.3 인덱스 모니터링

**미사용 인덱스 탐지**:
```sql
SELECT
  schemaname,
  tablename,
  indexname,
  idx_scan,
  idx_tup_read,
  idx_tup_fetch,
  pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indexrelname NOT LIKE 'pg_toast%'
ORDER BY pg_relation_size(indexrelid) DESC;
```

**인덱스 비대화 확인**:
```sql
SELECT
  schemaname,
  tablename,
  indexname,
  pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
  idx_scan,
  idx_tup_read / NULLIF(idx_scan, 0) AS avg_tuples_per_scan
FROM pg_stat_user_indexes
WHERE pg_relation_size(indexrelid) > 100 * 1024 * 1024  -- > 100MB
ORDER BY pg_relation_size(indexrelid) DESC;
```

**인덱스 재구성 필요 여부**:
```sql
SELECT
  schemaname,
  tablename,
  indexname,
  pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
  100 * (pg_relation_size(indexrelid)::numeric / NULLIF(pg_relation_size(indrelid), 0)) AS index_ratio
FROM pg_stat_user_indexes
WHERE pg_relation_size(indexrelid) > pg_relation_size(indrelid)
ORDER BY pg_relation_size(indexrelid) DESC;
```

### 3.4 정기 유지보수

**주간 ANALYZE**:
```sql
-- 통계 업데이트 (쿼리 플래너 최적화)
ANALYZE judgment_executions;
ANALYZE workflow_instances;
ANALYZE fact_daily_production;
```

**월간 REINDEX**:
```sql
-- 인덱스 재구성 (bloat 제거)
REINDEX TABLE CONCURRENTLY judgment_executions;
REINDEX TABLE CONCURRENTLY workflow_instances;
REINDEX INDEX CONCURRENTLY idx_rag_embeddings_vector;
```

**자동 VACUUM 튜닝**:
```sql
-- 테이블별 autovacuum 조정
ALTER TABLE judgment_executions SET (
  autovacuum_vacuum_scale_factor = 0.05,  -- 5% 변경 시 vacuum
  autovacuum_analyze_scale_factor = 0.05
);

ALTER TABLE llm_calls SET (
  autovacuum_vacuum_scale_factor = 0.1,
  autovacuum_analyze_scale_factor = 0.1
);
```

---

## 4. 마이그레이션 관리

### 4.1 마이그레이션 도구 선택

**도구 비교**:
| 도구 | 언어 | 장점 | 단점 | 권장 용도 |
|------|------|------|------|-----------|
| Alembic | Python | SQLAlchemy 통합, 자동 생성 | Python 의존성 | Python 백엔드 |
| Flyway | Java/Any | SQL 기반, 언어 무관 | 자동 생성 없음 | 다중 언어 |
| Prisma Migrate | TypeScript | ORM 통합, 타입 안전 | Node.js 전용 | TypeScript 백엔드 |
| Liquibase | XML/SQL | 엔터프라이즈급 기능 | 복잡한 설정 | 엔터프라이즈 |

**권장**: **Alembic** (Python 백엔드) 또는 **Flyway** (언어 무관)

### 4.2 Alembic 설정 예시

**디렉토리 구조**:
```
migrations/
├── alembic.ini
├── env.py
├── script.py.mako
└── versions/
    ├── 001_initial_schema.py
    ├── 002_add_judgment_cache.py
    └── 003_add_rag_tables.py
```

**alembic.ini**:
```ini
[alembic]
script_location = migrations
sqlalchemy.url = postgresql://user:pass@localhost/ai_factory

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic
```

**마이그레이션 스크립트 예시**:
```python
# migrations/versions/001_initial_schema.py
"""initial schema

Revision ID: 001
Revises:
Create Date: 2025-01-26

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # tenants
    op.create_table(
        'tenants',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('name', sa.Text(), nullable=False, unique=True),
        sa.Column('display_name', sa.Text(), nullable=False),
        sa.Column('settings', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('idx_tenants_name', 'tenants', ['name'])

    # users
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('tenant_id', sa.UUID(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.Text(), nullable=False),
        sa.Column('role', sa.Text(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('idx_users_tenant_role', 'users', ['tenant_id', 'role'])

def downgrade():
    op.drop_table('users')
    op.drop_table('tenants')
```

### 4.3 마이그레이션 규칙

**DO**:
- ✅ 스키마 변경은 반드시 마이그레이션 스크립트로 관리
- ✅ up/down 모두 작성 (롤백 가능하도록)
- ✅ 배포 전 dry-run 실행
- ✅ 트랜잭션 내에서 실행 (가능한 경우)
- ✅ 인덱스/제약조건까지 포함
- ✅ 시드 데이터는 별도 스크립트

**DON'T**:
- ❌ 프로덕션 DB에 직접 DDL 실행
- ❌ 마이그레이션 스크립트 수정 (새 버전 생성)
- ❌ down 없이 up만 작성
- ❌ 테이블 drop 후 재생성 (데이터 손실)

### 4.4 무중단 마이그레이션 전략

**컬럼 추가**:
```sql
-- 1단계: NULL 허용 컬럼 추가
ALTER TABLE judgment_executions ADD COLUMN new_field text;

-- 2단계: 기본값 설정 (백그라운드)
UPDATE judgment_executions SET new_field = 'default' WHERE new_field IS NULL;

-- 3단계: NOT NULL 제약 추가
ALTER TABLE judgment_executions ALTER COLUMN new_field SET NOT NULL;
```

**인덱스 생성**:
```sql
-- CONCURRENTLY 옵션으로 잠금 없이 생성
CREATE INDEX CONCURRENTLY idx_new_field ON judgment_executions (new_field);
```

**컬럼 삭제**:
```sql
-- 1단계: 컬럼 사용 중단 (애플리케이션 배포)
-- 2단계: 모니터링 (1주일)
-- 3단계: 컬럼 삭제
ALTER TABLE judgment_executions DROP COLUMN old_field;
```

---

## 5. 백업 및 복구

### 5.1 백업 전략

**3-2-1 백업 전략**:
- **3**: 3개 복사본
- **2**: 2가지 다른 미디어
- **1**: 1개는 오프사이트

**백업 종류**:
| 백업 종류 | 주기 | 보관 기간 | 복구 시간 | 용도 |
|----------|------|-----------|----------|------|
| 전체 백업 | 일일 | 30일 | 4-6시간 | 재해 복구 |
| 증분 백업 | 6시간 | 7일 | 1-2시간 | 빠른 복구 |
| WAL 아카이빙 | 연속 | 30일 | 분 단위 | PITR |
| 파티션 백업 | 주간 | 90일 | 파티션별 | 부분 복구 |
| 스냅샷 | 배포 전 | 7일 | 즉시 | 롤백 |

### 5.2 pg_dump 백업

**전체 백업**:
```bash
#!/bin/bash
# daily_backup.sh

BACKUP_DIR="/backup/postgres"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_NAME="ai_factory"

# 전체 백업 (압축)
pg_dump -h localhost -U postgres -F c -b -v \
  -f "${BACKUP_DIR}/full_${DB_NAME}_${TIMESTAMP}.dump" \
  ${DB_NAME}

# 오래된 백업 삭제 (30일 이상)
find ${BACKUP_DIR} -name "full_*.dump" -mtime +30 -delete

# S3 업로드 (오프사이트)
aws s3 cp "${BACKUP_DIR}/full_${DB_NAME}_${TIMESTAMP}.dump" \
  s3://ai-factory-backups/postgres/
```

**파티션별 백업**:
```bash
# 특정 파티션만 백업
pg_dump -h localhost -U postgres \
  -t judgment_executions_y2025m01 \
  -f backup_partition_202501.sql \
  ai_factory
```

**스키마만 백업**:
```bash
pg_dump -h localhost -U postgres -s \
  -f schema_only.sql ai_factory
```

### 5.3 WAL 아카이빙 (PITR)

**postgresql.conf 설정**:
```conf
wal_level = replica
archive_mode = on
archive_command = 'test ! -f /backup/wal_archive/%f && cp %p /backup/wal_archive/%f'
archive_timeout = 300  # 5분마다 WAL 전환
max_wal_senders = 5
```

**Point-In-Time Recovery**:
```bash
# 1단계: 베이스 백업 복원
pg_restore -h localhost -U postgres -d ai_factory \
  /backup/full_ai_factory_20250126.dump

# 2단계: recovery.conf 생성
cat > recovery.conf <<EOF
restore_command = 'cp /backup/wal_archive/%f %p'
recovery_target_time = '2025-01-26 14:30:00'
EOF

# 3단계: PostgreSQL 재시작
pg_ctl restart
```

### 5.4 복구 절차

**시나리오 1: 테이블 삭제 복구**:
```bash
# 특정 테이블만 복원
pg_restore -h localhost -U postgres -d ai_factory \
  -t judgment_executions \
  /backup/full_ai_factory_20250126.dump
```

**시나리오 2: 데이터베이스 전체 복구**:
```bash
# 1단계: 기존 DB 삭제
dropdb -h localhost -U postgres ai_factory

# 2단계: 새 DB 생성
createdb -h localhost -U postgres ai_factory

# 3단계: 백업 복원
pg_restore -h localhost -U postgres -d ai_factory \
  /backup/full_ai_factory_20250126.dump
```

**시나리오 3: 특정 시점 복구 (PITR)**:
```bash
# 위 WAL 아카이빙 섹션 참조
```

### 5.5 백업 검증

**월간 백업 복구 테스트**:
```bash
#!/bin/bash
# test_restore.sh

# 테스트 DB 생성
createdb -h localhost -U postgres ai_factory_test

# 최신 백업 복원
LATEST_BACKUP=$(ls -t /backup/full_*.dump | head -1)
pg_restore -h localhost -U postgres -d ai_factory_test ${LATEST_BACKUP}

# 데이터 검증
psql -h localhost -U postgres -d ai_factory_test -c "
SELECT
  (SELECT count(*) FROM tenants) AS tenant_count,
  (SELECT count(*) FROM users) AS user_count,
  (SELECT count(*) FROM judgment_executions) AS judgment_count;
"

# 테스트 DB 삭제
dropdb -h localhost -U postgres ai_factory_test
```

---

## 6. 데이터 라이프사이클

### 6.1 데이터 보관 정책

| 데이터 타입 | 핫 스토리지 | 콜드 스토리지 | 삭제 |
|------------|-----------|-------------|------|
| RAW 데이터 | 90일 | 1년 | 1년 후 |
| 판단 실행 이력 | 2년 | 5년 | 5년 후 (규제 시 연장) |
| 워크플로우 로그 | 1년 | - | 1년 후 |
| LLM 호출 로그 | 180일 | 1년 | 1년 후 |
| 감사 로그 | 5년 | 10년 | 10년 후 |
| BI FACT | 2년 | 5년 | 5년 후 |
| RAG 문서 | 영구 | - | 수동 삭제 |

### 6.2 콜드 스토리지 이전

**파티션 Export**:
```bash
#!/bin/bash
# archive_partition.sh

TABLE_NAME="raw_mes_production"
PARTITION_NAME="raw_mes_production_y2024m10"
ARCHIVE_DIR="/archive/postgres"

# 1단계: 파티션 Export
pg_dump -h localhost -U postgres -t ${PARTITION_NAME} \
  -f "${ARCHIVE_DIR}/${PARTITION_NAME}.sql.gz" \
  ai_factory

# 2단계: S3 업로드
aws s3 cp "${ARCHIVE_DIR}/${PARTITION_NAME}.sql.gz" \
  s3://ai-factory-archive/postgres/

# 3단계: Detach 파티션
psql -h localhost -U postgres -d ai_factory -c "
ALTER TABLE ${TABLE_NAME} DETACH PARTITION ${PARTITION_NAME};
"

# 4단계: Drop 파티션
psql -h localhost -U postgres -d ai_factory -c "
DROP TABLE ${PARTITION_NAME};
"
```

### 6.3 데이터 삭제 정책

**자동 삭제 배치**:
```sql
-- 180일 이상 LLM 호출 로그 삭제
DELETE FROM llm_calls
WHERE created_at < CURRENT_DATE - INTERVAL '180 days';

-- 만료된 캐시 삭제
DELETE FROM judgment_cache
WHERE expires_at < now();

-- 만료된 메모리 삭제
DELETE FROM memories
WHERE expires_at IS NOT NULL AND expires_at < now();
```

### 6.4 개인정보 마스킹/익명화

**PII 필드 마스킹**:
```sql
-- 1년 이상 된 사용자 이메일 마스킹
UPDATE users
SET email = 'masked_' || id || '@example.com'
WHERE created_at < CURRENT_DATE - INTERVAL '1 year'
  AND email NOT LIKE 'masked_%';

-- 감사 로그 IP 주소 익명화
UPDATE audit_logs
SET ip_address = inet '0.0.0.0'
WHERE created_at < CURRENT_DATE - INTERVAL '5 years';
```

---

## 7. 성능 모니터링

### 7.1 핵심 모니터링 지표

**데이터베이스 전체**:
```sql
-- 커넥션 상태
SELECT
  count(*) AS total_connections,
  count(*) FILTER (WHERE state = 'active') AS active_connections,
  count(*) FILTER (WHERE state = 'idle') AS idle_connections,
  count(*) FILTER (WHERE wait_event_type IS NOT NULL) AS waiting_connections
FROM pg_stat_activity
WHERE datname = 'ai_factory';

-- 트랜잭션 처리량
SELECT
  datname,
  xact_commit,
  xact_rollback,
  xact_commit + xact_rollback AS total_xacts,
  ROUND(100.0 * xact_commit / NULLIF(xact_commit + xact_rollback, 0), 2) AS commit_ratio
FROM pg_stat_database
WHERE datname = 'ai_factory';

-- 캐시 히트율
SELECT
  sum(heap_blks_read) AS heap_read,
  sum(heap_blks_hit) AS heap_hit,
  ROUND(100.0 * sum(heap_blks_hit) / NULLIF(sum(heap_blks_hit) + sum(heap_blks_read), 0), 2) AS cache_hit_ratio
FROM pg_statio_user_tables;
```

**테이블별 통계**:
```sql
SELECT
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
  n_live_tup AS live_rows,
  n_dead_tup AS dead_rows,
  ROUND(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) AS dead_ratio,
  last_vacuum,
  last_autovacuum,
  last_analyze
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 20;
```

**느린 쿼리 탐지** (pg_stat_statements):
```sql
SELECT
  query,
  calls,
  ROUND(total_exec_time::numeric / 1000, 2) AS total_time_sec,
  ROUND(mean_exec_time::numeric, 2) AS avg_time_ms,
  ROUND((100 * total_exec_time / sum(total_exec_time) OVER ())::numeric, 2) AS pct_total_time,
  rows
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat%'
ORDER BY total_exec_time DESC
LIMIT 20;
```

**잠금 대기**:
```sql
SELECT
  blocked_locks.pid AS blocked_pid,
  blocked_activity.usename AS blocked_user,
  blocking_locks.pid AS blocking_pid,
  blocking_activity.usename AS blocking_user,
  blocked_activity.query AS blocked_statement,
  blocking_activity.query AS blocking_statement
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
  AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
  AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
  AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
  AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
  AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
  AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
  AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
  AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
  AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
  AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
```

### 7.2 Prometheus Exporter

**postgres_exporter 설정**:
```yaml
# queries.yaml
pg_database:
  query: "SELECT datname, xact_commit, xact_rollback FROM pg_stat_database WHERE datname = 'ai_factory'"
  metrics:
    - datname:
        usage: "LABEL"
        description: "Database name"
    - xact_commit:
        usage: "COUNTER"
        description: "Transactions committed"
    - xact_rollback:
        usage: "COUNTER"
        description: "Transactions rolled back"

pg_judgment_executions:
  query: "SELECT result, COUNT(*) AS count FROM judgment_executions WHERE created_at > now() - INTERVAL '1 hour' GROUP BY result"
  metrics:
    - result:
        usage: "LABEL"
        description: "Judgment result"
    - count:
        usage: "GAUGE"
        description: "Judgment count"
```

### 7.3 알람 설정

**Grafana 알람 규칙**:
```yaml
# alerts.yaml
- alert: HighDatabaseConnections
  expr: pg_stat_activity_count{state="active"} > 80
  for: 5m
  annotations:
    summary: "High database connections ({{ $value }})"

- alert: LowCacheHitRatio
  expr: pg_cache_hit_ratio < 90
  for: 10m
  annotations:
    summary: "Low cache hit ratio ({{ $value }}%)"

- alert: SlowJudgmentQueries
  expr: histogram_quantile(0.95, pg_stat_statements_mean_exec_time{query=~".*judgment_executions.*"}) > 500
  for: 5m
  annotations:
    summary: "Slow judgment queries (p95 > 500ms)"

- alert: HighDeadTupleRatio
  expr: 100 * pg_stat_user_tables_n_dead_tup / (pg_stat_user_tables_n_live_tup + pg_stat_user_tables_n_dead_tup) > 20
  for: 30m
  annotations:
    summary: "High dead tuple ratio ({{ $value }}%)"
```

---

## 8. 용량 계획

### 8.1 용량 산정

**테이블별 예상 크기 (연간)**:
| 테이블 | 예상 행 수 | 행 크기 | 인덱스 비율 | 총 크기 |
|--------|-----------|---------|------------|---------|
| judgment_executions | 18M | 2KB | 100% | ~72GB |
| workflow_instances | 5M | 1KB | 80% | ~9GB |
| llm_calls | 36M | 500B | 50% | ~27GB |
| raw_mes_production | 100M | 1KB | 30% | ~130GB |
| fact_daily_production | 10M | 300B | 50% | ~4.5GB |
| rag_documents | 100k | 2KB | 50% | ~300MB |
| rag_embeddings | 100k | 6KB | 100% | ~1.2GB |
| **총계** | | | | **~250GB** |

**증가율**: 연간 20% 증가 예상
- 1년차: 250GB
- 2년차: 300GB
- 3년차: 360GB

### 8.2 디스크 공간 모니터링

```sql
-- 데이터베이스 총 크기
SELECT
  pg_size_pretty(pg_database_size('ai_factory')) AS db_size;

-- 테이블별 크기
SELECT
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
  pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) AS index_size
FROM pg_catalog.pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 20;

-- 파티션별 크기
SELECT
  parent.relname AS parent_table,
  child.relname AS partition_name,
  pg_size_pretty(pg_relation_size(child.oid)) AS partition_size
FROM pg_inherits
JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
JOIN pg_class child ON pg_inherits.inhrelid = child.oid
WHERE parent.relname = 'judgment_executions'
ORDER BY pg_relation_size(child.oid) DESC;
```

### 8.3 용량 최적화

**테이블 bloat 제거**:
```sql
-- bloat 확인
SELECT
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
  ROUND(100 * (pg_total_relation_size(schemaname||'.'||tablename)::numeric - pg_relation_size(schemaname||'.'||tablename)) / NULLIF(pg_total_relation_size(schemaname||'.'||tablename), 0), 2) AS bloat_pct
FROM pg_stat_user_tables
WHERE pg_total_relation_size(schemaname||'.'||tablename) > 100 * 1024 * 1024
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- bloat 제거 (VACUUM FULL - 주의: 락 발생)
VACUUM FULL judgment_executions;
```

**압축 활용**:
```sql
-- TOAST 압축 설정
ALTER TABLE judgment_executions ALTER COLUMN input_data SET STORAGE EXTENDED;
ALTER TABLE judgment_executions ALTER COLUMN evidence SET STORAGE EXTENDED;
```

---

## 9. 운영 절차

### 9.1 일일 점검

```bash
#!/bin/bash
# daily_health_check.sh

# 1. 커넥션 수
psql -c "SELECT count(*) AS connections FROM pg_stat_activity WHERE datname = 'ai_factory';"

# 2. 캐시 히트율
psql -c "SELECT ROUND(100.0 * sum(heap_blks_hit) / NULLIF(sum(heap_blks_hit) + sum(heap_blks_read), 0), 2) AS cache_hit_ratio FROM pg_statio_user_tables;"

# 3. Dead tuple 비율
psql -c "SELECT tablename, ROUND(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) AS dead_ratio FROM pg_stat_user_tables WHERE n_dead_tup > 1000 ORDER BY dead_ratio DESC LIMIT 10;"

# 4. 디스크 사용량
df -h /var/lib/postgresql/data

# 5. 백업 확인
ls -lh /backup/postgres/full_*.dump | tail -1
```

### 9.2 주간 점검

- ANALYZE 실행
- 미사용 인덱스 점검
- 느린 쿼리 분석
- 파티션 생성 확인

### 9.3 월간 점검

- REINDEX 실행
- 백업 복구 테스트
- 용량 트렌드 분석
- 파티션 아카이빙

---

## 10. 트러블슈팅

### 10.1 성능 저하

**증상**: 쿼리 응답 시간 증가

**진단**:
```sql
-- 1. 캐시 히트율 확인
SELECT ROUND(100.0 * sum(heap_blks_hit) / NULLIF(sum(heap_blks_hit) + sum(heap_blks_read), 0), 2) AS cache_hit_ratio FROM pg_statio_user_tables;

-- 2. 느린 쿼리 식별
SELECT query, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;

-- 3. 인덱스 사용 확인
SELECT tablename, indexname, idx_scan FROM pg_stat_user_indexes WHERE idx_scan = 0;
```

**조치**:
- 캐시 히트율 < 90%: shared_buffers 증가
- 느린 쿼리: 인덱스 추가, 쿼리 최적화
- 미사용 인덱스: DROP

### 10.2 디스크 공간 부족

**증상**: 디스크 사용률 > 85%

**진단**:
```sql
-- 큰 테이블 식별
SELECT tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC LIMIT 10;
```

**조치**:
- 오래된 파티션 아카이빙
- VACUUM FULL 실행
- 로그 테이블 정리

### 10.3 커넥션 고갈

**증상**: `FATAL: remaining connection slots are reserved`

**진단**:
```sql
SELECT count(*), state FROM pg_stat_activity GROUP BY state;
```

**조치**:
- max_connections 증가
- 커넥션 풀 설정 조정
- idle 커넥션 타임아웃 설정

---

## 부록 A. PostgreSQL 설정 권장값

```conf
# postgresql.conf

# 메모리
shared_buffers = 8GB             # RAM의 25%
effective_cache_size = 24GB      # RAM의 75%
work_mem = 64MB
maintenance_work_mem = 1GB

# WAL
wal_buffers = 16MB
checkpoint_completion_target = 0.9
max_wal_size = 4GB
min_wal_size = 1GB

# 쿼리 플래너
random_page_cost = 1.1           # SSD
effective_io_concurrency = 200   # SSD

# 로깅
log_min_duration_statement = 1000  # 1초 이상 쿼리 로깅
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
log_checkpoints = on
log_connections = on
log_disconnections = on
log_lock_waits = on

# 통계
shared_preload_libraries = 'pg_stat_statements'
pg_stat_statements.track = all
```

---

## 부록 B. 체크리스트

### 배포 전 체크리스트
- [ ] 마이그레이션 스크립트 dry-run 실행
- [ ] 백업 생성 및 검증
- [ ] 롤백 계획 수립
- [ ] 파티션 생성 확인
- [ ] 인덱스 생성 완료

### 운영 체크리스트
- [ ] 일일 백업 확인
- [ ] 주간 ANALYZE 실행
- [ ] 월간 REINDEX 실행
- [ ] 분기별 백업 복구 테스트
- [ ] 연간 용량 계획 검토

---

**문서 버전**: 2.0
**최종 검토**: 2025-01-26
**승인자**: AI Factory DevOps Team
