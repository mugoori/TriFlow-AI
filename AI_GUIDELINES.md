# TriFlow AI - AI 개발 가이드라인

## Project Context & Persona
너는 제조 현장 데이터를 분석하고 의사결정을 지원하는 솔루션 **'TriFlow AI' (AI Factory Decision Engine)** 프로젝트의 수석 아키텍트이자 리드 개발자다.
업로드된 문서 docs>specs의 모든 문서 명세를 기반으로 개발하되, 아래의 **수정된 MVP 제약조건**을 최우선으로 따른다.

---

## ⚠️ CRITICAL INSTRUCTION: MVP Scope & Constraints
우리는 문서 C-1 계획에 따라 3개월 내 **TriFlow AI**의 MVP 출시를 목표로 한다.
**최우선 목표**: **PC 설치형 데스크톱 애플리케이션 (Windows/Mac/Linux)** 완성. (모바일은 V2 이후 고려)

### 1. Technology Stack (Optimized for MVP)
- **Client**: Tauri v2 + React (Vite, TypeScript) + Tailwind CSS.
- **Server**: Python (FastAPI) + Pydantic.
  - **Dev Mode**: Docker Compose로 서버 실행.
  - **Prod Mode**: Tauri 앱 실행 시 Python 백엔드를 Sidecar로 실행하거나 Docker 컨테이너와 통신.
- **Database**: PostgreSQL 14+ (pgvector 포함) + Redis 7.2.
- **Object Storage**: MinIO (Docker, 로컬).
- **AI Stack**:
  - **LLM**: `anthropic` SDK (Claude 3.5 Sonnet) **만** 사용.
  - **Embedding**: `sentence-transformers` (로컬 모델) 또는 PostgreSQL pgvector 내장 기능.
- **Core Engines**:
  - **Rule Engine**: `rhai` (Rust 기반, Python 바인딩).
  - **Workflow**: Custom JSON DSL Executor.
- **Logging/Monitoring**: Python `logging` (JSON format) + Simple Stats API.

**🚫 명시적 제외 항목**:
- OpenAI SDK, LangChain (Rule 8 참조)
- Kubernetes, Helm, ArgoCD, Loki (로컬 환경 불필요)
- AWS S3 (MinIO 사용)

---

## 🌐 Rule 0: Language Policy (Korean First)
**모든 문서와 소통은 '한국어'를 기본 원칙으로 한다.**
1. **Documentation**: `TASKS.md`, `docs/` 하위 문서는 **반드시 한국어**로 작성한다.
2. **Comments**: 코드 주석과 Docstring도 **한국어**로 작성한다.

---

## ⚖️ Rule 1: Dev/Prod Parity
1. **Docker for Backend**: 백엔드 개발 환경은 `docker-compose.yml`로 통일한다.
2. **Secret Safety**: `.env`는 절대 커밋하지 않으며, `.env.example`을 최신화한다.

---

## 🛠️ Rule 2: Workflow & Git Strategy (Strict)
1. **GitHub CLI Integration**: **현재 깃허브 CLI(`gh`)가 연결되어 있으므로, 이를 활용하여 깃허브 레파지토리에 커밋 및 푸시를 수행한다.** (별도의 인증 절차 불필요)
2. **Completion Routine**: 작업 단위 완료 시 **반드시** 다음 순서를 따른다.
   1. `AI_GUIDELINES.md` 내의 **Rule 4 (Dashboard)** 업데이트 (진척도 반영).
   2. `git add .` -> `git commit` -> `git push`.
3. **CI/CD & Error Handling**:
   - **Functional Errors**: 기능 동작에 영향을 주는 에러는 **반드시 해결**해야 한다. (타협 불가)
   - **Non-functional Errors**: 린트(Lint), 스타일 등 기능과 무관한 에러는 `# noqa` 등으로 예외 처리하여 **스킵(Skip) 가능**하다.

---

## 🧩 Rule 3: Agent & Prompt Structure
**프롬프트와 실행 코드를 분리한다.** (B-6 설계 반영)
1. **Structure**: `prompts/` (Markdown/Jinja2), `agents/` (Logic), `tools/` (Execution).
2. **Orchestration**: Meta Agent가 사용자의 입력을 받아 적절한 Sub-Agent로 라우팅하거나 답변을 생성한다.

---

## 🤖 Rule 6: Sub-Agents & Custom Skills Definition
**각 에이전트는 지정된 모델(`claude-sonnet-4-5-20250929`)과 스킬(Tool)만을 사용하여 구현한다.**

| Agent | Model | Skills (Tools) |
| :--- | :--- | :--- |
| **Meta Router Agent** | claude-sonnet-4-5-20250929 | classify_intent, extract_slots, route_request |
| **Judgment Agent** | claude-sonnet-4-5-20250929 | run_rhai_engine, query_rag_knowledge, fetch_sensor_history |
| **Workflow Planner Agent** | claude-sonnet-4-5-20250929 | generate_workflow_dsl, validate_node_schema, search_action_catalog |
| **BI Planner Agent** | claude-sonnet-4-5-20250929 | get_table_schema, execute_safe_sql, generate_chart_config |
| **Learning Agent** | claude-sonnet-4-5-20250929 | analyze_feedback_logs, propose_new_rule, run_zwave_simulation |

---

## 📝 Rule 4: Task & Roadmap Dashboard
이 섹션은 프로젝트의 **메인 상태판**이다. 작업 진행 시마다 이곳을 직접 업데이트하여 커밋한다.

### 📊 TriFlow AI Project Dashboard

#### 📅 Product Roadmap
| Milestone | Goal | Status | Progress | 완료/전체 |
| :--- | :--- | :--- | :--- | :--- |
| **MVP** | **PC 설치형 데스크톱 앱** (Core + Chat UI) | 🔄 In Progress | █████░░░░░ 53% | 9/17 |
| **V1** | Builder UI & Learning Pipeline | ⏳ Pending | ░░░░░░░░░░ 0% | 0/8 |
| **V2** | Mobile App & Advanced Simulation | ⏳ Pending | ░░░░░░░░░░ 0% | 0/6 |

#### 🚀 MVP Detailed Progress (Sprint 1~6)

##### 📋 Phase 0: 프로젝트 기획 및 문서화
| Task | Status | Progress |
| :--- | :--- | :--- |
| 프로젝트 문서 (A-1 ~ D-4) 작성 | ✅ 완료 | ██████████ 100% |
| AI_GUIDELINES.md 작성 (Rule 0~8) | ✅ 완료 | ██████████ 100% |
| TASKS.md 작성 | ✅ 완료 | ██████████ 100% |
| README.md 작성 | ✅ 완료 | ██████████ 100% |
| Git 저장소 초기화 | ✅ 완료 | ██████████ 100% |

##### 🔙 Backend (Python/FastAPI)
| Sprint | Task | Status | Progress |
| :--- | :--- | :--- | :--- |
| **Sprint 1** | **[Infra]** Docker Compose (Postgres, Redis, MinIO) | ✅ 완료 | ██████████ 100% |
| | **[DB]** Init Schemas (Core, BI, RAG, Audit) | ✅ 완료 | ██████████ 100% |
| | **[Core]** `tools/rhai.py` (Rhai Engine MVP) 구현 | ✅ 완료 | ██████████ 100% |
| | **[Core]** `tools/db.py` (Safe Query) 구현 | ✅ 완료 | ██████████ 100% |
| | **[Core]** FastAPI Main App 구조 생성 | ✅ 완료 | ██████████ 100% |
| | **[CI/CD]** GitHub Actions 워크플로우 설정 | ✅ 완료 | ██████████ 100% |
| **Sprint 2** | **[Agent]** Meta Router & Judgment Agent 구현 | ⏳ Pending | ░░░░░░░░░░ 0% |
| | **[Agent]** Workflow Planner (NL->DSL) 구현 | ⏳ Pending | ░░░░░░░░░░ 0% |
| | **[Agent]** BI Planner (Text-to-SQL) 구현 | ⏳ Pending | ░░░░░░░░░░ 0% |
| **Sprint 4** | **[Learning]** Feedback Loop & Zwave Sim Tool | ⏳ Pending | ░░░░░░░░░░ 0% |
| **Sprint 5** | **[Security]** Auth & PII Masking Middleware | ⏳ Pending | ░░░░░░░░░░ 0% |

##### 🎨 Frontend (Tauri/React)
| Sprint | Task | Status | Progress |
| :--- | :--- | :--- | :--- |
| **Sprint 1** | **[Setup]** Tauri v2 + React + Vite Init | ⏳ Pending | ░░░░░░░░░░ 0% |
| | **[Setup]** Tailwind + Shadcn/ui Config | ⏳ Pending | ░░░░░░░░░░ 0% |
| **Sprint 3** | **[UI]** Chat-Centric Interface Layout | ⏳ Pending | ░░░░░░░░░░ 0% |
| | **[UI]** Dashboard & Chart Visualization | ⏳ Pending | ░░░░░░░░░░ 0% |
| **Sprint 6** | **[Release]** UAT & Production Build | ⏳ Pending | ░░░░░░░░░░ 0% |

---

## 📄 Rule 5: Document Governance
1. **AI_GUIDELINES.md**: 이 내용을 프로젝트 루트에 저장하고 항상 준수한다.
2. **Archiving**: 문서(기술 문서 등)의 내용이 너무 길어지거나 오래된 내용은 `docs/archive/` 폴더로 이동하여 현재 문서를 간결하게 유지한다.

---

## 🧪 Rule 7: Code Quality
1. **Linting**: 커밋 전 `ruff check . --fix` 실행.
2. **Coverage**: 핵심 로직(Rule Engine, DSL Parser)은 단위 테스트 필수.

---

## 🛑 Rule 8: MVP Anti-Patterns & Tech Diet (Strict Exclusions)
기존 설계 문서(B-Series, D-Series)에 언급되었더라도, **PC 설치형 MVP** 목표 달성을 위해 다음 기술과 패턴은 **구현에서 배제한다.**

### 1. 🚫 Excluded Libraries & Tools
- **OpenAI SDK**: 제거. LLM은 오직 `anthropic` SDK만 사용한다. Embeddings는 로컬(`sentence-transformers`)이나 DB(`pgvector`) 기능을 사용한다.
- **LangChain**: 제거. 에이전트 로직은 `anthropic` SDK를 사용하여 직접 제어(Control Flow)하는 것이 더 가볍고 디버깅에 유리하다.
- **Kubernetes / Helm / ArgoCD**: 제거. 배포 환경은 사용자의 로컬 PC다. 복잡한 오케스트레이션 도구 대신 `docker-compose`로 통일한다.
- **Loki / Distributed Tracing**: 제거. 단일 사용자 환경이므로 파일 기반 로깅이나 Docker 로그로 충분하다.
- **AWS S3**: 제거. 로컬 MinIO 사용.

### 2. 🚫 Design Patterns to Avoid
- **Canary / Blue-Green Deployment**: 제거. 데스크톱 앱은 '설치 파일 업데이트' 방식이다. 서버 트래픽 제어 개념을 적용하지 않는다.
- **Multi-Tenancy at Scale**: 단순화. MVP는 단일 사용자 또는 소규모 팀을 가정한다. 복잡한 테넌트 격리는 불필요하다.
- **Native Python eval()**: 절대 금지. 보안과 성능을 위해 **Rhai (Rust)** 엔진으로 통일한다.

### 3. ✅ MVP-First Alternatives
| 기존 (Docs) | MVP 대안 | 이유 |
|-------------|----------|------|
| OpenAI API | Anthropic Claude API | 단일 LLM 제공자로 단순화 |
| LangChain | Direct `anthropic` SDK | 가볍고 디버깅 용이 |
| Kubernetes | Docker Compose | 로컬 환경에 적합 |
| AWS S3 | MinIO (Docker) | 오프라인 호환성 |
| Loki | Python logging (JSON) | 로컬 로그 충분 |
| Canary Deployment | 앱 버전 업데이트 | 데스크톱 앱 배포 방식 |

### 4. 📌 Implementation Guideline
- 문서 B-1-4, D-1 등에 언급된 기술 스택은 **참고만** 하되, Rule 8이 우선한다.
- `requirements.txt` 작성 시 OpenAI, LangChain 의존성을 포함하지 않는다.
- 에이전트 구현 시 `anthropic` SDK의 Tool Use 기능을 직접 사용한다.
