# A-3. Use Case / User Story 정의서

## 1. Actor 정의
- **경영자/품질 책임자**: KPI 모니터링, 정책 승인, 리포트 수신
- **생산/설비 팀장**: 라인 상태 조회, 경보/조치 실행·승인, 작업지시 확인
- **QA/QC**: CCP/HACCP 로그 검증, 샘플 검사/Release 승인, 이탈 RCA
- **데이터/IT 관리자**: 커넥터/스키마/보안 설정, 배포/모니터링, 백업
- **시스템/에이전트**: Intent Router, Planner/Executor, Judgment Engine, BI Service, MCP ToolHub, Learning Service

## 2. 주요 Use Case 목록 (예시)
| ID | 이름 | 주요 Actor | 개요 |
| --- | --- | --- | --- |
| UC-01 | 판단 실행(라인 이상 판단) | 생산팀장, Judgment Engine | 라인/시간/지표 JSON을 입력 받아 상태(normal/warning/critical)와 조치안을 반환 |
| UC-02 | BI 인사이트 조회 | 경영자, BI Planner | “지난주 불량 요약” 자연어 요청 → 차트/요약 카드 생성 |
| UC-03 | 워크플로우 설계/승인 | 생산팀장, WF Builder | 자연어 요구 → LLM이 DSL 생성 → 사람이 검토/승인 후 활성화 |
| UC-04 | 커넥터 등록/데이터 수집 | 데이터관리자, MCP Hub | ERP/MES/Excel 연결을 등록/검증하고 raw→fact 적재 스케줄 실행 |
| UC-05 | 피드백·학습 | 모든 사용자, Learning | 판단 결과에 👍/👎/코멘트 → Rule 후보/Prompt 개선안 생성 |
| UC-06 | 로그/감사 조회 | QA/감사, Observability | 판단/Rule/모델/워크플로우 실행 로그를 조회/필터링 |

## 3. Use Case 상세 (예: UC-01 판단 실행)
- **목적**: 라인/지표 기반 실시간 품질/설비 판단과 조치 제안
- **선행조건**: workflow_id와 input_data(line, shift, kpi값 등)가 유효; 커넥터/데이터 최신; Rule/LLM 정책 활성
- **후행조건**: judgment_executions 로그 저장; recommended_actions 제공; 필요 시 WF Action(알림/티켓) 트리거
- **기본 시나리오 (메인 플로우)**
  1) 사용자/시스템이 `POST /judgment/execute` 호출 (workflow_id+input_data)
  2) 캐시 조회 후 Miss 시 Rule 평가 → 필요 시 LLM 보완 → Hybrid 결과 산출
  3) result/confidence/method_used/explanation/recommended_actions 반환
  4) raw_trace/llm_trace/Rule 버전과 함께 로그 저장, 캐시에 저장
  5) 옵션에 따라 WF Action 실행(알림/티켓)
- **예외 시나리오**
  - 입력 검증 실패: 400 반환, validation_error 로그
  - Rule/LLM 실패: fallback 정책 적용(LLM만/Rule만/기본값), error_code 남김
  - 외부 의존성(MCP/DB) 실패: 재시도 후 실패 시 degrade 결과와 알람

### UC-03 워크플로우 설계/승인 (요약)
- 선행조건: 노드 카탈로그/DSL 스키마 고정
- 메인 플로우: NL 요구 → LLM 계획 → DSL JSON → 사람이 승인 → 저장/버전업 → 활성화
- 예외: 승인 거절/Validation 실패 시 수정 요청, 이전 버전 유지

### UC-04 커넥터 등록/수집 (요약)
- 선행조건: 인증정보/네트워크 접근 권한 확보
- 메인 플로우: connector 생성 → 테스트 → 스케줄 등록 → raw 적재 → ETL→fact → 모니터링
- 예외: 인증 실패/스키마 불일치 시 알람 및 롤백

## 4. User Story 목록 (Agile 예시)
- As a **생산팀장**, I want to **get real-time judgment for L01 night shift defect rate**, so that **I can stop the line before defects escalate**.
- As a **QA**, I want to **approve or reject recommended Rules**, so that **only validated policies affect CCP decisions**.
- As a **경영자**, I want to **ask “지난주 불량 요약” in chat and see charts**, so that **I can review trends without SQL**.
- As an **IT 관리자**, I want to **register an ERP connector and monitor its health**, so that **data feeds stay reliable**.
- As a **Learning agent**, I want to **gather feedback and propose new rules**, so that **the system improves over time**.
