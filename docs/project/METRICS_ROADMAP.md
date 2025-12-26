# TriFlow AI 품질 지표 및 로드맵

> **문서 버전**: 1.0
> **작성일**: 2025-12-26
> **대상 독자**: 기술 리더, CTO
> **관련 문서**: [메인 현황](PROJECT_STATUS.md) | [스펙 비교](SPEC_COMPARISON.md) | [아키텍처](ARCHITECTURE.md) | [구현 가이드](IMPLEMENTATION_GUIDE.md)

---

## 목차

1. [구현 통계](#1-구현-통계)
2. [품질 지표](#2-품질-지표)
3. [향후 과제 및 권장사항](#3-향후-과제-및-권장사항)
4. [부록: 파일 경로](#4-부록-파일-경로)
5. [부록: API 엔드포인트](#5-부록-api-엔드포인트)
6. [부록: 데이터베이스 스키마](#6-부록-데이터베이스-스키마)

---

## 1. 구현 통계

### 1.1 백엔드 통계

| 항목 | 수치 |
|------|-----:|
| **서비스 클래스** | 28개 |
| **API 라우터** | 19개 |
| **데이터 모델** | 66개 |
| **AI 에이전트** | 5개 |
| **프롬프트 템플릿** | 5개 |
| **미들웨어** | 5개 |
| **총 Python 파일** | 80+ 개 |
| **주요 파일 라인 수** | |
| - workflow_engine.py | 6,552줄 |
| - bi_planner.py | 3,200줄 |
| - bi_chat_service.py | 1,800줄 |

### 1.2 프론트엔드 통계

| 항목 | 수치 |
|------|-----:|
| **페이지 컴포넌트** | 9개 |
| **UI 컴포넌트** | 50+ 개 |
| **서비스 클래스** | 17개 |
| **총 TSX 파일** | 60+ 개 |
| **주요 파일 라인 수** | |
| - FlowEditor.tsx | 3,203줄 |
| - DashboardPage.tsx | 1,200줄 |

### 1.3 기능별 구현 현황

| 기능 그룹 | 항목 수 | 완료 | 완료율 |
|----------|--------:|-----:|-------:|
| AI 에이전트 | 5 | 5 | 100% |
| 워크플로우 노드 | 18 | 18 | 100% |
| MCP 도구 | 11 | 11 | 100% |
| API 엔드포인트 | 44 | 44 | 100% |
| 데이터 모델 | 66 | 66 | 100% |

---

## 2. 품질 지표

### 2.1 성능 측정 결과

| 항목 | 목표 (스펙 NFR) | 실측값 | 상태 | 비고 |
|------|----------------|--------|:----:|------|
| Judgment 지연 (캐시) | ≤300ms | 50ms | ✅ | Redis 캐시 hit |
| Judgment 지연 (LLM) | ≤1.5s | 5.3s | ⚠️ | Claude API 지연 포함 |
| BI 계획 생성 | ≤3s | 22.4s | ⚠️ | 복잡 쿼리 시 LLM 지연 |
| MCP 호출 타임아웃 | 5s | 5s | ✅ | 설정값 준수 |
| LLM JSON 파싱 실패율 | <0.5% | <0.3% | ✅ | 구조화된 출력 사용 |

> **참고**: LLM 포함 지연은 Claude API 응답 시간에 의존하며, 캐싱 및 배치 처리로 개선 가능

### 2.2 테스트 결과 (2025-12-23)

**워크플로우 노드 통합 테스트 (13개)**:

| 노드 | 결과 | 실행 시간 | 비고 |
|------|:----:|----------:|------|
| CONDITION | ✅ 성공 | <1초 | - |
| IF_ELSE | ✅ 성공 | <1초 | - |
| LOOP | ✅ 성공 | <1초 | 5회 반복 |
| PARALLEL | ✅ 성공 | <1초 | 3개 병렬 |
| DATA | ✅ 성공 | <1초 | SQL 쿼리 |
| CODE | ✅ 성공 | <1초 | Python 실행 |
| MCP | ✅ 성공 | <1초 | 도구 호출 |
| JUDGMENT | ✅ 성공 | 5.3초 | Claude API |
| BI | ✅ 성공 | 22.4초 | Claude API |
| SWITCH | ✅ 성공 | <1초 | 3개 분기 |
| WAIT | ✅ 성공 | 2초 | 지연 설정 |
| ROLLBACK | ⚠️ 예상된 실패 | - | 이전 버전 없음 |
| APPROVAL | ⏳ 대기 | - | 인간 승인 대기 |

### 2.3 발견된 버그 및 수정 (3건)

| 버그 | 원인 | 수정 내용 |
|------|------|----------|
| MCPCallRequest 모델 호환성 | 필드명 불일치 | 필드명 통일 |
| await on sync function | 동기 함수 await 호출 | async 제거 |
| MCPCallResponse 필드명 | output vs result | result로 통일 |

---

## 3. 향후 과제 및 권장사항

### 3.1 미구현/개선 필요 항목

| 우선순위 | 항목 | 현재 상태 | 권장 조치 |
|:--------:|------|----------|----------|
| **높음** | LLM 지연 최적화 | 5~22초 | 캐싱 강화, 스트리밍 응답 |
| **높음** | 프로덕션 모니터링 | 기본 지표만 | Prometheus + Grafana 연동 |
| **중간** | 멀티테넌트 격리 | 테이블 수준 | 스키마 수준 격리 검토 |
| **중간** | Prompt Tuning 자동화 | 수동 추가 | Few-shot 자동 선별 |
| **낮음** | 모바일 UI | 미지원 | PWA 또는 네이티브 앱 |

### 3.2 추가 개발 권장사항

| 영역 | 권장 기능 | 기대 효과 |
|------|----------|----------|
| **MCP 래퍼 확장** | QMS, WMS, SCM 래퍼 | 품질/물류 시스템 통합 |
| **온프레미스 LLM** | Ollama 지원 | 보안 민감 환경 대응 |
| **고급 분석** | 이상 탐지 모델 | 실시간 품질 예측 |
| **UX 개선** | 음성 인터페이스 | 현장 작업자 편의성 |
| **배포** | Helm Chart | Kubernetes 배포 자동화 |

### 3.3 기술 부채

| 항목 | 설명 | 해결 방안 |
|------|------|----------|
| 테스트 커버리지 | 단위 테스트 부족 | pytest 커버리지 70% 목표 |
| 문서화 | API 문서 자동화 필요 | OpenAPI 스펙 보완 |
| 의존성 관리 | requirements.txt 분리 필요 | dev/prod 분리 |

---

## 4. 부록: 파일 경로

### 백엔드

```
backend/app/
├── agents/
│   ├── meta_router.py          # 의도 분류 및 라우팅
│   ├── judgment_agent.py       # AI 판단 에이전트
│   ├── workflow_planner.py     # 워크플로우 생성
│   ├── bi_planner.py           # BI 분석 (3,200줄)
│   └── learning_agent.py       # 학습 에이전트
├── services/
│   ├── workflow_engine.py      # 워크플로우 엔진 (6,552줄)
│   ├── mcp_toolhub.py          # MCP 서버 관리
│   ├── mcp_proxy.py            # MCP HTTP 프록시
│   ├── bi_service.py           # BI 서비스
│   ├── bi_chat_service.py      # GenBI 채팅
│   ├── stat_card_service.py    # StatCard 계산
│   ├── insight_service.py      # Executive Summary
│   ├── story_service.py        # Data Stories
│   ├── circuit_breaker.py      # 회로 차단기
│   └── judgment_policy.py      # 판단 정책
├── mcp_wrappers/
│   ├── base_wrapper.py         # MCP 래퍼 베이스
│   ├── mes_wrapper.py          # MES 래퍼 (5개 도구)
│   ├── erp_wrapper.py          # ERP 래퍼 (6개 도구)
│   └── run_wrapper.py          # CLI 실행 스크립트
├── routers/
│   ├── workflows.py            # 워크플로우 API (66KB)
│   ├── bi.py                   # BI API (90KB)
│   └── mcp.py                  # MCP API
└── models/
    ├── core.py                 # 핵심 모델 (65KB, 50+ 클래스)
    ├── bi.py                   # BI 모델 (33KB, 23개 클래스)
    └── statcard.py             # StatCard 모델
```

### 프론트엔드

```
frontend/src/
├── components/
│   ├── workflow/
│   │   └── FlowEditor.tsx      # 비주얼 에디터 (3,203줄)
│   ├── pages/
│   │   ├── DashboardPage.tsx   # 대시보드
│   │   ├── WorkflowsPage.tsx   # 워크플로우 관리
│   │   └── LearningPage.tsx    # 학습 대시보드
│   └── dashboard/
│       ├── StatCard.tsx        # KPI 카드
│       └── BIChatPanel.tsx     # GenBI 채팅
└── services/
    ├── workflowService.ts      # 워크플로우 API 클라이언트
    ├── biService.ts            # BI API 클라이언트
    └── statCardService.ts      # StatCard API 클라이언트
```

---

## 5. 부록: API 엔드포인트

| 카테고리 | 엔드포인트 | 메서드 | 설명 |
|----------|-----------|:------:|------|
| **Workflows** | `/api/v1/workflows` | GET/POST | 워크플로우 CRUD |
| | `/api/v1/workflows/{id}/execute` | POST | 워크플로우 실행 |
| | `/api/v1/workflows/{id}/instances` | GET | 인스턴스 목록 |
| **BI** | `/api/v1/bi/analyze` | POST | 자연어 분석 |
| | `/api/v1/bi/dashboards` | GET/POST | 대시보드 CRUD |
| | `/api/v1/bi/statcards` | GET/POST | StatCard CRUD |
| **MCP** | `/api/v1/mcp/servers` | GET/POST | MCP 서버 관리 |
| | `/api/v1/mcp/call` | POST | 도구 호출 |
| **Agents** | `/api/v1/agents/chat` | POST | 채팅 메시지 |
| | `/api/v1/agents/intent` | POST | 의도 분류 |
| **Rulesets** | `/api/v1/rulesets` | GET/POST | 규칙셋 CRUD |
| | `/api/v1/rulesets/{id}/versions` | GET/POST | 버전 관리 |

---

## 6. 부록: 데이터베이스 스키마

### 핵심 테이블

| 테이블 | 설명 | 주요 컬럼 |
|--------|------|----------|
| `tenants` | 테넌트 (조직) | id, name, subscription_plan |
| `users` | 사용자 | id, tenant_id, role, email |
| `workflows` | 워크플로우 정의 | id, tenant_id, dsl_json, version |
| `workflow_instances` | 워크플로우 실행 | id, workflow_id, status, context |
| `rulesets` | 규칙셋 | id, tenant_id, name, script |
| `judgment_executions` | 판단 실행 로그 | id, workflow_id, result, confidence |

### BI 테이블

| 테이블 | 설명 |
|--------|------|
| `raw_mes_production` | MES 생산 원본 데이터 |
| `dim_date`, `dim_line`, `dim_product` | 차원 테이블 |
| `fact_daily_production`, `fact_daily_defect` | 팩트 테이블 |
| `bi_datasets`, `bi_metrics`, `bi_dashboards` | BI 카탈로그 |

### MCP 테이블

| 테이블 | 설명 |
|--------|------|
| `mcp_servers` | 등록된 MCP 서버 |
| `mcp_tools` | 서버별 도구 목록 |
| `mcp_call_logs` | 도구 호출 로그 |

---

## 문서 이력

| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2025-12-26 | AI 개발팀 | PROJECT_STATUS.md에서 분리 |

---

**문서 끝**
