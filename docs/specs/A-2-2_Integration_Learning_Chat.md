# A-2-2. System Requirements Specification - Integration, Learning, Chat

## 문서 정보
- **문서 ID**: A-2-2
- **버전**: 1.0
- **최종 수정일**: 2025-11-26
- **상태**: Draft
- **선행 문서**: A-2-1 System Requirements Overview

## 목차
1. [기능 요구사항 - Integration / MCP](#1-기능-요구사항---integration--mcp)
2. [기능 요구사항 - Learning / Rule Ops](#2-기능-요구사항---learning--rule-ops)
3. [기능 요구사항 - Chat / Intent](#3-기능-요구사항---chat--intent)
4. [기능 요구사항 - Security](#4-기능-요구사항---security)
5. [기능 요구사항 - Observability](#5-기능-요구사항---observability)

---

## 1. 기능 요구사항 - Integration / MCP

### 1.1 개요
Integration/MCP ToolHub는 외부 MCP 서버(Excel, GDrive, Jira, 로봇 등) 호출을 표준화하는 게이트웨이다. 도구 레지스트리, 실행 중계, 회로 차단, Drift 탐지 기능을 제공한다.

### 1.2 상세 요구사항

#### INT-FR-010: MCP Registry (MCP 레지스트리)

**요구사항 설명**:
- 시스템은 MCP 서버 및 도구(Tool)의 메타데이터(이름, 스키마, 엔드포인트)를 등록하고 관리해야 한다.

**상세 기준**:
- **MCP 서버 메타데이터**:
  - server_id, name, description
  - base_url, auth_type (none/api_key/oauth)
  - status (active/inactive/deprecated)
  - health_check_url, health_check_interval
- **MCP 도구 메타데이터**:
  - tool_id, tool_name, description
  - input_schema (JSON Schema)
  - output_schema (JSON Schema)
  - timeout_ms, retry_policy
- **자동 검색**: MCP 서버 연결 시 도구 목록 자동 조회 (MCP Protocol: `tools/list`)

**MCP 서버 등록 예시**:
```json
{
  "server_id": "mcp-excel",
  "name": "Excel MCP Server",
  "description": "Excel 파일 읽기/쓰기 도구",
  "base_url": "https://mcp-excel.factory.ai",
  "auth_type": "api_key",
  "api_key": "{{ env.MCP_EXCEL_KEY }}",
  "health_check_url": "/health",
  "health_check_interval": 60,
  "status": "active",
  "metadata": {
    "version": "1.2.0",
    "protocol_version": "2024-11-05"
  }
}
```

**MCP 도구 등록 예시**:
```json
{
  "tool_id": "excel-read",
  "server_id": "mcp-excel",
  "tool_name": "read_excel",
  "description": "Excel 파일에서 데이터 읽기",
  "input_schema": {
    "type": "object",
    "properties": {
      "file_path": { "type": "string" },
      "sheet_name": { "type": "string" },
      "range": { "type": "string", "pattern": "^[A-Z]+[0-9]+:[A-Z]+[0-9]+$" }
    },
    "required": ["file_path"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "rows": { "type": "array", "items": { "type": "array" } },
      "columns": { "type": "array", "items": { "type": "string" } }
    }
  },
  "timeout_ms": 10000,
  "retry_policy": { "max_attempts": 3, "backoff": "exponential" }
}
```

**자동 검색 API 호출**:
```http
POST https://mcp-excel.factory.ai/mcp/tools/list
Authorization: Bearer {{ api_key }}

Response:
{
  "tools": [
    { "name": "read_excel", "description": "...", "inputSchema": {...} },
    { "name": "write_excel", "description": "...", "inputSchema": {...} }
  ]
}
```

**수락 기준**:
- [ ] MCP 서버 CRUD API 동작 확인
- [ ] MCP 도구 CRUD API 동작 확인
- [ ] 자동 검색 기능 (tools/list 호출)
- [ ] JSON Schema 검증
- [ ] Health check 주기적 실행 (interval에 따라)

**우선순위**: P0 (Critical)
**관련 모듈**: Integration Hub
**의존성**: mcp_servers, mcp_tools 테이블
**테스트 케이스**: C-3-TC-INT-010-*

---

#### INT-FR-020: Tool Execution (도구 실행)

**요구사항 설명**:
- 시스템은 MCP 도구 호출 요청을 중계(Proxy)하고, 인증 헤더 주입 및 타임아웃을 처리해야 한다.

**상세 기준**:
- **호출 흐름**:
  1. 클라이언트 → ToolHub → MCP 서버
  2. 인증 헤더 자동 주입 (API Key, OAuth Token)
  3. 타임아웃 처리 (도구별 설정값)
  4. 응답 검증 (output_schema)
  5. 결과 반환 및 로깅
- **재시도 정책**:
  - 네트워크 에러: 최대 3회, 지수 백오프
  - 타임아웃: 재시도 없음 (즉시 실패)
  - 5xx 에러: 최대 2회, 선형 백오프
  - 4xx 에러: 재시도 없음 (클라이언트 에러)
- **로깅**: 요청/응답 페이로드, 실행 시간, 에러 메시지

**도구 호출 요청**:
```json
{
  "tool_id": "excel-read",
  "input": {
    "file_path": "s3://bucket/data.xlsx",
    "sheet_name": "Sheet1",
    "range": "A1:D100"
  },
  "timeout_ms": 10000
}
```

**ToolHub 내부 처리**:
```
1. tool_id로 도구 메타데이터 조회
2. input_schema로 입력 검증
3. MCP 서버 base_url + auth 조회
4. HTTP POST 요청:
   POST https://mcp-excel.factory.ai/mcp/tools/call
   Authorization: Bearer {{ api_key }}
   {
     "method": "read_excel",
     "params": { "file_path": "...", "sheet_name": "...", "range": "..." }
   }
5. 응답 수신 및 output_schema 검증
6. 클라이언트에 결과 반환
```

**도구 호출 응답**:
```json
{
  "tool_execution_id": "exec-789",
  "tool_id": "excel-read",
  "status": "success",
  "output": {
    "rows": [
      ["Name", "Age", "City", "Score"],
      ["Alice", 30, "Seoul", 95],
      ["Bob", 25, "Busan", 88]
    ],
    "columns": ["Name", "Age", "City", "Score"],
    "row_count": 3
  },
  "execution_time_ms": 850,
  "server_id": "mcp-excel"
}
```

**에러 응답 예시**:
```json
{
  "tool_execution_id": "exec-790",
  "tool_id": "excel-read",
  "status": "failed",
  "error": {
    "type": "timeout",
    "message": "MCP server did not respond within 10000ms",
    "retry_attempts": 0
  },
  "execution_time_ms": 10050
}
```

**수락 기준**:
- [ ] 도구 호출 성공률 > 98%
- [ ] 인증 헤더 자동 주입 동작 확인
- [ ] 타임아웃 처리 정확도 ±100ms
- [ ] 재시도 정책 동작 확인 (네트워크 에러, 5xx)
- [ ] 입력/출력 스키마 검증

**우선순위**: P0 (Critical)
**관련 모듈**: Integration Hub
**의존성**: mcp_servers, mcp_tools
**테스트 케이스**: C-3-TC-INT-020-*

---

#### INT-FR-030: Connector Management (커넥터 관리)

**요구사항 설명**:
- 시스템은 DB/API 커넥터(ERP, MES 등)의 연결 정보를 관리하고 헬스 체크를 수행해야 한다.

**상세 기준**:
- **지원 커넥터 타입**:
  - **DB**: PostgreSQL, MySQL, MSSQL, Oracle
  - **REST API**: JSON/XML, OAuth/API Key 인증
  - **MQTT**: IoT 센서 데이터 구독
  - **OPC UA**: 산업 자동화 프로토콜
- **연결 정보 암호화**: 비밀번호/API Key는 AES-256 암호화 저장
- **헬스 체크**:
  - DB: 단순 SELECT 1 쿼리
  - REST API: /health 엔드포인트 호출
  - MQTT/OPC UA: 연결 상태 확인
  - 주기: 5분마다
- **상태 알람**: 헬스 체크 3회 연속 실패 시 알람 발송

**DB 커넥터 등록**:
```json
{
  "connector_id": "conn-erp-001",
  "name": "ERP Database",
  "type": "postgresql",
  "host": "erp-db.company.com",
  "port": 5432,
  "database": "erp_prod",
  "username": "readonly_user",
  "password": "{{ encrypted }}",
  "ssl_mode": "require",
  "pool_size": 10,
  "health_check_query": "SELECT 1",
  "health_check_interval": 300,
  "status": "active"
}
```

**REST API 커넥터 등록**:
```json
{
  "connector_id": "conn-mes-api",
  "name": "MES API",
  "type": "rest_api",
  "base_url": "https://mes.company.com/api",
  "auth_type": "oauth2",
  "oauth_config": {
    "token_url": "https://mes.company.com/oauth/token",
    "client_id": "{{ env.MES_CLIENT_ID }}",
    "client_secret": "{{ encrypted }}"
  },
  "health_check_url": "/health",
  "health_check_interval": 300,
  "timeout_ms": 5000,
  "status": "active"
}
```

**헬스 체크 결과**:
```json
{
  "connector_id": "conn-erp-001",
  "status": "healthy",
  "last_check_at": "2025-11-26T11:00:00Z",
  "response_time_ms": 35,
  "consecutive_failures": 0
}
```

**헬스 체크 실패 시 알람**:
```json
{
  "alert_type": "connector_health_check_failed",
  "connector_id": "conn-mes-api",
  "connector_name": "MES API",
  "consecutive_failures": 3,
  "last_error": "Connection timeout after 5000ms",
  "timestamp": "2025-11-26T11:05:00Z"
}
```

**수락 기준**:
- [ ] 4가지 커넥터 타입 지원 (DB, REST, MQTT, OPC UA)
- [ ] 비밀번호/API Key 암호화 저장
- [ ] 헬스 체크 주기적 실행 (5분)
- [ ] 3회 연속 실패 시 알람 발송
- [ ] 커넥터 상태 대시보드 제공

**우선순위**: P1 (High)
**관련 모듈**: Integration Hub
**의존성**: data_connectors 테이블
**테스트 케이스**: C-3-TC-INT-030-*

---

#### INT-FR-040: Drift Detection (스키마 변경 감지)

**요구사항 설명**:
- 시스템은 외부 데이터 소스의 스키마 변경을 주기적으로 감지하고, 변경 발생 시 알림을 발송해야 한다.

**상세 기준**:
- **스키마 스냅샷**: 커넥터 최초 등록 시 스키마 정보 저장
  - DB: 테이블명, 컬럼명, 데이터 타입, 제약조건
  - REST API: 엔드포인트 경로, 파라미터, 응답 스키마
- **주기적 비교**: 일 1회 또는 수동 트리거
- **변경 유형**:
  - **컬럼 추가**: 새 컬럼 발견
  - **컬럼 삭제**: 기존 컬럼 누락
  - **타입 변경**: 데이터 타입 불일치 (예: INT → VARCHAR)
  - **제약조건 변경**: NOT NULL, UNIQUE 등
- **알람 발송**: Slack, Email, Webhook
- **영향 분석**: 해당 커넥터 사용하는 Workflow 목록 표시

**스키마 스냅샷 예시** (DB 테이블):
```json
{
  "connector_id": "conn-erp-001",
  "table_name": "production_orders",
  "snapshot_at": "2025-11-01T00:00:00Z",
  "schema": {
    "columns": [
      { "name": "order_id", "type": "VARCHAR(50)", "nullable": false, "primary_key": true },
      { "name": "product_code", "type": "VARCHAR(20)", "nullable": false },
      { "name": "quantity", "type": "INTEGER", "nullable": false },
      { "name": "created_at", "type": "TIMESTAMP", "nullable": false }
    ],
    "indexes": [
      { "name": "idx_product_code", "columns": ["product_code"] }
    ]
  }
}
```

**스키마 변경 감지 결과**:
```json
{
  "drift_detection_id": "drift-123",
  "connector_id": "conn-erp-001",
  "table_name": "production_orders",
  "detected_at": "2025-11-26T03:00:00Z",
  "changes": [
    {
      "type": "column_added",
      "column_name": "priority",
      "details": { "type": "VARCHAR(10)", "nullable": true }
    },
    {
      "type": "type_changed",
      "column_name": "quantity",
      "old_type": "INTEGER",
      "new_type": "BIGINT"
    }
  ],
  "impact_analysis": {
    "affected_workflows": ["wf-001", "wf-003"],
    "affected_queries": ["query-456"]
  }
}
```

**알람 메시지 예시**:
```
⚠️ Schema Drift Detected

Connector: ERP Database (conn-erp-001)
Table: production_orders

Changes:
- ➕ Column added: priority (VARCHAR(10))
- 🔄 Type changed: quantity (INTEGER → BIGINT)

Affected Workflows: wf-001, wf-003

Action Required: Review and update affected workflows.
```

**수락 기준**:
- [ ] 스키마 스냅샷 자동 저장 (커넥터 등록 시)
- [ ] 일 1회 자동 Drift 검사
- [ ] 4가지 변경 유형 감지 (추가/삭제/타입/제약)
- [ ] 영향 받는 Workflow 목록 표시
- [ ] 알람 발송 (Slack, Email)

**우선순위**: P2 (Medium)
**관련 모듈**: Integration Hub
**의존성**: data_connectors, workflows
**테스트 케이스**: C-3-TC-INT-040-*

---

## 2. 기능 요구사항 - Learning / Rule Ops

### 2.1 개요
Learning Service는 피드백/샘플/로그를 수집하여 Rule·Prompt를 자동/반자동 개선하고 배포/롤백을 관리하는 학습 파이프라인이다.

### 2.2 상세 요구사항

#### LRN-FR-010: Feedback Collection (피드백 수집)

**요구사항 설명**:
- 시스템은 판단 및 채팅 결과에 대한 사용자 피드백(좋아요/싫어요, 코멘트)을 수집하고 저장해야 한다.

**상세 기준**:
- **피드백 타입**:
  - **Judgment 피드백**: 판단 결과의 정확성 평가
  - **Chat 피드백**: 챗봇 응답의 유용성 평가
  - **Workflow 피드백**: 워크플로우 전체 결과 평가
- **피드백 방법**:
  - **Thumbs Up/Down**: 간단한 긍정/부정 평가
  - **Rating**: 1~5점 평가
  - **Comment**: 자유 텍스트 코멘트
  - **Correction**: 올바른 결과 직접 입력
- **저장 정보**:
  - feedback_id, execution_id, user_id
  - feedback_type (thumbs/rating/comment/correction)
  - feedback_value, comment, correct_result
  - timestamp

**Judgment 피드백 수집 UI**:
```
┌────────────────────────────────────────┐
│ Judgment Result                        │
│ Status: HIGH_DEFECT (Confidence: 0.92) │
│ Explanation: 불량률 5% 초과              │
├────────────────────────────────────────┤
│ Was this judgment helpful?             │
│  👍 Yes    👎 No                       │
│                                        │
│ [Optional] Add comment:                │
│ ┌────────────────────────────────────┐ │
│ │ __________________________________ │ │
│ └────────────────────────────────────┘ │
│                                        │
│ [Submit Feedback]                      │
└────────────────────────────────────────┘
```

**피드백 저장 예시**:
```json
{
  "feedback_id": "fb-123",
  "execution_id": "jud-456",
  "execution_type": "judgment",
  "user_id": "user-789",
  "feedback_type": "thumbs",
  "feedback_value": "down",
  "comment": "실제로는 MODERATE_DEFECT였음. 임계값이 너무 낮음.",
  "correct_result": {
    "status": "MODERATE_DEFECT",
    "severity": "warning"
  },
  "timestamp": "2025-11-26T11:30:00Z",
  "metadata": {
    "workflow_id": "wf-001",
    "ruleset_version": "v1.3.0"
  }
}
```

**수락 기준**:
- [ ] 3가지 실행 타입 피드백 수집 (Judgment, Chat, Workflow)
- [ ] 4가지 피드백 방법 지원 (Thumbs, Rating, Comment, Correction)
- [ ] UI에서 피드백 수집 기능 제공
- [ ] 피드백 저장 성공률 > 99%
- [ ] 피드백 익명화 옵션 지원

**우선순위**: P1 (High)
**관련 모듈**: Learning Service, Frontend
**의존성**: feedbacks 테이블
**테스트 케이스**: C-3-TC-LRN-010-*

---

#### LRN-FR-020: Sample Curation (샘플 큐레이션)

**요구사항 설명**:
- 시스템은 피드백이 긍정적인 로그를 `learning_samples`로 분류하여 학습 데이터로 구축해야 한다.

**상세 기준**:
- **샘플 선택 기준**:
  - 피드백 thumbs_up 또는 rating >= 4
  - Judgment confidence >= 0.8
  - 올바른 결과 확인됨 (correction 제공 시 반영)
- **샘플 분류**:
  - **Positive Sample**: 긍정 피드백, 정확한 판단
  - **Negative Sample**: 부정 피드백, 오판
  - **Correction Sample**: 사용자가 올바른 결과 제공
- **데이터 증강**: 유사 케이스 자동 생성 (선택적)
- **샘플 검증**: 도메인 전문가 리뷰 (선택적)

**샘플 큐레이션 파이프라인**:
```
1. 피드백 수집 (feedbacks 테이블)
2. 선택 기준 필터링 (thumbs_up, rating >= 4, confidence >= 0.8)
3. 샘플 추출 (input, output, feedback, metadata)
4. 중복 제거 (input 해시 기반)
5. 품질 검증 (optional: 도메인 전문가 리뷰)
6. learning_samples 저장
```

**Learning Sample 예시**:
```json
{
  "sample_id": "sample-123",
  "source_execution_id": "jud-456",
  "sample_type": "positive",
  "workflow_id": "wf-001",
  "input_data": {
    "line_code": "LINE-A",
    "defect_count": 5,
    "production_count": 100
  },
  "expected_output": {
    "status": "HIGH_DEFECT",
    "severity": "critical",
    "confidence": 0.92
  },
  "feedback_summary": {
    "feedback_type": "thumbs",
    "feedback_value": "up",
    "comment": "정확한 판단이었음"
  },
  "created_at": "2025-11-26T12:00:00Z",
  "validated_by": "user-789",
  "quality_score": 0.95,
  "metadata": {
    "ruleset_version": "v1.3.0",
    "tags": ["defect", "line-a", "high-severity"]
  }
}
```

**샘플 통계 대시보드**:
```
┌──────────────────────────────────────┐
│ Learning Samples Dashboard           │
├──────────────────────────────────────┤
│ Total Samples: 1,234                 │
│ - Positive: 890 (72%)                │
│ - Negative: 234 (19%)                │
│ - Correction: 110 (9%)               │
│                                      │
│ By Workflow:                         │
│ - wf-001: 450 samples                │
│ - wf-002: 320 samples                │
│ - wf-003: 464 samples                │
│                                      │
│ Quality Score: 0.89 avg              │
└──────────────────────────────────────┘
```

**수락 기준**:
- [ ] 피드백 기반 샘플 자동 추출
- [ ] 3가지 샘플 타입 분류 (Positive, Negative, Correction)
- [ ] 중복 제거 (input 해시 기반)
- [ ] 품질 점수 계산
- [ ] 샘플 통계 대시보드 제공

**우선순위**: P1 (High)
**관련 모듈**: Learning Service
**의존성**: feedbacks, learning_samples 테이블
**테스트 케이스**: C-3-TC-LRN-020-*

---

#### LRN-FR-030: Rule Extraction (Rule 추출)

**요구사항 설명**:
- 시스템은 로그 및 샘플을 분석하여 Rhai Rule 후보를 자동 생성하고, 예상 정밀도/커버리지를 산출해야 한다.

**상세 기준**:
- **Rule 추출 알고리즘**:
  - **Decision Tree**: 샘플을 기반으로 결정 트리 생성 → Rhai 코드 변환
  - **Frequent Pattern Mining**: 반복 패턴 추출 → Rule 생성
  - **Manual Template**: 도메인 전문가가 템플릿 제공 → 파라미터 자동 튜닝
- **품질 지표**:
  - **Precision**: TP / (TP + FP) - 예측이 맞는 비율
  - **Recall (Coverage)**: TP / (TP + FN) - 실제를 맞추는 비율
  - **F1-Score**: 2 * (Precision * Recall) / (Precision + Recall)
- **검증**: 별도 테스트 샘플(30%)로 검증
- **승인 워크플로우**: 자동 생성 Rule은 전문가 승인 후 배포

**Rule 추출 프로세스**:
```
1. Learning Samples 조회 (workflow별)
2. Feature Engineering (입력 데이터 변환)
3. Decision Tree 학습 (sklearn DecisionTreeClassifier)
4. Tree → Rhai 코드 변환
5. 검증 세트로 Precision/Recall 계산
6. auto_rule_candidates 저장
7. 전문가 리뷰 요청
```

**자동 생성 Rule 예시**:
```rust
// Auto-generated Rule Candidate
// Precision: 0.92, Recall: 0.85, F1: 0.88

let defect_rate = input.defect_count / input.production_count;
let is_line_a = input.line_code == "LINE-A";

if defect_rate > 0.05 && is_line_a {
    #{
        status: "HIGH_DEFECT",
        severity: "critical",
        confidence: 0.90,
        matched_rules: ["AUTO_RULE_001"]
    }
} else if defect_rate > 0.02 {
    #{
        status: "MODERATE_DEFECT",
        severity: "warning",
        confidence: 0.85,
        matched_rules: ["AUTO_RULE_002"]
    }
} else {
    #{
        status: "NORMAL",
        severity: "info",
        confidence: 0.80,
        matched_rules: ["AUTO_RULE_003"]
    }
}
```

**Rule Candidate 메타데이터**:
```json
{
  "candidate_id": "rc-123",
  "workflow_id": "wf-001",
  "rule_name": "Auto Defect Detection v1",
  "rule_script": "// Rhai code...",
  "extraction_method": "decision_tree",
  "quality_metrics": {
    "precision": 0.92,
    "recall": 0.85,
    "f1_score": 0.88,
    "sample_count": 450,
    "test_sample_count": 135
  },
  "created_at": "2025-11-26T14:00:00Z",
  "status": "pending_approval",
  "reviewer": null,
  "metadata": {
    "feature_importance": {
      "defect_rate": 0.75,
      "line_code": 0.15,
      "shift": 0.10
    }
  }
}
```

**수락 기준**:
- [ ] Decision Tree 기반 Rule 자동 생성
- [ ] Precision, Recall, F1 계산
- [ ] Rule 코드 검증 (Syntax, 실행 가능성)
- [ ] 승인 워크플로우 제공
- [ ] Feature Importance 표시

**우선순위**: P2 (Medium)
**관련 모듈**: Learning Service
**의존성**: learning_samples, auto_rule_candidates 테이블
**테스트 케이스**: C-3-TC-LRN-030-*

---

#### LRN-FR-040: Prompt Tuning (프롬프트 튜닝)

**요구사항 설명**:
- 시스템은 의도 분류 실패 또는 저신뢰도 로그를 식별하여 프롬프트의 Few-shot 예시로 추가해야 한다.

**상세 기준**:
- **튜닝 대상**:
  - Intent 분류 프롬프트
  - Judgment 판단 프롬프트
  - BI 플래너 프롬프트
- **실패 케이스 식별**:
  - Intent confidence < 0.5
  - Judgment confidence < 0.7
  - BI 플래너 파싱 실패 (LLM JSON 파싱 에러)
- **Few-shot 예시 추가**:
  - 실패 케이스에서 올바른 예시 추출
  - 프롬프트 템플릿에 Few-shot 예시 추가
  - 버전 관리 (prompt_versions)
- **자동 평가**: 튜닝 후 성능 향상 확인 (A/B 테스트)

**Intent 분류 프롬프트 튜닝 예시**:

**기존 프롬프트**:
```
You are an intent classifier for manufacturing AI platform.

Classify user input into one of the following intents:
- production_inquiry: 생산량 조회
- defect_inquiry: 불량 조회
- equipment_status: 설비 상태 조회
- report_generation: 보고서 생성

User: {{ user_input }}
Intent:
```

**실패 케이스 발생**:
```
User: "어제 LINE-A 생산 실적 알려줘"
Predicted Intent: equipment_status (confidence: 0.45) ❌
Correct Intent: production_inquiry
```

**튜닝 후 프롬프트** (Few-shot 추가):
```
You are an intent classifier for manufacturing AI platform.

Classify user input into one of the following intents:
- production_inquiry: 생산량 조회
- defect_inquiry: 불량 조회
- equipment_status: 설비 상태 조회
- report_generation: 보고서 생성

Examples:
1. User: "어제 LINE-A 생산 실적 알려줘" → production_inquiry
2. User: "지난주 불량률 통계 보여줘" → defect_inquiry
3. User: "현재 설비 가동률은?" → equipment_status
4. User: "월간 품질 보고서 만들어줘" → report_generation

User: {{ user_input }}
Intent:
```

**프롬프트 버전 관리**:
```json
{
  "prompt_version_id": "pv-123",
  "template_id": "intent_classifier",
  "version": "1.2.0",
  "prompt_text": "You are an intent classifier...",
  "few_shot_examples": [
    { "user": "어제 LINE-A 생산 실적 알려줘", "intent": "production_inquiry" },
    { "user": "지난주 불량률 통계 보여줘", "intent": "defect_inquiry" }
  ],
  "created_at": "2025-11-26T15:00:00Z",
  "created_by": "system_auto_tuning",
  "performance_metrics": {
    "accuracy_before": 0.82,
    "accuracy_after": 0.89,
    "confidence_avg_before": 0.75,
    "confidence_avg_after": 0.84
  },
  "status": "active"
}
```

**수락 기준**:
- [ ] 저신뢰도 케이스 자동 식별 (threshold 설정 가능)
- [ ] Few-shot 예시 자동 추출
- [ ] 프롬프트 템플릿 버전 관리
- [ ] 튜닝 전후 성능 비교
- [ ] A/B 테스트 기능 (선택적)

**우선순위**: P2 (Medium)
**관련 모듈**: Learning Service, Prompt Manager
**의존성**: prompt_templates, llm_calls 테이블
**테스트 케이스**: C-3-TC-LRN-040-*

---

#### LRN-FR-050: Deployment (배포)

**요구사항 설명**:
- 시스템은 Rule/Prompt의 버전을 관리하고, 카나리 배포(Canary Deployment) 및 롤백 기능을 제공해야 한다.

**상세 기준**:
- **배포 전략**:
  - **Canary**: 트래픽의 일부(예: 10%)만 신규 버전으로 라우팅
  - **Blue-Green**: 구버전(Blue)과 신버전(Green) 동시 운영, 전환 후 구버전 종료
  - **Rolling**: 점진적 교체 (노드별 순차 배포)
- **트래픽 라우팅**: workflow 인스턴스별 랜덤 또는 사용자별 sticky
- **모니터링**: 신규 버전의 에러율, 지연시간, 정확도 실시간 추적
- **자동 롤백**: 에러율 > threshold 시 자동 롤백
- **수동 롤백**: 관리자가 이전 버전으로 즉시 롤백

**Canary 배포 설정**:
```json
{
  "deployment_id": "deploy-123",
  "target_type": "ruleset",
  "target_id": "ruleset-456",
  "workflow_id": "wf-001",
  "strategy": "canary",
  "old_version": "v1.3.0",
  "new_version": "v1.4.0",
  "canary_config": {
    "traffic_percentage": 10,
    "duration_minutes": 60,
    "success_criteria": {
      "error_rate_max": 0.01,
      "latency_p95_max": 2000,
      "accuracy_min": 0.85
    },
    "auto_rollback": true
  },
  "status": "in_progress",
  "started_at": "2025-11-26T16:00:00Z"
}
```

**배포 상태 모니터링**:
```
┌───────────────────────────────────────────┐
│ Canary Deployment: ruleset-456 v1.4.0    │
├───────────────────────────────────────────┤
│ Traffic: 10% → v1.4.0, 90% → v1.3.0      │
│ Duration: 30min / 60min                   │
│                                           │
│ Metrics (v1.4.0):                         │
│ - Error Rate: 0.005 (✓ < 0.01)           │
│ - Latency P95: 1,200ms (✓ < 2,000ms)     │
│ - Accuracy: 0.88 (✓ >= 0.85)             │
│                                           │
│ Status: ✅ Healthy (Auto-promote at 60min) │
│                                           │
│ [Promote to 100%]  [Rollback]            │
└───────────────────────────────────────────┘
```

**자동 롤백 트리거**:
```json
{
  "deployment_id": "deploy-123",
  "rollback_triggered": true,
  "rollback_reason": "error_rate_exceeded",
  "metrics_at_rollback": {
    "error_rate": 0.015,
    "threshold": 0.01,
    "requests_affected": 15
  },
  "rolled_back_at": "2025-11-26T16:30:00Z",
  "rolled_back_to_version": "v1.3.0"
}
```

**수락 기준**:
- [ ] 3가지 배포 전략 지원 (Canary, Blue-Green, Rolling)
- [ ] 트래픽 라우팅 정확도 ±1% (10% Canary면 9~11%)
- [ ] 배포 중 메트릭 실시간 수집
- [ ] 자동 롤백 조건 충족 시 즉시 롤백
- [ ] 수동 롤백 기능 제공

**우선순위**: P1 (High)
**관련 모듈**: Learning Service, Rule Ops
**의존성**: rule_deployments, prompt_versions 테이블
**테스트 케이스**: C-3-TC-LRN-050-*

---

## 3. 기능 요구사항 - Chat / Intent

### 3.1 개요
Chat/Intent Router는 사용자 발화를 분석하여 의도(Intent)로 분류하고, 필요한 파라미터(Slot)를 추출하며, 적절한 LLM 모델로 라우팅하는 챗봇 엔진이다.

### 3.2 상세 요구사항

#### CHAT-FR-010: Intent Recognition (의도 인식)

**요구사항 설명**:
- 시스템은 사용자 발화를 분석하여 정의된 의도(Intent)로 분류하고 신뢰도를 산출해야 한다.

**상세 기준**:
- **Intent 정의**:
  - intent_id, name, description
  - required_slots (필수 파라미터)
  - examples (Few-shot 예시)
- **분류 방법**:
  - LLM 기반: Few-shot 프롬프트 + 사용자 발화
  - 신뢰도 산출: LLM 응답에서 confidence 추출
- **지원 Intent 예시**:
  - production_inquiry: 생산량 조회
  - defect_inquiry: 불량 조회
  - equipment_status: 설비 상태 조회
  - report_generation: 보고서 생성
  - workflow_execution: 워크플로우 실행

**Intent 정의 예시**:
```json
{
  "intent_id": "production_inquiry",
  "name": "생산량 조회",
  "description": "특정 기간/라인의 생산량 정보 조회",
  "required_slots": ["line_code", "date_range"],
  "optional_slots": ["product_code", "shift"],
  "examples": [
    "어제 LINE-A 생산량 알려줘",
    "지난주 전체 라인 생산 실적 보여줘",
    "11월 20일 LINE-B의 PROD-123 생산량은?"
  ],
  "response_template": "{{ line_code }}의 {{ date_range }} 생산량은 {{ production_count }}개입니다."
}
```

**Intent 분류 프롬프트**:
```
You are an intent classifier for a manufacturing AI platform.

Available Intents:
1. production_inquiry: 생산량 조회
   Examples: "어제 LINE-A 생산량 알려줘", "지난주 생산 실적 보여줘"

2. defect_inquiry: 불량 조회
   Examples: "오늘 불량률은?", "LINE-B 불량 통계 보여줘"

3. equipment_status: 설비 상태 조회
   Examples: "현재 설비 가동률은?", "LINE-A 설비 상태 확인"

4. report_generation: 보고서 생성
   Examples: "월간 품질 보고서 만들어줘", "주간 생산 리포트 작성"

User: {{ user_input }}

Classify the intent and provide confidence score (0.0-1.0).
Respond in JSON:
{
  "intent": "production_inquiry",
  "confidence": 0.92,
  "reasoning": "User is asking about production quantity for a specific line and date"
}
```

**Intent 분류 결과**:
```json
{
  "utterance": "어제 LINE-A 생산량 알려줘",
  "intent": "production_inquiry",
  "confidence": 0.92,
  "reasoning": "User is asking about production quantity for LINE-A on yesterday",
  "alternative_intents": [
    { "intent": "equipment_status", "confidence": 0.05 },
    { "intent": "report_generation", "confidence": 0.03 }
  ]
}
```

**수락 기준**:
- [ ] Intent 정의 CRUD API
- [ ] LLM 기반 Intent 분류 성공률 > 90%
- [ ] 신뢰도 산출 정확도 (캘리브레이션)
- [ ] 대체 Intent 제시 (Top-3)
- [ ] Few-shot 예시 자동 업데이트 (LRN-FR-040 연계)

**우선순위**: P0 (Critical)
**관련 모듈**: Chat Engine
**의존성**: intents, llm_calls 테이블
**테스트 케이스**: C-3-TC-CHAT-010-*

---

#### CHAT-FR-020: Slot Filling (슬롯 추출)

**요구사항 설명**:
- 시스템은 사용자 발화 내에서 필요한 파라미터(Slot)를 추출해야 한다.

**상세 기준**:
- **Slot 타입**:
  - **Entity**: 고유명사 (라인명, 제품명, 설비명)
  - **Date/Time**: 날짜, 시간 범위
  - **Number**: 수량, 비율
  - **Enum**: 사전 정의된 값 (shift: day/night/all)
- **추출 방법**:
  - NER (Named Entity Recognition): spaCy, Stanza
  - LLM 기반: Few-shot 프롬프트
  - 정규표현식: 날짜, 숫자 패턴
- **정규화**: 추출된 값을 표준 형식으로 변환
  - "어제" → "2025-11-25"
  - "지난주" → "2025-11-18 ~ 2025-11-24"

**Slot Filling 프롬프트**:
```
Extract the following slots from the user utterance:

Required Slots:
- line_code: Line name (e.g., LINE-A, LINE-B)
- date_range: Date or date range (e.g., yesterday, last week, 2025-11-20)

Optional Slots:
- product_code: Product name (e.g., PROD-123)
- shift: Shift type (day, night, all)

User: {{ user_input }}

Respond in JSON:
{
  "slots": {
    "line_code": "LINE-A",
    "date_range": "yesterday",
    "product_code": null,
    "shift": null
  },
  "missing_required_slots": []
}
```

**Slot 추출 결과**:
```json
{
  "utterance": "어제 LINE-A 생산량 알려줘",
  "intent": "production_inquiry",
  "slots": {
    "line_code": { "value": "LINE-A", "confidence": 0.95 },
    "date_range": { "value": "yesterday", "normalized": "2025-11-25", "confidence": 0.90 },
    "product_code": { "value": null, "confidence": 0.0 },
    "shift": { "value": null, "confidence": 0.0 }
  },
  "missing_required_slots": [],
  "all_slots_filled": true
}
```

**슬롯 누락 시 예시**:
```json
{
  "utterance": "생산량 알려줘",
  "intent": "production_inquiry",
  "slots": {
    "line_code": { "value": null },
    "date_range": { "value": null }
  },
  "missing_required_slots": ["line_code", "date_range"],
  "all_slots_filled": false
}
```

**수락 기준**:
- [ ] 4가지 Slot 타입 지원 (Entity, Date/Time, Number, Enum)
- [ ] Slot 추출 정확도 > 85%
- [ ] 날짜 정규화 정확도 > 95% (상대 날짜 → 절대 날짜)
- [ ] 누락된 필수 Slot 식별
- [ ] Slot confidence 산출

**우선순위**: P0 (Critical)
**관련 모듈**: Chat Engine
**의존성**: intents 테이블
**테스트 케이스**: C-3-TC-CHAT-020-*

---

#### CHAT-FR-030: Ambiguity Handling (애매함 처리)

**요구사항 설명**:
- 시스템은 의도 신뢰도가 낮거나 필수 슬롯이 누락된 경우, 사용자에게 되묻는 질문을 생성해야 한다.

**상세 기준**:
- **애매함 조건**:
  - Intent confidence < 0.5
  - 필수 Slot 누락
  - 여러 Intent 유사한 신뢰도 (Top-2 차이 < 0.2)
- **되묻기 전략**:
  - Intent 애매: "생산량 조회와 불량 조회 중 어느 것을 원하시나요?"
  - Slot 누락: "어떤 라인의 생산량을 조회할까요? (예: LINE-A, LINE-B)"
  - 다중 해석: "LINE-A의 어제 생산량 또는 오늘 생산량 중 어느 것인가요?"
- **대화 컨텍스트**: 이전 대화 내용 유지하여 연속 질문 지원

**애매한 발화 예시 1** (Intent 불명확):
```
User: "실적 보여줘"

System Analysis:
- production_inquiry: 0.45
- defect_inquiry: 0.40
- report_generation: 0.15

System Response:
"어떤 실적을 조회하시겠습니까?
1. 생산량 실적
2. 불량 실적
3. 종합 보고서"
```

**애매한 발화 예시 2** (Slot 누락):
```
User: "생산량 알려줘"

System Analysis:
- Intent: production_inquiry (confidence: 0.92)
- Missing Slots: line_code, date_range

System Response:
"생산량 조회를 도와드리겠습니다.
- 라인 코드를 알려주세요 (예: LINE-A, LINE-B)
- 조회 기간을 알려주세요 (예: 어제, 지난주, 11월 20일)"
```

**대화 컨텍스트 유지 예시**:
```
User: "LINE-A"
[Context: 이전에 라인 코드 요청됨]

System Analysis:
- 이전 Context: Intent=production_inquiry, missing_slots=[line_code, date_range]
- 현재 입력: "LINE-A" → line_code로 매핑

System Response:
"LINE-A의 생산량을 조회하겠습니다. 조회 기간을 알려주세요 (예: 어제, 지난주)"
```

**수락 기준**:
- [ ] Intent confidence < 0.5 시 되묻기 생성
- [ ] 필수 Slot 누락 시 가이드 메시지 생성
- [ ] 대화 컨텍스트 유지 (세션별)
- [ ] 연속 질문 지원 (Multi-turn dialog)
- [ ] 되묻기 응답 시간 < 2초

**우선순위**: P1 (High)
**관련 모듈**: Chat Engine
**의존성**: chat_sessions 테이블
**테스트 케이스**: C-3-TC-CHAT-030-*

---

#### CHAT-FR-040: Model Routing (모델 라우팅)

**요구사항 설명**:
- 시스템은 작업의 난이도와 비용 정책에 따라 고성능 모델(GPT-4) 또는 경량 모델(Haiku)로 라우팅해야 한다.

**상세 기준**:
- **라우팅 기준**:
  - **Task Complexity**: Intent 복잡도, Slot 개수
  - **Context Length**: 대화 히스토리 길이
  - **Cost Policy**: 사용자 등급 (Free/Standard/Premium)
  - **Latency Requirement**: 실시간 응답 필요 여부
- **모델 선택 매트릭스**:

| Task Complexity | Context Length | Cost Policy | Model |
|-----------------|----------------|-------------|-------|
| Low | Short | Free | Haiku |
| Low | Long | Standard | Haiku |
| Medium | Short | Standard | GPT-4o-mini |
| Medium | Long | Premium | GPT-4o |
| High | Any | Premium | GPT-4 |

- **모델 메타데이터**:
  - model_id, provider (OpenAI, Anthropic)
  - cost_per_1k_tokens, latency_avg
  - max_context_length

**라우팅 로직**:
```python
def select_model(intent, slots, context_length, user_tier):
    complexity = calculate_complexity(intent, slots)

    if user_tier == "free":
        return "haiku"

    if complexity == "low" and context_length < 1000:
        return "haiku"
    elif complexity == "medium":
        return "gpt-4o-mini"
    else:
        return "gpt-4"

def calculate_complexity(intent, slots):
    if intent in ["production_inquiry", "defect_inquiry"]:
        return "low"
    elif intent in ["report_generation", "workflow_execution"]:
        return "high"
    else:
        return "medium"
```

**라우팅 결과 로깅**:
```json
{
  "session_id": "sess-123",
  "utterance": "어제 LINE-A 생산량 알려줘",
  "intent": "production_inquiry",
  "complexity": "low",
  "context_length": 150,
  "user_tier": "standard",
  "selected_model": "haiku",
  "selection_reason": "Low complexity + short context",
  "cost_estimated": 0.0001,
  "latency_estimated": 0.8
}
```

**수락 기준**:
- [ ] 4가지 모델 지원 (Haiku, GPT-4o-mini, GPT-4o, GPT-4)
- [ ] Task complexity 계산 로직
- [ ] Cost policy 적용 (사용자 등급)
- [ ] 모델 선택 이유 로깅
- [ ] 비용 및 지연 시간 추정

**우선순위**: P2 (Medium)
**관련 모듈**: Chat Engine
**의존성**: llm_calls, users 테이블
**테스트 케이스**: C-3-TC-CHAT-040-*

---

## 4. 기능 요구사항 - Security

### 4.1 개요
Security 모듈은 인증/인가, PII 마스킹, 감사 로그 기능을 제공한다.

### 4.2 상세 요구사항

#### SEC-FR-010: Authentication & Authorization (인증 및 인가)

**요구사항 설명**:
- 시스템은 모든 API 요청에 대해 OAuth2/JWT 인증을 수행하고, RBAC 기반으로 리소스 접근을 제어해야 한다.

**상세 기준**:
- **인증 방식**:
  - OAuth 2.0 (Authorization Code Grant)
  - JWT (JSON Web Token)
  - API Key (M2M 통신)
- **역할 정의**:
  - **Admin**: 전체 시스템 설정 및 사용자 관리
  - **Manager**: Workflow 생성/수정, Rule 승인
  - **Analyst**: BI 분석, 대시보드 조회
  - **Operator**: Workflow 실행, 결과 조회
  - **Viewer**: 읽기 전용
- **권한 체크**: API 엔드포인트별 필요 권한 정의

**JWT 토큰 구조**:
```json
{
  "sub": "user-123",
  "tenant_id": "tenant-456",
  "email": "user@company.com",
  "roles": ["manager", "analyst"],
  "permissions": ["workflow:create", "workflow:execute", "bi:query"],
  "iat": 1732608000,
  "exp": 1732694400
}
```

**권한 매트릭스**:

| 리소스 | Admin | Manager | Analyst | Operator | Viewer |
|--------|-------|---------|---------|----------|--------|
| Workflow 생성/수정 | ✅ | ✅ | ❌ | ❌ | ❌ |
| Workflow 실행 | ✅ | ✅ | ❌ | ✅ | ❌ |
| Judgment 조회 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Rule 승인/배포 | ✅ | ✅ | ❌ | ❌ | ❌ |
| BI 분석 생성 | ✅ | ✅ | ✅ | ❌ | ❌ |
| BI 분석 조회 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 사용자 관리 | ✅ | ❌ | ❌ | ❌ | ❌ |

**API 권한 체크 예시**:
```http
POST /api/v1/workflows
Authorization: Bearer {{ jwt_token }}

Response (403 Forbidden):
{
  "error": "insufficient_permissions",
  "message": "User does not have 'workflow:create' permission",
  "required_permission": "workflow:create",
  "user_roles": ["operator"]
}
```

**수락 기준**:
- [ ] OAuth 2.0 / JWT 인증 구현
- [ ] 5가지 역할 지원 (Admin, Manager, Analyst, Operator, Viewer)
- [ ] RBAC 권한 체크 (API 엔드포인트별)
- [ ] JWT 토큰 만료 및 갱신
- [ ] 권한 부족 시 403 에러 반환

**우선순위**: P0 (Critical)
**관련 모듈**: Auth Service
**의존성**: users, roles, permissions 테이블
**테스트 케이스**: C-3-TC-SEC-010-*

---

#### SEC-FR-020: PII Masking (개인정보 마스킹)

**요구사항 설명**:
- 시스템은 LLM 입력 및 로그 저장 시 개인정보(PII) 패턴을 탐지하여 마스킹 처리해야 한다.

**상세 기준**:
- **PII 패턴**:
  - 이름: 한글 2~4자
  - 이메일: email@domain.com
  - 전화번호: 010-1234-5678
  - 주민등록번호: 123456-1234567
  - 신용카드 번호: 1234-5678-9012-3456
- **마스킹 방법**:
  - 이름: 홍\*동
  - 이메일: u\*\*\*@domain.com
  - 전화번호: 010-\*\*\*\*-5678
  - 주민등록번호: 123456-\*\*\*\*\*\*\*
- **적용 위치**:
  - LLM 요청 전 입력 마스킹
  - 로그 저장 시 마스킹
  - 응답 출력 시 마스킹 (선택적)

**PII 탐지 및 마스킹 예시**:

**원본 텍스트**:
```
고객 홍길동(010-1234-5678, hong@example.com)이 주문한
제품 PROD-123의 배송 상태를 확인해주세요.
주민등록번호: 801201-1234567
```

**마스킹 후**:
```
고객 홍*동(010-****-5678, h***@example.com)이 주문한
제품 PROD-123의 배송 상태를 확인해주세요.
주민등록번호: 801201-*******
```

**마스킹 로직**:
```python
import re

def mask_pii(text):
    # 이름 (한글 2~4자)
    text = re.sub(r'([가-힣])([가-힣]+)([가-힣])', r'\1*\3', text)

    # 이메일
    text = re.sub(r'([a-zA-Z0-9])([a-zA-Z0-9._%+-]+)(@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', r'\1***\3', text)

    # 전화번호
    text = re.sub(r'(\d{3})-(\d{4})-(\d{4})', r'\1-****-\3', text)

    # 주민등록번호
    text = re.sub(r'(\d{6})-(\d{7})', r'\1-*******', text)

    return text
```

**수락 기준**:
- [ ] 5가지 PII 패턴 탐지 (이름, 이메일, 전화, 주민번호, 카드번호)
- [ ] 탐지 정확도 > 95% (False Positive < 5%)
- [ ] LLM 입력 자동 마스킹
- [ ] 로그 저장 시 자동 마스킹
- [ ] 마스킹 설정 On/Off 가능

**우선순위**: P1 (High)
**관련 모듈**: Security Service
**의존성**: 없음
**테스트 케이스**: C-3-TC-SEC-020-*

---

#### SEC-FR-030: Audit Log (감사 로그)

**요구사항 설명**:
- 시스템은 주요 변경 사항(배포, 승인, 설정 변경)에 대해 행위자, 시각, 변경 내용을 감사 로그로 기록해야 한다.

**상세 기준**:
- **로그 대상**:
  - Rule/Prompt 배포 및 롤백
  - Workflow 생성/수정/삭제
  - 사용자 권한 변경
  - 시스템 설정 변경
  - 데이터 삭제 (물리 삭제)
- **로그 항목**:
  - audit_log_id, tenant_id, user_id
  - action_type (create/update/delete/deploy/rollback/approve)
  - resource_type (workflow/ruleset/prompt/user/setting)
  - resource_id, old_value, new_value
  - timestamp, ip_address, user_agent
- **불변성**: 로그는 수정/삭제 불가 (Append-only)

**감사 로그 예시**:
```json
{
  "audit_log_id": "audit-123",
  "tenant_id": "tenant-456",
  "user_id": "user-789",
  "action_type": "deploy",
  "resource_type": "ruleset",
  "resource_id": "ruleset-456",
  "old_value": {
    "version": "v1.3.0",
    "status": "active"
  },
  "new_value": {
    "version": "v1.4.0",
    "status": "active",
    "deployment_strategy": "canary",
    "traffic_percentage": 10
  },
  "timestamp": "2025-11-26T16:00:00Z",
  "ip_address": "192.168.1.100",
  "user_agent": "Mozilla/5.0...",
  "metadata": {
    "deployment_id": "deploy-123",
    "reviewer": "user-admin"
  }
}
```

**감사 로그 조회 API**:
```http
GET /api/v1/audit-logs?resource_type=ruleset&action_type=deploy&start_date=2025-11-01

Response:
{
  "logs": [
    { "audit_log_id": "audit-123", ... },
    { "audit_log_id": "audit-124", ... }
  ],
  "total_count": 15,
  "page": 1,
  "page_size": 20
}
```

**수락 기준**:
- [ ] 5가지 액션 타입 로깅 (create/update/delete/deploy/approve)
- [ ] 로그 불변성 보장 (수정/삭제 불가)
- [ ] old_value, new_value 차이 명시
- [ ] 로그 조회 API (필터링, 페이징)
- [ ] 로그 보존 기간 2년 이상

**우선순위**: P1 (High)
**관련 모듈**: Security Service
**의존성**: audit_logs 테이블
**테스트 케이스**: C-3-TC-SEC-030-*

---

## 5. 기능 요구사항 - Observability

### 5.1 개요
Observability 모듈은 구조화 로깅, 메트릭 수집, 분산 추적 기능을 제공한다.

### 5.2 상세 요구사항

#### OBS-FR-010: Structured Logging (구조화 로깅)

**요구사항 설명**:
- 시스템은 모든 서비스 로그에 Trace ID, Tenant ID를 포함하여 구조화된 로그(JSON)를 남겨야 한다.

**상세 기준**:
- **로그 레벨**: DEBUG, INFO, WARN, ERROR, FATAL
- **필수 필드**:
  - timestamp (ISO 8601)
  - level, message
  - trace_id, span_id (분산 추적)
  - tenant_id, user_id
  - service_name, host_name
- **로그 출력**: stdout (JSON 형식) → 로그 수집기(Fluent Bit, Logstash)

**구조화 로그 예시**:
```json
{
  "timestamp": "2025-11-26T16:30:15.123Z",
  "level": "INFO",
  "message": "Judgment execution completed",
  "trace_id": "a1b2c3d4e5f6",
  "span_id": "span-123",
  "tenant_id": "tenant-456",
  "user_id": "user-789",
  "service_name": "judgment-engine",
  "host_name": "pod-judgment-01",
  "execution_id": "jud-123",
  "workflow_id": "wf-001",
  "result_status": "HIGH_DEFECT",
  "confidence": 0.92,
  "execution_time_ms": 1250,
  "method_used": "hybrid_weighted"
}
```

**에러 로그 예시**:
```json
{
  "timestamp": "2025-11-26T16:30:20.456Z",
  "level": "ERROR",
  "message": "MCP tool execution failed",
  "trace_id": "a1b2c3d4e5f6",
  "tenant_id": "tenant-456",
  "service_name": "mcp-hub",
  "tool_id": "excel-read",
  "error_type": "timeout",
  "error_message": "MCP server did not respond within 10000ms",
  "stack_trace": "Traceback (most recent call last):\n  File ...",
  "retry_attempts": 3
}
```

**수락 기준**:
- [ ] JSON 형식 구조화 로그
- [ ] 필수 필드 포함 (trace_id, tenant_id, service_name 등)
- [ ] 로그 레벨 설정 가능 (환경변수)
- [ ] 민감 정보 마스킹 (PII)
- [ ] 로그 수집기 연동 (Fluent Bit)

**우선순위**: P0 (Critical)
**관련 모듈**: All Services
**의존성**: 로그 수집 인프라
**테스트 케이스**: C-3-TC-OBS-010-*

---

#### OBS-FR-020: Metrics Collection (메트릭 수집)

**요구사항 설명**:
- 시스템은 서비스 지연, 에러율, 비즈니스 지표(판단 정확도 등)를 수집하여 모니터링 시스템에 제공해야 한다.

**상세 기준**:
- **메트릭 타입**:
  - **Counter**: 누적 카운트 (요청 수, 에러 수)
  - **Gauge**: 현재 값 (활성 세션 수, CPU 사용률)
  - **Histogram**: 분포 (응답 시간, 페이로드 크기)
  - **Summary**: 통계 (P50, P95, P99)
- **비즈니스 메트릭**:
  - Judgment 정확도, 캐시 적중률
  - Workflow 성공률, 평균 실행 시간
  - LLM 비용, 토큰 사용량
  - Intent 분류 정확도
- **시스템 메트릭**:
  - CPU, 메모리, 디스크 사용률
  - 네트워크 I/O, DB 연결 수
- **출력 형식**: Prometheus 포맷

**메트릭 정의 예시** (Prometheus):
```python
from prometheus_client import Counter, Histogram, Gauge

# Counter: Judgment 실행 횟수
judgment_executions_total = Counter(
    'judgment_executions_total',
    'Total number of judgment executions',
    ['tenant_id', 'workflow_id', 'status']
)

# Histogram: Judgment 실행 시간
judgment_execution_duration_seconds = Histogram(
    'judgment_execution_duration_seconds',
    'Judgment execution duration in seconds',
    ['tenant_id', 'workflow_id', 'method']
)

# Gauge: 활성 워크플로우 인스턴스
workflow_instances_active = Gauge(
    'workflow_instances_active',
    'Number of active workflow instances',
    ['tenant_id', 'workflow_id']
)

# Counter: LLM 호출 비용
llm_cost_usd_total = Counter(
    'llm_cost_usd_total',
    'Total LLM cost in USD',
    ['tenant_id', 'model', 'provider']
)
```

**메트릭 수집 예시**:
```python
# Judgment 실행
judgment_executions_total.labels(
    tenant_id='tenant-456',
    workflow_id='wf-001',
    status='success'
).inc()

judgment_execution_duration_seconds.labels(
    tenant_id='tenant-456',
    workflow_id='wf-001',
    method='hybrid_weighted'
).observe(1.25)
```

**Prometheus 스크래핑 엔드포인트**:
```http
GET /metrics

# HELP judgment_executions_total Total number of judgment executions
# TYPE judgment_executions_total counter
judgment_executions_total{tenant_id="tenant-456",workflow_id="wf-001",status="success"} 1234

# HELP judgment_execution_duration_seconds Judgment execution duration in seconds
# TYPE judgment_execution_duration_seconds histogram
judgment_execution_duration_seconds_bucket{tenant_id="tenant-456",workflow_id="wf-001",method="hybrid_weighted",le="0.5"} 120
judgment_execution_duration_seconds_bucket{tenant_id="tenant-456",workflow_id="wf-001",method="hybrid_weighted",le="1.0"} 450
judgment_execution_duration_seconds_bucket{tenant_id="tenant-456",workflow_id="wf-001",method="hybrid_weighted",le="2.0"} 890
judgment_execution_duration_seconds_sum{tenant_id="tenant-456",workflow_id="wf-001",method="hybrid_weighted"} 1543.25
judgment_execution_duration_seconds_count{tenant_id="tenant-456",workflow_id="wf-001",method="hybrid_weighted"} 1234
```

**수락 기준**:
- [ ] 4가지 메트릭 타입 지원 (Counter, Gauge, Histogram, Summary)
- [ ] 비즈니스 메트릭 수집 (판단 정확도, 캐시 적중률 등)
- [ ] Prometheus 포맷 출력 (/metrics 엔드포인트)
- [ ] Tenant/Workflow별 메트릭 레이블링
- [ ] Grafana 대시보드 연동

**우선순위**: P0 (Critical)
**관련 모듈**: All Services
**의존성**: Prometheus, Grafana
**테스트 케이스**: C-3-TC-OBS-020-*

---

## 다음 파일로 계속

본 문서는 A-2-2로, Integration, Learning, Chat, Security, Observability 요구사항을 포함한다.

**다음 파일**:
- **A-2-3**: 비기능 요구사항 (성능, 보안, 가용성, 품질)
- **A-2-4**: 데이터/인터페이스 요구사항 및 추적성 매트릭스

---

## 문서 이력
| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2025-11-26 | AI Factory Team | 초안 작성 |
