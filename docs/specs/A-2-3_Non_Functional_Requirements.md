# A-2-3. System Requirements Specification - Non-Functional Requirements

## 문서 정보
- **문서 ID**: A-2-3
- **버전**: 1.0
- **최종 수정일**: 2025-11-26
- **상태**: Draft
- **선행 문서**: A-2-1, A-2-2

## 목차
1. [성능 요구사항 (Performance)](#1-성능-요구사항-performance)
2. [확장성 요구사항 (Scalability)](#2-확장성-요구사항-scalability)
3. [가용성 및 복구 요구사항 (Availability & Recovery)](#3-가용성-및-복구-요구사항-availability--recovery)
4. [보안 요구사항 (Security)](#4-보안-요구사항-security)
5. [감사 및 추적성 요구사항 (Auditability & Traceability)](#5-감사-및-추적성-요구사항-auditability--traceability)
6. [국제화 및 현지화 요구사항 (I18N & L10N)](#6-국제화-및-현지화-요구사항-i18n--l10n)
7. [품질 및 알람 요구사항 (Quality & Alerting)](#7-품질-및-알람-요구사항-quality--alerting)

---

## 1. 성능 요구사항 (Performance)

### 1.1 개요
시스템 응답 시간, 처리량, 리소스 사용률에 대한 정량적 목표를 정의한다.

### 1.2 응답 시간 (Latency)

#### NFR-PERF-010: Judgment Engine 응답 시간

**요구사항 설명**:
- Judgment Engine은 평균 1.5초 이내, 캐시 적중 시 300ms 이내로 응답해야 한다.

**상세 기준**:

| 시나리오 | 평균 (P50) | P95 | P99 | 최대 |
|----------|------------|-----|-----|------|
| **캐시 적중** | 200ms | 300ms | 400ms | 500ms |
| **Rule Only** | 400ms | 800ms | 1200ms | 1500ms |
| **LLM Only** | 3000ms | 5000ms | 8000ms | 15000ms |
| **Hybrid Weighted** | 1500ms | 2500ms | 4000ms | 10000ms |
| **Hybrid Gate (Rule 성공)** | 400ms | 800ms | 1200ms | 1500ms |
| **Hybrid Gate (LLM 호출)** | 3500ms | 6000ms | 9000ms | 15000ms |

**측정 방법**:
- Prometheus 메트릭: `judgment_execution_duration_seconds`
- 모니터링: Grafana 대시보드, P50/P95/P99 패널
- 알람: P95 > 3초 또는 P99 > 5초 시 알람

**최적화 전략**:
- 캐시 TTL 조정 (기본 300초 → 최적값 찾기)
- Rule 엔진 최적화 (Rhai 스크립트 복잡도 감소)
- LLM API 병렬 호출 (여러 모델 동시 호출)
- 타임아웃 설정 (Rule 500ms, LLM 15초)

**수락 기준**:
- [ ] 운영 환경에서 P50 < 1.5초 (Hybrid 기준)
- [ ] 캐시 적중 시 P95 < 300ms
- [ ] P99 < 5초 (LLM 호출 포함)
- [ ] 타임아웃 초과 시 적절한 에러 반환

**우선순위**: P0 (Critical)
**테스트 케이스**: C-3-TC-NFR-PERF-010-*

---

#### NFR-PERF-020: BI 플래너 응답 시간

**요구사항 설명**:
- BI 플래너는 자연어 질의를 analysis_plan으로 변환하고 SQL을 실행하여 3초 이내로 응답해야 한다.

**상세 기준**:

| 구간 | 평균 (P50) | P95 | P99 | 최대 |
|------|------------|-----|-----|------|
| **자연어 → analysis_plan** | 1000ms | 2000ms | 3000ms | 5000ms |
| **SQL 생성 및 실행** | 500ms | 1500ms | 2500ms | 10000ms |
| **차트 설정 생성** | 200ms | 400ms | 600ms | 1000ms |
| **전체 (E2E)** | 1700ms | 3000ms | 4500ms | 10000ms |

**최적화 전략**:
- LLM 모델 선택 (Haiku for simple queries, GPT-4o for complex)
- Pre-aggregation 활용 (Materialized Views)
- 쿼리 캐싱 (Redis, TTL 600초)
- SQL 타임아웃 (기본 30초)

**수락 기준**:
- [ ] E2E P50 < 2초
- [ ] E2E P95 < 3초
- [ ] Pre-agg 사용 시 SQL 실행 < 500ms
- [ ] 캐시 적중률 > 30%

**우선순위**: P0 (Critical)
**테스트 케이스**: C-3-TC-NFR-PERF-020-*

---

#### NFR-PERF-030: Workflow 실행 응답 시간

**요구사항 설명**:
- Workflow 인스턴스는 노드 수와 복잡도에 따라 적절한 시간 내에 완료되어야 한다.

**상세 기준**:

| 워크플로우 복잡도 | 노드 수 | 평균 실행 시간 | P95 | 최대 |
|------------------|---------|----------------|-----|------|
| **Simple** | 3~5 | 5초 | 10초 | 30초 |
| **Medium** | 6~10 | 15초 | 30초 | 60초 |
| **Complex** | 11~20 | 30초 | 60초 | 120초 |
| **Very Complex** | 21+ | 60초 | 120초 | 300초 |

**노드별 평균 실행 시간**:

| 노드 타입 | 평균 | P95 | 설명 |
|----------|------|-----|------|
| DATA | 300ms | 800ms | DB 쿼리 실행 |
| JUDGMENT | 1500ms | 3000ms | Judgment Engine 호출 |
| MCP | 2000ms | 5000ms | 외부 MCP 서버 호출 |
| ACTION | 500ms | 1000ms | Slack/Email 전송 |
| SWITCH | 50ms | 100ms | 조건 평가 |
| PARALLEL | Variable | Variable | 병렬 분기 중 최대 시간 |
| WAIT | Variable | Variable | 외부 이벤트 대기 |

**수락 기준**:
- [ ] Simple Workflow P95 < 10초
- [ ] Complex Workflow P95 < 120초
- [ ] 각 노드 타입별 P95 목표 달성
- [ ] 타임아웃 설정 및 자동 재시도

**우선순위**: P1 (High)
**테스트 케이스**: C-3-TC-NFR-PERF-030-*

---

#### NFR-PERF-040: MCP 도구 호출 응답 시간

**요구사항 설명**:
- MCP 도구 호출은 기본 타임아웃 5초를 준수하며, 도구별로 조정 가능해야 한다.

**상세 기준**:

| MCP 도구 | 평균 | P95 | 타임아웃 |
|----------|------|-----|----------|
| Excel 읽기 | 800ms | 2000ms | 10000ms |
| Excel 쓰기 | 1200ms | 3000ms | 15000ms |
| GDrive 파일 조회 | 1500ms | 4000ms | 10000ms |
| Jira 이슈 생성 | 2000ms | 5000ms | 10000ms |
| 로봇 명령 전송 | 500ms | 1000ms | 5000ms |

**재시도 정책**:
- 네트워크 에러: 최대 3회, 지수 백오프 (1초, 2초, 4초)
- 5xx 에러: 최대 2회, 선형 백오프 (1초, 2초)
- 타임아웃: 재시도 없음
- 4xx 에러: 재시도 없음

**수락 기준**:
- [ ] 기본 타임아웃 5초 설정
- [ ] 도구별 타임아웃 개별 설정 가능
- [ ] 재시도 정책 동작 확인
- [ ] 타임아웃 발생 시 명확한 에러 메시지

**우선순위**: P1 (High)
**테스트 케이스**: C-3-TC-NFR-PERF-040-*

---

### 1.3 처리량 (Throughput)

#### NFR-PERF-050: 동시 요청 처리량

**요구사항 설명**:
- 시스템은 동시 사용자 500명, 초당 50 Judgment 요청을 처리할 수 있어야 한다.

**상세 기준**:

| 서비스 | 목표 TPS | 동시 요청 | 스케일링 기준 |
|--------|----------|-----------|--------------|
| **Judgment Engine** | 50 TPS | 100 concurrent | CPU > 70% 시 스케일아웃 |
| **Workflow Engine** | 20 TPS | 50 concurrent | 인스턴스 대기 > 10개 |
| **BI Engine** | 10 TPS | 30 concurrent | 쿼리 대기 > 5개 |
| **MCP Hub** | 30 TPS | 80 concurrent | 도구 호출 대기 > 20개 |
| **Chat Engine** | 40 TPS | 100 concurrent | 세션 대기 > 15개 |

**부하 테스트 시나리오**:
- **Judgment 부하**: 100 사용자, 10분간 연속 요청
- **BI 부하**: 50 사용자, 동시 쿼리 실행
- **Workflow 부하**: 30 사용자, 복잡한 워크플로우 실행
- **혼합 부하**: 실제 사용 패턴 시뮬레이션

**수락 기준**:
- [ ] Judgment Engine 50 TPS 처리 가능
- [ ] 전체 시스템 500 동시 사용자 지원
- [ ] 부하 테스트 통과 (에러율 < 1%)
- [ ] 자동 스케일링 동작 확인

**우선순위**: P1 (High)
**테스트 케이스**: C-3-TC-NFR-PERF-050-*

---

### 1.4 리소스 사용률

#### NFR-PERF-060: 리소스 제한

**요구사항 설명**:
- 각 서비스는 정의된 리소스 제한 내에서 동작해야 한다.

**상세 기준**:

| 서비스 | CPU (Request/Limit) | 메모리 (Request/Limit) | 디스크 |
|--------|---------------------|------------------------|--------|
| **Judgment Engine** | 500m / 2000m | 512Mi / 2Gi | 5GB |
| **Workflow Engine** | 300m / 1000m | 256Mi / 1Gi | 10GB |
| **BI Engine** | 500m / 2000m | 1Gi / 4Gi | 5GB |
| **MCP Hub** | 200m / 800m | 256Mi / 1Gi | 2GB |
| **Chat Engine** | 300m / 1000m | 512Mi / 2Gi | 5GB |
| **PostgreSQL** | 1000m / 4000m | 4Gi / 16Gi | 500GB |
| **Redis** | 200m / 500m | 512Mi / 2Gi | 10GB |

**모니터링 및 알람**:
- CPU 사용률 > 80%: Warning
- CPU 사용률 > 90%: Critical
- 메모리 사용률 > 85%: Warning
- 메모리 사용률 > 95%: Critical
- 디스크 사용률 > 80%: Warning

**수락 기준**:
- [ ] 각 서비스 리소스 제한 준수
- [ ] 리소스 초과 시 자동 스케일아웃
- [ ] OOM (Out of Memory) 발생 시 자동 재시작
- [ ] 리소스 사용률 모니터링 대시보드

**우선순위**: P1 (High)
**테스트 케이스**: C-3-TC-NFR-PERF-060-*

---

### 1.5 LLM 파싱 성공률

#### NFR-PERF-070: LLM JSON 파싱 실패율

**요구사항 설명**:
- LLM JSON 응답 파싱 실패율은 0.5% 미만이어야 한다.

**상세 기준**:
- **파싱 실패 원인**:
  - JSON 형식 오류 (Syntax Error)
  - 필수 필드 누락
  - 타입 불일치
  - 불완전한 응답 (중간 잘림)
- **복구 전략**:
  - 자동 재시도 (최대 3회)
  - JSON 수정 시도 (자동 보정)
  - 기본 응답 반환 (Fallback)
- **모니터링**:
  - 파싱 실패율 실시간 추적
  - 실패 원인 분류 및 로깅

**파싱 실패 처리 흐름**:
```
1. LLM 응답 수신
2. JSON 파싱 시도
3. 파싱 실패 → 재시도 (최대 3회)
4. 3회 실패 → JSON 자동 보정 시도
5. 보정 실패 → 기본 응답 반환
6. 실패 로그 기록 (원인, LLM 프롬프트, 응답)
```

**수락 기준**:
- [ ] 파싱 실패율 < 0.5%
- [ ] 자동 재시도 로직 동작 확인
- [ ] JSON 자동 보정 기능 동작 확인
- [ ] 실패 로그 및 알람

**우선순위**: P1 (High)
**테스트 케이스**: C-3-TC-NFR-PERF-070-*

---

## 2. 확장성 요구사항 (Scalability)

### 2.1 개요
시스템은 사용자 증가, 데이터 증가, 트래픽 증가에 대응할 수 있어야 한다.

### 2.2 수평 확장 (Horizontal Scaling)

#### NFR-SCALE-010: 모듈 단위 스케일아웃

**요구사항 설명**:
- 각 모듈(API, Judgment, WF, BI, MCP Hub)은 독립적으로 수평 확장 가능해야 한다.

**상세 기준**:
- **Stateless 설계**: 인스턴스 간 상태 공유 없음 (세션은 Redis)
- **로드 밸런싱**: Kubernetes Service (Round-robin) 또는 Ingress (가중치)
- **자동 스케일링**: Horizontal Pod Autoscaler (HPA)
  - 메트릭: CPU, 메모리, 커스텀 메트릭 (요청 큐 길이)
  - 최소 인스턴스: 2개 (High Availability)
  - 최대 인스턴스: 10개 (비용 제한)
- **스케일아웃 조건**:
  - CPU > 70% for 3분
  - 메모리 > 80% for 3분
  - 요청 큐 > threshold for 1분

**HPA 설정 예시** (Kubernetes):
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: judgment-engine-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: judgment-engine
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Pods
        value: 1
        periodSeconds: 60
```

**수락 기준**:
- [ ] 각 모듈 독립적 스케일아웃 가능
- [ ] HPA 동작 확인 (부하 테스트)
- [ ] 스케일아웃 후 로드 밸런싱 정상 동작
- [ ] 스케일다운 시 Graceful Shutdown

**우선순위**: P0 (Critical)
**테스트 케이스**: C-3-TC-NFR-SCALE-010-*

---

#### NFR-SCALE-020: 테넌트 분리

**요구사항 설명**:
- 멀티테넌트 구조에서 각 테넌트는 독립적으로 격리되고, 하나의 테넌트 문제가 다른 테넌트에 영향을 주지 않아야 한다.

**상세 기준**:
- **데이터 격리**: 모든 테이블에 `tenant_id` 포함, RLS (Row-Level Security) 적용 가능
- **리소스 격리**: 테넌트별 쿼터 설정 (Judgment 횟수, 저장 용량)
- **네트워크 격리**: 테넌트별 Virtual Network (선택적, 엔터프라이즈)
- **쿼터 정책**:

| 등급 | Judgment/월 | 저장 용량 | 동시 Workflow |
|------|-------------|-----------|--------------|
| **Free** | 1,000회 | 1GB | 5개 |
| **Standard** | 10,000회 | 10GB | 20개 |
| **Premium** | 100,000회 | 100GB | 100개 |
| **Enterprise** | Unlimited | Unlimited | Unlimited |

**쿼터 초과 처리**:
- 경고 (80%): 이메일 알림
- 제한 (100%): API 429 에러 반환
- 자동 업그레이드 안내

**수락 기준**:
- [ ] tenant_id 기반 데이터 격리
- [ ] 쿼터 정책 적용 및 초과 시 제한
- [ ] 테넌트 간 성능 간섭 최소화 (QoS)
- [ ] 쿼터 모니터링 대시보드

**우선순위**: P0 (Critical)
**테스트 케이스**: C-3-TC-NFR-SCALE-020-*

---

### 2.3 데이터 확장

#### NFR-SCALE-030: 데이터 증가 대응

**요구사항 설명**:
- 시스템은 데이터 증가에 대응하기 위해 파티셔닝, 아카이빙, 퍼징 전략을 구현해야 한다.

**상세 기준**:
- **파티셔닝**: 시계열 데이터 월별/분기별 파티셔닝 (B-3-4 참조)
  - `judgment_executions`: 월별 파티션
  - `workflow_instances`: 월별 파티션
  - `fact_*` 테이블: 분기별 파티션
- **아카이빙**: 90일 이후 데이터 콜드 스토리지 이동
  - 핫 스토리지: 최근 90일 (SSD)
  - 콜드 스토리지: 90일~2년 (HDD 또는 Object Storage)
- **퍼징 (Purging)**: 보존 기간 초과 데이터 삭제
  - 로그 데이터: 2년 후 삭제
  - 학습 샘플: 영구 보존
  - 임시 데이터: 30일 후 삭제

**데이터 라이프사이클**:
```
생성 → 핫 스토리지 (0~90일) → 콜드 스토리지 (90일~2년) → 삭제 (2년+)
```

**수락 기준**:
- [ ] 파티셔닝 자동 생성 및 관리
- [ ] 90일 후 자동 아카이빙
- [ ] 2년 후 자동 삭제 (규제 준수)
- [ ] 아카이브 데이터 조회 API 제공

**우선순위**: P1 (High)
**테스트 케이스**: C-3-TC-NFR-SCALE-030-*

---

## 3. 가용성 및 복구 요구사항 (Availability & Recovery)

### 3.1 개요
시스템은 고가용성을 유지하고, 장애 발생 시 빠르게 복구할 수 있어야 한다.

### 3.2 고가용성 (High Availability)

#### NFR-HA-010: 핵심 서비스 이중화

**요구사항 설명**:
- 핵심 서비스는 최소 2개 이상의 인스턴스를 운영하여 단일 장애점(SPOF)을 제거해야 한다.

**상세 기준**:
- **핵심 서비스**: Judgment, Workflow, BI, API Gateway
- **최소 인스턴스**: 2개 (Active-Active)
- **로드 밸런싱**: Kubernetes Service (L4) + Ingress (L7)
- **헬스 체크**:
  - Liveness Probe: 서비스 생존 여부 (HTTP GET /health)
  - Readiness Probe: 트래픽 수신 준비 (HTTP GET /ready)
  - 실패 시 자동 재시작 또는 트래픽 제외

**헬스 체크 설정 예시** (Kubernetes):
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 2
```

**수락 기준**:
- [ ] 핵심 서비스 최소 2개 인스턴스 운영
- [ ] 헬스 체크 정상 동작
- [ ] 인스턴스 장애 시 자동 트래픽 제외
- [ ] 99.9% 가용성 (월 43분 다운타임 허용)

**우선순위**: P0 (Critical)
**테스트 케이스**: C-3-TC-NFR-HA-010-*

---

#### NFR-HA-020: 데이터베이스 복제

**요구사항 설명**:
- PostgreSQL은 마스터-슬레이브 복제를 구성하여 읽기 부하 분산 및 장애 대응을 지원해야 한다.

**상세 기준**:
- **복제 방식**: Streaming Replication (동기 또는 비동기)
- **토폴로지**: 1 Master + 2 Replicas
- **읽기/쓰기 분리**:
  - Master: 쓰기 전용
  - Replica: 읽기 전용 (분석 쿼리, 보고서)
- **자동 Failover**: Patroni 또는 PgPool 사용
  - Master 장애 시 Replica를 Master로 승격
  - VIP (Virtual IP) 또는 DNS 업데이트

**Failover 시나리오**:
```
1. Master 장애 감지 (헬스 체크 3회 실패)
2. Replica 중 하나를 Master로 승격
3. 다른 Replica는 새 Master를 따르도록 재설정
4. VIP를 새 Master로 이동
5. 애플리케이션은 VIP 통해 자동 재연결
6. 구 Master 복구 후 Replica로 재참여
```

**수락 기준**:
- [ ] Streaming Replication 구성
- [ ] 읽기/쓰기 분리 동작 확인
- [ ] Failover 자동화 (5분 이내 복구)
- [ ] 데이터 손실 없음 (동기 복제 시)

**우선순위**: P1 (High)
**테스트 케이스**: C-3-TC-NFR-HA-020-*

---

#### NFR-HA-030: Redis 복제 및 AOF

**요구사항 설명**:
- Redis는 복제 또는 AOF(Append-Only File)를 구성하여 캐시 데이터 손실을 최소화해야 한다.

**상세 기준**:
- **복제 방식**: Master-Replica (비동기 복제)
- **지속성**: AOF (Append-Only File) 활성화
  - `appendfsync everysec`: 1초마다 디스크 동기화
  - 재시작 시 AOF 파일로 복구
- **센티널**: Redis Sentinel을 통한 자동 Failover
  - Master 장애 시 Replica를 Master로 승격
  - 클라이언트 자동 재연결

**Redis 설정 예시**:
```conf
# redis.conf
appendonly yes
appendfsync everysec
save 900 1
save 300 10
save 60 10000
```

**수락 기준**:
- [ ] Redis Replication 구성
- [ ] AOF 활성화 및 복구 테스트
- [ ] Sentinel 자동 Failover 동작 확인
- [ ] 캐시 데이터 손실 < 1초 범위

**우선순위**: P1 (High)
**테스트 케이스**: C-3-TC-NFR-HA-030-*

---

### 3.3 재해 복구 (Disaster Recovery)

#### NFR-DR-010: 백업 전략

**요구사항 설명**:
- 시스템은 정기적으로 데이터를 백업하고, 복구 시나리오를 검증해야 한다.

**상세 기준**:
- **PostgreSQL 백업**:
  - **Full Backup**: 일 1회 (오전 3시)
  - **Incremental Backup**: WAL 아카이빙 (실시간)
  - **보존 기간**: 30일
- **Redis 백업**:
  - **RDB 스냅샷**: 시간 1회
  - **AOF 파일**: 실시간
  - **보존 기간**: 7일
- **백업 저장소**: S3 또는 NAS (원격 위치)
- **암호화**: AES-256 암호화 저장

**백업 스크립트 예시**:
```bash
#!/bin/bash
# PostgreSQL Full Backup
DATE=$(date +%Y%m%d)
pg_dump -h localhost -U postgres -d factory_ai -F c -f /backup/factory_ai_$DATE.dump

# Upload to S3
aws s3 cp /backup/factory_ai_$DATE.dump s3://factory-ai-backups/postgres/

# Delete old backups (30 days)
find /backup -name "factory_ai_*.dump" -mtime +30 -delete
```

**수락 기준**:
- [ ] 일 1회 Full Backup 자동 실행
- [ ] WAL 아카이빙 실시간 동작
- [ ] 백업 파일 암호화
- [ ] 백업 파일 원격 저장소 업로드

**우선순위**: P0 (Critical)
**테스트 케이스**: C-3-TC-NFR-DR-010-*

---

#### NFR-DR-020: 복구 시간 목표 (RTO/RPO)

**요구사항 설명**:
- 시스템은 정의된 RTO/RPO 목표를 달성할 수 있어야 한다.

**상세 기준**:

| 서비스 | RTO (Recovery Time Objective) | RPO (Recovery Point Objective) |
|--------|--------------------------------|--------------------------------|
| **핵심 서비스** | 4시간 | 30분 |
| **PostgreSQL** | 1시간 | 15분 (WAL 아카이빙) |
| **Redis** | 30분 | 1초 (AOF) |
| **파일 스토리지** | 2시간 | 1시간 |

**복구 시나리오**:
- **시나리오 1**: PostgreSQL 데이터 손상
  - 최신 Full Backup 복원 (30분)
  - WAL 아카이브 재생 (15분)
  - 애플리케이션 재연결 (5분)
  - **총 RTO**: 50분
- **시나리오 2**: Redis 장애
  - Replica를 Master로 승격 (5분)
  - 애플리케이션 자동 재연결 (1분)
  - **총 RTO**: 6분
- **시나리오 3**: 전체 데이터센터 장애
  - DR 사이트로 트래픽 전환 (30분)
  - 백업 데이터 복원 (3시간)
  - **총 RTO**: 3.5시간

**수락 기준**:
- [ ] 각 서비스 RTO 목표 달성
- [ ] RPO 목표 달성 (데이터 손실 최소화)
- [ ] 복구 절차 문서화 (D-3 참조)
- [ ] 연 1회 DR 훈련 실시

**우선순위**: P1 (High)
**테스트 케이스**: C-3-TC-NFR-DR-020-*

---

## 4. 보안 요구사항 (Security)

### 4.1 개요
시스템은 인증, 암호화, 취약점 방어, 규제 준수를 통해 보안을 보장해야 한다.

### 4.2 전송 및 저장 암호화

#### NFR-SEC-010: 전송 암호화 (TLS)

**요구사항 설명**:
- 모든 외부 통신은 TLS 1.2 이상을 사용하여 암호화해야 한다.

**상세 기준**:
- **프로토콜**: TLS 1.2 또는 TLS 1.3
- **암호화 스위트**:
  - 권장: `ECDHE-RSA-AES256-GCM-SHA384`
  - 금지: RC4, DES, 3DES, MD5
- **인증서**: Let's Encrypt 또는 상용 인증서
- **HSTS**: HTTP Strict Transport Security 헤더 추가

**Nginx 설정 예시**:
```nginx
server {
    listen 443 ssl http2;
    server_name factory-ai.example.com;

    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256';
    ssl_prefer_server_ciphers on;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    location / {
        proxy_pass http://api-gateway:8080;
    }
}
```

**수락 기준**:
- [ ] TLS 1.2 이상 사용
- [ ] 안전한 암호화 스위트만 허용
- [ ] HSTS 헤더 추가
- [ ] SSL Labs A+ 등급 (테스트)

**우선순위**: P0 (Critical)
**테스트 케이스**: C-3-TC-NFR-SEC-010-*

---

#### NFR-SEC-020: 저장 암호화

**요구사항 설명**:
- 민감 정보(비밀번호, API Key, PII)는 AES-256으로 암호화하여 저장해야 한다.

**상세 기준**:
- **암호화 대상**:
  - 사용자 비밀번호: bcrypt (해시)
  - API Key: AES-256-GCM
  - 커넥터 비밀번호: AES-256-GCM
  - PII (선택적): AES-256-GCM
- **키 관리**: AWS KMS, HashiCorp Vault, 또는 자체 키 관리
- **키 로테이션**: 연 1회 암호화 키 교체

**암호화 예시** (Python):
```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

def encrypt(plaintext, key):
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return nonce + ciphertext

def decrypt(ciphertext, key):
    aesgcm = AESGCM(key)
    nonce = ciphertext[:12]
    plaintext = aesgcm.decrypt(nonce, ciphertext[12:], None)
    return plaintext.decode()

# Usage
key = os.urandom(32)  # 256-bit key
encrypted = encrypt("my-secret-password", key)
decrypted = decrypt(encrypted, key)
```

**수락 기준**:
- [ ] 민감 정보 AES-256 암호화
- [ ] 암호화 키 안전 저장 (KMS/Vault)
- [ ] 키 로테이션 절차 수립
- [ ] 암호화/복호화 성능 < 10ms

**우선순위**: P0 (Critical)
**테스트 케이스**: C-3-TC-NFR-SEC-020-*

---

### 4.3 Webhook 보안

#### NFR-SEC-030: Webhook 서명 및 멱등성

**요구사항 설명**:
- Webhook 요청은 HMAC 서명으로 인증하고, 멱등성 키로 중복 처리를 방지해야 한다.

**상세 기준**:
- **HMAC 서명**: SHA-256 기반 HMAC
  - 헤더: `X-Signature: sha256=<hmac_hex>`
  - 페이로드 전체를 서명
- **멱등성 키**: 각 요청에 고유 ID 포함
  - 헤더: `X-Idempotency-Key: <uuid>`
  - Redis에 키 저장 (TTL 24시간)
  - 동일 키 재요청 시 이전 응답 반환
- **타임스탬프**: 요청 시각 포함
  - 헤더: `X-Timestamp: <unix_timestamp>`
  - 5분 이상 오래된 요청 거부 (Replay Attack 방지)

**Webhook 발송 예시**:
```python
import hmac
import hashlib
import time
import uuid

def send_webhook(url, payload, secret):
    idempotency_key = str(uuid.uuid4())
    timestamp = int(time.time())

    # HMAC 서명 생성
    message = f"{timestamp}.{json.dumps(payload)}"
    signature = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    headers = {
        'X-Signature': f'sha256={signature}',
        'X-Idempotency-Key': idempotency_key,
        'X-Timestamp': str(timestamp),
        'Content-Type': 'application/json'
    }

    response = requests.post(url, json=payload, headers=headers)
    return response
```

**Webhook 수신 검증**:
```python
def verify_webhook(request, secret):
    timestamp = int(request.headers['X-Timestamp'])
    signature = request.headers['X-Signature'].replace('sha256=', '')
    idempotency_key = request.headers['X-Idempotency-Key']

    # 타임스탬프 검증 (5분 이내)
    if abs(time.time() - timestamp) > 300:
        raise ValueError("Request too old")

    # 멱등성 키 검증
    if redis_client.exists(f"webhook:{idempotency_key}"):
        return redis_client.get(f"webhook:{idempotency_key}")

    # HMAC 서명 검증
    message = f"{timestamp}.{request.body}"
    expected_signature = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        raise ValueError("Invalid signature")

    # 처리 후 멱등성 키 저장 (24시간 TTL)
    result = process_webhook(request.json)
    redis_client.setex(f"webhook:{idempotency_key}", 86400, result)
    return result
```

**수락 기준**:
- [ ] HMAC SHA-256 서명 검증
- [ ] 멱등성 키 중복 요청 방지
- [ ] 타임스탬프 Replay Attack 방지
- [ ] 서명 불일치 시 401 에러 반환

**우선순위**: P1 (High)
**테스트 케이스**: C-3-TC-NFR-SEC-030-*

---

### 4.4 취약점 방어

#### NFR-SEC-040: SQL Injection 방어

**요구사항 설명**:
- 모든 SQL 쿼리는 Prepared Statement를 사용하여 SQL Injection을 방어해야 한다.

**상세 기준**:
- **Prepared Statement**: 파라미터 바인딩 사용
- **ORM 사용**: SQLAlchemy, Django ORM 등
- **입력 검증**: 화이트리스트 기반 검증
- **에러 메시지**: SQL 에러 노출 금지

**Bad Example** (SQL Injection 취약):
```python
# ❌ 절대 사용 금지
user_input = request.args.get('line_code')
query = f"SELECT * FROM fact_daily_production WHERE line_code = '{user_input}'"
result = db.execute(query)
```

**Good Example** (Prepared Statement):
```python
# ✅ 권장
user_input = request.args.get('line_code')
query = "SELECT * FROM fact_daily_production WHERE line_code = %s"
result = db.execute(query, (user_input,))
```

**수락 기준**:
- [ ] 모든 SQL 쿼리 Prepared Statement 사용
- [ ] ORM 사용 권장
- [ ] SQL Injection 보안 스캔 통과 (OWASP ZAP)
- [ ] 코드 리뷰 시 SQL Injection 체크

**우선순위**: P0 (Critical)
**테스트 케이스**: C-3-TC-NFR-SEC-040-*

---

#### NFR-SEC-050: XSS 및 CSRF 방어

**요구사항 설명**:
- 웹 애플리케이션은 XSS(Cross-Site Scripting) 및 CSRF(Cross-Site Request Forgery) 공격을 방어해야 한다.

**상세 기준**:
- **XSS 방어**:
  - 사용자 입력 HTML 이스케이프
  - Content Security Policy (CSP) 헤더
  - HTTP Only 쿠키 (JavaScript 접근 금지)
- **CSRF 방어**:
  - CSRF 토큰 사용
  - SameSite 쿠키 속성
  - Referer 헤더 검증

**CSP 헤더 예시**:
```
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' https://api.factory-ai.com;
```

**CSRF 토큰 예시** (Flask):
```python
from flask_wtf.csrf import CSRFProtect

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
csrf = CSRFProtect(app)

@app.route('/workflow/create', methods=['POST'])
def create_workflow():
    # CSRF 토큰 자동 검증
    data = request.json
    # ... workflow 생성 로직
```

**수락 기준**:
- [ ] CSP 헤더 적용
- [ ] CSRF 토큰 검증
- [ ] XSS 보안 스캔 통과
- [ ] HTTP Only 쿠키 사용

**우선순위**: P1 (High)
**테스트 케이스**: C-3-TC-NFR-SEC-050-*

---

## 5. 감사 및 추적성 요구사항 (Auditability & Traceability)

### 5.1 개요
시스템은 모든 주요 변경 사항과 실행 이력을 추적하고, 규제 요구사항을 준수해야 한다.

### 5.2 버전 관리 및 추적

#### NFR-AUDIT-010: Rule/Prompt/모델 버전 추적

**요구사항 설명**:
- Rule, Prompt, LLM 모델의 버전을 함께 저장하여 재현 가능성을 보장해야 한다.

**상세 기준**:
- **버전 정보 저장**:
  - judgment_executions: ruleset_version, prompt_version, model_name
  - chat_messages: prompt_version, model_name
  - workflow_instances: workflow_version, dsl_hash
- **버전 명명 규칙**: Semantic Versioning (vMAJOR.MINOR.PATCH)
- **DSL 해시**: Workflow DSL 전체를 SHA-256 해시하여 저장
- **재현 가능성**: execution_id + versions → 동일 결과 재생산

**판단 실행 버전 추적 예시**:
```json
{
  "execution_id": "jud-123",
  "workflow_id": "wf-001",
  "workflow_version": "v1.5.2",
  "workflow_dsl_hash": "a1b2c3d4e5f6...",
  "ruleset_version": "v1.3.0",
  "rule_script_hash": "f6e5d4c3b2a1...",
  "prompt_version": "v2.1.0",
  "llm_model": "gpt-4-0613",
  "input_data": { ... },
  "result": { ... },
  "executed_at": "2025-11-26T16:00:00Z"
}
```

**수락 기준**:
- [ ] 모든 실행에 버전 정보 저장
- [ ] Semantic Versioning 준수
- [ ] DSL 해시로 변경 감지
- [ ] execution_id로 과거 실행 재현 가능

**우선순위**: P0 (Critical)
**테스트 케이스**: C-3-TC-NFR-AUDIT-010-*

---

#### NFR-AUDIT-020: 로그 보존 기간

**요구사항 설명**:
- 판단 로그, CCP 로그, LOT 추적 로그는 2년 이상 보존해야 한다.

**상세 기준**:
- **보존 대상**:
  - judgment_executions: 2년
  - workflow_instances: 2년
  - audit_logs: 2년
  - chat_messages: 1년
  - 시스템 로그: 90일
- **보존 방식**:
  - 핫 스토리지: 90일 (빠른 조회)
  - 콜드 스토리지: 90일~2년 (아카이브)
- **규제 준수**: HACCP, ISO 22000, GMP

**로그 보존 정책 예시**:
```sql
-- 90일 이후 데이터 콜드 스토리지 이동
INSERT INTO judgment_executions_archive
SELECT * FROM judgment_executions
WHERE executed_at < NOW() - INTERVAL '90 days';

DELETE FROM judgment_executions
WHERE executed_at < NOW() - INTERVAL '90 days';

-- 2년 이후 데이터 삭제
DELETE FROM judgment_executions_archive
WHERE executed_at < NOW() - INTERVAL '2 years';
```

**수락 기준**:
- [ ] 판단 로그 2년 보존
- [ ] 90일 후 자동 아카이빙
- [ ] 2년 후 자동 삭제
- [ ] 아카이브 데이터 조회 API

**우선순위**: P0 (Critical)
**테스트 케이스**: C-3-TC-NFR-AUDIT-020-*

---

#### NFR-AUDIT-030: 배포 및 롤백 이력

**요구사항 설명**:
- Rule, Prompt, Workflow의 배포 및 롤백 이력을 기록해야 한다.

**상세 기준**:
- **이력 항목**:
  - 배포 ID, 대상 (Rule/Prompt/Workflow)
  - 배포 전략 (Canary/Blue-Green/Rolling)
  - 구버전, 신버전
  - 배포 시각, 배포자
  - 롤백 여부, 롤백 시각, 롤백 사유
- **이력 조회**: 시간순, 대상별 필터링

**배포 이력 예시**:
```json
{
  "deployment_id": "deploy-123",
  "target_type": "ruleset",
  "target_id": "ruleset-456",
  "workflow_id": "wf-001",
  "strategy": "canary",
  "old_version": "v1.3.0",
  "new_version": "v1.4.0",
  "deployed_by": "user-admin",
  "deployed_at": "2025-11-26T16:00:00Z",
  "status": "completed",
  "rollback_occurred": false,
  "metrics": {
    "error_rate": 0.005,
    "latency_p95": 1200,
    "accuracy": 0.88
  }
}
```

**롤백 이력 예시**:
```json
{
  "deployment_id": "deploy-124",
  "target_type": "ruleset",
  "target_id": "ruleset-456",
  "workflow_id": "wf-001",
  "strategy": "canary",
  "old_version": "v1.4.0",
  "new_version": "v1.3.0",
  "deployed_by": "system_auto_rollback",
  "deployed_at": "2025-11-26T16:30:00Z",
  "status": "completed",
  "rollback_occurred": true,
  "rollback_reason": "error_rate_exceeded",
  "rollback_trigger": {
    "error_rate": 0.015,
    "threshold": 0.01
  }
}
```

**수락 기준**:
- [ ] 모든 배포 이력 기록
- [ ] 롤백 발생 시 이력 기록
- [ ] 배포/롤백 이력 조회 API
- [ ] 이력 기반 롤백 가능

**우선순위**: P1 (High)
**테스트 케이스**: C-3-TC-NFR-AUDIT-030-*

---

## 6. 국제화 및 현지화 요구사항 (I18N & L10N)

### 6.1 개요
시스템은 다국어 사용자를 지원하고, 지역별 날짜/시간 형식을 준수해야 한다.

### 6.2 다국어 지원

#### NFR-I18N-010: 응답 다국어 템플릿

**요구사항 설명**:
- 시스템 응답(에러 메시지, 알림, 설명)은 다국어 템플릿을 지원해야 한다.

**상세 기준**:
- **지원 언어**: ko (한국어), en (영어) 우선
- **확장 가능**: ja, zh, es, de 등 추가 가능
- **템플릿 관리**: JSON 파일 또는 DB 테이블
- **언어 선택**:
  - HTTP 헤더: `Accept-Language: ko-KR,en-US`
  - 사용자 프로필: user.preferred_language
- **폴백**: 지원하지 않는 언어 → 영어 (기본값)

**다국어 템플릿 예시**:
```json
{
  "judgment.high_defect.message": {
    "ko": "불량률이 임계값을 초과했습니다. 즉시 라인을 중단하세요.",
    "en": "Defect rate exceeded threshold. Stop the line immediately."
  },
  "workflow.approval_required.message": {
    "ko": "{approver}님의 승인이 필요합니다.",
    "en": "Approval from {approver} is required."
  },
  "error.invalid_input.message": {
    "ko": "입력 데이터가 유효하지 않습니다: {field}",
    "en": "Invalid input data: {field}"
  }
}
```

**다국어 응답 예시**:
```python
def get_message(key, lang='ko', **kwargs):
    messages = load_messages()
    template = messages.get(key, {}).get(lang, messages[key]['en'])
    return template.format(**kwargs)

# Usage
message = get_message('judgment.high_defect.message', lang='ko')
# → "불량률이 임계값을 초과했습니다. 즉시 라인을 중단하세요."

message = get_message('workflow.approval_required.message', lang='en', approver='John')
# → "Approval from John is required."
```

**수락 기준**:
- [ ] 한국어, 영어 템플릿 지원
- [ ] Accept-Language 헤더 인식
- [ ] 사용자 언어 설정 반영
- [ ] 지원하지 않는 언어 → 영어 폴백

**우선순위**: P2 (Medium)
**테스트 케이스**: C-3-TC-NFR-I18N-010-*

---

### 6.3 시간대 처리

#### NFR-I18N-020: UTC 저장 및 로컬 렌더링

**요구사항 설명**:
- 모든 타임스탬프는 UTC로 저장하고, 클라이언트에서 로컬 시간대로 렌더링해야 한다.

**상세 기준**:
- **저장**: UTC (ISO 8601 형식)
  - `2025-11-26T07:30:00Z` (Z = UTC)
- **렌더링**: 사용자 로컬 시간대
  - 한국: `2025-11-26 16:30:00 KST`
  - 미국 동부: `2025-11-26 02:30:00 EST`
- **시간대 설정**: 사용자 프로필 또는 브라우저 설정
- **API 응답**: UTC + 로컬 시간대 모두 제공 (선택적)

**API 응답 예시**:
```json
{
  "execution_id": "jud-123",
  "executed_at": "2025-11-26T07:30:00Z",
  "executed_at_local": "2025-11-26T16:30:00+09:00",
  "timezone": "Asia/Seoul"
}
```

**프론트엔드 렌더링** (JavaScript):
```javascript
// UTC 타임스탬프를 로컬 시간대로 변환
const utcTimestamp = '2025-11-26T07:30:00Z';
const localTimestamp = new Date(utcTimestamp).toLocaleString('ko-KR', {
  timeZone: 'Asia/Seoul',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit'
});
// → "2025-11-26 16:30:00"
```

**수락 기준**:
- [ ] 모든 타임스탬프 UTC 저장
- [ ] 사용자 시간대 설정 반영
- [ ] 프론트엔드 로컬 시간대 렌더링
- [ ] ISO 8601 형식 준수

**우선순위**: P1 (High)
**테스트 케이스**: C-3-TC-NFR-I18N-020-*

---

## 7. 품질 및 알람 요구사항 (Quality & Alerting)

### 7.1 개요
시스템은 데이터 품질, 스키마 변경, 충돌을 감지하고 알람을 발송해야 한다.

### 7.2 품질 모니터링

#### NFR-QUAL-010: Drift 및 충돌 감지 알람

**요구사항 설명**:
- 외부 데이터 소스 스키마 변경, Rule 충돌 발생 시 알람을 발행해야 한다.

**상세 기준**:
- **Drift 감지**: INT-FR-040 참조
  - 스키마 변경 감지 시 Slack/Email 알람
- **Rule 충돌 감지**:
  - 동일 조건에 여러 Rule 매치 시 경고
  - 모순되는 결과 (HIGH_DEFECT vs NORMAL) 감지
- **알람 채널**: Slack, Email, Webhook
- **알람 우선순위**: Critical, Warning, Info

**Drift 알람 예시** (Slack):
```
⚠️ Schema Drift Detected

Connector: ERP Database (conn-erp-001)
Table: production_orders

Changes:
- ➕ Column added: priority (VARCHAR(10))
- 🔄 Type changed: quantity (INTEGER → BIGINT)

Affected Workflows: wf-001, wf-003

[View Details] [Acknowledge]
```

**Rule 충돌 알람 예시** (Email):
```
Subject: Rule Conflict Detected in wf-001

Dear Admin,

A rule conflict has been detected in Workflow wf-001:

Conflicting Rules:
1. RULE_DEFECT_HIGH: status=HIGH_DEFECT, confidence=0.90
2. RULE_DEFECT_NORMAL: status=NORMAL, confidence=0.85

Input Data:
{
  "line_code": "LINE-A",
  "defect_count": 3,
  "production_count": 100
}

Action Required: Review and update rule conditions to prevent conflicts.

Best regards,
AI Factory System
```

**수락 기준**:
- [ ] Drift 감지 시 자동 알람
- [ ] Rule 충돌 감지 및 알람
- [ ] Slack/Email/Webhook 알람 발송
- [ ] 알람 우선순위 설정

**우선순위**: P1 (High)
**테스트 케이스**: C-3-TC-NFR-QUAL-010-*

---

#### NFR-QUAL-020: 재학습 및 승인 트리거

**요구사항 설명**:
- 품질 저하 감지 시 재학습 또는 승인 트리거를 연계해야 한다.

**상세 기준**:
- **품질 저하 조건**:
  - Judgment 정확도 < 80% (7일 평균)
  - 부정 피드백 비율 > 20%
  - Rule 적중률 < 50%
- **자동 트리거**:
  - 재학습 파이프라인 시작 (LRN-FR-030)
  - 도메인 전문가에게 리뷰 요청
  - 알람 발송 (Slack, Email)

**품질 저하 알람 예시**:
```
🚨 Quality Degradation Alert

Workflow: wf-001 (Defect Detection)

Metrics (Last 7 days):
- Judgment Accuracy: 75% (↓ from 90%)
- Negative Feedback: 25% (↑ from 10%)
- Rule Hit Rate: 45% (↓ from 70%)

Recommended Actions:
1. Review recent judgments with negative feedback
2. Analyze rule performance
3. Trigger re-learning pipeline

[View Dashboard] [Start Re-learning] [Acknowledge]
```

**수락 기준**:
- [ ] 품질 저하 조건 모니터링
- [ ] 조건 충족 시 자동 알람
- [ ] 재학습 파이프라인 트리거
- [ ] 전문가 리뷰 요청 워크플로우

**우선순위**: P2 (Medium)
**테스트 케이스**: C-3-TC-NFR-QUAL-020-*

---

#### NFR-QUAL-030: ETL 중단 트리거

**요구사항 설명**:
- 스키마 변경 감지 시 ETL 작업을 자동 중단하여 데이터 손상을 방지해야 한다.

**상세 기준**:
- **중단 조건**: Drift Detection 결과 Critical 변경 (컬럼 삭제, 타입 변경)
- **중단 범위**: 해당 커넥터 사용하는 모든 ETL 작업
- **알람 발송**: Slack, Email, Webhook
- **복구 절차**: 스키마 업데이트 후 수동 재시작

**ETL 중단 알람 예시**:
```
🛑 ETL Jobs Suspended

Reason: Critical schema change detected
Connector: ERP Database (conn-erp-001)
Table: production_orders

Critical Changes:
- ❌ Column deleted: order_date
- ⚠️ Type changed: quantity (INTEGER → VARCHAR)

Suspended ETL Jobs:
- etl-daily-production
- etl-order-summary

Action Required:
1. Update ETL mappings for schema changes
2. Test ETL jobs in staging environment
3. Resume ETL jobs manually

[View Drift Details] [Update ETL] [Resume Jobs]
```

**수락 기준**:
- [ ] Critical Drift 감지 시 ETL 자동 중단
- [ ] 중단 알람 발송
- [ ] 중단된 ETL 목록 표시
- [ ] 수동 재시작 API 제공

**우선순위**: P1 (High)
**테스트 케이스**: C-3-TC-NFR-QUAL-030-*

---

## 다음 파일로 계속

본 문서는 A-2-3로, 비기능 요구사항 (성능, 확장성, 가용성, 보안, 감사, 국제화, 품질)을 포함한다.

**다음 파일**:
- **A-2-4**: 데이터/인터페이스 요구사항 및 추적성 매트릭스

---

## 문서 이력
| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2025-11-26 | AI Factory Team | 초안 작성 |
