# TriFlow AI - WBS (Work Breakdown Structure)

> **버전**: 1.0.0
> **최종 수정**: 2025-11-27
> **목표**: 3개월 내 MVP 출시

---

## 1. 프로젝트 개요

### 1.1 목표

**TriFlow AI MVP**는 PC 설치형 데스크톱 애플리케이션으로, 제조 현장의 데이터를 분석하고 AI 기반 의사결정을 지원하는 솔루션입니다.

### 1.2 핵심 기능

| 기능 | 설명 | 담당 Agent |
|------|------|------------|
| **AI 채팅** | 자연어로 데이터 분석 요청 | Meta Router |
| **불량 판단** | 센서 데이터 기반 양불 판정 | Judgment Agent |
| **워크플로우 생성** | 자동화 규칙 DSL 생성 | Workflow Planner |
| **BI 분석** | Text-to-SQL 데이터 조회 | BI Planner |
| **대시보드** | 실시간 모니터링 차트 | Frontend |

---

## 2. 로드맵 타임라인

![간트 차트](diagrams/wbs_roadmap_gantt.svg)

### 2.1 Phase별 일정

| Phase | 기간 | 목표 | 상태 |
|-------|------|------|------|
| **Phase 0** | Week 1 | 프로젝트 기획 및 문서화 | ✅ 완료 |
| **Sprint 1** | Week 2-3 | 인프라 및 기본 설정 | ✅ 완료 |
| **Sprint 2** | Week 4-5 | 에이전트 시스템 구현 | ✅ 완료 |
| **Sprint 3** | Week 6-7 | Chat UI 구현 | ✅ 완료 |
| **Sprint 4** | Week 8-9 | 학습 파이프라인 | ⏳ 예정 |
| **Sprint 5** | Week 10 | 보안 | ⏳ 예정 |
| **Sprint 6** | Week 11-12 | 릴리스 | ✅ 완료 |

---

## 3. 상세 작업 분해

### 3.1 Phase 0: 프로젝트 기획 (Week 1)

| ID | 작업 | 담당 | 의존성 | 상태 |
|----|------|------|--------|------|
| P0-1 | 프로젝트 문서 작성 (A-1 ~ D-4) | PM | - | ✅ |
| P0-2 | AI_GUIDELINES.md 작성 | Dev | P0-1 | ✅ |
| P0-3 | TASKS.md 작성 | Dev | P0-1 | ✅ |
| P0-4 | README.md 작성 | Dev | P0-2 | ✅ |
| P0-5 | Git 저장소 초기화 | Dev | P0-3 | ✅ |

### 3.2 Sprint 1: 인프라 설정 (Week 2-3)

| ID | 작업 | 담당 | 의존성 | 상태 |
|----|------|------|--------|------|
| S1-1 | Docker Compose 설정 | Backend | P0-5 | ✅ |
| S1-2 | PostgreSQL + pgvector 설정 | Backend | S1-1 | ✅ |
| S1-3 | Redis 설정 | Backend | S1-1 | ✅ |
| S1-4 | MinIO 설정 | Backend | S1-1 | ✅ |
| S1-5 | DB 스키마 초기화 (4개 스키마) | Backend | S1-2 | ✅ |
| S1-6 | Rhai 룰 엔진 바인딩 | Backend | S1-2 | ✅ |
| S1-7 | Safe SQL 쿼리 실행기 | Backend | S1-5 | ✅ |
| S1-8 | GitHub Actions CI/CD | DevOps | S1-1 | ✅ |
| S1-9 | Tauri + React 프로젝트 초기화 | Frontend | P0-5 | ✅ |
| S1-10 | Tailwind + Shadcn/ui 설정 | Frontend | S1-9 | ✅ |

### 3.3 Sprint 2: 에이전트 시스템 (Week 4-5)

| ID | 작업 | 담당 | 의존성 | 상태 |
|----|------|------|--------|------|
| S2-1 | Base Agent 클래스 구현 | Backend | S1-6 | ✅ |
| S2-2 | Meta Router Agent | Backend | S2-1 | ✅ |
| S2-3 | Judgment Agent | Backend | S2-1 | ✅ |
| S2-4 | Workflow Planner Agent | Backend | S2-1 | ✅ |
| S2-5 | BI Planner Agent | Backend | S2-1, S1-7 | ✅ |
| S2-6 | Agent API 엔드포인트 | Backend | S2-2~5 | ✅ |
| S2-7 | 프롬프트 템플릿 작성 | Backend | S2-2~5 | ✅ |

### 3.4 Sprint 3: Chat UI (Week 6-7)

| ID | 작업 | 담당 | 의존성 | 상태 |
|----|------|------|--------|------|
| S3-1 | TypeScript 타입 정의 | Frontend | S2-6 | ✅ |
| S3-2 | Agent API 서비스 | Frontend | S3-1 | ✅ |
| S3-3 | ChatMessage 컴포넌트 | Frontend | S3-2 | ✅ |
| S3-4 | ChatInput 컴포넌트 | Frontend | S3-2 | ✅ |
| S3-5 | ChatContainer 컴포넌트 | Frontend | S3-3, S3-4 | ✅ |
| S3-6 | Dashboard 레이아웃 | Frontend | S1-10 | ✅ |
| S3-7 | Chart 컴포넌트 (6종) | Frontend | S3-6 | ✅ |
| S3-8 | Sidebar Navigation | Frontend | S3-5 | ✅ |
| S3-9 | Settings 페이지 | Frontend | S3-8 | ✅ |

### 3.5 Sprint 4: 학습 파이프라인 (Week 8-9)

| ID | 작업 | 담당 | 의존성 | 상태 |
|----|------|------|--------|------|
| S4-1 | Feedback Loop 구현 | Backend | S2-3 | ⏳ |
| S4-2 | analyze_feedback_logs Tool | Backend | S4-1 | ⏳ |
| S4-3 | propose_new_rule Tool | Backend | S4-2 | ⏳ |
| S4-4 | Zwave 시뮬레이션 Tool | Backend | S4-1 | ⏳ |
| S4-5 | Learning Agent 통합 | Backend | S4-2~4 | ⏳ |

### 3.6 Sprint 5: 보안 (Week 10)

| ID | 작업 | 담당 | 의존성 | 상태 |
|----|------|------|--------|------|
| S5-1 | 인증 시스템 구현 | Backend | S2-6 | ⏳ |
| S5-2 | PII 마스킹 미들웨어 | Backend | S5-1 | ⏳ |
| S5-3 | API 키 관리 UI | Frontend | S5-1 | ⏳ |

### 3.7 Sprint 6: 릴리스 (Week 11-12)

| ID | 작업 | 담당 | 의존성 | 상태 |
|----|------|------|--------|------|
| S6-1 | UAT 테스트 | QA | S3-9 | ✅ |
| S6-2 | 버그 수정 | Dev | S6-1 | ✅ |
| S6-3 | Production 빌드 | DevOps | S6-2 | ✅ |
| S6-4 | 설치 패키지 생성 (MSI, NSIS) | DevOps | S6-3 | ✅ |
| S6-5 | v0.1.0 태그 생성 | DevOps | S6-4 | ✅ |

---

## 4. 데이터 처리 흐름

![데이터 처리 흐름도](diagrams/wbs_process_flow.svg)

### 4.1 처리 단계

```
[센서 데이터] → [ETL 파이프라인] → [PostgreSQL] → [AI 분석] → [결과 시각화]
     │              │                  │              │             │
     └──────────────┴──────────────────┴──────────────┴─────────────┘
                              TriFlow AI 처리 범위
```

### 4.2 에이전트 라우팅 흐름

```
사용자 입력
    │
    ▼
┌────────────────────┐
│  Meta Router Agent │
│  (의도 분류)        │
└────────────────────┘
    │
    ├─→ [데이터 분석] ──→ BI Planner Agent
    │
    ├─→ [불량 판단] ──→ Judgment Agent
    │
    ├─→ [워크플로우] ──→ Workflow Planner Agent
    │
    └─→ [일반 질문] ──→ General Response
```

---

## 5. 리소스 할당

### 5.1 역할별 담당

| 역할 | 담당 영역 |
|------|----------|
| **Backend Dev** | FastAPI, Agent 시스템, DB |
| **Frontend Dev** | Tauri, React, UI 컴포넌트 |
| **DevOps** | Docker, CI/CD, 빌드 |
| **PM** | 문서, 일정 관리 |
| **QA** | 테스트, 버그 리포트 |

### 5.2 기술 스택별 복잡도

| 기술 | 복잡도 | 예상 공수 |
|------|--------|----------|
| Anthropic Agent | 높음 | 40% |
| FastAPI Backend | 중간 | 25% |
| Tauri/React UI | 중간 | 25% |
| DevOps/CI | 낮음 | 10% |

---

## 6. 위험 요소 및 대응

| 위험 | 영향도 | 대응 방안 |
|------|--------|----------|
| API 응답 지연 | 중간 | 타임아웃 설정, 캐싱 |
| 차트 렌더링 성능 | 낮음 | 데이터 페이지네이션 |
| 크로스 플랫폼 빌드 | 중간 | CI 매트릭스 테스트 |
| LLM 할루시네이션 | 높음 | 프롬프트 엔지니어링, 검증 로직 |

---

## 7. 마일스톤 정의

### MVP v0.1.0 (현재)

**포함 기능:**
- ✅ AI Chat (Meta Router)
- ✅ Judgment Agent (Rhai 룰 엔진)
- ✅ Workflow Planner (DSL 생성)
- ✅ BI Planner (Text-to-SQL, 차트)
- ✅ Dashboard (Stats, 고정 차트)
- ✅ Settings (연결 상태, API 키)

**제외 기능:**
- ⏳ Learning Pipeline
- ⏳ 인증/권한 시스템
- ⏳ Workflow Builder UI (노드 기반)

### V1.0 (Post-MVP)

**추가 기능:**
- 노드 기반 워크플로우 빌더 UI
- Learning Agent (피드백 루프)
- 고급 인증 시스템
- 다국어 지원

### V2.0 (미래)

**추가 기능:**
- 모바일 앱 (React Native)
- 고급 시뮬레이션 (Zwave)
- 엔터프라이즈 기능

---

## 8. 진척도 요약

| 항목 | 완료 | 전체 | 진행률 |
|------|------|------|--------|
| Phase 0 | 5 | 5 | 100% |
| Sprint 1 | 10 | 10 | 100% |
| Sprint 2 | 7 | 7 | 100% |
| Sprint 3 | 9 | 9 | 100% |
| Sprint 4 | 0 | 5 | 0% |
| Sprint 5 | 0 | 3 | 0% |
| Sprint 6 | 5 | 5 | 100% |
| **총계** | **36** | **44** | **82%** |

---

## 9. 다이어그램 목록

| 파일명 | 설명 |
|--------|------|
| `wbs_roadmap_gantt.svg` | Sprint 1~6 간트 차트 |
| `wbs_process_flow.svg` | 백엔드 데이터 처리 흐름도 |

---

## 10. 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.0.0 | 2025-11-27 | 최초 작성 |
