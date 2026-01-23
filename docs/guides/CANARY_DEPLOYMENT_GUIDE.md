# Canary Deployment 운영 가이드

> **작성일**: 2026-01-23
> **대상**: Approver, Admin, 운영팀
> **관련 파일**: `backend/app/services/canary_deployment_service.py` (412줄)

---

## 목차

1. [개요](#개요)
2. [빠른 시작](#빠른-시작)
3. [배포 라이프사이클](#배포-라이프사이클)
4. [Sticky Session](#sticky-session)
5. [자동 롤백](#자동-롤백)
6. [메트릭 모니터링](#메트릭-모니터링)
7. [트러블슈팅](#트러블슈팅)

---

## 개요

Canary Deployment는 **새 규칙 버전을 소수 사용자에게 먼저 배포**하여 안전성을 검증한 후 전체 배포하는 기능입니다.

### 주요 기능

- ✅ **점진적 트래픽 증가**: 10% → 50% → 100%
- ✅ **Sticky Session**: 사용자별 버전 고정 (3계층)
- ✅ **자동 롤백**: Error Rate, Latency 기준
- ✅ **Circuit Breaker**: 장애 전파 방지
- ✅ **v1 vs v2 메트릭 비교**: 성능 추적
- ✅ **보상 트랜잭션**: 롤백 시 데이터 정합성

---

## 빠른 시작

### 5분 Canary 배포

```bash
# 1. 배포 생성
curl -X POST http://localhost:8000/api/v1/deployments \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d '{
    "ruleset_id": "uuid-ruleset",
    "version": "v2.0.0",
    "changelog": "Decision Tree 기반 자동 생성 규칙",
    "canary_config": {
      "initial_traffic_percentage": 10,
      "increment": 10,
      "duration_minutes": 60
    }
  }'

# 응답: deployment_id 저장
# → { "deployment_id": "uuid-deploy", "status": "draft" }

# 2. Canary 시작 (10% 트래픽)
curl -X POST http://localhost:8000/api/v1/deployments/{deployment_id}/start-canary \
  -H "Content-Type: application/json" \
  -d '{
    "canary_pct": 10
  }'

# 3. 30분 후 메트릭 확인
curl http://localhost:8000/api/v1/deployments/{deployment_id}/comparison

# 4. 트래픽 증가 (10% → 50%)
curl -X PUT http://localhost:8000/api/v1/deployments/{deployment_id}/traffic \
  -H "Content-Type: application/json" \
  -d '{
    "traffic_percentage": 50
  }'

# 5. 문제 없으면 100% 승격
curl -X POST http://localhost:8000/api/v1/deployments/{deployment_id}/promote

# 6. 문제 발생 시 즉시 롤백
curl -X POST http://localhost:8000/api/v1/deployments/{deployment_id}/rollback
```

---

## 배포 라이프사이클

### 상태 전이도

```
draft (초기)
  ↓
  start-canary
  ↓
canary (10% → 50% → 100%)
  ↓
  promote
  ↓
active (100% 배포)

  (언제든지)
  ↓
  rollback
  ↓
rolled_back
```

### 상태별 설명

| 상태 | 설명 | 가능한 작업 |
|------|------|------------|
| `draft` | 생성됨, 미시작 | start-canary, update, delete |
| `canary` | Canary 진행 중 | update-traffic, promote, rollback |
| `active` | 100% 배포 완료 | rollback, deprecate |
| `rolled_back` | 롤백됨 | (재배포 시 새 deployment 생성) |
| `deprecated` | 폐기됨 | (읽기 전용) |

---

## 1. 배포 생성

### API

`POST /api/v1/deployments`

### 요청 예시

```json
{
  "ruleset_id": "uuid-ruleset",
  "version": "v2.1.0",
  "changelog": "온도 임계값 25 → 27로 조정",
  "canary_config": {
    "initial_traffic_percentage": 10,
    "increment": 10,
    "duration_minutes": 60,
    "success_threshold": 0.95,
    "error_threshold": 0.05
  },
  "compensation_strategy": "rollback_only"
}
```

### canary_config 파라미터

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `initial_traffic_percentage` | int | 10 | 초기 트래픽 비율 (%) |
| `increment` | int | 10 | 증가 단위 (%) |
| `duration_minutes` | int | 60 | 각 단계 지속 시간 (분) |
| `success_threshold` | float | 0.95 | 성공률 임계값 |
| `error_threshold` | float | 0.05 | 에러율 임계값 |

### compensation_strategy

롤백 시 보상 전략:

| 전략 | 설명 |
|------|------|
| `rollback_only` | 단순 롤백 (기본) |
| `notify_and_rollback` | 알림 + 롤백 |
| `manual` | 수동 처리 대기 |

---

## 2. Canary 시작

### API

`POST /api/v1/deployments/{deployment_id}/start-canary`

### 요청 예시

```json
{
  "canary_pct": 10,
  "canary_target_filter": {
    "user_ids": ["uuid-user-1", "uuid-user-2"],
    "workflow_ids": ["uuid-wf-1"]
  }
}
```

### canary_target_filter (선택적)

특정 사용자/워크플로우에만 Canary 적용:

| 필드 | 타입 | 설명 |
|------|------|------|
| `user_ids` | list[UUID] | 대상 사용자 (null이면 랜덤) |
| `workflow_ids` | list[UUID] | 대상 워크플로우 |

**미지정 시**: 랜덤으로 10% 사용자에게 할당

---

## 3. 트래픽 조정

### API

`PUT /api/v1/deployments/{deployment_id}/traffic`

### 사용 시점

- Canary 메트릭이 양호할 때
- 점진적 확대 (10% → 50% → 100%)
- 문제 발견 시 축소 (50% → 10%)

### 요청 예시

```json
{
  "traffic_percentage": 50
}
```

**권장 증가 주기**:
- 10% → 30분 모니터링
- 20% → 30분 모니터링
- 50% → 1시간 모니터링
- 100% → promote 실행

---

## 4. 승격 (Promote)

### API

`POST /api/v1/deployments/{deployment_id}/promote`

### 효과

1. `status: canary` → `active`
2. `traffic_percentage` → 100%
3. 이전 버전 `status` → `deprecated`
4. 모든 사용자에게 v2 적용

### 사전 확인

```bash
# 1. 메트릭 확인
GET /api/v1/deployments/{deployment_id}/comparison

# 체크 사항:
# - v2_success_rate >= 0.95
# - v2_error_rate <= 0.05
# - v2_p95_latency <= v1_p95_latency × 1.2

# 2. 건강 상태 확인
GET /api/v1/deployments/{deployment_id}/health

# 체크 사항:
# - circuit_breaker_state: CLOSED
# - health_status: healthy
```

---

## 5. 롤백 (Rollback)

### 긴급 롤백 (3분 이내)

```bash
# 즉시 롤백
curl -X POST http://localhost:8000/api/v1/deployments/{deployment_id}/rollback \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Error Rate 5% 초과",
    "apply_compensation": true
  }'
```

### 롤백 파라미터

| 필드 | 설명 |
|------|------|
| `reason` | 롤백 사유 (필수) |
| `apply_compensation` | 보상 트랜잭션 실행 여부 (기본: true) |

### 롤백 효과

1. `status: canary` → `rolled_back`
2. 모든 사용자에게 v1 적용
3. Canary 할당 초기화
4. 보상 트랜잭션 실행 (필요시)
5. 알림 발송 (Slack/Email)

### 보상 트랜잭션 (Compensation)

**rollback_only**:
- 단순히 이전 버전으로 복구
- 데이터 변경 없음

**notify_and_rollback**:
- 롤백 + Slack/Email 알림
- 관리자에게 즉시 통보

**manual**:
- 롤백만 실행
- 수동 보상 작업 대기

---

## Sticky Session

### 3계층 우선순위

Canary 배포 시 사용자별로 버전이 **고정(Sticky)**됩니다.

```
우선순위 1: workflow_id (최우선)
  → 같은 워크플로우는 항상 같은 버전

우선순위 2: session_id (중간)
  → 같은 세션은 같은 버전

우선순위 3: user_id (낮음)
  → 같은 사용자는 같은 버전
```

### 동작 예시

```
사용자 A:
  - workflow_123 → v2 할당 (10% Canary)
  - workflow_123 재실행 → v2 유지 (Sticky)
  - workflow_456 → v1 할당 (90%)

사용자 B:
  - 모든 워크플로우 → v1 (90%)
```

### 할당 확인

```bash
GET /api/v1/deployments/{deployment_id}/assignments?user_id={user_id}
```

**응답**:
```json
{
  "assignments": [
    {
      "assignment_id": "uuid-assign",
      "user_id": "uuid-user",
      "workflow_id": "uuid-wf",
      "session_id": "uuid-session",
      "canary_version_id": "uuid-v2",
      "assigned_at": "2026-01-23T10:00:00Z",
      "priority": "workflow"
    }
  ],
  "total": 1
}
```

---

## 자동 롤백

### 롤백 조건

자동 롤백이 트리거되는 조건:

| 조건 | 임계값 | 측정 주기 |
|------|--------|----------|
| **Error Rate** | > 5% | 5분 |
| **p95 Latency** | > 2× baseline | 5분 |
| **Circuit Breaker** | OPEN 상태 | 즉시 |
| **Success Rate** | < 95% | 10분 |

### Circuit Breaker 동작

```
CLOSED (정상)
  ↓ (연속 5회 실패)
OPEN (차단)
  ↓ (60초 대기)
HALF_OPEN (테스트)
  ↓ (성공 시)
CLOSED

  ↓ (실패 시)
OPEN
```

**OPEN 상태**: 모든 요청이 v1으로 즉시 라우팅됨

### 모니터링

**자동 모니터링 작업**: `canary_monitor_task.py` (5분마다)

```python
# 체크 항목:
1. Error Rate 계산
2. Latency p95 계산
3. Circuit Breaker 상태
4. 자동 롤백 조건 평가
5. 알림 발송 (임계값 초과 시)
```

---

## 메트릭 모니터링

### 실시간 메트릭 조회

**API**: `GET /api/v1/deployments/{deployment_id}/metrics`

```bash
curl http://localhost:8000/api/v1/deployments/{deployment_id}/metrics
```

**응답**:
```json
{
  "deployment_id": "uuid-deploy",
  "v1_metrics": {
    "total_requests": 1000,
    "success_count": 970,
    "error_count": 30,
    "success_rate": 0.97,
    "error_rate": 0.03,
    "avg_latency_ms": 150,
    "p95_latency_ms": 280,
    "p99_latency_ms": 450
  },
  "v2_metrics": {
    "total_requests": 100,
    "success_count": 95,
    "error_count": 5,
    "success_rate": 0.95,
    "error_rate": 0.05,
    "avg_latency_ms": 160,
    "p95_latency_ms": 300,
    "p99_latency_ms": 480
  }
}
```

---

### v1 vs v2 비교

**API**: `GET /api/v1/deployments/{deployment_id}/comparison`

```bash
curl http://localhost:8000/api/v1/deployments/{deployment_id}/comparison
```

**응답**:
```json
{
  "comparison": {
    "success_rate_diff": -0.02,
    "error_rate_diff": +0.02,
    "latency_diff_ms": +10,
    "is_better": false,
    "recommendation": "rollback"
  },
  "analysis": {
    "v1_is_more_reliable": true,
    "v2_is_faster": false,
    "significant_difference": true
  }
}
```

**판정 기준**:
- `is_better: true` → 승격 권장
- `is_better: false` → 롤백 권장
- `significant_difference: false` → 더 데이터 수집 필요

---

### 건강 상태 체크

**API**: `GET /api/v1/deployments/{deployment_id}/health`

```bash
curl http://localhost:8000/api/v1/deployments/{deployment_id}/health
```

**응답**:
```json
{
  "health_status": "healthy",
  "circuit_breaker_state": "CLOSED",
  "current_error_rate": 0.03,
  "current_success_rate": 0.97,
  "last_check_at": "2026-01-23T10:00:00Z",
  "warnings": []
}
```

**health_status 값**:
- `healthy`: 정상
- `degraded`: 성능 저하
- `unhealthy`: 심각한 문제

---

## 운영 시나리오

### 시나리오 1: 정상 배포 (권장 흐름)

```
Day 1, 10:00 - 배포 생성
Day 1, 10:05 - Canary 시작 (10%)
Day 1, 10:35 - 메트릭 확인 (30분 후)
  → v2 Success Rate: 0.97 ✅
  → Error Rate: 0.03 ✅

Day 1, 10:40 - 트래픽 증가 (10% → 50%)
Day 1, 11:40 - 메트릭 확인 (1시간 후)
  → v2 Success Rate: 0.96 ✅
  → Error Rate: 0.04 ✅

Day 1, 11:45 - 100% 승격 (promote)
Day 1, 11:50 - 최종 확인
  → status: active ✅
  → 모든 사용자 v2 사용 ✅
```

---

### 시나리오 2: 문제 발견 및 롤백

```
Day 1, 10:00 - Canary 시작 (10%)
Day 1, 10:30 - 메트릭 확인
  → v2 Error Rate: 0.08 ⚠️ (임계값 0.05 초과)

Day 1, 10:32 - 즉시 롤백
POST /api/v1/deployments/{id}/rollback
{
  "reason": "Error Rate 8% (임계값 5% 초과)",
  "apply_compensation": true
}

Day 1, 10:33 - 롤백 완료
  → 모든 사용자 v1으로 복구
  → Slack 알림 발송
  → Circuit Breaker OPEN (60초)

Day 1, 10:40 - 원인 분석
  → Rhai 스크립트 버그 발견
  → 규칙 수정

Day 1, 14:00 - 수정 후 재배포
  → 새 deployment 생성
```

---

### 시나리오 3: 자동 롤백 (Circuit Breaker)

```
Day 1, 10:00 - Canary 시작 (10%)
Day 1, 10:15 - v2 연속 5회 실패
  → Circuit Breaker: CLOSED → OPEN
  → 자동 롤백 트리거

Day 1, 10:16 - 자동 롤백 실행
  → deployment.status: rolled_back
  → 알림 발송: "Circuit Breaker OPEN, 자동 롤백됨"
  → 로그: canary_execution_logs

Day 1, 11:16 - Circuit Breaker HALF_OPEN (60초 후)
  → 테스트 요청 허용
```

---

## Sticky Session 상세

### 할당 우선순위

**1순위: workflow_id**
```
사용 목적: A/B 테스트 정확도
동작: 같은 워크플로우는 항상 같은 버전

예시:
workflow_123 → v2 할당
  → 이후 모든 실행에서 v2 사용
  → 사용자가 바뀌어도 v2 유지
```

**2순위: session_id**
```
사용 목적: 사용자 경험 일관성
동작: 같은 세션은 같은 버전

예시:
session_abc → v2 할당
  → 세션 내 모든 요청 v2
  → 새 세션 시작 → 재할당
```

**3순위: user_id**
```
사용 목적: 장기 추적
동작: 같은 사용자는 같은 버전

예시:
user_A → v2 할당
  → 모든 워크플로우에서 v2
  → 로그인 다시 해도 v2 유지
```

### 할당 확인

```bash
# 사용자별 할당
GET /api/v1/deployments/{deployment_id}/assignments?user_id={user_id}

# 워크플로우별 할당
GET /api/v1/deployments/{deployment_id}/assignments?workflow_id={workflow_id}

# 전체 할당
GET /api/v1/deployments/{deployment_id}/assignments?page=1&page_size=100
```

---

## 모니터링 대시보드 (Grafana)

### Canary Deployment 메트릭

**Prometheus 메트릭** (자동 수집):

```
canary_deployment_status{deployment_id, status}
canary_traffic_percentage{deployment_id}
canary_v1_requests_total{deployment_id}
canary_v2_requests_total{deployment_id}
canary_v1_errors_total{deployment_id}
canary_v2_errors_total{deployment_id}
canary_v1_latency_seconds{deployment_id, quantile}
canary_v2_latency_seconds{deployment_id, quantile}
```

### Grafana 쿼리 예시

**Success Rate**:
```promql
sum(rate(canary_v2_requests_total[5m]))
/
(sum(rate(canary_v2_requests_total[5m])) + sum(rate(canary_v2_errors_total[5m])))
```

**Error Rate**:
```promql
sum(rate(canary_v2_errors_total[5m]))
/
sum(rate(canary_v2_requests_total[5m]))
```

**Latency p95**:
```promql
histogram_quantile(0.95, canary_v2_latency_seconds)
```

---

## 프론트엔드 통합

### useCanaryVersion Hook

**파일**: `frontend/src/hooks/useCanaryVersion.ts`

```typescript
import { useCanaryVersion } from '@/hooks/useCanaryVersion';

function MyComponent() {
  const { canaryVersion, isCanary } = useCanaryVersion();

  // 쿼리 키에 버전 포함
  const { data } = useQuery({
    queryKey: ['rulesets', canaryVersion],
    queryFn: () => fetchRulesets(),
  });

  return (
    <div>
      {isCanary && <Badge>Canary v2</Badge>}
      {/* ... */}
    </div>
  );
}
```

### 버전별 쿼리 키 관리

```typescript
// v1과 v2의 캐시를 분리
withCanaryVersion(['rulesets'])
// → ['rulesets', 'v1'] 또는 ['rulesets', 'v2']

// 버전 변경 시 캐시 무효화
invalidateCanaryQueries(['rulesets'])
```

---

## 트러블슈팅

### 1. Canary 시작 실패

**증상**: `400 Bad Request: 이미 active 배포가 있습니다`

**원인**: 동일 Ruleset에 이미 active 배포 존재

**해결**:
```bash
# 1. 기존 배포 확인
GET /api/v1/deployments?ruleset_id={ruleset_id}&status=active

# 2. 기존 배포 deprecate 또는 삭제
POST /api/v1/deployments/{old_id}/rollback

# 3. 새 배포 시작
POST /api/v1/deployments/{new_id}/start-canary
```

---

### 2. 트래픽 비율 안 변함

**증상**: `traffic_percentage` 업데이트했는데 실제 트래픽 변화 없음

**원인**: Sticky Session 때문에 기존 할당 유지

**해결**:
```bash
# 정상 동작임!
# Sticky Session은 버전 고정이 목적
# 새 사용자/세션부터 새 비율 적용됨

# 강제 재할당 (주의!)
# → 모든 할당 초기화 후 재시작
POST /api/v1/deployments/{id}/rollback
POST /api/v1/deployments/{id}/start-canary
```

---

### 3. 메트릭 데이터 없음

**증상**: `v2_metrics: null`

**원인**: v2로 실행된 요청이 아직 없음

**해결**:
```bash
# 1. Canary 할당 확인
GET /api/v1/deployments/{id}/assignments

# 2. 할당된 사용자가 있는지 확인
# 3. 없으면 트래픽 비율 증가
PUT /api/v1/deployments/{id}/traffic
{
  "traffic_percentage": 20  # 10 → 20
}

# 4. 30분 대기 후 재확인
```

---

### 4. 자동 롤백 안됨

**증상**: Error Rate 10%인데 롤백 안됨

**원인**: 자동 모니터링 작업 미실행

**확인**:
```bash
# 스케줄러 상태 확인
GET /api/v1/scheduler/jobs

# canary_monitor_task가 active인지 확인
```

**해결**:
```bash
# 스케줄러 재시작
docker-compose restart backend

# 수동 롤백
POST /api/v1/deployments/{id}/rollback
```

---

### 5. Circuit Breaker 항상 OPEN

**증상**: Circuit Breaker가 계속 OPEN 상태

**원인**: v2 규칙에 버그가 있어서 계속 실패

**해결**:
```bash
# 1. 롤백
POST /api/v1/deployments/{id}/rollback

# 2. v2 규칙 검토
GET /api/v1/rulesets/{ruleset_id}/versions

# 3. Rhai 스크립트 디버그
POST /api/v1/rulesets/{id}/test
{
  "input": {...},
  "expected_output": {...}
}

# 4. 규칙 수정 후 재배포
```

---

## 권장 사항

### DO (권장)

✅ **점진적 증가**: 10% → 20% → 50% → 100%
✅ **충분한 모니터링**: 각 단계마다 30분 이상
✅ **메트릭 비교**: v1 vs v2 반드시 확인
✅ **롤백 준비**: 언제든지 롤백 가능하도록
✅ **Slack 알림 설정**: 자동 롤백 알림 활성화

### DON'T (지양)

❌ **급격한 증가**: 10% → 100% (위험)
❌ **모니터링 생략**: 메트릭 확인 없이 승격
❌ **장시간 Canary**: 7일 이상 (결정 지연)
❌ **수동 버전 고정**: Sticky Session 무시
❌ **Circuit Breaker 무시**: OPEN 상태에서 재시도

---

## 권한 요구사항

| 작업 | 필요 권한 |
|------|----------|
| 배포 조회 | Viewer 이상 |
| 배포 생성 | Approver 이상 |
| Canary 시작 | Approver 이상 |
| 트래픽 조정 | Approver 이상 |
| 승격 (Promote) | Approver 이상 |
| 롤백 (Rollback) | Approver 이상 |
| 배포 삭제 | Admin |

---

## 체크리스트

### Canary 시작 전
- [ ] v2 규칙 테스트 완료 (`POST /rulesets/{id}/test`)
- [ ] Slack 알림 설정 확인
- [ ] 롤백 절차 숙지
- [ ] 모니터링 대시보드 준비

### Canary 진행 중 (매 30분)
- [ ] 메트릭 확인 (`GET /deployments/{id}/comparison`)
- [ ] Circuit Breaker 상태 확인 (`GET /deployments/{id}/health`)
- [ ] Error Rate < 5% 확인
- [ ] Success Rate >= 95% 확인

### 승격 전
- [ ] 최소 1시간 이상 50% 트래픽 유지
- [ ] v2 Success Rate >= v1 Success Rate
- [ ] v2 p95 Latency <= v1 × 1.2
- [ ] Circuit Breaker CLOSED 상태

### 승격 후
- [ ] 모든 사용자 v2 사용 확인
- [ ] 이전 버전 status: deprecated 확인
- [ ] 24시간 모니터링

---

## 참조 문서

- [V2_Implementation_Plan.md](../project/V2_Implementation_Plan.md) - V2 Phase 0 계획
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - 일반 트러블슈팅
- [Trust Model 가이드](../specs/A-requirements/A-2-5_V2_Algorithm_Specification.md) - Trust Level 연동

---

**문서 버전**: 1.0
**최종 업데이트**: 2026-01-23
