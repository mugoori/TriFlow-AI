# C-2. Coding Standard & Repository Guide - Enhanced

## 문서 정보
- **문서 ID**: C-2
- **버전**: 3.0 (V7 Intent + Orchestrator)
- **최종 수정일**: 2025-12-16
- **상태**: Active Development
- **관련 문서**:
  - B-1 System Architecture
  - B-2 Module/Service Design
  - C-1 Development Plan
  - C-3 Test Plan

## 목차
1. [코딩 컨벤션](#1-코딩-컨벤션)
2. [프로젝트 구조](#2-프로젝트-구조)
3. [Git 브랜치 전략](#3-git-브랜치-전략)
4. [코드 리뷰 정책](#4-코드-리뷰-정책)
5. [품질 자동화](#5-품질-자동화)
6. [문서 및 스키마 관리](#6-문서-및-스키마-관리)

---

## 1. 코딩 컨벤션

### 1.1 Python (Backend)

#### 1.1.1 스타일 가이드

**기준**: PEP 8 + Google Python Style Guide

**주요 규칙**:
- **들여쓰기**: 4 spaces (탭 금지)
- **줄 길이**: 최대 100자 (docstring 72자)
- **명명 규칙**:
  - 클래스: PascalCase (`JudgmentService`)
  - 함수/변수: snake_case (`execute_judgment`)
  - 상수: UPPER_SNAKE_CASE (`MAX_RETRY_COUNT`)
  - Private: _leading_underscore (`_internal_method`)

**예시**:
```python
# ✅ 좋은 예
from typing import Optional, Dict, Any

class JudgmentService:
    """Judgment 실행 서비스

    Attributes:
        rule_engine: Rule 엔진
        llm_client: LLM 클라이언트
    """

    MAX_RETRY_COUNT = 3  # 상수

    def __init__(
        self,
        rule_engine: IRuleEngine,
        llm_client: ILLMClient
    ):
        self.rule_engine = rule_engine
        self.llm_client = llm_client

    async def execute_judgment(
        self,
        workflow_id: str,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Judgment 실행

        Args:
            workflow_id: Workflow ID
            input_data: 입력 데이터

        Returns:
            Judgment 결과 dict

        Raises:
            ValidationError: 입력 검증 실패
            JudgmentError: 판단 실행 실패
        """
        # 구현...
        pass

    def _validate_input(self, input_data: dict) -> None:
        """내부 메소드 (private)"""
        pass
```

#### 1.1.2 타입 힌트 (Type Hints)

**원칙**: 모든 함수에 타입 힌트 필수

```python
from typing import Optional, List, Dict, Any, Union

# ✅ 좋은 예
async def get_judgment(
    judgment_id: str,
    include_explanation: bool = False
) -> Optional[Dict[str, Any]]:
    """Judgment 조회"""
    pass

# ❌ 나쁜 예 (타입 힌트 없음)
async def get_judgment(judgment_id, include_explanation=False):
    pass
```

**mypy 설정** (pyproject.toml):
```toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

#### 1.1.3 포맷팅 및 Linting

**도구**:
- **Black**: 자동 포맷팅
- **isort**: import 정렬
- **Ruff**: Linting (pylint 대체, 빠름)

**설정** (pyproject.toml):
```toml
[tool.black]
line-length = 100
target-version = ['py311']

[tool.isort]
profile = "black"
line_length = 100

[tool.ruff]
line-length = 100
select = ["E", "F", "W", "I", "N", "UP", "ANN", "S", "B"]
ignore = ["ANN101", "ANN102"]  # self, cls 타입 힌트 생략 허용
```

---

### 1.2 TypeScript (Frontend)

#### 1.2.1 스타일 가이드

**기준**: Airbnb TypeScript Style Guide

**주요 규칙**:
- **들여쓰기**: 2 spaces
- **세미콜론**: 필수
- **따옴표**: 싱글 쿼트 (')
- **명명 규칙**:
  - 컴포넌트: PascalCase (`JudgmentCard`)
  - 함수/변수: camelCase (`executeJudgment`)
  - 상수: UPPER_SNAKE_CASE (`MAX_RETRY_COUNT`)
  - 인터페이스: PascalCase + I 접두사 (`IJudgmentService`)
  - 타입: PascalCase (`JudgmentResult`)

**예시**:
```typescript
// ✅ 좋은 예
import React from 'react';

interface JudgmentCardProps {
  judgment: Judgment;
  onFeedback: (feedback: Feedback) => void;
}

const JudgmentCard: React.FC<JudgmentCardProps> = ({ judgment, onFeedback }) => {
  const handleThumbsUp = () => {
    onFeedback({ type: 'thumbs_up', execution_id: judgment.execution_id });
  };

  return (
    <div className="judgment-card">
      <h3>{judgment.result.status}</h3>
      <p>Confidence: {judgment.confidence.toFixed(2)}</p>
      <button onClick={handleThumbsUp}>👍 Helpful</button>
    </div>
  );
};

export default JudgmentCard;
```

#### 1.2.2 ESLint 및 Prettier 설정

**.eslintrc.json**:
```json
{
  "extends": [
    "airbnb",
    "airbnb-typescript",
    "airbnb/hooks",
    "plugin:@typescript-eslint/recommended",
    "plugin:prettier/recommended"
  ],
  "parserOptions": {
    "project": "./tsconfig.json"
  },
  "rules": {
    "react/react-in-jsx-scope": "off",
    "import/prefer-default-export": "off",
    "@typescript-eslint/explicit-function-return-type": "warn"
  }
}
```

**.prettierrc**:
```json
{
  "semi": true,
  "singleQuote": true,
  "tabWidth": 2,
  "trailingComma": "es5",
  "printWidth": 100
}
```

---

### 1.3 SQL (Database)

#### 1.3.1 명명 규칙

**원칙**: snake_case, 명확한 이름, 약어 최소화

| 항목 | 규칙 | 예시 |
|------|------|------|
| **테이블** | 복수형, snake_case | `judgment_executions`, `workflow_instances` |
| **컬럼** | snake_case | `workflow_id`, `executed_at` |
| **인덱스** | idx_{table}_{columns} | `idx_judgment_executions_tenant_workflow` |
| **제약조건 (FK)** | fk_{table}_{ref_table} | `fk_judgment_executions_workflows` |
| **함수** | snake_case, 동사 시작 | `create_monthly_partition()` |
| **스키마** | snake_case | `core`, `bi`, `rag` |

**SQL 포맷팅**:
```sql
-- ✅ 좋은 예
SELECT
  j.id,
  j.workflow_id,
  j.executed_at,
  w.name AS workflow_name
FROM core.judgment_executions j
JOIN core.workflows w ON j.workflow_id = w.id
WHERE j.tenant_id = $1
  AND j.executed_at >= $2
ORDER BY j.executed_at DESC
LIMIT 100;

-- ❌ 나쁜 예 (포맷팅 없음)
SELECT j.id,j.workflow_id,j.executed_at,w.name as workflow_name FROM core.judgment_executions j JOIN core.workflows w ON j.workflow_id=w.id WHERE j.tenant_id=$1 AND j.executed_at>=$2 ORDER BY j.executed_at DESC LIMIT 100;
```

---

### 1.4 V7 Intent 및 노드 타입 명명 규칙

#### 1.4.1 V7 Intent 명명 규칙

**Intent 카테고리별 상수**:
```python
# ✅ 좋은 예 - V7 Intent 정의
class V7Intent(str, Enum):
    """V7 Intent 열거형 (14개)"""
    # 정보 조회 (Information) - 4개
    CHECK = "CHECK"               # 단순 현재 상태/수치 조회
    TREND = "TREND"               # 시간에 따른 변화/추이
    COMPARE = "COMPARE"           # 두 개 이상 대상 비교
    RANK = "RANK"                 # 순위/최대/최소 조회

    # 분석 (Analysis) - 4개
    FIND_CAUSE = "FIND_CAUSE"     # 원인 분석
    DETECT_ANOMALY = "DETECT_ANOMALY"  # 이상/문제 탐지
    PREDICT = "PREDICT"           # 미래 예측
    WHAT_IF = "WHAT_IF"           # 가정/시뮬레이션

    # 액션 (Action) - 2개
    REPORT = "REPORT"             # 보고서/차트 생성
    NOTIFY = "NOTIFY"             # 알림/워크플로우 설정

    # 대화 제어 (Conversation) - 4개
    CONTINUE = "CONTINUE"         # 대화 계속
    CLARIFY = "CLARIFY"           # 명확화 필요
    STOP = "STOP"                 # 중단/취소
    SYSTEM = "SYSTEM"             # 인사, 도움말
```

**Route Target 정의**:
```python
class RouteTarget(str, Enum):
    """V7 Intent → 라우팅 대상"""
    DATA_LAYER = "data_layer"           # 직접 데이터 조회
    JUDGMENT_ENGINE = "judgment_engine" # 판단/분석 필요
    RULE_ENGINE = "rule_engine"         # 규칙 기반 처리
    BI_GUIDE = "bi_guide"               # BI 서비스 안내
    WORKFLOW_GUIDE = "workflow_guide"   # Workflow 생성 안내
    CONTEXT_DEPENDENT = "context_dependent"  # 이전 대화 기반
    ASK_BACK = "ask_back"               # 추가 질문 필요
    DIRECT_RESPONSE = "direct_response" # 직접 응답
```

#### 1.4.2 노드 타입 명명 규칙 (15개)

**노드 타입 상수**:
```python
class NodeType(str, Enum):
    """Workflow 노드 타입 (15개, 우선순위별)"""
    # P0 (핵심) - 5개
    DATA = "DATA"           # 데이터 조회
    JUDGMENT = "JUDGMENT"   # 판단 수행
    CODE = "CODE"           # Python 코드 실행
    SWITCH = "SWITCH"       # 분기 처리
    ACTION = "ACTION"       # 외부 액션

    # P1 (확장) - 5개
    BI = "BI"               # BI 대시보드
    MCP = "MCP"             # MCP 도구 호출
    TRIGGER = "TRIGGER"     # 이벤트 트리거 (신규)
    WAIT = "WAIT"           # 대기
    APPROVAL = "APPROVAL"   # 승인

    # P2 (고급) - 5개
    PARALLEL = "PARALLEL"   # 병렬 실행
    COMPENSATION = "COMPENSATION"  # 보상 트랜잭션
    DEPLOY = "DEPLOY"       # 배포
    ROLLBACK = "ROLLBACK"   # 롤백
    SIMULATE = "SIMULATE"   # 시뮬레이션
```

**Route → Node 매핑 규칙**:
```python
# Orchestrator Plan Generator 패턴
ROUTE_TO_NODE_MAP: Dict[str, List[NodeType]] = {
    "data_layer": [NodeType.DATA, NodeType.CODE],
    "judgment_engine": [NodeType.DATA, NodeType.JUDGMENT, NodeType.CODE],
    "rule_engine": [NodeType.DATA, NodeType.CODE, NodeType.SWITCH],
    "bi_guide": [NodeType.DATA, NodeType.BI, NodeType.CODE],
    "workflow_guide": [
        NodeType.TRIGGER, NodeType.DATA, NodeType.JUDGMENT,
        NodeType.ACTION, NodeType.WAIT
    ],
}
```

---

## 2. 프로젝트 구조

### 2.1 Monorepo 구조

```
factory-ai-platform/
├── services/
│   ├── judgment/
│   │   ├── src/
│   │   │   ├── api/
│   │   │   │   ├── routes.py
│   │   │   │   └── dependencies.py
│   │   │   ├── domain/
│   │   │   │   ├── service.py
│   │   │   │   ├── rule_engine.py
│   │   │   │   └── llm_client.py
│   │   │   ├── infrastructure/
│   │   │   │   ├── repository.py
│   │   │   │   └── cache.py
│   │   │   └── main.py
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   ├── integration/
│   │   │   └── conftest.py
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── pyproject.toml
│   ├── intent-router/          # V7 Intent 체계
│   │   ├── src/
│   │   │   ├── schema.py       # V7 Intent 정의 (14개)
│   │   │   ├── classifier.py   # Intent 분류기
│   │   │   ├── slot_extractor.py
│   │   │   ├── legacy_mapper.py  # Legacy → V7 매핑
│   │   │   └── router.py
│   │   └── tests/
│   ├── orchestrator/           # Orchestrator Service
│   │   ├── src/
│   │   │   ├── plan_generator.py
│   │   │   ├── route_mapper.py  # Route → Node 매핑
│   │   │   ├── dsl_generator.py
│   │   │   └── orchestrator.py
│   │   └── tests/
│   ├── workflow/               # 15 노드 타입
│   │   ├── src/
│   │   │   ├── nodes/
│   │   │   │   ├── p0/         # 핵심 노드 (DATA, JUDGMENT, CODE, SWITCH, ACTION)
│   │   │   │   ├── p1/         # 확장 노드 (BI, MCP, TRIGGER, WAIT, APPROVAL)
│   │   │   │   └── p2/         # 고급 노드 (PARALLEL, COMPENSATION, ...)
│   │   │   ├── engine.py
│   │   │   └── state.py
│   │   └── tests/
│   └── bi/
│       └── (동일 구조)
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Judgment/
│   │   │   ├── Workflow/
│   │   │   └── BI/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── stores/
│   │   └── api/
│   ├── public/
│   ├── package.json
│   └── tsconfig.json
├── libs/
│   ├── common-types/
│   │   ├── src/
│   │   │   ├── judgment.ts
│   │   │   ├── workflow.ts
│   │   │   └── bi.ts
│   │   └── package.json
│   └── tracing/
│       └── (공통 추적 라이브러리)
├── infra/
│   ├── k8s/
│   │   ├── base/
│   │   └── overlays/
│   │       ├── staging/
│   │       └── production/
│   └── terraform/
│       └── (IaC)
├── data/
│   ├── migrations/
│   │   └── versions/
│   └── seeds/
│       └── seed_data.sql
├── docs/
│   └── (A-1~D-4 문서)
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── cd.yml
├── docker-compose.yml
└── README.md
```

### 2.2 Service 내부 구조 (Clean Architecture)

```
judgment/
├── src/
│   ├── api/                      # Presentation Layer
│   │   ├── routes.py            # FastAPI routes
│   │   ├── schemas.py           # Pydantic models (DTO)
│   │   └── dependencies.py       # Dependency Injection
│   ├── domain/                   # Domain Layer
│   │   ├── service.py           # JudgmentService (비즈니스 로직)
│   │   ├── entities.py          # Domain entities
│   │   ├── interfaces.py        # Interfaces (IRuleEngine, ILLMClient)
│   │   ├── rule_engine.py       # Rule 실행
│   │   └── llm_client.py        # LLM 호출
│   ├── infrastructure/           # Infrastructure Layer
│   │   ├── repository.py        # DB 접근 (SQLAlchemy)
│   │   ├── cache.py             # Redis 캐시
│   │   └── event_publisher.py   # 이벤트 발행
│   ├── config.py                 # 설정
│   ├── logging_config.py         # 로깅 설정
│   └── main.py                   # FastAPI 앱
└── tests/
    ├── unit/
    ├── integration/
    └── conftest.py
```

---

## 3. Git 브랜치 전략

### 3.1 Trunk-Based Development

**주요 브랜치**:
- **main**: Production 배포 브랜치 (보호됨)
- **feature/\***: 기능 개발 브랜치 (단기, 1~3일)
- **hotfix/\***: 긴급 수정 브랜치

**흐름**:
```
main ──┬─────────────────────────> v1.0.0
       │
       ├─ feature/judgment-cache
       │  └─> (PR) ─> main
       │
       ├─ feature/workflow-switch
       │  └─> (PR) ─> main
       │
       └─ hotfix/llm-parsing-fix
          └─> (PR) ─> main
```

**브랜치 명명**:
- `feature/{jira-ticket}-{short-description}`
  - 예: `feature/FAC-123-judgment-cache`
- `hotfix/{issue-number}-{short-description}`
  - 예: `hotfix/456-llm-parsing-fix`

### 3.2 Commit Message Convention

**형식**: `type(scope): message`

**타입**:
- `feat`: 새 기능
- `fix`: 버그 수정
- `refactor`: 리팩토링
- `test`: 테스트 추가
- `docs`: 문서 변경
- `chore`: 기타 (빌드, 의존성)
- `perf`: 성능 개선
- `ci`: CI/CD 변경

**예시**:
```
feat(judgment): add hybrid weighted aggregation
fix(workflow): resolve circuit breaker timeout issue
refactor(bi): extract SQL generator to separate class
test(judgment): add unit tests for rule engine
docs(readme): update installation instructions
chore(deps): upgrade fastapi to 0.104.1
perf(cache): optimize redis pipeline
ci(github): add security scan to workflow
```

---

## 4. 코드 리뷰 정책

### 4.1 Pull Request 규칙

**필수 조건**:
- [ ] CI 테스트 통과 (lint, test, build)
- [ ] 최소 1명 승인 (핵심 모듈은 2명)
- [ ] 브랜치명 및 커밋 메시지 컨벤션 준수
- [ ] PR 설명 작성 (변경 사항, 테스트 방법)

**PR 템플릿**:
```markdown
## 변경 사항
- Judgment Service에 Hybrid Weighted 정책 추가
- 가중치 설정 기능 (rule_weight, llm_weight)

## 테스트
- 단위 테스트: test_hybrid_aggregator.py (커버리지 95%)
- 통합 테스트: test_judgment_integration.py

## 체크리스트
- [x] 코드 리뷰 체크리스트 확인
- [x] 단위 테스트 작성 및 통과
- [x] 문서 업데이트 (API 문서)
- [x] Breaking Change 없음

## 스크린샷 (선택적)
(UI 변경 시 스크린샷 첨부)
```

### 4.2 코드 리뷰 체크리스트

#### 4.2.1 기능 및 설계
- [ ] 요구사항 충족 (A-2 참조)
- [ ] 설계 문서 준수 (B-2 참조)
- [ ] SOLID 원칙 준수
- [ ] 에러 처리 적절 (try-except, 로그)
- [ ] 비즈니스 로직이 Domain Layer에 위치

#### 4.2.2 보안
- [ ] SQL Injection 방어 (Prepared Statement)
- [ ] XSS 방어 (출력 인코딩)
- [ ] PII 마스킹 적용
- [ ] 권한 체크 (RBAC)
- [ ] 민감 정보 로깅 금지

#### 4.2.3 성능
- [ ] N+1 쿼리 없음
- [ ] 적절한 인덱스 사용
- [ ] 캐싱 고려
- [ ] 비동기 I/O 사용 (가능한 경우)
- [ ] 메모리 누수 없음

#### 4.2.4 테스트
- [ ] 단위 테스트 작성 (커버리지 > 80%)
- [ ] 주요 경로 통합 테스트
- [ ] 엣지 케이스 테스트 (경계값, null, 빈 배열)

---

## 5. 품질 자동화

### 5.1 Pre-commit Hooks

**설치**:
```bash
pip install pre-commit
pre-commit install
```

**.pre-commit-config.yaml**:
```yaml
repos:
  # Python
  - repo: https://github.com/psf/black
    rev: 23.11.0
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort

  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.1.5
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]

  # TypeScript
  - repo: https://github.com/pre-commit/mirrors-prettier
    rev: v3.1.0
    hooks:
      - id: prettier
        types_or: [javascript, jsx, ts, tsx]

  # 보안
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']

  # Git
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
```

**실행**:
```bash
# 커밋 전 자동 실행
git commit -m "feat(judgment): add caching"

# 수동 실행 (모든 파일)
pre-commit run --all-files
```

### 5.2 CI 파이프라인 (GitHub Actions)

**단계**:
1. **Lint**: pylint, mypy, ESLint
2. **Test**: pytest (단위 + 통합)
3. **Build**: Docker 이미지 빌드
4. **Security Scan**: Bandit, Trivy, npm audit
5. **Push**: Container Registry

**통과 기준**:
- Lint 에러 0개
- 테스트 통과율 100%
- 커버리지 > 80%
- 보안 스캔 Critical 취약점 0개

---

## 6. 문서 및 스키마 관리

### 6.1 API 문서 (OpenAPI/Swagger)

**FastAPI 자동 생성**:
```python
from fastapi import FastAPI

app = FastAPI(
    title="AI Factory Judgment Service",
    description="Rule + LLM Hybrid Judgment Engine",
    version="1.4.0",
    openapi_tags=[
        {
            "name": "judgment",
            "description": "Judgment execution and queries"
        },
        {
            "name": "simulation",
            "description": "What-if simulation and replay"
        }
    ]
)

@app.post(
    "/api/v1/judgment/execute",
    tags=["judgment"],
    summary="Execute judgment",
    response_model=JudgmentResponse
)
async def execute_judgment(request: JudgmentRequest):
    """
    Judgment 실행

    - **workflow_id**: Workflow ID (UUID)
    - **input_data**: 입력 데이터 (dict)
    - **policy**: Judgment 정책 (RULE_ONLY, LLM_ONLY, HYBRID_WEIGHTED, ...)

    Returns:
    - **execution_id**: 실행 ID
    - **result**: 판단 결과 (status, severity, confidence)
    - **explanation**: 설명 (선택적)
    """
    pass
```

**Swagger UI**: http://localhost:8010/docs

### 6.2 DB 마이그레이션 관리

**Alembic 워크플로우**:
```bash
# 마이그레이션 생성
alembic revision --autogenerate -m "add confidence field"

# 마이그레이션 적용
alembic upgrade head

# 롤백
alembic downgrade -1

# 현재 버전
alembic current

# 히스토리
alembic history
```

**마이그레이션 파일 리뷰**:
- [ ] Up/Down 스크립트 모두 작성
- [ ] 호환성 마이그레이션 (Zero-Downtime)
- [ ] 데이터 무결성 확인 (제약조건)
- [ ] 인덱스 추가 시 CONCURRENTLY 사용

---

## 결론

본 문서(C-2)는 **AI Factory Decision Engine** 의 코딩 표준 및 저장소 가이드를 상세히 수립하였다.

### 주요 성과
1. **코딩 컨벤션**: Python (PEP 8), TypeScript (Airbnb), SQL (snake_case)
2. **타입 안전성**: mypy (Python), TypeScript (strict mode)
3. **프로젝트 구조**: Monorepo, Clean Architecture, Bounded Context
4. **Git 전략**: Trunk-Based, Commit Message Convention
5. **코드 리뷰**: PR 템플릿, 체크리스트 (기능, 보안, 성능, 테스트)
6. **품질 자동화**: Pre-commit Hooks, CI/CD, 보안 스캔

### 다음 단계
1. 팀 교육 (Coding Standard)
2. Pre-commit Hooks 설치
3. 코드 리뷰 체크리스트 적용
4. 품질 메트릭 모니터링 (커버리지, Lint 점수)

---

## 문서 이력
| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2025-10-30 | Engineering Team | 초안 작성 |
| 2.0 | 2025-11-26 | Engineering Team | Enhanced 버전 (Python/TS 상세, Clean Architecture 추가) |
| 3.0 | 2025-12-16 | Engineering Team | V7 Intent + Orchestrator 통합 업데이트 |

### v3.0 변경 사항
- **V7 Intent 명명 규칙**: 14개 V7 Intent Enum 정의 가이드라인 추가
- **노드 타입 명명 규칙**: 15개 노드 타입 (P0/P1/P2) 코딩 표준 추가
- **Route Target 정의**: Intent→Route→Node 매핑 규칙 추가
- **프로젝트 구조 확장**: intent-router, orchestrator 서비스 디렉토리 구조 추가
- **Workflow 노드 구조**: P0/P1/P2 우선순위별 노드 디렉토리 구조 정의
