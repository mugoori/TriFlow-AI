# TriFlow AI - 작업 목록 (TASKS)

> **최종 업데이트**: 2025-12-01
> **현재 Phase**: MVP v0.1.0 릴리즈 완료 → V1 개발 시작
> **현재 브랜치**: `develop` (V1 개발용)

---

## 📊 TriFlow AI Project Dashboard

### 📅 Product Roadmap
| Milestone | Goal | Status | Progress | 완료/전체 |
| :--- | :--- | :--- | :--- | :--- |
| **MVP** | **PC 설치형 데스크톱 앱** (Core + Chat UI) | ✅ v0.1.0 릴리즈 | ██████████ 100% | 18/18 |
| **V1** | Builder UI & Learning Pipeline | 🚧 개발 중 | ███████░░░ 71% | 10/14 |
| **V2** | Mobile App & Advanced Simulation | ⏳ Pending | ░░░░░░░░░░ 0% | 0/6 |

### 🚀 MVP Detailed Progress (Sprint 1~6)

#### 📋 Phase 0: 프로젝트 기획 및 문서화
| Task | Status | Progress |
| :--- | :--- | :--- |
| 프로젝트 문서 (A-1 ~ D-4) 작성 | ✅ 완료 | ██████████ 100% |
| AI_GUIDELINES.md 작성 | ✅ 완료 | ██████████ 100% |
| TASKS.md 작성 | ✅ 완료 | ██████████ 100% |
| README.md 작성 | ✅ 완료 | ██████████ 100% |
| Git 저장소 초기화 | ✅ 완료 | ██████████ 100% |

#### 🔙 Backend (Python/FastAPI)
| Sprint | Task | Status | Progress |
| :--- | :--- | :--- | :--- |
| **Sprint 1** | **[Infra]** Docker Compose (Postgres, Redis, MinIO) | ✅ 완료 | ██████████ 100% |
| | **[DB]** Init Schemas (Core, BI, RAG, Audit) | ✅ 완료 | ██████████ 100% |
| | **[Core]** `tools/rhai.py` (Rust Binding) 구현 | ✅ 완료 | ██████████ 100% |
| | **[Core]** `tools/db.py` (Safe Query) 구현 | ✅ 완료 | ██████████ 100% |
| | **[CI/CD]** GitHub Actions 워크플로우 설정 | ✅ 완료 | ██████████ 100% |
| | **[Docker]** backend/Dockerfile 생성 | ✅ 완료 | ██████████ 100% |
| **Sprint 2** | **[Agent]** Meta Router & Judgment Agent 구현 | ✅ 완료 | ██████████ 100% |
| | **[Agent]** Workflow Planner (NL->DSL) 구현 | ✅ 완료 | ██████████ 100% |
| | **[Agent]** BI Planner (Text-to-SQL) 구현 | ✅ 완료 | ██████████ 100% |
| **Sprint 4** | **[Learning]** Feedback Loop & Zwave Sim Tool | ✅ 완료 | ██████████ 100% |
| **Sprint 5** | **[Security]** Auth & PII Masking Middleware | ✅ 완료 | ██████████ 100% |

#### 🎨 Frontend (Tauri/React)
| Sprint | Task | Status | Progress |
| :--- | :--- | :--- | :--- |
| **Sprint 1** | **[Setup]** Tauri v2 + React + Vite Init | ✅ 완료 | ██████████ 100% |
| | **[Setup]** Tailwind + Shadcn/ui Config | ✅ 완료 | ██████████ 100% |
| **Sprint 3** | **[UI]** Chat-Centric Interface Layout | ✅ 완료 | ██████████ 100% |
| | **[UI]** Dashboard & Chart Visualization | ✅ 완료 | ██████████ 100% |
| **Sprint 6** | **[Release]** UAT & Production Build | ✅ 완료 | ██████████ 100% |

---

## 🏷️ MVP v0.1.0 릴리즈 (2025-11-28)

### 릴리즈 정보
- **태그**: `v0.1.0`
- **브랜치**: `main` (안정 버전), `develop` (V1 개발)
- **빌드**: Windows MSI/NSIS, Docker Image (ghcr.io)

### 주요 기능
- 5개 AI 에이전트 (Meta Router, Judgment, Workflow Planner, BI Planner, Learning)
- Chat-Centric UI (Tauri v2 + React)
- Dashboard & Chart Visualization (Recharts)
- Workflows/Data/Settings 페이지
- JWT 인증 + PII 마스킹

---

## 📋 V1 개발 작업 목록

### 🔧 V1 Sprint 1: Builder UI & Workflow Execution ✅
| Task | Status | Progress |
| :--- | :--- | :--- |
| **[UI]** Workflow Visual Editor (Drag & Drop) | ✅ 완료 | ██████████ 100% |
| **[UI]** Ruleset Editor (Rhai Script 편집기) | ✅ 완료 | ██████████ 100% |
| **[UI]** Action Catalog 관리 UI | ✅ 완료 | ██████████ 100% |
| **[i18n]** Action Catalog 한글화 | ✅ 완료 | ██████████ 100% |
| **[Engine]** Workflow Execution Pipeline | ✅ 완료 | ██████████ 100% |
| **[Engine]** Sensor Data Simulator | ✅ 완료 | ██████████ 100% |
| **[UI]** Simulation Test Panel | ✅ 완료 | ██████████ 100% |
| **[UI]** Execution Log Panel | ✅ 완료 | ██████████ 100% |

#### 📋 V1 Sprint 1 완료 작업 내역 (2025-11-28)
- [x] **[UI]** ActionDetailModal 컴포넌트 구현 (`frontend/src/components/workflow/ActionDetailModal.tsx`)
  - 액션 상세 정보 표시 (이름, 설명, 카테고리)
  - 파라미터 목록 및 타입 정보
  - DSL 예시 생성 및 복사 기능
  - 카테고리별 아이콘/색상 매핑
- [x] **[UI]** WorkflowsPage 액션 카탈로그 개선 (`frontend/src/components/pages/WorkflowsPage.tsx`)
  - 카테고리 필터링 (알림, 데이터, 제어, 분석)
  - 액션 카드 클릭 시 상세 모달
  - 개선된 UI (카테고리별 색상, 아이콘, 파라미터 수 표시)
  - 필터 초기화 기능
- [x] **[UI]** WorkflowEditor 컴포넌트 구현 (`frontend/src/components/workflow/WorkflowEditor.tsx`)
  - 워크플로우 이름/설명 편집
  - 트리거 타입 선택 (수동, 이벤트, 스케줄)
  - 조건/액션 노드 추가/삭제/이동
  - 노드 설정 (조건식, 액션 선택, 파라미터 JSON)
  - DSL 실시간 미리보기
  - WorkflowsPage와 통합 (새 워크플로우 버튼)
- [x] **[Engine]** Workflow Execution Pipeline 구현 (`backend/app/services/workflow_engine.py`)
  - `SensorSimulator`: 시나리오별 센서 데이터 생성 (normal, alert, random, preset)
  - `ConditionEvaluator`: 조건식 평가 (>, <, >=, <=, ==, !=, &&, ||)
  - `ActionExecutor`: 비알림 액션 실행 (log_event, save_to_database 등)
  - `WorkflowEngine`: 전체 워크플로우 오케스트레이션
  - `ExecutionLogStore`: 인메모리 실행 로그 저장소
- [x] **[API]** Workflow Execution APIs 확장 (`backend/app/routers/workflows.py`)
  - `POST /simulator/generate` - 센서 시뮬레이션 데이터 생성
  - `GET /logs/execution` - 실행 로그 조회
  - `DELETE /logs/execution` - 실행 로그 초기화
  - `POST /test/condition` - 조건식 테스트
  - `POST /{workflow_id}/run` - 시뮬레이션 옵션 지원
- [x] **[Service]** Frontend Workflow Service 확장 (`frontend/src/services/workflowService.ts`)
  - WorkflowRunOptions, SimulatorResponse, ConditionTestResponse, ExecutionLog 타입
  - generateSimulatedData(), testCondition(), getExecutionLogs(), clearExecutionLogs()
- [x] **[UI]** Simulation Test Panel 구현 (`frontend/src/components/pages/WorkflowsPage.tsx`)
  - 시나리오 선택 (normal, alert, random)
  - 시뮬레이션 데이터 생성 및 표시
  - 워크플로우 실행 버튼 (시뮬레이션 모드)
- [x] **[UI]** Execution Log Panel 구현
  - 실행 로그 실시간 표시
  - 로그 초기화 기능
  - 이벤트 타입/시간/상세정보 표시
- [x] **[UI]** Ruleset Editor 구현 (`frontend/src/components/ruleset/`)
  - `RulesetsPage.tsx` - 룰셋 목록/상세 페이지
    - 검색 및 활성 상태 필터
    - 룰셋 CRUD (생성, 편집, 삭제)
    - 빠른 테스트 실행 패널
  - `RulesetEditorModal.tsx` - Monaco Editor 기반 Rhai 편집기
    - 커스텀 Rhai 구문 하이라이팅 (Monarch Tokenizer)
    - 자동완성 (키워드, input 속성)
    - 샘플 스크립트 선택 드롭다운
    - 테스트 실행 및 결과 표시
  - `rulesetService.ts` - Ruleset API 클라이언트
- [x] **[i18n]** Action Catalog 한글화
  - display_name, category_display_name 필드 추가
  - 12개 액션 한글 이름 적용
  - 4개 카테고리 한글 표시

### 🧠 V1 Sprint 2: Learning Pipeline 강화
| Task | Status | Progress |
| :--- | :--- | :--- |
| **[Learning]** 채팅으로 룰셋 생성 기능 | ✅ 완료 | ██████████ 100% |
| **[Learning]** 피드백 수집 UI | ✅ 완료 | ██████████ 100% |
| **[Learning]** 규칙 자동 제안 개선 | ⏳ Pending | ░░░░░░░░░░ 0% |
| **[Learning]** A/B 테스트 프레임워크 | ⏳ Pending | ░░░░░░░░░░ 0% |

#### 📋 V1 Sprint 2 완료 작업 내역 (2025-12-01)
- [x] **[UI]** 피드백 수집 UI 구현
  - Backend: `backend/app/routers/feedback.py` - 피드백 CRUD API
    - POST / - 피드백 생성 (positive, negative, correction)
    - GET / - 피드백 목록 조회 (필터링, 페이지네이션)
    - GET /stats - 피드백 통계
    - GET /{id} - 피드백 상세
    - PATCH /{id}/process - 처리됨 마킹
    - DELETE /{id} - 삭제
  - Frontend: `frontend/src/services/feedbackService.ts` - API 클라이언트
  - Frontend: `frontend/src/components/FeedbackModal.tsx` - 상세 피드백 모달
    - 피드백 유형 선택 (개선 필요/수정 제안)
    - 6가지 이유 선택 (틀림, 부족, 관련없음, 이해어려움, 느림, 기타)
    - 상세 내용 입력
    - 수정 제안 시 원하는 답변 입력
  - Frontend: ChatMessage에 피드백 버튼 추가
    - 👍/👎 빠른 피드백
    - 💬 상세 피드백 모달 열기
- [x] **[Agent]** LearningAgent에 `create_ruleset` 도구 추가
  - 자연어 요청을 Rhai 스크립트로 자동 변환
  - DB 저장 (Ruleset 모델 사용)
  - 센서 타입: temperature, pressure, humidity, vibration, flow_rate, defect_rate
  - 액션 타입: notification, stop_line, log, maintenance
- [x] **[Router]** MetaRouter 프롬프트 업데이트
  - "룰셋", "규칙 만들어", "판단 규칙", "~면 경고", "~면 위험" 키워드 → learning 라우팅
- [x] **[API]** agents.py에 tool_choice 조건부 설정
  - 룰셋 생성 요청 감지 시 `create_ruleset` 도구 강제 호출
- [x] **[UX]** 에이전트 응답 형식 간결화 (Chat-Optimized)
  - LearningAgent, WorkflowPlannerAgent, BIPlannerAgent 프롬프트 업데이트
  - UUID/코드 전문 출력 금지
  - 테이블 1개 + 다음 단계 액션 형식으로 통일
- [x] **[Bug Fix]** Workflow 저장 안되는 버그 수정
  - 원인: SQLAlchemy JSONB 필드 mutation detection 실패
  - 해결: `copy.deepcopy()` + `flag_modified()` 적용
  - 파일: `backend/app/routers/workflows.py`
- [x] **[DX]** 백엔드 서버 관리 스크립트 추가
  - `backend/start_server.bat` - 기존 프로세스 종료 + 서버 시작
  - `scripts/kill_port.bat` - 포트 점유 프로세스 종료 유틸리티
  - 다중 서버 인스턴스 문제 방지
- [x] **[Docs]** AI_GUIDELINES.md Verification Protocol 추가
  - Rule 2에 "3. Verification Protocol (Mandatory)" 섹션 추가
  - Backend: pytest 명령어 제시 필수
  - Frontend: UI 동작 시나리오 명시 필수
  - Infra/DB: Health Check 명령어 제시 필수

### 🔌 V1 Sprint 3: 외부 시스템 연동 ✅
| Task | Status | Progress |
| :--- | :--- | :--- |
| **[Integration]** Slack 알림 실제 연동 | ✅ 완료 | ██████████ 100% |
| **[Integration]** Email 알림 연동 (SMTP) | ✅ 완료 | ██████████ 100% |

#### 📋 V1 Sprint 3 완료 작업 내역 (2025-11-28)
- [x] **[Service]** Notification Service 구현 (`backend/app/services/notifications.py`)
  - `SlackNotificationService` - Slack Webhook 알림 (httpx async)
  - `EmailNotificationService` - SMTP 이메일 (smtplib)
  - `SMSNotificationService` - SMS 알림 플레이스홀더 (V2 예정)
  - `NotificationManager` - 알림 통합 관리자
  - 환경변수 기반 설정 (graceful degradation)
- [x] **[API]** Notifications Router 구현 (`backend/app/routers/notifications.py`)
  - `GET /api/v1/notifications/status` - 알림 서비스 상태 조회
  - `POST /api/v1/notifications/test/slack` - Slack 테스트
  - `POST /api/v1/notifications/test/email` - Email 테스트
  - `POST /api/v1/notifications/send` - 범용 알림 전송
- [x] **[Workflow]** 워크플로우 실행기 통합 (`backend/app/routers/workflows.py`)
  - DSL 노드 순차 실행
  - 알림 액션 자동 실행 (send_slack_notification, send_email, send_sms)
  - 실행 결과 상세 로깅
- [x] **[Config]** 환경변수 업데이트 (`.env.example`)
  - Slack: SLACK_WEBHOOK_URL, SLACK_DEFAULT_CHANNEL
  - Email: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_USE_TLS

---

## 📋 MVP 완료 작업 (Archive)

### Sprint 6: Production Build & Release ✅ (2025-11-27)
- [x] Tauri v2 앱 메타데이터 설정
  - productName: "TriFlow AI"
  - identifier: "com.triflow.ai"
  - 윈도우 설정: 1280x800 (min 800x600), 중앙 배치
  - 번들 정보: Productivity 카테고리, 설명, 저작권
- [x] Rust 설정 업데이트 (Cargo.toml)
  - name: "triflow-ai"
  - lib name: "triflow_ai_lib"
  - MIT 라이선스, GitHub 저장소 링크
- [x] tauri-plugin-shell 설치 및 설정
  - shell:allow-open, shell:allow-execute 권한 추가
  - Docker 명령 실행을 위한 준비
- [x] TypeScript 빌드 오류 수정
  - shadcn/ui Alert, Table 컴포넌트 추가
  - PieChartComponent 라벨 타입 수정
  - ChartRenderer JSX namespace 수정
- [x] Production 빌드 성공
  - **MSI**: `TriFlow AI_0.1.0_x64_en-US.msi`
  - **NSIS**: `TriFlow AI_0.1.0_x64-setup.exe`
  - 빌드 위치: `frontend/src-tauri/target/release/bundle/`

### 샘플 센서 데이터 생성 ✅ (2025-11-27)
- [x] SQL 스크립트 작성 (`backend/db/init/99_insert_sample_sensor_data.sql`)
  - 최근 7일간 센서 데이터 (1시간 간격)
  - 4개 라인 (LINE_A~D) × 5개 센서 타입 × 168시간 = 3,360건
  - 센서 타입: temperature, pressure, humidity, vibration, flow_rate
- [x] DB INSERT 완료 및 API 테스트 성공
  - `/api/v1/sensors/data` - 480건 조회 (최근 24시간)
  - `/api/v1/sensors/summary` - 라인별 평균값 정상 계산

### Backend DB 실제 연결 ✅ (2025-11-27)
- [x] Sensors API: Mock 데이터 → PostgreSQL DB 쿼리로 전환
  - `GET /api/v1/sensors/data` - SensorData 모델 쿼리
  - `GET /api/v1/sensors/filters` - DISTINCT 값 조회 (DB 데이터 없으면 기본값)
  - `GET /api/v1/sensors/summary` - 집계 쿼리 (line_code별 평균, 카운트)
- [x] Workflows API: Mock 데이터 → PostgreSQL DB 쿼리로 전환
  - CRUD 엔드포인트 전체 DB 연동
  - WorkflowInstance 실행 이력 DB 저장
  - Default Tenant 자동 생성 (MVP)
- [x] ORM 모델 DB 컬럼명 매핑 수정
  - Workflow.dsl_definition → DB: dsl_json
  - Ruleset.rhai_script → DB: rhai_code
- [x] main.py 라우터 등록 에러 핸들링 추가 (try-except)
- [x] API 테스트 완료 (sensors/filters, workflows 정상 동작)

### Settings 페이지 구현 ✅ (2025-11-27)
- [x] SettingsPage 컴포넌트 전면 개편 (`frontend/src/components/pages/SettingsPage.tsx`)
  - 일반 설정: 테마 (시스템/라이트/다크), 언어, 알림 토글
  - Backend 연결: 연결 상태 표시, API URL 설정, 연결 테스트, 자동 재연결
  - AI 모델: 모델 선택 (Claude Sonnet 4.5/3.5/Haiku), Max Tokens, Tenant ID
  - 앱 정보: 버전 (0.1.0), 빌드 (2025.11.27), 라이선스, GitHub 링크
- [x] 테마 적용 기능 구현 (dark mode 지원)
- [x] localStorage 설정 저장/불러오기
- [x] 2x2 그리드 레이아웃 (반응형)

### WBS 로드맵 다이어그램 추가 ✅ (2025-11-27)
- [x] V1/V2 로드맵 SVG 다이어그램 생성 (`docs/diagrams/`)
  - `wbs_v1_roadmap.svg` - V1 로드맵 (Builder UI, Learning Pipeline, 외부 연동, 보안 강화)
    - 예상 기간: 약 16주 (3~4개월)
    - 탭 구조: MVP와 동일 (5개 탭 유지)
  - `wbs_v2_roadmap.svg` - V2 로드맵 (Mobile App, Simulation, Multi-Tenant, 고급 AI)
    - 예상 기간: 약 34주 (6개월+)
    - 탭 구조: +2개 추가 예정 (Simulation, Admin)

### UI 다이어그램 추가 ✅ (2025-11-27)
- [x] 탭별 UI SVG 다이어그램 추가 (`docs/diagrams/`)
  - `ui_05_dashboard.svg` - Dashboard 페이지 (Stats Grid, 고정된 차트, 최근 활동)
  - `ui_06_data_page.svg` - Data 페이지 (필터, 센서 데이터 테이블, 페이지네이션)
  - `ui_07_settings_page.svg` - Settings 페이지 (일반 설정, Backend 연결, AI 모델, 앱 정보)

### Workflows 페이지 구현 ✅ (2025-11-27)
- [x] Backend: 워크플로우 API 라우터 구현 (`backend/app/routers/workflows.py`)
  - `GET /api/v1/workflows` - 워크플로우 목록 조회 (검색, 활성 상태 필터)
  - `GET /api/v1/workflows/{id}` - 워크플로우 상세 조회
  - `POST /api/v1/workflows` - 워크플로우 생성
  - `PATCH /api/v1/workflows/{id}` - 워크플로우 수정
  - `DELETE /api/v1/workflows/{id}` - 워크플로우 삭제
  - `POST /api/v1/workflows/{id}/run` - 워크플로우 실행
  - `GET /api/v1/workflows/{id}/instances` - 실행 이력 조회
  - `GET /api/v1/workflows/actions` - 액션 카탈로그 조회
  - Mock 데이터: 3개 샘플 워크플로우 (불량률 경고, 온도 긴급 대응, 정기 점검)
- [x] Frontend: 워크플로우 서비스 구현 (`frontend/src/services/workflowService.ts`)
- [x] Frontend: WorkflowsPage 컴포넌트 구현 (`frontend/src/components/pages/WorkflowsPage.tsx`)
  - 워크플로우 목록 테이블 (이름, 트리거, 상태, 버전, 수정일)
  - 검색 및 활성 상태 필터
  - 워크플로우 실행/활성화/삭제 기능
  - 워크플로우 상세: DSL 노드 시각화, 실행 이력
  - 액션 카탈로그 뷰 (12개 액션, 4개 카테고리)
- [x] App.tsx 라우팅 연결 (PlaceholderPage → WorkflowsPage)

### Data 페이지 구현 ✅ (2025-11-27)
- [x] Backend: 센서 데이터 API 라우터 구현 (`backend/app/routers/sensors.py`)
  - `GET /api/v1/sensors/data` - 센서 데이터 조회 (페이지네이션, 필터링)
  - `GET /api/v1/sensors/filters` - 필터 옵션 (라인, 센서 타입)
  - `GET /api/v1/sensors/summary` - 요약 통계
  - Mock 데이터 생성 (LINE_A~D, 5가지 센서 타입)
- [x] Frontend: 센서 데이터 서비스 구현 (`frontend/src/services/sensorService.ts`)
- [x] Frontend: DataPage 컴포넌트 구현 (`frontend/src/components/pages/DataPage.tsx`)
  - 테이블 뷰 (센서 ID, 기록 시간, 라인, 센서 타입, 값)
  - 필터링 (날짜 범위, 생산 라인, 센서 타입)
  - 페이지네이션 (20건씩)
  - CSV 다운로드 기능
  - 새로고침 버튼
- [x] App.tsx 라우팅 연결 (PlaceholderPage → DataPage)
- [x] BaseChartConfig에 title 속성 추가 (기존 타입 오류 수정)

### UI 개선 및 Dashboard 기능 강화 ✅ (2025-11-27)
- [x] Sidebar Navigation 구현
  - Chat, Dashboard, Workflows, Data, Settings 탭
  - TriFlow AI 로고 및 브랜딩
  - Backend 연결 상태 표시
- [x] Dashboard 차트 고정 기능 (Option A)
  - DashboardContext: 차트 상태 관리
  - ChatMessage: "대시보드에 고정" 버튼
  - DashboardPage: 고정된 차트 목록 & 삭제 기능
  - 스크롤 지원
- [x] Tool 호출 정보 UX 개선
  - 기본: 간략한 근거 표시 (classify_intent reason)
  - "상세 정보" 토글로 Tool 호출 JSON 확인
- [x] BI Agent 차트 생성 개선
  - 데이터 없을 때 데모 차트 생성 강제
  - Frontend extractChartConfig: { success, config } 구조 지원
- [x] Tauri 아이콘 교체
  - TriFlow 커스텀 아이콘으로 전체 교체
  - 128x128 고해상도 로고

### Dashboard & Chart Visualization 구현 ✅ (2025-11-27)
- [x] Recharts 라이브러리 설치 (v2.x, 178 packages)
- [x] Chart 타입 시스템 구현 (chart.ts)
  - TypeScript Discriminated Union: ChartType = 'line' | 'bar' | 'pie' | 'area' | 'scatter' | 'table'
  - 타입별 Config 인터페이스: LineChartConfig, BarChartConfig, PieChartConfig, etc.
  - CHART_COLORS 팔레트 (8색) 및 DEFAULT_CHART_STYLE 정의
- [x] Chart 컴포넌트 6종 구현
  - ✅ LineChartComponent.tsx - 시계열 데이터 시각화
  - ✅ BarChartComponent.tsx - 카테고리 비교 차트
  - ✅ PieChartComponent.tsx - 비율 데이터 시각화
  - ✅ AreaChartComponent.tsx - 누적 추이 분석
  - ✅ ScatterChartComponent.tsx - 상관관계 분석
  - ✅ TableComponent.tsx - 데이터 테이블 (shadcn/ui)
- [x] ChartRenderer 구현
  - Config 타입 기반 동적 컴포넌트 렌더링
  - 에러 핸들링 및 유효성 검증
  - Alert 컴포넌트를 통한 사용자 피드백
- [x] Chat UI 통합
  - ChatMessage.tsx에 extractChartConfig 함수 추가
  - BI Agent의 generate_chart_config tool_call 결과 자동 감지
  - 차트 포함 메시지는 max-width 95% (일반 메시지는 80%)
- [x] 테스트 준비 완료
  - 프론트엔드 서버 실행 중 (HMR 정상 동작)
  - BI Agent와의 E2E 테스트 준비 완료

### BI Planner Agent 구현 ✅ (2025-11-27)
- [x] BI Planner Agent 프롬프트 작성 (bi_planner.md)
- [x] BI Planner Agent 클래스 구현 (bi_planner.py)
  - 3개 Tools: get_table_schema, execute_safe_sql, generate_chart_config
  - 보안: tenant_id 필수 필터링, SELECT-only SQL
  - 차트 타입: line, bar, pie, area, scatter, table
- [x] API 엔드포인트 통합 (agents.py)
- [x] 테스트 완료 (3개 시나리오)
  - ✅ sensor_data 테이블 스키마 조회 (General Agent로 라우팅)
  - ✅ 최근 센서 데이터 라인 차트 시각화 (BI Agent 정상 동작, tenant_id 보안 확인)
  - ✅ 라인별 평균 온도 Bar 차트 생성 (BI Agent 정상 동작, tenant_id 보안 확인)
- [x] 보안 기능 검증: tenant_id 필터 없는 SQL 자동 거부 ✅

### Workflow Planner Agent 구현 ✅ (2025-11-27)
- [x] Workflow Planner Agent 프롬프트 작성 (workflow_planner.md)
- [x] Action Catalog 시스템 구현 (12개 액션)
  - notification: send_slack_notification, send_email, send_sms
  - data: save_to_database, export_to_csv, log_event
  - control: stop_production_line, adjust_sensor_threshold, trigger_maintenance
  - analysis: calculate_defect_rate, analyze_sensor_trend, predict_equipment_failure
- [x] Workflow DSL 생성 로직 구현 (MVP: Template-based)
- [x] Schema 검증 기능 구현 (validate_node_schema)
- [x] API 엔드포인트 통합 (agents.py)
- [x] 테스트 완료 (3개 시나리오)
  - ✅ 불량률 5% 초과 시 Slack 알림 워크플로우
  - ✅ 온도 80°C 초과 시 생산 라인 중지 + 이메일 알림
  - ✅ 장비 고장 예측 기반 유지보수 자동화

### Chat UI 통합 테스트 ✅ (2025-11-27)
- [x] Backend 서버 상태 확인 (http://127.0.0.1:8000)
- [x] Frontend 개발 서버 실행 (http://localhost:1420)
- [x] agentService.ts import 오류 수정
  - 문제: `import { api }` → 실제 export는 `apiClient`
  - 해결: import 구문 수정 및 API 호출 패턴 변경
- [x] CORS 설정 문제 해결
  - 문제: `http://localhost:1420`이 CORS origins에 없음
  - 해결: `backend/.env` 파일 생성 및 CORS_ORIGINS 업데이트
  - 추가 문제: 환경변수가 .env 파일을 오버라이드
  - 최종 해결: 환경변수 unset 후 서버 재시작
- [x] Chat UI 기본 기능 테스트
  - ✅ 메시지 입력 및 전송
  - ✅ Agent 응답 수신 (MetaRouterAgent)
  - ✅ Tool 호출 시각화 (classify_intent, extract_slots, route_request)
  - ✅ JSON 포맷 렌더링
  - ✅ 타임스탬프 표시
  - ✅ 한글 메시지 처리

### CI/CD Optimization ✅
- [x] AI_GUIDELINES.md에 Rule 2.2 추가 (CI Optimization - Concurrency)
- [x] 모든 GitHub Actions 워크플로우에 Concurrency 설정 적용
  - [x] backend-ci.yml
  - [x] frontend-ci.yml
  - [x] docker-build.yml

### Sprint 3: Chat UI 구현 ✅
- [x] TypeScript 타입 정의 (`frontend/src/types/agent.ts`)
  - [x] ToolCall, AgentResponse, ChatMessage, AgentRequest 인터페이스
- [x] Agent API 서비스 (`frontend/src/services/agentService.ts`)
  - [x] chat() 메서드 - `/api/v1/agents/chat` 호출
  - [x] status() 메서드 - `/api/v1/agents/status` 호출
- [x] 채팅 메시지 컴포넌트 (`frontend/src/components/ChatMessage.tsx`)
  - [x] User/Assistant 메시지 구분
  - [x] Tool 호출 시각화 (JSON 포맷)
  - [x] 타임스탬프 표시
- [x] 메시지 입력 컴포넌트 (`frontend/src/components/ChatInput.tsx`)
  - [x] Textarea + Send 버튼
  - [x] Enter 키로 전송 (Shift+Enter로 줄바꿈)
  - [x] Disabled 상태 처리
- [x] 채팅 컨테이너 (`frontend/src/components/ChatContainer.tsx`)
  - [x] 메시지 히스토리 관리
  - [x] Auto-scroll 기능
  - [x] Loading 애니메이션
  - [x] 에러 처리
- [x] App.tsx 통합
  - [x] Chat/Tenants 뷰 전환 토글 버튼
  - [x] Full-screen flex 레이아웃

### Sprint 2: 에이전트 시스템 구현 ✅
- [x] Base Agent 클래스 구현 (Anthropic Tool Calling Pattern)
- [x] Meta Router Agent 구현 (Intent 분류 및 라우팅)
- [x] Judgment Agent 구현 (센서 데이터 분석 + Rhai 엔진)
- [x] Agent API 엔드포인트 구현 (`/api/v1/agents/chat`, `/api/v1/agents/judgment`, `/api/v1/agents/status`)
- [x] Agent 프롬프트 작성 (meta_router.md, judgment_agent.md)
- [x] Tools 모듈 구조화 (`backend/app/tools/`)
- [x] Docker Build CI 수정 (backend/Dockerfile 생성)

---

## 🗓️ Sprint 1: 인프라 및 기본 설정

### 🔧 Backend 인프라
- [x] **[Infra]** Docker Compose 설정 ✅
  - [x] PostgreSQL 14+ (pgvector 확장 포함) 컨테이너 설정
  - [x] Redis 7.2 컨테이너 설정
  - [x] MinIO (오브젝트 스토리지) 컨테이너 설정
  - [x] 네트워크 및 볼륨 구성

- [x] **[DB]** 데이터베이스 스키마 초기화 ✅
  - [x] Core 스키마 (rules, workflows, sensors)
  - [x] BI 스키마 (reports, dashboards)
  - [x] RAG 스키마 (documents, embeddings)
  - [x] Audit 스키마 (logs, feedback)

- [x] **[Core]** 핵심 도구 구현 ✅
  - [x] `tools/rhai.py` - Rhai 룰 엔진 Python 바인딩
  - [x] `tools/db.py` - 안전한 SQL 쿼리 실행기

- [x] **[CI/CD]** GitHub Actions 워크플로우 ✅
  - [x] Lint & Test 워크플로우 (Python: ruff, pytest)
  - [x] Lint & Test 워크플로우 (Frontend: eslint, vitest)
  - [x] Docker 이미지 빌드 및 푸시

### 🎨 Frontend 초기 설정
- [x] **[Setup]** Tauri v2 + React + Vite 프로젝트 초기화 ✅
- [x] **[Setup]** Tailwind CSS 설정 ✅
- [x] **[Setup]** Shadcn/ui 컴포넌트 라이브러리 설정 ✅

---

## 🗓️ Sprint 2: 에이전트 시스템 구현

### 🤖 AI 에이전트
- [x] **[Agent]** Base Agent 클래스 구현 ✅
  - [x] Anthropic Tool Calling Pattern 적용
  - [x] Tool 실행 루프 (최대 5회 반복)
  - [x] 시스템 프롬프트 로딩 (Markdown 파일)

- [x] **[Agent]** Meta Router Agent 구현 ✅
  - [x] 의도 분류 (classify_intent)
  - [x] 슬롯 추출 (extract_slots)
  - [x] 요청 라우팅 (route_request)

- [x] **[Agent]** Judgment Agent 구현 ✅
  - [x] Rhai 룰 엔진 실행 (run_rhai_engine)
  - [x] RAG 지식 조회 (query_rag_knowledge) - MVP Placeholder
  - [x] 센서 히스토리 조회 (fetch_sensor_history)

- [x] **[Agent]** Workflow Planner Agent 구현 ✅
  - [x] 워크플로우 DSL 생성 (generate_workflow_dsl)
  - [x] 노드 스키마 검증 (validate_node_schema)
  - [x] 액션 카탈로그 검색 (search_action_catalog)

- [x] **[Agent]** BI Planner Agent 구현 ✅
  - [x] 테이블 스키마 조회 (get_table_schema)
  - [x] 안전한 SQL 실행 (execute_safe_sql)
  - [x] 차트 설정 생성 (generate_chart_config)

### 🔌 API 엔드포인트
- [x] **[API]** Agent 라우터 구현 ✅
  - [x] `POST /api/v1/agents/chat` - Meta Router를 통한 채팅
  - [x] `POST /api/v1/agents/judgment` - Judgment Agent 직접 실행
  - [x] `GET /api/v1/agents/status` - Agent 시스템 상태 확인

### 📝 프롬프트 작성
- [x] **[Prompts]** Agent 시스템 프롬프트 ✅
  - [x] `meta_router.md` - Meta Router 역할 정의
  - [x] `judgment_agent.md` - Judgment Agent 역할 정의

### 🛠️ 도구 모듈
- [x] **[Tools]** 도구 모듈 재구성 ✅
  - [x] `backend/tools` → `backend/app/tools` 이동
  - [x] 모듈 구조 수정 및 import 경로 업데이트

---

## 🗓️ Sprint 3: UI 구현

### 💬 Chat-Centric Interface
- [x] **[UI]** 채팅 인터페이스 레이아웃 ✅
  - [x] 메시지 입력 컴포넌트 (ChatInput.tsx)
  - [x] 메시지 목록 컴포넌트 (ChatContainer.tsx)
  - [x] 에이전트 응답 렌더링 (ChatMessage.tsx)
  - [x] Agent API 연동 (agentService.ts)
  - [x] TypeScript 타입 정의 (agent.ts)
  - [x] Tool 호출 시각화 (JSON 포맷)
  - [x] Auto-scroll & Loading State
  - [x] App.tsx 통합 (Chat/Tenants 뷰 전환)

### 📊 Dashboard & Visualization
- [x] **[UI]** 대시보드 레이아웃 ✅
- [x] **[UI]** 차트 시각화 컴포넌트 (Recharts/Chart.js) ✅
- [x] **[UI]** 실시간 데이터 표시 ✅

---

## 🗓️ Sprint 4: 학습 파이프라인 ✅

### 🧠 Learning System
- [x] **[Learning]** Feedback Loop 구현 ✅
  - [x] 피드백 로그 분석 (analyze_feedback_logs)
  - [x] 신규 규칙 제안 (propose_new_rule)
  - [x] 규칙 성능 분석 (get_rule_performance)

- [x] **[Learning]** Zwave 시뮬레이션 도구 ✅
  - [x] 시뮬레이션 실행 (run_zwave_simulation)

### 📋 Sprint 4 완료 작업 내역 (2025-11-28)
- [x] **[DB]** Learning System ORM 모델 추가
  - `FeedbackLog` - 피드백 로그 저장 (feedback_type, original_output, corrected_output)
  - `ProposedRule` - 제안된 규칙 저장 (rule_name, rhai_script, confidence, status)
- [x] **[Agent]** Learning Agent 구현 (`backend/app/agents/learning_agent.py`)
  - 4개 Tools: analyze_feedback_logs, propose_new_rule, run_zwave_simulation, get_rule_performance
  - 피드백 패턴 분석 및 규칙 자동 생성
  - Rhai 스크립트 자동 생성 (자연어 → DSL)
  - Z-Wave 시뮬레이션 (정확도 측정, 재현율, F1 스코어)
- [x] **[Prompts]** Learning Agent 프롬프트 작성 (`backend/app/prompts/learning_agent.md`)
- [x] **[API]** Agent 라우터 통합 (target_agent="learning" 라우팅)
- [x] **[Router]** Meta Router 업데이트 ("학습", "피드백", "시뮬레이션" 키워드 → learning)

---

## 🗓️ Sprint 5: 보안 ✅

### 🔐 Security
- [x] **[Security]** 인증 시스템 구현 ✅
- [x] **[Security]** PII 마스킹 미들웨어 ✅

### 📋 Sprint 5 완료 작업 내역 (2025-11-28)

#### 🔐 JWT 인증 시스템
- [x] **[Auth]** Password Hashing (`backend/app/auth/password.py`)
  - bcrypt 알고리즘 사용 (passlib)
  - verify_password, get_password_hash 함수
- [x] **[Auth]** JWT Token 관리 (`backend/app/auth/jwt.py`)
  - Access Token (30분), Refresh Token (7일)
  - 환경변수: JWT_SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES
- [x] **[Auth]** FastAPI Dependencies (`backend/app/auth/dependencies.py`)
  - get_current_user, get_current_active_user, get_optional_user
  - Bearer Token 검증 및 사용자 조회
- [x] **[Auth]** Auth Schemas (`backend/app/schemas/auth.py`)
  - LoginRequest, RegisterRequest, TokenResponse, UserResponse 등
- [x] **[Auth]** Auth API Router (`backend/app/routers/auth.py`)
  - POST /login - 로그인 (이메일/비밀번호)
  - POST /register - 회원가입
  - POST /refresh - 토큰 갱신
  - POST /change-password - 비밀번호 변경
  - GET /me - 현재 사용자 정보
  - GET /status - 인증 상태 확인
- [x] **[DB]** Admin 계정 자동 시딩 (`backend/app/init_db.py`)
  - 환경변수: ADMIN_EMAIL (기본: admin@triflow.ai), ADMIN_PASSWORD (기본: admin1234)
  - 서버 시작 시 Default Tenant + Admin User 자동 생성

#### 🛡️ PII 마스킹 미들웨어
- [x] **[PII]** 한국 PII 패턴 정의 (`backend/app/utils/pii_patterns.py`)
  - 10개 패턴: 주민등록번호, 외국인등록번호, 여권번호, 운전면허번호
  - 휴대전화 (010), 일반전화, 이메일, 신용카드, 계좌번호, IP주소
  - mask_pii(), contains_pii() 함수
- [x] **[PII]** Request/Response 마스킹 미들웨어 (`backend/app/middleware/pii_masking.py`)
  - BaseHTTPMiddleware 상속
  - Request Body 마스킹 (LLM 보호 우선)
  - Response Body 마스킹
  - PIIMaskingFilter (로깅 마스킹)
  - 환경변수: PII_MASKING_ENABLED (기본: true)
- [x] **[Main]** main.py 통합
  - lifespan 컨텍스트로 DB 초기화
  - PIIMaskingMiddleware 등록
  - Auth Router 등록 (/api/v1/auth)

#### 🔒 인증 적용 범위 (Option B)
- **Public APIs**: /health, /auth/*, /docs, /redoc, /openapi.json
- **Protected APIs**: 모든 기타 API (MVP에서는 선택적 적용)

---

## 🗓️ Sprint 6: 릴리스 ✅

### 🚀 Release
- [x] **[Release]** UAT (사용자 수용 테스트) ✅
- [x] **[Release]** Production 빌드 생성 ✅
- [x] **[Release]** 설치 패키지 생성 (Windows/Mac/Linux) ✅
  - MSI: `TriFlow AI_0.1.0_x64_en-US.msi`
  - NSIS: `TriFlow AI_0.1.0_x64-setup.exe`

---

## 📁 프로젝트 구조 (예정)

```
triflow-ai/
├── AI_GUIDELINES.md          # AI 개발 가이드라인
├── TASKS.md                  # 작업 목록
├── docker-compose.yml        # Docker 개발 환경
├── .env.example              # 환경 변수 템플릿
│
├── backend/                  # Python FastAPI 백엔드
│   ├── agents/               # AI 에이전트 로직
│   ├── tools/                # 에이전트 도구 (rhai, db 등)
│   ├── prompts/              # 프롬프트 템플릿
│   ├── api/                  # API 엔드포인트
│   └── models/               # Pydantic 모델
│
├── frontend/                 # Tauri + React 프론트엔드
│   ├── src/                  # React 소스
│   ├── src-tauri/            # Tauri (Rust) 소스
│   └── public/               # 정적 파일
│
└── docs/                     # 문서
    ├── specs/                # 기술 명세서
    └── archive/              # 아카이브된 문서
```

---

## 📌 참고 사항

- **기술 스택**: Tauri v2 + React + FastAPI + PostgreSQL + Redis
- **AI 모델**: Anthropic Claude API (claude-sonnet-4-5-20250929)
- **룰 엔진**: Rhai (Rust 기반)
- **목표**: 3개월 내 MVP 출시
