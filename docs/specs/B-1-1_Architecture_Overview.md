# B-1-1. System Architecture Specification - Overview & Logical Architecture

## 문서 정보
- **문서 ID**: B-1-1
- **버전**: 1.0
- **최종 수정일**: 2025-11-26
- **상태**: Draft
- **관련 문서**:
  - A-2 System Requirements Spec
  - B-2 Module/Service Design
  - B-3 Data/DB Schema
  - B-4 API Interface Spec
  - B-5 Workflow/State Machine Spec
  - B-6 AI/Agent/Prompt Spec

## 목차
1. [아키텍처 개요](#1-아키텍처-개요)
2. [설계 원칙 및 철학](#2-설계-원칙-및-철학)
3. [논리적 아키텍처](#3-논리적-아키텍처)
4. [계층 구조 (Layered Architecture)](#4-계층-구조-layered-architecture)
5. [서비스 경계 (Bounded Context)](#5-서비스-경계-bounded-context)
6. [데이터 흐름 (Data Flow)](#6-데이터-흐름-data-flow)

---

## 1. 아키텍처 개요

### 1.1 시스템 비전
**AI Factory Decision Engine**은 제조 현장의 의사결정을 AI로 지원하는 플랫폼이다. Rule과 LLM을 하이브리드로 결합하여 정확하고 설명 가능한 판단을 제공하며, 자연어 기반 BI 분석, 워크플로우 자동화, 지속적 학습을 통해 제조업 디지털 전환을 가속화한다.

### 1.2 아키텍처 목표

| 목표 | 설명 | 측정 지표 |
|------|------|----------|
| **정확성** | Rule + LLM Hybrid로 높은 판단 정확도 | 정확도 > 90%, 오탐률 < 5% |
| **응답성** | 실시간 의사결정 지원 | Judgment < 1.5s, BI < 3s |
| **확장성** | 사용자/데이터 증가 대응 | 수평 확장, 500명 동시 사용자 |
| **유연성** | DSL 기반 워크플로우, MCP 표준 연동 | 워크플로우 생성 < 1시간, MCP 추가 < 1일 |
| **학습성** | 피드백 기반 지속 개선 | Rule 자동 추출, 정확도 향상 추세 |
| **안정성** | 고가용성 및 장애 복구 | 가용성 99.9%, RTO 4시간 |
| **보안성** | 멀티테넌트 격리, 인증/암호화 | PII 마스킹 100%, TLS 1.2+ |

### 1.3 아키텍처 스타일

본 시스템은 다음 아키텍처 패턴을 조합한다:

#### 1.3.1 마이크로서비스 아키텍처 (Microservices)
- **이유**: 독립적 배포, 기술 스택 유연성, 수평 확장
- **서비스 분할**: Judgment, Workflow, BI, Chat, Learning, MCP Hub, Data Hub
- **통신**: REST API (동기), Redis Pub/Sub (비동기), gRPC (고성능 필요 시)
- **데이터**: 서비스별 독립 스키마, 공유 DB (멀티테넌트 격리)

#### 1.3.2 이벤트 기반 아키텍처 (Event-Driven)
- **이유**: 비동기 처리, 느슨한 결합, 확장성
- **이벤트 타입**:
  - `judgment.executed`: 판단 완료 시 발행 → Learning Service 구독
  - `rule.deployed`: Rule 배포 시 발행 → Cache 무효화, 알람 발송
  - `workflow.completed`: Workflow 완료 시 발행 → 후속 액션 트리거
  - `drift.detected`: 스키마 변경 감지 → ETL 중단, 알람 발송
- **이벤트 브로커**: Redis Pub/Sub (경량) 또는 RabbitMQ (엔터프라이즈)

#### 1.3.3 계층형 아키텍처 (Layered Architecture)
- **Presentation Layer**: Web UI, Slack Bot, API Gateway
- **Application Layer**: Intent Router, Planner, Executor
- **Domain Layer**: Judgment, Workflow, BI, Learning, MCP Hub
- **Infrastructure Layer**: DB, Cache, Storage, Logging, Monitoring

#### 1.3.4 Hexagonal Architecture (Ports & Adapters)
- **Core Domain**: Judgment Engine, Workflow Engine (비즈니스 로직)
- **Ports**: 인터페이스 정의 (IJudgment, IWorkflow, IBIPlanner)
- **Adapters**: 구현체 (RhaiRuleEngine, OpenAIClient, PostgresRepository)
- **이점**: 테스트 용이성, 기술 교체 가능성 (예: PostgreSQL → MySQL)

### 1.4 배포 모델

본 시스템은 **클라우드/온프렘 겸용**으로 설계된다.

| 배포 방식 | 환경 | 장점 | 단점 |
|----------|------|------|------|
| **클라우드 (AWS/Azure/GCP)** | Kubernetes (EKS/AKS/GKE) | 탄력적 확장, 관리 편의성, 글로벌 배포 | 네트워크 지연, 비용, 데이터 주권 |
| **온프렘** | Kubernetes (RKE/K3s) | 데이터 통제, 낮은 지연, 규제 준수 | 초기 투자, 운영 부담, 확장 제약 |
| **하이브리드** | 클라우드 + 온프렘 | 민감 데이터 온프렘, 분석 클라우드 | 복잡한 네트워크, 데이터 동기화 |

**권장 배포**: 클라우드 우선 (AWS EKS), 고객 요청 시 온프렘 지원

---

## 2. 설계 원칙 및 철학

### 2.1 핵심 설계 원칙

#### 2.1.1 Separation of Concerns (관심사 분리)
- **원칙**: 각 서비스/모듈은 단일 책임을 가지며, 다른 관심사와 분리한다.
- **적용**:
  - Judgment Service: 판단 로직만 담당 (Workflow 실행 X)
  - Workflow Service: 실행 흐름 관리만 (판단 로직 X)
  - BI Service: 분석 계획 생성 및 실행만 (알림 발송 X)
- **이점**: 변경 영향 최소화, 테스트 용이성, 재사용성

#### 2.1.2 Loose Coupling (느슨한 결합)
- **원칙**: 서비스 간 의존성을 최소화하고, 인터페이스로만 통신한다.
- **적용**:
  - REST API 또는 이벤트를 통한 간접 통신
  - 직접 DB 접근 금지 (각 서비스는 자신의 스키마만 접근)
  - MCP ToolHub로 외부 시스템 추상화
- **이점**: 독립적 배포, 장애 격리, 기술 교체 가능

#### 2.1.3 High Cohesion (높은 응집도)
- **원칙**: 관련 기능은 동일 서비스/모듈에 위치한다.
- **적용**:
  - Judgment: Rule 실행 + LLM 호출 + Hybrid 결합 + 캐싱 (모두 함께)
  - Learning: 피드백 수집 + 샘플 큐레이션 + Rule 추출 + 배포 (모두 함께)
- **이점**: 코드 이해 용이, 변경 범위 최소화

#### 2.1.4 Fail-Safe Defaults (안전한 기본값)
- **원칙**: 에러 발생 시 안전한 기본 동작을 수행한다.
- **적용**:
  - LLM API 에러 시 Rule 결과 사용
  - MCP 타임아웃 시 Fallback 응답
  - Cache 장애 시 DB 직접 조회
  - Circuit Breaker OPEN 시 기본 응답
- **이점**: 부분 장애 시에도 서비스 지속

#### 2.1.5 Design for Failure (장애 대비 설계)
- **원칙**: 모든 외부 호출은 실패할 수 있다고 가정한다.
- **적용**:
  - 타임아웃 설정 (LLM 15s, MCP 5s, DB 10s)
  - 재시도 로직 (지수 백오프)
  - Circuit Breaker (실패율 추적)
  - Graceful Degradation (일부 기능 비활성화)
- **이점**: 안정성, 예측 가능한 동작

#### 2.1.6 Observability by Design (관찰 가능성 기본 설계)
- **원칙**: 모든 서비스는 로깅, 메트릭, 추적을 기본 제공한다.
- **적용**:
  - 구조화 로그 (JSON, trace_id, tenant_id)
  - Prometheus 메트릭 (Counter, Gauge, Histogram)
  - 분산 추적 (OpenTelemetry)
- **이점**: 문제 진단 용이, 성능 분석, SLO 측정

---

## 3. 논리적 아키텍처

### 3.1 전체 시스템 개요

```
┌─────────────────────────────────────────────────────────────────┐
│                   AI Factory Decision Engine                    │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Presentation Layer (UI/API)                 │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐         │  │
│  │  │  Web UI    │  │ Slack Bot  │  │ REST API   │         │  │
│  │  │  (React)   │  │  (Bolt)    │  │  Gateway   │         │  │
│  │  └────────────┘  └────────────┘  └────────────┘         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                           ▲                                     │
│                           │ HTTP/WebSocket                      │
│                           ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │           Application Layer (Orchestration)              │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐         │  │
│  │  │ Intent     │  │ Planner    │  │ Executor   │         │  │
│  │  │ Router     │  │ (LLM)      │  │ (Workflow) │         │  │
│  │  └────────────┘  └────────────┘  └────────────┘         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                           ▲                                     │
│                           │ Internal API                        │
│                           ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Domain Layer (Core Logic)                   │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐│  │
│  │  │Judgment  │  │Workflow  │  │    BI    │  │ Learning ││  │
│  │  │ Engine   │  │ Engine   │  │ Planner  │  │ Service  ││  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘│  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐               │  │
│  │  │   MCP    │  │   Data   │  │  Cache   │               │  │
│  │  │ ToolHub  │  │   Hub    │  │ Manager  │               │  │
│  │  └──────────┘  └──────────┘  └──────────┘               │  │
│  └──────────────────────────────────────────────────────────┘  │
│                           ▲                                     │
│                           │ Repository Interface                │
│                           ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │          Infrastructure Layer (Persistence)              │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐│  │
│  │  │PostgreSQL│  │  Redis   │  │ pgvector │  │ S3/Blob  ││  │
│  │  │(Primary) │  │ (Cache)  │  │ (Vector) │  │ (Files)  ││  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘│  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │       Cross-Cutting Concerns (횡단 관심사)                 │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐│  │
│  │  │   Auth   │  │  Audit   │  │Observab. │  │  Config  ││  │
│  │  │  (JWT)   │  │  Log     │  │(Metrics) │  │ (Vault)  ││  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘│  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

         ▲                                              ▲
         │                                              │
  ┌──────┴───────┐                              ┌──────┴───────┐
  │   External   │                              │  External    │
  │   Systems    │                              │     LLM      │
  │ (ERP/MES/IoT)│                              │   (OpenAI)   │
  └──────────────┘                              └──────────────┘
```

### 1.4 주요 기술적 결정 (High-Level)

| 결정 항목 | 선택 | 근거 |
|----------|------|------|
| **아키텍처 스타일** | Microservices + Event-Driven | 확장성, 독립 배포, 비동기 처리 |
| **프로그래밍 언어** | Python (FastAPI) | AI/ML 생태계, 빠른 개발, 풍부한 라이브러리 |
| **데이터베이스** | PostgreSQL 14+ | ACID, JSON 지원, 벡터 검색 (pgvector), 성숙도 |
| **캐시** | Redis 6+ | 고성능, Pub/Sub, Lua 스크립트, 성숙도 |
| **Rule 엔진** | Rhai | Rust 기반 안전성, 샌드박스, 성능 |
| **컨테이너** | Docker + Kubernetes | 이식성, 오케스트레이션, 자동 스케일링 |
| **API 게이트웨이** | Nginx 또는 Kong | 로드 밸런싱, TLS, Rate Limiting |
| **모니터링** | Prometheus + Grafana | 메트릭 수집, 시각화, 알람 |
| **로깅** | Loki 또는 ELK | 구조화 로그, 검색, 장기 보존 |

---

## 2. 설계 원칙 및 철학

### 2.1 Domain-Driven Design (DDD) 적용

#### 2.1.1 Bounded Context 식별
각 서비스는 명확한 도메인 경계를 가지며, 독립적으로 진화할 수 있다.

| Bounded Context | 핵심 개념 | 책임 |
|-----------------|----------|------|
| **Judgment Context** | Rule, LLM, Policy, Confidence | 입력 → 판단 결과 산출 |
| **Workflow Context** | DSL, Node, Edge, Instance, State | 다단계 워크플로우 실행 |
| **BI Context** | Dataset, Metric, Component, Plan | 자연어 → 분석 결과 |
| **Learning Context** | Feedback, Sample, Candidate, Deployment | 지속적 학습 및 개선 |
| **Integration Context** | MCP Server, Tool, Connector | 외부 시스템 연동 |
| **Chat Context** | Intent, Slot, Session, Message | 자연어 대화 처리 |

#### 2.1.2 유비쿼터스 언어 (Ubiquitous Language)
모든 팀원이 공통으로 사용하는 도메인 용어를 정의한다.

| 도메인 용어 | 정의 | 사용 예시 |
|------------|------|----------|
| **Judgment** | Rule + LLM Hybrid 판단 | "Judgment를 실행하여 불량 상태를 판정한다" |
| **Confidence** | 판단의 신뢰도 (0.0~1.0) | "Rule의 Confidence가 0.7 이하면 LLM Fallback" |
| **Ruleset** | Rule 스크립트 집합 (버전 관리 단위) | "Ruleset v1.3.0을 Canary 배포한다" |
| **Workflow DSL** | 워크플로우 정의 언어 | "Workflow DSL을 검증하고 저장한다" |
| **analysis_plan** | BI 분석 계획 (metrics, dimensions, filters) | "자연어를 analysis_plan으로 변환한다" |

### 2.2 SOLID 원칙 적용

#### 2.2.1 Single Responsibility (단일 책임)
각 클래스/모듈은 하나의 책임만 가진다.

**예시**:
```python
# ❌ 나쁜 예: 여러 책임
class JudgmentService:
    def execute(self, input_data):
        # 입력 검증
        # Rule 실행
        # LLM 호출
        # 캐시 저장
        # 로그 기록
        # 알람 발송
        pass

# ✅ 좋은 예: 단일 책임
class JudgmentService:
    def execute(self, input_data):
        # 판단 로직 오케스트레이션만 담당
        validated = self.validator.validate(input_data)
        rule_result = self.rule_engine.execute(validated)
        llm_result = self.llm_client.call(validated) if self.should_call_llm(rule_result) else None
        final_result = self.aggregator.combine(rule_result, llm_result)
        return final_result

class InputValidator:
    def validate(self, input_data): ...

class RuleEngine:
    def execute(self, input_data): ...

class LLMClient:
    def call(self, input_data): ...

class ResultAggregator:
    def combine(self, rule_result, llm_result): ...
```

#### 2.2.2 Open/Closed (개방/폐쇄)
확장에는 열려있고, 수정에는 닫혀있다.

**예시**:
```python
# ✅ 전략 패턴으로 확장 가능
class JudgmentPolicyStrategy(ABC):
    @abstractmethod
    def execute(self, input_data) -> JudgmentResult:
        pass

class RuleOnlyPolicy(JudgmentPolicyStrategy):
    def execute(self, input_data):
        return self.rule_engine.execute(input_data)

class LLMOnlyPolicy(JudgmentPolicyStrategy):
    def execute(self, input_data):
        return self.llm_client.call(input_data)

class HybridWeightedPolicy(JudgmentPolicyStrategy):
    def execute(self, input_data):
        rule_result = self.rule_engine.execute(input_data)
        llm_result = self.llm_client.call(input_data)
        return self.aggregator.combine(rule_result, llm_result)

# 새로운 정책 추가 시 기존 코드 수정 없음
class AdaptivePolicy(JudgmentPolicyStrategy):
    def execute(self, input_data):
        # 복잡도에 따라 동적 선택
        ...
```

#### 2.2.3 Dependency Inversion (의존성 역전)
고수준 모듈은 저수준 모듈에 의존하지 않고, 추상화에 의존한다.

**예시**:
```python
# ✅ 인터페이스에 의존
class JudgmentService:
    def __init__(
        self,
        rule_engine: IRuleEngine,  # 인터페이스
        llm_client: ILLMClient,    # 인터페이스
        cache: ICacheManager       # 인터페이스
    ):
        self.rule_engine = rule_engine
        self.llm_client = llm_client
        self.cache = cache

# 구현체는 외부에서 주입 (Dependency Injection)
judgment_service = JudgmentService(
    rule_engine=RhaiRuleEngine(),
    llm_client=OpenAIClient(),
    cache=RedisCacheManager()
)

# 테스트 시 Mock으로 교체 가능
test_judgment_service = JudgmentService(
    rule_engine=MockRuleEngine(),
    llm_client=MockLLMClient(),
    cache=MockCacheManager()
)
```

### 2.3 12-Factor App 준수

| Factor | 적용 | 설명 |
|--------|------|------|
| **I. Codebase** | Git 단일 저장소, 다중 배포 | Monorepo 또는 Multi-repo |
| **II. Dependencies** | requirements.txt, poetry | 명시적 의존성 선언 |
| **III. Config** | 환경변수, ConfigMap/Secret | DB URL, API Key 등 외부화 |
| **IV. Backing Services** | 첨부된 리소스 | DB, Redis, LLM API를 서비스로 취급 |
| **V. Build/Release/Run** | CI/CD 파이프라인 | 빌드 → 릴리스 → 실행 분리 |
| **VI. Processes** | Stateless | 상태는 DB/Redis에 저장 |
| **VII. Port Binding** | HTTP 8080, gRPC 50051 | 서비스 자체가 포트 바인딩 |
| **VIII. Concurrency** | HPA (Horizontal Scaling) | 프로세스 모델로 확장 |
| **IX. Disposability** | Graceful Shutdown | SIGTERM 처리, 연결 종료 |
| **X. Dev/Prod Parity** | Docker 이미지 동일 | 개발/스테이징/프로덕션 일관성 |
| **XI. Logs** | stdout, JSON 형식 | 로그 수집기로 전달 |
| **XII. Admin Processes** | 별도 스크립트 | 마이그레이션, 시딩 스크립트 |

---

## 3. 논리적 아키텍처

### 3.1 서비스 맵 (Service Map)

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Layer                             │
│  Web UI (React) │ Slack Bot │ Mobile App (향후)                 │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼ HTTPS/TLS
┌─────────────────────────────────────────────────────────────────┐
│                      API Gateway (Nginx/Kong)                   │
│  Routing │ Auth (JWT) │ Rate Limiting │ TLS Termination         │
└─────────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│Chat Service  │  │Workflow      │  │   Admin      │
│              │  │Service       │  │   Service    │
│- Intent      │  │              │  │              │
│- Session     │  │- Planner     │  │- User Mgmt   │
│- Message     │  │- Executor    │  │- Config      │
└──────────────┘  └──────────────┘  └──────────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│Judgment      │  │BI Service    │  │Learning      │
│Service       │  │              │  │Service       │
│              │  │- Planner     │  │              │
│- Rule Engine │  │- Catalog     │  │- Feedback    │
│- LLM Client  │  │- Query       │  │- Training    │
│- Cache       │  │- Chart       │  │- Deployment  │
└──────────────┘  └──────────────┘  └──────────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                ┌───────────┼───────────┐
                ▼           ▼           ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │   MCP    │  │   Data   │  │  Event   │
        │ ToolHub  │  │   Hub    │  │  Bus     │
        │          │  │          │  │          │
        │- Registry│  │- ETL     │  │- Pub/Sub │
        │- Proxy   │  │- Vector  │  │- Queue   │
        └──────────┘  └──────────┘  └──────────┘
                │           │           │
        ┌───────┴───────────┴───────────┴───────┐
        ▼                                       ▼
┌──────────────┐                      ┌──────────────┐
│  PostgreSQL  │                      │    Redis     │
│              │                      │              │
│- Core Data   │                      │- Cache       │
│- BI Data     │                      │- Session     │
│- Vector      │                      │- Lock        │
└──────────────┘                      └──────────────┘
```

### 3.2 서비스 간 통신 패턴

#### 3.2.1 동기 통신 (REST API)
- **사용 케이스**: 즉시 응답 필요 (Judgment 실행, BI 쿼리)
- **프로토콜**: HTTP/REST (JSON)
- **타임아웃**: 서비스별 설정 (Judgment 10s, BI 30s)
- **재시도**: Exponential Backoff (1s, 2s, 4s)

**예시**: Workflow Service → Judgment Service
```http
POST http://judgment-service:8080/api/v1/judgment/execute
Content-Type: application/json
Authorization: Bearer {{ internal_token }}

{
  "workflow_id": "wf-001",
  "input_data": { ... },
  "policy": "HYBRID_WEIGHTED"
}
```

#### 3.2.2 비동기 통신 (Event Pub/Sub)
- **사용 케이스**: 후속 처리, 알림, 학습 (즉시 응답 불필요)
- **프로토콜**: Redis Pub/Sub 또는 RabbitMQ
- **이벤트**: JSON 메시지
- **구독자**: 여러 서비스가 동일 이벤트 구독 가능

**예시**: Judgment 완료 → Learning Service 구독
```python
# Judgment Service (Publisher)
redis_client.publish('judgment.executed', json.dumps({
    'execution_id': 'jud-123',
    'workflow_id': 'wf-001',
    'result': { ... },
    'timestamp': '2025-11-26T10:00:00Z'
}))

# Learning Service (Subscriber)
pubsub = redis_client.pubsub()
pubsub.subscribe('judgment.executed')

for message in pubsub.listen():
    if message['type'] == 'message':
        data = json.loads(message['data'])
        process_judgment_for_learning(data)
```

#### 3.2.3 내부 gRPC (고성능 필요 시)
- **사용 케이스**: 고빈도 호출, 낮은 지연 (Judgment Engine 내부 모듈)
- **프로토콜**: gRPC (Protocol Buffers)
- **장점**: 성능, 타입 안전성, 스트리밍
- **선택적**: 초기에는 REST 사용, 성능 이슈 시 gRPC 전환

---

## 4. 계층 구조 (Layered Architecture)

### 4.1 Presentation Layer (표현 계층)

**책임**: 사용자 인터페이스, 요청/응답 처리

| 컴포넌트 | 기술 | 포트 | 책임 |
|---------|------|------|------|
| **Web UI** | React 18, TypeScript, Tailwind CSS | 3000 | SPA, 차트, 폼, 대시보드 |
| **API Gateway** | Nginx 또는 Kong | 80/443 | 라우팅, Auth, Rate Limit, TLS |
| **Slack Bot** | Bolt (Node.js) | - | Slack 이벤트 수신, Block Kit 응답 |

**기능**:
- 사용자 요청 수신 (HTTP, WebSocket, Slack Event)
- JWT 토큰 검증 (API Gateway)
- 요청 라우팅 (서비스별)
- 응답 포맷팅 (JSON, HTML, Slack Blocks)

### 4.2 Application Layer (애플리케이션 계층)

**책임**: 비즈니스 로직 오케스트레이션, 서비스 조정

| 컴포넌트 | 기술 | 포트 | 책임 |
|---------|------|------|------|
| **Chat Service** | Python FastAPI | 8001 | 메시지 수집, 세션 관리, Intent 요청 |
| **Intent Router** | Python FastAPI | 8002 | Intent/Slot 추출, LLM 호출 |
| **Workflow Service** | Python FastAPI | 8003 | DSL 검증, Workflow 실행, 상태 관리 |

**기능**:
- 사용자 요청 해석 (Intent 분류, Slot 추출)
- 워크플로우 계획 생성 (Planner)
- 워크플로우 실행 오케스트레이션 (Executor)
- 서비스 간 조정 (Judgment, BI, MCP 호출)

### 4.3 Domain Layer (도메인 계층)

**책임**: 핵심 비즈니스 로직, 판단, 분석, 학습

| 컴포넌트 | 기술 | 포트 | 책임 |
|---------|------|------|------|
| **Judgment Service** | Python FastAPI | 8010 | Rule + LLM Hybrid 판단 |
| **BI Service** | Python FastAPI | 8020 | BI 플래너, SQL 생성, 차트 |
| **Learning Service** | Python FastAPI | 8030 | 피드백, 샘플, Rule 추출, 배포 |
| **MCP ToolHub** | Python FastAPI | 8040 | MCP 서버 호출, 커넥터 관리 |
| **Data Hub** | Python FastAPI | 8050 | ETL, 벡터화, Pre-agg 관리 |

**기능**:
- Judgment: Rule 실행, LLM 호출, 결과 병합
- BI: 자연어 → SQL, 차트 설정 생성
- Learning: Rule 자동 추출, Canary 배포
- MCP Hub: 외부 도구 호출 중계
- Data Hub: 데이터 수집, 변환, 적재

### 4.4 Infrastructure Layer (인프라 계층)

**책임**: 데이터 영속화, 캐싱, 메시징, 스토리지

| 컴포넌트 | 기술 | 포트 | 책임 |
|---------|------|------|------|
| **PostgreSQL** | PostgreSQL 14+ | 5432 | 주 데이터베이스 (Core, BI, RAG) |
| **Redis** | Redis 6+ | 6379 | 캐시, 세션, Pub/Sub, Lock |
| **S3/Blob Storage** | MinIO 또는 AWS S3 | - | 파일 저장 (백업, 로그, 임베딩) |
| **Event Bus** | Redis Pub/Sub 또는 RabbitMQ | - | 이벤트 발행/구독 |

**기능**:
- 데이터 저장 및 조회 (PostgreSQL)
- 캐시 저장 및 조회 (Redis)
- 파일 업로드/다운로드 (S3)
- 이벤트 발행/구독 (Redis Pub/Sub)

### 4.5 Cross-Cutting Layer (횡단 관심사)

**책임**: 모든 계층에서 사용하는 공통 기능

| 컴포넌트 | 기술 | 책임 |
|---------|------|------|
| **Auth Service** | JWT, OAuth 2.0 | 인증, 토큰 발급/검증 |
| **Audit Service** | PostgreSQL | 감사 로그 기록 |
| **Observability** | Prometheus, Loki, OpenTelemetry | 메트릭, 로그, 추적 |
| **Config Service** | Vault, ConfigMap | 환경 설정, 비밀 관리 |

---

## 5. 서비스 경계 (Bounded Context)

### 5.1 Judgment Context

**핵심 엔티티**:
- Judgment Execution
- Ruleset
- Prompt Template
- LLM Call
- Cache Entry

**핵심 비즈니스 로직**:
- 입력 검증 (Input Validation)
- Rule 실행 (Rhai 엔진)
- LLM 호출 (OpenAI/Anthropic)
- Hybrid 결합 (가중 평균, Gate 조건)
- 캐시 관리 (Redis)
- Explanation 생성

**외부 의존성**:
- PostgreSQL (rulesets, prompt_templates, judgment_executions)
- Redis (캐시, 회로 차단 상태)
- LLM API (OpenAI, Anthropic)

**제공 API**:
- POST /api/v1/judgment/execute
- POST /api/v1/judgment/simulate
- GET /api/v1/judgment/{id}

**이벤트 발행**:
- `judgment.executed`: 판단 완료 시

**이벤트 구독**:
- `rule.deployed`: Rule 배포 시 캐시 무효화

---

### 5.2 Workflow Context

**핵심 엔티티**:
- Workflow (DSL 정의)
- Workflow Step (노드)
- Workflow Instance (실행 인스턴스)
- Node Execution Log

**핵심 비즈니스 로직**:
- DSL 파싱 및 검증
- 노드 실행 (DATA, JUDGMENT, MCP, ACTION 등)
- 상태 관리 (PENDING, RUNNING, WAITING, COMPLETED, FAILED)
- 흐름 제어 (SWITCH, PARALLEL, WAIT)
- Circuit Breaker
- 보상 트랜잭션 (COMPENSATION)

**외부 의존성**:
- PostgreSQL (workflows, workflow_instances)
- Redis (인스턴스 상태, 락)
- Judgment Service (JUDGMENT 노드)
- BI Service (BI 노드)
- MCP ToolHub (MCP 노드)

**제공 API**:
- POST /api/v1/workflows (생성)
- POST /api/v1/workflows/validate (DSL 검증)
- POST /api/v1/workflows/{id}/execute (실행)
- GET /api/v1/workflows/instances/{id} (인스턴스 조회)

**이벤트 발행**:
- `workflow.started`: 워크플로우 시작
- `workflow.completed`: 워크플로우 완료
- `workflow.failed`: 워크플로우 실패

**이벤트 구독**:
- `approval.received`: 승인 노드 재개

---

### 5.3 BI Context

**핵심 엔티티**:
- BI Dataset
- BI Metric
- BI Component
- Analysis Plan
- Query Result

**핵심 비즈니스 로직**:
- 자연어 → analysis_plan 변환 (LLM)
- analysis_plan → SQL 생성
- SQL 실행 (Fact/Dim/Pre-agg)
- 차트 설정 생성 (Chart.js/ECharts)
- 쿼리 캐싱

**외부 의존성**:
- PostgreSQL (fact_*, dim_*, mv_*, bi_*)
- Redis (쿼리 결과 캐시)
- LLM API (BI Planner)

**제공 API**:
- POST /api/v1/bi/plan (자연어 → analysis_plan)
- POST /api/v1/bi/execute (SQL 실행)
- GET /api/v1/bi/catalog (Dataset/Metric 조회)

**이벤트 발행**:
- `bi.query.executed`: 쿼리 실행 완료

**이벤트 구독**:
- `etl.completed`: ETL 완료 시 캐시 무효화

---

### 5.4 Learning Context

**핵심 엔티티**:
- Feedback
- Learning Sample
- Auto Rule Candidate
- Rule Deployment
- Prompt Version

**핵심 비즈니스 로직**:
- 피드백 수집
- 샘플 큐레이션 (Positive/Negative)
- Rule 자동 추출 (Decision Tree)
- Prompt Few-shot 튜닝
- Canary 배포 (트래픽 라우팅, 메트릭 모니터링, 자동 롤백)

**외부 의존성**:
- PostgreSQL (feedbacks, learning_samples, rule_deployments)
- Redis (배포 상태, 트래픽 라우팅)
- scikit-learn (Decision Tree 학습)

**제공 API**:
- POST /api/v1/feedback (피드백 제출)
- POST /api/v1/learning/extract-rules (Rule 추출)
- POST /api/v1/learning/deploy (Canary 배포)
- POST /api/v1/learning/rollback (롤백)

**이벤트 발행**:
- `rule.deployed`: Rule 배포 완료
- `rule.rolled_back`: Rule 롤백
- `prompt.updated`: Prompt 업데이트

**이벤트 구독**:
- `judgment.executed`: 판단 완료 시 피드백 대기 상태로 전환

---

### 5.5 MCP ToolHub Context

**핵심 엔티티**:
- MCP Server
- MCP Tool
- Tool Execution
- Connector (DB/API/MQTT)

**핵심 비즈니스 로직**:
- MCP 서버 등록 및 관리
- 도구 메타데이터 저장
- 도구 호출 프록시 (인증, 타임아웃, 재시도)
- 커넥터 헬스 체크
- Circuit Breaker

**외부 의존성**:
- PostgreSQL (mcp_servers, mcp_tools, data_connectors)
- Redis (Circuit Breaker 상태)
- 외부 MCP 서버 (Excel, GDrive, Jira)

**제공 API**:
- GET /api/v1/mcp/servers (MCP 서버 목록)
- POST /api/v1/mcp/tools/call (도구 호출)
- POST /api/v1/connectors (커넥터 등록)
- GET /api/v1/connectors/health (헬스 체크)

**이벤트 발행**:
- `connector.health_failed`: 헬스 체크 실패
- `drift.detected`: 스키마 변경 감지

---

### 5.6 Data Hub Context

**핵심 엔티티**:
- ETL Job
- ETL Execution
- Raw Data
- Dimension Table
- Fact Table
- Pre-aggregation View

**핵심 비즈니스 로직**:
- ETL 파이프라인 (RAW → DIM → FACT)
- 데이터 품질 검사
- 벡터 임베딩 생성 (pgvector)
- Materialized View 관리 (리프레시)
- 파티션 관리 (생성, 삭제)

**외부 의존성**:
- PostgreSQL (raw_*, dim_*, fact_*, mv_*)
- 외부 데이터 소스 (ERP, MES, 센서)
- OpenAI Embeddings API (벡터화)

**제공 API**:
- POST /api/v1/etl/jobs (ETL 작업 생성)
- POST /api/v1/etl/jobs/{id}/run (ETL 실행)
- GET /api/v1/data/quality (데이터 품질 보고서)

**이벤트 발행**:
- `etl.started`: ETL 시작
- `etl.completed`: ETL 완료
- `etl.failed`: ETL 실패

**이벤트 구독**:
- `drift.detected`: 스키마 변경 시 ETL 중단

---

## 6. 데이터 흐름 (Data Flow)

### 6.1 엔드투엔드 흐름: 불량 판단 요청

```
[사용자] → [Slack Bot] → [Chat Service] → [Intent Router] → [Workflow Service] → [Judgment Service] → [DB/Cache]
    ↓
[Slack 응답] ← [Chat Service] ← [Workflow Service] ← [Judgment Result]
    ↓
[Learning Service] ← [judgment.executed Event] → [피드백 대기]
```

**상세 단계**:
1. **사용자**: Slack에서 `@AI-Factory LINE-A 불량 판단` 멘션
2. **Slack Bot**: Slack Event API 수신 → Chat Service로 전달
3. **Chat Service**:
   - 메시지 저장 (chat_messages)
   - Intent Router 호출
4. **Intent Router**:
   - LLM 호출: `intent=defect_inquiry, slots={line_code: LINE-A}`
   - Intent 로그 저장 (intent_logs)
5. **Workflow Service**:
   - Intent에 맞는 Workflow 선택 (wf-defect-001)
   - Workflow 인스턴스 생성 (PENDING)
   - Executor 시작
6. **Executor**:
   - 노드 1 (DATA): MES DB에서 생산 데이터 조회
   - 노드 2 (JUDGMENT): Judgment Service 호출
7. **Judgment Service**:
   - Redis 캐시 조회 (Cache MISS)
   - Rule 실행: 불량률 5% > 임계값 2% → HIGH_DEFECT (confidence 0.95)
   - 신뢰도 높음 → LLM 호출 생략
   - 결과 저장 (judgment_executions)
   - Redis 캐시 저장 (TTL 300s)
   - 이벤트 발행: `judgment.executed`
8. **Executor**:
   - 노드 3 (ACTION): Slack Webhook 호출 (알림 발송)
   - Workflow 완료 (COMPLETED)
9. **Chat Service**:
   - Slack Block Kit 응답 생성
   - Slack Bot으로 전달
10. **Slack Bot**:
    - 사용자에게 응답 표시 (카드, 버튼)
11. **Learning Service** (비동기):
    - `judgment.executed` 이벤트 수신
    - 피드백 대기 상태로 전환

**데이터 흐름 다이어그램**:
```
┌─────────┐     ┌──────────┐     ┌─────────────┐     ┌──────────────┐
│ Slack   │ ──> │   Chat   │ ──> │   Intent    │ ──> │   Workflow   │
│  User   │     │ Service  │     │   Router    │     │   Service    │
└─────────┘     └──────────┘     └─────────────┘     └──────────────┘
                                                              │
                                                              ▼
                ┌──────────────┐                    ┌──────────────┐
                │   Judgment   │ <────────────────  │   Executor   │
                │   Service    │                    │   (노드 실행) │
                └──────────────┘                    └──────────────┘
                      │   │                               │
                      │   └──> [Redis Cache]              │
                      │                                   │
                      └──> [PostgreSQL]                   │
                      │                                   │
                      └──> [Event: judgment.executed] ──> │
                                                          │
                                                          ▼
                                              ┌──────────────────┐
                                              │    Learning      │
                                              │    Service       │
                                              └──────────────────┘
```

### 6.2 엔드투엔드 흐름: BI 자연어 쿼리

```
[사용자] → [Web UI] → [BI Service] → [LLM API] → [PostgreSQL] → [Chart Rendering]
                             ↓
                      [Redis Cache]
```

**상세 단계**:
1. **사용자**: Web UI에서 "지난 7일간 LINE-A 불량률 보여줘" 입력
2. **Web UI**: POST /api/v1/bi/plan 호출
3. **BI Service**:
   - 캐시 조회 (plan_hash 기반)
   - Cache MISS
   - BI 카탈로그 조회 (bi_datasets, bi_metrics)
   - LLM 프롬프트 구성 (카탈로그 + 자연어 질의)
4. **LLM API**:
   - GPT-4o-mini 호출 (저비용)
   - `analysis_plan` JSON 생성
5. **BI Service**:
   - `analysis_plan` → SQL 변환
   - Pre-aggregation 최적화 (mv_daily_line_metrics 사용)
   - SQL 실행
   ```sql
   SELECT date, defect_rate
   FROM mv_daily_line_metrics
   WHERE tenant_id = $1 AND line_code = $2 AND date >= $3
   ORDER BY date ASC;
   ```
6. **PostgreSQL**:
   - 쿼리 실행 (< 500ms)
   - 결과 반환 (7 rows)
7. **BI Service**:
   - 차트 설정 생성 (Line Chart Config)
   - Redis 캐시 저장 (TTL 600s)
   - 결과 반환
8. **Web UI**:
   - Chart.js로 Line Chart 렌더링
   - 사용자에게 표시

---

## 7. 계층 간 의존성 규칙

### 7.1 Dependency Rule

```
Presentation Layer
      ↓ (의존 가능)
Application Layer
      ↓ (의존 가능)
Domain Layer
      ↓ (의존 가능)
Infrastructure Layer
```

**규칙**:
- 상위 계층은 하위 계층에 의존할 수 있다.
- 하위 계층은 상위 계층에 의존할 수 없다 (의존성 역전).
- Domain Layer는 Infrastructure에 직접 의존하지 않고, 인터페이스(Port)에 의존한다.

**예시**:
```python
# ✅ 좋은 예: Domain → Interface (Port)
class JudgmentService:
    def __init__(self, repository: IJudgmentRepository):
        self.repository = repository

    def execute(self, input_data):
        result = self.calculate_judgment(input_data)
        self.repository.save(result)
        return result

# Interface (Port)
class IJudgmentRepository(ABC):
    @abstractmethod
    def save(self, judgment): ...
    @abstractmethod
    def find_by_id(self, id): ...

# Infrastructure → Implementation (Adapter)
class PostgresJudgmentRepository(IJudgmentRepository):
    def save(self, judgment):
        # PostgreSQL 구현
        ...
```

### 7.2 통신 방향

```
┌───────────────────────────────────────────────────────────┐
│                     Client Layer                          │
└───────────────────────────────────────────────────────────┘
                       │
                       ▼ (HTTP/REST)
┌───────────────────────────────────────────────────────────┐
│                  API Gateway (Nginx)                      │
└───────────────────────────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│Chat Service  │ │Workflow Svc  │ │Admin Service │
└──────────────┘ └──────────────┘ └──────────────┘
        │              │              │
        └──────────────┼──────────────┘
                       ▼ (Internal API)
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│Judgment Svc  │ │BI Service    │ │Learning Svc  │
└──────────────┘ └──────────────┘ └──────────────┘
        │              │              │
        └──────────────┼──────────────┘
                       ▼ (Repository)
┌───────────────────────────────────────────────────────────┐
│            PostgreSQL │ Redis │ S3                        │
└───────────────────────────────────────────────────────────┘
```

---

## 다음 파일로 계속

본 문서는 B-1-1로, 아키텍처 개요 및 논리적 아키텍처를 포함한다.

**다음 파일**:
- **B-1-2**: 물리적 아키텍처, 배포 아키텍처, 데이터 아키텍처
- **B-1-3**: 통합 아키텍처, 보안 아키텍처, 확장성/가용성 아키텍처
- **B-1-4**: 기술 스택 상세, 아키텍처 결정 기록 (ADR)

---

## 문서 이력
| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2025-11-26 | AI Factory Team | 초안 작성 |
