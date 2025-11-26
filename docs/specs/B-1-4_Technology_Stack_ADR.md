# B-1-4. System Architecture Specification - Technology Stack & Architecture Decision Records

## 문서 정보
- **문서 ID**: B-1-4
- **버전**: 1.0
- **최종 수정일**: 2025-11-26
- **상태**: Draft
- **선행 문서**: B-1-1, B-1-2, B-1-3

## 목차
1. [기술 스택 상세](#1-기술-스택-상세)
2. [아키텍처 결정 기록 (ADR)](#2-아키텍처-결정-기록-adr)
3. [마이그레이션 전략](#3-마이그레이션-전략)
4. [성능 최적화 전략](#4-성능-최적화-전략)

---

## 1. 기술 스택 상세

### 1.1 전체 기술 스택 개요

```
┌─────────────────────────────────────────────────────────────────┐
│                        Technology Stack                         │
├─────────────────────────────────────────────────────────────────┤
│  Layer              │ Technology                                │
├─────────────────────────────────────────────────────────────────┤
│  Frontend           │ React 18, TypeScript, Tailwind CSS       │
│                     │ Chart.js, React Query, Zustand           │
├─────────────────────────────────────────────────────────────────┤
│  API Gateway        │ Nginx 1.24 or Kong 3.x                   │
├─────────────────────────────────────────────────────────────────┤
│  Backend Services   │ Python 3.11, FastAPI 0.104, Pydantic    │
│                     │ SQLAlchemy 2.0, Alembic, uvicorn        │
├─────────────────────────────────────────────────────────────────┤
│  Rule Engine        │ Rhai 1.16 (Rust 기반 스크립트 언어)      │
├─────────────────────────────────────────────────────────────────┤
│  LLM Integration    │ OpenAI API (GPT-4, GPT-4o, GPT-4o-mini) │
│                     │ Anthropic API (Claude-3-Opus/Sonnet/Haiku)│
│                     │ LangChain 0.1.x (선택적)                 │
├─────────────────────────────────────────────────────────────────┤
│  Database           │ PostgreSQL 14.10, pgvector 0.5.1        │
│                     │ Patroni 3.2 (HA), pg_partman (파티셔닝)  │
├─────────────────────────────────────────────────────────────────┤
│  Cache & Queue      │ Redis 7.2, redis-py 5.0                 │
│                     │ Redis Sentinel (HA)                     │
├─────────────────────────────────────────────────────────────────┤
│  Object Storage     │ MinIO (온프렘) or AWS S3 (클라우드)      │
├─────────────────────────────────────────────────────────────────┤
│  Container          │ Docker 24.0, Kubernetes 1.28             │
│  Orchestration      │ Helm 3.13 (차트 관리)                    │
├─────────────────────────────────────────────────────────────────┤
│  Monitoring         │ Prometheus 2.47, Grafana 10.2           │
│                     │ Loki 2.9 (로그), Alertmanager 0.26      │
│                     │ OpenTelemetry (분산 추적)                │
├─────────────────────────────────────────────────────────────────┤
│  CI/CD              │ GitHub Actions or GitLab CI             │
│                     │ ArgoCD 2.9 (GitOps)                     │
├─────────────────────────────────────────────────────────────────┤
│  Security           │ Vault 1.15 (비밀 관리)                   │
│                     │ OWASP ZAP (보안 스캔)                    │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 프로그래밍 언어 및 프레임워크

#### 1.2.1 Backend: Python + FastAPI

**선택 이유**:
- **AI/ML 생태계**: scikit-learn, pandas, numpy 등 풍부한 라이브러리
- **LLM 연동**: OpenAI, LangChain 공식 지원
- **빠른 개발**: 간결한 문법, 높은 생산성
- **타입 안전성**: Pydantic으로 타입 검증
- **성능**: uvicorn (ASGI), 비동기 I/O

**주요 라이브러리**:
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
sqlalchemy==2.0.23
alembic==1.12.1
redis==5.0.1
psycopg2-binary==2.9.9
openai==1.3.8
anthropic==0.7.1
rhai-py==0.2.0  # Rhai Python 바인딩
numpy==1.26.2
pandas==2.1.3
scikit-learn==1.3.2
```

**서비스 구조 예시**:
```python
# main.py
from fastapi import FastAPI
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db_pool()
    await init_redis_client()
    yield
    # Shutdown
    await close_db_pool()
    await close_redis_client()

app = FastAPI(
    title="AI Factory Judgment Service",
    version="1.4.0",
    lifespan=lifespan
)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/api/v1/judgment/execute")
async def execute_judgment(request: JudgmentRequest):
    # ... 판단 로직
    return result
```

#### 1.2.2 Rule Engine: Rhai

**선택 이유**:
- **Rust 기반**: 메모리 안전성, 고성능
- **샌드박스**: 안전한 스크립트 실행 (파일/네트워크 접근 차단)
- **타입 안전**: 동적 타입이지만 런타임 타입 체크
- **Python 바인딩**: rhai-py로 Python에서 실행 가능

**Rhai 실행 예시**:
```python
from rhai import Engine

engine = Engine()

# Rhai 스크립트
script = """
let defect_rate = input.defect_count / input.production_count;

if defect_rate > 0.05 {
    #{
        status: "HIGH_DEFECT",
        confidence: 0.95
    }
} else {
    #{
        status: "NORMAL",
        confidence: 0.80
    }
}
"""

# 입력 데이터 주입
input_data = {
    "defect_count": 5,
    "production_count": 100
}

engine.set_global("input", input_data)

# 스크립트 실행
result = engine.eval(script)
# → {"status": "HIGH_DEFECT", "confidence": 0.95}
```

#### 1.2.3 Frontend: React + TypeScript

**선택 이유**:
- **컴포넌트 기반**: 재사용성, 유지보수성
- **타입 안전성**: TypeScript로 런타임 에러 감소
- **생태계**: 풍부한 라이브러리 (Chart.js, React Query, Zustand)
- **성능**: Virtual DOM, 코드 스플리팅

**주요 라이브러리**:
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "typescript": "^5.3.0",
    "tailwindcss": "^3.3.0",
    "chart.js": "^4.4.0",
    "react-chartjs-2": "^5.2.0",
    "@tanstack/react-query": "^5.12.0",
    "zustand": "^4.4.0",
    "react-router-dom": "^6.20.0",
    "axios": "^1.6.0"
  }
}
```

**프로젝트 구조**:
```
frontend/
├── src/
│   ├── components/
│   │   ├── Judgment/
│   │   │   ├── JudgmentCard.tsx
│   │   │   ├── JudgmentList.tsx
│   │   │   └── FeedbackButton.tsx
│   │   ├── Workflow/
│   │   │   ├── WorkflowEditor.tsx
│   │   │   ├── WorkflowCanvas.tsx
│   │   │   └── NodePalette.tsx
│   │   └── BI/
│   │       ├── BIQueryInput.tsx
│   │       ├── ChartRenderer.tsx
│   │       └── DashboardBuilder.tsx
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── Judgment.tsx
│   │   ├── Workflow.tsx
│   │   └── BI.tsx
│   ├── hooks/
│   │   ├── useJudgment.ts
│   │   ├── useWorkflow.ts
│   │   └── useBIQuery.ts
│   ├── stores/
│   │   ├── authStore.ts
│   │   ├── judgmentStore.ts
│   │   └── workflowStore.ts
│   └── api/
│       ├── judgment.ts
│       ├── workflow.ts
│       └── bi.ts
└── package.json
```

### 1.3 데이터베이스 및 스토리지

#### 1.3.1 PostgreSQL 14+

**선택 이유**:
- **ACID 보장**: 트랜잭션 안정성
- **JSONB 지원**: 유연한 메타데이터 저장
- **pgvector**: 벡터 유사도 검색 (RAG)
- **파티셔닝**: 대용량 데이터 관리
- **Streaming Replication**: 고가용성
- **성숙도**: 30년 이상 검증된 안정성

**확장 모듈**:
```sql
-- pgvector: 벡터 임베딩 저장 및 검색
CREATE EXTENSION vector;

-- pg_stat_statements: 쿼리 성능 모니터링
CREATE EXTENSION pg_stat_statements;

-- pg_trgm: 텍스트 유사도 검색
CREATE EXTENSION pg_trgm;

-- uuid-ossp: UUID 생성
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

**postgresql.conf 최적화**:
```conf
# 연결
max_connections = 200

# 메모리
shared_buffers = 4GB
effective_cache_size = 12GB
work_mem = 64MB
maintenance_work_mem = 1GB

# WAL
wal_level = replica
max_wal_senders = 5
max_replication_slots = 5
wal_keep_size = 1GB

# 성능
random_page_cost = 1.1
effective_io_concurrency = 200
checkpoint_timeout = 15min
checkpoint_completion_target = 0.9
```

#### 1.3.2 Redis 7.2

**선택 이유**:
- **고성능**: 인메모리, 초저지연 (< 1ms)
- **다양한 자료구조**: String, Hash, List, Set, Sorted Set
- **Pub/Sub**: 이벤트 버스
- **Lua 스크립트**: 원자적 연산
- **Persistence**: AOF, RDB 스냅샷

**사용 용도**:
- **캐시**: Judgment 결과, BI 쿼리 결과
- **세션**: Chat 세션 상태
- **Pub/Sub**: 이벤트 발행/구독
- **Lock**: 분산 락 (Redlock 알고리즘)
- **Circuit Breaker**: 회로 차단 상태 저장

**redis.conf 설정**:
```conf
# 메모리
maxmemory 16gb
maxmemory-policy allkeys-lru

# 지속성
appendonly yes
appendfsync everysec

# 스냅샷
save 900 1
save 300 10
save 60 10000

# 복제
replica-read-only yes
min-replicas-to-write 1
min-replicas-max-lag 10
```

### 1.4 LLM 및 AI/ML 스택

#### 1.4.1 LLM API

**지원 모델**:

| 제공자 | 모델 | 용도 | 비용 (1M 토큰) |
|--------|------|------|----------------|
| **OpenAI** | GPT-4 | 복잡한 판단, RCA | $30 / $60 (in/out) |
| **OpenAI** | GPT-4o | 중간 복잡도, BI 플래너 | $2.5 / $10 |
| **OpenAI** | GPT-4o-mini | Intent 분류, 간단한 판단 | $0.15 / $0.6 |
| **Anthropic** | Claude-3-Opus | 최고 품질 판단 | $15 / $75 |
| **Anthropic** | Claude-3-Sonnet | 균형 잡힌 판단 | $3 / $15 |
| **Anthropic** | Claude-3-Haiku | 저비용 빠른 응답 | $0.25 / $1.25 |
| **OpenAI** | text-embedding-3-small | 벡터 임베딩 (1536 차원) | $0.02 |

**모델 선택 전략**:
```python
def select_llm_model(task_complexity: str, user_tier: str) -> str:
    if user_tier == "free":
        return "gpt-4o-mini"

    if task_complexity == "low":
        return "gpt-4o-mini"
    elif task_complexity == "medium":
        return "gpt-4o"
    else:  # high
        return "gpt-4"

# 비용 추적
def track_llm_cost(model: str, input_tokens: int, output_tokens: int):
    cost_table = {
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4o": {"input": 0.0025, "output": 0.01},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    }

    cost = (
        input_tokens / 1000 * cost_table[model]["input"] +
        output_tokens / 1000 * cost_table[model]["output"]
    )

    # DB 저장
    save_llm_call_log(model, input_tokens, output_tokens, cost)
```

#### 1.4.2 Machine Learning 라이브러리

**Rule 자동 추출**:
```python
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score

# 학습 샘플 로드
samples = load_learning_samples(workflow_id="wf-001")
X = [s['input_data'] for s in samples]
y = [s['expected_output']['status'] for s in samples]

# Train/Test 분할 (70/30)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)

# Decision Tree 학습
clf = DecisionTreeClassifier(max_depth=5, min_samples_split=10)
clf.fit(X_train, y_train)

# 예측 및 평가
y_pred = clf.predict(X_test)
precision = precision_score(y_test, y_pred, average='weighted')
recall = recall_score(y_test, y_pred, average='weighted')
f1 = f1_score(y_test, y_pred, average='weighted')

print(f"Precision: {precision:.2f}, Recall: {recall:.2f}, F1: {f1:.2f}")

# Decision Tree → Rhai 코드 변환
tree_rules = export_text(clf, feature_names=['defect_rate', 'line_code', 'shift'])
rhai_code = convert_tree_to_rhai(tree_rules)
```

**벡터 임베딩**:
```python
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_embedding(text: str) -> list[float]:
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
        encoding_format="float"
    )
    return response.data[0].embedding  # 1536 차원

# 문서 벡터화
doc_text = "LINE-A 설비 점검 매뉴얼: 온도 센서 캘리브레이션..."
embedding = generate_embedding(doc_text)

# pgvector에 저장
save_embedding(doc_id, embedding)
```

### 1.5 인프라 및 DevOps

#### 1.5.1 Kubernetes 버전 및 설정

**Kubernetes 1.28** (AWS EKS, GKE, AKS)

**클러스터 구성**:
- **Node Pool 1 (서비스)**: t3.large × 5~10 (Auto-scaling)
- **Node Pool 2 (DB)**: r6i.2xlarge × 3 (StatefulSet)
- **Node Pool 3 (모니터링)**: t3.large × 1

**kube-system 애드온**:
- **metrics-server**: HPA 메트릭 수집
- **cluster-autoscaler**: 노드 Auto-scaling
- **aws-load-balancer-controller**: ALB 관리 (AWS)
- **cert-manager**: TLS 인증서 자동 관리

#### 1.5.2 Helm Charts

**Helm을 통한 애플리케이션 배포**:

```yaml
# values.yaml
global:
  environment: production
  tenantId: default

judgmentService:
  image: factory-ai/judgment-service:v1.4.0
  replicas: 3
  resources:
    requests:
      cpu: 500m
      memory: 512Mi
    limits:
      cpu: 2000m
      memory: 2Gi
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 10
    targetCPUUtilizationPercentage: 70

postgresql:
  enabled: true
  image: postgres:14-alpine
  persistence:
    size: 500Gi
  replication:
    enabled: true
    replicas: 2

redis:
  enabled: true
  image: redis:7.2-alpine
  sentinel:
    enabled: true
    quorum: 2
```

**Helm 설치 명령**:
```bash
# Helm Chart 설치
helm install factory-ai ./helm/factory-ai \
  --namespace production \
  --create-namespace \
  --values values-production.yaml

# 업그레이드
helm upgrade factory-ai ./helm/factory-ai \
  --namespace production \
  --values values-production.yaml

# 롤백
helm rollback factory-ai 1 --namespace production
```

---

## 2. 아키텍처 결정 기록 (ADR)

### 2.1 ADR 템플릿

```markdown
# ADR-{번호}: {제목}

**날짜**: YYYY-MM-DD
**상태**: Proposed | Accepted | Rejected | Superseded
**컨텍스트**: 결정이 필요한 배경 및 문제
**결정**: 최종 선택 및 이유
**대안**: 고려했지만 채택하지 않은 옵션
**결과**: 결정의 영향 및 트레이드오프
**관련 문서**: A-2, B-3 등
```

---

### 2.2 주요 ADR

#### ADR-001: 프로그래밍 언어 선택 (Python vs Node.js vs Go)

**날짜**: 2025-10-15
**상태**: Accepted

**컨텍스트**:
- Backend 서비스 개발 언어 선택 필요
- AI/ML 통합, LLM 연동, 빠른 개발 중요
- 성능, 타입 안전성, 생태계 고려

**결정**: **Python 3.11 + FastAPI** 선택

**이유**:
- AI/ML 생태계 (scikit-learn, pandas) 우수
- LLM API 공식 지원 (OpenAI, LangChain)
- FastAPI의 높은 성능 (uvicorn, ASGI)
- Pydantic으로 타입 안전성 확보
- 빠른 개발 속도 (MVP 우선)

**대안**:
- **Node.js (TypeScript)**: 타입 안전성 우수, 비동기 I/O 우수하지만 AI/ML 생태계 약함
- **Go**: 성능 우수, 동시성 우수하지만 AI/ML 라이브러리 부족, 개발 속도 느림

**결과**:
- 장점: 빠른 MVP 개발, AI/ML 통합 용이
- 단점: Node.js 대비 약간 낮은 동시성 성능 (비동기 I/O로 완화)
- 트레이드오프: 개발 속도 > 성능 (초기 단계에서 적절한 선택)

---

#### ADR-002: Rule 엔진 선택 (Rhai vs Lua vs Python Eval)

**날짜**: 2025-10-20
**상태**: Accepted

**컨텍스트**:
- Rule 스크립트 실행 엔진 필요
- 안전성 (샌드박스), 성능, 표현력 중요
- Python eval()은 보안 위험

**결정**: **Rhai** 선택

**이유**:
- **Rust 기반**: 메모리 안전성, 고성능
- **샌드박스**: 파일/네트워크 접근 차단, 안전한 실행
- **타입 시스템**: 동적이지만 런타임 타입 체크
- **표현력**: Rust와 유사한 문법, 조건문/반복문 지원
- **Python 바인딩**: rhai-py로 쉽게 통합

**대안**:
- **Lua**: 성능 우수, 임베딩 용이하지만 타입 안전성 부족, 생태계 작음
- **Python eval()**: 표현력 최고지만 보안 위험 (임의 코드 실행), 샌드박스 어려움
- **Rego (OPA)**: 정책 언어로 적합하지만 범용 Rule 표현에는 제한적

**결과**:
- 장점: 안전한 Rule 실행, 성능 우수 (Rust 기반)
- 단점: Rhai 학습 곡선, 디버깅 도구 부족
- 트레이드오프: 안전성 > 편의성

---

#### ADR-003: 데이터베이스 선택 (PostgreSQL vs MySQL vs MongoDB)

**날짜**: 2025-10-18
**상태**: Accepted

**컨텍스트**:
- 주 데이터베이스 선택 필요
- ACID, JSONB, 벡터 검색, 파티셔닝 필요
- 멀티테넌트 격리, 고성능 쿼리

**결정**: **PostgreSQL 14+** 선택

**이유**:
- **JSONB**: 유연한 메타데이터 저장 (workflow context, llm metadata)
- **pgvector**: 벡터 임베딩 저장 및 유사도 검색 (RAG)
- **파티셔닝**: 대용량 시계열 데이터 관리
- **ACID**: 트랜잭션 안정성
- **성숙도**: 30년 이상 검증, 풍부한 도구

**대안**:
- **MySQL**: 성능 우수하지만 JSONB 지원 약함, 벡터 검색 미지원
- **MongoDB**: JSONB 우수하지만 ACID 약함, 벡터 검색 지원하지만 성숙도 낮음
- **Cassandra**: 확장성 우수하지만 복잡도 높음, ACID 약함

**결과**:
- 장점: JSONB + 벡터 검색 + ACID 모두 지원
- 단점: 수평 확장 어려움 (샤딩 필요 시 복잡)
- 트레이드오프: 기능 완전성 > 수평 확장성 (초기에는 적절)

---

#### ADR-004: API 통신 방식 (REST vs gRPC vs GraphQL)

**날짜**: 2025-10-22
**상태**: Accepted

**컨텍스트**:
- 서비스 간 통신 프로토콜 선택
- 개발 편의성, 성능, 클라이언트 호환성 고려

**결정**: **REST (JSON)** 우선, 성능 필요 시 **gRPC** 추가

**이유**:
- **REST**:
  - 개발 편의성 (FastAPI 기본 지원)
  - 클라이언트 호환성 (Web, Slack, 모바일)
  - 디버깅 용이 (Postman, cURL)
- **gRPC** (선택적):
  - 고빈도 내부 호출 시 성능 우수 (Judgment Engine 내부 모듈)
  - 타입 안전성 (Protocol Buffers)
  - 스트리밍 지원

**대안**:
- **GraphQL**: 유연한 쿼리하지만 복잡도 높음, 캐싱 어려움
- **gRPC Only**: 성능 최고지만 Web 클라이언트 호환성 낮음 (gRPC-Web 필요)

**결과**:
- 장점: 개발 속도, 클라이언트 호환성
- 단점: REST는 gRPC 대비 느림 (하지만 충분히 빠름)
- 트레이드오프: 개발 편의성 > 성능 (초기), 필요 시 gRPC 추가

---

#### ADR-005: 캐시 전략 (Redis vs Memcached vs In-Memory)

**날짜**: 2025-10-25
**상태**: Accepted

**컨텍스트**:
- 캐시 솔루션 선택 필요
- 고성능, Pub/Sub, 분산 락 필요

**결정**: **Redis 7.2** 선택

**이유**:
- **다양한 자료구조**: String, Hash, List, Set (Memcached는 Key-Value만)
- **Pub/Sub**: 이벤트 버스로 활용 가능
- **Lua 스크립트**: 원자적 연산 지원
- **Persistence**: AOF, RDB로 재시작 후 복구
- **Sentinel**: 고가용성 자동 Failover

**대안**:
- **Memcached**: 성능 우수하지만 기능 제한적 (Key-Value만), Pub/Sub 미지원
- **In-Memory (Python dict)**: 빠르지만 분산 환경 미지원, 재시작 시 손실

**결과**:
- 장점: 풍부한 기능, Pub/Sub, 분산 락
- 단점: Memcached 대비 약간 느림 (하지만 충분히 빠름)
- 트레이드오프: 기능 > 성능

---

#### ADR-006: 이벤트 버스 (Redis Pub/Sub vs RabbitMQ vs Kafka)

**날짜**: 2025-10-28
**상태**: Accepted (Redis Pub/Sub 우선, 향후 RabbitMQ 고려)

**컨텍스트**:
- 서비스 간 비동기 이벤트 전달 필요
- 이벤트 타입: judgment.executed, rule.deployed, workflow.completed
- 처리량: 초기 ~100 events/sec

**결정**: **Redis Pub/Sub** 선택 (초기), 처리량 증가 시 **RabbitMQ** 전환

**이유**:
- **Redis Pub/Sub**:
  - 이미 Redis 사용 중 (캐시)
  - 간단한 설정
  - 저지연 (< 10ms)
  - 초기 처리량 (< 1000 events/sec) 충분
- **향후 RabbitMQ**:
  - 높은 처리량 (> 10,000 events/sec)
  - 메시지 지속성 (Redis Pub/Sub은 메모리만)
  - Dead Letter Queue (DLQ)

**대안**:
- **Kafka**: 최고 처리량 (> 100,000 events/sec), 복잡도 높음, 초기 오버스펙
- **RabbitMQ**: 안정성 우수, 기능 풍부하지만 초기에는 Redis로 충분

**결과**:
- 장점: 간단한 구성, 저지연
- 단점: 메시지 지속성 없음 (재시작 시 손실), 처리량 제한적
- 트레이드오프: 단순성 > 기능 (초기), 향후 마이그레이션 계획

---

#### ADR-007: ORM 사용 여부 (SQLAlchemy vs Raw SQL)

**날짜**: 2025-10-30
**상태**: Accepted (SQLAlchemy ORM + Raw SQL 혼용)

**컨텍스트**:
- DB 접근 방식 선택
- 개발 생산성, 성능, 유지보수성 고려

**결정**: **SQLAlchemy 2.0 ORM** 사용, 복잡한 쿼리는 **Raw SQL**

**이유**:
- **SQLAlchemy ORM**:
  - 개발 생산성 (CRUD 간편)
  - 타입 안전성 (SQLAlchemy 모델)
  - 마이그레이션 (Alembic 연동)
  - DB 독립성 (PostgreSQL ↔ MySQL 전환 가능)
- **Raw SQL** (선택적):
  - 복잡한 집계 쿼리 (BI, Pre-agg)
  - 성능 최적화 (Index Hint, CTE)
  - 벡터 검색 (pgvector 함수)

**대안**:
- **Raw SQL Only**: 성능 최고하지만 생산성 낮음, SQL Injection 위험
- **ORM Only**: 생산성 높지만 복잡한 쿼리 제한적, N+1 문제

**결과**:
- 장점: 생산성 + 성능 균형
- 단점: 두 가지 방식 혼용으로 복잡도 증가
- 트레이드오프: 균형 잡힌 선택

**사용 가이드**:
```python
# ✅ ORM 사용 (CRUD)
from sqlalchemy.orm import Session
from models import JudgmentExecution

def create_judgment(session: Session, data: dict):
    judgment = JudgmentExecution(**data)
    session.add(judgment)
    session.commit()
    return judgment

# ✅ Raw SQL 사용 (복잡한 집계)
def get_oee_stats(session: Session, line_code: str, start_date: str):
    query = """
    SELECT
        date,
        AVG(availability * performance * quality) AS oee
    FROM fact_daily_production
    WHERE line_code = :line_code AND date >= :start_date
    GROUP BY date
    ORDER BY date ASC
    """
    result = session.execute(text(query), {
        "line_code": line_code,
        "start_date": start_date
    })
    return result.fetchall()
```

---

#### ADR-008: 프론트엔드 상태 관리 (Redux vs Zustand vs React Query)

**날짜**: 2025-11-01
**상태**: Accepted

**컨텍스트**:
- 클라이언트 상태 관리 라이브러리 선택
- 서버 상태 (API 데이터) vs 클라이언트 상태 (UI 상태)

**결정**: **React Query** (서버 상태) + **Zustand** (클라이언트 상태)

**이유**:
- **React Query**:
  - 서버 데이터 캐싱, 자동 리프레시
  - Optimistic Update, Infinite Query
  - 에러/로딩 상태 자동 관리
- **Zustand**:
  - 경량 (Redux 대비 간단)
  - TypeScript 친화적
  - Middleware 지원 (persist, devtools)

**대안**:
- **Redux**: 강력하지만 보일러플레이트 많음, 초기 학습 곡선
- **Context API**: 간단하지만 성능 이슈 (불필요한 리렌더링)

**결과**:
- 장점: 간결한 코드, 서버/클라이언트 상태 명확히 분리
- 단점: 두 라이브러리 학습 필요
- 트레이드오프: 단순성 + 기능

**사용 예시**:
```typescript
// React Query (서버 상태)
import { useQuery, useMutation } from '@tanstack/react-query';

function useJudgment(judgmentId: string) {
  return useQuery({
    queryKey: ['judgment', judgmentId],
    queryFn: () => fetchJudgment(judgmentId),
    staleTime: 5 * 60 * 1000, // 5분
  });
}

function useExecuteJudgment() {
  return useMutation({
    mutationFn: (input: JudgmentInput) => executeJudgment(input),
    onSuccess: () => {
      queryClient.invalidateQueries(['judgments']);
    },
  });
}

// Zustand (클라이언트 상태)
import create from 'zustand';

interface UIState {
  sidebarOpen: boolean;
  theme: 'light' | 'dark';
  toggleSidebar: () => void;
  setTheme: (theme: 'light' | 'dark') => void;
}

const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  theme: 'light',
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setTheme: (theme) => set({ theme }),
}));
```

---

#### ADR-009: 배포 전략 (Blue-Green vs Canary vs Rolling)

**날짜**: 2025-11-05
**상태**: Accepted

**컨텍스트**:
- Rule/Prompt 배포 시 안전한 배포 전략 필요
- 서비스 중단 최소화, 빠른 롤백 지원

**결정**: **Canary 배포** 우선, **Blue-Green** 선택적 사용

**이유**:
- **Canary**:
  - 점진적 트래픽 전환 (10% → 50% → 100%)
  - 실시간 모니터링으로 문제 조기 발견
  - 자동 롤백 (성공 기준 미달 시)
  - 위험 최소화 (일부 사용자만 영향)
- **Blue-Green** (선택적):
  - 즉시 전환 (100% 트래픽)
  - 빠른 롤백 (Blue ↔ Green 스위칭)
  - 리소스 2배 필요 (비용)

**대안**:
- **Rolling Update**: Kubernetes 기본, 서비스 배포에는 적합하지만 Rule 버전 관리에는 부적합
- **Blue-Green Only**: 리소스 비용 높음, Canary 대비 위험 높음

**결과**:
- 장점: 안전한 점진적 배포, 자동 롤백
- 단점: 복잡한 트래픽 라우팅 로직 필요
- 트레이드오프: 안정성 > 단순성

---

#### ADR-010: 모니터링 스택 (Prometheus vs Datadog vs New Relic)

**날짜**: 2025-11-08
**상태**: Accepted

**컨텍스트**:
- 시스템 메트릭 수집 및 시각화 솔루션 선택
- 오픈소스 vs 상용, 비용, 기능 고려

**결정**: **Prometheus + Grafana** (오픈소스)

**이유**:
- **무료**: 오픈소스, 비용 없음
- **풍부한 생태계**: Exporters, Alertmanager, 커뮤니티
- **Kubernetes 네이티브**: Service Discovery, Pod 메트릭
- **PromQL**: 강력한 쿼리 언어
- **Grafana**: 우수한 시각화

**대안**:
- **Datadog**: 기능 강력하지만 비용 높음 ($15~$23/host/월)
- **New Relic**: APM 우수하지만 비용 높음, Vendor Lock-in

**결과**:
- 장점: 비용 절감, Kubernetes 통합 우수
- 단점: 초기 설정 복잡, 상용 대비 일부 기능 부족
- 트레이드오프: 비용 > 편의성

---

## 3. 마이그레이션 전략

### 3.1 데이터베이스 마이그레이션 (Alembic)

#### 3.1.1 마이그레이션 파일 구조

```
alembic/
├── versions/
│   ├── 20251101_1000__initial_schema.py
│   ├── 20251110_1500__add_confidence_field.py
│   ├── 20251115_0900__create_bi_tables.py
│   └── 20251120_1400__add_rag_embeddings.py
├── env.py
├── script.py.mako
└── alembic.ini
```

#### 3.1.2 마이그레이션 버전 명명 규칙

**형식**: `V{YYYYMMDD}_{HHMM}__{description}.py`

**예시**:
- `20251126_1600__add_judgment_confidence.py`
- `20251127_0900__create_bi_datasets_table.py`

#### 3.1.3 마이그레이션 예시

```python
# alembic/versions/20251126_1600__add_judgment_confidence.py
"""Add confidence field to judgment_executions

Revision ID: a1b2c3d4e5f6
Revises: f6e5d4c3b2a1
Create Date: 2025-11-26 16:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'f6e5d4c3b2a1'
branch_labels = None
depends_on = None

def upgrade():
    # confidence 컬럼 추가 (nullable=True)
    op.add_column('judgment_executions',
        sa.Column('confidence', sa.Float, nullable=True),
        schema='core'
    )

    # 기존 데이터 기본값 설정
    op.execute("""
        UPDATE core.judgment_executions
        SET confidence = 0.5
        WHERE confidence IS NULL
    """)

    # nullable=False로 변경
    op.alter_column('judgment_executions', 'confidence',
        existing_type=sa.Float,
        nullable=False,
        schema='core'
    )

    # 인덱스 추가
    op.create_index(
        'idx_judgment_executions_confidence',
        'judgment_executions',
        ['tenant_id', 'confidence'],
        schema='core'
    )

def downgrade():
    # 인덱스 삭제
    op.drop_index('idx_judgment_executions_confidence', schema='core')

    # confidence 컬럼 삭제
    op.drop_column('judgment_executions', 'confidence', schema='core')
```

**마이그레이션 실행**:
```bash
# 현재 버전 확인
alembic current

# 최신 버전으로 업그레이드
alembic upgrade head

# 특정 버전으로 업그레이드
alembic upgrade a1b2c3d4e5f6

# 한 버전 롤백
alembic downgrade -1

# 마이그레이션 이력
alembic history
```

### 3.2 Zero-Downtime 배포 전략

#### 3.2.1 Rolling Update (Kubernetes)

**기본 배포 방식**: Kubernetes Rolling Update

```yaml
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 1
```

**배포 흐름**:
```
1. 새 버전 이미지 빌드 및 푸시
2. Deployment 업데이트 (image: v1.5.0)
3. Kubernetes가 하나씩 Pod 교체
   - Pod 3개 중 1개 종료 (maxUnavailable: 1)
   - 새 버전 Pod 시작
   - Readiness Probe 통과 확인
   - 다음 Pod 교체
4. 모든 Pod 교체 완료
5. 총 배포 시간: 3~5분
```

#### 3.2.2 데이터베이스 마이그레이션 Zero-Downtime

**전략**: Backward Compatible Migration (호환 마이그레이션)

**단계**:
1. **Phase 1**: 새 컬럼 추가 (nullable=True)
2. **Phase 2**: 애플리케이션 배포 (신규 컬럼 사용)
3. **Phase 3**: 데이터 마이그레이션 (기존 데이터 변환)
4. **Phase 4**: 구 컬럼 삭제 (다음 배포)

**예시**: `method_used` 컬럼 추가
```python
# Phase 1: 컬럼 추가 (nullable)
def upgrade_phase1():
    op.add_column('judgment_executions',
        sa.Column('method_used', sa.String(50), nullable=True)
    )

# Phase 2: 애플리케이션 배포 (신규 컬럼 사용 시작)
# judgment_service v1.5.0에서 method_used 저장 시작

# Phase 3: 기존 데이터 마이그레이션
def upgrade_phase3():
    op.execute("""
        UPDATE core.judgment_executions
        SET method_used = 'unknown'
        WHERE method_used IS NULL
    """)

    op.alter_column('judgment_executions', 'method_used',
        nullable=False
    )

# Phase 4: 구 컬럼 삭제 (다음 릴리스에서)
# (필요 시)
```

---

## 4. 성능 최적화 전략

### 4.1 데이터베이스 최적화

#### 4.1.1 Connection Pooling

**목적**: DB 연결 재사용, 연결 오버헤드 감소

**SQLAlchemy Pool 설정**:
```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,          # 기본 연결 수
    max_overflow=40,       # 최대 추가 연결
    pool_timeout=30,       # 연결 대기 타임아웃
    pool_recycle=3600,     # 연결 재사용 시간 (1시간)
    pool_pre_ping=True,    # 연결 유효성 사전 확인
    echo=False
)
```

**모니터링**:
```sql
-- 활성 연결 수
SELECT count(*) FROM pg_stat_activity WHERE state = 'active';

-- 대기 중인 연결
SELECT count(*) FROM pg_stat_activity WHERE wait_event IS NOT NULL;
```

#### 4.1.2 Query Optimization

**인덱스 활용**:
```sql
-- Before (Full Table Scan)
SELECT * FROM judgment_executions
WHERE workflow_id = '...' AND executed_at > '2025-11-01';
-- Seq Scan on judgment_executions (cost=0.00..50000.00)

-- After (Index Scan)
CREATE INDEX idx_judgment_executions_workflow_time
ON judgment_executions(tenant_id, workflow_id, executed_at DESC);

SELECT * FROM judgment_executions
WHERE tenant_id = '...' AND workflow_id = '...' AND executed_at > '2025-11-01';
-- Index Scan using idx_judgment_executions_workflow_time (cost=0.43..120.50)
```

**쿼리 힌트** (필요 시):
```sql
-- 특정 인덱스 강제 사용 (PostgreSQL은 힌트 미지원, 통계 업데이트로 유도)
ANALYZE judgment_executions;
```

#### 4.1.3 Pre-aggregation (Materialized Views)

**목적**: 반복 집계 쿼리 성능 최적화

**Materialized View 예시**:
```sql
CREATE MATERIALIZED VIEW mv_oee_daily AS
SELECT
  tenant_id,
  date,
  line_code,
  shift,
  SUM(runtime_minutes)::numeric / NULLIF(SUM(runtime_minutes + downtime_minutes), 0) AS availability,
  SUM(actual_production)::numeric / NULLIF(SUM(target_production), 0) AS performance,
  1 - (SUM(defect_count)::numeric / NULLIF(SUM(production_count), 0)) AS quality,
  (
    SUM(runtime_minutes)::numeric / NULLIF(SUM(runtime_minutes + downtime_minutes), 0) *
    SUM(actual_production)::numeric / NULLIF(SUM(target_production), 0) *
    (1 - SUM(defect_count)::numeric / NULLIF(SUM(production_count), 0))
  ) AS oee
FROM fact_daily_production
GROUP BY tenant_id, date, line_code, shift;

-- 인덱스
CREATE INDEX idx_mv_oee_daily_tenant_line_date
ON mv_oee_daily(tenant_id, line_code, date DESC);

-- 리프레시 (일 1회)
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_oee_daily;
```

**리프레시 스케줄** (Cron):
```bash
# crontab
0 6 * * * psql -h localhost -U postgres -d factory_ai -c "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_oee_daily;"
```

### 4.2 캐시 최적화

#### 4.2.1 Cache-Aside Pattern

**목적**: 캐시 미스 시 DB 조회 후 캐시 저장

**구현**:
```python
async def get_judgment_with_cache(workflow_id: str, input_data: dict) -> dict:
    cache_key = get_cache_key(workflow_id, input_data)

    # 1. 캐시 조회
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # 2. 캐시 미스 → DB 조회
    result = await execute_judgment(workflow_id, input_data)

    # 3. 캐시 저장 (TTL 300초)
    await redis_client.setex(cache_key, 300, json.dumps(result))

    return result
```

#### 4.2.2 Cache Invalidation (캐시 무효화)

**전략**: Event-driven Invalidation

**예시**: Rule 배포 시 캐시 무효화
```python
# Learning Service (Rule 배포 시)
async def deploy_ruleset(ruleset_id: str, workflow_id: str):
    # 1. Rule 배포
    await update_ruleset_version(ruleset_id)

    # 2. 캐시 무효화
    pattern = f"judgment:cache:{workflow_id}:*"
    keys = await redis_client.keys(pattern)
    if keys:
        await redis_client.delete(*keys)

    # 3. 이벤트 발행
    await publish_event('rule.deployed', {
        'ruleset_id': ruleset_id,
        'workflow_id': workflow_id,
        'version': 'v1.4.0'
    })
```

### 4.3 LLM 최적화

#### 4.3.1 Prompt Caching (OpenAI)

**목적**: System Prompt 재사용으로 비용 절감

**OpenAI Prompt Caching**:
```python
from openai import OpenAI

client = OpenAI()

# System Prompt (캐싱 가능, 1024 토큰 이상 권장)
system_prompt = """
You are a manufacturing quality expert...
[긴 프롬프트, 1500 토큰]
"""

response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": system_prompt},  # 캐시됨
        {"role": "user", "content": f"Analyze: {input_data}"}  # 매번 변경
    ],
    temperature=0.7
)

# 비용: System Prompt는 캐시 사용 시 50% 할인
```

#### 4.3.2 배치 처리 (Batch Processing)

**목적**: 여러 요청을 한 번에 처리하여 API 호출 감소

**예시**: 여러 문서 임베딩 한 번에 생성
```python
from openai import OpenAI

client = OpenAI()

documents = [
    "LINE-A 설비 점검 매뉴얼...",
    "PROD-123 생산 지침서...",
    "불량 처리 절차..."
]

# 배치 임베딩 (최대 2048개)
response = client.embeddings.create(
    model="text-embedding-3-small",
    input=documents,
    encoding_format="float"
)

embeddings = [data.embedding for data in response.data]
# → [[0.1, 0.2, ...], [0.3, 0.4, ...], [0.5, 0.6, ...]]

# 벡터 저장
for doc, embedding in zip(documents, embeddings):
    save_embedding(doc, embedding)
```

### 4.4 프론트엔드 최적화

#### 4.4.1 Code Splitting (코드 분할)

**목적**: 초기 로딩 시간 단축

**React Lazy Loading**:
```typescript
import React, { lazy, Suspense } from 'react';

// 코드 분할
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Judgment = lazy(() => import('./pages/Judgment'));
const Workflow = lazy(() => import('./pages/Workflow'));

function App() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/judgment" element={<Judgment />} />
        <Route path="/workflow" element={<Workflow />} />
      </Routes>
    </Suspense>
  );
}
```

**번들 분석**:
```bash
# Vite 빌드
npm run build

# 번들 사이즈
dist/
├── index.html
├── assets/
│   ├── index-a1b2c3d4.js       (200 KB)  # 메인 번들
│   ├── Dashboard-e5f6a7b8.js   (50 KB)   # 코드 분할
│   ├── Judgment-c9d0e1f2.js    (80 KB)
│   └── Workflow-g3h4i5j6.js    (120 KB)
```

#### 4.4.2 API 요청 최적화 (React Query)

**캐싱 전략**:
```typescript
import { useQuery } from '@tanstack/react-query';

function useJudgmentList(workflowId: string) {
  return useQuery({
    queryKey: ['judgments', workflowId],
    queryFn: () => fetchJudgments(workflowId),
    staleTime: 5 * 60 * 1000,      // 5분 동안 fresh
    cacheTime: 10 * 60 * 1000,     // 10분 동안 캐시 유지
    refetchOnWindowFocus: false,   // 윈도우 포커스 시 리프레시 안 함
    retry: 3,                      // 실패 시 3회 재시도
  });
}
```

---

## 결론

본 문서(B-1)는 **제조업 AI 플랫폼 (AI Factory Decision Engine)** 의 시스템 아키텍처를 포괄적으로 명세하였다.

### 문서 구성 요약
- **B-1-1**: 아키텍처 개요, 설계 원칙, 논리적 아키텍처, 계층 구조, 서비스 경계
- **B-1-2**: 물리적 아키텍처, 배포 아키텍처 (Kubernetes), 데이터 아키텍처, 네트워크 아키텍처
- **B-1-3**: 통합 아키텍처 (MCP, DB Connector, MQTT), 보안 아키텍처 (Auth, 암호화, PII), 확장성 아키텍처 (HPA, 샤딩), 가용성/DR 아키텍처
- **B-1-4**: 기술 스택 상세, 아키텍처 결정 기록 (ADR 10개), 마이그레이션 전략, 성능 최적화

### 주요 성과
1. **10개 ADR 문서화**: 기술 선택 근거 명확화
2. **4계층 아키텍처**: Presentation, Application, Domain, Infrastructure
3. **7개 Bounded Context**: Judgment, Workflow, BI, Learning, MCP Hub, Data Hub, Chat
4. **고가용성 설계**: Multi-AZ, PostgreSQL Replication, Redis Sentinel
5. **확장성 전략**: HPA, Stateless 서비스, 파티셔닝, 샤딩 (향후)
6. **보안 아키텍처**: TLS, JWT, AES-256, PII 마스킹, RBAC
7. **성능 최적화**: Connection Pool, Pre-agg, Cache, Code Splitting

### 다음 단계
1. B-2 Module/Service Design 상세 설계
2. 프로토타입 개발 (Judgment + Workflow 핵심 기능)
3. 인프라 구축 (Kubernetes 클러스터, PostgreSQL, Redis)
4. CI/CD 파이프라인 구축
5. 보안 감사 (OWASP ZAP, 침투 테스트)

---

## 문서 이력
| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2025-11-26 | AI Factory Team | 초안 작성 (B-1-1~B-1-4 통합) |

---

**문서 끝**
