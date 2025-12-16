# B-2. Module / Service Design Spec

## 공통 규칙
- 각 서비스는 **Responsibility/Interface/Sequence/Error/Config** 5개 축으로 기술.
- 모든 서비스는 `tenant_id`를 1급 파라미터로 수신, 감사/로그는 공통 스키마를 따른다.

## 1) Judgment Service
- **Responsibility**: 입력(workflow_id+input_data)을 Rule+LLM Hybrid로 판단하고 result/confidence/method_used/explanation/recommended_actions/raw_trace/evidence/feature_importance를 반환.
- **주요 기능**
  - Rule Eval(Rhai) + LLM Adapter(JSON 강제, few-shot, RAG)
  - Hybrid Aggregator(Policy/가중/신뢰도 산식, RULE_ONLY/LLM_FALLBACK/HYBRID)
  - 캐시(Read-through TTL), Trace/Logging, Policy 관리(버전 pinning)
- **내부 컴포넌트**
  - `RuleEvaluator`(AST sandbox, 변수 바인딩, 테스트 DSL)
  - `LlmAdapter`(prompt 템플릿, 모델 라우팅, 파싱/validation)
  - `HybridOrchestrator`(policy_id, method 결정, confidence 계산)
  - `CacheClient`(Redis), `TraceLogger`(DB/ES)
- **시퀀스(UC-01)**: request → cache miss → RuleEvaluator → (optional) LlmAdapter → HybridOrchestrator → persist logs → cache set → response
- **에러/예외**: 입력 검증 400; Rule 실행 실패 시 LLM fallback; LLM 실패 시 Rule-only or default result; 외부 실패 시 degrade + 알람
- **Config**: policy_id, model 선택, temperature, cache_ttl, rule_timeout, llm_timeout, fallback_mode, explainability 옵션(evidence/feature_importance)

## 2) Workflow Service (Planner/DSL/Runtime)
- **Responsibility**: 자연어를 DSL로 변환하고, DSL을 실행/감시/재시도/승인 관리.
- **주요 기능**
  - DSL 스키마 검증/버전 관리
  - Planner(LLM) → Step list → DSL JSON 생성
  - Executor: 노드 러너(DATA/BI/JUDGMENT/MCP/ACTION/APPROVAL/WAIT/SWITCH/PARALLEL/COMPENSATION/**DEPLOY/ROLLBACK/SIMULATE**)
  - 재시도/backoff, 장기 실행 저장, 승인/보상 트랜잭션, 회로차단
- **내부 컴포넌트**
  - `DslValidator`(JSON Schema)
  - `PlanBuilder`(LLM 프롬프트 + 노드 카탈로그)
  - `NodeRunner` 인터페이스(입력→출력), 실행엔진(락/큐), `InstanceStore`(Postgres)
- **시퀀스(예: 판단→알림 WF)**: DSL load → task enqueue → NodeRunner(DATA) → NodeRunner(JUDGMENT) → NodeRunner(ACTION) → 상태 업데이트 → 로그 저장
- **에러/예외**: 노드 단위 재시도 n회/backoff; 실패 시 COMPENSATION 실행; 장기 승인 대기 시 타임아웃/취소; 회로차단 on/off 및 대체 경로
- **Config**: max_retry, backoff, timeout, approval_expire, parallel_limit, default_queue, compensation map, circuit_breaker, deploy/rollback 옵션(canary_pct, rollback_to)

## 3) BI Service
- **Responsibility**: 자연어 질의를 dataset/metric/component 계획으로 변환하고 차트/요약을 생성.
- **BI Service**: BI Planner(analysis_plan 생성), Metric/Dataset/Component 카탈로그, 차트/요약 생성.
  - **Component Catalog Layer**:
    - **Dataset**: 데이터 원천 정의 (예: `view_production_daily`, `table_quality_logs`).
    - **Metric**: 집계 로직 정의 (예: `avg_defect_rate`, `sum_output_qty`, `wow_growth`).
    - **Visualization**: 차트 유형 및 설정 (예: `line_chart_trend`, `bar_chart_comparison`, `kpi_card`).
  - **Chart Intelligence**: "L01 라인 생산량" 요청 시 `line` 필드 기준 Pivot 자동 적용, 시계열 데이터 감지 시 Line Chart 자동 추천. - Pre-agg 뷰/캐시 제공, 차트 데이터 포맷 변환, 차트 규칙 엔진/Insight 템플릿 적용
- **내부 컴포넌트**
  - `BiPlanner`(LLM prompt, 차트 규칙 엔진, insight_type/ preferred_components 처리)
  - `CatalogStore`(dataset/metric/component/insight template)
  - `QueryExecutor`(SQL/agg 함수 선택, Pre-agg/Cache)
  - `ChartAssembler`(kpi_card/line/bar/pie/table payload 구성)
- **시퀀스(예: “지난주 불량 요약”)**: NL → BiPlanner → analysis_plan → QueryExecutor(Pre-agg 우선) → ChartAssembler → 응답/캐시
- **에러/예외**: 스키마 불일치 시 안전 필터링/예외 필드 제거; LLM 실패 시 템플릿 기반 기본 플랜 사용; 쿼리 타임아웃 시 축약 응답
- **Config**: default_time_range, preagg_view, cache_ttl, chart_ruleset, timeout

### 차트 규칙/템플릿 예시(발췌)
- 시계열(metric + time): 기본 `line_chart`, 이상치 포함 시 `line+anomaly_band`.
- 범주/비율(metric + category): `bar_chart`, top-N일 때 `bar_topN`, 분포는 `histogram`.
- 누적/비중: `stacked_bar`, `pie`(소규모 카테고리만), `treemap`(대규모).
- KPI 카드: 단일 값 + 전기간 대비 증감률 표시.
- Insight 템플릿: `defect_overview`, `shift_compare`, `oee_daily`, `inventory_cov` 등과 필요한 metric 리스트 매핑.

## 4) MCP ToolHub / Integration
- **Responsibility**: MCP 서버/툴 호출 단일화, 인증/타임아웃/재시도 관리.
- **주요 기능**: 서버/툴 메타 조회, 호출 라우팅, 에러 번역, 호출 로그 기록.
- **내부 컴포넌트**: `McpRegistry`, `McpInvoker`(HTTP/WS/MQTT), `CredentialStore`, `CallLogger`.
- **에러/예외**: 서버 미등록/툴 미등록 시 404; 호출 타임아웃/재시도; 회로차단.
- **Config**: default_timeout, max_retry, circuit_breaker, audit_log flag.

## 5) Learning Service
- **Responsibility**: 판단/피드백 데이터를 샘플화하고 Rule/Prompt 개선안을 생성·승인·배포.
- **주요 기능**: feedback 수집, training_samples 생성, auto_rule_candidates(빈도/DT/LLM), 검증/승인 라인, Prompt 개선안 관리.
- **내부 컴포넌트**: `FeedbackIngestor`, `SampleBuilder`, `RuleMiner`(freq/DT/LLM), `Validator`, `ApprovalFlow`, `Deployer`.
- **에러/예외**: 품질 기준 미달 시 후보 폐기; 충돌 Rule 감지 시 보류; 배포 실패 시 롤백.
- **Config**: min_support, min_precision, validation_window, approver_roles, deploy_strategy(canary/manual).

## 6) Observability/DevOps (요약)
- **Responsibility**: 로그/메트릭/트레이스/알람 관리, CI/CD 배포/롤백.
- **주요 기능**: 구조화 로그 수집, 서비스 메트릭, 알람 라우팅, 배포 파이프라인.
- **내부 컴포넌트**: `LogCollector(Loki/ELK)`, `Metrics(Prometheus)`, `Alertmanager`, `CI/CD pipeline`.
- **Config**: log_retention, alert_threshold, rollout_strategy, backup/restore schedule.

## 7) 캐시/TTL 매트릭스 (공통 가이드)
- Judgment 캐시: 키=`judgment:{workflow_id}:{hash(input)}`, TTL 5~15분(정책별), hit시 300ms 이하 목표.
- BI 캐시/Pre-agg: 키=`bi:{plan_hash}`, TTL 10~30분; MV 리프레시 1h/피크 전 수동 리프레시.
- MCP 호출 캐시(옵션): 읽기 전용 툴에 한정, TTL 1~5분, 회로차단과 병행.
- RAG 컨텍스트 캐시: 자주 쓰는 문서 chunk embedding 조회 캐싱 TTL 10분.
- Invalidation: 입력 해시 변경, ruleset/policy 변경 시 judgment 캐시 purge; dataset 업데이트 시 BI 캐시/MV 리프레시.

## 8) 에러/회로차단 정책 표 (요약)
| 대상 | 타임아웃 | 재시도 | 회로차단 임계 | 대체 경로 |
| --- | --- | --- | --- | --- |
| LLM 호출 | 5s 기본 | 1~2회, backoff | 파싱 실패/오류 5% 초과 | 대체 모델/Rule-only |
| MCP 호출 | 5s 기본 | 2회, backoff | 실패율 5%/1분 | 대체 노드/수동 안내 |
| DB/쿼리 | 3s 기본 | 1회 | 슬로우 쿼리 누적 | Pre-agg 사용/쿼리 제한 |
| Action(Webhook) | 3s | 2회 | 실패율 10% | 보류/재시도 큐 |

## 9) 추적성 체크리스트 (모듈 ↔ 요구/데이터/테스트)
- **Judgment**: A-2 JUD-FR ↔ B-4 Judgment API ↔ B-3 `judgment_executions`/캐시 키 ↔ C-3 TC(LLM 파싱/캐시/리플레이) ↔ D-2 SLO(지연/파싱 실패) ↔ D-3 배포/롤백.
- **Workflow**: A-2 WF-FR ↔ B-5 DSL/노드 ↔ B-3 workflows/steps/instances ↔ B-4 WF API ↔ C-3 TC(승인/장기 실행/DEPLOY) ↔ D-2 회로차단/실패율.
- **BI**: A-2 BI-FR ↔ B-4 BI plan/execute/catalog ↔ B-3 bi_* DDL ↔ C-3 TC(BI pre-agg) ↔ D-2 BI SLO.
- **MCP/Integration**: A-2 INT/DATA-FR ↔ B-4 MCP/Connector API ↔ B-3 connectors/mcp_* ↔ C-3 TC(MCP 타임아웃) ↔ D-2 MCP 알람.
- **Learning**: A-2 LRN-FR ↔ B-4 candidates/approve API ↔ B-3 feedbacks/learning_samples/auto_rule_candidates/rule_deployments ↔ C-3 TC(canary/충돌) ↔ D-2 품질 대시보드.
- **Chat/Intent**: A-2 CHAT-FR ↔ B-4 Chat/Intent API ↔ C-3 TC(Intent/slot/모델 스위치) ↔ D-2 LLM 비용/실패율.
- **Observability/DevOps**: A-2 OBS/SEC/DR-FR ↔ B-4 logs/traces ↔ B-3 audit_logs ↔ C-3 보안/관측 TC ↔ D-2 SLO/알람 ↔ D-3 DR/배포 runbook.

## 10) BI 차트 규칙/Pre-agg 뷰 (상세 예시)
- 차트 규칙:
  - 시계열(metric+time) → line_chart, 이상치 표시 필요 시 anomaly_band 오버레이
  - 범주/비율(metric+category) → bar_chart, top-N이면 bar_topN, 분포는 histogram
  - 누적/비중 → stacked_bar, pie(카테고리 적을 때), treemap(카테고리 많을 때)
  - KPI 카드 → 단일 값 + 전기간 대비 증감률, 목표 대비 편차 표시
- Pre-agg 뷰/리프레시:
  - mv_defect_trend(line,date,defect_rate,top_defect_type) → 1h 주기, 피크 전 수동 리프레시
  - mv_oee_daily(line,date,oee,availability,performance,quality) → 일단위 새벽 리프레시
  - mv_inventory_cov(product,date,cov_days) → 일단위 리프레시
  - 리프레시 실패 시 알람, 리프레시 후 BI 캐시 무효화

## 11) Learning 충돌/Drift/샘플 큐레이션 기준
- Rule 충돌: 조건 overlap 80% 이상이면서 상반된 action → 충돌 플래그, 승인 전 해결 필요
- Concept drift: 입력 분포 KL-divergence > 0.1 (7일 롤링) 또는 타깃 레이블 분포 변동 > 5%p → 알람/재학습 트리거
- Few-shot 필터: 유사도 ≥ 0.7, 성공 사례 우선 포함, 실패 사례는 negative prompt로 별도 관리

## 12) MCP/커넥터 스키마 변경 감지
- 커넥터 등록 시 스키마 해시 저장, ETL 전후 스키마 비교 → 변동 시 알람/중단 옵션
- MCP tool schema 변경 시 승인 워크플로우 필요(변경 diff + 영향 대상 노드 표시)
- 센서/로봇 래퍼: MQTT/OPC-UA → MCP 서버로 래핑, payload 스키마 정의, 레이트리밋/회로차단 적용
