# C-4. Performance & Capacity Planning

## 1. 목표 성능 지표 (초안)
- Judgment API p95 지연 ≤ 1.5s (캐시 히트 시 ≤ 300ms), TPS 목표 50~200 req/s 테넌트 합산
- Workflow 실행 성공률 ≥ 99%, 평균 노드 체류시간 ≤ 500ms(외부 I/O 제외)
- BI Plan 생성 ≤ 3s, BI Query 응답 p95 ≤ 2s(Pre-agg/캐시 기준)
- LLM 파싱 실패율 < 0.5%, 캐시 적중률 40%+

## 2. 부하 시나리오
- **정상**: 판단 요청 10rps, BI 질의 2rps, WF 실행 5rps, MCP 호출 3rps
- **피크**: 판단 50rps, WF 20rps(병렬), MCP 15rps, LLM 호출 집중 (이벤트/알림 폭증)
- **최악**: 외부 DB 지연/LLM 장애 + 재시도 증가 → 회로차단/폴백 경로 작동 확인

## 3. 아키텍처 성능 설계 포인트
- 캐시: Redis read-through, 키=workflow_id+입력 해시, TTL 정책; BI Pre-agg/Materialized View
- 비동기화: MCP/Action/외부 I/O 비동기 실행, WF 노드 병렬 지원
- CQRS: 읽기(BI/조회)와 쓰기(판단/로그) 분리 옵션, 읽기 레플리카 고려
- 샤딩/스케일: 테넌트/서비스별 HPA, Redis Cluster/DB 파티셔닝(날짜 기준)
- 지연 단축: LLM 토큰 제한/압축 프롬프트, RAG 결과 캐싱, Rule-only fast path

## 4. 성능 테스트 계획
- **벤치**: k6/Locust로 Judgment/Workflow/BI/API 별 독립 부하 + 종합 부하
- **시나리오**: 캐시 히트/미스, LLM 타임아웃, MCP 지연, 대량 병렬 WF
- **계측**: p50/p95/p99, 에러율, 재시도율, 큐 대기시간, CPU/Mem, Redis/DB latency
- **용량 산정**: rps→서비스 인스턴스 수, Redis/DB QPS, 네트워크 I/O 추정, 버퍼 30% 적용
- **튜닝 루프**: 병목 식별(슬로우 쿼리/락), 인덱스/파티션 정비, 캐시 TTL 조정, 스레드/워크자 풀 조정
