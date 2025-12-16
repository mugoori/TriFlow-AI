# C-3. Test Plan & QA Strategy

## 문서 정보
- **문서 ID**: C-3
- **버전**: 3.0 (V7 Intent + Orchestrator)
- **최종 수정일**: 2025-12-16
- **상태**: Active Development
- **관련 문서**:
  - B-5 Workflow State Machine Spec
  - B-6 AI Agent Architecture
  - C-1 Development Plan

---

## 1. 테스트 종류/범위
- **단위(Unit)**: RuleEvaluator, LlmAdapter 파서, Hybrid Aggregator, NodeRunner (15 노드 타입)
- **V7 Intent 테스트**: Intent 분류기 (14개 V7 Intent), Slot 추출기, Legacy Intent 매핑 (15개)
- **Orchestrator 테스트**: Plan Generator, Route→Node 매핑, DSL 생성기
- **통합(Integration)**: V7 Intent Router→Orchestrator→Workflow; Judgment + Redis + Postgres; BI Planner→QueryExecutor; MCP call/health
- **E2E**: 발화→V7 Intent→Orchestrator Plan→Workflow→응답 전체 파이프라인
- **성능/부하**: Intent 분류 지연, Orchestrator Plan 생성 시간, Workflow 병렬 실행, BI 질의/캐시/Pre-agg 리프레시
- **보안**: 인증/인가 우회, Webhook 서명/HMAC, LLM 프롬프트 주입/PII 마스킹, 입력 검증
- **회귀/리플레이**: **Zwave Replay**로 Rule/Prompt/모델 변경 시 과거 데이터 재실행하여 비교

## 2. 커버리지 목표
- 단위 테스트: 핵심 로직 70% 이상(Line/Branch)
- **V7 Intent 분류**: 정확도 > 90%, 14개 Intent 전체 커버리지
- **Orchestrator Plan**: 성공률 > 85%, Route→Node 매핑 정확도 > 95%
- **15개 노드 타입**: P0 100%, P1 90%, P2 70% 테스트 커버리지
- 통합/E2E: 핵심 경로 100% 스모크, 승인/보상/회로차단 시나리오 포함
- LLM 응답 검증: JSON 파싱 실패율 < 0.5% (테스트셋 기준)

## 3. 테스트 케이스 설계 기준
- ID 체계: TC-JUD-XXX, TC-WF-XXX, TC-BI-XXX, TC-SEC-XXX, **TC-INT-XXX (V7 Intent)**, **TC-ORC-XXX (Orchestrator)**
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

## 7.1 V7 Intent 테스트 케이스 (신규)

| ID | 유형 | 설명 | 기대 결과 |
| --- | --- | --- | --- |
| TC-INT-001 | 단위 | CHECK Intent 분류 ("오늘 생산량 얼마야?") | v7_intent=CHECK, route_to=data_layer |
| TC-INT-002 | 단위 | TREND Intent 분류 ("이번 주 불량률 추이") | v7_intent=TREND, route_to=data_layer |
| TC-INT-003 | 단위 | COMPARE Intent 분류 ("1호기랑 2호기 비교") | v7_intent=COMPARE, route_to=judgment_engine |
| TC-INT-004 | 단위 | RANK Intent 분류 ("제일 문제인 설비") | v7_intent=RANK, route_to=judgment_engine |
| TC-INT-005 | 단위 | FIND_CAUSE Intent 분류 ("왜 불량률이 높아?") | v7_intent=FIND_CAUSE, route_to=judgment_engine |
| TC-INT-006 | 단위 | DETECT_ANOMALY Intent 분류 ("이상 있어?") | v7_intent=DETECT_ANOMALY, route_to=rule_engine |
| TC-INT-007 | 단위 | PREDICT Intent 분류 ("오늘 목표 달성 가능해?") | v7_intent=PREDICT, route_to=judgment_engine |
| TC-INT-008 | 단위 | WHAT_IF Intent 분류 ("1호기 멈추면 어떻게 돼?") | v7_intent=WHAT_IF, route_to=judgment_engine |
| TC-INT-009 | 단위 | REPORT Intent 분류 ("일일 리포트 만들어줘") | v7_intent=REPORT, route_to=bi_guide |
| TC-INT-010 | 단위 | NOTIFY Intent 분류 ("온도 60도 넘으면 알려줘") | v7_intent=NOTIFY, route_to=workflow_guide |
| TC-INT-011 | 단위 | CONTINUE Intent 분류 ("응", "더 자세히") | v7_intent=CONTINUE, route_to=context_dependent |
| TC-INT-012 | 단위 | CLARIFY Intent 분류 (모호한 발화) | v7_intent=CLARIFY, route_to=ask_back |
| TC-INT-013 | 단위 | SYSTEM Intent 분류 ("안녕", "도움말") | v7_intent=SYSTEM, route_to=direct_response |
| TC-INT-014 | 단위 | Legacy Intent 매핑 (production_status→CHECK) | legacy_intent=production_status, v7_intent=CHECK |
| TC-INT-015 | 통합 | Slot 추출 (metric, target, period) | slots 정확 추출 |

## 7.2 Orchestrator 테스트 케이스 (신규)

| ID | 유형 | 설명 | 기대 결과 |
| --- | --- | --- | --- |
| TC-ORC-001 | 단위 | CHECK Intent → Plan 생성 | 1단계 (DATA 노드) |
| TC-ORC-002 | 단위 | FIND_CAUSE Intent → Plan 생성 | 3단계 (DATA→JUDGMENT→CODE) |
| TC-ORC-003 | 단위 | DETECT_ANOMALY Intent → Plan 생성 | 2단계 (DATA→SWITCH) |
| TC-ORC-004 | 단위 | REPORT Intent → Plan 생성 | 2단계 (DATA→BI) |
| TC-ORC-005 | 단위 | NOTIFY Intent → Plan 생성 | 3단계 (TRIGGER→JUDGMENT→ACTION) |
| TC-ORC-006 | 통합 | Route→Node 매핑 (data_layer) | [DATA, CODE] 노드 생성 |
| TC-ORC-007 | 통합 | Route→Node 매핑 (judgment_engine) | [DATA, JUDGMENT, CODE] 노드 생성 |
| TC-ORC-008 | 통합 | DSL 생성 검증 | 유효한 JSON DSL 생성 |
| TC-ORC-009 | E2E | V7 Intent→Orchestrator→Workflow 파이프라인 | 전체 파이프라인 성공 |
| TC-ORC-010 | 성능 | Plan 생성 시간 | < 500ms |

## 7.3 15개 노드 타입 테스트 케이스 (확장)

| ID | 유형 | 노드 타입 | 설명 | 기대 결과 |
| --- | --- | --- | --- | --- |
| TC-WF-P0-001 | 단위 | DATA | 데이터 조회 노드 | SQL 실행 성공 |
| TC-WF-P0-002 | 단위 | JUDGMENT | 판단 노드 | Rule+LLM 판단 성공 |
| TC-WF-P0-003 | 단위 | CODE | Python 코드 실행 노드 | 코드 실행 및 결과 반환 |
| TC-WF-P0-004 | 단위 | SWITCH | 분기 노드 | 조건별 경로 선택 |
| TC-WF-P0-005 | 단위 | ACTION | 외부 액션 노드 | 외부 시스템 호출 성공 |
| TC-WF-P1-001 | 단위 | BI | BI 대시보드 노드 | 차트 생성 성공 |
| TC-WF-P1-002 | 단위 | MCP | MCP 도구 호출 노드 | 도구 호출 및 응답 |
| TC-WF-P1-003 | 단위 | TRIGGER | 이벤트 트리거 노드 | 이벤트 발생 감지 |
| TC-WF-P1-004 | 단위 | WAIT | 대기 노드 | 지정 시간/조건 대기 |
| TC-WF-P1-005 | 단위 | APPROVAL | 승인 노드 | 승인/거절 처리 |
| TC-WF-P2-001 | 단위 | PARALLEL | 병렬 실행 노드 | 병렬 실행 및 결과 병합 |
| TC-WF-P2-002 | 단위 | COMPENSATION | 보상 트랜잭션 노드 | 실패 시 보상 로직 실행 |
| TC-WF-P2-003 | 단위 | DEPLOY | 배포 노드 | Canary/Blue-Green 배포 |
| TC-WF-P2-004 | 단위 | ROLLBACK | 롤백 노드 | 이전 버전 복원 |
| TC-WF-P2-005 | 단위 | SIMULATE | 시뮬레이션 노드 | What-if 시뮬레이션 실행 |

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

---

## 문서 이력
| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2025-10-30 | QA Team | 초안 작성 |
| 2.0 | 2025-11-15 | QA Team | 테스트 케이스 확장 |
| 3.0 | 2025-12-16 | QA Team | V7 Intent + Orchestrator + 15 노드 타입 테스트 추가 |

### v3.0 변경 사항
- **V7 Intent 테스트**: 14개 V7 Intent 분류 테스트 케이스 추가 (TC-INT-001~015)
- **Orchestrator 테스트**: Plan 생성 및 Route→Node 매핑 테스트 추가 (TC-ORC-001~010)
- **15 노드 타입 테스트**: P0/P1/P2 우선순위별 노드 테스트 케이스 추가 (TC-WF-P0/P1/P2)
- **커버리지 목표 확장**: V7 Intent 정확도 > 90%, Orchestrator 성공률 > 85%
- **테스트 ID 체계 확장**: TC-INT-XXX, TC-ORC-XXX 추가
