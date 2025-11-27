# TriFlow AI - 작업 목록 (TASKS)

> **최종 업데이트**: 2025-11-27
> **현재 Phase**: Sprint 3 - Chat UI 구현 완료

---

## 📊 TriFlow AI Project Dashboard

### 📅 Product Roadmap
| Milestone | Goal | Status | Progress | 완료/전체 |
| :--- | :--- | :--- | :--- | :--- |
| **MVP** | **PC 설치형 데스크톱 앱** (Core + Chat UI) | 🔄 In Progress | ████████░░ 76% | 13/17 |
| **V1** | Builder UI & Learning Pipeline | ⏳ Pending | ░░░░░░░░░░ 0% | 0/8 |
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
| | **[Agent]** Workflow Planner (NL->DSL) 구현 | ⏳ Pending | ░░░░░░░░░░ 0% |
| | **[Agent]** BI Planner (Text-to-SQL) 구현 | ⏳ Pending | ░░░░░░░░░░ 0% |
| **Sprint 4** | **[Learning]** Feedback Loop & Zwave Sim Tool | ⏳ Pending | ░░░░░░░░░░ 0% |
| **Sprint 5** | **[Security]** Auth & PII Masking Middleware | ⏳ Pending | ░░░░░░░░░░ 0% |

#### 🎨 Frontend (Tauri/React)
| Sprint | Task | Status | Progress |
| :--- | :--- | :--- | :--- |
| **Sprint 1** | **[Setup]** Tauri v2 + React + Vite Init | ✅ 완료 | ██████████ 100% |
| | **[Setup]** Tailwind + Shadcn/ui Config | ✅ 완료 | ██████████ 100% |
| **Sprint 3** | **[UI]** Chat-Centric Interface Layout | ✅ 완료 | ██████████ 100% |
| | **[UI]** Dashboard & Chart Visualization | ⏳ Pending | ░░░░░░░░░░ 0% |
| **Sprint 6** | **[Release]** UAT & Production Build | ⏳ Pending | ░░░░░░░░░░ 0% |

---

## 📋 현재 진행 중인 작업

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

- [ ] **[Agent]** Workflow Planner Agent 구현
  - [ ] 워크플로우 DSL 생성 (generate_workflow_dsl)
  - [ ] 노드 스키마 검증 (validate_node_schema)
  - [ ] 액션 카탈로그 검색 (search_action_catalog)

- [ ] **[Agent]** BI Planner Agent 구현
  - [ ] 테이블 스키마 조회 (get_table_schema)
  - [ ] 안전한 SQL 실행 (execute_safe_sql)
  - [ ] 차트 설정 생성 (generate_chart_config)

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
- [ ] **[UI]** 대시보드 레이아웃
- [ ] **[UI]** 차트 시각화 컴포넌트 (Recharts/Chart.js)
- [ ] **[UI]** 실시간 데이터 표시

---

## 🗓️ Sprint 4: 학습 파이프라인

### 🧠 Learning System
- [ ] **[Learning]** Feedback Loop 구현
  - [ ] 피드백 로그 분석 (analyze_feedback_logs)
  - [ ] 신규 규칙 제안 (propose_new_rule)

- [ ] **[Learning]** Zwave 시뮬레이션 도구
  - [ ] 시뮬레이션 실행 (run_zwave_simulation)

---

## 🗓️ Sprint 5: 보안

### 🔐 Security
- [ ] **[Security]** 인증 시스템 구현
- [ ] **[Security]** PII 마스킹 미들웨어

---

## 🗓️ Sprint 6: 릴리스

### 🚀 Release
- [ ] **[Release]** UAT (사용자 수용 테스트)
- [ ] **[Release]** Production 빌드 생성
- [ ] **[Release]** 설치 패키지 생성 (Windows/Mac/Linux)

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
