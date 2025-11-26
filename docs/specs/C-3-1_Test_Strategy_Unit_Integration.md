# C-3-1. Test Plan & QA Strategy - Test Strategy, Unit & Integration Testing

## 문서 정보
- **문서 ID**: C-3-1
- **버전**: 2.0 (Enhanced)
- **최종 수정일**: 2025-11-26
- **상태**: Draft
- **관련 문서**:
  - A-2 System Requirements Spec
  - B-2 Module/Service Design
  - C-1 Development Plan & WBS
  - C-2 Coding Standard

## 목차
1. [테스트 전략 개요](#1-테스트-전략-개요)
2. [단위 테스트 (Unit Testing)](#2-단위-테스트-unit-testing)
3. [통합 테스트 (Integration Testing)](#3-통합-테스트-integration-testing)

---

## 1. 테스트 전략 개요

### 1.1 테스트 목표

| 목표 | 설명 | 측정 지표 |
|------|------|----------|
| **품질 보증** | 요구사항 충족 및 결함 최소화 | 결함 밀도 < 5/KLOC |
| **성능 검증** | 응답 시간 및 처리량 목표 달성 | Judgment P95 < 2.5s, BI P95 < 3s |
| **보안 강화** | 취약점 제로, 규제 준수 | Critical 취약점 0개 |
| **안정성 확보** | 장애 복구, 가용성 목표 달성 | 가용성 > 99%, RTO < 4h |

### 1.2 테스트 피라미드

```
           ┌──────────────┐
           │  E2E Tests   │  (10%)
           │  (10 cases)  │
           └──────────────┘
         ┌──────────────────┐
         │Integration Tests │  (20%)
         │   (40 cases)     │
         └──────────────────┘
    ┌─────────────────────────┐
    │    Unit Tests            │  (70%)
    │    (200+ cases)          │
    └─────────────────────────┘
```

**비율**:
- **Unit Tests**: 70% (200+ 케이스) - 빠른 피드백, 높은 커버리지
- **Integration Tests**: 20% (40 케이스) - 서비스 간 연동 검증
- **E2E Tests**: 10% (10 케이스) - 핵심 사용자 시나리오

### 1.3 테스트 레벨별 범위

| 테스트 레벨 | 범위 | 도구 | 담당 | 빈도 |
|------------|------|------|------|------|
| **Unit** | 함수, 클래스, 모듈 | pytest, Jest | 개발자 | 매 커밋 |
| **Integration** | 서비스 간 연동, DB, Cache | pytest, Postman | 개발자, QA | 매 PR |
| **E2E** | 전체 시스템 흐름 | Playwright, Cypress | QA | 매 스프린트 |
| **Performance** | 응답 시간, 처리량 | Locust, k6 | QA | 주 1회 |
| **Security** | 취약점, 침투 테스트 | OWASP ZAP, Bandit | QA | 스프린트 종료 |
| **UAT** | 사용자 수락 | Manual | 고객사 | 릴리스 전 |

---

## 2. 단위 테스트 (Unit Testing)

### 2.1 개요
단위 테스트는 개별 함수, 클래스, 모듈의 동작을 검증한다.

**목표**:
- 코드 커버리지 > 80% (Line Coverage)
- Branch 커버리지 > 70%
- 빠른 실행 (전체 < 30초)

### 2.2 테스트 프레임워크

#### 2.2.1 Backend (Python)

**pytest + pytest-cov + pytest-mock**

**프로젝트 구조**:
```
backend/
├── src/
│   ├── judgment/
│   │   ├── service.py
│   │   ├── rule_engine.py
│   │   └── llm_client.py
│   └── workflow/
│       ├── executor.py
│       └── node_executors.py
└── tests/
    ├── unit/
    │   ├── judgment/
    │   │   ├── test_service.py
    │   │   ├── test_rule_engine.py
    │   │   └── test_llm_client.py
    │   └── workflow/
    │       ├── test_executor.py
    │       └── test_node_executors.py
    └── conftest.py
```

**pytest 설정** (pytest.ini):
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    --cov=src
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=80
    --verbose
```

#### 2.2.2 Frontend (TypeScript)

**Jest + React Testing Library**

**프로젝트 구조**:
```
frontend/
├── src/
│   ├── components/
│   │   ├── Judgment/
│   │   │   ├── JudgmentCard.tsx
│   │   │   └── JudgmentCard.test.tsx
│   │   └── Workflow/
│   │       ├── WorkflowEditor.tsx
│   │       └── WorkflowEditor.test.tsx
│   └── hooks/
│       ├── useJudgment.ts
│       └── useJudgment.test.ts
└── jest.config.js
```

### 2.3 단위 테스트 케이스 예시

#### TC-JUD-001: RuleEngine 기본 실행

**목적**: Rhai Rule 실행 및 결과 반환 검증

```python
# tests/unit/judgment/test_rule_engine.py
import pytest
from src.judgment.rule_engine import RhaiEngine

class TestRhaiEngine:
    @pytest.fixture
    def engine(self):
        return RhaiEngine()

    @pytest.fixture
    def sample_rule(self):
        return """
        let defect_rate = input.defect_count / input.production_count;

        if defect_rate > 0.05 {
            #{ status: "HIGH_DEFECT", confidence: 0.95 }
        } else {
            #{ status: "NORMAL", confidence: 0.80 }
        }
        """

    def test_execute_high_defect(self, engine, sample_rule):
        """불량률 > 5% → HIGH_DEFECT"""
        # Arrange
        input_data = {
            'defect_count': 5,
            'production_count': 100
        }

        # Act
        result = engine.execute(sample_rule, input_data)

        # Assert
        assert result['status'] == 'HIGH_DEFECT'
        assert result['confidence'] == 0.95

    def test_execute_normal(self, engine, sample_rule):
        """불량률 < 5% → NORMAL"""
        # Arrange
        input_data = {
            'defect_count': 1,
            'production_count': 100
        }

        # Act
        result = engine.execute(sample_rule, input_data)

        # Assert
        assert result['status'] == 'NORMAL'
        assert result['confidence'] == 0.80

    def test_execute_zero_production(self, engine, sample_rule):
        """생산량 0 → 예외 처리"""
        # Arrange
        input_data = {
            'defect_count': 0,
            'production_count': 0
        }

        # Act & Assert
        with pytest.raises(ZeroDivisionError):
            engine.execute(sample_rule, input_data)
```

---

#### TC-JUD-005: InputValidator 스키마 검증

```python
# tests/unit/judgment/test_input_validator.py
import pytest
from src.judgment.input_validator import InputValidator
from src.judgment.exceptions import ValidationError

class TestInputValidator:
    @pytest.fixture
    def validator(self):
        return InputValidator()

    @pytest.fixture
    def schema(self):
        return {
            'type': 'object',
            'properties': {
                'line_code': {'type': 'string'},
                'defect_count': {'type': 'number'},
                'production_count': {'type': 'number'}
            },
            'required': ['line_code', 'defect_count', 'production_count']
        }

    def test_validate_success(self, validator, schema):
        """정상 입력 → 검증 통과"""
        input_data = {
            'line_code': 'LINE-A',
            'defect_count': 5,
            'production_count': 100
        }

        # 예외 없이 통과
        validator.validate(input_data, schema)

    def test_validate_missing_required(self, validator, schema):
        """필수 필드 누락 → ValidationError"""
        input_data = {
            'line_code': 'LINE-A'
            # defect_count, production_count 누락
        }

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(input_data, schema)

        assert 'defect_count' in str(exc_info.value)
        assert 'production_count' in str(exc_info.value)

    def test_validate_type_mismatch(self, validator, schema):
        """타입 불일치 → ValidationError"""
        input_data = {
            'line_code': 'LINE-A',
            'defect_count': '5',  # 문자열 (숫자 기대)
            'production_count': 100
        }

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(input_data, schema)

        assert 'defect_count' in str(exc_info.value)
        assert 'type' in str(exc_info.value).lower()
```

---

#### TC-JUD-030: HybridAggregator 가중 평균

```python
# tests/unit/judgment/test_result_aggregator.py
from src.judgment.result_aggregator import HybridWeightedAggregator

class TestHybridWeightedAggregator:
    def test_combine_weighted_average(self):
        """Rule + LLM 가중 평균"""
        aggregator = HybridWeightedAggregator(
            rule_weight=0.6,
            llm_weight=0.4
        )

        rule_result = {
            'status': 'HIGH_DEFECT',
            'confidence': 0.90
        }

        llm_result = {
            'status': 'MODERATE_DEFECT',
            'confidence': 0.70
        }

        # Act
        final_result = aggregator.combine(rule_result, llm_result)

        # Assert
        expected_confidence = 0.90 * 0.6 + 0.70 * 0.4  # 0.82
        assert final_result['confidence'] == pytest.approx(0.82, abs=0.01)
        assert final_result['status'] == 'HIGH_DEFECT'  # 높은 신뢰도 우선
```

---

## 3. 통합 테스트 (Integration Testing)

### 3.1 개요
통합 테스트는 여러 컴포넌트 간 연동을 검증한다 (서비스, DB, Cache, 외부 API).

**목표**:
- 주요 API 엔드포인트 100% 커버
- 서비스 간 통신 정상 동작
- DB 트랜잭션 일관성

### 3.2 테스트 환경

**Docker Compose** (로컬 통합 테스트):
```yaml
# docker-compose.test.yml
version: '3.9'
services:
  postgres:
    image: postgres:14-alpine
    environment:
      POSTGRES_DB: factory_ai_test
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_password
    ports:
      - "5432:5432"

  redis:
    image: redis:7.2-alpine
    ports:
      - "6379:6379"

  judgment-service:
    build: ./backend/judgment
    depends_on:
      - postgres
      - redis
    environment:
      DATABASE_URL: postgresql://test_user:test_password@postgres:5432/factory_ai_test
      REDIS_URL: redis://redis:6379
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    ports:
      - "8010:8010"

  workflow-service:
    build: ./backend/workflow
    depends_on:
      - postgres
      - redis
      - judgment-service
    environment:
      DATABASE_URL: postgresql://test_user:test_password@postgres:5432/factory_ai_test
      JUDGMENT_SERVICE_URL: http://judgment-service:8010
    ports:
      - "8003:8003"
```

**실행**:
```bash
# 통합 테스트 환경 시작
docker-compose -f docker-compose.test.yml up -d

# 테스트 실행
pytest tests/integration -v

# 환경 정리
docker-compose -f docker-compose.test.yml down -v
```

### 3.3 통합 테스트 케이스 예시

#### TC-JUD-010: Judgment + Redis Cache 통합

**목적**: Judgment 실행 및 캐시 저장/조회 검증

```python
# tests/integration/judgment/test_judgment_cache.py
import pytest
import httpx
import time

@pytest.mark.integration
class TestJudgmentCache:
    @pytest.fixture
    async def client(self):
        async with httpx.AsyncClient(base_url="http://localhost:8010") as client:
            yield client

    async def test_cache_miss_then_hit(self, client):
        """Cache MISS → 실행 → Cache HIT"""
        # Arrange
        request_data = {
            'workflow_id': 'test-workflow-001',
            'input_data': {
                'line_code': 'LINE-A',
                'defect_count': 5,
                'production_count': 100
            },
            'policy': 'RULE_ONLY'  # LLM 호출 없음 (빠른 테스트)
        }

        # Act 1: 첫 번째 요청 (Cache MISS)
        start_time = time.time()
        response1 = await client.post('/api/v1/judgment/execute', json=request_data)
        elapsed1 = (time.time() - start_time) * 1000

        # Assert 1
        assert response1.status_code == 200
        result1 = response1.json()
        assert result1['from_cache'] == False
        assert elapsed1 < 1500  # < 1.5초 (Rule Only)

        # Act 2: 두 번째 요청 (Cache HIT)
        start_time = time.time()
        response2 = await client.post('/api/v1/judgment/execute', json=request_data)
        elapsed2 = (time.time() - start_time) * 1000

        # Assert 2
        assert response2.status_code == 200
        result2 = response2.json()
        assert result2['from_cache'] == True
        assert elapsed2 < 300  # < 300ms (캐시 적중)
        assert result2['result'] == result1['result']  # 결과 동일

    async def test_cache_invalidation_on_rule_deploy(self, client):
        """Rule 배포 시 캐시 무효화"""
        # Arrange: 첫 번째 Judgment 실행 (캐시 저장)
        request_data = { ... }
        response1 = await client.post('/api/v1/judgment/execute', json=request_data)

        # Act: Rule 배포 (캐시 무효화)
        deploy_response = await client.post('/api/v1/learning/deploy', json={
            'ruleset_id': 'ruleset-001',
            'workflow_id': 'test-workflow-001',
            'strategy': 'immediate'
        })
        assert deploy_response.status_code == 200

        # Act: 다시 Judgment 실행 (Cache MISS 기대)
        response2 = await client.post('/api/v1/judgment/execute', json=request_data)

        # Assert: from_cache = False (캐시 무효화 확인)
        result2 = response2.json()
        assert result2['from_cache'] == False
```

---

#### TC-WF-030: Workflow SWITCH 노드 통합

**목적**: SWITCH 노드 조건 분기 검증

```python
# tests/integration/workflow/test_flow_control.py
@pytest.mark.integration
class TestSwitchNode:
    async def test_switch_critical_branch(self, client):
        """Severity = critical → notify_manager 분기"""
        # Arrange: Workflow DSL
        workflow_dsl = {
            'nodes': [
                {
                    'id': 'judge',
                    'type': 'JUDGMENT',
                    'config': {
                        'judgment_workflow_id': 'test-judgment-001',
                        'input_mapping': {...}
                    }
                },
                {
                    'id': 'severity_switch',
                    'type': 'SWITCH',
                    'config': {
                        'branches': [
                            {
                                'condition': "{{ nodes.judge.result.severity == 'critical' }}",
                                'target': 'notify_manager'
                            },
                            {
                                'condition': 'default',
                                'target': 'log_only'
                            }
                        ]
                    }
                },
                {
                    'id': 'notify_manager',
                    'type': 'ACTION',
                    'config': {'channel': 'slack', ...}
                },
                {
                    'id': 'log_only',
                    'type': 'DATA',
                    'config': {...}
                }
            ],
            'edges': [
                {'source': 'judge', 'target': 'severity_switch'},
                {'source': 'severity_switch', 'target': 'notify_manager'},
                {'source': 'severity_switch', 'target': 'log_only'}
            ]
        }

        # Act: Workflow 실행
        response = await client.post('/api/v1/workflows/execute', json={
            'workflow_dsl': workflow_dsl,
            'input_data': {'line_code': 'LINE-A', ...}
        })

        # Assert
        assert response.status_code == 200
        instance = response.json()

        # Context 확인
        context = instance['context']
        assert context['nodes']['judge']['output']['result']['severity'] == 'critical'
        assert 'notify_manager' in context['nodes']
        assert 'log_only' not in context['nodes']  # default 분기 실행 안 됨
```

---

#### TC-MCP-060: MCP 호출 Circuit Breaker 통합

**목적**: Circuit Breaker 동작 검증 (OPEN → Fallback)

```python
# tests/integration/mcp/test_circuit_breaker.py
@pytest.mark.integration
class TestMCPCircuitBreaker:
    async def test_circuit_breaker_opens_on_failures(self, client):
        """10회 중 6회 실패 → Circuit OPEN"""
        # Arrange: Mock MCP 서버 (실패 응답)
        mock_mcp_server_url = "http://localhost:9999/mcp"

        # Act: 10회 호출
        for i in range(10):
            if i < 6:
                # 처음 6회는 실패 (타임아웃)
                with pytest.raises(httpx.TimeoutException):
                    await call_mcp_tool('mcp-test', 'test_tool', {})
            else:
                # 나머지 4회는 성공
                result = await call_mcp_tool('mcp-test', 'test_tool', {})

        # Assert: Circuit Breaker OPEN 확인
        breaker_status = await get_circuit_breaker_status('mcp-test')
        assert breaker_status['state'] == 'OPEN'
        assert breaker_status['failure_rate'] > 0.5

        # Act: Circuit OPEN 상태에서 호출 → 즉시 에러
        with pytest.raises(CircuitBreakerOpenError):
            await call_mcp_tool('mcp-test', 'test_tool', {})

    async def test_circuit_breaker_half_open_recovery(self, client):
        """Circuit OPEN → 30초 대기 → HALF_OPEN → 성공 → CLOSED"""
        # Arrange: Circuit OPEN 상태 만들기 (위 테스트와 동일)
        # ...

        # Act: 30초 대기
        await asyncio.sleep(30)

        # Circuit HALF_OPEN 상태 확인
        breaker_status = await get_circuit_breaker_status('mcp-test')
        assert breaker_status['state'] == 'HALF_OPEN'

        # 테스트 요청 (성공)
        result = await call_mcp_tool('mcp-test', 'test_tool', {})

        # Assert: Circuit CLOSED로 복구
        breaker_status = await get_circuit_breaker_status('mcp-test')
        assert breaker_status['state'] == 'CLOSED'
```

---

### 3.4 통합 테스트 패턴

#### 3.4.1 Mocking 전략

**원칙**: 외부 의존성은 Mock, 내부 서비스는 실제 연동

| 컴포넌트 | Mock 여부 | 이유 |
|---------|----------|------|
| **PostgreSQL** | ❌ Real | DB 트랜잭션 검증 필요 |
| **Redis** | ❌ Real | 캐시 동작 검증 필요 |
| **LLM API** | ✅ Mock | 비용, 속도, 안정성 |
| **MCP Server** | ✅ Mock | 외부 의존성, 제어 불가 |
| **ERP/MES** | ✅ Mock | 외부 시스템, 테스트 데이터 |

**LLM Mock 예시**:
```python
# tests/mocks/mock_llm_client.py
from src.judgment.llm_client import ILLMClient

class MockLLMClient(ILLMClient):
    def __init__(self, responses: dict):
        self.responses = responses

    async def call(self, workflow_id: str, input_data: dict, rule_result: dict) -> dict:
        """고정된 응답 반환"""
        # workflow_id 기반 사전 정의 응답
        if workflow_id in self.responses:
            return self.responses[workflow_id]
        else:
            # 기본 응답
            return {
                'status': 'MODERATE_DEFECT',
                'confidence': 0.75,
                'explanation': 'Mock LLM response'
            }

# 사용 예시
mock_llm = MockLLMClient(responses={
    'test-workflow-001': {
        'status': 'HIGH_DEFECT',
        'confidence': 0.88,
        'explanation': 'Equipment calibration issue detected'
    }
})

judgment_service = JudgmentService(
    llm_client=mock_llm  # Mock 주입
)
```

#### 3.4.2 테스트 Fixture

**pytest conftest.py**:
```python
# tests/conftest.py
import pytest
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture(scope="session")
def event_loop():
    """이벤트 루프 (비동기 테스트)"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def db_engine():
    """테스트 DB 엔진"""
    engine = create_engine('postgresql://test_user:test_password@localhost:5432/factory_ai_test')
    yield engine
    engine.dispose()

@pytest.fixture(scope="function")
def db_session(db_engine):
    """테스트 DB 세션 (각 테스트 후 롤백)"""
    connection = db_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture
def redis_client():
    """Redis 클라이언트"""
    import redis
    client = redis.Redis(host='localhost', port=6379, db=1, decode_responses=True)
    yield client
    client.flushdb()  # 테스트 후 DB 클리어

@pytest.fixture
def mock_llm_client():
    """Mock LLM 클라이언트"""
    return MockLLMClient(responses={})
```

---

## 다음 파일로 계속

본 문서는 C-3-1로, 테스트 전략 개요, 단위 테스트, 통합 테스트를 포함한다.

**다음 파일**:
- **C-3-2**: E2E 테스트, 성능 테스트, 보안 테스트, UAT

---

## 문서 이력
| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2025-10-20 | QA Team | 초안 작성 |
| 2.0 | 2025-11-26 | QA Team | Enhanced 버전 (상세 테스트 케이스, Mock 전략 추가) |
