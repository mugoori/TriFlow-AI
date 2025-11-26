# B-1-2. System Architecture Specification - Physical, Deployment, Data Architecture

## 문서 정보
- **문서 ID**: B-1-2
- **버전**: 1.0
- **최종 수정일**: 2025-11-26
- **상태**: Draft
- **선행 문서**: B-1-1 Architecture Overview

## 목차
1. [물리적 아키텍처](#1-물리적-아키텍처)
2. [배포 아키텍처](#2-배포-아키텍처)
3. [데이터 아키텍처](#3-데이터-아키텍처)
4. [네트워크 아키텍처](#4-네트워크-아키텍처)

---

## 1. 물리적 아키텍처

### 1.1 개요
물리적 아키텍처는 서비스, 데이터베이스, 캐시, 스토리지가 실제 하드웨어/클라우드 인프라에 어떻게 배치되는지 정의한다.

### 1.2 서버 구성 (클라우드 배포 기준)

#### 1.2.1 Production 환경

| 노드 타입 | 수량 | 스펙 (AWS 기준) | 용도 |
|----------|------|-----------------|------|
| **API Gateway** | 2 | t3.medium (2 vCPU, 4GB RAM) | Nginx/Kong, 로드 밸런싱, TLS |
| **Judgment Service** | 3 | c6i.xlarge (4 vCPU, 8GB RAM) | Rule + LLM Hybrid 판단 |
| **Workflow Service** | 2 | t3.large (2 vCPU, 8GB RAM) | Workflow 실행 및 상태 관리 |
| **BI Service** | 2 | c6i.xlarge (4 vCPU, 8GB RAM) | BI Planner, SQL 실행 |
| **Learning Service** | 1 | t3.large (2 vCPU, 8GB RAM) | Rule 추출, 배포 관리 |
| **MCP ToolHub** | 2 | t3.medium (2 vCPU, 4GB RAM) | MCP 도구 호출 프록시 |
| **Chat Service** | 2 | t3.medium (2 vCPU, 4GB RAM) | Intent 분류, 세션 관리 |
| **Data Hub** | 1 | t3.large (2 vCPU, 8GB RAM) | ETL, 벡터화 |
| **PostgreSQL** | 3 | r6i.2xlarge (8 vCPU, 64GB RAM) | Primary + 2 Replicas |
| **Redis** | 3 | r6g.large (2 vCPU, 16GB RAM) | Master + 2 Replicas (Sentinel) |
| **Monitoring** | 1 | t3.large (2 vCPU, 8GB RAM) | Prometheus, Grafana, Loki |

**총 서버 수**: 22대
**총 비용 (예상)**: $3,000~$5,000/월 (AWS)

#### 1.2.2 Staging 환경

| 노드 타입 | 수량 | 스펙 | 용도 |
|----------|------|------|------|
| **All Services** | 1 각 | t3.small (1 vCPU, 2GB RAM) | 통합 테스트, UAT |
| **PostgreSQL** | 1 | t3.medium (2 vCPU, 4GB RAM) | 테스트 데이터 |
| **Redis** | 1 | t3.small (1 vCPU, 2GB RAM) | 캐시 테스트 |

**총 비용**: $300~$500/월

#### 1.2.3 Development 환경

| 노드 타입 | 수량 | 스펙 | 용도 |
|----------|------|------|------|
| **Docker Compose** | 1 | 로컬 머신 | 로컬 개발, 단위 테스트 |
| **PostgreSQL** | 1 | Docker 컨테이너 | 로컬 DB |
| **Redis** | 1 | Docker 컨테이너 | 로컬 캐시 |

---

## 2. 배포 아키텍처

### 2.1 Kubernetes 배포 구조

#### 2.1.1 Namespace 구조

```
┌─────────────────────────────────────────────┐
│          Kubernetes Cluster (EKS)           │
├─────────────────────────────────────────────┤
│  Namespace: production                      │
│    ├─ Deployment: judgment-service          │
│    ├─ Deployment: workflow-service          │
│    ├─ Deployment: bi-service                │
│    ├─ Deployment: learning-service          │
│    ├─ Deployment: mcp-hub                   │
│    ├─ Deployment: chat-service              │
│    ├─ Deployment: api-gateway               │
│    ├─ StatefulSet: postgresql               │
│    ├─ StatefulSet: redis                    │
│    └─ ConfigMap, Secret                     │
├─────────────────────────────────────────────┤
│  Namespace: staging                         │
│    └─ (동일 구조, 작은 스펙)                 │
├─────────────────────────────────────────────┤
│  Namespace: monitoring                      │
│    ├─ Deployment: prometheus                │
│    ├─ Deployment: grafana                   │
│    └─ Deployment: loki                      │
└─────────────────────────────────────────────┘
```

#### 2.1.2 Deployment 예시: Judgment Service

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: judgment-service
  namespace: production
  labels:
    app: judgment-service
    version: v1.4.0
spec:
  replicas: 3
  selector:
    matchLabels:
      app: judgment-service
  template:
    metadata:
      labels:
        app: judgment-service
        version: v1.4.0
    spec:
      containers:
      - name: judgment-service
        image: factory-ai/judgment-service:v1.4.0
        ports:
        - containerPort: 8010
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: url
        - name: REDIS_URL
          valueFrom:
            configMapKeyRef:
              name: redis-config
              key: url
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: llm-secret
              key: openai_key
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 2000m
            memory: 2Gi
        livenessProbe:
          httpGet:
            path: /health
            port: 8010
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8010
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: judgment-service
  namespace: production
spec:
  selector:
    app: judgment-service
  ports:
  - protocol: TCP
    port: 8010
    targetPort: 8010
  type: ClusterIP
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: judgment-service-hpa
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: judgment-service
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

#### 2.1.3 StatefulSet 예시: PostgreSQL

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgresql
  namespace: production
spec:
  serviceName: postgresql
  replicas: 3
  selector:
    matchLabels:
      app: postgresql
  template:
    metadata:
      labels:
        app: postgresql
    spec:
      containers:
      - name: postgresql
        image: postgres:14-alpine
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_DB
          value: factory_ai
        - name: POSTGRES_USER
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: username
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: password
        - name: PGDATA
          value: /var/lib/postgresql/data/pgdata
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
        resources:
          requests:
            cpu: 1000m
            memory: 4Gi
          limits:
            cpu: 4000m
            memory: 16Gi
  volumeClaimTemplates:
  - metadata:
      name: postgres-storage
    spec:
      accessModes: [ "ReadWriteOnce" ]
      storageClassName: gp3
      resources:
        requests:
          storage: 500Gi
```

### 2.2 로드 밸런싱 전략

#### 2.2.1 외부 로드 밸런서 (L4/L7)
- **AWS ALB (Application Load Balancer)**:
  - HTTPS 트래픽 (443) → API Gateway
  - TLS 종료
  - Health Check: GET /health
  - Sticky Session (선택적)

#### 2.2.2 Kubernetes Service (L4)
- **ClusterIP**: 내부 서비스 간 통신
  - judgment-service:8010
  - workflow-service:8003
- **Round-robin**: 기본 로드 밸런싱
- **Session Affinity**: sessionAffinity: ClientIP (선택적)

#### 2.2.3 Ingress (L7)
- **Path 기반 라우팅**:
  - `/api/v1/judgment/*` → judgment-service
  - `/api/v1/workflow/*` → workflow-service
  - `/api/v1/bi/*` → bi-service

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-ingress
  namespace: production
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/rate-limit: "100"
spec:
  tls:
  - hosts:
    - api.factory-ai.com
    secretName: tls-secret
  rules:
  - host: api.factory-ai.com
    http:
      paths:
      - path: /api/v1/judgment
        pathType: Prefix
        backend:
          service:
            name: judgment-service
            port:
              number: 8010
      - path: /api/v1/workflow
        pathType: Prefix
        backend:
          service:
            name: workflow-service
            port:
              number: 8003
```

---

## 3. 데이터 아키텍처

### 3.1 데이터 계층 구조

```
┌─────────────────────────────────────────────────────────────────┐
│                      Application Layer                          │
│  Services (Judgment, Workflow, BI, Learning, MCP Hub, Chat)     │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼ (Repository Pattern)
┌─────────────────────────────────────────────────────────────────┐
│                    Data Access Layer (DAL)                      │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐               │
│  │   ORM      │  │   Redis    │  │   S3       │               │
│  │(SQLAlchemy)│  │  Client    │  │  Client    │               │
│  └────────────┘  └────────────┘  └────────────┘               │
└─────────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ PostgreSQL   │  │    Redis     │  │   S3/MinIO   │
│              │  │              │  │              │
│- Core Schema │  │- Cache       │  │- Files       │
│- BI Schema   │  │- Session     │  │- Backups     │
│- RAG Schema  │  │- Pub/Sub     │  │- Logs        │
│- Vector      │  │- Lock        │  │- Embeddings  │
└──────────────┘  └──────────────┘  └──────────────┘
```

### 3.2 데이터베이스 아키텍처

#### 3.2.1 PostgreSQL 데이터 레이아웃

**스키마 분리**:
```sql
-- Core Operational Schema
CREATE SCHEMA core;
  -- tenants, users, roles, permissions
  -- workflows, workflow_steps, workflow_instances
  -- judgment_executions, rulesets, rule_scripts
  -- prompt_templates, llm_calls
  -- chat_sessions, intent_logs
  -- data_connectors, mcp_servers, mcp_tools
  -- audit_logs, feedbacks, learning_samples

-- BI & Analytics Schema
CREATE SCHEMA bi;
  -- raw_mes_production, raw_erp_order, raw_inventory
  -- dim_date, dim_line, dim_product, dim_equipment
  -- fact_daily_production, fact_daily_defect, fact_inventory_snapshot
  -- mv_defect_trend_hourly, mv_oee_daily
  -- bi_datasets, bi_metrics, bi_components
  -- etl_jobs, etl_job_executions

-- RAG & AAS Schema
CREATE SCHEMA rag;
  -- rag_documents, rag_embeddings
  -- memories (short_term, long_term)
  -- aas_assets, aas_submodels, aas_elements, aas_source_mappings

-- Monitoring & Audit Schema
CREATE SCHEMA audit;
  -- audit_logs (immutable)
  -- schema_snapshots, drift_detections
```

#### 3.2.2 테이블 파티셔닝 전략

**시계열 데이터 파티셔닝** (B-3-4 참조):

| 테이블 | 파티션 전략 | 보존 기간 | 예시 파티션 |
|--------|------------|-----------|------------|
| `core.judgment_executions` | 월별 Range | 2년 (핫 90일) | `_y2025m11`, `_y2025m12` |
| `core.workflow_instances` | 월별 Range | 2년 (핫 90일) | `_y2025m11`, `_y2025m12` |
| `bi.fact_daily_production` | 분기별 Range | 3년 | `_y2025q4`, `_y2026q1` |
| `bi.fact_hourly_production` | 월별 Range | 1년 | `_y2025m11`, `_y2025m12` |
| `core.llm_calls` | 월별 Range | 1년 | `_y2025m11`, `_y2025m12` |

**파티션 자동 생성**:
- 미래 3개월 파티션 사전 생성 (cron job)
- 보존 기간 초과 파티션 자동 삭제

#### 3.2.3 인덱스 전략

**주요 인덱스** (B-3-4 참조):

| 테이블 | 인덱스 | 타입 | 목적 |
|--------|--------|------|------|
| `judgment_executions` | `(tenant_id, workflow_id, executed_at DESC)` | B-tree | 워크플로우별 조회 |
| `judgment_executions` | `(tenant_id, executed_at DESC)` | B-tree | 시간순 조회 |
| `workflow_instances` | `(tenant_id, status, started_at DESC)` | B-tree | 상태별 조회 |
| `rag_embeddings` | `(embedding) vector_cosine_ops` | IVFFlat | 벡터 유사도 검색 |
| `llm_calls` | `(response_metadata) GIN` | GIN | JSONB 검색 |
| `fact_daily_production` | `(tenant_id, date, line_code)` | B-tree | 일별 라인 조회 |

### 3.3 캐시 아키텍처

#### 3.3.1 Redis 데이터 구조

**캐시 키 명명 규칙**:
```
{service}:{type}:{tenant_id}:{key}
```

**주요 캐시 키**:

| 키 패턴 | TTL | 용도 | 무효화 조건 |
|---------|-----|------|------------|
| `judgment:cache:{workflow_id}:{input_hash}` | 300s | Judgment 결과 캐싱 | Rule 배포 시 |
| `bi:cache:{tenant_id}:{plan_hash}` | 600s | BI 쿼리 결과 캐싱 | ETL 완료 시 |
| `session:{session_id}` | 3600s | Chat 세션 상태 | 세션 종료 시 |
| `circuit:{service}:{node_id}` | 60s | Circuit Breaker 상태 | 수동 리셋 |
| `webhook:idempotency:{key}` | 86400s | Webhook 멱등성 | TTL 만료 |

**예시**:
```python
# Judgment 결과 캐싱
import hashlib
import json

def get_cache_key(workflow_id, input_data):
    input_hash = hashlib.sha256(
        json.dumps(input_data, sort_keys=True).encode()
    ).hexdigest()
    return f"judgment:cache:{workflow_id}:{input_hash}"

# Cache 저장
redis_client.setex(
    get_cache_key("wf-001", input_data),
    300,  # TTL 5분
    json.dumps(result)
)

# Cache 조회
cached = redis_client.get(get_cache_key("wf-001", input_data))
if cached:
    return json.loads(cached)
```

#### 3.3.2 Redis Pub/Sub 채널

| 채널 | 발행자 | 구독자 | 메시지 타입 |
|------|--------|--------|------------|
| `judgment.executed` | Judgment Service | Learning Service | Judgment 완료 이벤트 |
| `rule.deployed` | Learning Service | Judgment Service | Rule 배포 이벤트 (캐시 무효화) |
| `workflow.completed` | Workflow Service | Notification Service | Workflow 완료 알림 |
| `drift.detected` | Integration Hub | Data Hub, Notification | 스키마 변경 알림 |
| `etl.completed` | Data Hub | BI Service | ETL 완료 (캐시 무효화) |

---

## 4. 네트워크 아키텍처

### 4.1 네트워크 토폴로지

```
┌────────────────────────────────────────────────────────────┐
│                      Internet                              │
└────────────────────────────────────────────────────────────┘
                         │
                         ▼ HTTPS (443)
┌────────────────────────────────────────────────────────────┐
│              AWS Application Load Balancer                 │
│  - TLS Termination                                         │
│  - Health Check: /health                                   │
│  - Sticky Session: Cookie-based                            │
└────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│                  Public Subnet (DMZ)                       │
│  ┌────────────┐  ┌────────────┐                           │
│  │    NAT     │  │  Bastion   │                           │
│  │  Gateway   │  │    Host    │                           │
│  └────────────┘  └────────────┘                           │
└────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│               Private Subnet (Application)                 │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐          │
│  │ Judgment   │  │ Workflow   │  │ BI Service │          │
│  │  Service   │  │  Service   │  │            │          │
│  └────────────┘  └────────────┘  └────────────┘          │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐          │
│  │ Learning   │  │ MCP Hub    │  │ Chat Svc   │          │
│  └────────────┘  └────────────┘  └────────────┘          │
└────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│                Private Subnet (Database)                   │
│  ┌────────────┐  ┌────────────┐                           │
│  │PostgreSQL  │  │   Redis    │                           │
│  │ (Primary)  │  │  (Master)  │                           │
│  └────────────┘  └────────────┘                           │
│  ┌────────────┐  ┌────────────┐                           │
│  │PostgreSQL  │  │   Redis    │                           │
│  │(Replica 1) │  │(Replica 1) │                           │
│  └────────────┘  └────────────┘                           │
└────────────────────────────────────────────────────────────┘
```

### 4.2 방화벽 규칙

#### 4.2.1 인바운드 규칙

| Source | Destination | Port | Protocol | 설명 |
|--------|-------------|------|----------|------|
| Internet | ALB | 443 | HTTPS | 외부 사용자 접근 |
| ALB | API Gateway | 80 | HTTP | 내부 HTTP (TLS 종료됨) |
| API Gateway | All Services | 8000-8099 | HTTP | 서비스 호출 |
| All Services | PostgreSQL | 5432 | TCP | DB 연결 |
| All Services | Redis | 6379 | TCP | 캐시 연결 |
| Monitoring | All Services | 8080/metrics | HTTP | Prometheus 스크래핑 |

#### 4.2.2 아웃바운드 규칙

| Source | Destination | Port | Protocol | 설명 |
|--------|-------------|------|----------|------|
| Judgment Service | OpenAI API | 443 | HTTPS | LLM 호출 |
| MCP Hub | External MCP | 443 | HTTPS | MCP 서버 호출 |
| Workflow Service | Slack API | 443 | HTTPS | Slack 알림 |
| Data Hub | ERP/MES | 443/5432 | HTTPS/TCP | 데이터 수집 |
| NAT Gateway | Internet | 443 | HTTPS | 아웃바운드 인터넷 |

### 4.3 보안 그룹 (Security Groups)

#### Public Subnet Security Group
```
Inbound:
- 0.0.0.0/0 → 443 (HTTPS)

Outbound:
- All traffic (ALB → Private Subnet)
```

#### Application Subnet Security Group
```
Inbound:
- ALB Security Group → 8000-8099
- Monitoring SG → 8080/metrics

Outbound:
- Database SG → 5432
- Redis SG → 6379
- Internet (via NAT) → 443
```

#### Database Subnet Security Group
```
Inbound:
- Application SG → 5432 (PostgreSQL)
- Application SG → 6379 (Redis)

Outbound:
- None (격리)
```

---

## 5. 데이터 아키텍처 상세

### 5.1 데이터 모델 계층

```
┌─────────────────────────────────────────────────────────────────┐
│                    Presentation Data (DTO)                      │
│  API 응답, UI 모델 (JSON, 평탄화)                                │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼ (Mapper)
┌─────────────────────────────────────────────────────────────────┐
│                   Domain Model (Entity)                         │
│  비즈니스 엔티티 (Judgment, Workflow, BI Plan)                   │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼ (ORM)
┌─────────────────────────────────────────────────────────────────┐
│                   Persistence Model (Table)                     │
│  DB 테이블 (judgment_executions, workflows, fact_*)             │
└─────────────────────────────────────────────────────────────────┘
```

**예시**:
```python
# Presentation DTO
class JudgmentResponseDTO:
    execution_id: str
    status: str
    confidence: float
    explanation: str

# Domain Entity
class Judgment:
    id: UUID
    workflow_id: UUID
    input_data: dict
    rule_result: RuleResult
    llm_result: Optional[LLMResult]
    final_result: JudgmentResult
    confidence: float
    method_used: str

    def execute(self): ...
    def calculate_confidence(self): ...

# Persistence Model (SQLAlchemy)
class JudgmentExecutionModel(Base):
    __tablename__ = 'judgment_executions'
    __table_args__ = {'schema': 'core'}

    id = Column(UUID, primary_key=True)
    tenant_id = Column(UUID, nullable=False)
    workflow_id = Column(UUID, nullable=False)
    executed_at = Column(DateTime(timezone=True), default=func.now())
    # ...
```

### 5.2 데이터 흐름: ETL 파이프라인

```
[External Systems] → [Data Hub] → [PostgreSQL]
                                        │
                                        ▼
                        [RAW Tables] (raw_mes_production, raw_erp_order)
                                        │
                                        ▼ ETL (Transform)
                        [DIM Tables] (dim_line, dim_product, dim_equipment)
                                        │
                                        ▼ ETL (Aggregate)
                        [FACT Tables] (fact_daily_production, fact_daily_defect)
                                        │
                                        ▼ ETL (Pre-agg)
                        [Materialized Views] (mv_oee_daily, mv_defect_trend_hourly)
                                        │
                                        ▼
                        [BI Service] (쿼리 실행, 차트 생성)
```

**ETL 스케줄**:
```
03:00 - RAW 데이터 수집 (ERP, MES)
04:00 - DIM 테이블 업데이트 (SCD Type 2)
05:00 - FACT 테이블 적재 (일별 집계)
06:00 - Materialized View 리프레시
07:00 - 데이터 품질 검사
```

### 5.3 벡터 데이터 아키텍처 (RAG)

#### Vector 저장 및 검색

```
[Document] → [Chunking] → [Embedding API] → [pgvector] → [Vector Search]
```

**단계별 상세**:
1. **Document Chunking**: 문서를 512 토큰 단위로 분할
2. **Embedding Generation**: OpenAI `text-embedding-3-small` (1536 차원)
3. **Vector Storage**: pgvector 테이블에 저장
4. **Index Creation**: IVFFlat 인덱스 (lists=100)
5. **Similarity Search**: Cosine 유사도 기반 Top-K 검색

**Vector Search 함수**:
```sql
CREATE OR REPLACE FUNCTION search_rag_documents(
  p_tenant_id uuid,
  p_query_embedding vector(1536),
  p_limit int DEFAULT 5
) RETURNS TABLE (
  doc_id uuid,
  title text,
  text text,
  similarity float
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    d.id,
    d.title,
    d.text,
    1 - (e.embedding <=> p_query_embedding) AS similarity
  FROM rag.rag_embeddings e
  JOIN rag.rag_documents d ON e.doc_id = d.id
  WHERE d.tenant_id = p_tenant_id
  ORDER BY e.embedding <=> p_query_embedding
  LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;
```

---

## 다음 파일로 계속

본 문서는 B-1-2로, 물리적 아키텍처, 배포 아키텍처, 데이터 아키텍처, 네트워크 아키텍처를 포함한다.

**다음 파일**:
- **B-1-3**: 통합 아키텍처, 보안 아키텍처, 확장성/가용성 아키텍처
- **B-1-4**: 기술 스택 상세, 아키텍처 결정 기록 (ADR)

---

## 문서 이력
| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2025-11-26 | AI Factory Team | 초안 작성 |
