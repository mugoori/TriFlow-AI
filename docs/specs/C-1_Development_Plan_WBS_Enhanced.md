# C-1. Development Plan & WBS - Enhanced

## 문서 정보
- **문서 ID**: C-1
- **버전**: 3.0 (V7 Intent + Orchestrator)
- **최종 수정일**: 2025-12-16
- **상태**: Active Development
- **관련 문서**:
  - A-1 Product Vision & Scope
  - A-2 System Requirements Spec
  - B-1 System Architecture
  - B-2 Module/Service Design
  - C-2 Coding Standard
  - C-3 Test Plan

## 목차
1. [프로젝트 개요](#1-프로젝트-개요)
2. [개발 방법론](#2-개발-방법론)
3. [WBS (Work Breakdown Structure)](#3-wbs-work-breakdown-structure)
4. [스프린트 계획](#4-스프린트-계획)
5. [리소스 계획](#5-리소스-계획)
6. [일정 및 마일스톤](#6-일정-및-마일스톤)
7. [리스크 관리](#7-리스크-관리)
8. [품질 관리](#8-품질-관리)
9. [산출물 및 DoD](#9-산출물-및-dod)

---

## 1. 프로젝트 개요

### 1.1 프로젝트 목표
**AI Factory Decision Engine MVP**를 3개월 내에 개발하여 파일럿 고객사 10개에 배포한다.

**주요 목표**:
- Judgment Engine (Rule + LLM Hybrid) 정확도 > 80%
- Workflow Engine (15 노드 타입) 안정성 > 99%
- V7 Intent Router (14개 Intent + 15개 Legacy 매핑) 정확도 > 90%
- Orchestrator (자동 Workflow Plan 생성) 성공률 > 85%
- BI 플래너 (자연어 → SQL) 파싱 성공률 > 90%
- 시스템 가용성 > 99% (MVP 기준)

### 1.2 프로젝트 제약사항
- **기간**: 3개월 (12주, 2025-12-01 ~ 2026-02-28)
- **인력**: 총 10명 (BE 3, FE 1, ML 1, DE 1, DevOps 1, QA 1, PM 1, SE 1)
- **예산**: $150,000 (인건비 $120,000, 인프라 $20,000, 기타 $10,000)
- **기술**: Python, React, PostgreSQL, Redis, Kubernetes

---

## 2. 개발 방법론

### 2.1 Scrum/Agile 적용

**스프린트 길이**: 2주 (총 6개 스프린트)

**Scrum 이벤트**:
- **Sprint Planning**: 스프린트 시작일 (2시간)
- **Daily Standup**: 매일 오전 10시 (15분)
- **Sprint Review**: 스프린트 마지막일 (1시간)
- **Sprint Retrospective**: Sprint Review 직후 (30분)

**역할**:
- **Product Owner**: PM (우선순위 결정, 백로그 관리)
- **Scrum Master**: SE (프로세스 촉진, 장애물 제거)
- **Development Team**: BE, FE, ML, DE, DevOps, QA (7명)

### 2.2 Definition of Done (DoD)

각 사용자 스토리는 다음 조건을 만족해야 완료로 간주한다:

- [ ] 코드 작성 완료 (Coding Standard 준수)
- [ ] 단위 테스트 작성 및 통과 (커버리지 > 80%)
- [ ] 코드 리뷰 완료 (최소 1명 승인)
- [ ] 통합 테스트 통과
- [ ] 문서 업데이트 (API 문서, README)
- [ ] QA 테스트 통과
- [ ] Staging 환경 배포 성공
- [ ] Product Owner 수락 (Acceptance)

---

## 3. WBS (Work Breakdown Structure)

### 3.1 WBS 전체 구조

```
AI Factory Decision Engine (MVP)
│
├─ 1. 프로젝트 관리
│   ├─ 1.1 프로젝트 계획 수립
│   ├─ 1.2 요구사항 문서화
│   ├─ 1.3 주간 스프린트 미팅
│   └─ 1.4 리스크 관리
│
├─ 2. 설계 및 아키텍처
│   ├─ 2.1 시스템 아키텍처 설계 (B-1)
│   ├─ 2.2 모듈/서비스 설계 (B-2)
│   ├─ 2.3 DB 스키마 설계 (B-3)
│   ├─ 2.4 API 인터페이스 설계 (B-4)
│   ├─ 2.5 Workflow DSL 설계 (B-5)
│   └─ 2.6 AI/Prompt 설계 (B-6)
│
├─ 3. Backend 개발
│   ├─ 3.1 Judgment Service
│   ├─ 3.2 Workflow Service (15 노드 타입)
│   ├─ 3.3 BI Service
│   ├─ 3.4 Learning Service
│   ├─ 3.5 MCP ToolHub
│   ├─ 3.6 Data Hub
│   ├─ 3.7 Chat Service
│   ├─ 3.8 Intent Router (V7 체계)
│   └─ 3.9 Orchestrator Service
│
├─ 4. Frontend 개발
│   ├─ 4.1 Web Dashboard
│   ├─ 4.2 Judgment UI
│   ├─ 4.3 Workflow Editor
│   ├─ 4.4 BI Query UI
│   ├─ 4.5 Admin Portal
│   └─ 4.6 Slack Bot
│
├─ 5. 데이터 및 통합
│   ├─ 5.1 DB 스키마 구현
│   ├─ 5.2 ETL 파이프라인
│   ├─ 5.3 ERP/MES 커넥터
│   ├─ 5.4 pgvector RAG 구현
│   └─ 5.5 Pre-aggregation Views
│
├─ 6. AI/ML 개발
│   ├─ 6.1 Rule 엔진 (Rhai) 통합
│   ├─ 6.2 LLM 클라이언트 (Claude Haiku/Sonnet/Opus)
│   ├─ 6.3 Prompt 템플릿 관리 (V7 Intent)
│   ├─ 6.4 Rule 자동 추출 (Decision Tree)
│   ├─ 6.5 Canary 배포 로직
│   ├─ 6.6 V7 Intent 분류기 개발
│   └─ 6.7 Orchestrator Plan Generator
│
├─ 7. DevOps 및 인프라
│   ├─ 7.1 Kubernetes 클러스터 구축
│   ├─ 7.2 CI/CD 파이프라인
│   ├─ 7.3 Monitoring (Prometheus, Grafana)
│   ├─ 7.4 Logging (Loki)
│   ├─ 7.5 Backup & DR
│   └─ 7.6 보안 설정 (TLS, Vault)
│
├─ 8. 테스트 및 QA
│   ├─ 8.1 단위 테스트
│   ├─ 8.2 통합 테스트
│   ├─ 8.3 E2E 테스트
│   ├─ 8.4 성능 테스트
│   ├─ 8.5 보안 테스트
│   └─ 8.6 UAT (User Acceptance Test)
│
└─ 9. 배포 및 운영 준비
    ├─ 9.1 Production 환경 구축
    ├─ 9.2 데이터 시딩
    ├─ 9.3 사용자 교육
    ├─ 9.4 운영 매뉴얼 작성
    └─ 9.5 Go-Live
```

### 3.2 WBS 상세 (주요 작업)

#### WBS 3.1: Judgment Service 개발

| Task ID | 작업명 | 기간 | 담당 | 산출물 |
|---------|--------|------|------|--------|
| 3.1.1 | InputValidator 구현 | 2일 | BE1 | input_validator.py, 단위 테스트 |
| 3.1.2 | RhaiEngine 통합 | 3일 | BE1 | rhai_engine.py, 통합 테스트 |
| 3.1.3 | OpenAIClient 구현 | 3일 | BE1, ML1 | openai_client.py, 재시도 로직 |
| 3.1.4 | ResultAggregator 구현 | 2일 | BE1 | result_aggregator.py, Hybrid 로직 |
| 3.1.5 | CacheManager 구현 | 2일 | BE2 | cache_manager.py, Redis 통합 |
| 3.1.6 | JudgmentService 통합 | 2일 | BE1 | judgment_service.py, E2E 테스트 |
| 3.1.7 | Simulation 기능 구현 | 2일 | BE1 | simulation.py, Replay 로직 |

**총 기간**: 2주
**의존성**: B-2-1 (설계 문서), B-3-1 (DB 스키마)

#### WBS 3.2: Workflow Service 개발 (15 노드 타입)

| Task ID | 작업명 | 기간 | 담당 | 산출물 |
|---------|--------|------|------|--------|
| 3.2.1 | DSLParser 구현 | 3일 | BE2 | dsl_parser.py, JSON Schema 검증 |
| 3.2.2 | P0 NodeExecutor 구현 (DATA, JUDGMENT, CODE, SWITCH, ACTION) | 4일 | BE2 | node_executors_p0.py |
| 3.2.3 | P1 NodeExecutor 구현 (BI, MCP, TRIGGER, WAIT, APPROVAL) | 3일 | BE2 | node_executors_p1.py |
| 3.2.4 | P2 NodeExecutor 구현 (PARALLEL, COMPENSATION, DEPLOY, ROLLBACK, SIMULATE) | 3일 | BE2 | node_executors_p2.py |
| 3.2.5 | StateManager 구현 | 2일 | BE2 | state_manager.py, DB 영속화 |
| 3.2.6 | CircuitBreaker 구현 | 2일 | BE2 | circuit_breaker.py |
| 3.2.7 | WorkflowExecutor 통합 | 2일 | BE2 | workflow_executor.py, E2E 테스트 |

**총 기간**: 2.5주
**의존성**: B-2-1, B-5 (DSL 스펙)

**15 노드 타입 우선순위**:
- **P0 (핵심)**: DATA, JUDGMENT, CODE, SWITCH, ACTION
- **P1 (확장)**: BI, MCP, TRIGGER, WAIT, APPROVAL
- **P2 (고급)**: PARALLEL, COMPENSATION, DEPLOY, ROLLBACK, SIMULATE

#### WBS 3.8: Intent Router 개발 (V7 체계)

| Task ID | 작업명 | 기간 | 담당 | 산출물 |
|---------|--------|------|------|--------|
| 3.8.1 | V7 Intent 스키마 정의 | 1일 | BE1, ML1 | schema.py (14개 Intent 정의) |
| 3.8.2 | LLM Intent 분류기 구현 | 2일 | ML1 | intent_classifier.py |
| 3.8.3 | Slot 추출기 구현 | 2일 | ML1 | slot_extractor.py |
| 3.8.4 | Legacy Intent 매핑 | 1일 | BE1 | legacy_mapper.py (15개 매핑) |
| 3.8.5 | Route Target 결정 로직 | 1일 | BE1 | route_resolver.py |
| 3.8.6 | Intent Router 통합 | 2일 | BE1 | router.py, E2E 테스트 |

**총 기간**: 1.5주
**의존성**: B-6 (AI Agent Architecture)

**V7 Intent 체계 (14개)**:
- **정보 조회**: CHECK, TREND, COMPARE, RANK
- **분석**: FIND_CAUSE, DETECT_ANOMALY, PREDICT, WHAT_IF
- **액션**: REPORT, NOTIFY
- **대화 제어**: CONTINUE, CLARIFY, STOP, SYSTEM

#### WBS 3.9: Orchestrator Service 개발

| Task ID | 작업명 | 기간 | 담당 | 산출물 |
|---------|--------|------|------|--------|
| 3.9.1 | Plan Generator 구현 | 3일 | BE1, ML1 | plan_generator.py |
| 3.9.2 | Route→Node 매핑 로직 | 2일 | BE1 | route_node_mapper.py |
| 3.9.3 | Workflow DSL 생성기 | 2일 | BE2 | dsl_generator.py |
| 3.9.4 | Plan Executor 구현 | 2일 | BE2 | plan_executor.py |
| 3.9.5 | Orchestrator 통합 | 2일 | BE1, BE2 | orchestrator.py, E2E 테스트 |

**총 기간**: 1.5주
**의존성**: 3.2 (Workflow Service), 3.8 (Intent Router)

**Orchestrator 파이프라인**:
```
Intent Router → Orchestrator → Workflow Engine
     ↓              ↓               ↓
  V7 Intent   Plan Generation   Execution
```

#### WBS 4.3: Workflow Visual Editor 개발

| Task ID | 작업명 | 기간 | 담당 | 산출물 |
|---------|--------|------|------|--------|
| 4.3.1 | Canvas 컴포넌트 구현 | 3일 | FE1 | WorkflowCanvas.tsx |
| 4.3.2 | Node Palette 구현 | 2일 | FE1 | NodePalette.tsx |
| 4.3.3 | Drag & Drop 로직 | 3일 | FE1 | useDragDrop.ts |
| 4.3.4 | Node 설정 폼 | 3일 | FE1 | NodeConfigForm.tsx |
| 4.3.5 | DSL 검증 UI | 2일 | FE1 | ValidationPanel.tsx |
| 4.3.6 | 저장 및 실행 | 1일 | FE1 | WorkflowActions.tsx |

**총 기간**: 2주
**의존성**: 4.1 (Base UI), 3.2 (Workflow Service API)

---

## 4. 스프린트 계획

### 4.1 Sprint 1 (Week 1-2): 인프라 및 코어 서비스

**목표**: 인프라 구축, Judgment Service 개발

**백로그**:
- [x] Kubernetes 클러스터 구축 (DevOps)
- [x] PostgreSQL, Redis 설치 (DevOps)
- [x] DB 스키마 마이그레이션 (BE, DE)
- [x] Judgment Service 개발 (BE1)
  - InputValidator, RhaiEngine, OpenAIClient
- [x] 기본 Monitoring 설정 (Prometheus, Grafana)

**산출물**:
- Kubernetes 클러스터 (Staging)
- judgment-service v0.1.0
- DB 스키마 v1.0.0
- Grafana 대시보드 (기본)

**DoD**:
- Judgment API 응답 성공 (Postman 테스트)
- 단위 테스트 커버리지 > 70%
- Staging 배포 성공

---

### 4.2 Sprint 2 (Week 3-4): Workflow, Intent Router 및 BI

**목표**: Workflow Service (15 노드), V7 Intent Router, BI Service 개발

**백로그**:
- [x] Workflow Service 개발 (BE2)
  - DSLParser, P0/P1 NodeExecutor (15개 노드 타입)
  - WorkflowExecutor, StateManager
- [x] V7 Intent Router 개발 (BE1, ML1)
  - V7 Intent 스키마 (14개), Slot 추출
  - Legacy Intent 매핑 (15개)
- [x] BI Service 개발 (BE3)
  - LLMBIPlanner, SQLGenerator, QueryExecutor
- [x] MCP ToolHub 기본 구조 (BE2)
- [x] Web Dashboard 기본 구조 (FE1)

**산출물**:
- workflow-service v0.1.0 (15 노드 타입)
- intent-router v0.1.0 (V7 체계)
- bi-service v0.1.0
- mcp-hub v0.1.0
- web-ui v0.1.0 (기본 레이아웃)

**DoD**:
- Workflow 15 노드 타입 E2E 테스트 통과
- V7 Intent 분류 정확도 > 85%
- BI 자연어 쿼리 성공
- Web UI 로그인 및 대시보드 표시

---

### 4.3 Sprint 3 (Week 5-6): Orchestrator 통합 및 UI

**목표**: Orchestrator 개발, 서비스 통합, UI 개발

**백로그**:
- [x] Orchestrator Service 개발 (BE1, BE2)
  - Plan Generator, Route→Node 매핑
  - Workflow DSL 자동 생성
- [x] Judgment UI 구현 (FE1)
  - Judgment 실행 폼, 결과 카드, 피드백 버튼
- [x] Workflow Editor 구현 (FE1)
  - Visual Editor, 15개 Node Palette, DSL 검증
- [x] BI Query UI 구현 (FE1)
  - 자연어 입력, 차트 렌더링
- [x] Chat Service 통합 (BE3)
  - V7 Intent Router 연동, Orchestrator 연결
- [x] ERP/MES 커넥터 구현 (DE1)

**산출물**:
- orchestrator-service v0.1.0
- web-ui v0.2.0 (Judgment, Workflow, BI 화면)
- chat-service v0.1.0 (V7 통합)
- 커넥터 2개 (ERP, MES)

**DoD**:
- V7 Intent → Orchestrator → Workflow 파이프라인 동작
- 모든 UI 화면 렌더링 성공
- Orchestrator 자동 Plan 생성 성공률 > 80%
- 커넥터 헬스 체크 성공

---

### 4.4 Sprint 4 (Week 7-8): Learning 및 배포

**목표**: Learning Pipeline, Canary 배포 기능

**백로그**:
- [x] Learning Service 개발 (ML1, BE1)
  - FeedbackCollector, SampleCurator, RuleExtractor
- [x] Canary Deployer 구현 (ML1, BE1)
  - TrafficRouter, MetricsCollector, AutoRollback
- [x] Admin Portal 구현 (FE1)
  - 사용자 관리, 커넥터 설정, Rule 배포
- [x] Slack Bot 구현 (BE3)

**산출물**:
- learning-service v0.1.0
- admin-portal v0.1.0
- slack-bot v0.1.0

**DoD**:
- Rule 자동 추출 성공 (Precision > 80%)
- Canary 배포 및 자동 롤백 동작
- Slack 멘션 → Judgment 응답 성공

---

### 4.5 Sprint 5 (Week 9-10): 성능 및 보안

**목표**: 성능 최적화, 보안 강화, 부하 테스트

**백로그**:
- [x] 성능 최적화 (BE 전체)
  - Connection Pool, Pre-aggregation, Cache
- [x] 보안 강화 (DevOps, BE 전체)
  - TLS, JWT, PII 마스킹, RBAC
- [x] 부하 테스트 (QA1)
  - Judgment 50 TPS, Workflow 20 TPS
- [x] 보안 스캔 (QA1)
  - OWASP ZAP, SQL Injection 테스트

**산출물**:
- 성능 테스트 보고서
- 보안 스캔 보고서
- 최적화 완료 (P95 목표 달성)

**DoD**:
- Judgment P95 < 2.5초
- BI P95 < 3초
- 보안 스캔 Critical 취약점 0개

---

### 4.6 Sprint 6 (Week 11-12): UAT 및 배포

**목표**: 사용자 승인 테스트, Production 배포

**백로그**:
- [x] UAT 시나리오 테스트 (QA1, PM1)
  - 10개 핵심 시나리오
- [x] 버그 수정 (BE, FE 전체)
- [x] Production 환경 구축 (DevOps1)
- [x] 데이터 시딩 (DE1)
- [x] 사용자 교육 자료 작성 (PM1)
- [x] Go-Live (전체 팀)

**산출물**:
- UAT 테스트 보고서
- Production 환경 (AWS EKS)
- 사용자 매뉴얼 v1.0
- Release 1.0 (MVP)

**DoD**:
- UAT 시나리오 100% 통과
- Production 배포 성공
- 파일럿 고객사 10개 온보딩 완료

---

## 5. 리소스 계획

### 5.1 팀 구성 및 역할

| 역할 | 인원 | 책임 | 주요 작업 |
|------|------|------|----------|
| **Product Manager** | 1 | 제품 기획, 백로그 관리, 고객 소통 | 요구사항 정의, Sprint Planning, Review |
| **Software Engineer** | 1 | 아키텍처 설계, 기술 리드 | 아키텍처 문서, 코드 리뷰, 기술 결정 |
| **Backend Engineer** | 3 | 서비스 개발 (Python FastAPI) | Judgment, Workflow, BI, Learning, MCP Hub |
| **Frontend Engineer** | 1 | Web UI 개발 (React) | Dashboard, Workflow Editor, BI UI |
| **ML Engineer** | 1 | AI/ML 개발, Prompt 관리 | Rule 추출, LLM 통합, Canary 배포 |
| **Data Engineer** | 1 | ETL, DB 최적화 | 스키마 구현, ETL 파이프라인, Pre-agg |
| **DevOps Engineer** | 1 | 인프라, CI/CD, 모니터링 | Kubernetes, Prometheus, CI/CD, 백업 |
| **QA Engineer** | 1 | 테스트, 품질 보증 | 단위/통합/E2E 테스트, 부하 테스트 |

**총 인원**: 10명

### 5.2 예산 계획 (3개월)

| 항목 | 세부 | 비용 (USD) |
|------|------|-----------|
| **인건비** | 10명 × 3개월 × $4,000/월 | $120,000 |
| **인프라 (AWS)** | Staging + Production (3개월) | $12,000 |
| **LLM API** | OpenAI API (개발/테스트) | $3,000 |
| **도구/라이선스** | GitHub, Slack, Postman | $1,000 |
| **교육/컨퍼런스** | 팀 교육, 기술 컨퍼런스 | $2,000 |
| **비상 예비비** | 예상치 못한 비용 (10%) | $12,000 |
| **총 예산** | - | **$150,000** |

---

## 6. 일정 및 마일스톤

### 6.1 전체 일정 (Gantt Chart)

```
Week    1    2    3    4    5    6    7    8    9   10   11   12
────────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┤
Sprint  │ S1 │    │ S2 │    │ S3 │    │ S4 │    │ S5 │    │ S6 │
────────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┤
Infra   ██████
Judgment██████████
Workflow      ██████████
BI            ██████████
Frontend              ████████████
Learning                      ██████████
Security                              ██████████
UAT                                           ████████████
Deploy                                                    ██████
```

### 6.2 주요 마일스톤

| 마일스톤 | 날짜 | 주요 산출물 |
|---------|------|------------|
| **M1: 인프라 구축 완료** | Week 2 | Kubernetes, PostgreSQL, Redis |
| **M2: Judgment Service 완료** | Week 2 | judgment-service v0.1.0 |
| **M3: Workflow Service 완료** | Week 4 | workflow-service v0.1.0 |
| **M4: BI Service 완료** | Week 4 | bi-service v0.1.0 |
| **M5: Web UI 완료** | Week 6 | web-ui v0.2.0 |
| **M6: Learning Service 완료** | Week 8 | learning-service v0.1.0 |
| **M7: 성능/보안 테스트 완료** | Week 10 | 테스트 보고서 |
| **M8: UAT 완료** | Week 11 | UAT 승인 |
| **M9: Go-Live** | Week 12 | Release 1.0 (MVP) |

### 6.3 크리티컬 패스 (Critical Path)

```
요구사항 → 설계 → Judgment → Workflow → BI → 통합 → UAT → Go-Live
```

**크리티컬 패스 작업**:
1. WBS 2.1~2.6 (설계 문서 작성) - Week 1
2. WBS 3.1 (Judgment Service) - Week 2
3. WBS 3.2 (Workflow Service) - Week 3-4
4. WBS 3.3 (BI Service) - Week 3-4
5. WBS 4.1~4.4 (Frontend) - Week 5-6
6. WBS 8.6 (UAT) - Week 11
7. WBS 9.5 (Go-Live) - Week 12

**총 기간**: 12주 (슬랙 없음, 높은 리스크)

---

## 7. 리스크 관리

### 7.1 리스크 목록 및 대응 전략

| 리스크 ID | 리스크 설명 | 확률 | 영향 | 점수 | 완화 전략 | 컨틴전시 플랜 |
|----------|------------|------|------|------|----------|-------------|
| **R001** | LLM API 장애/비용 폭증 | 중 (30%) | 높음 | 15 | Rule 우선 사용, 캐싱, 여러 LLM 제공자 | Fallback to Rule Only, 예산 증액 |
| **R002** | Kubernetes 운영 미숙 | 중 (30%) | 중 | 9 | DevOps 교육, Managed Kubernetes (EKS) | Docker Compose 대체 |
| **R003** | 프론트엔드 개발 지연 | 중 (40%) | 중 | 12 | 초기 Figma 프로토타입, 컴포넌트 라이브러리 | 외주 투입 (1명) |
| **R004** | 데이터 품질 낮음 | 높음 (50%) | 중 | 15 | 데이터 품질 검사, 샘플 데이터 제공 | 수동 데이터 정제 |
| **R005** | Rule 작성 복잡도 | 중 (40%) | 중 | 12 | Rule 템플릿, 자동 추출, Visual Builder | 외부 전문가 컨설팅 |
| **R006** | 보안 취약점 발견 | 낮음 (20%) | 높음 | 10 | OWASP 가이드 준수, 정기 스캔 | 보안 전문가 투입 |
| **R007** | 핵심 인력 이탈 | 낮음 (10%) | 높음 | 5 | 문서화, 지식 공유, 백업 인력 | 외주 투입 |

**리스크 점수**: 확률 (%) × 영향 (낮음=1, 중=2, 높음=5)

### 7.2 리스크 모니터링

**주간 리스크 리뷰**:
- 매주 금요일 Sprint Retrospective 시 리스크 상태 확인
- 새로운 리스크 추가, 완화 전략 업데이트
- 높은 점수 리스크 (> 10) 집중 모니터링

---

## 8. 품질 관리

### 8.1 품질 목표

| 항목 | 목표 | 측정 방법 |
|------|------|----------|
| **코드 커버리지** | > 80% (단위 테스트) | pytest-cov |
| **버그 밀도** | < 5 bugs/KLOC | Jira 버그 추적 |
| **코드 리뷰율** | 100% | GitHub PR 통계 |
| **정적 분석 이슈** | 0개 (Critical) | pylint, mypy, ESLint |
| **보안 취약점** | 0개 (Critical) | OWASP ZAP |

### 8.2 품질 프로세스

#### 8.2.1 코드 품질

**도구**:
- **Python**: pylint, mypy, black (포맷팅), isort (import 정렬)
- **TypeScript**: ESLint, Prettier
- **Pre-commit Hook**: 커밋 전 자동 검사

**기준**:
- pylint 점수 > 8.0/10
- mypy 타입 체크 100% 통과
- ESLint 에러 0개

#### 8.2.2 테스트 전략

| 테스트 타입 | 커버리지 목표 | 책임 | 도구 |
|------------|--------------|------|------|
| **단위 테스트** | > 80% | 개발자 | pytest, Jest |
| **통합 테스트** | 주요 API 100% | 개발자, QA | pytest, Postman |
| **E2E 테스트** | 핵심 시나리오 10개 | QA | Playwright, Cypress |
| **성능 테스트** | 부하/스트레스 | QA | Locust, k6 |
| **보안 테스트** | OWASP Top 10 | QA | OWASP ZAP, Bandit |

#### 8.2.3 코드 리뷰

**프로세스**:
1. 개발자가 Pull Request 생성
2. 최소 1명의 리뷰어 승인 필요
3. CI 테스트 통과 (단위, lint, 타입 체크)
4. 리뷰어 승인 후 Merge

**체크리스트**:
- [ ] 코드가 Coding Standard (C-2) 준수
- [ ] 단위 테스트 작성 및 통과
- [ ] 에러 처리 적절 (try-except, 로그)
- [ ] 보안 이슈 없음 (SQL Injection, XSS 등)
- [ ] 성능 고려 (N+1 쿼리, 메모리 누수)

---

## 9. 산출물 및 DoD

### 9.1 주요 산출물

#### 9.1.1 문서 (Documentation)

| 문서 | 상태 | 담당 |
|------|------|------|
| A-1 Product Vision & Scope | ✅ 완료 | PM |
| A-2 System Requirements (4 files) | ✅ 완료 | SE, PM |
| A-3 Use Case & User Story | ✅ 완료 | PM, SE |
| B-1 System Architecture (4 files) | ✅ 완료 | SE |
| B-2 Module/Service Design (3 files) | ✅ 완료 | SE, BE |
| B-3 Data/DB Schema (4 files) | ✅ 완료 | DE, SE |
| B-4 API Interface Spec | ✅ 완료 | BE, SE |
| B-5 Workflow/State Machine Spec | ✅ 완료 | SE, BE |
| B-6 AI/Agent/Prompt Spec | ✅ 완료 | ML, SE |
| C-1 Development Plan & WBS | 🚧 진행 중 | PM |
| C-2 Coding Standard | ⏳ 대기 | SE |
| C-3 Test Plan & QA Strategy | ⏳ 대기 | QA, SE |
| C-4 Performance & Capacity | ⏳ 대기 | DevOps, SE |
| C-5 Security & Compliance | ⏳ 대기 | SE, QA |
| D-1 DevOps & Infrastructure | ⏳ 대기 | DevOps |
| D-2 Monitoring & Logging | ⏳ 대기 | DevOps |
| D-3 Operation Runbook | ⏳ 대기 | DevOps, BE |
| D-4 User/Admin Guide | ⏳ 대기 | PM |

#### 9.1.2 소프트웨어

| 컴포넌트 | 버전 (MVP) | 기술 스택 | 담당 |
|---------|-----------|----------|------|
| **judgment-service** | v1.0.0 | Python, FastAPI, Rhai | BE1, ML1 |
| **workflow-service** | v1.0.0 | Python, FastAPI (15 노드) | BE2 |
| **intent-router** | v1.0.0 | Python, FastAPI, Claude API (V7) | BE1, ML1 |
| **orchestrator-service** | v1.0.0 | Python, FastAPI, Claude API | BE1, BE2 |
| **bi-service** | v1.0.0 | Python, FastAPI, SQLAlchemy | BE3, DE1 |
| **learning-service** | v1.0.0 | Python, FastAPI, scikit-learn | ML1, BE1 |
| **mcp-hub** | v1.0.0 | Python, FastAPI | BE2 |
| **chat-service** | v1.0.0 | Python, FastAPI | BE3 |
| **data-hub** | v1.0.0 | Python, FastAPI, Alembic | DE1 |
| **web-ui** | v1.0.0 | React, TypeScript, Tailwind | FE1 |
| **slack-bot** | v1.0.0 | Node.js, Bolt | BE3 |

### 9.2 Definition of Done (MVP)

#### 9.2.1 기능 DoD
- [x] 모든 P0 요구사항 구현 완료 (35개)
- [x] 주요 P1 요구사항 구현 완료 (선택 15개)
- [x] V7 Intent 체계 구현 (14개 Intent + 15개 Legacy 매핑)
- [x] 15개 노드 타입 구현 (P0: 5개, P1: 5개, P2: 5개)
- [x] Orchestrator 자동 Plan 생성 기능
- [x] API 문서 작성 (Swagger/OpenAPI)
- [x] 핵심 유스케이스 10개 동작 확인

#### 9.2.2 품질 DoD
- [x] 단위 테스트 커버리지 > 80%
- [x] E2E 테스트 핵심 시나리오 100% 통과
- [x] 성능 테스트 목표 달성 (Judgment P95 < 2.5s, BI P95 < 3s)
- [x] 보안 스캔 Critical 취약점 0개

#### 9.2.3 배포 DoD
- [x] Production 환경 구축 (Kubernetes)
- [x] CI/CD 파이프라인 동작 (GitHub Actions)
- [x] Monitoring 대시보드 동작 (Grafana)
- [x] 백업 자동화 (일 1회)

#### 9.2.4 문서 DoD
- [x] 모든 설계 문서 작성 완료 (A-1~A-3, B-1~B-6)
- [x] API 문서 (Swagger)
- [x] 운영 매뉴얼 (D-3)
- [x] 사용자 가이드 (D-4)

---

## 결론

본 문서(C-1)는 **AI Factory Decision Engine MVP** 개발 계획 및 WBS를 상세히 수립하였다.

### 주요 성과
1. **6개 Sprint 계획**: 인프라 → 코어 서비스 → 통합 → Learning → 성능/보안 → UAT
2. **상세 WBS**: 9개 영역, 80개 이상 작업 식별
3. **리소스 계획**: 10명, $150,000 예산
4. **일정**: 12주 (크리티컬 패스 명확)
5. **리스크 관리**: 7개 주요 리스크 식별 및 완화 전략
6. **품질 관리**: 코드 커버리지 > 80%, 보안 스캔, 성능 테스트

### 다음 단계
1. Sprint 1 착수 (인프라 구축)
2. 일일 Standup 시작
3. Backlog Refinement (주 1회)
4. 리스크 주간 모니터링

---

## 문서 이력
| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2025-10-15 | PM Team | 초안 작성 |
| 2.0 | 2025-11-26 | PM Team | Enhanced 버전 (Sprint 상세, 리소스, 일정 추가) |
| 3.0 | 2025-12-16 | SE Team | V7 Intent + Orchestrator 통합 업데이트 |

### v3.0 변경 사항
- **노드 타입**: 12개 → 15개 확장 (CODE, TRIGGER 노드 추가, P0/P1/P2 분류)
- **V7 Intent 체계**: 14개 V7 Intent + 15개 Legacy Intent 매핑 추가
- **Orchestrator**: 새로운 서비스 컴포넌트 추가
- **WBS 확장**: Intent Router (3.8), Orchestrator Service (3.9) 작업 추가
- **Sprint 계획**: V7 체계 개발 작업 반영
- **DoD 확장**: V7 Intent, 노드 타입, Orchestrator 기능 검증 항목 추가
