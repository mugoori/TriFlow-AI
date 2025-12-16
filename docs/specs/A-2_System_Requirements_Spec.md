# A-2. System Requirements Specification (SRS)

## 1. 용어 정의 (발췌)
- **Judgment**: 입력 JSON을 받아 Rule+LLM Hybrid로 상태/조치/설명을 반환하는 코어 판단
- **Workflow(WWF)**: DSL로 정의된 다단계 실행 플로우. 노드 타입: DATA/BI/JUDGMENT/MCP/ACTION/APPROVAL/WAIT/SWITCH/PARALLEL/COMPENSATION/DEPLOY/ROLLBACK/SIMULATE
- **MCP ToolHub**: 외부 MCP 서버(Excel/GDrive/Jira/로봇 등) 호출을 표준화하는 게이트웨이
- **Learning Service**: 피드백/샘플/로그를 수집하여 Rule·Prompt를 자동/반자동 개선하고 배포/롤백을 관리
- **BI Planner**: 자연어 요청을 dataset/metric/component 계획(analysis_plan)으로 변환하는 LLM 플래너

## 2. 전제조건 및 제약
- **연동 시스템**: ERP/MES/센서 DB(포스트그레스/마이SQL/MSSQL), 파일(Excel/CSV), MCP 서버(추후 로봇/PLC 포함)
- **운영 환경**: Kubernetes 또는 Docker Compose, Postgres 14+, Redis 6+, VectorDB(pgvector)
- **보안/규제**: 고객사 망 분리 가능성, 외부 LLM 사용 시 데이터 마스킹/비식별화 필요, 판단/CCP 로그 보존 ≥ 2년
- **클라이언트**: Web/Slack/Chat UI, 향후 음성/모바일 확장. 최소 Chrome 최신/Edge 지원

## 3. 기능 요구사항 (엔진/기능별)

### Judgment Engine (JUD)
- **JUD-FR-010 (Input Validation)**: `workflow_id` 및 `input_data` 스키마 유효성을 검증하고, 필수 필드 누락 시 에러를 반환한다.
- **JUD-FR-020 (Rule Execution)**: 지정된 Ruleset(Rhai)을 실행하여 Rule 기반의 결과(result)와 신뢰도(confidence)를 산출한다.
- **JUD-FR-030 (LLM Fallback)**: Rule 신뢰도가 임계값 미만이거나 정책이 `LLM_FALLBACK`인 경우 LLM을 호출하여 판단을 보완한다.
- **JUD-FR-040 (Hybrid Aggregation)**: Rule과 LLM 결과를 `Hybrid Policy`(가중치, 게이트 조건)에 따라 병합하여 최종 결과를 도출한다.
- **JUD-FR-050 (Explanation)**: 요청 옵션(`need_explanation`)에 따라 판단의 근거(explanation), 추천 조치(recommended_actions), 증거 데이터(evidence)를 생성한다.
- **JUD-FR-060 (Caching)**: `workflow_id`와 입력 데이터 해시를 키로 Redis 캐시를 조회하여, 유효한 캐시가 있을 경우 즉시 반환한다.
- **JUD-FR-070 (Simulation)**: 과거 실행 ID(`execution_id`) 또는 특정 페이로드를 사용하여, 특정 정책/Rule 버전으로 판단을 재실행(Replay)한다.

### Workflow Engine (WF)
- **WF-FR-010 (DSL Parsing)**: Workflow DSL JSON을 파싱하고, 노드 타입, 필수 파라미터, 연결 구조(Edge)의 유효성을 검증한다.
- **WF-FR-020 (Node - Data)**: DATA 노드를 실행하여 Fact/Dim 테이블 또는 Pre-agg 뷰에서 데이터를 조회한다.
- **WF-FR-030 (Node - Judgment)**: JUDGMENT 노드를 실행하여 Judgment Engine API를 호출하고 결과를 컨텍스트에 저장한다.
- **WF-FR-040 (Node - Action)**: ACTION 노드를 실행하여 설정된 채널(Slack, Email, Webhook)로 메시지나 페이로드를 전송한다.
- **WF-FR-050 (Flow Control)**: SWITCH(조건 분기), PARALLEL(병렬 실행), WAIT(일시 정지/타임아웃) 로직을 처리한다.
- **WF-FR-060 (State Persistence)**: 인스턴스의 상태(PENDING, RUNNING, WAITING)와 실행 컨텍스트를 DB에 영구 저장하여 장애 복구 및 재개를 지원한다.
- **WF-FR-070 (Circuit Breaker)**: 노드/서비스별 실패율을 추적하여 임계 초과 시 회로를 차단하고 대체 경로(Fallback)를 실행한다.

### BI Engine (BI)
- **BI-FR-010 (NL Understanding)**: 자연어 질의를 분석하여 `analysis_plan`(지표, 차원, 필터, 기간) JSON으로 변환한다.
- **BI-FR-020 (Plan Execution)**: `analysis_plan`을 실행 가능한 SQL로 변환하여 데이터베이스(Fact/Pre-agg)를 조회한다.
- **BI-FR-030 (Catalog Mgmt)**: `bi_datasets`, `bi_metrics`, `bi_components`에 대한 등록/수정/삭제 API를 제공한다.
- **BI-FR-040 (Chart Rendering)**: 조회된 데이터를 바탕으로 프론트엔드 렌더링을 위한 차트 설정(Chart Config)을 생성한다.
- **BI-FR-050 (Caching)**: 분석 계획 해시를 기반으로 쿼리 결과를 캐싱하고, 데이터 갱신 시 무효화한다.

### Integration / MCP (INT)
- **INT-FR-010 (MCP Registry)**: MCP 서버 및 도구(Tool)의 메타데이터(이름, 스키마, 엔드포인트)를 등록하고 관리한다.
- **INT-FR-020 (Tool Execution)**: MCP 도구 호출 요청을 중계(Proxy)하고, 인증 헤더 주입 및 타임아웃을 처리한다.
- **INT-FR-030 (Connector Mgmt)**: DB/API 커넥터(ERP, MES 등)의 연결 정보를 관리하고 헬스 체크를 수행한다.
- **INT-FR-040 (Drift Detection)**: 외부 데이터 소스의 스키마 변경을 주기적으로 감지하고, 변경 발생 시 알림을 발송한다.

### Learning / Rule Ops (LRN)
- **LRN-FR-010 (Feedback)**: 판단 및 채팅 결과에 대한 사용자 피드백(좋아요/싫어요, 코멘트)을 수집하고 저장한다.
- **LRN-FR-020 (Sample Curation)**: 피드백이 긍정적인 로그를 `learning_samples`로 분류하여 학습 데이터로 구축한다.
- **LRN-FR-030 (Rule Extraction)**: 로그 및 샘플을 분석하여 Rhai Rule 후보를 자동 생성하고, 예상 정밀도/커버리지를 산출한다.
- **LRN-FR-040 (Prompt Tuning)**: 의도 분류 실패 또는 저신뢰도 로그를 식별하여 프롬프트의 Few-shot 예시로 추가한다.
- **LRN-FR-050 (Deployment)**: Rule/Prompt의 버전을 관리하고, 카나리 배포(Canary Deployment) 및 롤백 기능을 제공한다.

### Chat / Intent (CHAT)
- **CHAT-FR-010 (Intent Recog)**: 사용자 발화를 분석하여 정의된 의도(Intent)로 분류하고 신뢰도를 산출한다.
- **CHAT-FR-020 (Slot Filling)**: 발화 내에서 필요한 파라미터(Slot - 예: 라인명, 날짜, 제품명)를 추출한다.
- **CHAT-FR-030 (Ambiguity)**: 의도 신뢰도가 낮거나 필수 슬롯이 누락된 경우, 사용자에게 되묻는 질문을 생성한다.
- **CHAT-FR-040 (Model Routing)**: 작업의 난이도와 비용 정책에 따라 고성능 모델(GPT-4) 또는 경량 모델(Haiku)로 라우팅한다.

### Security / Observability (SEC/OBS)
- **SEC-FR-010 (AuthN/AuthZ)**: 모든 API 요청에 대해 OAuth2/JWT 인증을 수행하고, RBAC 기반으로 리소스 접근을 제어한다.
- **SEC-FR-020 (PII Masking)**: LLM 입력 및 로그 저장 시 개인정보(PII) 패턴을 탐지하여 마스킹 처리한다.
- **SEC-FR-030 (Audit Log)**: 주요 변경 사항(배포, 승인, 설정 변경)에 대해 행위자, 시각, 변경 내용을 감사 로그로 기록한다.
- **OBS-FR-010 (Logging)**: 모든 서비스 로그에 Trace ID, Tenant ID를 포함하여 구조화된 로그(JSON)를 남긴다.
- **OBS-FR-020 (Metrics)**: 서비스 지연, 에러율, 비즈니스 지표(판단 정확도 등)를 수집하여 모니터링 시스템에 제공한다.

## 4. 비기능 요구사항 (NFR)
- **성능**: Judgment 평균 지연 ≤ 1.5s(캐시 적중 ≤ 300ms); BI 계획 생성 ≤ 3s; MCP 호출 타임아웃 기본 5s; LLM JSON 파싱 실패율 < 0.5%
- **확장성**: 테넌트 분리(tenant_id), 모듈 단위 수평 확장(API, Judgment, WF, BI, MCP Hub)
- **가용성/복구**: 핵심 서비스 이중화; Postgres WAL 백업; Redis 복제 또는 AOF; DR RTO/RPO 목표 명시(예: RTO 4h, RPO 30m)
- **보안**: JWT/OAuth 기반 인증+역할/권한; 전송/저장 암호화; LLM 외부 호출 시 PII 마스킹/로깅 제한; Webhook 서명/HMAC/idempotency
- **감사/추적성**: Rule/Prompt/모델/DSL 버전과 입력/출력/결과를 함께 저장; CCP/LOT/판단 로그 2년 이상 보관; 배포/롤백 이력 기록
- **국제화/현지화**: 다국어 응답 템플릿 지원(ko/en 우선), UTC 저장/로컬 타임존 렌더링
- **품질/알람**: Drift/충돌/스키마 변경 감지 시 알람 발행, 재학습/승인/ETL 중단 트리거와 연계

## 5. 기능별 교차 검증 체크리스트 (추적성)
- **Judgment**: B-4 API(실행/조회/리플레이)와 B-2 모듈 책임, B-3 `judgment_executions`/캐시 키, C-3 테스트(LLM 파싱/캐시/리플레이), D-2 SLO(지연/파싱 실패) 일치 여부 확인.
- **Workflow**: B-5 DSL 스키마/노드 타입 ↔ B-4 Workflow API CRUD/인스턴스 로그 ↔ B-3 `workflows/steps/instances` 제약 ↔ C-3 TC(승인/장기 실행/DEPLOY/ROLLBACK) ↔ D-2 회로차단/실패율 알람.
- **BI**: B-2 BI Planner/카탈로그 ↔ B-4 BI plan/execute/catalog API ↔ B-3 bi_datasets/bi_metrics/bi_components DDL ↔ C-3 TC(BI pre-agg) ↔ D-2 BI 지표(SLO 2~3s).
- **MCP/Integration**: B-4 MCP list/health/test/call ↔ B-2 MCP ToolHub 회로차단 정책 ↔ B-3 connector/mcp_* 테이블 ↔ C-3 TC(MCP 타임아웃/대체) ↔ D-2 MCP 알람 임계.
- **Learning**: B-2 Learning 파이프라인 ↔ B-3 feedbacks/learning_samples/auto_rule_candidates/rule_deployments ↔ B-4 candidates/approve API ↔ C-3 TC(canary/롤백, 충돌), D-2 품질 대시보드(오경보/미탐지).
- **Chat/Intent**: B-2 Intent Router 책임 ↔ B-4 Chat/Intent API ↔ C-3 TC(Intent/slot/모델 스위치) ↔ D-2 LLM 비용/실패율 알람.
- **Security/DR/Observability**: C-5 RBAC/HMAC/PII ↔ B-4 인증/웹훅 보안 ↔ B-3 audit_logs ↔ C-3 보안 TC ↔ D-2 SLO/알람 액션 ↔ D-3 DR 절차/검증 SQL.
## 5. 규제/준수사항 (필요 시)
- 식품/의약/안전 관련 규제 준수: HACCP/ISO22000/FSSC 로그 보존, 변경이력 관리
- 개인정보 처리 시: 최소 수집, 목적 외 이용 금지, 민감정보 저장 시 암호화 및 접근통제
- 외부 클라우드 사용 시: 고객사 망 분리/온프렘 옵션을 계약 사항에 명시
