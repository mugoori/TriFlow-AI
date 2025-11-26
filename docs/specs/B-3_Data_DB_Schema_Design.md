# B-3. Data & DB Schema Design

## 1. 데이터 도메인 정의
- **운영 데이터**: 생산/품질/설비/재고(ERP/MES/센서)
- **판단/워크플로우**: judgment_executions, workflow_instances/logs, rulesets
- **학습/프롬프트/배포**: feedbacks, training_samples, auto_rule_candidates, prompt_templates, llm_calls, **rule_deployments**
- **BI/집계**: raw_* → dim_* → fact_* (daily/shift/line), pre-agg views
- **RAG/메모리**: rag_documents/embeddings, memories
- **AAS 매핑**: aas_assets/submodels/elements/source_mappings

## 2. 논리 모델(핵심 테이블 요약)
### 기초 테넌트/설정
- `tenants(id uuid PK, name text, settings jsonb, created_at)` — 멀티테넌시 기준
- `users(id uuid PK, tenant_id FK, email text unique, role text, status text, created_at)`
- `data_connectors(id uuid PK, tenant_id FK, type text, engine text, config jsonb, status text, last_health_at)`
- `mcp_servers(id uuid PK, tenant_id FK, name text, endpoint text, config jsonb, status text, last_health_at)`
- `mcp_tools(id uuid PK, mcp_server_id FK, tool_name text, schema jsonb, description text)`

### 운영/집계 데이터
- RAW: `raw_mes_production(id uuid PK, tenant_id FK, src_system text, src_table text, src_pk text, payload jsonb, event_time timestamptz, created_at)` *(raw_erp_order, raw_inventory 등 유사)*
- DIM:
  - `dim_date(date PK, year, month, week, dow, is_weekend)`
  - `dim_line(tenant_id, line_code PK, name, category, capacity, timezone, is_active)`
  - `dim_product(tenant_id, product_code PK, name, spec, category, unit, is_active)`
  - `dim_equipment(tenant_id, equipment_code PK, line_code FK, name, vendor, install_date, is_active)`
  - `dim_kpi(tenant_id, kpi_code PK, name, unit, description, default_target)`
- FACT (일/교대 기준):
  - `fact_daily_production(tenant_id, date, line_code, product_code, shift, total_qty, good_qty, defect_qty, cycle_time_avg, runtime_minutes, downtime_minutes)`
  - `fact_daily_defect(tenant_id, date, line_code, product_code, shift, defect_rate, top_defect_type jsonb)`
  - `fact_inventory_snapshot(tenant_id, date, product_code, location, stock_qty, safety_stock_qty)`
  - `fact_event_log(tenant_id, date, equipment_code, event_type, count, duration_minutes)`
  - **Pre-agg 뷰**: `mv_defect_trend`, `mv_oee_daily` 등 materialized view로 제공

### 판단/워크플로우/학습/배포
- `workflows(id uuid PK, tenant_id FK, name, description, version int, is_active bool, created_at)`
- `workflow_steps(id uuid PK, workflow_id FK, step_order int, type text, config jsonb, created_at)`
- `workflow_instances(id uuid PK, workflow_id FK, tenant_id FK, status text, context jsonb, started_at, ended_at, last_error text)`
- `judgment_executions(id uuid PK, tenant_id FK, workflow_id FK, source text, input_data jsonb, result text, confidence float, method_used text, explanation text, recommended_actions jsonb, rule_trace jsonb, llm_metadata jsonb, evidence jsonb, feature_importance jsonb, cache_hit bool, created_at)`
- `rulesets(id uuid PK, tenant_id FK, name text, target_kpi text, is_active bool, created_at); rule_scripts(id uuid PK, ruleset_id FK, version int, language text, script text, created_at)`
- `feedbacks(id uuid PK, tenant_id FK, judgment_execution_id FK, user_id FK, feedback text, comment text, created_at)`
- `learning_samples(id uuid PK, tenant_id FK, judgment_execution_id FK, input_features jsonb, label jsonb, source text, created_at)`
- `auto_rule_candidates(id uuid PK, tenant_id FK, ruleset_id FK, generated_rule text, coverage float, precision float, conflict_with text[], is_approved bool, created_at)`
- **`rule_deployments(id uuid PK, tenant_id FK, ruleset_id FK, version int, approver text, changelog text, canary_pct float, rollback_to int, created_at, status text)`**
- `prompt_templates(id uuid PK, tenant_id FK, purpose text, version int, metadata jsonb); prompt_template_bodies(id uuid PK, template_id FK, locale text, body text)`
- `llm_calls(id uuid PK, tenant_id FK, call_type text, model text, prompt_summary text, tokens_prompt int, tokens_completion int, cost_estimate numeric, success bool, validation_error bool, created_at)`
- **`chat_sessions(id uuid PK, tenant_id FK, user_id FK, title text, created_at, updated_at)`**
- **`chat_messages(id uuid PK, session_id FK, role text, content text, intent_log_id FK, created_at)`**
- **`intent_logs(id uuid PK, tenant_id FK, user_query text, predicted_intent text, confidence float, extracted_slots jsonb, feedback_score int, feedback_comment text, created_at)`**

### RAG/메모리/AAS
- `rag_documents(id uuid PK, tenant_id FK, source_type text, source_id text, title text, section text, chunk_index int, text, metadata jsonb, is_active bool)`
- `rag_embeddings(doc_id PK/FK, embedding vector(1536))` (pgvector)
- `memories(id uuid PK, tenant_id FK, type text, key text, value jsonb, importance int, expires_at)`
- `aas_assets(id uuid PK, tenant_id FK, asset_id text, asset_type text, ref_code text, name text, metadata jsonb)`
- `aas_submodels(id uuid PK, asset_id FK, submodel_id text, name text, category text, description text)`
- `aas_elements(id uuid PK, submodel_id FK, element_id text, name text, datatype text, unit text, description text)`
- `aas_source_mappings(id uuid PK, tenant_id FK, element_id FK, source_type text, source_table text, source_column text, filter_expr text, aggregation text, transform_expr text, description text)`

## 3. 주요 테이블 상세(예시)
- **judgment_executions**  
  - PK: `id uuid`  
  - FK: `tenant_id`, `workflow_id`  
  - 필드: `source text`, `input_data jsonb`, `result text check (in ('normal','warning','critical'))`, `confidence float`, `method_used text`, `explanation text`, `recommended_actions jsonb[]`, `rule_trace jsonb`, `llm_metadata jsonb`, `evidence jsonb`(data_refs/urls), `feature_importance jsonb`, `cache_hit bool`, `created_at timestamptz`  
  - 인덱스: `(tenant_id, created_at DESC)`, `(tenant_id, workflow_id, created_at DESC)`, GIN on `input_data`, `evidence`
- **workflows / workflow_steps / workflow_instances**  
  - `workflows`: PK `id`, `version int`, `is_active bool`, `dsl_digest text`(변경 추적)  
  - `workflow_steps`: `step_order int`, `type text check (in ('DATA','BI','MCP','JUDGMENT','ACTION','APPROVAL','WAIT','SWITCH','PARALLEL','COMPENSATION','DEPLOY','ROLLBACK','SIMULATE'))`  
  - `workflow_instances`: `status text check (in ('PENDING','RUNNING','WAITING','COMPLETED','FAILED','CANCELLED','TIMEOUT'))`, `context jsonb`, `last_error text`, 인덱스 `(tenant_id, status)`, `(tenant_id, started_at DESC)`
- **fact_daily_production**  
  - PK `(tenant_id, date, line_code, product_code, shift)`  
  - 인덱스 `(tenant_id, date)`, `(tenant_id, line_code, date)`  
  - 필드: `total_qty numeric`, `good_qty numeric`, `defect_qty numeric`, `cycle_time_avg numeric`, `runtime_minutes numeric`, `downtime_minutes numeric`
- **rulesets / rule_scripts / rule_deployments**  
  - `rule_scripts`: `version int`, `language text check (in ('rhai'))`, `script text`, `created_at`  
  - `rule_deployments`: `status text check (in ('draft','canary','active','rolled_back'))`, `canary_pct float`, `rollback_to int`, `changelog text`, `approver text`, `created_at`
- **catalog/BI** (선택적 확장)  
  - `bi_datasets(id, tenant_id, name, source_type, source_ref, default_filters jsonb)`  
  - `bi_metrics(id, tenant_id, name, dataset_id, expression_sql text, agg_type text, default_chart text)`  
  - `bi_components(id, tenant_id, type text, required_fields jsonb, options_schema jsonb)`

## 4. 인덱스/파티셔닝 전략
- 대용량 테이블(raw_*, fact_*, judgment_executions, logs): `PARTITION BY RANGE (date/event_time)`; 보관/삭제 정책과 연계
- 검색 패턴에 맞는 복합 인덱스: (tenant_id, date), (tenant_id, workflow_id, created_at DESC), (tenant_id, status) for instances
- pgvector: cosine index on rag_embeddings(embedding)
- JSONB: 필요한 필드에 GIN 인덱스 (예: input_data->'line', evidence)
- MV/Pre-agg: materialized view는 `REFRESH CONCURRENTLY` + 인덱스 적용

## 5. 데이터 라이프사이클
1) 수집: connectors/MCP → raw_* 적재 (스키마 검증/DDL 캐시)  
2) 정제/집계: ETL 스케줄(raw→dim→fact), Pre-agg view(materialized view)  
3) 사용: Judgment/BI/Workflow에서 fact/pre-agg 조회 + RAG/AAS context refs  
4) 아카이빙: raw/log 90일 후 cold storage, 판단 로그 2년 보관 (규제 시 연장)  
5) 삭제/익명화: 보존기간 만료 시 삭제/마스킹; PII 컬럼 대상 정책 적용

## 6. 로그/트레이스 구조
- **판단 로그**: id, tenant_id, workflow_id, policy_id, rule_version, prompt_version, model, latency, cache_hit, error_code
- **WF 실행 로그**: instance_id, step_id, status, start/end, retry_count, error, output digest, circuit_breaker_event
- **LLM 호출 로그**: call_type, model, tokens, cost_estimate, success/fail, validation_error 여부
- **감사/보안 로그**: 사용자 권한 변경, 커넥터 등록/수정, Rule/Prompt 배포 이력, Webhook 서명 실패

## 7. 핵심 테이블 DDL 스니펫 (초안)
```sql
CREATE TABLE judgment_executions (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  workflow_id uuid NOT NULL,
  source text,
  input_data jsonb NOT NULL,
  result text CHECK (result IN ('normal','warning','critical')),
  confidence double precision,
  method_used text,
  explanation text,
  recommended_actions jsonb,
  rule_trace jsonb,
  llm_metadata jsonb,
  evidence jsonb,
  feature_importance jsonb,
  cache_hit boolean DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON judgment_executions (tenant_id, created_at DESC);
CREATE INDEX ON judgment_executions (tenant_id, workflow_id, created_at DESC);
CREATE INDEX ON judgment_executions USING GIN (input_data);
```
```sql
CREATE TABLE workflows (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  name text NOT NULL,
  description text,
  version int NOT NULL,
  dsl_digest text,
  is_active boolean DEFAULT false,
  created_at timestamptz DEFAULT now()
);
CREATE TABLE workflow_steps (
  id uuid PRIMARY KEY,
  workflow_id uuid REFERENCES workflows(id),
  step_order int NOT NULL,
  type text CHECK (type IN ('DATA','BI','MCP','JUDGMENT','ACTION','APPROVAL','WAIT','SWITCH','PARALLEL','COMPENSATION','DEPLOY','ROLLBACK','SIMULATE')),
  config jsonb NOT NULL,
  created_at timestamptz DEFAULT now()
);
CREATE TABLE workflow_instances (
  id uuid PRIMARY KEY,
  workflow_id uuid REFERENCES workflows(id),
  tenant_id uuid NOT NULL,
  status text CHECK (status IN ('PENDING','RUNNING','WAITING','COMPLETED','FAILED','CANCELLED','TIMEOUT')),
  context jsonb,
  last_error text,
  started_at timestamptz,
  ended_at timestamptz
);
CREATE INDEX ON workflow_instances (tenant_id, status);
CREATE INDEX ON workflow_instances (tenant_id, started_at DESC);
```
```sql
CREATE TABLE rulesets (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  name text,
  target_kpi text,
  is_active boolean DEFAULT false,
  created_at timestamptz DEFAULT now()
);
CREATE TABLE rule_scripts (
  id uuid PRIMARY KEY,
  ruleset_id uuid REFERENCES rulesets(id),
  version int NOT NULL,
  language text CHECK (language = 'rhai'),
  script text NOT NULL,
  created_at timestamptz DEFAULT now()
);
CREATE TABLE rule_deployments (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  ruleset_id uuid REFERENCES rulesets(id),
  version int,
  approver text,
  changelog text,
  canary_pct numeric,
  rollback_to int,
  status text CHECK (status IN ('draft','canary','active','rolled_back')),
  created_at timestamptz DEFAULT now()
);
```
```sql
CREATE TABLE fact_daily_production (
  tenant_id uuid NOT NULL,
  date date NOT NULL,
  line_code text NOT NULL,
  product_code text NOT NULL,
  shift text,
  total_qty numeric,
  good_qty numeric,
  defect_qty numeric,
  cycle_time_avg numeric,
  runtime_minutes numeric,
  downtime_minutes numeric,
  PRIMARY KEY (tenant_id, date, line_code, product_code, shift)
);
CREATE INDEX ON fact_daily_production (tenant_id, date);
CREATE INDEX ON fact_daily_production (tenant_id, line_code, date);
```
```sql
CREATE TABLE rag_documents (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  source_type text,
  source_id text,
  title text,
  section text,
  chunk_index int,
  text text,
  metadata jsonb,
  is_active boolean DEFAULT true
);
CREATE TABLE rag_embeddings (
  doc_id uuid PRIMARY KEY REFERENCES rag_documents(id),
  embedding vector(1536)
);
CREATE INDEX ON rag_embeddings USING ivfflat (embedding vector_cosine_ops);
```

```sql
-- BI 카탈로그
CREATE TABLE bi_datasets (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  name text NOT NULL,
  source_type text CHECK (source_type IN ('postgres','aggregation_service')),
  source_ref text NOT NULL,
  default_filters jsonb
);
CREATE TABLE bi_metrics (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  name text NOT NULL,
  dataset_id uuid REFERENCES bi_datasets(id),
  expression_sql text,
  agg_type text,
  default_chart text
);
CREATE TABLE bi_components (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  type text,
  required_fields jsonb,
  options_schema jsonb
);
```

```sql
-- 감사/액세스 로그 (요약)
CREATE TABLE audit_logs (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  actor text,
  action text,
  target_type text,
  target_id text,
  before jsonb,
  after jsonb,
  trace_id text,
  created_at timestamptz DEFAULT now()
);
CREATE INDEX ON audit_logs (tenant_id, created_at DESC);
CREATE INDEX ON audit_logs (tenant_id, target_type, target_id);
```

```sql
-- 파티션 템플릿 예시 (judgment_executions by month)
CREATE TABLE judgment_executions_y2025m11 PARTITION OF judgment_executions
FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');
-- 월별 자동 생성 스크립트(마이그레이션/배치에서 실행)
```

## 8. 스토리지/성능 가이드 (초안)
- 초기 가정: 테넌트 5, 라인 20, 일일 판단 50k, judgment_executions 1년 ≈ 18M rows → 파티셔닝 필수.
- 로그/LLM 호출: llm_calls 일 100k 기준 180일 핫보관, 이후 콜드 스토리지 이전.
- MV 리프레시: 일/교대 단위 뷰는 1h 주기, 대시보드 피크 시간대 전 리프레시 예약.

## 9. 마이그레이션/시드/백업 전략
- **도구**: Alembic/Flyway/Prisma 중 하나 선택, 스키마 버전 테이블 유지, up/down 스크립트 필수.
- **규칙**: PK/FK/인덱스/체크 제약까지 마이그레이션에 포함, 배포 전 dry-run; 롤백 스크립트 작성.
- **시드 데이터**: dim_date, dim_kpi, 기본 roles, 샘플 workflow/ruleset/bi_catalog; 환경별 시드 분리.
- **백업**: Postgres WAL+일일 전체 스냅샷, 파티션 단위 백업 허용; 백업 무결성 주간 검증(샘플 복구).

## 10. 데이터 검증/품질 체크 (예시 쿼리)
```sql
-- 필수 외래키 orphan 검사
SELECT e.id FROM judgment_executions e
LEFT JOIN workflows w ON w.id = e.workflow_id
WHERE w.id IS NULL;
-- 일자/라인 결측 검사
SELECT date, line_code, count(*) FROM fact_daily_production
WHERE total_qty IS NULL OR good_qty IS NULL
GROUP BY date, line_code;
-- 파티션 범위 확인
SELECT inhrelid::regclass AS partition FROM pg_inherits
WHERE inhparent = 'judgment_executions'::regclass;
```

## 11. 예상 용량/성능 가정 (초안)
- judgment_executions: 50k/일/테넌트, 1년 18M rows → 월 파티션 18~20개, 핫스토리지 3~6개월, 콜드 이전.
- llm_calls: 100k/일 → 180일 핫, 이후 오브젝트 스토리지 로테이션.
- 비즈니스 fact 테이블: 라인 20 × 제품 100 × 일 = 2,000 rows/day → 1년 730k rows (pre-agg로 조회).
- 인덱스/파티션 유지보수: 월 1회 REINDEX/ANALYZE, 파티션 드롭/아카이브 작업 배치.
- 예상 응답: 캐시 히트 judgment 300ms, 미스 1.5s; BI pre-agg 2s 이내.

## 12. 추적성 체크리스트 (데이터 ↔ 요구/API/테스트)
- judgment_executions: A-2 JUD-FR ↔ B-4 Judgment API ↔ C-3 TC(리플레이/캐시/파싱) ↔ D-2 지연/파싱 알람.
- workflows/steps/instances: A-2 WF-FR ↔ B-4 Workflow API ↔ B-5 DSL ↔ C-3 TC(장기 실행/승인/DEPLOY) ↔ D-2 실패율/회로차단.
- bi_*: A-2 BI-FR ↔ B-4 BI API ↔ C-3 TC(BI pre-agg) ↔ D-2 BI SLO.
- connectors/mcp_*: A-2 INT/DATA-FR ↔ B-4 MCP/Connector API ↔ C-3 TC(MCP 타임아웃) ↔ D-2 MCP 알람.
- learning_samples/auto_rule_candidates/rule_deployments: A-2 LRN-FR ↔ B-4 Learning API ↔ C-3 TC(canary/충돌) ↔ D-2 품질 지표.
- audit_logs: A-2 SEC/OBS-FR ↔ C-5 보안 정책 ↔ C-3 보안 TC ↔ D-2 보안/감사 로그 보관.

## 14. Pre-agg 뷰 매핑 표 (예시)
| 뷰 이름 | 소스 | 주요 컬럼 | 리프레시 | 용도 |
| --- | --- | --- | --- | --- |
| mv_defect_trend | fact_daily_defect | line, date, defect_rate, top_defect_type | 1h + 피크 전 수동 | 불량 추이/알람 |
| mv_oee_daily | fact_daily_production (조인 dim_line) | line, date, oee, availability, performance, quality | 일 1회(새벽) | OEE 지표/BI |
| mv_inventory_cov | fact_inventory_snapshot | product, date, cov_days | 일 1회 | 재고 커버리지 |

## 15. 캐시/무효화 정책 예시 (DDL/코드 가이드)
- Judgment 캐시 키: `judgment:{workflow_id}:{hash(input_data)}` → ruleset/policy 변경 시 `judgment:*` 또는 정책별 prefix purge.
- BI 캐시 키: `bi:{plan_hash}` → dataset/metric/Pre-agg 뷰 리프레시 시 해당 해시 무효화.
- MCP 캐시(옵션): 읽기 전용 툴에 한정, `mcp:{server}:{tool}:{hash(args)}`, TTL 짧게(1~5분).
- 구현 가이드: 캐시 메타 테이블(optional)로 키/prefix, TTL, 최근 퍼지 내역을 기록해 운영 추적성 확보.
- 코드 스니펫 예시 (Typescript/Redis):
```ts
async function purgePrefix(prefix: string) {
  const keys = await redis.keys(`${prefix}*`);
  if (keys.length) await redis.del(...keys);
}
```

## 16. 파티션/아카이브 배치 예시
- 월별 judgment_executions 파티션 생성 스크립트 (배치):
```sql
DO $$
DECLARE m date := date_trunc('month', now());
BEGIN
  EXECUTE format('CREATE TABLE IF NOT EXISTS judgment_executions_%s PARTITION OF judgment_executions FOR VALUES FROM (%L) TO (%L)',
    to_char(m,'YYYYMM'), m, m + interval '1 month');
END$$;
```
- 파티션 드롭/아카이브: 보존기간 지난 파티션을 Export→드롭, 메타에 기록.


## 13. AAS 매핑 샘플 및 조회 예시
- 매핑 예시
  - aas_assets: asset_id='line:L01', asset_type='line', ref_code='L01'
  - aas_submodels: submodel_id='ProductionQuality', category='production'
  - aas_elements:
    - element_id='daily_defect_rate', datatype='float', unit='%', description='일일 불량률'
    - element_id='oee', datatype='float', unit='%', description='종합설비효율'
  - aas_source_mappings:
    - daily_defect_rate ← fact_daily_defect.defect_rate WHERE line_code=:line AND date=:date
    - oee ← mv_oee_daily.oee WHERE line_code=:line AND date=:date
- 조회 예시 쿼리 (AAS 뷰)
```sql
SELECT ae.element_id, asm.submodel_id, asrc.aggregation, asrc.transform_expr,
       CASE ae.element_id
         WHEN 'daily_defect_rate' THEN (SELECT defect_rate FROM fact_daily_defect WHERE line_code = 'L01' AND date = current_date)
         WHEN 'oee' THEN (SELECT oee FROM mv_oee_daily WHERE line_code = 'L01' AND date = current_date)
       END AS value
FROM aas_elements ae
JOIN aas_submodels asm ON asm.id = ae.submodel_id
JOIN aas_source_mappings asrc ON asrc.element_id = ae.id
WHERE asm.submodel_id = 'ProductionQuality' AND asm.asset_id = (SELECT id FROM aas_assets WHERE ref_code='L01');
```
