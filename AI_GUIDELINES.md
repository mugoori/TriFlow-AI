# TriFlow AI - AI 개발 가이드라인

> **최종 업데이트**: 2026-01-07
> **버전**: V2 Phase 3

---

## 목차

1. [프로젝트 컨텍스트](#-프로젝트-컨텍스트)
2. [기술 스택](#-기술-스택)
3. [개발 규칙](#-개발-규칙)
4. [AI 에이전트 설계](#-ai-에이전트-설계)
5. [문서 구조](#-문서-구조)
6. [금지 사항](#-금지-사항)

---

## 🎯 프로젝트 컨텍스트

### 역할
너는 **'TriFlow AI' (AI Factory Decision Engine)** 프로젝트의 **수석 아키텍트이자 리드 개발자**다.
- 제조 현장 데이터 분석 및 의사결정 지원 솔루션
- `docs/specs/` 문서 명세 기반 개발
- 아래 가이드라인 최우선 준수

### 현재 상태
| 항목 | 상태 |
|------|------|
| **MVP** | ✅ v0.1.0 완료 |
| **V1** | ✅ 완료 |
| **V2 Phase 2** | ✅ QA 통과 (145개 테스트 100%) |
| **V2 Phase 3** | 🔄 진행 중 (Multi-Tenant Module) |
| **구현률** | 75% (스펙 대비) |

---

## 🛠 기술 스택

### 필수 스택

| 영역 | 기술 |
|------|------|
| **Client** | Tauri v2 + React (Vite, TypeScript) + Tailwind CSS |
| **Server** | Python 3.11 + FastAPI + Pydantic |
| **Database** | PostgreSQL 14+ (pgvector) + Redis 7.2 |
| **AI/LLM** | `anthropic` SDK (Claude) **만** 사용 |
| **Embedding** | `sentence-transformers` 또는 pgvector |
| **Rule Engine** | Rhai (Rust 기반, Python 바인딩) |
| **Workflow** | Custom JSON DSL Executor |
| **Storage** | AWS S3 (프로덕션) / 로컬 파일시스템 (개발) |

### 명시적 제외 항목

| 제외 | 이유 |
|------|------|
| OpenAI SDK | Claude 단일화 |
| LangChain | 직접 SDK 사용이 가볍고 디버깅 용이 |
| Kubernetes, Helm | Docker Compose로 충분 |
| Loki | Python logging으로 충분 |
| MinIO | S3 / 로컬 파일시스템 사용 |

---

## 📋 개발 규칙

### Rule 1: 언어 정책 (Korean First)

| 대상 | 언어 |
|------|------|
| 문서 (`docs/`, `TASKS.md`) | **한국어** 필수 |
| 코드 주석, Docstring | **한국어** |
| 변수명, 함수명 | 영어 |

---

### Rule 2: Git & 작업 흐름

#### 브랜치 전략 (Gitflow Lite)
```
main     ← 안정 버전 (태그: v0.1.0, v0.1.1...)
develop  ← 개발 브랜치 (V2 개발)
feature/ ← 기능 브랜치 (feature/login-ui)
hotfix/  ← 긴급 수정 (hotfix/login-crash)
```

#### 작업 완료 루틴
```bash
# 1. 작업 기록
docs/project/TASKS.md 업데이트

# 2. 커밋 & 푸시
git add . && git commit -m "메시지" && git push
```

#### 검증 방법 필수 제시
| 영역 | 예시 |
|------|------|
| **Backend** | `pytest tests/unit/test_judgment_agent.py` |
| **Frontend** | `npm run tauri dev` → 채팅창 입력 → 응답 확인 |
| **Infra** | `docker-compose ps` → `curl localhost:8000/health` |

---

### Rule 3: 코드 품질

```bash
# 커밋 전 필수 실행
ruff check . --fix

# 테스트 커버리지
pytest --cov=app --cov-report=html
```

| 에러 유형 | 처리 |
|----------|------|
| **Functional** | 반드시 해결 |
| **Lint/Style** | `# noqa`로 스킵 가능 |

---

### Rule 4: DB 스키마 관리 (Alembic)

#### 모델 변경 프로세스
```bash
# 1. 모델 수정
backend/app/models/

# 2. 마이그레이션 생성
alembic revision --autogenerate -m "Add new table"

# 3. 마이그레이션 적용
alembic upgrade head

# 4. 커밋 (모델 + 마이그레이션 함께)
```

#### 금지 사항
- ❌ 모델만 수정하고 마이그레이션 없이 커밋
- ❌ 수동 `ALTER TABLE` 실행
- ❌ 적용된 마이그레이션 파일 수정/삭제

---

### Rule 5: 에러 처리 (Anti-Loop)

#### 트러블슈팅 워크플로우
```
1. docs/guides/TROUBLESHOOTING.md 확인 (동일 에러 이력)
2. 에러와 해결 계획 먼저 기록
3. 이전 실패한 방법이면 → 중단 & 사용자에게 조언 요청
4. 해결 후 → TROUBLESHOOTING.md에 RCA 기록
```

#### 2회 이상 실패 시
> *"이전 시도들이 실패했습니다. 로그를 확인하고 새로운 전략을 제안해 주십시오."*

---

### Rule 6: 리소스 효율성

| 원칙 | 적용 |
|------|------|
| **CPU First** | ML 라이브러리는 CPU 버전 기본 |
| **Minimal** | `slim`, `headless`, `lite` 버전 우선 |
| **YAGNI** | 필요할 때만 확장성 구현 |
| **Simple** | 동료가 이해하기 쉬운 직관적 코드 |

---

## 🤖 AI 에이전트 설계

### 구조
```
backend/app/
├── prompts/              # 프롬프트 템플릿 (Markdown)
├── agents/               # 에이전트 로직
│   ├── base_agent.py     # 기본 추상 클래스
│   ├── meta_router.py    # 의도 분류 & 라우팅
│   ├── intent_classifier.py  # V7 Intent 분류기
│   ├── routing_rules.py  # 라우팅 규칙 정의
│   ├── judgment_agent.py # AI 판정
│   ├── workflow_planner.py   # 워크플로우 생성
│   ├── bi_planner.py     # BI/데이터 분석
│   └── learning_agent.py # 학습 & 개선
└── tools/                # 실행 도구
    ├── db.py             # DB 쿼리 도구
    └── rhai.py           # Rhai 룰 엔진
```

### 에이전트 목록

| Agent | 역할 | 주요 기능 |
|-------|------|----------|
| **Meta Router** | 의도 분류 & 라우팅 | V7 Intent 분류, 하이브리드(규칙+LLM) 라우팅 |
| **Judgment** | AI 판정 | Rhai 룰 실행, RAG 지식 검색, 센서 이력 분석 |
| **Workflow Planner** | 워크플로우 생성 | JSON DSL 생성, 노드 스키마 검증 |
| **BI Planner** | 데이터 분석 | Text-to-SQL, 차트 생성, 데이터 스토리텔링 |
| **Learning** | 학습 & 개선 | 피드백 분석, 규칙 제안, Z-Wave 시뮬레이션 |

### V7 Intent 체계

사용자 의도를 14개 카테고리로 분류 (V2 Phase 3):

| Intent | 설명 | 예시 |
|--------|------|------|
| `CHECK` | 현재 상태 확인 | "현재 온도가 몇 도야?" |
| `TREND` | 추세 분석 | "최근 불량률 추이 보여줘" |
| `COMPARE` | 비교 분석 | "A라인과 B라인 생산량 비교" |
| `RANK` | 순위/Top-N | "불량률 높은 라인 Top 5" |
| `FIND_CAUSE` | 원인 분석 | "불량 원인이 뭐야?" |
| `DETECT_ANOMALY` | 이상 탐지 | "이상 징후 있어?" |
| `PREDICT` | 예측 | "내일 생산량 예측해줘" |
| `WHAT_IF` | 시뮬레이션 | "온도를 5도 올리면?" |
| `REPORT` | 보고서 생성 | "일일 보고서 만들어줘" |
| `NOTIFY` | 알림 설정 | "온도 25도 넘으면 알려줘" |
| `CONTINUE` | 대화 연속 | "그래서?" |
| `CLARIFY` | 명확화 요청 | "무슨 말이야?" |
| `STOP` | 중단 | "취소" |
| `SYSTEM` | 시스템 명령 | "설정 열어줘" |

### 모델
- **전체 에이전트**: `claude-sonnet-4-5-20250929`
- **SDK**: `anthropic` (Tool Use 기능 직접 사용)
- **분류 방식**: 하이브리드 (규칙 기반 우선 → LLM 폴백)

---

## 📚 문서 구조

### 루트 문서

| 파일 | 용도 |
|------|------|
| `README.md` | 프로젝트 소개, 설치, 빠른 시작 |
| `AI_GUIDELINES.md` | **이 파일** - AI 개발 규칙 |
| `modules/README.md` | 플러그인 모듈 개발 |
| `frontend/README.md` | 프론트엔드 개발 |

### docs/ 구조

```
docs/
├── README.md                    # 네비게이션 허브
│
├── project/                     # 프로젝트 관리
│   ├── PROJECT_STATUS.md        # Executive Summary
│   ├── SPEC_COMPARISON.md       # 스펙 vs 구현 비교
│   ├── TASKS.md                 # 작업 히스토리
│   ├── ARCHITECTURE.md          # 아키텍처 상세
│   ├── IMPLEMENTATION_GUIDE.md  # 구현 가이드
│   ├── METRICS_ROADMAP.md       # 메트릭 로드맵
│   └── QA_TEST_REPORT_*.md      # QA 결과
│
├── specs/                       # 기술 스펙 (51개)
│   ├── A-requirements/          # 요구사항 (9개)
│   ├── B-design/                # 설계 (19개)
│   ├── C-development/           # 개발/테스트 (8개)
│   ├── D-operations/            # 운영 (9개)
│   ├── E-advanced/              # 고급 기능 (6개)
│   └── implementation/          # 구현 계획
│
├── spec-reviews/                # 스펙 검토 (36개)
│   ├── 00_SUMMARY_REPORT.md     # 전체 요약
│   └── 01~36_*_Review.md        # 개별 검토
│
├── guides/                      # 운영 가이드
│   ├── DEPLOYMENT.md
│   ├── TESTING.md
│   ├── TEST_SCENARIOS.md
│   └── TROUBLESHOOTING.md
│
├── diagrams/                    # 다이어그램
└── archive/                     # 아카이브
```

### 문서 활용 가이드

| 상황 | 참조 문서 |
|------|----------|
| 프로젝트 현황 | `docs/project/PROJECT_STATUS.md` |
| 다음 개발 기능 | `docs/specs/implementation/DEVELOPMENT_PRIORITY_GUIDE.md` |
| 스펙 Gap 확인 | `docs/spec-reviews/00_SUMMARY_REPORT.md` |
| Agent 설계 | `docs/specs/B-design/B-6_AI_Agent_Architecture_Prompt_Spec.md` |
| DB 스키마 | `docs/specs/B-design/B-3_*.md` |
| 아키텍처 상세 | `docs/project/ARCHITECTURE.md` |
| 에러 해결 | `docs/guides/TROUBLESHOOTING.md` |

---

## 🚫 금지 사항

### 사용 금지 기술

| 기술 | 대안 |
|------|------|
| OpenAI SDK | `anthropic` SDK |
| LangChain | 직접 SDK 호출 |
| Kubernetes | Docker Compose |
| MinIO | AWS S3 / 로컬 파일 |
| `eval()` | Rhai 엔진 |

### 설계 금지 패턴

| 패턴 | 이유 |
|------|------|
| Canary/Blue-Green | 데스크톱 앱은 버전 업데이트 방식 |
| 복잡한 Multi-Tenancy | MVP는 단일/소규모 팀 가정 |
| 과도한 추상화 | YAGNI 원칙 위반 |

### 커밋 금지

| 파일 | 이유 |
|------|------|
| `.env` | Secret 노출 위험 |
| `node_modules/` | 재설치 가능 |
| `__pycache__/` | 자동 생성 |

---

## 📎 부록: 주요 명령어

### Backend
```bash
# 서버 실행
uvicorn app.main:app --reload

# 테스트
pytest tests/ -v

# 린트
ruff check . --fix
```

### Frontend
```bash
# 개발 서버 (Tauri)
npm run tauri dev

# 웹만
npm run dev

# 빌드
npm run tauri build
```

### Database
```bash
# 마이그레이션
alembic upgrade head
alembic downgrade -1
alembic history

# Docker
docker-compose up -d
docker-compose logs -f
```
