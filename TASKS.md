# TriFlow AI - 작업 목록 (TASKS)

> **최종 업데이트**: 2025-11-26
> **현재 Phase**: Phase 1 - 프로젝트 초기 설정

---

## 📊 TriFlow AI Project Dashboard

### 📅 Product Roadmap
| Milestone | Goal | Status | Progress | 완료/전체 |
| :--- | :--- | :--- | :--- | :--- |
| **MVP** | **PC 설치형 데스크톱 앱** (Core + Chat UI) | 🔄 In Progress | ██░░░░░░░░ 18% | 3/17 |
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
| **Sprint 1** | **[Infra]** Docker Compose (Postgres, Redis, MinIO) | ⏳ Pending | ░░░░░░░░░░ 0% |
| | **[DB]** Init Schemas (Core, BI, RAG, Audit) | ⏳ Pending | ░░░░░░░░░░ 0% |
| | **[Core]** `tools/rhai.py` (Rust Binding) 구현 | ⏳ Pending | ░░░░░░░░░░ 0% |
| | **[Core]** `tools/db.py` (Safe Query) 구현 | ⏳ Pending | ░░░░░░░░░░ 0% |
| | **[CI/CD]** GitHub Actions 워크플로우 설정 | ⏳ Pending | ░░░░░░░░░░ 0% |
| **Sprint 2** | **[Agent]** Meta Router & Judgment Agent 구현 | ⏳ Pending | ░░░░░░░░░░ 0% |
| | **[Agent]** Workflow Planner (NL->DSL) 구현 | ⏳ Pending | ░░░░░░░░░░ 0% |
| | **[Agent]** BI Planner (Text-to-SQL) 구현 | ⏳ Pending | ░░░░░░░░░░ 0% |
| **Sprint 4** | **[Learning]** Feedback Loop & Zwave Sim Tool | ⏳ Pending | ░░░░░░░░░░ 0% |
| **Sprint 5** | **[Security]** Auth & PII Masking Middleware | ⏳ Pending | ░░░░░░░░░░ 0% |

#### 🎨 Frontend (Tauri/React)
| Sprint | Task | Status | Progress |
| :--- | :--- | :--- | :--- |
| **Sprint 1** | **[Setup]** Tauri v2 + React + Vite Init | ⏳ Pending | ░░░░░░░░░░ 0% |
| | **[Setup]** Tailwind + Shadcn/ui Config | ⏳ Pending | ░░░░░░░░░░ 0% |
| **Sprint 3** | **[UI]** Chat-Centric Interface Layout | ⏳ Pending | ░░░░░░░░░░ 0% |
| | **[UI]** Dashboard & Chart Visualization | ⏳ Pending | ░░░░░░░░░░ 0% |
| **Sprint 6** | **[Release]** UAT & Production Build | ⏳ Pending | ░░░░░░░░░░ 0% |

---

## 📋 현재 진행 중인 작업

### Phase 1: 프로젝트 초기 설정 ✅
- [x] `AI_GUIDELINES.md` 생성 및 개발 가이드라인 저장
- [x] `TASKS.md` 생성 및 초기 할 일 목록 작성
- [x] `README.md` 생성
- [x] Git 초기 커밋 및 푸시

---

## 🗓️ Sprint 1: 인프라 및 기본 설정

### 🔧 Backend 인프라
- [ ] **[Infra]** Docker Compose 설정
  - [ ] PostgreSQL 14+ (pgvector 확장 포함) 컨테이너 설정
  - [ ] Redis 7.2 컨테이너 설정
  - [ ] MinIO (오브젝트 스토리지) 컨테이너 설정
  - [ ] 네트워크 및 볼륨 구성

- [ ] **[DB]** 데이터베이스 스키마 초기화
  - [ ] Core 스키마 (rules, workflows, sensors)
  - [ ] BI 스키마 (reports, dashboards)
  - [ ] RAG 스키마 (documents, embeddings)
  - [ ] Audit 스키마 (logs, feedback)

- [ ] **[Core]** 핵심 도구 구현
  - [ ] `tools/rhai.py` - Rhai 룰 엔진 Python 바인딩
  - [ ] `tools/db.py` - 안전한 SQL 쿼리 실행기

- [ ] **[CI/CD]** GitHub Actions 워크플로우
  - [ ] Lint & Test 워크플로우 (Python: ruff, pytest)
  - [ ] Lint & Test 워크플로우 (Frontend: eslint, vitest)
  - [ ] Docker 이미지 빌드 및 푸시
  - [ ] 자동 배포 워크플로우 (선택적)

### 🎨 Frontend 초기 설정
- [ ] **[Setup]** Tauri v2 + React + Vite 프로젝트 초기화
- [ ] **[Setup]** Tailwind CSS 설정
- [ ] **[Setup]** Shadcn/ui 컴포넌트 라이브러리 설정

---

## 🗓️ Sprint 2: 에이전트 시스템 구현

### 🤖 AI 에이전트
- [ ] **[Agent]** Meta Router Agent 구현
  - [ ] 의도 분류 (classify_intent)
  - [ ] 슬롯 추출 (extract_slots)
  - [ ] 요청 라우팅 (route_request)

- [ ] **[Agent]** Judgment Agent 구현
  - [ ] Rhai 룰 엔진 실행 (run_rhai_engine)
  - [ ] RAG 지식 조회 (query_rag_knowledge)
  - [ ] 센서 히스토리 조회 (fetch_sensor_history)

- [ ] **[Agent]** Workflow Planner Agent 구현
  - [ ] 워크플로우 DSL 생성 (generate_workflow_dsl)
  - [ ] 노드 스키마 검증 (validate_node_schema)
  - [ ] 액션 카탈로그 검색 (search_action_catalog)

- [ ] **[Agent]** BI Planner Agent 구현
  - [ ] 테이블 스키마 조회 (get_table_schema)
  - [ ] 안전한 SQL 실행 (execute_safe_sql)
  - [ ] 차트 설정 생성 (generate_chart_config)

---

## 🗓️ Sprint 3: UI 구현

### 💬 Chat-Centric Interface
- [ ] **[UI]** 채팅 인터페이스 레이아웃
  - [ ] 메시지 입력 컴포넌트
  - [ ] 메시지 목록 컴포넌트
  - [ ] 에이전트 응답 렌더링

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
