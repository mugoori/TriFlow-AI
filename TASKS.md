# TriFlow AI - 작업 목록 (TASKS)

> **최종 업데이트**: 2025-12-26
> **현재 Phase**: MVP v0.1.0 릴리즈 완료 → V1 개발 완료 → V2 Phase 2 진행 중
> **현재 브랜치**: `develop`

---

## 📊 Project Dashboard

### 📅 Product Roadmap
| Milestone | Goal | Status | Progress |
|-----------|------|--------|----------|
| **MVP** | PC 설치형 데스크톱 앱 (Core + Chat UI) | ✅ v0.1.0 | ██████████ 100% |
| **V1** | Builder UI & Learning & 외부연동 & 보안 | ✅ 완료 | ██████████ 100% |
| **V2** | Advanced Workflow & MCP 연동 | 🔄 진행중 | ████████░░ 80% |

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
│   │   │   ├── workflow_engine.py    # 워크플로우 엔진 (6,552줄)
│   │   │   ├── mcp_proxy.py          # MCP HTTP 프록시
│   │   │   ├── mcp_toolhub.py        # MCP 서버 레지스트리
│   │   │   └── ...
│   │   ├── mcp_wrappers/         # MCP 래퍼 서버
│   │   │   ├── base_wrapper.py       # 베이스 클래스
│   │   │   ├── mes_wrapper.py        # MES 래퍼
│   │   │   └── erp_wrapper.py        # ERP 래퍼
│   │   ├── routers/              # API 엔드포인트
│   │   ├── models/               # Pydantic 모델
│   │   ├── tools/                # 에이전트 도구
│   │   └── prompts/              # 프롬프트 템플릿
│   └── migrations/               # DB 마이그레이션
│
├── frontend/                     # Tauri + React 프론트엔드
│   ├── src/
│   │   ├── components/
│   │   │   ├── workflow/
│   │   │   │   └── FlowEditor.tsx    # 비주얼 에디터 (3,203줄)
│   │   │   ├── ruleset/              # 룰셋 편집기
│   │   │   ├── pages/                # 페이지 컴포넌트
│   │   │   └── layout/               # 레이아웃
│   │   └── services/             # API 클라이언트
│   └── src-tauri/                # Tauri (Rust)
│
├── docs/                         # 문서
│   ├── specs/                    # 기술 명세서
│   └── archive/                  # 아카이브
│
├── AI_GUIDELINES.md              # AI 개발 가이드라인
├── TASKS.md                      # 작업 목록 (현재 파일)
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

---

## 📌 참고 사항

- **기술 스택**: Tauri v2 + React + FastAPI + PostgreSQL + Redis
- **AI 모델**: Anthropic Claude API (claude-sonnet-4-5-20250929)
- **룰 엔진**: Rhai (Rust 기반)
- **워크플로우**: Custom JSON DSL Executor
