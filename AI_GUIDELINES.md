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
- **Object Storage**: AWS S3 (프로덕션) / 로컬 파일시스템 (개발).
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
   1. `TASKS.md`에 작업 내용을 적고 현황판 업데이트 (진척도 반영).
   2. `git add .` -> `git commit` -> `git push`.
3. **Verification Protocol (Mandatory)**: 작업 완료 보고(Commit/Push 전) 시, 반드시 **"검증 방법(How to Test)"**을 코멘트로 남겨야 한다.
   - **Backend**: 새로 작성하거나 수정한 기능을 검증할 수 있는 **구체적인 `pytest` 명령어**를 제시한다.
     - *예시*: "Judgment 로직을 검증하려면 `pytest tests/unit/test_judgment_agent.py`를 실행하세요."
   - **Frontend**: 실행 후 확인해야 할 **UI 동작 시나리오**를 단계별로 명시한다.
     - *예시*: "1. `npm run tauri dev` 실행 -> 2. 채팅창에 '안녕' 입력 -> 3. 응답 카드가 뜨는지 확인."
   - **Infra/DB**: 정상 구동 확인을 위한 **Health Check 명령어**를 제시한다.
     - *예시*: "`docker-compose ps`로 컨테이너 상태 확인 후, `curl http://localhost:8000/health` 호출."
4. **CI/CD & Error Handling**:
   - **Functional Errors**: 기능 동작에 영향을 주는 에러는 **반드시 해결**해야 한다. (타협 불가)
   - **Non-functional Errors**: 린트(Lint), 스타일 등 기능과 무관한 에러는 `# noqa` 등으로 예외 처리하여 **스킵(Skip) 가능**하다.

---

## 🌿 Rule 2.1: Branch & Versioning Strategy (Desktop App Lifecycle)
이 프로젝트는 설치형 애플리케이션이므로 **버전 태깅(Tagging)**과 **안정성** 중심의 브랜치 전략을 따른다.

### 1. MVP 개발 단계 (Current Phase)
- **전략**: **Trunk-Based Development (단일 브랜치)**
- **Main Branch**: `main` 브랜치에서 모든 개발을 진행한다.
- **Feature Branch**: 복잡한 기능 개발 시에만 `feature/기능명` 브랜치를 생성하고, 완료 즉시 `main`으로 머지(Squash & Merge)한다.

### 2. MVP 배포 및 V1 개발 단계 (Post-MVP)
MVP가 완성되어 `v0.1.0`으로 배포된 직후부터는 **Gitflow Lite** 전략으로 전환한다.

1. **MVP 릴리즈 (Release)**: `main` 브랜치 커밋에 `v0.1.0` 태그를 생성하여 버전을 박제한다.
2. **V1 개발 (Develop)**: `main`에서 `develop` 브랜치를 분기(Branching)한다. 이후 모든 V1 기능 개발은 `develop`을 기준으로 진행한다.
3. **긴급 수정 (Hotfix)**: 배포된 MVP(`main`)에 버그가 발생하면 `hotfix/이슈명` 브랜치에서 수정 후 `main`에 머지하고 태그(`v0.1.1`)를 붙인다. 수정 사항은 반드시 `develop`에도 머지(Backport)한다.

### 🏷️ Naming Convention
- **Feature**: `feature/login-ui`, `feature/rhai-engine`
- **Hotfix**: `hotfix/login-crash`
- **Tags**: `v{Major}.{Minor}.{Patch}` (예: `v0.1.0`)

---

## ⚡ Rule 2.2: CI Optimization (Concurrency)
지속적인 커밋으로 인해 CI 파이프라인이 중복 실행되는 것을 방지하고 리소스를 절약하기 위해, 모든 GitHub Actions 워크플로우 파일(`.github/workflows/*.yml`)에는 반드시 **Concurrency(자동 취소)** 설정을 포함한다.

**필수 적용 예시:**
```yaml
# 동일한 브랜치/PR에 새로운 커밋이 오면 기존 진행 중인 작업을 취소함
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

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
**작업 진행 시마다 `TASKS.md`에 작업 내용을 적고 현황판을 업데이트한 후 커밋한다.**

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
- **MinIO**: 제거. AWS S3 또는 로컬 파일시스템 사용.

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
| MinIO | AWS S3 / 로컬 파일시스템 | 클라우드 배포 지원 |
| Loki | Python logging (JSON) | 로컬 로그 충분 |
| Canary Deployment | 앱 버전 업데이트 | 데스크톱 앱 배포 방식 |

### 4. 📌 Implementation Guideline
- 문서 B-1-4, D-1 등에 언급된 기술 스택은 **참고만** 하되, Rule 8이 우선한다.
- `requirements.txt` 작성 시 OpenAI, LangChain 의존성을 포함하지 않는다.
- 에이전트 구현 시 `anthropic` SDK의 Tool Use 기능을 직접 사용한다.

---

## 🛡️ Rule 9: Anti-Loop & Troubleshooting Protocol
**AI가 동일한 오류 수정 시도를 반복(Loop)하는 것을 방지하기 위해 '트러블 슈팅 로그'를 강제한다.**

### 1. Troubleshooting Log File
- **파일 위치**: `docs/TROUBLESHOOTING.md`
- **필수 항목**: 날짜, 에러 메시지(요약), 시도한 해결책, 결과(성공/실패), 근본 원인(RCA).

### 2. Anti-Loop Workflow
에러(CI 실패, 빌드 오류, 런타임 에러)가 발생하면 즉시 수정을 시도하지 말고 다음 절차를 따른다:

1. **Check History**: `docs/TROUBLESHOOTING.md`를 읽어 동일한 에러가 이전에 발생했는지 확인한다.
2. **Log First**: 현재 발생한 에러와 계획된 해결책을 로그 파일에 먼저 기록한다.
3. **Verify Strategy**: 만약 이전에 실패했던 해결책과 동일하다면, **작업을 중단**하고 다른 접근 방식을 찾거나 사용자에게 조언을 구한다.
4. **Commit Log**: 에러 수정 코드를 커밋할 때, 업데이트된 `TROUBLESHOOTING.md` 파일도 함께 커밋한다.

### 3. Loop Break Condition
- 동일한 에러로 **2회 이상 실패**할 경우, 즉시 멈추고 사용자에게 다음을 요청한다:
  - *"이전 시도들이 실패했습니다. 로그를 확인하고 새로운 전략을 제안해 주십시오."*

### 4. 오류 해결 후 필수 기록 (Mandatory Documentation)
- **에러 해결 즉시 기록**: 오류를 성공적으로 해결한 후, 반드시 `docs/TROUBLESHOOTING.md`에 다음 항목을 기록한다:
  - **에러 메시지**: 발생한 오류의 핵심 메시지
  - **발생 위치**: 파일명, 라인번호 또는 컴포넌트명
  - **근본 원인 (RCA)**: 왜 이 에러가 발생했는지 분석
  - **최종 해결책**: 어떻게 수정했는지 구체적인 코드 예시 포함
  - **디버깅 팁**: 향후 같은 문제 발생 시 빠르게 해결할 수 있는 힌트
- **목적**: 동일한 오류가 재발했을 때 이전 해결책을 참조하여 **Loop를 방지**하고 효율적으로 해결한다.
- **체크리스트화**: 자주 발생하는 패턴(예: CORS 에러, 테이블 누락)은 "Common Issues & Solutions" 섹션에 체크리스트로 정리한다.

---

## 📉 Rule 10: Resource Efficiency & Minimalism (Core Engineering Principle)
**"작동하는 가장 가벼운 방법"을 선택한다. 이는 MVP뿐만 아니라 V1, V2 등 프로젝트 전 라이프사이클에 적용되는 불변의 원칙이다.**

### 1. Dependency Hygiene (의존성 다이어트)
- **CPU First Strategy**: ML/AI 라이브러리는 **CPU 전용 버전을 기본(Default)**으로 한다. GPU 버전은 명확한 성능 요구사항이 증명된 경우에만 추가한다.
  - *예시*: `torch` 설치 시 `--index-url https://download.pytorch.org/whl/cpu` 옵션 필수.
- **Minimal Installation**: 무거운 전체 패키지 대신 `headless`, `slim`, `lite` 버전을 우선 사용한다.
  - *예시*: `opencv-python-headless`, `python:3.11-slim`.

### 2. Infrastructure Agnostic (인프라 중립성)
- **Protocol over Vendor**: 특정 클라우드 벤더(AWS, GCP)의 종속적인 기능 대신, **표준 프로토콜**(S3 Protocol, Postgres Wire Protocol)을 준수하는 도구를 사용한다.
  - *이유*: 이를 통해 로컬(Docker), 온프레미스, 클라우드 어디든 코드 수정 없이 배포할 수 있다.
- **Container Optimization**: `Dockerfile`은 항상 Layer Caching과 Multi-stage build를 적용하여 빌드 속도와 용량을 최적화한다.

### 3. YAGNI & Simple Design
- **Complexity on Demand**: 확장성(Sharding, Microservices)은 **실제 병목이 발생했을 때** 도입한다. 미리 예측해서 구현하지 않는다.
- **Understandable Code**: "멋진 코드"보다 "동료가 이해하기 쉬운 직관적인 코드"를 작성한다.

---

## 🗄️ Rule 11: Database Schema Management (Alembic Migration)
**모든 데이터베이스 스키마 변경은 Alembic 마이그레이션을 통해 관리한다.**

### 1. 스키마 관리 원칙
- **Alembic 마이그레이션 필수**: 모든 스키마 변경은 마이그레이션 파일로 추적한다.
- **스펙 문서 기준**: B-3-1 (Core), B-3-2 (BI Analytics), B-3-3 (RAG & AAS) 스펙 문서를 기준으로 스키마를 정의한다.
- **멀티 스키마 지원**: `core`, `analytics`, `rag`, `aas` 4개 스키마를 분리하여 관리한다.

### 2. 모델 변경 시 필수 프로세스
SQLAlchemy 모델을 수정하거나 새 테이블을 추가할 때 반드시 다음 순서를 따른다:

1. **모델 수정**: `backend/app/models/` 파일에서 ORM 모델을 수정한다.
2. **마이그레이션 생성**: `alembic revision --autogenerate -m "변경_설명"` 실행.
3. **마이그레이션 검토**: 생성된 마이그레이션 파일(`backend/alembic/versions/`)을 검토하고 필요시 수정한다.
4. **마이그레이션 적용**: `alembic upgrade head` 실행.
5. **커밋**: 마이그레이션 파일과 모델 파일을 함께 커밋한다.

### 3. 금지 사항
- ❌ **모델만 수정하고 마이그레이션 없이 커밋** - 개발/프로덕션 스키마 불일치 발생
- ❌ **수동 ALTER TABLE 실행** (긴급 상황 제외) - 마이그레이션 이력 깨짐
- ❌ **이미 적용된 마이그레이션 파일 수정/삭제** - 다른 환경과 충돌 발생

### 4. 자동 마이그레이션
- 서버 시작 시 `init_db.py`가 자동으로 `alembic upgrade head`를 실행한다.
- 환경변수 `USE_ALEMBIC_MIGRATION=false`로 비활성화 가능 (테스트 환경 등).

### 5. 마이그레이션 파일 구조
```
backend/
├── alembic.ini                      # Alembic 설정
├── alembic/
│   ├── env.py                       # 마이그레이션 환경 설정
│   ├── script.py.mako               # 마이그레이션 템플릿
│   └── versions/
│       ├── 001_core_schema_baseline.py       # Core 스키마 (B-3-1)
│       ├── 002_bi_analytics_schema.py        # BI Analytics (B-3-2)
│       └── 003_rag_aas_schema.py             # RAG & AAS (B-3-3)
```

### 6. 주요 명령어
```bash
# 현재 마이그레이션 상태 확인
alembic current

# 마이그레이션 이력 확인
alembic history

# 새 마이그레이션 생성 (autogenerate)
alembic revision --autogenerate -m "Add new table"

# 마이그레이션 적용
alembic upgrade head

# 마이그레이션 롤백 (1단계)
alembic downgrade -1

# 특정 버전으로 이동
alembic upgrade 001_core_baseline
```
