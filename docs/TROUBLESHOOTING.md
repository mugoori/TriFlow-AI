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

#### 🐳 Docker/Infrastructure
- 아직 기록된 이슈 없음

#### 🔄 CI/CD
- 아직 기록된 이슈 없음

---

## 🚫 Known Anti-Patterns (반복 금지)

이 섹션에는 **2회 이상 실패한 해결책**을 기록하여 재시도를 방지합니다.

- 아직 기록된 항목 없음

---

## 📝 Notes

- 에러 수정 전에 반드시 이 파일을 먼저 확인할 것
- 동일 에러가 2회 실패 시 즉시 작업 중단 후 사용자에게 보고
- 성공한 해결책은 "Common Issues & Solutions" 섹션에 정리
