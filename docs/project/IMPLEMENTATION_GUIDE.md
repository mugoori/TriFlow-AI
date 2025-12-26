# TriFlow AI 기능별 상세 구현 가이드

> **문서 버전**: 1.0
> **작성일**: 2025-12-26
> **대상 독자**: 개발자
> **관련 문서**: [메인 현황](PROJECT_STATUS.md) | [스펙 비교](SPEC_COMPARISON.md) | [아키텍처](ARCHITECTURE.md) | [지표/로드맵](METRICS_ROADMAP.md)

---

## 목차

1. [AI 에이전트 시스템](#1-ai-에이전트-시스템)
2. [워크플로우 엔진](#2-워크플로우-엔진)
3. [MCP 시스템 (ToolHub + 래퍼 서버)](#3-mcp-시스템-toolhub--래퍼-서버)
4. [GenBI (Text-to-SQL + 인사이트)](#4-genbi-text-to-sql--인사이트)
5. [규칙 엔진 (Rhai)](#5-규칙-엔진-rhai)
6. [학습 시스템](#6-학습-시스템)
7. [인증/보안](#7-인증보안)
8. [실시간 통신 (WebSocket)](#8-실시간-통신-websocket)
9. [데이터 계층](#9-데이터-계층)

---

## 1. AI 에이전트 시스템

### 기술 스택

| 구성요소 | 기술 | 용도 |
|---------|------|------|
| LLM API | Anthropic Claude API | 자연어 이해 및 생성 |
| 모델 | claude-sonnet-4-5-20250929 | 빠른 응답 + 도구 사용 |
| 프롬프트 관리 | Markdown 파일 | `backend/app/prompts/*.md` |
| Tool Use | Anthropic Tool Use API | 구조화된 도구 호출 |

### 구현 방식

**에이전트 구조**:
```python
# backend/app/agents/base_agent.py
class BaseAgent:
    def __init__(self, name, model, max_tokens):
        self.client = anthropic.Anthropic()

    def get_system_prompt(self) -> str:
        """prompts/*.md 파일에서 로드"""

    def get_tools(self) -> List[Dict]:
        """Claude Tool Use 형식의 도구 정의"""

    def execute_tool(self, tool_name, tool_input) -> Any:
        """도구 실행 (하위 클래스에서 구현)"""

    async def run(self, user_message, context) -> str:
        """에이전트 실행 루프"""
```

**5개 에이전트 역할**:

| 에이전트 | 파일 | 역할 |
|---------|------|------|
| Meta Router | `meta_router.py` | 의도 분류 → 적절한 에이전트로 라우팅 |
| Judgment | `judgment_agent.py` | 센서 데이터 분석 + 규칙 실행 + 판단 |
| Workflow Planner | `workflow_planner.py` | 자연어 → 워크플로우 DSL 생성 |
| BI Planner | `bi_planner.py` | Text-to-SQL + 차트 설계 |
| Learning | `learning_agent.py` | 피드백 분석 + 규칙 제안 |

### 사용법 (API 호출)

```bash
# 채팅 메시지 전송
POST /api/v1/agents/chat
Authorization: Bearer {token}
Content-Type: application/json

{
  "message": "라인 A의 온도가 80도 넘으면 알림 보내줘",
  "session_id": "optional-session-id"
}
```

**응답 예시**:
```json
{
  "message": "라인 A의 온도 모니터링 규칙을 생성했습니다...",
  "intent": "workflow_create",
  "confidence": 0.95,
  "agent": "WorkflowPlanner",
  "artifacts": {
    "workflow_id": "uuid-xxx"
  }
}
```

### 주요 파일

```
backend/app/agents/
├── meta_router.py         # 의도 분류 (V7 체계, 14개 의도)
├── judgment_agent.py      # 판단 에이전트
├── workflow_planner.py    # 워크플로우 생성
├── bi_planner.py          # BI 분석 (3,200줄)
└── learning_agent.py      # 학습/피드백

backend/app/prompts/
├── meta_router.md         # 시스템 프롬프트
├── judgment.md
├── workflow_planner.md
├── bi_planner.md
└── learning.md
```

---

## 2. 워크플로우 엔진

### 기술 스택

| 구성요소 | 기술 | 용도 |
|---------|------|------|
| 실행 엔진 | Python asyncio | 비동기 노드 실행 |
| 상태 관리 | PostgreSQL + 인메모리 | 영속 상태 저장 |
| DSL 포맷 | JSON Schema | 워크플로우 정의 |
| 시각화 | React Flow | 프론트엔드 에디터 |

### DSL 구조

```json
{
  "id": "workflow-uuid",
  "name": "온도 모니터링",
  "version": "1.0",
  "nodes": [
    {
      "id": "node1",
      "type": "data",
      "config": {
        "query": "SELECT * FROM sensors WHERE line='A'",
        "source": "postgresql"
      },
      "next": ["node2"]
    },
    {
      "id": "node2",
      "type": "condition",
      "config": {
        "expression": "temperature > 80"
      },
      "next": ["node3"]
    },
    {
      "id": "node3",
      "type": "action",
      "config": {
        "action_type": "slack_notify",
        "channel": "#alerts",
        "message": "온도 경고: {{temperature}}C"
      }
    }
  ]
}
```

### 노드 실행 흐름

```python
# backend/app/services/workflow_engine.py
class WorkflowEngine:
    async def execute_workflow(self, workflow_id, trigger_data):
        instance = await self._create_instance(workflow_id)

        for node in self._get_execution_order(instance.workflow):
            result = await self._execute_node(node, instance.context)
            instance.context.update(result)
            await self._save_checkpoint(instance)

        return instance

    async def _execute_node(self, node, context):
        executor = self._get_executor(node.type)  # 18개 노드 타입
        return await executor.execute(node.config, context)
```

### 18개 노드 타입 요약

| 카테고리 | 노드 | 기능 |
|---------|------|------|
| **제어** | condition | 조건식 평가 (true/false) |
| | if_else | 이진 분기 (then/else) |
| | switch | 다중 분기 (case별) |
| | loop | 반복 실행 (for/while) |
| | parallel | 병렬 실행 |
| **데이터** | data | SQL 쿼리 실행 |
| | code | Python 코드 샌드박스 실행 |
| **AI** | judgment | JudgmentAgent 호출 |
| | bi | BIPlannerAgent 호출 |
| **외부** | mcp | MCP 도구 호출 |
| | action | 10개 액션 타입 실행 |
| | trigger | 워크플로우 자동 시작 |
| **승인** | wait | 시간/이벤트 대기 |
| | approval | 인간 승인 대기 |
| **고급** | compensation | 보상 트랜잭션 |
| | deploy | 배포 (ruleset/model) |
| | rollback | 이전 버전 복구 |
| | simulate | What-if 시뮬레이션 |

### 사용법 (API)

```bash
# 워크플로우 실행
POST /api/v1/workflows/{workflow_id}/execute
Authorization: Bearer {token}
Content-Type: application/json

{
  "trigger_data": {
    "temperature": 85,
    "line_code": "LINE_A"
  }
}
```

### 주요 파일

```
backend/app/services/
├── workflow_engine.py     # 워크플로우 엔진 (6,552줄)
├── checkpoint_manager.py  # 체크포인트 관리
└── action_executor.py     # 액션 실행기

frontend/src/components/workflow/
└── FlowEditor.tsx         # 비주얼 에디터 (3,203줄)
```

---

## 3. MCP 시스템 (ToolHub + 래퍼 서버)

### 기술 스택

| 구성요소 | 기술 | 용도 |
|---------|------|------|
| 프로토콜 | JSON-RPC 2.0 / HTTP | MCP 표준 통신 |
| ToolHub | FastAPI | MCP 서버 레지스트리 + 프록시 |
| 래퍼 서버 | FastAPI + httpx | 외부 API → MCP 변환 |
| Circuit Breaker | 자체 구현 | 장애 전파 방지 |

### MCP ToolHub 아키텍처

```
[워크플로우 MCP 노드]
        ↓
[MCPToolHubService]  ← 서버 레지스트리, 도구 목록 관리
        ↓
[HTTPMCPProxy]       ← HTTP 호출, 재시도, 타임아웃
        ↓
[Circuit Breaker]    ← 5회 실패 → OPEN → 60초 후 HALF_OPEN
        ↓
[외부 MCP 서버 / 래퍼 서버]
```

### MCP 래퍼 서버 구현

```python
# backend/app/mcp_wrappers/base_wrapper.py
class MCPWrapperBase(ABC):
    """외부 API를 MCP 표준으로 변환하는 베이스 클래스"""

    @abstractmethod
    def get_tools(self) -> List[MCPToolDefinition]:
        """도구 목록 반환"""
        pass

    @abstractmethod
    async def call_tool(self, tool_name: str, args: Dict) -> Dict:
        """도구 실행 (외부 API 호출)"""
        pass

# MES 래퍼 예시
class MESWrapper(MCPWrapperBase):
    def get_tools(self):
        return [
            MCPToolDefinition(
                name="get_production_status",
                description="생산 현황 조회",
                input_schema={
                    "type": "object",
                    "properties": {"line_id": {"type": "string"}}
                }
            ),
            # ... 4개 더
        ]

    async def call_tool(self, tool_name, args):
        # 실제 MES API 호출
        response = await self.client.get(f"/api/{tool_name}", params=args)
        return response.json()
```

### 래퍼 서버 실행

```bash
# MES 래퍼 서버 실행 (포트 8100)
python -m app.mcp_wrappers.run_wrapper \
    --type mes \
    --port 8100 \
    --target-url http://mes-server.company.com \
    --api-key YOUR_API_KEY

# TriFlow에 등록
curl -X POST http://localhost:8000/api/v1/mcp/servers \
    -H "Authorization: Bearer $TOKEN" \
    -d '{
        "name": "MES Server",
        "endpoint": "http://localhost:8100",
        "protocol": "http"
    }'
```

### MCP 도구 호출 API

```bash
POST /api/v1/mcp/call
Authorization: Bearer {token}
Content-Type: application/json

{
  "mcp_server_id": "uuid-xxx",
  "tool_name": "get_production_status",
  "input_data": {"line_id": "LINE_A"}
}
```

### 주요 파일

```
backend/app/
├── services/
│   ├── mcp_toolhub.py     # MCP 서버 관리
│   ├── mcp_proxy.py       # HTTP 프록시
│   └── circuit_breaker.py # 회로 차단기
│
└── mcp_wrappers/
    ├── base_wrapper.py    # 베이스 클래스
    ├── mes_wrapper.py     # MES 래퍼 (5개 도구)
    ├── erp_wrapper.py     # ERP 래퍼 (6개 도구)
    └── run_wrapper.py     # CLI 실행 스크립트
```

---

## 4. GenBI (Text-to-SQL + 인사이트)

### 기술 스택

| 구성요소 | 기술 | 용도 |
|---------|------|------|
| Text-to-SQL | Claude API | 자연어 → SQL 변환 |
| 차트 렌더링 | Recharts + ECharts | 프론트엔드 시각화 |
| 데이터 웨어하우스 | PostgreSQL (Star Schema) | Fact/Dim 테이블 |
| 캐시 | Redis | 쿼리 결과 캐싱 |

### 데이터 모델 (Star Schema)

```
[dim_date]────┐
[dim_line]────┼──[fact_daily_production]
[dim_product]─┘

[dim_date]────┐
[dim_line]────┼──[fact_daily_defect]
[dim_defect_type]─┘
```

### GenBI 기능

**1. Text-to-SQL**:
```bash
POST /api/v1/bi/analyze
{
  "question": "이번 주 라인별 불량률을 보여줘"
}

# 응답
{
  "sql": "SELECT line_name, AVG(defect_rate) as avg_rate ...",
  "data": [...],
  "chart_config": {...}
}
```

**2. Executive Summary**:
```python
# backend/app/services/insight_service.py
class InsightService:
    async def generate_executive_summary(self, data, question):
        return {
            "fact": "이번 주 전체 불량률 2.1%, 전주 대비 0.3%p 감소",
            "reasoning": "라인 A 설비 점검 후 안정화, 라인 C 개선 필요",
            "action": "라인 C 설비 점검 권장, 품질 교육 실시 검토"
        }
```

**3. StatCard (KPI 카드)**:
```python
# 3가지 데이터 소스 지원
class StatCardDataSource(Enum):
    KPI = "kpi"           # bi.dim_kpi 테이블
    DB_QUERY = "db_query" # 직접 SQL 쿼리
    MCP_TOOL = "mcp_tool" # 외부 도구 호출
```

### StatCard API

```bash
POST /api/v1/bi/statcards
{
  "title": "금일 불량률",
  "data_source": "db_query",
  "config": {
    "table": "fact_daily_defect",
    "column": "defect_rate",
    "aggregation": "avg",
    "filter": "date = CURRENT_DATE"
  },
  "display": {
    "format": "percent",
    "threshold_warning": 3.0,
    "threshold_danger": 5.0
  }
}
```

### 주요 파일

```
backend/app/
├── agents/
│   └── bi_planner.py          # BI 분석 (3,200줄)
│
└── services/
    ├── bi_service.py          # BI 서비스
    ├── bi_chat_service.py     # GenBI 채팅
    ├── stat_card_service.py   # StatCard 계산
    ├── insight_service.py     # Executive Summary
    ├── story_service.py       # Data Stories
    └── chart_builder.py       # 차트 설정 생성
```

---

## 5. 규칙 엔진 (Rhai)

### 기술 스택

| 구성요소 | 기술 | 용도 |
|---------|------|------|
| 스크립팅 엔진 | Rhai 1.16 (MVP: Python Mock) | 규칙 스크립트 실행 |
| 바인딩 | PyO3 (계획) | Rust-Python 연동 |
| 규칙 저장소 | PostgreSQL | 규칙셋 버전 관리 |

### 규칙 스크립트 예시 (Rhai)

```rhai
// 온도 임계값 규칙
let threshold = 80.0;
let temperature = input.temperature;

if temperature > threshold {
    #{
        status: "WARNING",
        confidence: 0.95,
        message: `온도 ${temperature}C가 임계값 ${threshold}C 초과`
    }
} else {
    #{
        status: "NORMAL",
        confidence: 0.90,
        message: `온도 ${temperature}C 정상 범위`
    }
}
```

### 하이브리드 판단 정책

```python
# backend/app/services/judgment_policy.py
class JudgmentPolicy(Enum):
    RULE_ONLY = "rule_only"           # 규칙만 실행
    LLM_ONLY = "llm_only"             # LLM만 실행
    ESCALATE = "escalate"             # 규칙 실패 → LLM
    RULE_FALLBACK = "rule_fallback"   # LLM 실패 → 규칙
    HYBRID_GATE = "hybrid_gate"       # 규칙 통과 시만 LLM
    HYBRID_WEIGHTED = "hybrid_weighted" # 가중치 결합

class HybridJudgmentService:
    async def execute(self, policy, ruleset_id, input_data):
        if policy == JudgmentPolicy.ESCALATE:
            rule_result = await self.rhai_engine.execute(ruleset, input_data)
            if rule_result.status == "UNCERTAIN":
                return await self.llm_fallback(input_data)
            return rule_result
```

### 주요 파일

```
backend/app/
├── tools/
│   └── rhai.py                # Rhai 엔진 래퍼
│
└── services/
    ├── judgment_policy.py     # 판단 정책 서비스
    └── judgment_cache.py      # 판단 결과 캐시
```

---

## 6. 학습 시스템

### 기술 스택

| 구성요소 | 기술 | 용도 |
|---------|------|------|
| 피드백 수집 | REST API | 긍정/부정 + 상세 모달 |
| 피드백 분석 | LearningAgent | 패턴 발견 + 규칙 제안 |
| A/B 테스트 | 자체 구현 | 규칙 버전 비교 |
| 통계 검정 | Z-test | 유의성 검정 |

### 피드백 수집 흐름

```
[사용자 피드백]
    ↓
[POST /api/v1/feedback]  ← 긍정/부정 + 상세 의견
    ↓
[feedback_logs 테이블]
    ↓
[LearningAgent 분석]     ← 주기적 또는 수동 트리거
    ↓
[proposed_rules 테이블]   ← AI 규칙 제안
    ↓
[관리자 검토 → 배포]
```

### A/B 테스트 API

```bash
# 실험 생성
POST /api/v1/experiments
{
  "name": "온도 규칙 v2 테스트",
  "control_ruleset_id": "uuid-v1",
  "treatment_ruleset_id": "uuid-v2",
  "traffic_split": 0.5
}

# 결과 조회
GET /api/v1/experiments/{id}/results
{
  "control": {"success_rate": 0.82, "sample_size": 150},
  "treatment": {"success_rate": 0.89, "sample_size": 148},
  "p_value": 0.03,
  "significant": true
}
```

### 주요 파일

```
backend/app/
├── agents/
│   └── learning_agent.py      # 학습 에이전트
│
├── services/
│   ├── feedback_analyzer.py   # 피드백 분석
│   └── experiment_service.py  # A/B 테스트
│
└── routers/
    ├── feedback.py            # 피드백 API
    └── experiments.py         # 실험 API
```

---

## 7. 인증/보안

### 기술 스택

| 구성요소 | 기술 | 용도 |
|---------|------|------|
| 인증 | JWT (HS256) | Access/Refresh Token |
| 인가 | RBAC | Role-Based Access Control |
| 비밀번호 | bcrypt | 해싱 |
| PII 마스킹 | 정규표현식 | 개인정보 마스킹 |

### JWT 토큰 구조

```python
# backend/app/auth/jwt.py
{
    "sub": "user-uuid",         # 사용자 ID
    "email": "user@example.com",
    "role": "operator",         # admin, operator, viewer
    "tenant_id": "tenant-uuid", # 멀티테넌트 격리
    "exp": 1703577600,          # 만료 시간
    "type": "access"            # access / refresh
}
```

### 인증 방식

```python
# backend/app/auth/dependencies.py
async def get_current_user(
    credentials: HTTPAuthorizationCredentials,  # Bearer 토큰
    x_api_key: str = Header(None),              # API Key
    db: Session = Depends(get_db)
) -> User:
    # 1. API Key 우선 확인 (tfk_xxxxx 접두사)
    # 2. JWT 토큰 디코딩 및 검증
    # 3. 사용자 조회 및 반환
```

### RBAC 권한 체계

| Role | 워크플로우 | 규칙셋 | 사용자 관리 | 시스템 설정 |
|------|:----------:|:------:|:-----------:|:----------:|
| admin | CRUD | CRUD | CRUD | Yes |
| operator | CRU | CRU | - | - |
| viewer | Read | Read | - | - |

### 주요 파일

```
backend/app/
├── auth/
│   ├── jwt.py               # JWT 생성/검증
│   ├── dependencies.py      # 인증 의존성
│   └── rbac.py              # 역할 기반 권한
│
├── middleware/
│   └── pii_masking.py       # PII 마스킹
│
└── core/
    └── security.py          # 보안 유틸리티
```

---

## 8. 실시간 통신 (WebSocket)

### 기술 스택

| 구성요소 | 기술 | 용도 |
|---------|------|------|
| 프로토콜 | WebSocket | 양방향 실시간 통신 |
| 서버 | FastAPI WebSocket | 백엔드 |
| 클라이언트 | React useWebSocket | 프론트엔드 |

### WebSocket 엔드포인트

```python
# backend/app/routers/websocket.py
@router.websocket("/ws/{tenant_id}")
async def websocket_endpoint(websocket: WebSocket, tenant_id: str):
    await websocket.accept()

    # 센서 데이터 스트리밍
    async for data in sensor_stream(tenant_id):
        await websocket.send_json({
            "type": "sensor_update",
            "data": data
        })

    # 워크플로우 상태 업데이트
    async for status in workflow_status_stream(tenant_id):
        await websocket.send_json({
            "type": "workflow_status",
            "data": status
        })
```

### 프론트엔드 연결

```typescript
// frontend/src/hooks/useWebSocket.ts
const { sendMessage, lastMessage } = useWebSocket(
  `ws://localhost:8000/ws/${tenantId}`,
  {
    onMessage: (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'sensor_update') {
        updateSensorData(data.data);
      }
    }
  }
);
```

### 주요 파일

```
backend/app/routers/
└── websocket.py             # WebSocket 라우터

frontend/src/hooks/
└── useWebSocket.ts          # WebSocket 훅
```

---

## 9. 데이터 계층

### 기술 스택

| 구성요소 | 기술 | 용도 |
|---------|------|------|
| 메인 DB | PostgreSQL 14+ | 트랜잭션 데이터 |
| 벡터 DB | pgvector 0.5+ | RAG 임베딩 검색 |
| 캐시 | Redis 7.2 | 세션, 쿼리 캐시 |
| 파일 저장소 | AWS S3 / 로컬 | CSV 내보내기, 첨부파일 |
| ORM | SQLAlchemy 2.x | Python-DB 매핑 |

### 스키마 구조

```sql
-- 테넌트 기반 멀티테넌시
CREATE TABLE tenants (
    id UUID PRIMARY KEY,
    name VARCHAR(100),
    subscription_plan VARCHAR(20)  -- free, pro, enterprise
);

-- 모든 테이블에 tenant_id 외래키
CREATE TABLE workflows (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    name VARCHAR(100),
    dsl_json JSONB,
    version INTEGER DEFAULT 1
);

-- BI 스타 스키마
CREATE TABLE bi.fact_daily_production (
    id SERIAL PRIMARY KEY,
    date_id INTEGER REFERENCES bi.dim_date(id),
    line_id INTEGER REFERENCES bi.dim_line(id),
    product_id INTEGER REFERENCES bi.dim_product(id),
    production_count INTEGER,
    defect_count INTEGER
);
```

### Redis 캐시 패턴

```python
# backend/app/services/cache_service.py
class CacheService:
    async def get_or_set(self, key: str, ttl: int, factory: Callable):
        cached = await self.redis.get(key)
        if cached:
            return json.loads(cached)

        value = await factory()
        await self.redis.setex(key, ttl, json.dumps(value))
        return value

# 사용 예시
cache_key = f"bi:query:{hash(sql_query)}"
result = await cache.get_or_set(cache_key, ttl=300, factory=lambda: execute_sql(sql_query))
```

### S3 파일 저장 (AWS 배포 시)

```python
# backend/app/services/storage_service.py
class StorageService:
    def __init__(self):
        if S3_AVAILABLE:
            self.s3 = boto3.client('s3')
            self.bucket = os.getenv('S3_BUCKET')
        else:
            self.local_path = './uploads'

    async def upload(self, file_key: str, content: bytes):
        if S3_AVAILABLE:
            self.s3.put_object(Bucket=self.bucket, Key=file_key, Body=content)
        else:
            with open(f"{self.local_path}/{file_key}", 'wb') as f:
                f.write(content)
```

### 주요 파일

```
backend/app/
├── models/
│   ├── core.py            # 핵심 모델 (65KB, 50+ 클래스)
│   ├── bi.py              # BI 모델 (33KB, 23개 클래스)
│   └── statcard.py        # StatCard 모델
│
├── services/
│   ├── cache_service.py   # Redis 캐시
│   └── storage_service.py # S3/로컬 저장소
│
└── db/
    ├── session.py         # DB 세션
    └── migrations/        # Alembic 마이그레이션
```

---

## 문서 이력

| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2025-12-26 | AI 개발팀 | PROJECT_STATUS.md에서 분리 |

---

**문서 끝**
