# Tasks & Progress

## 2026-01-28: 코드베이스 리팩토링 (P1-P4 완료)

### 개요
Backend 180+파일, Frontend 50+파일 전체 코드 리뷰 후 보안, 성능, 아키텍처 개선 작업 완료.

### P1: Critical (보안 취약점 수정)

#### 1. SQL Injection 방지
- **파일**: `backend/app/services/audit_service.py`
- **문제**: 동적 WHERE절 직접 삽입
- **해결**: 파라미터 바인딩으로 변경

#### 2. 권한 검증 추가
- **파일**: `backend/app/routers/deployments.py`
- **문제**: `/rollback-history`, `/rollback-stats` 권한 검증 없음
- **해결**: `@Depends(get_current_user)`, `@Depends(check_permission)` 추가

- **파일**: `backend/app/routers/experiments.py`
- **문제**: 테넌트 필터링 없음
- **해결**: `list_experiments`에서 `tenant_id` 필터 적용

#### 3. N+1 쿼리 제거
- **파일**: `backend/app/services/experiment_service.py`
- **문제**: variant별 반복 쿼리 (416-454줄)
- **해결**: 배치 쿼리로 통합

#### 4. 민감정보 마스킹 강화
- **파일**: `backend/app/services/audit_service.py`
- **확장된 SENSITIVE_FIELDS**:
```python
# 기존: password, token, secret, api_key
# 추가:
"ssn", "social_security", "resident_number", "주민등록번호",
"credit_card", "card_number", "cvv", "cvc",
"phone", "phone_number", "mobile", "전화번호", "휴대폰",
"address", "street", "zip_code", "postal_code", "주소",
"email", "이메일", "birth", "birthday", "생년월일",
"passport", "여권", "account", "account_number", "계좌", "pin"
```

### P2: High (환경변수 통합, 공통 유틸리티)

#### 1. Feature Flag 중앙화
- **파일**: `backend/app/config.py`
- **추가된 설정**:
```python
# Feature Flags (main.py에서 통합)
rate_limit_enabled: bool = True
metrics_enabled: bool = True
security_headers_enabled: bool = True
pii_masking_enabled: bool = True
audit_log_enabled: bool = True
i18n_enabled: bool = True

# Sample Curation
sample_default_confidence: float = 0.7
sample_recency_min_factor: float = 0.5
sample_recency_decay_days: int = 30

# Rate Limit 기본값
rate_limit_default_requests: int = 200
rate_limit_default_window: int = 60
```

- **파일**: `backend/app/main.py`
- **변경**: `os.getenv()` 직접 호출 제거 → `settings.xxx_enabled` 사용

#### 2. 공통 에러 처리 유틸리티
- **파일**: `backend/app/utils/errors.py`
- **추가 함수**:
```python
def require_tenant_access(resource, tenant_id, resource_name) -> Any:
    """테넌트 접근 권한 확인 (없으면 404)"""

def handle_service_error(e, default_message) -> None:
    """서비스 레이어 에러 → HTTP 에러 변환"""
```

- **적용 파일**: `deployments.py`에서 반복되던 테넌트 검증 코드 통합

### P3: Medium (React 성능, 타입 안정성, 하드코딩 제거)

#### 1. React 성능 최적화
- **파일**: `frontend/src/components/ChatMessage.tsx`
- **변경**: `React.memo`, `useMemo` 적용
```typescript
export const ChatMessage = memo(function ChatMessage({ message }) {
  const chartConfig = useMemo(() => extractChartConfig(message), [message]);
  const reasoningSummary = useMemo(() => extractReasoningSummary(message), [message]);
  // ...
});
```

- **파일**: `frontend/src/components/pages/DashboardPage.tsx`
- **변경**: 임계값 상수화
```typescript
const TEMPERATURE_THRESHOLD = 70;  // °C
const PRESSURE_THRESHOLD = 8;      // bar
```

#### 2. Tauri 타입 선언
- **파일**: `frontend/src/types/tauri.d.ts` (신규)
```typescript
declare global {
  interface Window {
    __TAURI__?: {
      invoke: <T>(cmd: string, args?: Record<string, unknown>) => Promise<T>;
      path?: { ... };
      event?: { ... };
      shell?: { ... };
      os?: { ... };
    };
  }
}
```

- **파일**: `frontend/src/services/agentService.ts`
- **변경**: `(window as any).__TAURI__` → 타입 안전한 `window.__TAURI__`

### P4: Low (console.log 정리)

#### 제거된 디버그 로그 (46개)

| 파일 | 제거 개수 |
|------|----------|
| `BIChatPanel.tsx` | 13개 |
| `agentService.ts` | 3개 |
| `workflowService.ts` | 3개 |
| `api.ts` | 1개 |
| `sensorStreamService.ts` | 2개 |
| `ChatContext.tsx` | 3개 |
| `DashboardPage.tsx` | 5개 |
| `WorkflowsPage.tsx` | 6개 |
| `WorkflowEditor.tsx` | 1개 |
| `FlowEditor.tsx` | 1개 |
| `AIModelConfigSection.tsx` | 4개 |
| `ModuleManagerSection.tsx` | 2개 |
| `useSensorStream.ts` | 1개 |
| `useCanaryVersion.ts` | 1개 |

#### 유지된 로그 (디버깅 필수)
- WebSocket 연결 상태 (Connected/Disconnected/Reconnecting)
- Tauri/Browser 환경 감지
- SSE 스트림 완료/종료 시그널
- `console.error`는 에러 추적용으로 모두 유지

### 수정된 파일 목록 (28개)

| 카테고리 | 파일 |
|---------|------|
| **Backend** | |
| 설정 | `config.py`, `main.py` |
| 유틸 | `utils/errors.py` |
| 서비스 | `audit_service.py`, `experiment_service.py`, `sample_curation_service.py` |
| 라우터 | `deployments.py`, `experiments.py` |
| **Frontend** | |
| 컴포넌트 | `ChatMessage.tsx`, `ChatContainer.tsx`, `DashboardPage.tsx`, `WorkflowsPage.tsx`, `WorkflowEditor.tsx`, `FlowEditor.tsx` |
| BI | `BIChatPanel.tsx` |
| 설정 | `AIModelConfigSection.tsx`, `ModuleManagerSection.tsx` |
| 서비스 | `agentService.ts`, `workflowService.ts`, `api.ts`, `sensorStreamService.ts` |
| 컨텍스트 | `ChatContext.tsx` |
| Hooks | `useSensorStream.ts`, `useCanaryVersion.ts` |
| 타입 | `tauri.d.ts` (신규) |

### 검증 완료
- ✅ Backend 테스트 93개 통과 (experiment_service 50 + audit_service 43)
- ✅ TypeScript 타입 체크 통과 (`npx tsc --noEmit`)
- ✅ 기존 기능 정상 동작 확인

---

## 2026-01-28: Korea Biopharm AI 레시피 저장 기능 완성

### 개요
AI 생성 레시피 저장 시 500 에러 수정 및 UX 개선 (삭제 확인 토스트).

### 완료된 작업

#### 1. AI 레시피 저장 500 에러 수정
- **문제**: POST `/api/v1/korea-biopharm/recipes/ai-generated` → 500 Internal Server Error
- **원인**: `db_service.py`에 로깅 코드 추가 시 `import logging` 누락으로 `NameError: name 'logger' is not defined` 발생
- **해결**: logger import 추가

**수정 파일**:
- `modules/korea_biopharm/backend/services/db_service.py`: logger import 추가 (L1-11)

```python
import logging
from typing import List, Optional, Dict, Any
...
logger = logging.getLogger(__name__)
```

#### 2. 삭제 확인 UI 개선 (브라우저 confirm → 토스트)
- **문제**: 브라우저 기본 `confirm()` 다이얼로그 사용 (UX 불량)
- **해결**: 커스텀 토스트 확인 UI 구현

**수정 파일**:
- `frontend/src/modules/korea_biopharm/frontend/components/RecipesPage.tsx`

**구현 내용**:
- `deleteConfirm` 상태 추가 (show, recipeId)
- `confirmDelete()`, `cancelDelete()` 함수 분리
- 화면 하단 중앙 토스트 UI (애니메이션 포함)
- 삭제 중 로딩 스피너 표시

### 이전 세션 작업 (레시피 관리 시스템 구현)

#### 3. DB 스키마 생성
- **파일**: `backend/db/init/10_create_korea_biopharm_tables.sql`
- **테이블**: `ai_generated_recipes`, `recipe_feedback`
- **뷰**: `unified_recipes` (기존 DB + AI 생성 통합)

#### 4. 백엔드 API 구현
- **파일**: `modules/korea_biopharm/backend/routers/recipes.py`
- **엔드포인트**:

| Method | Path | 설명 |
|--------|------|------|
| GET | `/unified` | 통합 레시피 목록 |
| POST | `/ai-generated` | AI 레시피 저장 |
| GET | `/ai-generated/{id}` | AI 레시피 상세 |
| DELETE | `/ai-generated/{id}` | AI 레시피 삭제 |
| PATCH | `/ai-generated/{id}/status` | 상태 변경 |
| POST | `/ai-generated/{id}/feedback` | 피드백 저장 |
| GET | `/ai-generated/{id}/feedback` | 피드백 조회 |

#### 5. 프론트엔드 구현
- **RecipesPage.tsx**: 통합 레시피 관리 UI (신규)
- **RecipeViewer.tsx**: 저장 기능 연결
- **api.ts**: AI 레시피 API 함수 추가
- **types/index.ts**: 타입 정의 추가

### 수정된 파일 목록 (17개)

| 카테고리 | 파일 |
|---------|------|
| **Backend** | |
| DB | `backend/db/init/10_create_korea_biopharm_tables.sql` (신규) |
| 서비스 | `services/db_service.py`, `services/recipe_service.py`, `services/search_service.py` |
| 라우터 | `routers/recipes.py`, `routers/search.py` |
| 스키마 | `models/schemas.py` |
| **Frontend** | |
| 컴포넌트 | `components/RecipesPage.tsx` (신규), `components/PromptOutput.tsx`, `components/RecipeViewer.tsx`, `components/ProductDetailModal.tsx` |
| 서비스 | `services/api.ts` |
| 타입 | `types/index.ts` |
| 페이지 | `KoreaBiopharmPage.tsx` |
| 스타일 | `index.css` |

### 검증 완료
- ✅ Python 문법 검사 통과
- ✅ TypeScript 타입 검사 통과
- ✅ 백엔드 서버 정상 실행
- ✅ AI 레시피 저장 테스트 성공 (`recipe_id = 25a591a1-...`)

---

## 2026-01-27: 과잉 구현 기능 정리 및 비활성화

### 개요
AWS 배포 대비 불필요하거나 과잉 구현된 기능들을 정리하여 시스템 복잡도 감소 및 리소스 절약.

### 완료된 작업

#### 1. Grafana 비활성화
- **이유**: AWS RDS 사용 시 CloudWatch + Enhanced Monitoring + Performance Insights로 충분
- **수정 파일**:
  - `docker-compose.yml`: grafana 서비스 및 grafana_data 볼륨 주석처리
  - `docker-compose.prod.yml`: 동일하게 주석처리
- **재활성화 방법**: 파일 내 주석 참조

#### 2. AlertManager 비활성화
- **이유**: AWS CloudWatch Alarms로 대체 가능
- **수정 파일**:
  - `docker-compose.yml`: alertmanager 서비스 및 alertmanager_data 볼륨 주석처리
- **참고**: docker-compose.prod.yml에는 AlertManager가 원래 없음

#### 3. IoT Collector 비활성화
- **이유**: 현재 프로젝트에서 MQTT/OPC UA 데이터 수집 미사용
- **수정 파일**:
  - `backend/app/main.py`: startup/shutdown 코드 주석처리 (lines 162-173, 191-198)
- **재활성화 방법**: 해당 주석 해제

#### 4. 미들웨어 환경변수 플래그 문서화
- **목적**: 선택적 비활성화 가능하도록 설정 가이드 추가
- **수정 파일**: `backend/.env.example`
- **지원 환경변수**:

| 환경변수 | 기본값 | 설명 |
|---------|:------:|------|
| `PII_MASKING_ENABLED` | true | 개인정보 자동 마스킹 |
| `AUDIT_LOG_ENABLED` | true | API 호출 감사 로그 |
| `RATE_LIMIT_ENABLED` | true | API 호출 제한 (DDoS 방지) |
| `I18N_ENABLED` | true | 다국어 에러 메시지 |
| `METRICS_ENABLED` | true | Prometheus 메트릭 수집 |
| `SECURITY_HEADERS_ENABLED` | true | XSS/Clickjacking 방지 헤더 |

### 유지된 서비스 (비활성화 제외)

| 서비스 | 유지 이유 |
|--------|----------|
| **MinIO** | 파일 업로드 기능 사용 시 RuntimeError 발생 가능 |
| **Prometheus** | 메트릭 수집 필요 (CloudWatch로 전송 가능) |
| **PostgreSQL/Redis** | 핵심 인프라 |

### 수정된 파일 목록 (4개)

| 파일 | 변경 내용 |
|------|----------|
| `docker-compose.yml` | Grafana, AlertManager 주석처리 |
| `docker-compose.prod.yml` | Grafana 주석처리 |
| `backend/app/main.py` | IoT Collector 주석처리 |
| `backend/.env.example` | 미들웨어 환경변수 섹션 추가 |

---

## 2026-01-27: Auto Execution 시스템 구현 (A-2-5 스펙)

### 개요
Trust Level × Risk Level → Execution Decision 기반의 자동 실행 시스템 구현.
AI(Ruleset)의 신뢰도와 작업 위험도를 조합하여 자동 실행 / 승인 필요 / 거부를 결정.

### 완료된 작업

#### 1. DB 마이그레이션 생성
- `backend/alembic/versions/017_auto_execution.py`
- 3개 테이블 생성: `decision_matrix`, `action_risk_definitions`, `auto_execution_logs`

#### 2. SQLAlchemy 모델 추가
- `backend/app/models/auto_execution.py`
- 모델: `DecisionMatrix`, `ActionRiskDefinition`, `AutoExecutionLog`
- 상수: `RiskLevel`, `ExecutionDecision`, `ExecutionStatus`

#### 3. DecisionMatrixService 구현
- `backend/app/services/decision_matrix_service.py`
- Decision Matrix CRUD 및 평가 로직
- A-2-5 스펙 기반 기본 매트릭스 정의

**Default Decision Matrix:**
```
              LOW      MEDIUM     HIGH      CRITICAL
Level 0    approval   approval   approval   reject
Level 1    approval   approval   approval   reject
Level 2    auto       approval   approval   reject
Level 3    auto       auto       approval   approval
```

#### 4. ActionRiskEvaluator 구현
- `backend/app/services/action_risk_evaluator.py`
- 액션 타입별 리스크 평가
- 패턴 매칭 지원 (fnmatch)

**기본 리스크 정의:**
| 액션 타입 | Risk Level |
|----------|:----------:|
| notification_* | LOW |
| data_query_* | LOW |
| parameter_adjust | MEDIUM |
| mes_equipment_control | HIGH |
| production_line_stop | CRITICAL |
| emergency_evacuation | CRITICAL |

#### 5. AutoExecutionRouter 구현
- `backend/app/services/auto_execution_router.py`
- TrustService + ActionRiskEvaluator + DecisionMatrixService 통합
- `evaluate()`: 실행 결정 평가만
- `route()`: 평가 + 실행/승인요청/거부 라우팅
- `execute_after_approval()`: 승인 후 실행
- `reject_after_approval()`: 승인 거부 처리

#### 6. Workflow Engine 연동
- `backend/app/services/workflow_engine.py` 수정
- `_evaluate_auto_execution()` 헬퍼 메서드 추가
- `_execute_approval_node()` 시작 시 Auto Execution 평가 먼저 수행
- `enable_auto_execution: true` 설정 시 활성화

#### 7. API 엔드포인트 구현
- `backend/app/schemas/auto_execution.py`: Pydantic 스키마
- `backend/app/routers/auto_execution.py`: API 라우터 (14개 엔드포인트)
- `backend/app/main.py`: 라우터 등록 (`/api/v2/auto-execution`)

**API 엔드포인트:**
| Method | Path | 설명 |
|--------|------|------|
| GET | /matrix | Decision Matrix 조회 |
| PUT | /matrix/{trust}/{risk} | 매트릭스 엔트리 수정 |
| POST | /matrix/reset | 기본값으로 리셋 |
| GET | /risks | 액션 리스크 정의 목록 |
| POST | /risks | 새 리스크 정의 생성 |
| POST | /risks/initialize | 기본 리스크 정의 초기화 |
| POST | /evaluate | 실행 결정 평가 |
| GET | /logs | 실행 로그 조회 |
| GET | /pending | 승인 대기 목록 |
| POST | /logs/{id}/action | 승인/거부 처리 |
| GET | /stats | 실행 통계 |
| GET | /risks/summary | 리스크 요약 |

### 수정된 파일 목록 (8개)

| 카테고리 | 파일 |
|---------|------|
| 마이그레이션 | `alembic/versions/017_auto_execution.py` |
| 모델 | `models/auto_execution.py`, `models/__init__.py` |
| 서비스 | `services/decision_matrix_service.py`, `services/action_risk_evaluator.py`, `services/auto_execution_router.py`, `services/workflow_engine.py` |
| 스키마 | `schemas/auto_execution.py` |
| 라우터 | `routers/auto_execution.py` |
| 앱 | `main.py` |

### 검증 완료
- ✅ 모든 모듈 import 테스트 통과
- ✅ 14개 API 라우트 등록 확인
- ✅ 마이그레이션 파일 생성 확인

### 사용 예시

```python
# 1. 실행 결정 평가 (API)
POST /api/v2/auto-execution/evaluate
{
    "action_type": "mes_equipment_control",
    "ruleset_id": "uuid-here"
}

# 응답
{
    "decision": "require_approval",
    "reason": "Trust Level 2 + HIGH Risk",
    "context": {
        "trust_level": 2,
        "risk_level": "HIGH"
    }
}

# 2. Workflow에서 사용 (approval node)
{
    "type": "approval",
    "config": {
        "enable_auto_execution": true,
        "action_type": "parameter_adjust"
    }
}
```

---

## 2026-01-26: 하드코딩 제거 및 설정값 통일

### 완료된 작업

#### 1. 테넌트 이름 불일치 버그 수정
- **문제**: `"Default"` vs `"Default Tenant"` 혼용으로 인한 멀티테넌트 버그 가능성
- **해결**: 모든 테넌트 이름을 `settings.default_tenant_name`으로 통일

**수정 파일 (10곳)**:
- `backend/app/config.py`: `default_tenant_name: str = "Default"` 설정 추가
- `backend/app/init_db.py`: 환경변수 → settings 사용
- `backend/app/routers/auth.py`: 4곳 수정
- `backend/app/routers/sensors.py`, `rulesets.py`, `feedback.py`, `workflows.py`
- `backend/app/agents/learning_agent.py`: 2곳 수정

#### 2. LLM 모델명 폴백값 통일
- **문제**: `or "claude-sonnet-4-5-20250929"` 하드코딩이 여러 곳에 산재
- **해결**: `settings.default_llm_model` 사용으로 통일

**수정 파일 (6곳)**:
- `backend/app/agents/base_agent.py`
- `backend/app/services/bi_chat_service.py`
- `backend/app/services/insight_service.py`
- `backend/app/services/judgment_policy.py`
- `backend/app/services/story_service.py`
- `backend/app/services/settings_service.py`

#### 3. 알림 이메일 수신자 설정화
- **문제**: `["admin@example.com"]` 하드코딩
- **해결**: `settings.alert_email_recipients` 환경변수 사용

**수정 파일**:
- `backend/app/config.py`: `alert_email_recipients: str = ""` 설정 추가
- `backend/app/services/alert_handler.py`: 동적 이메일 목록 로드

#### 4. 매직 넘버 상수화
- **audit_service.py**:
  - `MAX_LIST_ITEMS = 100`
  - `MAX_STRING_LENGTH = 1000`
  - `TRUNCATED_STRING_LENGTH = 500`
- **judgment_policy.py**: `DEFAULT_CONFIDENCE = 0.75`
- **bi_chat_service.py**: `DEFAULT_CONFIDENCE = 0.5`
- **learning_agent.py**: `DEFAULT_CONFIDENCE = 0.75`

#### 5. LLM 가격 정보 주석 개선
- `backend/app/utils/metrics.py`: 출처 및 업데이트 날짜 추가

### 수정 파일 목록 (총 17개)

| 카테고리 | 파일 |
|---------|------|
| 설정 | `config.py` |
| 에이전트 | `base_agent.py`, `learning_agent.py` |
| 서비스 | `bi_chat_service.py`, `insight_service.py`, `judgment_policy.py`, `story_service.py`, `settings_service.py`, `alert_handler.py`, `audit_service.py` |
| 라우터 | `auth.py`, `sensors.py`, `rulesets.py`, `feedback.py`, `workflows.py` |
| 유틸 | `metrics.py` |
| 초기화 | `init_db.py` |

### 검증 완료
- ✅ 17개 모듈 임포트 테스트 통과
- ✅ 서버 시작 확인 (345개 라우트 등록)
- ✅ DB 테넌트 확인 (Default 테넌트 정상)
- ✅ API 테스트 8개 엔드포인트 통과
  - Auth Login, Auth Me, Workflows, Rulesets
  - Feedback, Settings, Users, Audit Logs

### 추가된 환경변수
```env
DEFAULT_TENANT_NAME=Default        # 기본값: "Default"
ALERT_EMAIL_RECIPIENTS=            # 콤마 구분, 빈값=이메일 미발송
```

---

## 2026-01-26: BI Chat 날짜 파싱 및 바이오팜 도메인 키워드 확장

### 완료된 작업

#### 1. BI Chat 날짜 파싱 기능 구현
- **문제**: 사용자가 "2025년 12월 24일 생산 현황" 질문 시 날짜 인식 안됨
- **해결**: 자연어 날짜 파싱 후 데이터 조회, 날짜 미지정 시 최신 데이터 날짜 자동 선택

**지원 날짜 형식**:
- 오늘, 어제, 그제
- N일 전, N주 전, N개월 전
- YYYY년 MM월 DD일
- YYYY-MM-DD, YYYY/MM/DD

**수정 파일**:
- `backend/app/services/bi_chat_service.py`: `parse_date_from_message()` 함수 추가
- `backend/app/services/bi_data_collector.py`: `get_latest_data_date()` 메서드 추가
- `backend/app/services/bi_correlation_analyzer.py`: None 값 비교 오류 수정

#### 2. async_engine 호환성 문제 해결
- **문제**: `cannot import name 'async_engine' from 'app.database'`
- **해결**: `_AsyncEngineProxy` 클래스 추가로 역방향 호환성 유지
- **수정 파일**: `backend/app/database.py`

#### 3. 바이오팜 도메인 키워드 확장
- **문제**: "마그네슘", "아연" 등 성분 키워드가 MetaRouterAgent로 잘못 라우팅
- **해결**: `modules/_registry.json`에 추가 키워드 등록

**추가된 키워드**:
```
마그네슘, 아연, 칼슘, 철분, 오메가,
유산균, 프로바이오틱스, 콜라겐, 히알루론산,
루테인, 밀크씨슬, 레시피, 제품, 건강기능식품
```

### 테스트 결과

| 쿼리 | Agent | 결과 |
|------|-------|------|
| "비타민D3 성분이 들어간 제품 목록" | BIPlannerAgent | 96개 제품 검색 |
| "마그네슘 포함 레시피 검색" | BIPlannerAgent | 50개 제품 |
| "아연이 들어간 제품 중 최근 5개" | BIPlannerAgent | 5개 제품 |
| "2025년 12월 24일 생산 현황" | BI Chat | 날짜 파싱 후 데이터 조회 |

---

## 2026-01-23: BI 데이터 질의 도구 강제 호출 및 tenant_id 자동 주입

### 완료된 작업

#### 1. tenant_id 자동 주입 (멀티테넌트 보안 강화)
- **문제**: AI가 도구 호출 시 `tenant_id` 파라미터를 생략하거나 잘못 전달
- **해결**: BaseAgent에서 도구 실행 전 필수 파라미터 자동 주입
- **구현 내용**:
  - `base_agent.py`: `_current_context` 저장 및 `_ensure_required_context()` 메서드 추가
  - 모든 도구 호출에 `tenant_id` 자동 주입 (AI 실수 방지)

#### 2. BI 데이터 질의 시 도구 호출 강제
- **문제**: 자연어 질의("비타민 C 제품 알려줘")에 AI가 도구 호출 없이 텍스트만 응답
- **해결**: 2단계 강제 메커니즘 적용

**2-1. 코드 레벨 (agent_orchestrator.py)**:
```python
# BI 데이터 질의 키워드 확장
data_query_keywords = [
    "알려", "보여", "찾아", "검색", "조회",
    "레시피", "제품", "원료", "배합", "비타민", "제형",
    ...
]
if any(kw in msg_lower for kw in data_query_keywords):
    return {"type": "any"}  # tool_choice 강제
```

**2-2. 프롬프트 레벨 (bi_planner.md)**:
- 🚨 MANDATORY 섹션 추가 (도구 사용 필수 규칙)
- 절대 금지 사항 명시 (텍스트만 응답 금지)
- 즉시 실행 SQL 패턴 제공

#### 3. 한국어 응답 규칙 추가
- **문제**: AI가 영어로 응답 ("Great, the query executed successfully...")
- **해결**: bi_planner.md에 언어 규칙 섹션 추가
```markdown
## 🌐 언어 규칙 (LANGUAGE RULE)
**반드시 한국어로 응답하세요!**
```

#### 4. 수정된 파일 목록

**Backend:**
- `backend/app/agents/base_agent.py` - tenant_id 자동 주입
- `backend/app/prompts/bi_planner.md` - 도구 강제 + 한국어 규칙
- `backend/app/services/agent_orchestrator.py` - tool_choice 강제

**Frontend:**
- `frontend/src/types/agent.ts` - 모델 타입 추가

### 검증 완료
- "비타민 C 제품을 포함한 레시피 10개 알려줘" 질의 시 데이터 정상 반환
- tenant_id 자동 주입 로그 확인 (`Auto-injected tenant_id`)
- 한국어 응답 규칙 적용 대기 중

---

## 2026-01-23: AI 모델 설정 기능 구현 및 UI 정리

### 완료된 작업

#### 1. DB 기반 테넌트별 AI 모델 설정 구현
- **목적**: 다른 고객사 비용 절감 요구 대응 (Haiku는 Sonnet 대비 약 12배 저렴)
- **구현 내용**:
  - `settings_service.py`: AI 모델 설정 정의 추가 (`default_llm_model`, 에이전트별 모델)
  - `base_agent.py`: `get_model(context)` 메서드 추가 - 테넌트별 동적 모델 로딩
  - 모든 에이전트에서 하드코딩된 모델명 제거 (meta_router, bi_planner, workflow_planner, judgment_agent, learning_agent)
  - 서비스 클래스에서도 하드코딩 제거 (bi_chat_service, story_service, insight_service, judgment_policy)

#### 2. 설정 우선순위 체계
```
1. 에이전트별 테넌트 설정 (예: bi_planner_model for tenant-a)
2. 기본 테넌트 설정 (default_llm_model for tenant-a)
3. 글로벌 설정
4. 환경변수 (DEFAULT_LLM_MODEL)
5. 코드 기본값 (claude-sonnet-4-5-20250929)
```

#### 3. 프론트엔드 설정 UI 정리
- **제거된 항목** (사용자 설정 탭):
  - AI 모델 카드 (모델 선택, Max Tokens, Tenant ID) - localStorage만 사용, 실제 동작 안함
  - Backend 연결 카드 (연결 상태, API URL, 자동 재연결) - 실제 API 호출에 영향 없음

- **유지/추가된 항목** (관리자/운영 탭):
  - `AIModelConfigSection.tsx`: DB 기반 AI 모델 설정 컴포넌트
  - 프리셋 버튼: Sonnet (품질), 하이브리드, Haiku (비용)
  - 에이전트별 모델 설정 가능

#### 4. 수정된 파일 목록

**Backend:**
- `backend/app/agents/base_agent.py` - 동적 모델 로딩
- `backend/app/agents/meta_router.py` - 하드코딩 제거
- `backend/app/agents/bi_planner.py` - 하드코딩 제거
- `backend/app/agents/workflow_planner.py` - 하드코딩 제거
- `backend/app/agents/judgment_agent.py` - 하드코딩 제거
- `backend/app/agents/learning_agent.py` - 하드코딩 제거
- `backend/app/services/settings_service.py` - AI 모델 설정 정의
- `backend/app/services/bi_chat_service.py` - 하드코딩 제거
- `backend/app/services/story_service.py` - 하드코딩 제거
- `backend/app/services/insight_service.py` - 하드코딩 제거
- `backend/app/services/judgment_policy.py` - 하드코딩 제거

**Frontend:**
- `frontend/src/components/pages/SettingsPage.tsx` - UI 정리
- `frontend/src/components/settings/AIModelConfigSection.tsx` - 새 컴포넌트

### 검증 완료
- Haiku 프리셋 적용 후 백엔드 로그에서 `claude-3-haiku-20240307` 모델 사용 확인
- 설정 저장/로드 정상 동작 확인

### 하이브리드 접근법 권장
| 기능 | 권장 모델 | 이유 |
|------|-----------|------|
| Meta Router | Haiku | 규칙 기반 우선 처리 |
| Judgment Agent | Haiku | 단순 데이터 조회 |
| Learning Agent | Haiku | DB 집계 중심 |
| BI Planner (단순 SQL) | Haiku | 단일 테이블 쿼리 |
| BI Planner (복잡 SQL/차트/인사이트) | **Sonnet** | JOIN, 서브쿼리, JSON 구조 |
| Workflow Planner (복잡 DSL) | **Sonnet** | 중첩 노드 구조 |
