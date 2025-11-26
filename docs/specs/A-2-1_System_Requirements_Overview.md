# A-2-1. System Requirements Specification - Overview & Core Requirements

## 문서 정보
- **문서 ID**: A-2-1
- **버전**: 1.0
- **최종 수정일**: 2025-11-26
- **상태**: Draft
- **관련 문서**:
  - A-1 Product Vision & Scope
  - A-3 Use Case & User Story
  - B-1 System Architecture
  - B-2 Module/Service Design
  - B-3 Data/DB Schema
  - B-4 API Interface Spec
  - B-5 Workflow/State Machine Spec
  - B-6 AI/Agent/Prompt Spec

## 목차
1. [문서 개요](#1-문서-개요)
2. [시스템 컨텍스트](#2-시스템-컨텍스트)
3. [용어 정의](#3-용어-정의)
4. [전제조건 및 제약사항](#4-전제조건-및-제약사항)
5. [기능 요구사항 - Judgment Engine](#5-기능-요구사항---judgment-engine)
6. [기능 요구사항 - Workflow Engine](#6-기능-요구사항---workflow-engine)
7. [기능 요구사항 - BI Engine](#7-기능-요구사항---bi-engine)

---

## 1. 문서 개요

### 1.1 목적 (Purpose)
본 문서는 **제조업 AI 플랫폼 (AI Factory Decision Engine)** 의 시스템 요구사항을 상세히 명세하여, 개발팀, QA팀, 고객사, 유지보수 담당자가 시스템의 기능적/비기능적 요구사항을 명확히 이해하고 검증할 수 있도록 한다.

**대상 독자**:
- 개발팀 (Backend, Frontend, AI/ML)
- QA/테스트 엔지니어
- 프로젝트 관리자 및 제품 책임자
- 고객사 기술 담당자 및 최종 사용자 대표
- 유지보수 및 운영팀

### 1.2 범위 (Scope)
본 문서는 다음을 포함한다:
- **기능 요구사항 (Functional Requirements)**: 시스템이 제공해야 하는 기능 및 동작
- **비기능 요구사항 (Non-Functional Requirements)**: 성능, 보안, 확장성, 가용성 등
- **데이터 요구사항 (Data Requirements)**: 데이터 구조, 저장, 보존, 마이그레이션
- **인터페이스 요구사항 (Interface Requirements)**: 외부 시스템, 사용자 인터페이스, API
- **제약사항 (Constraints)**: 기술적, 규제적, 비즈니스 제약
- **추적성 매트릭스 (Traceability Matrix)**: 요구사항과 설계/구현/테스트 간 매핑

본 문서는 다음을 **포함하지 않는다**:
- 상세 설계 명세 (B-1, B-2 참조)
- API 상세 스펙 (B-4 참조)
- 테스트 케이스 상세 (C-3 참조)
- 배포 및 인프라 절차 (D-1, D-3 참조)

### 1.3 문서 구조
본 문서는 총 4개의 파일로 구성된다:
- **A-2-1**: 개요, 컨텍스트, 코어 엔진 요구사항 (Judgment, Workflow, BI)
- **A-2-2**: 통합/학습/챗봇 요구사항 (Integration, Learning, Chat)
- **A-2-3**: 비기능 요구사항 (성능, 보안, 가용성, 품질)
- **A-2-4**: 데이터/인터페이스 요구사항 및 추적성 매트릭스

---

## 2. 시스템 컨텍스트

### 2.1 시스템 경계 (System Boundary)

```
┌─────────────────────────────────────────────────────────────────┐
│                   AI Factory Decision Engine                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Judgment    │  │  Workflow    │  │  BI Engine   │          │
│  │  Engine      │  │  Engine      │  │  (Planner)   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Integration │  │  Learning    │  │  Chat/Intent │          │
│  │  (MCP Hub)   │  │  Service     │  │  Router      │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│  ┌──────────────────────────────────────────────────┐          │
│  │  Common Services (Auth, Audit, Cache, Storage)   │          │
│  └──────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────┘
          ▲                    ▲                    ▲
          │                    │                    │
    ┌─────┴─────┐        ┌─────┴─────┐        ┌─────┴─────┐
    │   Web UI  │        │ Slack Bot │        │ REST API  │
    └───────────┘        └───────────┘        └───────────┘
          ▲                    ▲                    ▲
          │                    │                    │
    ┌─────┴─────────────────────┴─────────────────┴─────┐
    │              External Systems                      │
    ├────────────────────────────────────────────────────┤
    │  ERP (SAP/Oracle) │ MES │ Sensors │ Excel/GDrive  │
    │  Jira/Asana       │ PLC │ Robots  │ Email/Webhook │
    └────────────────────────────────────────────────────┘
```

### 2.2 이해관계자 (Stakeholders)

| 역할 | 책임 | 주요 관심사 |
|------|------|------------|
| **제조 현장 관리자** | 생산 라인 모니터링 및 의사결정 | 실시간 판단 정확도, 빠른 응답 시간, 직관적 UI |
| **품질 관리자** | 품질 이슈 탐지 및 조치 | 불량 탐지 정확도, 근본 원인 분석, 추적 가능성 |
| **IT 관리자** | 시스템 구축 및 유지보수 | 안정성, 확장성, 통합 용이성, 보안 |
| **데이터 분석가** | 생산/품질 데이터 분석 및 보고서 작성 | BI 기능, 자연어 쿼리, 차트/대시보드 |
| **AI/ML 엔지니어** | 모델 개선 및 Rule 튜닝 | 학습 데이터 품질, 실험 기능, 배포 편의성 |
| **경영진** | 전사 생산성 및 품질 지표 모니터링 | 고수준 대시보드, ROI 측정, 규제 준수 |

### 2.3 외부 인터페이스 개요

#### 2.3.1 사용자 인터페이스
- **Web Dashboard**: React 기반 SPA, 차트/표/카드 컴포넌트, 반응형 디자인
- **Slack Bot**: 자연어 명령 수신 및 알림 발송
- **Chat UI**: 대화형 인터페이스, 멀티턴 대화 지원
- **모바일 (향후)**: iOS/Android 네이티브 앱 또는 PWA

#### 2.3.2 외부 시스템 인터페이스
- **ERP (SAP, Oracle)**: SOAP/REST API, 생산 계획/자재 정보 조회
- **MES**: REST API 또는 DB 직접 연결, 생산 실적/설비 데이터
- **센서/IoT**: MQTT/OPC UA, 실시간 센서 값 수집
- **Excel/Google Drive**: MCP Excel/GDrive 서버, 파일 읽기/쓰기
- **Jira/Asana**: MCP 서버, 이슈 생성/조회
- **Email/Webhook**: SMTP, HTTP POST, 알림 전송

#### 2.3.3 기술 스택 인터페이스
- **PostgreSQL 14+**: 주 데이터베이스
- **Redis 6+**: 캐시 및 세션 저장소
- **pgvector**: 벡터 임베딩 저장 및 유사도 검색
- **LLM API**: OpenAI, Anthropic, 기타 프로바이더
- **Kubernetes/Docker**: 컨테이너 오케스트레이션

---

## 3. 용어 정의

### 3.1 핵심 용어

| 용어 | 정의 | 관련 엔티티 |
|------|------|------------|
| **Tenant** | 멀티테넌시 구조에서 고객사 단위. 모든 데이터는 tenant_id로 격리됨 | tenants, 모든 테이블 |
| **Judgment** | 입력 JSON을 받아 Rule+LLM Hybrid로 상태/조치/설명을 반환하는 코어 판단 로직 | judgment_executions |
| **Workflow (WWF)** | DSL로 정의된 다단계 실행 플로우. 12가지 노드 타입 지원 | workflows, workflow_steps |
| **Ruleset** | Rhai 스크립트로 작성된 Rule 집합. 버전 관리 및 배포 단위 | rulesets, rule_scripts |
| **MCP Server** | Model Context Protocol 서버. 외부 도구/시스템 연동 표준화 | mcp_servers, mcp_tools |
| **ToolHub** | MCP 서버 호출을 중계하는 게이트웨이. 인증/타임아웃/회로차단 처리 | - |
| **Learning Sample** | 피드백 긍정인 로그에서 추출한 학습 데이터 | learning_samples |
| **Auto Rule Candidate** | 로그 분석으로 자동 생성된 Rule 후보 | auto_rule_candidates |
| **BI Planner** | 자연어 요청을 dataset/metric/component 계획(analysis_plan)으로 변환하는 LLM 플래너 | bi_* 테이블 |
| **RAG (Retrieval-Augmented Generation)** | 문서 검색 기반 생성. pgvector + LLM 조합 | rag_documents, rag_embeddings |
| **AAS (Asset Administration Shell)** | IEC 63278-1 표준 기반 디지털 트윈 메타모델 | aas_assets, aas_submodels |
| **OEE (Overall Equipment Effectiveness)** | 설비 종합 효율. Availability × Performance × Quality | fact_daily_production |

### 3.2 워크플로우 노드 타입

| 노드 타입 | 설명 | 주요 파라미터 |
|-----------|------|---------------|
| **DATA** | DB 쿼리 실행 (Fact/Dim/Pre-agg) | table, columns, filters |
| **BI** | BI 플래너 호출 및 차트 생성 | query, chart_type |
| **JUDGMENT** | Judgment Engine 호출 | judgment_config, policy |
| **MCP** | MCP 도구 호출 | server_id, tool_name, args |
| **ACTION** | 외부 채널 메시지 전송 (Slack/Email/Webhook) | channel, template |
| **APPROVAL** | 사용자 승인 대기 | approvers, timeout |
| **WAIT** | 일시 정지 또는 타임아웃 | duration, condition |
| **SWITCH** | 조건 분기 (if-else) | condition, branches |
| **PARALLEL** | 병렬 실행 | branches, join_policy |
| **COMPENSATION** | 보상 트랜잭션 (롤백) | compensation_steps |
| **DEPLOY** | Ruleset/Prompt 배포 | target, strategy (canary/blue-green) |
| **ROLLBACK** | 이전 버전으로 롤백 | target, version |
| **SIMULATE** | 과거 실행 재현 (What-if) | execution_id, override_params |

### 3.3 판단 정책 (Judgment Policy)

| 정책 | 설명 | 사용 시나리오 |
|------|------|--------------|
| **RULE_ONLY** | Rule만 실행, LLM 호출 없음 | 명확한 규칙 기반 판단, 저비용 |
| **LLM_ONLY** | LLM만 호출, Rule 건너뜀 | 복잡한 자연어 분석, 창의적 답변 |
| **RULE_FALLBACK** | Rule 우선, 신뢰도 부족 시 LLM | 대부분 Rule로 처리 가능한 경우 |
| **LLM_FALLBACK** | LLM 우선, 실패 시 Rule | 복잡한 문맥 이해 필요 + Rule 백업 |
| **HYBRID_WEIGHTED** | Rule + LLM 결과를 가중 평균 | 양쪽 장점 활용, 높은 정확도 |
| **HYBRID_GATE** | Rule이 특정 조건 만족 시만 LLM 호출 | 선택적 LLM 사용, 비용 최적화 |

### 3.4 약어 및 기술 용어

| 약어 | 전체 이름 | 설명 |
|------|----------|------|
| **SRS** | System Requirements Specification | 시스템 요구사항 명세서 |
| **FR** | Functional Requirement | 기능 요구사항 |
| **NFR** | Non-Functional Requirement | 비기능 요구사항 |
| **MCP** | Model Context Protocol | LLM 도구 연동 프로토콜 |
| **DSL** | Domain-Specific Language | 도메인 특화 언어 (Workflow 정의용) |
| **ETL** | Extract, Transform, Load | 데이터 추출/변환/적재 |
| **RBAC** | Role-Based Access Control | 역할 기반 접근 제어 |
| **JWT** | JSON Web Token | 인증 토큰 |
| **MQTT** | Message Queuing Telemetry Transport | IoT 메시징 프로토콜 |
| **OPC UA** | Open Platform Communications Unified Architecture | 산업 자동화 표준 |
| **PITR** | Point-In-Time Recovery | 시점 복구 |
| **RTO** | Recovery Time Objective | 복구 시간 목표 |
| **RPO** | Recovery Point Objective | 복구 시점 목표 |

---

## 4. 전제조건 및 제약사항

### 4.1 전제조건 (Assumptions)

#### 4.1.1 기술 환경
- **클라우드/온프렘**: 고객사 선택에 따라 AWS/Azure/GCP 또는 온프렘 Kubernetes 클러스터 사용 가능
- **네트워크**: 외부 LLM API 호출 가능한 아웃바운드 인터넷 연결 (프록시 허용)
- **데이터베이스**: PostgreSQL 14 이상 사용, pgvector 확장 설치 가능
- **캐시**: Redis 6 이상 사용, AOF 또는 복제 설정 가능
- **컨테이너**: Docker 20+ 및 Kubernetes 1.24+ 사용

#### 4.1.2 외부 시스템
- **ERP/MES**: REST API 또는 DB 직접 연결 가능, 스키마 정보 제공
- **센서/IoT**: MQTT 브로커 또는 OPC UA 서버 접근 가능
- **LLM API**: OpenAI API 키 또는 Anthropic API 키 제공
- **MCP 서버**: 표준 MCP 프로토콜 지원 서버 (Excel, GDrive 등)

#### 4.1.3 데이터 가용성
- **히스토리 데이터**: 최소 6개월 이상의 생산/품질 히스토리 데이터 제공
- **메타데이터**: 제품/라인/설비 마스터 데이터 제공
- **학습 데이터**: 초기 Rule 작성을 위한 도메인 전문가 인터뷰 가능

#### 4.1.4 인력 및 조직
- **관리자 권한**: 시스템 초기 설정을 위한 관리자 계정 생성 가능
- **도메인 전문가**: Rule 검증 및 피드백 제공 가능한 현장 전문가
- **IT 지원**: 시스템 배포 및 유지보수를 위한 IT 담당자

### 4.2 제약사항 (Constraints)

#### 4.2.1 기술 제약
| 제약 ID | 제약 내용 | 영향 범위 |
|---------|----------|----------|
| **TC-010** | PostgreSQL만 지원 (MySQL/MSSQL 미지원) | 데이터베이스 선택 |
| **TC-020** | pgvector 확장 필수 (벡터 검색용) | RAG 기능 |
| **TC-030** | Redis 필수 (캐시 및 세션) | 성능 최적화 |
| **TC-040** | Rhai 스크립트 언어만 지원 (Python/JS 미지원) | Rule 작성 |
| **TC-050** | MCP 프로토콜 표준 준수 서버만 연동 가능 | 외부 도구 통합 |
| **TC-060** | LLM API 응답 시간에 의존 (3~30초) | 판단 지연 시간 |
| **TC-070** | 동영상/음성 처리 미지원 (텍스트/이미지만) | 멀티모달 기능 |

#### 4.2.2 성능 제약
| 제약 ID | 제약 내용 | 근거 |
|---------|----------|------|
| **PC-010** | 동시 사용자 500명까지 지원 | 초기 목표 고객 규모 |
| **PC-020** | Judgment 평균 응답 1.5초 이내 (캐시 300ms) | 사용자 경험 |
| **PC-030** | BI 계획 생성 3초 이내 | 대화형 분석 요구 |
| **PC-040** | MCP 호출 기본 타임아웃 5초 | 외부 시스템 응답 |
| **PC-050** | 워크플로우 인스턴스 동시 실행 1,000개 | 리소스 제약 |
| **PC-060** | 임베딩 생성 처리량 100 docs/sec | 벡터화 속도 |

#### 4.2.3 보안 및 규제 제약
| 제약 ID | 제약 내용 | 규제/표준 |
|---------|----------|-----------|
| **SC-010** | 고객사 망 분리 환경 지원 필요 | 내부 정책 |
| **SC-020** | LLM 호출 시 PII 마스킹 필수 | GDPR, 개인정보보호법 |
| **SC-030** | 판단 로그 2년 이상 보존 | HACCP, ISO 22000 |
| **SC-040** | 감사 로그 변경 불가능 (Immutable) | 규제 요구 |
| **SC-050** | TLS 1.2 이상 전송 암호화 | 보안 표준 |
| **SC-060** | DB 저장 시 민감정보 암호화 (AES-256) | 보안 표준 |

#### 4.2.4 운영 제약
| 제약 ID | 제약 내용 | 이유 |
|---------|----------|------|
| **OC-010** | 계획된 유지보수 시간 주 2시간 (심야) | 서비스 중단 최소화 |
| **OC-020** | 백업 시간 일 1회 (오전 3시) | 성능 영향 최소화 |
| **OC-030** | Rule 배포는 카나리/블루그린만 허용 | 안정성 확보 |
| **OC-040** | 로그 보존 기간 핫 스토리지 90일 | 스토리지 비용 |
| **OC-050** | 알람 발송 빈도 제한 (동일 알람 10분 1회) | 알람 피로 방지 |

#### 4.2.5 비즈니스 제약
| 제약 ID | 제약 내용 | 이유 |
|---------|----------|------|
| **BC-010** | 멀티테넌트 격리 (tenant_id 기반) | SaaS 비즈니스 모델 |
| **BC-020** | 사용량 기반 과금 (Judgment 횟수, 저장 용량) | 수익 모델 |
| **BC-030** | 무료 Tier 제한 (월 1,000 Judgment) | 리소스 보호 |
| **BC-040** | LLM 비용 고객 전가 가능 | 원가 관리 |
| **BC-050** | 고객사별 SLA 차등 적용 (Standard/Premium) | 서비스 등급 |

---

## 5. 기능 요구사항 - Judgment Engine

### 5.1 개요
Judgment Engine은 입력 데이터를 받아 Rule과 LLM을 조합하여 판단 결과(상태, 조치, 설명)를 반환하는 핵심 엔진이다. Rule Only, LLM Only, Hybrid 방식을 지원하며, 캐싱 및 시뮬레이션 기능을 제공한다.

### 5.2 상세 요구사항

#### JUD-FR-010: Input Validation (입력 검증)

**요구사항 설명**:
- 시스템은 Judgment 요청 시 `workflow_id`, `input_data` 스키마의 유효성을 검증해야 한다.
- 필수 필드가 누락되거나 타입이 불일치할 경우 명확한 에러 메시지를 반환해야 한다.

**상세 기준**:
- **필수 필드**: `workflow_id` (UUID 형식), `input_data` (JSON 객체)
- **선택 필드**: `policy` (RULE_ONLY/LLM_ONLY/HYBRID), `need_explanation` (boolean), `context` (JSON)
- **스키마 검증**: workflow_id에 연결된 input_schema(JSON Schema)와 input_data 비교
- **타입 검증**: 문자열/숫자/불린/배열/객체 타입 일치 여부
- **범위 검증**: 숫자 min/max, 문자열 길이, enum 값

**입력 예시**:
```json
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "input_data": {
    "line_code": "LINE-A",
    "product_code": "PROD-123",
    "defect_count": 5,
    "timestamp": "2025-11-26T10:30:00Z"
  },
  "policy": "HYBRID_WEIGHTED",
  "need_explanation": true
}
```

**출력 예시 (정상)**:
```json
{
  "status": "validated",
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**출력 예시 (에러)**:
```json
{
  "status": "validation_failed",
  "errors": [
    {
      "field": "input_data.line_code",
      "message": "Required field missing"
    },
    {
      "field": "input_data.defect_count",
      "message": "Expected number, got string"
    }
  ]
}
```

**수락 기준 (Acceptance Criteria)**:
- [ ] 필수 필드 누락 시 400 에러 및 상세 메시지 반환
- [ ] 타입 불일치 시 필드명 및 기대 타입 명시
- [ ] JSON Schema 검증 라이브러리 사용 (ajv, jsonschema)
- [ ] 검증 실패율 < 0.1% (false positive/negative)
- [ ] 검증 처리 시간 < 50ms

**우선순위**: P0 (Critical)
**관련 모듈**: Judgment Engine, Workflow Engine
**의존성**: workflow input_schema 사전 정의
**테스트 케이스**: C-3-TC-JUD-010-*

---

#### JUD-FR-020: Rule Execution (Rule 실행)

**요구사항 설명**:
- 시스템은 지정된 Ruleset(Rhai 스크립트)을 실행하여 Rule 기반 판단 결과와 신뢰도를 산출해야 한다.

**상세 기준**:
- **Ruleset 선택**: workflow_id에 연결된 활성(active) ruleset 버전 자동 선택
- **실행 환경**: Rhai 엔진에 input_data, context, 기준 데이터 주입
- **결과 구조**: `{ result: {...}, confidence: 0.0~1.0, matched_rules: [...] }`
- **신뢰도 계산**: Rule 매치 강도, 데이터 품질, 히스토리 정확도 기반
- **타임아웃**: Rule 실행 최대 500ms, 초과 시 타임아웃 에러

**Rule 스크립트 예시** (Rhai):
```rust
// 불량률 판단 Rule
let defect_rate = input.defect_count / input.production_count;

if defect_rate > 0.05 {
    #{
        status: "HIGH_DEFECT",
        severity: "critical",
        confidence: 0.95,
        matched_rules: ["RULE_DEFECT_RATE_HIGH"]
    }
} else if defect_rate > 0.02 {
    #{
        status: "MODERATE_DEFECT",
        severity: "warning",
        confidence: 0.85,
        matched_rules: ["RULE_DEFECT_RATE_MODERATE"]
    }
} else {
    #{
        status: "NORMAL",
        severity: "info",
        confidence: 0.90,
        matched_rules: ["RULE_DEFECT_RATE_NORMAL"]
    }
}
```

**출력 예시**:
```json
{
  "result": {
    "status": "HIGH_DEFECT",
    "severity": "critical",
    "recommended_actions": ["Stop line", "Inspect equipment"]
  },
  "confidence": 0.95,
  "matched_rules": ["RULE_DEFECT_RATE_HIGH"],
  "execution_time_ms": 45
}
```

**수락 기준**:
- [ ] Ruleset 버전 선택 로직 정상 동작 (active, latest)
- [ ] Rhai 스크립트 실행 성공률 > 99.9%
- [ ] Rule 실행 시간 평균 < 100ms, 최대 < 500ms
- [ ] 신뢰도 계산 알고리즘 정의 및 문서화
- [ ] 타임아웃 발생 시 적절한 에러 반환

**우선순위**: P0 (Critical)
**관련 모듈**: Judgment Engine, Rule Ops
**의존성**: rulesets, rule_scripts, rule_deployments
**테스트 케이스**: C-3-TC-JUD-020-*

---

#### JUD-FR-030: LLM Fallback (LLM 대체 호출)

**요구사항 설명**:
- 시스템은 Rule 신뢰도가 임계값 미만이거나 정책이 LLM_FALLBACK/LLM_ONLY인 경우 LLM을 호출하여 판단을 보완해야 한다.

**상세 기준**:
- **호출 조건**:
  - Rule confidence < threshold (기본 0.7)
  - Policy = LLM_ONLY or LLM_FALLBACK
  - Rule 실행 실패 (syntax error, timeout)
- **LLM 선택**: 비용/품질 정책에 따라 GPT-4/GPT-4o-mini/Claude-3/Haiku 선택
- **프롬프트 구성**: 시스템 프롬프트 + 입력 데이터 + Few-shot 예시
- **응답 파싱**: JSON 모드 사용, 파싱 실패 시 재시도 (최대 3회)
- **타임아웃**: LLM 호출 최대 15초

**프롬프트 예시**:
```
You are a manufacturing quality expert. Analyze the following production data and provide judgment.

Input:
- Line: LINE-A
- Product: PROD-123
- Defect Count: 5
- Production Count: 100
- Timestamp: 2025-11-26 10:30:00

Respond in JSON format:
{
  "status": "HIGH_DEFECT|MODERATE_DEFECT|NORMAL",
  "severity": "critical|warning|info",
  "recommended_actions": ["action1", "action2"],
  "explanation": "Brief explanation",
  "confidence": 0.0-1.0
}
```

**LLM 응답 예시**:
```json
{
  "status": "HIGH_DEFECT",
  "severity": "critical",
  "recommended_actions": [
    "Immediately stop LINE-A",
    "Inspect PROD-123 production setup",
    "Review last 10 production batches"
  ],
  "explanation": "Defect rate of 5% exceeds threshold. Pattern indicates equipment calibration issue.",
  "confidence": 0.88
}
```

**수락 기준**:
- [ ] Rule confidence threshold 설정 가능 (workflow별)
- [ ] LLM API 호출 성공률 > 98%
- [ ] JSON 파싱 성공률 > 99.5%
- [ ] 파싱 실패 시 재시도 로직 동작
- [ ] LLM 응답 시간 평균 < 5초, 최대 < 15초
- [ ] LLM 비용 추적 (토큰 수, 비용)

**우선순위**: P0 (Critical)
**관련 모듈**: Judgment Engine, Prompt Manager
**의존성**: prompt_templates, llm_calls
**테스트 케이스**: C-3-TC-JUD-030-*

---

#### JUD-FR-040: Hybrid Aggregation (하이브리드 결합)

**요구사항 설명**:
- 시스템은 Rule과 LLM 결과를 Hybrid Policy에 따라 병합하여 최종 결과를 도출해야 한다.

**상세 기준**:
- **HYBRID_WEIGHTED**: 가중 평균
  - `final_confidence = rule_conf * rule_weight + llm_conf * llm_weight`
  - 기본 weight: rule=0.6, llm=0.4
- **HYBRID_GATE**: 조건부 LLM 호출
  - Rule confidence >= gate_threshold: Rule 결과 사용
  - Rule confidence < gate_threshold: LLM 호출 및 결과 병합
- **결과 병합 로직**:
  - status: 높은 confidence 우선
  - severity: 더 높은 심각도 우선
  - recommended_actions: Rule + LLM 액션 합집합
  - explanation: Rule 근거 + LLM 설명 결합

**병합 예시**:
```json
{
  "rule_result": {
    "status": "HIGH_DEFECT",
    "confidence": 0.85,
    "matched_rules": ["RULE_01"]
  },
  "llm_result": {
    "status": "MODERATE_DEFECT",
    "confidence": 0.75,
    "explanation": "Equipment shows signs of wear"
  },
  "final_result": {
    "status": "HIGH_DEFECT",
    "confidence": 0.81,
    "method_used": "hybrid_weighted",
    "explanation": "Rule matched HIGH_DEFECT threshold (conf=0.85). LLM suggests equipment wear (conf=0.75). Combined confidence: 0.81",
    "components": {
      "rule_confidence": 0.85,
      "llm_confidence": 0.75,
      "rule_weight": 0.6,
      "llm_weight": 0.4
    }
  }
}
```

**수락 기준**:
- [ ] HYBRID_WEIGHTED 가중치 설정 가능 (workflow별)
- [ ] HYBRID_GATE threshold 설정 가능
- [ ] 결과 병합 로직 테스트 커버리지 > 90%
- [ ] method_used 필드에 사용된 정책 명시
- [ ] components 필드에 Rule/LLM 개별 결과 보존

**우선순위**: P1 (High)
**관련 모듈**: Judgment Engine
**의존성**: JUD-FR-020, JUD-FR-030
**테스트 케이스**: C-3-TC-JUD-040-*

---

#### JUD-FR-050: Explanation Generation (설명 생성)

**요구사항 설명**:
- 시스템은 요청 옵션(`need_explanation=true`)에 따라 판단의 근거, 추천 조치, 증거 데이터를 생성해야 한다.

**상세 기준**:
- **근거 (Explanation)**: 왜 이 판단을 내렸는지 2-3문장 설명
- **추천 조치 (Recommended Actions)**: 구체적이고 실행 가능한 액션 리스트
- **증거 데이터 (Evidence)**: 판단 근거가 된 데이터 포인트 및 참조
- **생성 방법**:
  - Rule 기반: 매치된 Rule의 설명 템플릿 사용
  - LLM 기반: LLM 응답에서 explanation 추출
  - Hybrid: Rule + LLM 설명 결합
- **다국어 지원**: ko/en 템플릿 지원

**출력 예시**:
```json
{
  "judgment_id": "jud-123",
  "result": {
    "status": "HIGH_DEFECT",
    "severity": "critical"
  },
  "explanation": {
    "summary": "불량률 5%로 임계값(2%)을 초과했습니다. LINE-A 설비 점검이 필요합니다.",
    "reasoning": [
      "RULE_DEFECT_RATE_HIGH 매치 (confidence: 0.95)",
      "과거 7일 평균 불량률(1.2%) 대비 4.2배 증가",
      "유사 패턴 발생 시 설비 이상 확률 87%"
    ],
    "evidence": {
      "defect_count": 5,
      "production_count": 100,
      "defect_rate": 0.05,
      "threshold": 0.02,
      "historical_avg": 0.012,
      "similar_cases": 23
    },
    "recommended_actions": [
      {
        "priority": "immediate",
        "action": "LINE-A 생산 중단",
        "reason": "불량률 임계 초과"
      },
      {
        "priority": "high",
        "action": "설비 점검 및 캘리브레이션",
        "reason": "과거 유사 패턴 분석"
      },
      {
        "priority": "medium",
        "action": "최근 10개 배치 재검사",
        "reason": "추가 불량 발견 가능성"
      }
    ],
    "references": [
      {
        "type": "rule",
        "id": "RULE_DEFECT_RATE_HIGH",
        "version": "v1.2.3"
      },
      {
        "type": "data",
        "table": "fact_daily_production",
        "query": "SELECT * WHERE line_code='LINE-A' AND date >= '2025-11-19'"
      }
    ]
  },
  "language": "ko"
}
```

**수락 기준**:
- [ ] need_explanation=false 시 explanation 필드 생략 (성능 최적화)
- [ ] explanation 생성 추가 시간 < 200ms
- [ ] 다국어 템플릿 지원 (ko, en)
- [ ] recommended_actions에 우선순위 명시
- [ ] evidence에 판단 근거 데이터 포함
- [ ] references에 Rule/데이터 출처 명시

**우선순위**: P1 (High)
**관련 모듈**: Judgment Engine, Prompt Manager
**의존성**: JUD-FR-040
**테스트 케이스**: C-3-TC-JUD-050-*

---

#### JUD-FR-060: Caching (캐싱)

**요구사항 설명**:
- 시스템은 workflow_id와 입력 데이터 해시를 키로 Redis 캐시를 조회하여, 유효한 캐시가 있을 경우 즉시 반환해야 한다.

**상세 기준**:
- **캐시 키**: `judgment:cache:{workflow_id}:{input_hash}`
- **입력 해시**: input_data를 정규화하여 SHA-256 해시 생성
- **캐시 TTL**: 기본 300초 (5분), workflow별 설정 가능
- **캐시 무효화**:
  - Rule/Prompt 배포 시 해당 workflow 캐시 삭제
  - 수동 캐시 클리어 API 제공
- **캐시 우회**: 요청 헤더에 `X-Skip-Cache: true` 포함 시 캐시 무시

**캐시 흐름**:
```
1. 요청 수신 → input_hash 생성
2. Redis GET judgment:cache:{workflow_id}:{input_hash}
3. Cache HIT → 즉시 반환 (from_cache=true)
4. Cache MISS → Judgment 실행 → 결과 Redis SET (TTL 300s)
```

**출력 예시 (Cache HIT)**:
```json
{
  "judgment_id": "jud-123",
  "result": { ... },
  "from_cache": true,
  "cached_at": "2025-11-26T10:25:00Z",
  "cache_ttl_remaining": 180
}
```

**수락 기준**:
- [ ] 캐시 적중 시 응답 시간 < 300ms
- [ ] 캐시 적중률 > 40% (운영 초기 목표)
- [ ] input_hash 충돌 확률 < 10^-9
- [ ] Rule 배포 시 자동 캐시 무효화
- [ ] 캐시 TTL 설정 가능 (workflow별)
- [ ] from_cache 필드로 캐시 여부 명시

**우선순위**: P1 (High)
**관련 모듈**: Judgment Engine, Cache Manager
**의존성**: Redis
**테스트 케이스**: C-3-TC-JUD-060-*

---

#### JUD-FR-070: Simulation / Replay (시뮬레이션)

**요구사항 설명**:
- 시스템은 과거 실행 ID 또는 특정 페이로드를 사용하여 특정 정책/Rule 버전으로 판단을 재실행(Replay)할 수 있어야 한다.

**상세 기준**:
- **재실행 모드**:
  - **Historical Replay**: 과거 execution_id 지정하여 동일 입력 재실행
  - **What-if Scenario**: 입력 일부 변경하여 결과 비교
  - **Version Comparison**: 여러 Rule 버전으로 동시 실행하여 결과 비교
- **고정 조건**:
  - 지정한 Rule/Prompt 버전 사용 (현재 활성 버전 무시)
  - 캐시 사용 안 함
  - 실제 액션(Slack, Email) 실행 안 함 (dry-run)
- **출력**: 원본 결과와 재실행 결과 비교 (diff)

**API 요청 예시**:
```json
{
  "mode": "historical_replay",
  "execution_id": "exec-456",
  "override_versions": {
    "ruleset": "v1.2.0",
    "prompt": "v3.1.0"
  },
  "dry_run": true
}
```

**출력 예시**:
```json
{
  "simulation_id": "sim-789",
  "original_execution": {
    "execution_id": "exec-456",
    "result": { "status": "HIGH_DEFECT", "confidence": 0.95 },
    "ruleset_version": "v1.3.0",
    "executed_at": "2025-11-25T10:00:00Z"
  },
  "simulated_execution": {
    "result": { "status": "MODERATE_DEFECT", "confidence": 0.82 },
    "ruleset_version": "v1.2.0",
    "executed_at": "2025-11-26T11:00:00Z"
  },
  "diff": {
    "status_changed": true,
    "confidence_delta": -0.13,
    "explanation": "v1.3.0 Rule has stricter threshold"
  }
}
```

**수락 기준**:
- [ ] 과거 execution_id로 재실행 가능
- [ ] Rule/Prompt 버전 지정 가능
- [ ] What-if 시나리오 입력 변경 지원
- [ ] 여러 버전 동시 비교 (최대 5개)
- [ ] dry_run 모드에서 실제 액션 실행 안 됨
- [ ] 원본과 재실행 결과 diff 제공

**우선순위**: P2 (Medium)
**관련 모듈**: Judgment Engine, Rule Ops
**의존성**: judgment_executions, rule_deployments
**테스트 케이스**: C-3-TC-JUD-070-*

---

## 6. 기능 요구사항 - Workflow Engine

### 6.1 개요
Workflow Engine은 DSL로 정의된 다단계 워크플로우를 실행하는 엔진이다. 12가지 노드 타입을 지원하며, 상태 영속화, 회로 차단, 보상 트랜잭션 기능을 제공한다.

### 6.2 상세 요구사항

#### WF-FR-010: DSL Parsing and Validation (DSL 파싱 및 검증)

**요구사항 설명**:
- 시스템은 Workflow DSL JSON을 파싱하고, 노드 타입, 필수 파라미터, 연결 구조(Edge)의 유효성을 검증해야 한다.

**상세 기준**:
- **DSL 스키마 검증**:
  - nodes 배열: 각 노드에 id, type, config 필수
  - edges 배열: source, target, condition(선택)
  - 순환 참조(Cycle) 탐지 (WAIT/SWITCH 제외)
  - 고아 노드(Orphan) 탐지
  - 시작 노드(start=true) 정확히 1개
- **노드 타입별 필수 파라미터**:
  - DATA: table, columns
  - JUDGMENT: workflow_id 또는 inline config
  - MCP: server_id, tool_name
  - ACTION: channel, template
  - SWITCH: condition, branches
- **검증 실패 시**: 상세한 에러 메시지 및 노드 ID 반환

**DSL 예시**:
```json
{
  "workflow_id": "wf-001",
  "name": "Defect Analysis Workflow",
  "version": "1.0.0",
  "nodes": [
    {
      "id": "start",
      "type": "DATA",
      "start": true,
      "config": {
        "table": "fact_daily_production",
        "columns": ["line_code", "defect_count", "production_count"],
        "filters": { "date": "{{ input.date }}" }
      }
    },
    {
      "id": "judge",
      "type": "JUDGMENT",
      "config": {
        "judgment_workflow_id": "jud-defect-001",
        "input_mapping": {
          "line_code": "{{ nodes.start.line_code }}",
          "defect_count": "{{ nodes.start.defect_count }}"
        }
      }
    },
    {
      "id": "notify",
      "type": "ACTION",
      "config": {
        "channel": "slack",
        "webhook_url": "{{ env.SLACK_WEBHOOK }}",
        "template": "Defect detected: {{ nodes.judge.result.status }}"
      }
    }
  ],
  "edges": [
    { "source": "start", "target": "judge" },
    { "source": "judge", "target": "notify", "condition": "{{ nodes.judge.result.severity == 'critical' }}" }
  ]
}
```

**검증 에러 예시**:
```json
{
  "validation_errors": [
    {
      "node_id": "judge",
      "error": "Missing required config: judgment_workflow_id"
    },
    {
      "edge": { "source": "notify", "target": "start" },
      "error": "Cycle detected"
    },
    {
      "node_id": "orphan",
      "error": "Node has no incoming edges"
    }
  ]
}
```

**수락 기준**:
- [ ] DSL JSON 스키마 검증 (JSON Schema 사용)
- [ ] 12가지 노드 타입별 필수 파라미터 검증
- [ ] 순환 참조 탐지 (DFS/BFS 알고리즘)
- [ ] 고아 노드 탐지
- [ ] 시작 노드 정확히 1개 확인
- [ ] 검증 에러 시 노드 ID 및 에러 메시지 명시

**우선순위**: P0 (Critical)
**관련 모듈**: Workflow Engine
**의존성**: workflows, workflow_steps
**테스트 케이스**: C-3-TC-WF-010-*

---

#### WF-FR-020: Node Execution - DATA (데이터 노드)

**요구사항 설명**:
- 시스템은 DATA 노드를 실행하여 Fact/Dim 테이블 또는 Pre-agg 뷰에서 데이터를 조회해야 한다.

**상세 기준**:
- **쿼리 생성**: config의 table, columns, filters를 기반으로 SQL 생성
- **파라미터 바인딩**: `{{ input.* }}`, `{{ nodes.*.* }}` 템플릿 변수 치환
- **보안**: SQL Injection 방지 (Prepared Statement 사용)
- **결과 저장**: 조회 결과를 workflow 인스턴스 컨텍스트에 저장
- **에러 처리**: DB 에러 시 재시도 (최대 3회, 지수 백오프)

**노드 설정 예시**:
```json
{
  "id": "fetch_production",
  "type": "DATA",
  "config": {
    "table": "fact_daily_production",
    "columns": ["line_code", "date", "production_count", "defect_count"],
    "filters": {
      "line_code": "{{ input.line_code }}",
      "date": { ">=": "{{ input.start_date }}", "<=": "{{ input.end_date }}" }
    },
    "order_by": ["date DESC"],
    "limit": 10
  }
}
```

**생성 SQL (예시)**:
```sql
SELECT line_code, date, production_count, defect_count
FROM fact_daily_production
WHERE line_code = $1 AND date >= $2 AND date <= $3
ORDER BY date DESC
LIMIT 10;
```

**실행 결과**:
```json
{
  "node_id": "fetch_production",
  "status": "completed",
  "output": [
    { "line_code": "LINE-A", "date": "2025-11-25", "production_count": 500, "defect_count": 3 },
    { "line_code": "LINE-A", "date": "2025-11-24", "production_count": 480, "defect_count": 2 }
  ],
  "row_count": 2,
  "execution_time_ms": 35
}
```

**수락 기준**:
- [ ] SQL 생성 정확도 100% (단위 테스트)
- [ ] SQL Injection 취약점 없음 (보안 스캔)
- [ ] DB 조회 성공률 > 99%
- [ ] 평균 쿼리 시간 < 500ms
- [ ] 재시도 로직 동작 확인 (장애 주입 테스트)

**우선순위**: P0 (Critical)
**관련 모듈**: Workflow Engine
**의존성**: B-3 DB Schema
**테스트 케이스**: C-3-TC-WF-020-*

---

#### WF-FR-030: Node Execution - JUDGMENT (판단 노드)

**요구사항 설명**:
- 시스템은 JUDGMENT 노드를 실행하여 Judgment Engine API를 호출하고 결과를 컨텍스트에 저장해야 한다.

**상세 기준**:
- **API 호출**: 내부 Judgment Engine API (HTTP 또는 gRPC)
- **입력 매핑**: config의 input_mapping으로 입력 데이터 구성
- **결과 저장**: judgment_id, result, confidence, explanation 저장
- **에러 처리**: API 에러 시 재시도 (최대 2회), 실패 시 fallback 설정
- **타임아웃**: 기본 5초

**노드 설정 예시**:
```json
{
  "id": "defect_judgment",
  "type": "JUDGMENT",
  "config": {
    "judgment_workflow_id": "jud-defect-001",
    "input_mapping": {
      "line_code": "{{ nodes.fetch_production.output[0].line_code }}",
      "defect_count": "{{ nodes.fetch_production.output[0].defect_count }}",
      "production_count": "{{ nodes.fetch_production.output[0].production_count }}"
    },
    "policy": "HYBRID_WEIGHTED",
    "need_explanation": true,
    "timeout_ms": 5000
  }
}
```

**실행 결과**:
```json
{
  "node_id": "defect_judgment",
  "status": "completed",
  "output": {
    "judgment_id": "jud-123",
    "result": {
      "status": "HIGH_DEFECT",
      "severity": "critical"
    },
    "confidence": 0.92,
    "explanation": "불량률 5% 초과",
    "method_used": "hybrid_weighted"
  },
  "execution_time_ms": 1250
}
```

**수락 기준**:
- [ ] Judgment API 호출 성공률 > 99%
- [ ] input_mapping 템플릿 변수 치환 정확도 100%
- [ ] 평균 응답 시간 < 2초
- [ ] 재시도 로직 동작 확인
- [ ] 타임아웃 발생 시 적절한 에러 처리

**우선순위**: P0 (Critical)
**관련 모듈**: Workflow Engine, Judgment Engine
**의존성**: JUD-FR-*
**테스트 케이스**: C-3-TC-WF-030-*

---

#### WF-FR-040: Node Execution - ACTION (액션 노드)

**요구사항 설명**:
- 시스템은 ACTION 노드를 실행하여 설정된 채널(Slack, Email, Webhook)로 메시지나 페이로드를 전송해야 한다.

**상세 기준**:
- **지원 채널**:
  - **Slack**: Webhook URL 또는 Slack API
  - **Email**: SMTP 또는 SendGrid API
  - **Webhook**: HTTP POST with JSON payload
- **템플릿 엔진**: Handlebars 또는 Jinja2로 메시지 렌더링
- **재시도**: 전송 실패 시 재시도 (최대 3회, 지수 백오프)
- **멱등성**: 동일 메시지 중복 전송 방지 (idempotency key)
- **보안**: Webhook 서명 (HMAC) 지원

**Slack 노드 예시**:
```json
{
  "id": "notify_slack",
  "type": "ACTION",
  "config": {
    "channel": "slack",
    "webhook_url": "{{ env.SLACK_WEBHOOK }}",
    "template": {
      "text": "🚨 Critical Defect Detected",
      "blocks": [
        {
          "type": "section",
          "text": {
            "type": "mrkdwn",
            "text": "*Line*: {{ nodes.fetch_production.output[0].line_code }}\n*Status*: {{ nodes.defect_judgment.output.result.status }}\n*Confidence*: {{ nodes.defect_judgment.output.confidence }}"
          }
        }
      ]
    },
    "retry": { "max_attempts": 3, "backoff": "exponential" }
  }
}
```

**Email 노드 예시**:
```json
{
  "id": "notify_email",
  "type": "ACTION",
  "config": {
    "channel": "email",
    "smtp_host": "{{ env.SMTP_HOST }}",
    "smtp_port": 587,
    "from": "noreply@factory.ai",
    "to": ["manager@company.com"],
    "subject": "Defect Alert: {{ nodes.fetch_production.output[0].line_code }}",
    "body_html": "<h1>Defect Alert</h1><p>Line {{ nodes.fetch_production.output[0].line_code }} has {{ nodes.fetch_production.output[0].defect_count }} defects.</p>"
  }
}
```

**실행 결과**:
```json
{
  "node_id": "notify_slack",
  "status": "completed",
  "output": {
    "channel": "slack",
    "message_id": "msg-456",
    "sent_at": "2025-11-26T10:35:00Z",
    "status_code": 200
  },
  "execution_time_ms": 320
}
```

**수락 기준**:
- [ ] Slack/Email/Webhook 전송 성공률 > 98%
- [ ] 템플릿 변수 치환 정확도 100%
- [ ] 재시도 로직 동작 확인
- [ ] 멱등성 키 사용하여 중복 전송 방지
- [ ] Webhook HMAC 서명 검증 지원

**우선순위**: P1 (High)
**관련 모듈**: Workflow Engine, Notification Service
**의존성**: 외부 서비스 (Slack, SMTP)
**테스트 케이스**: C-3-TC-WF-040-*

---

#### WF-FR-050: Flow Control (흐름 제어)

**요구사항 설명**:
- 시스템은 SWITCH(조건 분기), PARALLEL(병렬 실행), WAIT(일시 정지) 로직을 처리해야 한다.

**상세 기준**:

##### SWITCH (조건 분기)
- **조건 평가**: 조건 표현식을 평가하여 참/거짓 판단
- **분기 선택**: 조건이 참인 첫 번째 분기 실행
- **기본 분기**: 모든 조건 거짓 시 default 분기 실행

**SWITCH 노드 예시**:
```json
{
  "id": "severity_switch",
  "type": "SWITCH",
  "config": {
    "branches": [
      {
        "condition": "{{ nodes.defect_judgment.output.result.severity == 'critical' }}",
        "target": "notify_manager"
      },
      {
        "condition": "{{ nodes.defect_judgment.output.result.severity == 'warning' }}",
        "target": "log_warning"
      },
      {
        "condition": "default",
        "target": "end"
      }
    ]
  }
}
```

##### PARALLEL (병렬 실행)
- **병렬 실행**: 여러 분기를 동시에 실행
- **조인 정책**:
  - **all**: 모든 분기 완료 대기
  - **any**: 하나라도 완료 시 진행
  - **majority**: 과반수 완료 시 진행
- **에러 처리**: 일부 분기 실패 시 처리 정책

**PARALLEL 노드 예시**:
```json
{
  "id": "parallel_notifications",
  "type": "PARALLEL",
  "config": {
    "branches": ["notify_slack", "notify_email", "update_dashboard"],
    "join_policy": "all",
    "timeout_ms": 10000,
    "on_error": "continue"
  }
}
```

##### WAIT (일시 정지)
- **대기 유형**:
  - **duration**: 지정 시간 대기
  - **condition**: 조건 만족까지 대기 (폴링)
  - **external_event**: 외부 이벤트 수신까지 대기
- **타임아웃**: 최대 대기 시간 설정

**WAIT 노드 예시**:
```json
{
  "id": "wait_approval",
  "type": "WAIT",
  "config": {
    "type": "external_event",
    "event_type": "approval_received",
    "timeout_ms": 86400000,
    "on_timeout": "rollback"
  }
}
```

**수락 기준**:
- [ ] SWITCH 조건 평가 정확도 100%
- [ ] PARALLEL 병렬 실행 및 조인 정책 동작 확인
- [ ] WAIT 타임아웃 정확도 ±100ms
- [ ] 외부 이벤트 수신 및 재개 동작 확인

**우선순위**: P1 (High)
**관련 모듈**: Workflow Engine
**의존성**: workflow_instances 상태 관리
**테스트 케이스**: C-3-TC-WF-050-*

---

#### WF-FR-060: State Persistence (상태 영속화)

**요구사항 설명**:
- 시스템은 워크플로우 인스턴스의 상태(PENDING, RUNNING, WAITING)와 실행 컨텍스트를 DB에 영구 저장하여 장애 복구 및 재개를 지원해야 한다.

**상세 기준**:
- **저장 시점**:
  - 인스턴스 생성 시 (PENDING)
  - 노드 실행 시작/완료 시 (RUNNING)
  - WAIT/APPROVAL 진입 시 (WAITING)
  - 인스턴스 완료/실패 시 (COMPLETED/FAILED)
- **저장 데이터**:
  - instance_id, workflow_id, status, current_node_id
  - context: 노드별 입력/출력 데이터
  - metadata: 시작 시각, 종료 시각, 에러 메시지
- **복구 로직**:
  - 서버 재시작 시 RUNNING 상태 인스턴스 복구
  - 마지막 완료 노드 이후부터 재개
  - 멱등성 보장 (같은 노드 중복 실행 방지)

**상태 전이도**:
```
PENDING → RUNNING → COMPLETED
              ↓
           WAITING → RUNNING → COMPLETED
              ↓
           FAILED
```

**workflow_instances 테이블 구조**:
```sql
CREATE TABLE workflow_instances (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  workflow_id uuid NOT NULL,
  status text NOT NULL, -- PENDING, RUNNING, WAITING, COMPLETED, FAILED
  current_node_id text,
  context jsonb NOT NULL DEFAULT '{}',
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  error_message text,
  metadata jsonb NOT NULL DEFAULT '{}'
);
```

**context 예시**:
```json
{
  "input": { "line_code": "LINE-A", "date": "2025-11-26" },
  "nodes": {
    "fetch_production": {
      "status": "completed",
      "output": [ { "line_code": "LINE-A", "defect_count": 5 } ]
    },
    "defect_judgment": {
      "status": "completed",
      "output": { "result": { "status": "HIGH_DEFECT" } }
    },
    "notify_slack": {
      "status": "running",
      "started_at": "2025-11-26T10:35:00Z"
    }
  }
}
```

**수락 기준**:
- [ ] 모든 상태 전이 시 DB 저장
- [ ] 서버 재시작 시 RUNNING 인스턴스 자동 복구
- [ ] 복구 후 중복 실행 없음 (멱등성)
- [ ] context 크기 제한 (최대 1MB)
- [ ] 상태 저장 실패 시 워크플로우 중단

**우선순위**: P0 (Critical)
**관련 모듈**: Workflow Engine
**의존성**: workflow_instances 테이블
**테스트 케이스**: C-3-TC-WF-060-*

---

#### WF-FR-070: Circuit Breaker (회로 차단)

**요구사항 설명**:
- 시스템은 노드/서비스별 실패율을 추적하여 임계 초과 시 회로를 차단하고 대체 경로(Fallback)를 실행해야 한다.

**상세 기준**:
- **실패율 추적**: 최근 N회 실행 중 실패 비율 계산 (슬라이딩 윈도우)
- **회로 상태**:
  - **CLOSED**: 정상 동작
  - **OPEN**: 회로 차단, 요청 즉시 실패
  - **HALF_OPEN**: 테스트 요청 허용 (회복 확인)
- **임계값**: 실패율 > 50% (최근 10회 중 5회 실패)
- **차단 시간**: 30초 후 HALF_OPEN 전환
- **Fallback**: 대체 노드 실행 또는 기본 응답 반환

**회로 차단 흐름**:
```
1. 노드 실행 → 성공/실패 기록
2. 실패율 계산 (최근 10회 기준)
3. 실패율 > 50% → OPEN 상태
4. 30초 대기 → HALF_OPEN 상태
5. 테스트 요청 성공 → CLOSED 상태
6. 테스트 요청 실패 → OPEN 상태 유지
```

**Fallback 설정 예시**:
```json
{
  "id": "call_external_api",
  "type": "MCP",
  "config": {
    "server_id": "mcp-external",
    "tool_name": "get_data",
    "circuit_breaker": {
      "failure_threshold": 0.5,
      "window_size": 10,
      "cooldown_ms": 30000
    },
    "fallback": {
      "type": "default_value",
      "value": { "status": "unavailable", "message": "Service temporarily unavailable" }
    }
  }
}
```

**회로 상태 모니터링**:
```json
{
  "node_id": "call_external_api",
  "circuit_breaker": {
    "state": "OPEN",
    "failure_rate": 0.6,
    "recent_failures": 6,
    "recent_successes": 4,
    "opened_at": "2025-11-26T10:30:00Z",
    "next_test_at": "2025-11-26T10:30:30Z"
  }
}
```

**수락 기준**:
- [ ] 실패율 추적 정확도 100%
- [ ] 임계 초과 시 회로 차단 (응답 시간 < 10ms)
- [ ] HALF_OPEN 상태 전환 정확도 ±1초
- [ ] Fallback 실행 성공률 > 99%
- [ ] 회로 상태 메트릭 수집 및 알람

**우선순위**: P1 (High)
**관련 모듈**: Workflow Engine
**의존성**: Redis (상태 저장)
**테스트 케이스**: C-3-TC-WF-070-*

---

## 7. 기능 요구사항 - BI Engine

### 7.1 개요
BI Engine은 자연어 질의를 받아 분석 계획(analysis_plan)으로 변환하고, SQL을 생성하여 데이터를 조회한 후 차트 설정을 생성하는 LLM 기반 BI 플래너다.

### 7.2 상세 요구사항

#### BI-FR-010: Natural Language Understanding (자연어 이해)

**요구사항 설명**:
- 시스템은 자연어 질의를 분석하여 `analysis_plan`(지표, 차원, 필터, 기간) JSON으로 변환해야 한다.

**상세 기준**:
- **LLM 프롬프트**: BI 카탈로그(datasets, metrics, components)를 컨텍스트로 주입
- **파싱 구조**:
  - **metrics**: 조회할 지표 (예: production_count, defect_rate, oee)
  - **dimensions**: 분석 차원 (예: line_code, date, shift)
  - **filters**: 필터 조건 (예: line_code = 'LINE-A')
  - **time_range**: 기간 (예: last_7_days, 2025-11-01 ~ 2025-11-30)
  - **aggregation**: 집계 함수 (sum, avg, count, min, max)
  - **granularity**: 시간 단위 (hour, day, week, month)
- **Few-shot 예시**: 과거 성공한 질의-계획 쌍 포함

**자연어 질의 예시**:
```
"지난 7일간 LINE-A의 일별 생산량과 불량률을 보여줘"
```

**생성된 analysis_plan**:
```json
{
  "query_text": "지난 7일간 LINE-A의 일별 생산량과 불량률을 보여줘",
  "intent": "time_series_analysis",
  "metrics": [
    {
      "name": "production_count",
      "aggregation": "sum",
      "label": "생산량"
    },
    {
      "name": "defect_rate",
      "aggregation": "avg",
      "label": "불량률"
    }
  ],
  "dimensions": [
    {
      "name": "date",
      "label": "날짜"
    }
  ],
  "filters": [
    {
      "field": "line_code",
      "operator": "=",
      "value": "LINE-A"
    },
    {
      "field": "date",
      "operator": ">=",
      "value": "{{ today - 7 days }}"
    }
  ],
  "time_range": {
    "type": "relative",
    "value": "last_7_days"
  },
  "granularity": "day",
  "chart_type": "line",
  "confidence": 0.92
}
```

**수락 기준**:
- [ ] 자연어 파싱 성공률 > 90%
- [ ] analysis_plan JSON 스키마 유효성 100%
- [ ] LLM 응답 시간 평균 < 3초
- [ ] Few-shot 예시 자동 업데이트 (학습)
- [ ] 애매한 질의 시 명확화 질문 생성

**우선순위**: P0 (Critical)
**관련 모듈**: BI Engine
**의존성**: bi_datasets, bi_metrics, LLM API
**테스트 케이스**: C-3-TC-BI-010-*

---

#### BI-FR-020: Plan Execution (계획 실행)

**요구사항 설명**:
- 시스템은 `analysis_plan`을 실행 가능한 SQL로 변환하여 데이터베이스(Fact/Pre-agg)를 조회해야 한다.

**상세 기준**:
- **SQL 생성 규칙**:
  - metrics → SELECT 절 집계 함수
  - dimensions → GROUP BY 절
  - filters → WHERE 절
  - time_range → WHERE 절 날짜 조건
  - granularity → DATE_TRUNC
- **Pre-aggregation 최적화**: 가능하면 Materialized View 사용
- **쿼리 타임아웃**: 기본 30초
- **결과 제한**: 최대 10,000 row

**analysis_plan to SQL 변환 예시**:

**Analysis Plan**:
```json
{
  "metrics": [
    { "name": "production_count", "aggregation": "sum" },
    { "name": "defect_rate", "aggregation": "avg" }
  ],
  "dimensions": [ { "name": "date" } ],
  "filters": [
    { "field": "line_code", "operator": "=", "value": "LINE-A" },
    { "field": "date", "operator": ">=", "value": "2025-11-19" }
  ],
  "granularity": "day"
}
```

**생성된 SQL**:
```sql
SELECT
  DATE_TRUNC('day', date) AS date,
  SUM(production_count) AS production_count,
  AVG(defect_count::float / production_count) AS defect_rate
FROM fact_daily_production
WHERE tenant_id = $1
  AND line_code = $2
  AND date >= $3
GROUP BY DATE_TRUNC('day', date)
ORDER BY date ASC
LIMIT 10000;
```

**쿼리 최적화 (Pre-agg 사용)**:
```sql
-- Materialized View 존재 시
SELECT
  date,
  production_count,
  defect_rate
FROM mv_daily_line_metrics
WHERE tenant_id = $1
  AND line_code = $2
  AND date >= $3
ORDER BY date ASC;
```

**실행 결과**:
```json
{
  "query_id": "qry-123",
  "analysis_plan": { ... },
  "sql": "SELECT ...",
  "result": {
    "columns": ["date", "production_count", "defect_rate"],
    "rows": [
      ["2025-11-19", 500, 0.012],
      ["2025-11-20", 480, 0.015],
      ["2025-11-21", 510, 0.010]
    ],
    "row_count": 7,
    "execution_time_ms": 125
  }
}
```

**수락 기준**:
- [ ] SQL 생성 정확도 > 95%
- [ ] Pre-agg 최적화 적용률 > 50%
- [ ] 쿼리 실행 성공률 > 99%
- [ ] 평균 쿼리 시간 < 2초
- [ ] 타임아웃 시 부분 결과 또는 에러 반환

**우선순위**: P0 (Critical)
**관련 모듈**: BI Engine
**의존성**: B-3 BI Schema (fact_*, mv_*)
**테스트 케이스**: C-3-TC-BI-020-*

---

#### BI-FR-030: Catalog Management (카탈로그 관리)

**요구사항 설명**:
- 시스템은 `bi_datasets`, `bi_metrics`, `bi_components`에 대한 등록/수정/삭제 API를 제공해야 한다.

**상세 기준**:
- **bi_datasets**: 데이터셋 메타데이터 (테이블명, 스키마, 설명)
- **bi_metrics**: 지표 정의 (이름, 계산식, 집계 함수)
- **bi_components**: 대시보드 컴포넌트 (차트 타입, 설정)
- **버전 관리**: 변경 이력 추적 (created_at, updated_at, updated_by)
- **권한 제어**: RBAC 기반 카탈로그 편집 권한

**Dataset 등록 예시**:
```json
{
  "name": "fact_daily_production",
  "display_name": "일일 생산 실적",
  "description": "라인별 일일 생산량 및 불량 데이터",
  "table_name": "fact_daily_production",
  "schema": {
    "columns": [
      { "name": "date", "type": "date", "label": "날짜" },
      { "name": "line_code", "type": "string", "label": "라인" },
      { "name": "production_count", "type": "number", "label": "생산량" },
      { "name": "defect_count", "type": "number", "label": "불량 수" }
    ]
  },
  "refresh_schedule": "daily 03:00"
}
```

**Metric 등록 예시**:
```json
{
  "name": "defect_rate",
  "display_name": "불량률",
  "description": "불량 수 / 생산량",
  "dataset": "fact_daily_production",
  "formula": "defect_count / production_count",
  "aggregation": "avg",
  "format": "percent",
  "thresholds": {
    "good": { "<=": 0.02 },
    "warning": { "<=": 0.05 },
    "critical": { ">": 0.05 }
  }
}
```

**Component 등록 예시**:
```json
{
  "name": "line_production_chart",
  "display_name": "라인별 생산량 차트",
  "chart_type": "bar",
  "dataset": "fact_daily_production",
  "metrics": ["production_count"],
  "dimensions": ["line_code"],
  "filters": { "date": "today" },
  "chart_config": {
    "xAxis": "line_code",
    "yAxis": "production_count",
    "color": "#4CAF50"
  }
}
```

**수락 기준**:
- [ ] CRUD API 동작 확인 (Create, Read, Update, Delete)
- [ ] 스키마 유효성 검증
- [ ] 중복 이름 검사
- [ ] 버전 이력 추적
- [ ] RBAC 권한 제어 (Admin만 편집 가능)

**우선순위**: P1 (High)
**관련 모듈**: BI Engine
**의존성**: bi_datasets, bi_metrics, bi_components 테이블
**테스트 케이스**: C-3-TC-BI-030-*

---

#### BI-FR-040: Chart Rendering (차트 렌더링)

**요구사항 설명**:
- 시스템은 조회된 데이터를 바탕으로 프론트엔드 렌더링을 위한 차트 설정(Chart Config)을 생성해야 한다.

**상세 기준**:
- **지원 차트 타입**: line, bar, pie, scatter, heatmap, table
- **차트 설정 항목**:
  - title, subtitle
  - xAxis, yAxis (label, scale, format)
  - series (data, color, legend)
  - annotations (threshold lines, markers)
- **반응형**: 모바일/데스크톱 대응
- **인터랙티브**: Zoom, Pan, Tooltip, Legend Toggle

**Chart Config 예시** (Line Chart):
```json
{
  "chart_id": "chart-123",
  "type": "line",
  "title": "LINE-A 일별 생산량 및 불량률",
  "subtitle": "2025-11-19 ~ 2025-11-25",
  "data": {
    "labels": ["2025-11-19", "2025-11-20", "2025-11-21", "2025-11-22", "2025-11-23", "2025-11-24", "2025-11-25"],
    "datasets": [
      {
        "label": "생산량",
        "data": [500, 480, 510, 495, 520, 505, 515],
        "borderColor": "#4CAF50",
        "backgroundColor": "rgba(76, 175, 80, 0.1)",
        "yAxisID": "y-left"
      },
      {
        "label": "불량률 (%)",
        "data": [1.2, 1.5, 1.0, 1.8, 1.3, 1.1, 0.9],
        "borderColor": "#F44336",
        "backgroundColor": "rgba(244, 67, 54, 0.1)",
        "yAxisID": "y-right"
      }
    ]
  },
  "options": {
    "responsive": true,
    "interaction": { "mode": "index", "intersect": false },
    "scales": {
      "x": { "display": true, "title": { "display": true, "text": "날짜" } },
      "y-left": { "type": "linear", "display": true, "position": "left", "title": { "display": true, "text": "생산량" } },
      "y-right": { "type": "linear", "display": true, "position": "right", "grid": { "drawOnChartArea": false }, "title": { "display": true, "text": "불량률 (%)" } }
    },
    "plugins": {
      "annotation": {
        "annotations": [
          {
            "type": "line",
            "yScaleID": "y-right",
            "yMin": 2.0,
            "yMax": 2.0,
            "borderColor": "#FFA726",
            "borderWidth": 2,
            "label": { "content": "경고 임계값 (2%)", "enabled": true }
          }
        ]
      }
    }
  }
}
```

**수락 기준**:
- [ ] 6가지 차트 타입 지원
- [ ] 차트 설정 JSON 스키마 유효성 100%
- [ ] 프론트엔드 라이브러리 호환 (Chart.js, ECharts)
- [ ] 반응형 렌더링 동작 확인
- [ ] 인터랙티브 기능 동작 확인

**우선순위**: P1 (High)
**관련 모듈**: BI Engine, Frontend
**의존성**: BI-FR-020
**테스트 케이스**: C-3-TC-BI-040-*

---

#### BI-FR-050: Caching (캐싱)

**요구사항 설명**:
- 시스템은 분석 계획 해시를 기반으로 쿼리 결과를 캐싱하고, 데이터 갱신 시 무효화해야 한다.

**상세 기준**:
- **캐시 키**: `bi:cache:{tenant_id}:{plan_hash}`
- **plan_hash**: analysis_plan JSON을 정규화하여 SHA-256 해시
- **캐시 TTL**: 기본 600초 (10분), dataset별 설정 가능
- **무효화 조건**:
  - ETL 작업 완료 시 (해당 dataset 캐시 삭제)
  - 수동 캐시 클리어 API 호출
  - TTL 만료
- **캐시 우회**: 요청 헤더 `X-Skip-Cache: true`

**캐시 키 생성 예시**:
```python
import hashlib
import json

def generate_plan_hash(analysis_plan):
    # 정규화: 키 정렬, 공백 제거
    normalized = json.dumps(analysis_plan, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(normalized.encode()).hexdigest()

plan = {
    "metrics": [{"name": "production_count", "aggregation": "sum"}],
    "dimensions": [{"name": "date"}],
    "filters": [{"field": "line_code", "operator": "=", "value": "LINE-A"}]
}

plan_hash = generate_plan_hash(plan)
# → "a1b2c3d4e5f6..."
```

**캐시 저장/조회 흐름**:
```
1. 요청 수신 → plan_hash 생성
2. Redis GET bi:cache:{tenant_id}:{plan_hash}
3. Cache HIT → 즉시 반환 (from_cache=true)
4. Cache MISS → SQL 실행 → 결과 Redis SET (TTL 600s)
```

**출력 예시 (Cache HIT)**:
```json
{
  "query_id": "qry-123",
  "result": { ... },
  "from_cache": true,
  "cached_at": "2025-11-26T10:45:00Z",
  "cache_ttl_remaining": 420
}
```

**수락 기준**:
- [ ] 캐시 적중 시 응답 시간 < 500ms
- [ ] 캐시 적중률 > 30% (운영 초기 목표)
- [ ] plan_hash 충돌 확률 < 10^-9
- [ ] ETL 완료 시 자동 캐시 무효화
- [ ] from_cache 필드로 캐시 여부 명시

**우선순위**: P1 (High)
**관련 모듈**: BI Engine, Cache Manager
**의존성**: Redis, ETL metadata
**테스트 케이스**: C-3-TC-BI-050-*

---

## 다음 파일로 계속

본 문서는 A-2-1로, 개요 및 코어 엔진(Judgment, Workflow, BI) 요구사항을 포함한다.

**다음 파일**:
- **A-2-2**: Integration, Learning, Chat 요구사항
- **A-2-3**: 비기능 요구사항 (성능, 보안, 가용성)
- **A-2-4**: 데이터/인터페이스 요구사항 및 추적성 매트릭스

---

## 문서 이력
| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2025-11-26 | AI Factory Team | 초안 작성 |
