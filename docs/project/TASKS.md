# TriFlow AI - 작업 목록 (TASKS)

> **최종 업데이트**: 2026-01-09
> **현재 Phase**: V2 Phase 3 진행 중 (Feature Flags & Module System)
> **현재 브랜치**: `develop`

---

## 📊 Project Dashboard

### 📅 Product Roadmap
| Milestone | Goal | Status | Progress |
|-----------|------|--------|----------|
| **MVP** | PC 설치형 데스크톱 앱 (Core + Chat UI) | ✅ v0.1.0 | ██████████ 100% |
| **V1** | Builder UI & Learning & 외부연동 & 보안 | ✅ 완료 | ██████████ 100% |
| **V2 Phase 1-2** | Advanced Workflow & MCP 연동 & QA | ✅ 완료 | ██████████ 100% |
| **V2 Phase 3** | Feature Flags & Multi-Tenant Module | 🔄 진행중 | ██████░░░░ 60% |
| **V2 Phase 0** | Critical Gap 해결 (Learning, RBAC, HA) | ⏳ 예정 | ░░░░░░░░░░ 0% |

---

## 🚧 현재 진행 중: V2 Phase 3

### 구현 현황 (DEVELOPMENT_PRIORITY_GUIDE.md 기준)

#### Backend 구현 현황
| 영역 | 구현률 | 상태 | 핵심 파일 |
|------|:------:|:----:|----------|
| **Trust System** | 100% | ✅ | `trust_service.py` |
| **Feature Flags** | 100% | ✅ | `feature_flag_service.py` |
| **Agent Orchestration** | 95% | ✅ | `agent_orchestrator.py` |
| **Judgment Engine** | 90% | ✅ | `judgment_policy.py` |
| **Workflow Engine** | 100% | ✅ | `workflow_engine.py` |
| **RAG/Search** | 85% | ✅ | `rag_service.py` |
| **BI/Analytics** | 80% | 🟢 | `bi_chat_service.py` |
| **MCP ToolHub** | 90% | ✅ | `mcp_toolhub.py` |
| **Learning Pipeline** | 30% | 🔴 | `feedback_analyzer.py` |
| **RBAC** | 40% | 🟡 | `rbac_service.py` |

#### Frontend 구현 현황
| 페이지 | 구현률 | V2 기능 | Learning/Feedback |
|--------|:------:|:-------:|:-----------------:|
| **Dashboard** | 90% | ✅ | ✅ |
| **Workflows** | 85% | ✅ | 🟢 |
| **Rulesets** | 85% | ✅ | ✅ |
| **Learning** | 70% | ✅ | ✅ |
| **Experiments** | 75% | 🟢 | 🟢 |
| **Data** | 60% | 🟢 | ❌ |
| **Settings** | 50% | ❌ | ❌ |

### 🔴 Critical Gap (V2 Plan Phase 0 대상)
| 기능 | 중요도 | 현재 상태 |
|------|:------:|:--------:|
| Sample Curation Service | 🔴🔴🔴 | 미구현 |
| Rule Extraction (Decision Tree → Rhai) | 🔴🔴🔴 | 미구현 |
| Canary Deployment | 🔴🔴 | 미구현 |
| Materialized Views | ✅ | **완료** (2026-01-09) |
| 5-tier RBAC + Data Scope Filter | 🔴🔴 | 40% |

---

## 🎯 구현 완료 기능 요약

### 🔷 1. AI 에이전트 시스템
> 5개 AI 에이전트 기반 자연어 인터페이스

| 에이전트 | 역할 | 핵심 기능 |
|----------|------|----------|
| **Meta Router** | 의도 분류 & 라우팅 | 사용자 입력 → 적절한 에이전트로 전달 |
| **Judgment** | AI 판정 | Rhai 규칙 실행, RAG 지식 조회, 센서 분석 |
| **Workflow Planner** | 워크플로우 생성 | 자연어 → DSL 변환, 노드 스키마 검증 |
| **BI Planner** | 데이터 분석 | Text-to-SQL, 차트 설정 생성 |
| **Learning** | 학습 & 개선 | 피드백 분석, 규칙 제안, 룰셋 생성 |

**핵심 파일**: `backend/app/agents/`, `backend/app/prompts/`

---

### 🔷 2. 워크플로우 엔진 (18개 노드)
> 비주얼 워크플로우 빌더 + 실행 엔진

#### P0: 기본 노드 (7개)
| 노드 | 설명 | UI | 실행 |
|------|------|:--:|:----:|
| `condition` | 조건 평가 | ✅ | ✅ |
| `action` | 액션 실행 | ✅ | ✅ |
| `if_else` | 조건 분기 | ✅ | ✅ |
| `loop` | 반복 실행 | ✅ | ✅ |
| `parallel` | 병렬 실행 | ✅ | ✅ |
| `switch` | 다중 분기 | ✅ | ✅ |
| `code` | Python 실행 | ✅ | ✅ |

#### P1: 비즈니스 노드 (7개)
| 노드 | 설명 | UI | 실행 |
|------|------|:--:|:----:|
| `data` | 데이터 조회 | ✅ | ✅ |
| `judgment` | AI 판정 | ✅ | ✅ |
| `bi` | BI 분석 | ✅ | ✅ |
| `mcp` | MCP 도구 호출 | ✅ | ✅ |
| `trigger` | 트리거 설정 | ✅ | ✅ |
| `wait` | 대기 | ✅ | ✅ |
| `approval` | 인간 승인 | ✅ | ✅ |

#### P2: 고급 노드 (4개)
| 노드 | 설명 | UI | 실행 |
|------|------|:--:|:----:|
| `compensation` | Saga 보상 트랜잭션 | ✅ | ✅ |
| `deploy` | 버전 배포 | ✅ | ✅ |
| `rollback` | 버전 롤백 | ✅ | ✅ |
| `simulate` | What-if 시뮬레이션 | ✅ | ✅ |

**핵심 파일**:
- `backend/app/services/workflow_engine.py` (6,552줄)
- `frontend/src/components/workflow/FlowEditor.tsx` (3,203줄)

---

### 🔷 3. MCP (Model Context Protocol) 시스템
> 외부 시스템 연동을 위한 표준화된 인터페이스

| 컴포넌트 | 설명 | 상태 |
|----------|------|:----:|
| **MCP ToolHub** | 서버/도구 레지스트리 | ✅ |
| **HTTP Proxy** | JSON-RPC 2.0 통신 | ✅ |
| **Circuit Breaker** | 장애 차단/복구 | ✅ |
| **MES 래퍼** | 제조실행시스템 연동 (5개 도구) | ✅ |
| **ERP 래퍼** | 전사자원관리 연동 (6개 도구) | ✅ |

**래퍼 서버 도구**:
```
MES: get_production_status, get_defect_data, get_equipment_status,
     get_work_orders, update_production_count

ERP: get_inventory, get_purchase_orders, create_purchase_order,
     get_sales_orders, get_bom, check_material_availability
```

**핵심 파일**: `backend/app/mcp_wrappers/`, `backend/app/services/mcp_*.py`

---

### 🔷 4. 룰셋 & 규칙 엔진
> Rhai (Rust) 기반 안전한 규칙 실행

| 기능 | 설명 | 상태 |
|------|------|:----:|
| **Rhai 편집기** | Monaco 기반, 구문 하이라이팅 | ✅ |
| **버전 관리** | 스냅샷 저장, 롤백 | ✅ |
| **테스트 실행** | 즉시 테스트 & 결과 표시 | ✅ |
| **AI 생성** | 자연어 → Rhai 스크립트 | ✅ |

**핵심 파일**: `backend/app/tools/rhai.py`, `frontend/src/components/ruleset/`

---

### 🔷 5. 학습 & 피드백 시스템
> 지속적인 개선을 위한 피드백 루프

| 기능 | 설명 | 상태 |
|------|------|:----:|
| **피드백 수집** | 👍/👎 + 상세 피드백 모달 | ✅ |
| **AI 규칙 제안** | 피드백 분석 → 규칙 자동 제안 | ✅ |
| **A/B 테스트** | 통계적 유의성 검정 (Z-test) | ✅ |
| **학습 대시보드** | 피드백/제안/실험 통합 뷰 | ✅ |

**핵심 파일**: `backend/app/services/feedback_analyzer.py`, `backend/app/services/experiment_service.py`

---

### 🔷 6. 외부 시스템 연동
> 알림, 데이터 가져오기, 실시간 스트리밍

| 기능 | 설명 | 상태 |
|------|------|:----:|
| **Slack 알림** | Webhook 기반 | ✅ |
| **Email 알림** | SMTP 지원 | ✅ |
| **CSV/Excel 가져오기** | 드래그앤드롭 업로드 | ✅ |
| **센서 스트리밍** | WebSocket 실시간 | ✅ |
| **데이터 동기화** | APScheduler 스케줄러 | ✅ |

**핵심 파일**: `backend/app/services/notifications.py`, `backend/app/services/data_sync.py`

---

### 🔷 7. BI & 대시보드
> 데이터 시각화 및 KPI 모니터링

| 기능 | 설명 | 상태 |
|------|------|:----:|
| **StatCard** | KPI 카드 (집계 기간 표시) | ✅ |
| **차트** | Recharts 기반 시각화 | ✅ |
| **Text-to-SQL** | 자연어 → SQL 변환 | ✅ |
| **GenBI** | AI 기반 분석 응답 | ✅ |

**핵심 파일**: `backend/app/services/stat_card_service.py`, `frontend/src/components/pages/DashboardPage.tsx`

---

### 🔷 8. 보안 & 인증
> JWT 인증 및 데이터 보호

| 기능 | 설명 | 상태 |
|------|------|:----:|
| **JWT 인증** | Access + Refresh Token | ✅ |
| **RBAC** | 역할 기반 메뉴 필터링 | ✅ |
| **PII 마스킹** | 개인정보 자동 마스킹 | ✅ |
| **Security Headers** | HSTS 등 프로덕션 헤더 | ✅ |

**핵심 파일**: `backend/app/core/security.py`, `backend/app/middleware/`

---

### 🔷 9. 인프라 & 배포
> Docker 기반 개발/배포 환경

| 기능 | 설명 | 상태 |
|------|------|:----:|
| **Docker Compose** | PostgreSQL, Redis | ✅ |
| **AWS S3** | 파일 저장소 (로컬 fallback) | ✅ |
| **GitHub Actions** | CI/CD 파이프라인 | ✅ |
| **Tauri 빌드** | Windows MSI/NSIS | ✅ |

**핵심 파일**: `docker-compose.yml`, `.github/workflows/`

---

## 📁 프로젝트 구조

```
triflow-ai/
├── backend/                      # Python FastAPI 백엔드
│   ├── app/
│   │   ├── agents/               # AI 에이전트 (5개)
│   │   ├── services/             # 비즈니스 로직
│   │   │   ├── workflow_engine.py    # 워크플로우 엔진
│   │   │   ├── feature_flag_service.py  # Feature Flag (V2 Phase 3)
│   │   │   ├── tenant_config_service.py # 테넌트 설정
│   │   │   ├── mcp_proxy.py          # MCP HTTP 프록시
│   │   │   ├── mcp_toolhub.py        # MCP 서버 레지스트리
│   │   │   └── ...
│   │   ├── mcp_wrappers/         # MCP 래퍼 서버
│   │   │   ├── base_wrapper.py       # 베이스 클래스
│   │   │   ├── mes_wrapper.py        # MES 래퍼
│   │   │   └── erp_wrapper.py        # ERP 래퍼
│   │   ├── routers/              # API 엔드포인트
│   │   │   ├── feature_flags.py      # Feature Flag API (V2 Phase 3)
│   │   │   ├── tenant_config.py      # 테넌트 설정 API
│   │   │   └── ...
│   │   ├── models/               # SQLAlchemy/Pydantic 모델
│   │   ├── tools/                # 에이전트 도구
│   │   └── prompts/              # 프롬프트 템플릿
│   ├── alembic/versions/         # DB 마이그레이션 (Alembic)
│   └── migrations/               # SQL 마이그레이션 (gitignore)
│
├── frontend/                     # Tauri + React 프론트엔드
│   ├── src/
│   │   ├── components/
│   │   │   ├── workflow/
│   │   │   │   └── FlowEditor.tsx    # 비주얼 에디터
│   │   │   ├── ruleset/              # 룰셋 편집기
│   │   │   ├── pages/                # 페이지 컴포넌트
│   │   │   └── layout/               # 레이아웃
│   │   ├── contexts/             # React Context (TenantConfig 등)
│   │   ├── hooks/                # Custom Hooks
│   │   ├── modules/              # V2 Module System
│   │   └── services/             # API 클라이언트
│   └── src-tauri/                # Tauri (Rust)
│
├── docs/                         # 문서
│   ├── project/                  # 프로젝트 관리
│   │   ├── TASKS.md              # 작업 목록 (현재 파일)
│   │   ├── PROJECT_STATUS.md     # 프로젝트 현황
│   │   └── QA_TEST_REPORT_*.md   # QA 테스트 보고서
│   ├── specs/                    # 기술 명세서 (gitignore)
│   │   └── implementation/       # 구현 계획 문서
│   ├── guides/                   # 운영 가이드
│   ├── archive/                  # 아카이브
│   └── diagrams/                 # 다이어그램
│
├── AI_GUIDELINES.md              # AI 개발 가이드라인
├── README.md                     # 프로젝트 소개
└── docker-compose.yml            # Docker 환경
```

---

## 📋 상세 작업 히스토리

<details>
<summary><b>🏷️ MVP v0.1.0 릴리즈 (2025-11-28)</b></summary>

### 릴리즈 정보
- **태그**: `v0.1.0`
- **브랜치**: `main` (안정 버전), `develop` (개발)
- **빌드**: Windows MSI/NSIS, Docker Image (ghcr.io)

### 주요 기능
- 5개 AI 에이전트 (Meta Router, Judgment, Workflow Planner, BI Planner, Learning)
- Chat-Centric UI (Tauri v2 + React)
- Dashboard & Chart Visualization (Recharts)
- Workflows/Data/Settings 페이지
- JWT 인증 + PII 마스킹

</details>

<details>
<summary><b>🔧 V1 Sprint 1: Builder UI & Workflow Execution (2025-11-28)</b></summary>

### 구현 내역
- **Workflow Visual Editor**: React Flow 기반 드래그앤드롭 에디터
- **Ruleset Editor**: Monaco Editor + Rhai 구문 하이라이팅
- **Workflow Engine**: 조건/액션/분기/반복/병렬 실행
- **Sensor Simulator**: normal, alert, random, preset 시나리오
- **Execution Log Panel**: 실시간 로그 표시

### 수정 파일
- `frontend/src/components/workflow/FlowEditor.tsx`
- `frontend/src/components/workflow/WorkflowEditor.tsx`
- `frontend/src/components/ruleset/RulesetEditorModal.tsx`
- `backend/app/services/workflow_engine.py`
- `backend/app/routers/workflows.py`

</details>

<details>
<summary><b>🧠 V1 Sprint 2: Learning Pipeline (2025-12-01~02)</b></summary>

### 구현 내역
- **피드백 수집 UI**: 👍/👎 + 상세 모달
- **AI 규칙 제안**: 피드백 패턴 분석 → 규칙 자동 제안
- **A/B 테스트 프레임워크**: 실험 CRUD, 통계적 유의성 검정
- **Rhai 버전 관리**: 스냅샷 저장/롤백
- **학습 대시보드**: 통합 뷰
- **RBAC**: 역할 기반 메뉴 필터링

### 수정 파일
- `backend/app/services/feedback_analyzer.py`
- `backend/app/services/experiment_service.py`
- `backend/app/routers/feedback.py`
- `backend/app/routers/experiments.py`
- `frontend/src/components/pages/LearningPage.tsx`
- `frontend/src/components/ruleset/ProposalsPanel.tsx`

</details>

<details>
<summary><b>🔌 V1 Sprint 3: 외부 시스템 연동 (2025-12-03~05)</b></summary>

### 구현 내역
- **Slack/Email 알림**: Webhook, SMTP 연동
- **CSV/Excel Import**: 드래그앤드롭 업로드
- **센서 스트리밍**: WebSocket 실시간 데이터
- **데이터 동기화**: APScheduler 스케줄러

### 수정 파일
- `backend/app/services/notifications.py`
- `backend/app/services/data_sync.py`
- `backend/app/routers/notifications.py`
- `frontend/src/components/pages/DataPage.tsx`

</details>

<details>
<summary><b>🔐 V1 Sprint 4: 보안 & 안정화 (2025-12-06~08)</b></summary>

### 구현 내역
- **JWT 인증 강화**: Refresh Token 로직
- **PII 마스킹 미들웨어**: 개인정보 자동 마스킹
- **Rate Limiting**: 요청 제한
- **Audit Logging**: 감사 로그

### 수정 파일
- `backend/app/core/security.py`
- `backend/app/middleware/pii_masking.py`
- `backend/app/middleware/rate_limit.py`

</details>

<details>
<summary><b>🚀 V2 Phase 1: Advanced RAG & Intent (2025-12-10~15)</b></summary>

### 구현 내역
- **RAG 시스템 강화**: pgvector 기반 벡터 검색
- **Intent 분류 개선**: 다중 인텐트 지원
- **컨텍스트 관리**: 대화 히스토리 압축

### 수정 파일
- `backend/app/services/rag_service.py`
- `backend/app/agents/meta_router.py`

</details>

<details>
<summary><b>🔧 V2 Phase 2: MCP ToolHub (2025-12-16~20)</b></summary>

### 구현 내역
- **MCP 서버 레지스트리**: CRUD API
- **HTTP 프록시**: JSON-RPC 2.0 통신
- **Circuit Breaker**: 장애 차단/복구 (5회 실패 → OPEN → 60초 후 HALF_OPEN)
- **인증 지원**: API Key, OAuth2, Basic Auth
- **도구 통계**: 호출 횟수, 평균 지연시간

### 수정 파일
- `backend/app/services/mcp_proxy.py`
- `backend/app/services/mcp_toolhub.py`
- `backend/app/services/circuit_breaker.py`
- `backend/app/routers/mcp.py`
- `backend/app/models/mcp.py`

</details>

<details>
<summary><b>✅ V2 Phase 2: 워크플로우 노드 테스트 (2025-12-23)</b></summary>

### 테스트 결과 (13개 노드)
| 노드 | 결과 | 비고 |
|------|------|------|
| CONDITION | ✅ 성공 | < 1초 |
| IF_ELSE | ✅ 성공 | < 1초 |
| LOOP | ✅ 성공 | < 1초 |
| PARALLEL | ✅ 성공 | < 1초 |
| DATA | ✅ 성공 | < 1초 |
| CODE | ✅ 성공 | < 1초 |
| MCP | ✅ 성공 | < 1초 |
| JUDGMENT | ✅ 성공 | 5.3초 (Claude API) |
| BI | ✅ 성공 | 22.4초 (Claude API) |
| ROLLBACK | ⚠️ 예상된 실패 | 이전 버전 없음 |
| APPROVAL | ⏳ 대기 | 인간 승인 대기 |

### 버그 수정 (3개)
1. `MCPCallRequest` 모델 호환성 - 필드명 불일치
2. `await` on sync function - 동기 함수 await 호출
3. `MCPCallResponse` 필드명 - output vs result

</details>

<details>
<summary><b>📊 V2 Phase 2: StatCard & KPI (2025-12-24)</b></summary>

### 구현 내역
- **집계 기간 표시**: period_start, period_end, period_label
- **KPI 계산 수정**: 실제 데이터 기반 계산

### 수정 파일
- `backend/app/schemas/statcard.py`
- `backend/app/services/stat_card_service.py`
- `frontend/src/components/dashboard/StatCard.tsx`

</details>

<details>
<summary><b>☁️ V2 Phase 2: AWS 배포 준비 (2025-12-24)</b></summary>

### 구현 내역
- **MinIO → S3 전환**: boto3 클라이언트
- **로컬 Fallback**: S3 키 없으면 ./exports/ 사용
- **AWS 호환성 검토**: Redis fallback, pgvector, Health Check

### 수정 파일
- `backend/requirements.txt`
- `backend/app/config.py`
- `backend/app/services/workflow_engine.py`

</details>

<details>
<summary><b>🔌 V2 Phase 2: MCP 래퍼 서버 (2025-12-26)</b></summary>

### 구현 내역
- **base_wrapper.py**: MCP 표준 인터페이스
- **mes_wrapper.py**: MES 시스템 래퍼 (5개 도구)
- **erp_wrapper.py**: ERP 시스템 래퍼 (6개 도구)
- **run_wrapper.py**: CLI 실행 스크립트

### 사용법
```bash
# MES 래퍼 서버 실행
python -m app.mcp_wrappers.run_wrapper \
  --type mes --port 8100 \
  --target-url http://mes-server.example.com

# TriFlow에 등록
curl -X POST http://localhost:8000/api/v1/mcp/servers \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "MES Server", "base_url": "http://localhost:8100"}'
```

</details>

<details>
<summary><b>🎨 V2 Phase 2: P2 노드 UI 개선 (2025-12-26)</b></summary>

### 구현 내역
| 노드 | UI 개선 내용 |
|------|-------------|
| **SIMULATE** | simulation_type 선택, scenario/parameter_sweep/monte_carlo 모드별 UI |
| **DEPLOY** | 배포 타입, 환경, 검증 규칙 설정 |
| **ROLLBACK** | 버전 선택, 롤백 사유 입력 |
| **COMPENSATION** | auto/manual 모드, 보상 액션 설정 |

### 수정 파일
- `frontend/src/components/workflow/FlowEditor.tsx`
- `frontend/src/services/workflowService.ts`

</details>

<details>
<summary><b>🗑️ V2 Phase 2: Analytics 페이지 제거 (2025-12-26)</b></summary>

### 변경 이유
대시보드와 기능 중복으로 사용자 경험 단순화

### 수정 파일
- `frontend/src/components/pages/AnalyticsPage.tsx` (삭제)
- `frontend/src/App.tsx`
- `frontend/src/components/layout/Sidebar.tsx`

</details>

<details>
<summary><b>🔗 V2 Phase 2: DataSource 기반 MCP 통합 (2025-12-26)</b></summary>

### 구현 내역
DataSource(MES/ERP) 등록 시 자동으로 MCP 도구를 사용할 수 있도록 통합

| 컴포넌트 | 설명 | 상태 |
|----------|------|:----:|
| **DataSourceMCPService** | DataSource 기반 동적 MCP 도구 관리 | ✅ |
| **MCP API 확장** | datasource-tools 엔드포인트 (목록/호출/헬스체크) | ✅ |
| **테스트** | 단위 테스트 42개 추가 (742 passed, 83 skipped) | ✅ |

### 신규 파일
- `backend/app/services/datasource_mcp_service.py` - DataSource MCP 서비스
- `backend/tests/test_datasource_mcp.py` - 테스트

### 수정 파일
- `backend/app/routers/mcp.py` - 3개 API 엔드포인트 추가
- `backend/app/mcp_wrappers/__init__.py` - export 추가

### API 엔드포인트
```
GET  /api/v1/mcp/datasource-tools        # DataSource별 도구 목록
POST /api/v1/mcp/datasource-tools/{id}/call   # 도구 호출
GET  /api/v1/mcp/datasource-tools/{id}/health # 헬스체크
```

</details>

<details>
<summary><b>🎨 V2 Phase 2: React Flow 다크/라이트 모드 (2025-12-26)</b></summary>

### 구현 내역
워크플로우 노드 편집기의 줌 컨트롤 버튼이 다크/라이트 모드에서 모두 보이도록 수정

### 수정 파일
- `frontend/src/index.css` - React Flow Controls/MiniMap 스타일
- `frontend/src/components/workflow/FlowEditor.tsx` - 다크 모드 감지 (MutationObserver)

### 프론트엔드 TypeScript 에러 수정 (19개)
- `ChatResponseType`에 'card_action' 추가
- 미사용 import 제거 (STATUS_COLORS, ChevronDown 등)
- 타입 불일치 수정 (onPin/onUnpin, toast.success)

</details>

<details>
<summary><b>🧪 V2 Phase 2: 테스트 커버리지 개선 (2025-12-29)</b></summary>

### 목표
백엔드 테스트 커버리지 80% 달성을 위한 대규모 테스트 추가

### 결과
- **전체 커버리지**: ~75% → ~80% (목표 달성)
- **신규 테스트 파일**: 45개
- **총 테스트 케이스**: 800+ 패스

### 주요 개선 서비스

| 서비스 | 이전 | 이후 | 추가 테스트 |
|--------|------|------|-------------|
| `audit_service.py` | 41% | 100% | Mock 기반 전체 커버리지 |
| `bi_chat_service.py` | 56% | 94% | 61개 테스트 (LLM 통합) |
| `rag_service.py` | 44% | 73% | 토큰 제한, 벡터 검색 |
| `stat_card_service.py` | 65% | 85% | 집계 로직 테스트 |
| `workflow_engine.py` | 57% | 57% | 외부 의존성으로 유지 |

### 신규 테스트 파일
```
test_agent_orchestrator.py    test_api_key_service.py
test_api_keys_router.py       test_auth_dependencies.py
test_base_wrapper.py          test_bi_chat_service.py
test_bi_correlation_analyzer.py   test_bi_data_collector.py
test_bi_planner.py            test_bi_router.py
test_chart_builder.py         test_circuit_breaker_service.py
test_database.py              test_drift_detector.py
test_erp_mes_router.py        test_erp_wrapper.py
test_insight_service.py       test_judgment_agent.py
test_judgment_cache.py        test_jwt.py
test_learning_agent.py        test_main.py
test_mcp_proxy.py             test_mcp_wrappers.py
test_meta_router.py           test_notifications_service.py
test_password.py              test_pii_masking_middleware.py
test_rag_service.py           test_rate_limit_middleware.py
test_routing_rules.py         test_run_wrapper.py
test_scheduler_router.py      test_scheduler_service.py
test_settings_service.py      test_stat_card_service.py
test_statcard_models.py       test_story_service.py
test_tenants_router.py        test_workflow_engine_extra.py
test_workflow_planner.py      test_workflows_mock.py
```

### 참고
- `workflow_engine.py` (57%)는 외부 의존성(MCP, Scheduler, LLM, S3)이 많아 단위 테스트 한계 존재
- 통합 테스트로 추가 커버리지 확보 권장

</details>

<details>
<summary><b>✅ V2 Phase 2: QA 테스트 완료 (2025-12-30)</b></summary>

### 테스트 결과 요약
전체 145개 테스트 항목 **100% 통과**

| 카테고리 | 항목 수 | 통과 | 상태 |
|----------|---------|------|------|
| 인증 및 로그인 | 6 | 6 | ✅ |
| AI 채팅 | 14 | 14 | ✅ |
| 대시보드 | 13 | 13 | ✅ |
| 워크플로우 | 22 | 22 | ✅ |
| 룰셋 | 18 | 18 | ✅ |
| A/B 테스트 | 14 | 14 | ✅ |
| 학습 (Learning) | 6 | 6 | ✅ |
| 데이터 관리 | 14 | 14 | ✅ |
| 설정 | 14 | 14 | ✅ |
| 통합 시나리오 | 18 | 18 | ✅ |
| 에러 케이스 | 6 | 6 | ✅ |

### 통합 테스트 시나리오
1. **10.1 전체 자동화 플로우**: AI 채팅 → 규칙 생성 → 워크플로우 생성 → 시뮬레이션 ✅
2. **10.2 BI 분석 플로우**: 대시보드 → AI 차트 생성 → 인사이트 → 데이터 스토리 ✅
3. **10.3 A/B 테스트 플로우**: 룰셋 생성 → 실험 생성 → 라이프사이클 (Draft→Running→Completed) ✅

### 검증된 API 엔드포인트 (14개)
- `/api/v1/auth/login` - 로그인
- `/api/v1/agents/chat` - AI 채팅 (규칙/워크플로우 생성)
- `/api/v1/bi/chat` - BI 채팅 (인사이트/스토리)
- `/api/v1/bi/stat-cards` - 통계 카드
- `/api/v1/bi/insights` - 인사이트 목록
- `/api/v1/bi/stories` - 스토리 목록
- `/api/v1/rulesets` - 룰셋 CRUD
- `/api/v1/rulesets/{id}/execute` - 룰셋 실행
- `/api/v1/workflows` - 워크플로우 CRUD
- `/api/v1/experiments` - 실험 CRUD
- `/api/v1/experiments/{id}/start` - 실험 시작
- `/api/v1/experiments/{id}/stats` - 실험 통계
- `/api/v1/sensors/data` - 센서 데이터 (962개 레코드)
- `/api/v1/rag/documents/{id}` - RAG 문서 상세 조회

### 수정된 이슈 (4개)
1. **Admin 비밀번호 불일치** - DB 해시 재설정 (`admin123`)
2. **RAG 문서 상세 API 누락** - GET 엔드포인트 추가
3. **CSV Import 파티션 오류** - 파티션 자동 생성 로직 추가
4. **A/B 실험 Control 그룹** - is_control 플래그 설정

### 문서화
- [TEST_SCENARIOS.md](docs/TEST_SCENARIOS.md) - 상세 체크리스트
- [QA_TEST_REPORT_20251230.md](docs/PROJECT/QA_TEST_REPORT_20251230.md) - 공식 보고서

</details>

<details>
<summary><b>🏢 V2 Phase 3: Multi-Tenant Module Configuration (2026-01-05)</b></summary>

### 구현 배경
B2B SaaS로 제조업 고객사별 커스터마이징 필요 (제약회사 vs 김치공장)
고객사마다 소스코드 분리 시 100개 고객사 = 100번 배포 지옥

### 목표
**One Codebase, Multi-Tenant Configuration**: 하나의 코드로 설정만 다르게

### 구현 내역

#### 1. DB 스키마 확장
| 테이블 | 설명 | 컬럼 |
|--------|------|------|
| `core.industry_profiles` | 산업별 프로필 마스터 | industry_code, name, default_modules, default_kpis |
| `core.module_definitions` | 모듈 정의 마스터 | module_code, name, category, requires_subscription |
| `core.tenant_modules` | 테넌트별 모듈 설정 | tenant_id, module_code, is_enabled, config |
| `core.tenants` (확장) | industry_code FK 추가 | - |

#### 2. 산업 프로필 (4개)
| 코드 | 명칭 | 기본 모듈 |
|------|------|----------|
| `general` | 일반 제조 | dashboard, chat, workflows, data, settings |
| `pharma` | 제약/화학 | + rulesets, quality_pharma, learning |
| `food` | 식품/발효 | + rulesets, quality_food |
| `electronics` | 전자/반도체 | + quality_elec, experiments |

#### 3. 모듈 정의 (11개)
| 카테고리 | 모듈 | 기본 활성화 |
|----------|------|:-----------:|
| **Core** | dashboard, chat, data, settings | ✅ |
| **Feature** | workflows, rulesets, experiments, learning | ⚙️ 설정 가능 |
| **Industry** | quality_pharma, quality_food, quality_elec | ⚙️ 산업별 |

#### 4. Backend
| 컴포넌트 | 설명 | 파일 |
|----------|------|------|
| **SQLAlchemy 모델** | IndustryProfile, ModuleDefinition, TenantModule | `models/tenant_config.py` |
| **TenantConfigService** | 모듈 CRUD, 초기화, 프로필 변경 | `services/tenant_config_service.py` |
| **API Router** | /tenant/* 엔드포인트 (9개) | `routers/tenant_config.py` |

#### 5. Frontend
| 컴포넌트 | 설명 | 파일 |
|----------|------|------|
| **TenantConfigContext** | isModuleEnabled, hasFeature 훅 | `contexts/TenantConfigContext.tsx` |
| **tenantService** | API 클라이언트 | `services/tenantService.ts` |
| **Sidebar** | 동적 모듈 필터링 | `components/layout/Sidebar.tsx` |

#### 6. API 엔드포인트
```
GET  /api/v1/tenant/config              # 테넌트 설정 조회
GET  /api/v1/tenant/modules             # 모듈 목록
POST /api/v1/tenant/modules/enable      # 모듈 활성화 (Admin)
POST /api/v1/tenant/modules/disable     # 모듈 비활성화 (Admin)
PATCH /api/v1/tenant/modules/config     # 모듈 설정 변경 (Admin)
GET  /api/v1/tenant/features            # 기능 플래그
GET  /api/v1/tenant/industries          # 산업 프로필 목록
POST /api/v1/tenant/industry            # 산업 프로필 변경 (Admin)
GET  /api/v1/tenant/modules/{code}/enabled  # 모듈 활성화 여부
```

### 수정/생성 파일
**Backend (신규)**:
- `backend/alembic/versions/005_tenant_modules.py`
- `backend/app/models/tenant_config.py`
- `backend/app/services/tenant_config_service.py`
- `backend/app/routers/tenant_config.py`

**Backend (수정)**:
- `backend/app/models/core.py` - Tenant에 industry_code 추가
- `backend/app/models/__init__.py` - 모델 export
- `backend/app/main.py` - 라우터 등록

**Frontend (신규)**:
- `frontend/src/contexts/TenantConfigContext.tsx`
- `frontend/src/services/tenantService.ts` (확장)

**Frontend (수정)**:
- `frontend/src/components/layout/Sidebar.tsx` - 동적 필터링

### 검증 방법 (How to Test)
```bash
# 1. DB 마이그레이션 실행
cd backend && python -m alembic upgrade head

# 2. 서버 시작
cd backend && uvicorn app.main:app --reload

# 3. 로그인 후 테넌트 설정 조회
curl -X GET http://localhost:8000/api/v1/tenant/config \
  -H "Authorization: Bearer $TOKEN"

# 4. 프론트엔드에서 Sidebar 메뉴 확인
# - Admin: 모든 모듈 표시
# - Member: 활성화된 모듈만 표시

# 5. 모듈 활성화/비활성화 (Admin)
curl -X POST http://localhost:8000/api/v1/tenant/modules/enable \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"module_code": "quality_pharma"}'
```

</details>

---

## 📝 작업 히스토리

### 2026-01-09 (Trust System 100% 완료)

#### 완료된 작업

1. **FeedbackLog 쿼리 버그 수정**
   - `FeedbackLog.ruleset_id` 필드가 존재하지 않아 발생한 버그 수정
   - JudgmentExecution 조인을 통해 간접적으로 ruleset_id 연결
   - `FeedbackLog.log_id` → `FeedbackLog.feedback_id` 오타 수정

2. **Age 컴포넌트 스펙 정합성 개선**
   - 기존: 61일 이상 만점 (단계별 계산)
   - 수정: `min(days_active / 90, 1.0)` 선형 공식 (A-2-5 스펙 준수)

3. **Critical Failure 강등 조건 추가**
   - `_count_recent_critical_failures()` 메서드 신규 추가
   - Level 3 (FULL_AUTO): 최근 7일간 critical failure 0건
   - Level 2 (LOW_RISK_AUTO): 최근 7일간 critical failure 1건까지 허용

#### 수정된 파일
- `backend/app/services/trust_service.py`
  - `_calculate_feedback_component()`: JudgmentExecution 조인 적용
  - `_get_consecutive_negative_feedback()`: JudgmentExecution 조인 적용
  - `_calculate_age_component()`: 90일 선형 공식으로 변경
  - `_count_recent_critical_failures()`: 신규 메서드
  - `evaluate_demotion()`: critical failure 체크 로직 추가

#### 검증 방법
```bash
# 1. Import 테스트
cd backend && python -c "from app.services.trust_service import TrustService; print('OK')"

# 2. 서버 시작 후 Trust API 확인
uvicorn app.main:app --reload
# 로그에서 "V2 Trust router registered" 확인

# 3. Trust API 호출 테스트
curl http://localhost:8000/api/v2/trust/levels
curl http://localhost:8000/api/v2/trust/stats
```

#### Trust System 완성도
| 항목 | Before | After |
|------|:------:|:-----:|
| FeedbackLog 쿼리 | ❌ 에러 | ✅ 정상 |
| Age 컴포넌트 | 61일 만점 | 90일 만점 (스펙 준수) |
| Critical Failure | ❌ 미체크 | ✅ 강등 조건 포함 |
| **완성도** | **90%** | **100%** |

---

### 2026-01-09 (Materialized Views 구현)

#### 완료된 작업

1. **Materialized Views 마이그레이션 생성**
   - `backend/alembic/versions/008_materialized_views.py`
   - 4개 MV: `mv_defect_trend`, `mv_oee_daily`, `mv_line_performance`, `mv_quality_summary`
   - 헬퍼 함수: `bi.refresh_all_mvs()`
   - UNIQUE INDEX 포함 (CONCURRENTLY 리프레시 지원)

2. **MV 리프레시 서비스 구현**
   - `backend/app/services/mv_refresh_service.py` (신규)
   - 30분마다 자동 리프레시 (CONCURRENTLY)
   - 상태 모니터링 및 로깅

3. **stat_card_service MV 연동**
   - OEE, 불량률, 품질률 등 주요 KPI는 MV에서 조회
   - 스키마 참조 수정 (`bi.` → `analytics.` for fact tables)

4. **scheduler_service에 MV 리프레시 job 등록**

#### 수정된 파일
- `backend/alembic/versions/008_materialized_views.py` (신규)
- `backend/app/services/mv_refresh_service.py` (신규)
- `backend/app/services/scheduler_service.py` (수정)
- `backend/app/services/stat_card_service.py` (수정)

#### 검증 방법
```bash
# 1. 마이그레이션 적용
cd backend && alembic upgrade head

# 2. MV 생성 확인
psql -c "SELECT * FROM pg_matviews WHERE schemaname = 'bi';"

# 3. 서버 시작 후 스케줄러 로그 확인
uvicorn app.main:app --reload
# 로그에서 "Registered job: refresh_materialized_views" 확인

# 4. 대시보드 로딩 시간 측정 (Before/After)
```

---

### 2026-01-09 (.gitignore 보안 강화 및 V2 Phase 3 코드 커밋)

#### 완료된 작업

1. **.gitignore 프로젝트 정보 보호 강화**
   - `demo/` - 데모 환경 설정 (.env 포함)
   - `dist*/` - 빌드 결과물
   - `scripts/build_demo*.ps1` - 내부 빌드 스크립트
   - `backend/migrations/` - DB 스키마/시드 데이터
   - `docs/spec-reviews/` - 내부 분석 문서

2. **V2 Phase 3 개발 코드 커밋**
   - Feature Flag API 추가 (`routers/feature_flags.py`)
   - Feature Flag Service 추가 (`services/feature_flag_service.py`)
   - Alembic 마이그레이션 006 (soft delete), 007 (BI 스키마 수정)
   - StatCard 기간별 캐시 버그 수정
   - BI Chat 서비스 개선
   - Frontend 모듈 시스템 V2 Phase 3 업데이트

3. **TASKS.md 최신화**
   - V2 Phase 3 진행 상황 추가
   - 구현 현황 테이블 업데이트 (DEVELOPMENT_PRIORITY_GUIDE.md 기준)
   - Critical Gap 목록 추가

#### 커밋 내역
```
6525d6c ✨ V2 Phase 3: Feature Flags & Module System (WIP)
452fafa 🔒 .gitignore 업데이트: 프로젝트 정보 보호 강화
```

#### 수정된 파일
- `.gitignore` - 보호 항목 추가
- `backend/app/routers/feature_flags.py` (신규)
- `backend/app/services/feature_flag_service.py` (신규)
- `backend/alembic/versions/006_add_deleted_at_column.py` (신규)
- `backend/alembic/versions/007_bi_schema_fixes.py` (신규)
- `frontend/src/App.tsx`, 페이지 컴포넌트들, `agentService.ts`
- `docs/project/TASKS.md` - 최신화

---

### 2026-01-07 (문서 정리 및 AI 가이드라인 업데이트)

#### 완료된 작업

1. **docs 외부 문서 정리**
   - `TASKS.md` → `docs/project/TASKS.md`로 이동
   - `README.md` (루트) 업데이트 - 문서 링크 및 구조 추가
   - `frontend/README.md` 프로젝트 맞춤 내용으로 재작성

2. **AI_GUIDELINES.md 전면 재작성**
   - 목차 추가 (6개 주요 섹션)
   - 규칙 통합 (기존 Rule 0-11 → 신규 Rule 1-6)
   - 프로젝트 현황 테이블 추가
   - 371줄 → 322줄로 간소화

3. **AI_GUIDELINES.md 실제 코드베이스와 동기화**
   - AI 에이전트 구조 업데이트 (8개 파일 반영)
   - V7 Intent 체계 추가 (14개 카테고리)
   - 에이전트 테이블 "주요 기능" 컬럼으로 변경
   - 문서 구조에 추가 프로젝트 문서 반영 (ARCHITECTURE.md, IMPLEMENTATION_GUIDE.md, METRICS_ROADMAP.md)

4. **스펙 문서 검증**
   - AI_GUIDELINES.md와 B-6_AI_Agent_Architecture_Prompt_Spec.md 일치 확인
   - V7 Intent 체계 스펙 문서와 동기화 확인

#### 수정된 파일
- `AI_GUIDELINES.md` - 전면 재작성 + V7 Intent 추가
- `README.md` - 문서 링크 추가
- `frontend/README.md` - 프로젝트 맞춤 내용
- `docs/project/TASKS.md` - 작업 기록 추가

---

## 📌 참고 사항

- **기술 스택**: Tauri v2 + React + FastAPI + PostgreSQL + Redis
- **AI 모델**: Anthropic Claude API (claude-sonnet-4-5-20250929)
- **룰 엔진**: Rhai (Rust 기반)
- **워크플로우**: Custom JSON DSL Executor
