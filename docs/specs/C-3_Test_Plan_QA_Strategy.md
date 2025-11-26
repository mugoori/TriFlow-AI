# C-3. Test Plan & QA Strategy

## 1. 테스트 종류/범위
- **단위(Unit)**: RuleEvaluator, LlmAdapter 파서, Hybrid Aggregator, NodeRunner
- **통합(Integration)**: Judgment + Redis + Postgres; Workflow 실행(재시도/승인/회로차단); BI Planner→QueryExecutor; MCP call/health
- **E2E**: Chat→Intent→Plan→Judgment→Action, 대표 WF 시나리오(불량 알림/CCP 이탈 처리/배포→롤백)
- **성능/부하**: Judgment TPS/지연, Workflow 병렬 실행, BI 질의/캐시/Pre-agg 리프레시, MCP 지연/타임아웃 주입, LLM 모델 스위칭 시 지연
- **보안**: 인증/인가 우회, Webhook 서명/HMAC, LLM 프롬프트 주입/PII 마스킹, 입력 검증
- **회귀/리플레이**: **Zwave Replay**로 Rule/Prompt/모델 변경 시 과거 데이터 재실행하여 비교

## 2. 커버리지 목표
- 단위 테스트: 핵심 로직 70% 이상(Line/Branch)
- 통합/E2E: 핵심 경로 100% 스모크, 승인/보상/회로차단 시나리오 포함
- LLM 응답 검증: JSON 파싱 실패율 < 0.5% (테스트셋 기준)

## 3. 테스트 케이스 설계 기준
- ID 체계: TC-JUD-XXX, TC-WF-XXX, TC-BI-XXX, TC-SEC-XXX
- 입력 경계값: 값 누락/유형 오류/허용 범위 초과
- 실패 주입: LLM 타임아웃, MCP 호출 실패, Redis/DB 지연, 회로차단 조건 충족
- 결정적 시나리오: Rule/LLM 충돌 시 정책별 기대 출력, canary배포→문제 발생→롤백 경로

## 4. 테스트 환경 구성
- **로컬**: Docker Compose(Postgres/Redis/Mock MCP/Mock LLM)
- **스테이징**: 실제 LLM/커넥터 샌드박스, 프리프로덕션 데이터 소량
- **데이터**: 샘플 fact/raw 데이터셋, RAG 샘플, Rule/Prompt 샘플 버전 고정; Replay용 고정 시나리오 세트
- **옵저버빌리티**: 테스트 시 Trace-id 기록, 로그/메트릭 대시보드 별도 뷰

## 5. 결함 관리 프로세스
- 도구: Jira/YouTrack 등 이슈 트래커, 심각도/우선순위 태깅
- SLA: 크리티컬 24h 이내 임시조치, 72h 이내 영구 해결 계획
- 결함 재현 스크립트/로그 첨부 필수, 원인분석(RCA) 기록, 회귀 테스트 케이스 추가

## 6. 승인/출시 전 체크리스트 (MVP)
- 모든 E2E 시나리오 PASS (알림/승인/배포/롤백 포함)
- 판단 로그/감사 로그 누락 없음
- 성능 스모크: Judgment p95 ≤ 1.5s, WF 성공률 ≥ 99%, LLM 파싱 실패율 목표 달성, BI/Pre-agg 리프레시 시간 확인
- 보안: 인증/인가/웹훅 서명 테스트 통과, LLM PII 마스킹 검증
- Replay 게이트: 핵심 Rule/Prompt/모델 변경은 Zwave Replay 비교 결과 승인 후 배포

## 7. 대표 테스트 케이스 목록 (발췌)
| ID | 유형 | 설명 | 기대 결과 |
| --- | --- | --- | --- |
| TC-JUD-001 | 단위 | RuleEvaluator 숫자 범위/조건 | 예상 라벨 반환 |
| TC-JUD-010 | 통합 | Judgment 캐시 히트/미스 지연 비교 | 캐시 히트 < 300ms |
| TC-JUD-020 | 통합 | LLM 파싱 실패 → 재시도→fallback | 오류 없이 fallback 결과 |
| TC-WF-030 | E2E | SWITCH 분기/병렬/COMPENSATION 실행 | 분기 맞게 실행, 실패 시 보상 |
| TC-WF-040 | E2E | APPROVAL 대기/만료/재개 | 만료 시 취소, 재개 시 상태 유지 |
| TC-WF-050 | E2E | DEPLOY(canary 10%)→롤백 | canary 후 롤백 성공 |
| TC-MCP-060 | 통합 | MCP 타임아웃→회로차단→대체 노드 | 차단 후 스킵, 대체 경로 실행 |
| TC-BI-070 | 통합 | BI Planner → Pre-agg 조회 | 2s 이내 응답 |
| TC-SEC-080 | 보안 | Webhook HMAC 검증 실패 | 401/로그 기록 |
| TC-OBS-090 | 관측 | Trace-id 전달/로그 수집 | 로그/트레이스에서 동일 id |
| TC-JUD-005 | 단위 | Judgment 입력 스키마/필수값 검증 | 필수 누락 시 400 에러 |
| TC-BI-075 | 통합 | BI 카탈로그 메트릭 등록/수정 | 등록 후 조회/계산 가능 |
| TC-CHAT-140 | E2E | 의도 모호/슬롯 누락 시 되묻기 | 질문 생성 및 컨텍스트 유지 |
| TC-LRN-150 | 통합 | 로그 분석 → Rule 후보 추출 | 후보 테이블에 적재 |

## 8. 테스트 환경/시크릿 관리
- 로컬: Docker Compose(Postgres/Redis/Mock LLM/MCP), 기본 시크릿 `.env.local`(샘플 키), 테스트 데이터 로더 스크립트 제공.
- 스테이징: 실 LLM/커넥터 샌드박스, 제한된 실데이터; 시크릿은 Vault/K8s Secret, RBAC 제한.
- 데이터 리셋: 익명화된 샘플로 리셋 가능하게 스크립트 제공; PII 제거/마스킹 확인.

## 9. 추적성 체크리스트 (테스트 ↔ 요구/모듈/데이터/모니터링)
- TC-JUD-*: A-2 JUD-FR-010~070 ↔ B-2 Judgment 모듈 ↔ B-4 Judgment API ↔ B-3 judgment_executions ↔ D-2 지연/파싱 알람.
- TC-WF-*: A-2 WF-FR-010~070 ↔ B-5 DSL ↔ B-4 WF API ↔ B-3 workflows/instances ↔ D-2 회로차단/실패율.
- TC-BI-*: A-2 BI-FR-010~050 ↔ B-2 BI 서비스 ↔ B-4 BI API ↔ B-3 bi_* ↔ D-2 BI SLO.
- TC-MCP-*: A-2 INT-FR-010~040 ↔ B-2 MCP ↔ B-4 MCP API ↔ B-3 connectors/mcp_* ↔ D-2 MCP 알람.
- TC-LRN-*: A-2 LRN-FR-010~050 ↔ B-2 Learning ↔ B-3 learning_samples/auto_rule_candidates ↔ D-2 품질 대시보드.
- TC-CHAT-*: A-2 CHAT-FR-010~040 ↔ B-2 Intent Router ↔ B-4 Chat API ↔ B-3 chat_* ↔ D-2 LLM 비용.
- TC-SEC/OBS-* : A-2 SEC-FR-010~030 / OBS-FR-010~020 ↔ C-5 보안 ↔ B-3 audit_logs ↔ D-2 보안/감사 로그.

## 10. 릴리즈 게이트 기준 (SLO 연계)
- Judgment: p95 ≤ 1.5s, 파싱 실패율 < 0.5%, Replay diff(중대한 상태 변화) ≤ 2% → 충족 시 배포 승인.
- Workflow: 실패율 < 1%, 회로차단 발생률 < 1%, DLQ 0 → 충족 시 배포 승인.
- BI: plan/execute p95 ≤ 2s, 캐시 적중률 ≥ 40% (집계 기준) → 충족 시 배포 승인.
- MCP: 타임아웃률 < 3%, 회로차단 off 상태 유지 → 충족 시 배포 승인.

## 11. 추가 테스트 케이스 (Drift/스키마 변경)
| ID | 유형 | 설명 | 기대 결과 |
| --- | --- | --- | --- |
| TC-LRN-100 | 품질 | Drift 감지(KL>0.1) 알람 트리거 | 알람/재학습 태스크 생성 |
| TC-LRN-110 | 품질 | Rule 충돌 감지(overlap 80%+역행 action) | 충돌 플래그, 배포 차단 |
| TC-MCP-120 | 통합 | 커넥터 스키마 변경 감지/알람 | 알람 발생, ETL 중단/승인 대기 |

## 12. 캐시/무효화 테스트
| ID | 유형 | 설명 | 기대 결과 |
| --- | --- | --- | --- |
| TC-CACHE-130 | 통합 | ruleset 변경 후 judgment 캐시 purge | 캐시 미스 발생, 새 결과 반영 |
| TC-CACHE-131 | 통합 | Pre-agg 리프레시 후 BI 캐시 무효화 | 최신 뷰 사용, stale 데이터 없음 |
| TC-CACHE-132 | 통합 | MCP 호출 TTL 만료/회로차단 | TTL 이후 재호출, 차단 시 대체 경로 |
