# TriFlow AI - Troubleshooting Log

> **목적**: 반복적인 에러 수정 시도(Loop)를 방지하고 효율적인 문제 해결을 위한 이력 관리
> **규칙**: AI_GUIDELINES.md의 Rule 9 (Anti-Loop & Troubleshooting Protocol) 준수

---

## 📋 Log Entry Template

각 에러 발생 시 아래 양식으로 기록:

```markdown
### [날짜] 에러 제목
- **에러 메시지**: `오류 메시지 요약`
- **발생 위치**: 파일명:라인번호 또는 컴포넌트명
- **시도한 해결책**:
  1. 첫 번째 시도 (결과: 성공/실패)
  2. 두 번째 시도 (결과: 성공/실패)
- **근본 원인 (RCA)**: 에러의 실제 원인
- **최종 해결책**: 성공한 방법 또는 미해결 상태
- **참고 링크**: 관련 이슈, 문서, Stack Overflow 등
```

---

## 🔍 Troubleshooting History

### [2025-11-27] 초기 파일 생성
- **목적**: Rule 9 적용을 위한 트러블슈팅 로그 파일 생성
- **상태**: 정상 운영 시작
- **비고**: 이후 에러 발생 시 본 파일에 기록

---

## 📚 Common Issues & Solutions

### 카테고리별 자주 발생하는 에러와 해결책

#### 🐍 Backend (Python/FastAPI)

**[2025-12-26] CORS 에러로 표시되는 500 Internal Server Error**
- **에러**: `Access to fetch has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header` + `500 Internal Server Error`
- **발생 위치**: 모든 API 엔드포인트 (특히 `/api/v1/feedback/stats`)
- **증상**:
  - 브라우저 콘솔에 CORS 에러 표시
  - Network 탭에서 500 상태 코드 확인 가능
  - 백엔드 로그에 실제 예외 메시지 존재
- **시도한 해결책**:
  1. CORSMiddleware 설정 확인 (결과: 이미 정상)
  2. 예외 핸들러에 CORS 헤더 추가 (결과: **성공**)
- **근본 원인 (RCA)**:
  - CORSMiddleware가 정상 응답에만 CORS 헤더를 추가
  - 예외 핸들러가 반환하는 JSONResponse에는 CORS 헤더가 없음
  - 브라우저는 CORS 헤더 없는 응답을 CORS 정책 위반으로 표시
  - **실제 에러(DB 테이블 없음, 필드명 불일치 등)가 CORS 에러로 가려짐**
- **최종 해결책**:
  - `backend/app/main.py`에 `add_cors_headers()` 함수 추가
  - 모든 예외 핸들러에서 `return add_cors_headers(response, request)` 호출
  ```python
  def add_cors_headers(response: JSONResponse, request: Request) -> JSONResponse:
      origin = request.headers.get("origin", "")
      if origin and origin in settings.cors_origins_list:
          response.headers["Access-Control-Allow-Origin"] = origin
          response.headers["Access-Control-Allow-Credentials"] = "true"
          response.headers["Access-Control-Allow-Methods"] = "*"
          response.headers["Access-Control-Allow-Headers"] = "*"
      return response
  ```
- **디버깅 팁**:
  > ⚠️ **CORS 에러가 보이면, 먼저 백엔드 터미널 로그를 확인하세요!**
  > 대부분 실제 서버 에러(500)가 CORS로 가려진 것입니다.
- **수정 파일**:
  - `backend/app/main.py:223-238` - `add_cors_headers()` 함수
  - `backend/app/main.py:254,264,298,316` - 예외 핸들러에 적용

**[2025-12-26] feedback_logs 테이블 없음**
- **에러**: `relation "core.feedback_logs" does not exist`
- **발생 위치**: `/api/v1/feedback/*` 엔드포인트
- **근본 원인 (RCA)**:
  - SQLAlchemy 모델은 `core.feedback_logs` 참조
  - SQL 초기화 스크립트에 테이블 정의 누락
  - 모델의 `comment` 속성과 라우터의 `feedback_text` 필드명 불일치
- **최종 해결책**:
  1. `backend/db/init/03_create_core_tables.sql`에 `feedback_logs` 테이블 추가
  2. `backend/app/init_db.py`에 `_ensure_tables_exist()` 함수 추가 (서버 시작 시 자동 생성)
  3. `backend/app/routers/feedback.py`에서 `feedback_text` → `comment` 수정
- **새 모델 추가 시 체크리스트**:
  - [ ] SQLAlchemy 모델 정의 (`backend/app/models/`)
  - [ ] SQL 초기화 스크립트에 테이블 추가 (`backend/db/init/`)
  - [ ] 모델 필드명과 라우터 속성명 일치 확인
  - [ ] 서버 재시작하여 테이블 자동 생성 확인

#### 🎨 Frontend (Tauri/React)

**[2025-12-11] Tauri SSE 스트리밍 ERR_INCOMPLETE_CHUNKED_ENCODING (4차 수정 완료)**
- **에러**: `ERR_INCOMPLETE_CHUNKED_ENCODING`, `error decoding response body`
- **발생 위치**: `frontend/src/services/agentService.ts` - chatStream 함수
- **증상**:
  - curl 테스트는 정상 작동
  - Tauri 앱에서만 스트리밍 실패
  - "의도 분석중" 표시 후 즉시 에러 발생
- **시도한 해결책**:
  1. 백엔드 `data: [DONE]` 시그널 추가 (결과: 실패)
  2. StreamingResponse 헤더 개선 (결과: 실패)
  3. Tauri HTTP 플러그인 적용 (결과: 부분 성공 - URL 권한 후 `error decoding response body`)
  4. **Tauri에서 비스트리밍 API 사용** (결과: 성공)
- **근본 원인 (RCA)**:
  - Windows WebView2가 SSE/chunked encoding을 완벽히 지원하지 않음
  - Tauri HTTP 플러그인도 SSE (`text/event-stream`) 응답 파싱을 지원하지 않음
- **최종 해결책**:
  - Tauri 환경에서는 `/api/v1/agents/chat` (비스트리밍 API) 사용
  - 브라우저에서는 기존 SSE 스트리밍 유지
  - 수정 파일:
    - `frontend/src-tauri/Cargo.toml` - `tauri-plugin-http = "2"` 추가
    - `frontend/src-tauri/src/lib.rs` - `.plugin(tauri_plugin_http::init())` 추가
    - `frontend/src-tauri/capabilities/default.json` - `http:default`, `http:allow-fetch` 권한 추가
    - `frontend/src/services/agentService.ts` - 환경별 분기 처리 (Tauri: 비스트리밍, 브라우저: SSE)
- **참고 링크**:
  - https://v2.tauri.app/plugin/http-client/
  - https://github.com/nicholasking900816/tauri-plugin-websocket/issues/3 (유사 이슈)

**[2025-11-27] Tauri 빌드 시 TypeScript 컴파일 오류**
- **에러**: `Cannot find module '@/components/ui/alert'`, `Cannot find module '@/components/ui/table'`
- **해결책**: shadcn/ui의 alert.tsx, table.tsx 컴포넌트 수동 생성
- **RCA**: 차트 컴포넌트에서 아직 설치되지 않은 UI 컴포넌트를 참조

**[2025-11-27] PieChartComponent 타입 오류**
- **에러**: `Type '(entry: Record<string, unknown>) => string' is not assignable to type 'PieLabel'`
- **해결책**: `PieLabelRenderProps` 타입 import 후 props.name, props.value 사용
- **RCA**: Recharts의 label prop은 특정 타입의 함수만 허용

**[2025-11-27] Tauri config 오류**
- **에러**: `dangerousRemoteDomainIpcAccess was unexpected`
- **해결책**: tauri.conf.json에서 deprecated된 `dangerousRemoteDomainIpcAccess` 속성 제거
- **RCA**: Tauri v2에서 해당 속성이 더 이상 지원되지 않음

#### 📊 Database/Data

**[2025-12-30] Admin 비밀번호 불일치 (로그인 실패)**
- **에러**: `401 Unauthorized` - 로그인 시 비밀번호 검증 실패
- **발생 위치**: `POST /api/v1/auth/login`
- **증상**:
  - `admin@triflow.ai` 계정으로 로그인 불가
  - 비밀번호 `admin123` 입력 시 401 에러
- **근본 원인 (RCA)**:
  - DB의 `password_hash` 값이 예상과 불일치
  - 이전 마이그레이션 또는 초기화 과정에서 해시값 변경
- **최종 해결책**:
  - bcrypt로 새 해시 생성 후 DB 업데이트
  ```python
  from passlib.context import CryptContext
  pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
  new_hash = pwd_context.hash('admin123')
  # DB 업데이트
  cur.execute("UPDATE core.users SET password_hash = %s WHERE email = 'admin@triflow.ai'", (new_hash,))
  ```
- **디버깅 팁**:
  > 로그인 실패 시 먼저 DB에서 해당 사용자의 password_hash 존재 여부 확인
  > `SELECT email, password_hash FROM core.users WHERE email = '...'`

**[2025-12-30] CSV Import 파티션 오류 (과거 날짜 데이터)**
- **에러**: `no partition of relation "sensor_data" found for row`
- **발생 위치**: `POST /api/v1/sensors/import-csv`
- **증상**:
  - 2024년 날짜가 포함된 CSV 파일 업로드 시 500 에러
  - 현재 파티션 (2025_11, 2025_12)만 존재
- **근본 원인 (RCA)**:
  - `sensor_data` 테이블이 `recorded_at` 기준 월별 파티션 테이블
  - 해당 월의 파티션이 없으면 INSERT 실패
- **최종 해결책**:
  - `_ensure_partition_exists()` 함수 추가 (파티션 자동 생성)
  ```python
  def _ensure_partition_exists(db: Session, recorded_at: datetime) -> None:
      year, month = recorded_at.year, recorded_at.month
      partition_name = f"sensor_data_{year}_{month:02d}"
      # 파티션 존재 여부 확인 후 없으면 CREATE TABLE PARTITION
  ```
- **수정 파일**: `backend/app/routers/sensors.py`

**[2025-12-30] ERP/MES 및 RAG 탭 401 Unauthorized 오류**
- **에러**: `GET http://localhost:8000/api/v1/erp-mes/stats 401 (Unauthorized)`
- **발생 위치**: Data 탭 → ERP/MES, 지식 베이스 탭
- **증상**:
  - 다른 탭(Chat, Dashboard, Rulesets)은 정상 작동
  - ERP/MES, RAG 탭만 401 에러 발생
  - 백엔드 로그에 `user_id: None` 기록됨
- **근본 원인 (RCA)**:
  - `sensorService`는 `apiClient` 사용 → `getAccessToken()`으로 localStorage에서 직접 토큰 가져옴 (정상)
  - `erpMesService`, `ragService`는 직접 `fetch()` 사용 → 컴포넌트에서 React Context 통해 토큰 전달 (문제)
  - React Context의 비동기 초기화 타이밍 문제로 토큰이 전달되지 않음
- **최종 해결책**:
  - `erpMesService.ts`, `ragService.ts`를 `apiClient` 사용하도록 리팩토링
  - 컴포넌트에서 token 파라미터 제거
  ```typescript
  // Before (문제)
  export async function listErpMesData(params, token: string) {
    const response = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` }
    });
  }

  // After (해결)
  export async function listErpMesData(params) {
    return apiClient.get<ErpMesData[]>(endpoint);
  }
  ```
- **수정 파일**:
  - `frontend/src/services/erpMesService.ts` - apiClient 사용으로 변경
  - `frontend/src/services/ragService.ts` - apiClient 사용으로 변경
  - `frontend/src/components/data/ErpMesDataTab.tsx` - token 파라미터 제거
  - `frontend/src/components/data/RagDocumentsTab.tsx` - token 파라미터 제거
- **디버깅 팁**:
  > 401 에러 시 백엔드 로그에서 `user_id: None`이면 토큰이 전달되지 않은 것
  > 서비스에서 `apiClient` 대신 직접 `fetch()`를 사용하면 React Context 타이밍 문제 발생 가능

**[2025-12-30] RAG 문서 상세 조회 API 누락**
- **에러**: 지식 베이스에서 문서 클릭 시 내용 표시 안됨
- **발생 위치**: 프론트엔드 Data 탭 → 지식 베이스
- **증상**:
  - 문서 목록은 표시됨
  - 문서 클릭 시 상세 내용 조회 불가 (API 없음)
- **근본 원인 (RCA)**:
  - `GET /api/v1/rag/documents/{id}` 엔드포인트 미구현
  - 프론트엔드에서 호출할 API 부재
- **최종 해결책**:
  - Backend: `rag_service.get_document()` 메서드 추가
    - 모든 청크를 조회하여 텍스트 병합
    - 메타데이터 (title, source_type, chunk_count, char_count) 반환
  - Backend: `GET /api/v1/rag/documents/{document_id}` 엔드포인트 추가
  - Frontend: `ragService.getDocument()` 함수 추가
  - Frontend: 문서 상세 보기 모달 UI 추가
- **수정 파일**:
  - `backend/app/services/rag_service.py` - `get_document()` 메서드
  - `backend/app/routers/rag.py` - GET 엔드포인트
  - `frontend/src/services/ragService.ts` - API 클라이언트
  - `frontend/src/components/data/RagDocumentsTab.tsx` - 모달 UI

**[2025-12-30] A/B 실험 시작 실패 (Control 그룹 누락)**
- **에러**: `400 Bad Request` - "control 그룹이 필요합니다"
- **발생 위치**: `POST /api/v1/experiments/{id}/start`
- **증상**:
  - 실험 생성 후 시작 버튼 클릭 시 에러
  - Variants는 존재하지만 시작 불가
- **근본 원인 (RCA)**:
  - 실험 시작 시 Control variant (is_control=True) 필수
  - 생성 시 is_control 플래그 미설정
- **최종 해결책**:
  - Control variant에 `is_control: true` 설정
  ```bash
  PUT /api/v1/experiments/{id}/variants/{variant_id}
  {"is_control": true}
  ```
- **디버깅 팁**:
  > 실험 생성 후 variants 목록에서 is_control 플래그 확인
  > `GET /api/v1/experiments/{id}` 응답의 variants 필드 검사

#### 🐳 Docker/Infrastructure
- 아직 기록된 이슈 없음

#### 🔄 CI/CD
- 아직 기록된 이슈 없음

---

## 🚫 Known Anti-Patterns (반복 금지)

이 섹션에는 **2회 이상 실패한 해결책**을 기록하여 재시도를 방지합니다.

- 아직 기록된 항목 없음

#### 🎓 Learning Pipeline

**[2026-01-23] 샘플 추출 안됨 (피드백 부족)**
- **에러**: `extracted_count: 0, skipped_duplicates: 0`
- **발생 위치**: `POST /api/v1/samples/extract`
- **증상**:
  - 샘플 자동 추출 실행하지만 결과 0개
  - 스케줄러는 정상 작동
- **근본 원인 (RCA)**:
  - `feedback_logs` 테이블에 `rating >= 4` 데이터 부족
  - 또는 모든 피드백이 이미 샘플로 추출됨 (중복)
- **최종 해결책**:
  ```bash
  # 1. 피드백 확인
  GET /api/v1/feedback?rating_gte=4

  # 2. 기준 낮추기
  POST /api/v1/samples/extract
  {"min_rating": 3, "min_confidence": 0.5}

  # 3. 이미 추출된 샘플 확인
  GET /api/v1/samples?page=1&page_size=100
  ```
- **참고**: `docs/guides/LEARNING_PIPELINE_GUIDE.md` 섹션 5.1

**[2026-01-23] Rule Extraction 샘플 부족 오류**
- **에러**: `ValueError: 샘플이 부족합니다. 필요: 20, 현재: 8`
- **발생 위치**: `POST /api/v1/rule-extraction/extract`
- **근본 원인 (RCA)**:
  - 승인된 샘플(`status=approved`)이 `min_samples` 미만
  - 샘플은 있지만 승인 프로세스 누락
- **최종 해결책**:
  ```bash
  # 1. 승인된 샘플 확인
  GET /api/v1/samples?status=approved

  # 2. Pending 샘플 승인
  POST /api/v1/samples/{sample_id}/approve

  # 3. min_samples 낮추기 (임시)
  POST /api/v1/rule-extraction/extract
  {"min_samples": 10}
  ```
- **디버깅 팁**: Decision Tree 학습에는 최소 20개 샘플 권장
- **참고**: `docs/guides/LEARNING_PIPELINE_GUIDE.md` 섹션 5.2

**[2026-01-23] Decision Tree F1 Score 낮음**
- **에러**: F1 Score < 0.7 (기준 미달)
- **발생 위치**: Rule Extraction 결과
- **근본 원인 (RCA)**:
  1. `max_depth`가 너무 낮음 (Tree가 단순함)
  2. 샘플 품질이 낮음
  3. 특징(feature) 수 부족
- **최종 해결책**:
  ```bash
  # max_depth 증가
  POST /api/v1/rule-extraction/extract
  {
    "max_depth": 10,           # 5 → 10
    "min_samples_leaf": 3      # 5 → 3
  }

  # 품질 기준 상향
  POST /api/v1/rule-extraction/extract
  {
    "min_quality_score": 0.9   # 0.7 → 0.9
  }
  ```
- **참고**: `docs/guides/LEARNING_PIPELINE_GUIDE.md` 섹션 5.3

#### 🚢 Canary Deployment

**[2026-01-23] Canary 시작 실패 (이미 active 배포 존재)**
- **에러**: `400 Bad Request: 이미 active 배포가 있습니다`
- **발생 위치**: `POST /api/v1/deployments/{id}/start-canary`
- **근본 원인 (RCA)**:
  - 동일 Ruleset에 `status=active` 배포가 이미 존재
  - 하나의 Ruleset에는 1개의 active 배포만 가능
- **최종 해결책**:
  ```bash
  # 1. 기존 배포 확인
  GET /api/v1/deployments?ruleset_id={ruleset_id}&status=active

  # 2. 기존 배포 deprecate
  POST /api/v1/deployments/{old_id}/rollback

  # 3. 새 배포 시작
  POST /api/v1/deployments/{new_id}/start-canary
  ```
- **참고**: `docs/guides/CANARY_DEPLOYMENT_GUIDE.md` 트러블슈팅 섹션 1

**[2026-01-23] 트래픽 비율 변경했는데 실제 트래픽 안 바뀜**
- **증상**: `traffic_percentage: 50%`로 변경했는데 여전히 10% 사용자만 v2 사용
- **발생 위치**: `PUT /api/v1/deployments/{id}/traffic`
- **근본 원인 (RCA)**:
  - **정상 동작입니다!**
  - Sticky Session 때문에 기존 할당은 유지됨
  - 새로운 사용자/세션부터 50% 확률로 v2 할당
- **이해**:
  ```
  기존 사용자 (이미 할당됨):
    - User A (v2) → v2 유지 (Sticky)
    - User B (v1) → v1 유지 (Sticky)

  신규 사용자:
    - User C → 50% 확률로 v2 할당
    - User D → 50% 확률로 v2 할당
  ```
- **강제 재할당** (주의!):
  ```bash
  # 모든 할당 초기화 (A/B 테스트 무효화됨)
  POST /api/v1/deployments/{id}/rollback
  POST /api/v1/deployments/{id}/start-canary
  {"canary_pct": 50}
  ```
- **참고**: `docs/guides/CANARY_DEPLOYMENT_GUIDE.md` 트러블슈팅 섹션 2

**[2026-01-23] 자동 롤백 안됨 (Error Rate 10%)**
- **에러**: Error Rate 10%인데 자동 롤백이 트리거되지 않음
- **발생 위치**: Canary 모니터링
- **근본 원인 (RCA)**:
  - `canary_monitor_task` 스케줄러 작업 미실행
  - 또는 Error Rate 임계값이 10%로 설정됨 (기본 5%)
- **최종 해결책**:
  ```bash
  # 1. 스케줄러 상태 확인
  GET /api/v1/scheduler/jobs
  # → canary_monitor_task가 active인지 확인

  # 2. 스케줄러 재시작
  docker-compose restart backend

  # 3. 수동 롤백
  POST /api/v1/deployments/{id}/rollback
  {"reason": "Error Rate 10% (수동 롤백)"}
  ```
- **참고**: `docs/guides/CANARY_DEPLOYMENT_GUIDE.md` 트러블슈팅 섹션 4

**[2026-01-23] Circuit Breaker 계속 OPEN 상태**
- **증상**: Circuit Breaker가 계속 OPEN이고 HALF_OPEN으로 전환 안됨
- **발생 위치**: Canary Deployment
- **근본 원인 (RCA)**:
  - v2 규칙에 버그가 있어서 테스트 요청도 계속 실패
  - HALF_OPEN → 실패 → 다시 OPEN 순환
- **최종 해결책**:
  ```bash
  # 1. 즉시 롤백
  POST /api/v1/deployments/{id}/rollback

  # 2. v2 규칙 디버그
  POST /api/v1/rulesets/{ruleset_id}/test
  {"input": {...}}

  # 3. 규칙 수정 후 재배포
  ```
- **참고**: `docs/guides/CANARY_DEPLOYMENT_GUIDE.md` 트러블슈팅 섹션 5

#### 📊 Materialized Views

**[2026-01-23] MV 리프레시 실패 (UNIQUE INDEX 없음)**
- **에러**: `ERROR: cannot refresh materialized view concurrently without a unique index`
- **발생 위치**: MV Refresh 스케줄러
- **근본 원인 (RCA)**:
  - CONCURRENTLY 옵션은 UNIQUE INDEX 필수
  - 마이그레이션 미적용 또는 인덱스 삭제됨
- **최종 해결책**:
  ```sql
  -- 인덱스 재생성
  CREATE UNIQUE INDEX idx_mv_defect_trend_pk
  ON bi.mv_defect_trend(tenant_id, date, line_code);

  CREATE UNIQUE INDEX idx_mv_oee_daily_pk
  ON bi.mv_oee_daily(tenant_id, date, line_code);

  CREATE UNIQUE INDEX idx_mv_line_performance_pk
  ON bi.mv_line_performance(tenant_id, line_code);

  CREATE UNIQUE INDEX idx_mv_quality_summary_pk
  ON bi.mv_quality_summary(tenant_id, date);
  ```
- **참고**: `docs/guides/MV_MANAGEMENT_GUIDE.md` 트러블슈팅 섹션 1

**[2026-01-23] MV 리프레시 느림 (60초 이상)**
- **증상**: `mv_refresh_duration_seconds > 60`
- **발생 위치**: MV Refresh
- **근본 원인 (RCA)**:
  1. 원본 테이블 통계 오래됨 (VACUUM ANALYZE 필요)
  2. 원본 테이블 데이터 급증
  3. CONCURRENTLY 오버헤드
- **최종 해결책**:
  ```sql
  -- 1. VACUUM ANALYZE 실행
  VACUUM ANALYZE analytics.fact_daily_defect;
  VACUUM ANALYZE analytics.fact_daily_production;

  -- 2. 원본 테이블 인덱스 확인
  SELECT * FROM pg_indexes
  WHERE tablename IN ('fact_daily_defect', 'fact_daily_production');

  -- 3. 데이터 보관 기간 단축 (필요시)
  -- 마이그레이션 수정: 90일 → 60일
  ```
- **참고**: `docs/guides/MV_MANAGEMENT_GUIDE.md` 트러블슈팅 섹션 2

**[2026-01-23] 대시보드에 최신 데이터 안 보임**
- **증상**: 5분 전에 발생한 불량이 대시보드에 표시 안됨
- **발생 위치**: Dashboard 페이지
- **근본 원인 (RCA)**:
  - **정상 동작입니다!**
  - MV는 30분마다 리프레시됨
  - 최신 데이터는 다음 리프레시까지 대기
- **해결 옵션**:
  ```bash
  # 옵션 1: 수동 리프레시 (즉시)
  REFRESH MATERIALIZED VIEW CONCURRENTLY bi.mv_defect_trend;

  # 옵션 2: 주기 단축 (15분)
  # scheduler_service.py 수정 필요

  # 옵션 3: 실시간 쿼리 (MV 우회)
  SELECT * FROM analytics.fact_daily_defect
  WHERE date = CURRENT_DATE;
  ```
- **참고**: `docs/guides/MV_MANAGEMENT_GUIDE.md` 트러블슈팅 섹션 3

---

## 🚫 Known Anti-Patterns (반복 금지)

이 섹션에는 **2회 이상 실패한 해결책**을 기록하여 재시도를 방지합니다.

### Learning Pipeline
- ❌ **샘플 부족 시 min_samples를 5 미만으로 낮추기** → Decision Tree가 과적합됨
- ❌ **F1 Score 낮을 때 max_depth를 20 이상으로 늘리기** → 과적합, 일반화 불가

### Canary Deployment
- ❌ **Circuit Breaker OPEN 상태에서 재시도** → 계속 OPEN 유지
- ❌ **Sticky Session 무시하고 강제 재할당** → A/B 테스트 무효화

### Materialized Views
- ❌ **CONCURRENTLY 없이 REFRESH** → 읽기 차단, 사용자 경험 저하
- ❌ **리프레시 주기를 5분 이하로 단축** → DB CPU 과부하

---

## 📝 Notes

- 에러 수정 전에 반드시 이 파일을 먼저 확인할 것
- 동일 에러가 2회 실패 시 즉시 작업 중단 후 사용자에게 보고
- 성공한 해결책은 "Common Issues & Solutions" 섹션에 정리
- Learning Pipeline, Canary, MV 관련 상세 가이드는 각 전용 문서 참조
