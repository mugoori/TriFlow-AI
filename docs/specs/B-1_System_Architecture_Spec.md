# B-1. System Architecture Specification

## 1. 전체 시스템 개요
- **배포 모델**: 클라우드/온프렘 겸용. Kubernetes(or Docker Compose) 기반 멀티 서비스 마이크로서비스 아키텍처.
- **주요 영역**: Chat/UI → Intent Router → Planner/Executor → Core (Judgment/Workflow/BI/**Zwave Simulation**) → Data Hub(ETL/Vector) → Integration(MCP/Native) → Observability/DevOps.

## 2. 서비스/모듈 목록 (Bounded Context)
- **Chat Interface Service**: 메시지 수집, 세션 관리, 의도 분류 요청, 응답 구성.
- **Intent Router**: 룰+저가형 LLM 기반 Intent/Slot 추출.
- **Planner/Executor (Workflow Service)**: 자연어 계획 생성, DSL 저장/검증, 실행/재시도/승인/장기 실행 관리.
- **Judgment Service**: Rule 엔진+LLM Hybrid 판단, 정책/캐시/로그 기록.
- **BI Service**: BI Planner(analysis_plan 생성), Metric/Dataset/Component 카탈로그, 차트/요약 생성.
- **Learning Service**: Feedback 수집, training_samples, auto_rule_candidates, 승인 후 Rule 반영.
- **MCP ToolHub**: MCP 서버/툴 호출 추상화, 커넥터 메타 관리.
- **Data Hub**: Connector/ETL(raw→dim→fact), VectorDB(pgvector), Pre-agg/Cache.
- **Observability**: Logging/Tracing/Monitoring/Alerting.
- **DevOps/Infra**: CI/CD, Secret/Config 관리, 배포/롤백.

## 3. 컴포넌트 다이어그램(텍스트 요약)
- **API Gateway** ⇄ Chat Service / WF Service / Judgment / BI / Learning / MCP Hub
- Judgment ↔ Redis(Cache) / Postgres(judgment_executions, rulesets, prompts) / VectorDB(optional RAG)
- Workflow Executor ↔ Redis(큐/락) ↔ Postgres(workflow_instances/logs)
- BI Service ↔ Postgres(fact/dim, analysis_plan) ↔ Cache/Pre-agg View
- MCP Hub ↔ MCP Servers(Excel/GDrive/Jira/Robot stub) & Native DB Connectors(ERP/MES)
- Observability ↔ Loki/ELK(로그), Prometheus/Grafana(메트릭/알람)

## 4. 데이터 흐름(입·출력)
1) 사용자 입력(채팅/UI/Webhook) → Intent Router (intent/slots)
2) Planner: intent에 따라 Plan(steps) 생성 → Workflow DSL 저장/승인
3) Executor: Plan/DSL 실행 → DATA/BI/MCP/JUDGMENT/ACTION 노드 순회
4) Judgment: Rule eval → LLM 보완 → Hybrid result → raw_trace/logging
5) BI: dataset/metric 조회 → 캐시/Pre-agg 활용 → 차트/요약 전달
6) Action: Slack/Webhook/Email/티켓/로봇 API(향후) 호출
7) Feedback: 사용자 👍👎 → Learning → Rule/Prompt 개선안 → 승인 → 배포

## 5. 기술 스택 (초안)
- **Backend**: TypeScript/Node 또는 Python(FastAPI), gRPC/REST
- **Rule Engine**: Rhai(AST, sandbox)
- **LLM**: OpenAI GPT-4.x mini/4.1, Claude Haiku 등(프롬프트+Few-shot+RAG), pgvector
- **DB**: Postgres 14+ (judgment/workflow/bi/catalog/log), pgvector, Redis 6+ (cache/lock)
- **Queue/Async**: Redis Streams/Sidekiq류 또는 RabbitMQ(선택)
- **Infra**: Docker/K8s, Nginx/Kong Gateway, Prometheus+Grafana, Loki/ELK, S3/object storage(로그/백업)

## 6. 확장·장애·보안 고려사항 개요
- **확장**: Stateless 서비스(HPA), Judgment/Executor/BI 별도 스케일; 캐시 로드 감소 위한 Pre-agg/TTL 튜닝
- **장애대응**: Circuit breaker(MCP/외부), 재시도/backoff, DLQ; 캐시 장애 시 DB degrade
- **보안**: 테넌트 분리(tenant_id), JWT/OAuth2, RBAC, TLS, 비공개 네트워크; LLM 호출 시 PII 마스킹
- **컴플라이언스**: 판단/Rule/모델/DSL 버전 관리 및 감사 로그; CCP/LOT 추적 보존

## 7. 추적성 체크리스트 (설계 ↔ 요구사항)
- Judgment: API(B-4) / JUD-FR-001~006 / 데이터(judgment_executions, cache) / 테스트(C-3 LLM 파싱/캐시/리플레이) / SLO(D-2 지연/파싱) / 운영(D-3 배포/롤백)
- Workflow: DSL/노드(B-5) / WF-FR-001~004 / 데이터(workflows/steps/instances) / 테스트(C-3 승인/장기 실행/DEPLOY) / 모니터링(D-2 회로차단/실패율)
- BI: BI Planner/카탈로그(B-2, B-4) / BI-FR-001~003 / 데이터(bi_* DDL) / 테스트(BI pre-agg) / SLO(2~3s)
- Integration/MCP/Data: MCP/커넥터(B-4) / INT/DATA-FR / 데이터(connectors/mcp_*) / 테스트(MCP 타임아웃) / 알람(D-2)
- Learning: 파이프라인(B-2) / LRN-FR / 데이터(feedbacks/learning_samples/auto_rule_candidates/rule_deployments) / 테스트(canary/충돌) / 품질 대시보드(D-2)
- Chat/Intent: Router(B-2) / CHAT-FR / 테스트(Intent/slot/모델 스위치) / 비용/실패율 알람(D-2)
- Security/DR/Observability: C-5/HMAC/RBAC/audit_logs / SEC/DR-FR / 테스트(보안 TC) / SLO/DR(D-2/D-3)

## 10. 향후 보완 로드맵(설계 관점)
- **LLM 모델 정책**: 작업→모델/토큰/자동 다운그레이드 기준을 설정하고, 알람(D-2)과 연계해 자동 전환.
- **Drift/충돌 오토핸들러**: Drift 감지 시 재학습 태스크 생성, Rule 충돌 시 승인 대기로 전환하는 오토플로우 구현.
- **MCP/커넥터 스키마 변경**: 변경 diff를 UI/알람에 노출, 영향받는 WF/BI 목록 자동 표시.
- **AAS 통합 강화**: aas_source_mappings 기반 조회 API 및 Judgment/BI 컨텍스트 삽입 경로 명시, 샘플 응답 스펙 추가.
- **BI 차트 인텔리전스**: 차트 규칙 라이브러리 확장, Pre-agg 매핑 자동 추천 로직 정의.
- **캐시/무효화 전략 코드화**: 주요 키/TTL/무효화 조건을 설정 서비스/코드로 명문화.
