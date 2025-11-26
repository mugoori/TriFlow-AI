# C-4. Performance & Capacity Planning - Enhanced

## 문서 정보
- **문서 ID**: C-4
- **버전**: 2.0 (Enhanced)
- **최종 수정일**: 2025-11-26
- **상태**: Draft
- **관련 문서**:
  - A-2 System Requirements Spec (NFR-PERF-*)
  - B-1 System Architecture
  - B-3-4 Performance & Operations
  - C-3 Test Plan (Performance Tests)
  - D-2 Monitoring & Logging

## 목차
1. [성능 목표 및 SLO](#1-성능-목표-및-slo)
2. [성능 설계 전략](#2-성능-설계-전략)
3. [용량 계획 (Capacity Planning)](#3-용량-계획-capacity-planning)
4. [부하 시나리오 및 테스트](#4-부하-시나리오-및-테스트)
5. [성능 최적화 가이드](#5-성능-최적화-가이드)
6. [성능 모니터링 및 알람](#6-성능-모니터링-및-알람)

---

## 1. 성능 목표 및 SLO

### 1.1 Service Level Objectives (SLO)

#### 1.1.1 응답 시간 (Latency)

| 서비스 | 메트릭 | P50 | P95 | P99 | 목표 | 알람 임계값 |
|--------|--------|-----|-----|-----|------|------------|
| **Judgment** (캐시 적중) | `judgment_duration_ms` | 200ms | 300ms | 400ms | < 300ms | P95 > 400ms |
| **Judgment** (Rule Only) | `judgment_duration_ms` | 400ms | 800ms | 1200ms | < 800ms | P95 > 1200ms |
| **Judgment** (Hybrid) | `judgment_duration_ms` | 1500ms | 2500ms | 4000ms | < 2500ms | P95 > 3000ms |
| **BI** (자연어 → SQL) | `bi_plan_duration_ms` | 1000ms | 2000ms | 3000ms | < 2000ms | P95 > 2500ms |
| **BI** (SQL 실행) | `bi_query_duration_ms` | 500ms | 1500ms | 2500ms | < 1500ms | P95 > 2000ms |
| **Workflow** (Simple, 3~5 노드) | `workflow_duration_s` | 5s | 10s | 15s | < 10s | P95 > 12s |
| **Workflow** (Complex, 11~20 노드) | `workflow_duration_s` | 30s | 60s | 90s | < 60s | P95 > 75s |
| **MCP** 호출 | `mcp_call_duration_ms` | 1000ms | 3000ms | 5000ms | < 3000ms | P95 > 4000ms |

#### 1.1.2 처리량 (Throughput)

| 서비스 | 메트릭 | 목표 TPS | 최대 TPS | 동시 요청 | 알람 임계값 |
|--------|--------|----------|---------|-----------|------------|
| **Judgment** | `judgment_requests_total` | 50 | 200 | 100 | 요청 큐 > 50 |
| **Workflow** | `workflow_executions_total` | 20 | 80 | 50 | 인스턴스 대기 > 20 |
| **BI** | `bi_queries_total` | 10 | 40 | 30 | 쿼리 대기 > 10 |
| **MCP Hub** | `mcp_calls_total` | 30 | 100 | 80 | 호출 대기 > 30 |
| **Chat** | `chat_messages_total` | 40 | 150 | 100 | 세션 대기 > 40 |

#### 1.1.3 가용성 (Availability)

| 서비스 | SLO | 허용 다운타임 (월) | 모니터링 |
|--------|-----|------------------|----------|
| **전체 시스템** | 99.9% | 43분 | Uptime 모니터링 |
| **Judgment** | 99.95% | 21분 | Health Check (30초) |
| **PostgreSQL** | 99.99% | 4분 | Patroni, Replication Lag |
| **Redis** | 99.9% | 43분 | Sentinel, Master Check |

---

## 2. 성능 설계 전략

### 2.1 캐싱 전략

#### 2.1.1 계층형 캐시 (L1 + L2)

```
┌────────────────────────────────────────┐
│  L1 Cache (In-Memory, TTL 60s)         │
│  - LRU Cache (1000개)                  │
│  - Hit Ratio: ~20%                     │
│  - Latency: < 10ms                     │
└────────────────────────────────────────┘
         │ (Miss)
         ▼
┌────────────────────────────────────────┐
│  L2 Cache (Redis, TTL 300~600s)        │
│  - Distributed Cache                   │
│  - Hit Ratio: ~40%                     │
│  - Latency: < 50ms                     │
└────────────────────────────────────────┘
         │ (Miss)
         ▼
┌────────────────────────────────────────┐
│  PostgreSQL (Source of Truth)          │
│  - Latency: 100~500ms                  │
└────────────────────────────────────────┘
```

**캐시 TTL 최적화**:

| 데이터 타입 | TTL | 무효화 조건 |
|------------|-----|------------|
| Judgment 결과 | 300s (5분) | Rule/Prompt 배포 |
| BI 쿼리 결과 | 600s (10분) | ETL 완료 |
| Chat 세션 | 3600s (1시간) | 세션 종료 |
| MCP 도구 메타 | 7200s (2시간) | 수동 업데이트 |

#### 2.1.2 Pre-aggregation (Materialized Views)

**목적**: 반복 집계 쿼리 성능 향상 (100~500ms → 10~50ms)

**적용 대상**:
- `mv_oee_daily`: 일별 OEE 계산
- `mv_defect_trend_hourly`: 시간별 불량 트렌드
- `mv_line_performance_daily`: 라인별 생산 성능
- `mv_inventory_coverage_daily`: 재고 커버리지

**리프레시 전략**:
```sql
-- 일 1회 리프레시 (06:00 AM)
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_oee_daily;

-- 시간 1회 리프레시 (매 정각)
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_defect_trend_hourly;
```

**성능 비교**:

| 쿼리 | Direct Query | Materialized View | 개선 |
|------|--------------|-------------------|------|
| OEE 계산 | 450ms | 35ms | **12.9배** |
| 불량 트렌드 | 320ms | 28ms | **11.4배** |
| 라인 성능 | 280ms | 25ms | **11.2배** |

### 2.2 비동기 처리 (Asynchronous Processing)

#### 2.2.1 FastAPI 비동기 I/O

**동기 vs 비동기 성능**:

| 방식 | 처리량 (req/s) | 응답 시간 (P95) |
|------|---------------|----------------|
| **동기 (Sync)** | 100 | 2500ms |
| **비동기 (Async)** | 300 | 1200ms |

**비동기 코드 예시**:
```python
# ✅ 비동기 (권장)
import httpx
import asyncio

async def execute_judgment(request: JudgmentRequest):
    # 병렬 실행 (Rule + LLM)
    rule_task = asyncio.create_task(rule_engine.execute(request.input_data))
    llm_task = asyncio.create_task(llm_client.call(request.input_data))

    # 동시 대기
    rule_result, llm_result = await asyncio.gather(rule_task, llm_task)

    # 결과 병합
    return aggregator.combine(rule_result, llm_result)
```

#### 2.2.2 Workflow 병렬 노드 실행

**PARALLEL 노드**:
```python
async def execute_parallel_node(node: ParallelNode, context: dict):
    """병렬 분기 실행"""
    # 모든 분기를 동시 실행
    tasks = [
        execute_node(branch_node, context)
        for branch_node in node.branches
    ]

    # 조인 정책에 따라 대기
    if node.join_policy == 'all':
        results = await asyncio.gather(*tasks)
    elif node.join_policy == 'any':
        results = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

    return results
```

### 2.3 Connection Pooling

#### PostgreSQL Connection Pool 설정:
```python
from sqlalchemy import create_engine

engine = create_engine(
    DATABASE_URL,
    pool_size=20,          # 기본 연결 수
    max_overflow=40,       # 최대 추가 연결 (총 60개)
    pool_timeout=30,       # 연결 대기 타임아웃
    pool_recycle=3600,     # 1시간마다 연결 재생성
    pool_pre_ping=True     # 연결 유효성 사전 확인
)
```

**Connection Pool 모니터링**:
```sql
-- 활성 연결 수
SELECT count(*) FROM pg_stat_activity WHERE state = 'active';

-- 대기 중인 연결
SELECT count(*) FROM pg_stat_activity WHERE wait_event IS NOT NULL;

-- 최대 연결 수
SHOW max_connections;
```

---

## 3. 용량 계획 (Capacity Planning)

### 3.1 현재 용량 (MVP 기준)

#### 3.1.1 서비스 용량

| 서비스 | Replicas | CPU (각) | 메모리 (각) | 총 TPS |
|--------|---------|---------|------------|--------|
| Judgment | 3 | 2 vCPU | 2GB | 150 |
| Workflow | 2 | 2 vCPU | 1GB | 40 |
| BI | 2 | 2 vCPU | 2GB | 30 |
| MCP Hub | 2 | 1 vCPU | 1GB | 80 |
| Chat | 2 | 1 vCPU | 1GB | 120 |

**총 리소스**: 24 vCPU, 20GB RAM

#### 3.1.2 데이터베이스 용량

| 항목 | 현재 | 6개월 후 | 1년 후 |
|------|------|---------|--------|
| **데이터 크기** | 50GB | 200GB | 350GB |
| **일일 증가량** | 300MB | 500MB | 800MB |
| **QPS (Queries/Sec)** | 100 | 300 | 500 |
| **연결 수 (Peak)** | 50 | 150 | 250 |

**PostgreSQL 스펙 (운영)**:
- **CPU**: 8 vCPU
- **메모리**: 64GB (shared_buffers 16GB, effective_cache 48GB)
- **스토리지**: 500GB SSD (IOPS 3000)
- **Replicas**: 2개 (읽기 부하 분산)

#### 3.1.3 Redis 용량

| 항목 | 현재 | 6개월 후 | 1년 후 |
|------|------|---------|--------|
| **메모리 사용량** | 2GB | 8GB | 16GB |
| **Keys 수** | 100K | 500K | 1M |
| **QPS** | 1000 | 3000 | 5000 |

**Redis 스펙**:
- **메모리**: 16GB (maxmemory-policy: allkeys-lru)
- **Replicas**: 2개 + Sentinel 3개

### 3.2 스케일링 전략

#### 3.2.1 Auto-Scaling 기준

**HPA (Horizontal Pod Autoscaler)**:

| 서비스 | 스케일 조건 | Min | Max |
|--------|------------|-----|-----|
| **Judgment** | CPU > 70% or 요청 큐 > 50 | 2 | 10 |
| **Workflow** | CPU > 70% or 인스턴스 대기 > 20 | 2 | 8 |
| **BI** | CPU > 70% or 쿼리 대기 > 10 | 2 | 6 |
| **MCP Hub** | 호출 대기 > 30 | 2 | 5 |

**스케일아웃 시나리오**:
```
초기: Judgment 2 replicas (CPU 60%)
부하 증가: CPU 75% for 3분 → HPA 트리거
→ Judgment 3 replicas (+ 1개 추가)
→ CPU 55% (부하 분산)
```

#### 3.2.2 데이터베이스 스케일링

**Read Replica 추가**:
- 읽기 부하 > 70% → Replica 추가 (최대 5개)
- 읽기/쓰기 분리:
  - Master: 쓰기 (Judgment 저장, Workflow 상태 업데이트)
  - Replica: 읽기 (BI 쿼리, 보고서, 대시보드)

**Vertical Scaling (필요 시)**:
- 8 vCPU, 64GB → 16 vCPU, 128GB
- IOPS 3000 → 6000

---

## 4. 부하 시나리오 및 테스트

### 4.1 부하 시나리오

#### 4.1.1 정상 부하 (Normal Load)

**사용자**: 100명 동시 접속
**패턴**: 업무 시간 (09:00~18:00)

| 액션 | TPS | 비율 |
|------|-----|------|
| Judgment 실행 | 10 | 40% |
| BI 쿼리 | 2 | 8% |
| Workflow 실행 | 5 | 20% |
| MCP 호출 | 3 | 12% |
| Dashboard 조회 | 5 | 20% |

**총 TPS**: 25

#### 4.1.2 피크 부하 (Peak Load)

**사용자**: 500명 동시 접속
**패턴**: 이벤트 발생 (불량 급증, 설비 이상)

| 액션 | TPS | 비율 |
|------|-----|------|
| Judgment 실행 | 50 | 50% |
| BI 쿼리 | 10 | 10% |
| Workflow 실행 | 20 | 20% |
| MCP 호출 | 15 | 15% |
| Dashboard 조회 | 5 | 5% |

**총 TPS**: 100

#### 4.1.3 최악 시나리오 (Worst Case)

**조건**:
- LLM API 지연 (5초 → 15초)
- ERP/MES DB 지연 (100ms → 1000ms)
- 재시도 증가

**대응**:
- Circuit Breaker OPEN → Fallback 응답
- 캐시 적중률 유지
- 타임아웃 설정 준수

### 4.2 부하 테스트 스크립트

#### Locust 부하 테스트:
```python
# tests/performance/locustfile.py
from locust import HttpUser, task, between, events
import logging

class FactoryAIUser(HttpUser):
    wait_time = between(1, 5)  # 1~5초 대기

    @task(5)
    def execute_judgment(self):
        """Judgment 실행 (50%)"""
        self.client.post('/api/v1/judgment/execute', json={
            'workflow_id': 'wf-001',
            'input_data': { ... },
            'policy': 'HYBRID_WEIGHTED'
        }, name='/api/v1/judgment/execute')

    @task(2)
    def execute_workflow(self):
        """Workflow 실행 (20%)"""
        self.client.post('/api/v1/workflows/execute', json={
            'workflow_id': 'wf-rca-001',
            'input_data': { ... }
        }, name='/api/v1/workflows/execute')

    @task(1)
    def bi_query(self):
        """BI 쿼리 (10%)"""
        self.client.post('/api/v1/bi/execute-nl-query', json={
            'query_text': '지난 7일간 LINE-A 불량률'
        }, name='/api/v1/bi/execute-nl-query')

    @task(2)
    def view_dashboard(self):
        """대시보드 조회 (20%)"""
        self.client.get('/api/v1/dashboard', name='/api/v1/dashboard')

# 이벤트 핸들러: 응답 시간 로깅
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    if exception:
        logging.error(f"{name} failed: {exception}")
    elif response_time > 3000:  # 3초 초과 시 경고
        logging.warning(f"{name} slow response: {response_time}ms")
```

**실행 및 분석**:
```bash
# 500 사용자, 10분 테스트
locust -f tests/performance/locustfile.py \
  --host https://staging.factory-ai.com \
  --users 500 \
  --spawn-rate 50 \
  --run-time 10m \
  --html report.html

# 결과 분석
# report.html 확인 → P50, P95, P99, 에러율
```

---

## 5. 성능 최적화 가이드

### 5.1 데이터베이스 최적화

#### 5.1.1 슬로우 쿼리 식별

**pg_stat_statements 사용**:
```sql
-- 가장 느린 쿼리 Top 10
SELECT
  query,
  calls,
  mean_exec_time,
  max_exec_time,
  total_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- 가장 많이 호출되는 쿼리
SELECT
  query,
  calls,
  mean_exec_time
FROM pg_stat_statements
ORDER BY calls DESC
LIMIT 10;
```

#### 5.1.2 인덱스 최적화

**Missing Index 탐지**:
```sql
-- Seq Scan이 많은 테이블
SELECT
  schemaname,
  tablename,
  seq_scan,
  seq_tup_read,
  idx_scan,
  seq_tup_read / seq_scan AS avg_seq_tup_read
FROM pg_stat_user_tables
WHERE seq_scan > 0
ORDER BY seq_tup_read DESC
LIMIT 10;

-- 인덱스 사용률 낮은 인덱스
SELECT
  schemaname,
  tablename,
  indexname,
  idx_scan,
  idx_tup_read
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY pg_relation_size(indexrelid) DESC
LIMIT 10;
```

**인덱스 추가 가이드**:
- WHERE 절에 자주 사용되는 컬럼
- JOIN 조건 컬럼
- ORDER BY 컬럼
- 복합 인덱스 (tenant_id, date, ...)

#### 5.1.3 VACUUM 및 ANALYZE

**정기 VACUUM**:
```bash
# 매일 03:00 AM (부하 낮은 시간)
0 3 * * * vacuumdb -h localhost -U postgres -d factory_ai --analyze --verbose
```

**AUTOVACUUM 설정**:
```sql
-- postgresql.conf
autovacuum = on
autovacuum_max_workers = 3
autovacuum_naptime = 1min
```

### 5.2 LLM 최적화

#### 5.2.1 Prompt 최적화

**목표**: 토큰 수 감소 → 비용 절감, 응답 시간 단축

**Before**:
```
You are an expert manufacturing quality analyst with 20 years of experience in defect detection and root cause analysis. You have extensive knowledge of production lines, equipment maintenance, and quality control processes.

Please analyze the following production data and provide a detailed judgment including status, severity, recommended actions, and explanation. Consider historical trends, similar cases, and industry best practices.

Input Data:
- Line: LINE-A
- Defect Count: 5
- Production Count: 100

Provide your analysis in the following JSON format: {...}

Total Tokens: ~250
```

**After** (최적화):
```
Manufacturing quality expert. Analyze defect data.

Input:
- Line: LINE-A
- Defect: 5/100

JSON format: {status, severity, actions, explanation}

Total Tokens: ~80 (68% 감소)
```

#### 5.2.2 모델 선택 최적화

**비용/성능 비교**:

| 모델 | 입력 비용 (1M 토큰) | 출력 비용 (1M 토큰) | 평균 응답 시간 | 용도 |
|------|-------------------|-------------------|--------------|------|
| GPT-4o-mini | $0.15 | $0.6 | 0.8초 | Intent 분류, 간단한 판단 |
| GPT-4o | $2.5 | $10 | 2.0초 | BI 플래너, 중간 복잡도 |
| GPT-4 | $30 | $60 | 4.0초 | 복잡한 RCA, 고품질 판단 |

**전략**:
- 80% 요청: GPT-4o-mini (저비용)
- 15% 요청: GPT-4o (균형)
- 5% 요청: GPT-4 (고품질)

---

## 6. 성능 모니터링 및 알람

### 6.1 Prometheus 메트릭

#### 6.1.1 Judgment Service 메트릭

```python
from prometheus_client import Counter, Histogram, Gauge

# Counter: 실행 횟수
judgment_executions_total = Counter(
    'judgment_executions_total',
    'Total judgment executions',
    ['tenant_id', 'workflow_id', 'status', 'method']
)

# Histogram: 실행 시간
judgment_duration_seconds = Histogram(
    'judgment_duration_seconds',
    'Judgment execution duration',
    ['tenant_id', 'workflow_id', 'method'],
    buckets=[0.1, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0]
)

# Gauge: 활성 실행 수
judgment_active_executions = Gauge(
    'judgment_active_executions',
    'Number of active judgment executions',
    ['tenant_id']
)

# 사용 예시
judgment_executions_total.labels(
    tenant_id='tenant-456',
    workflow_id='wf-001',
    status='success',
    method='hybrid_weighted'
).inc()

judgment_duration_seconds.labels(
    tenant_id='tenant-456',
    workflow_id='wf-001',
    method='hybrid_weighted'
).observe(1.25)
```

### 6.2 Grafana 대시보드

#### 6.2.1 Judgment Performance Dashboard

**패널 구성**:
- **Requests Per Second (RPS)**: `rate(judgment_executions_total[5m])`
- **P50/P95/P99 Latency**: `histogram_quantile(0.95, judgment_duration_seconds)`
- **Error Rate**: `rate(judgment_executions_total{status="error"}[5m])`
- **Cache Hit Rate**: `redis_cache_hits / (redis_cache_hits + redis_cache_misses)`
- **Method Distribution**: Pie Chart (Rule Only, LLM Only, Hybrid)

**알람 규칙**:
```yaml
# prometheus/rules/judgment.yml
groups:
- name: judgment_performance
  interval: 30s
  rules:
  - alert: JudgmentHighLatency
    expr: histogram_quantile(0.95, judgment_duration_seconds) > 3
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Judgment P95 latency > 3s"
      description: "P95 latency is {{ $value }}s (threshold: 3s)"

  - alert: JudgmentHighErrorRate
    expr: rate(judgment_executions_total{status="error"}[5m]) > 0.01
    for: 3m
    labels:
      severity: critical
    annotations:
      summary: "Judgment error rate > 1%"
      description: "Error rate is {{ $value }} (threshold: 0.01)"
```

---

## 결론

본 문서(C-4)는 **AI Factory Decision Engine** 의 성능 및 용량 계획을 상세히 수립하였다.

### 주요 성과
1. **명확한 SLO**: Judgment P95 < 2.5s, BI P95 < 3s, 가용성 99.9%
2. **성능 설계 전략**: 계층형 캐시, Pre-agg, 비동기 I/O, Connection Pool
3. **용량 계획**: 현재 24 vCPU, 6개월 후 50 vCPU, 1년 후 100 vCPU
4. **부하 테스트**: 정상/피크/최악 시나리오, Locust 스크립트
5. **성능 최적화**: DB 인덱스, LLM Prompt, 모델 선택
6. **모니터링**: Prometheus 메트릭, Grafana 대시보드, 알람 규칙

### 다음 단계
1. 부하 테스트 실행 (Sprint 5)
2. 병목 식별 및 최적화
3. HPA 설정 및 검증
4. 성능 목표 달성 확인

---

## 문서 이력
| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2025-10-25 | DevOps Team | 초안 작성 |
| 2.0 | 2025-11-26 | DevOps Team | Enhanced 버전 (용량 계획, 최적화 가이드 추가) |
