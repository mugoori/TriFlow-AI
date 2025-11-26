# D-2. Monitoring & Logging - Enhanced

## 문서 정보
- **문서 ID**: D-2
- **버전**: 2.0 (Enhanced)
- **최종 수정일**: 2025-11-26
- **상태**: Draft
- **관련 문서**:
  - A-2 System Requirements (OBS-FR-*)
  - C-4 Performance & Capacity
  - C-5 Security & Compliance
  - D-1 DevOps & Infrastructure

## 목차
1. [모니터링 개요](#1-모니터링-개요)
2. [메트릭 수집 (Prometheus)](#2-메트릭-수집-prometheus)
3. [로깅 (Loki/ELK)](#3-로깅-lokielk)
4. [분산 추적 (OpenTelemetry)](#4-분산-추적-opentelemetry)
5. [알람 (Alerting)](#5-알람-alerting)
6. [대시보드 (Grafana)](#6-대시보드-grafana)

---

## 1. 모니터링 개요

### 1.1 모니터링 목표

| 목표 | 설명 | 도구 |
|------|------|------|
| **서비스 상태 확인** | 각 서비스 정상 동작 여부 | Prometheus, Grafana |
| **성능 추적** | 응답 시간, 처리량, 에러율 | Prometheus, Grafana |
| **비즈니스 지표** | Judgment 정확도, 캐시 적중률 | Prometheus, Custom Metrics |
| **로그 분석** | 에러 로그, 감사 로그 검색 | Loki, Grafana |
| **분산 추적** | 요청 흐름, 병목 지점 파악 | OpenTelemetry, Jaeger |
| **알람 발송** | 이상 탐지 시 즉시 알람 | Alertmanager, Slack |

### 1.2 관찰 가능성 스택 (Observability Stack)

```
┌─────────────────────────────────────────────────────────┐
│                   Application Services                  │
│  (Judgment, Workflow, BI, Learning, MCP Hub, Chat)      │
└─────────────────────────────────────────────────────────┘
         │                  │                  │
         ▼ Metrics          ▼ Logs             ▼ Traces
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Prometheus   │  │    Loki      │  │OpenTelemetry │
│  (Metrics)   │  │  (Logs)      │  │ (Traces)     │
└──────────────┘  └──────────────┘  └──────────────┘
         │                  │                  │
         └──────────────────┼──────────────────┘
                            ▼
               ┌──────────────────────┐
               │       Grafana        │
               │ (통합 시각화 및 알람) │
               └──────────────────────┘
                            │
                            ▼
               ┌──────────────────────┐
               │    Alertmanager      │
               │ (알람 라우팅 및 발송) │
               └──────────────────────┘
                            │
                            ▼
               ┌──────────────────────┐
               │  Notification (Slack)│
               └──────────────────────┘
```

---

## 2. 메트릭 수집 (Prometheus)

### 2.1 메트릭 정의

#### 2.1.1 Judgment Service 메트릭

```python
from prometheus_client import Counter, Histogram, Gauge

# Counter: 실행 횟수
judgment_executions_total = Counter(
    'judgment_executions_total',
    'Total judgment executions',
    ['tenant_id', 'workflow_id', 'status', 'method']
)

# Histogram: 실행 시간
judgment_duration_seconds = Histogram(
    'judgment_duration_seconds',
    'Judgment execution duration in seconds',
    ['tenant_id', 'workflow_id', 'method'],
    buckets=[0.1, 0.3, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0]
)

# Counter: 캐시
judgment_cache_hits_total = Counter(
    'judgment_cache_hits_total',
    'Judgment cache hits',
    ['tenant_id', 'workflow_id']
)

judgment_cache_misses_total = Counter(
    'judgment_cache_misses_total',
    'Judgment cache misses',
    ['tenant_id', 'workflow_id']
)

# Counter: LLM 호출
llm_calls_total = Counter(
    'llm_calls_total',
    'LLM API calls',
    ['tenant_id', 'model', 'status']
)

# Counter: LLM 파싱 실패
llm_parsing_failures_total = Counter(
    'llm_parsing_failures_total',
    'LLM response parsing failures',
    ['tenant_id', 'model']
)

# Counter: LLM 비용
llm_cost_usd_total = Counter(
    'llm_cost_usd_total',
    'LLM cost in USD',
    ['tenant_id', 'model']
)

# Gauge: 활성 실행
judgment_active_executions = Gauge(
    'judgment_active_executions',
    'Active judgment executions',
    ['tenant_id']
)
```

#### 2.1.2 Workflow Service 메트릭

```python
# Counter: 인스턴스 수
workflow_instances_total = Counter(
    'workflow_instances_total',
    'Total workflow instances',
    ['tenant_id', 'workflow_id', 'status']
)

# Histogram: 실행 시간
workflow_duration_seconds = Histogram(
    'workflow_duration_seconds',
    'Workflow execution duration',
    ['tenant_id', 'workflow_id'],
    buckets=[1, 5, 10, 30, 60, 120, 300]
)

# Gauge: 활성 인스턴스
workflow_instances_active = Gauge(
    'workflow_instances_active',
    'Active workflow instances',
    ['tenant_id', 'workflow_id', 'status']
)

# Counter: 노드 실패
workflow_node_failures_total = Counter(
    'workflow_node_failures_total',
    'Workflow node failures',
    ['tenant_id', 'workflow_id', 'node_type']
)

# Counter: Circuit Breaker
circuit_breaker_state_changes_total = Counter(
    'circuit_breaker_state_changes_total',
    'Circuit breaker state changes',
    ['service', 'node_id', 'from_state', 'to_state']
)
```

### 2.2 Prometheus 설정

**prometheus.yml**:
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'factory-ai-production'
    region: 'us-east-1'

rule_files:
  - /etc/prometheus/rules/judgment.yml
  - /etc/prometheus/rules/workflow.yml
  - /etc/prometheus/rules/infrastructure.yml

scrape_configs:
  - job_name: 'judgment-service'
    kubernetes_sd_configs:
      - role: pod
        namespaces:
          names:
            - production
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app]
        action: keep
        regex: judgment-service
      - source_labels: [__meta_kubernetes_pod_name]
        target_label: pod
      - source_labels: [__meta_kubernetes_namespace]
        target_label: namespace

  - job_name: 'workflow-service'
    kubernetes_sd_configs:
      - role: pod
        namespaces:
          names:
            - production
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app]
        action: keep
        regex: workflow-service

  - job_name: 'postgres-exporter'
    static_configs:
      - targets: ['postgres-exporter:9187']

  - job_name: 'redis-exporter'
    static_configs:
      - targets: ['redis-exporter:9121']
```

---

## 3. 로깅 (Loki/ELK)

### 3.1 구조화 로그 (Structured Logging)

**로그 형식 (JSON)**:
```json
{
  "timestamp": "2025-11-26T16:30:15.123Z",
  "level": "INFO",
  "service": "judgment-service",
  "trace_id": "a1b2c3d4e5f6",
  "span_id": "span-123",
  "tenant_id": "tenant-456",
  "user_id": "user-789",
  "message": "Judgment execution completed",
  "execution_id": "jud-123",
  "workflow_id": "wf-001",
  "result_status": "HIGH_DEFECT",
  "confidence": 0.92,
  "execution_time_ms": 1250,
  "method_used": "hybrid_weighted"
}
```

**Python 로깅 설정**:
```python
import logging
import json
from pythonjsonlogger import jsonlogger

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record['service'] = 'judgment-service'
        log_record['trace_id'] = get_trace_id()  # 컨텍스트에서 조회
        log_record['tenant_id'] = get_tenant_id()

# 로거 설정
logger = logging.getLogger()
logHandler = logging.StreamHandler()
formatter = CustomJsonFormatter('%(timestamp)s %(level)s %(service)s %(message)s')
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

# 사용 예시
logger.info('Judgment execution completed', extra={
    'execution_id': 'jud-123',
    'workflow_id': 'wf-001',
    'confidence': 0.92
})
```

### 3.2 Loki 설정

**promtail.yml** (로그 수집):
```yaml
server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: kubernetes-pods
    kubernetes_sd_configs:
      - role: pod
    pipeline_stages:
      - docker: {}
      - json:
          expressions:
            level: level
            service: service
            trace_id: trace_id
            tenant_id: tenant_id
      - labels:
          level:
          service:
          tenant_id:
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app]
        target_label: app
      - source_labels: [__meta_kubernetes_namespace]
        target_label: namespace
```

---

## 4. 분산 추적 (OpenTelemetry)

### 4.1 OpenTelemetry 설정

**Python 계측**:
```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor

# Tracer Provider 설정
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

# OTLP Exporter (Jaeger)
otlp_exporter = OTLPSpanExporter(endpoint="http://jaeger:4317", insecure=True)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# FastAPI 자동 계측
FastAPIInstrumentor.instrument_app(app)

# SQLAlchemy 자동 계측
SQLAlchemyInstrumentor().instrument(engine=engine)

# Redis 자동 계측
RedisInstrumentor().instrument()

# 수동 Span 생성
@app.post("/api/v1/judgment/execute")
async def execute_judgment(request: JudgmentRequest):
    with tracer.start_as_current_span("judgment.execute") as span:
        span.set_attribute("workflow_id", request.workflow_id)
        span.set_attribute("policy", request.policy)

        # Rule 실행
        with tracer.start_as_current_span("judgment.rule_execution"):
            rule_result = await rule_engine.execute(request.input_data)

        # LLM 호출
        if should_call_llm(rule_result):
            with tracer.start_as_current_span("judgment.llm_call") as llm_span:
                llm_span.set_attribute("model", "gpt-4o")
                llm_result = await llm_client.call(request.input_data)

        # 결과 반환
        span.set_attribute("result.status", final_result['status'])
        span.set_attribute("result.confidence", final_result['confidence'])

        return final_result
```

---

## 5. 알람 (Alerting)

### 5.1 알람 규칙 (Prometheus Alert Rules)

**prometheus/rules/judgment.yml**:
```yaml
groups:
- name: judgment_alerts
  interval: 30s
  rules:
  # 높은 지연
  - alert: JudgmentHighLatency
    expr: histogram_quantile(0.95, judgment_duration_seconds) > 2.5
    for: 5m
    labels:
      severity: warning
      component: judgment
    annotations:
      summary: "Judgment P95 latency > 2.5s"
      description: "P95 latency is {{ $value }}s for workflow {{ $labels.workflow_id }}"
      runbook_url: "https://docs.factory-ai.com/runbooks/judgment-high-latency"

  # 높은 에러율
  - alert: JudgmentHighErrorRate
    expr: rate(judgment_executions_total{status="error"}[5m]) > 0.01
    for: 3m
    labels:
      severity: critical
      component: judgment
    annotations:
      summary: "Judgment error rate > 1%"
      description: "Error rate is {{ $value }} (threshold: 0.01)"

  # LLM 파싱 실패
  - alert: LLMParsingHighFailureRate
    expr: rate(llm_parsing_failures_total[5m]) > 0.005
    for: 3m
    labels:
      severity: warning
      component: llm
    annotations:
      summary: "LLM parsing failure rate > 0.5%"
      description: "Parsing failure rate is {{ $value }} for model {{ $labels.model }}"

  # 캐시 적중률 낮음
  - alert: JudgmentLowCacheHitRate
    expr: (
      rate(judgment_cache_hits_total[10m]) /
      (rate(judgment_cache_hits_total[10m]) + rate(judgment_cache_misses_total[10m]))
    ) < 0.3
    for: 10m
    labels:
      severity: warning
      component: cache
    annotations:
      summary: "Cache hit rate < 30%"
      description: "Cache hit rate is {{ $value }} (threshold: 0.30)"

  # LLM 비용 급증
  - alert: LLMCostBudgetExceeded
    expr: increase(llm_cost_usd_total[1d]) > 100
    labels:
      severity: warning
      component: llm
    annotations:
      summary: "Daily LLM cost > $100"
      description: "Daily cost is ${{ $value }} (budget: $100)"
```

### 5.2 Alertmanager 설정

**alertmanager.yml**:
```yaml
global:
  resolve_timeout: 5m
  slack_api_url: 'https://hooks.slack.com/services/...'

route:
  receiver: 'default'
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 10s
  group_interval: 5m
  repeat_interval: 4h

  routes:
  # Critical 알람 → PagerDuty (즉시)
  - match:
      severity: critical
    receiver: 'pagerduty'
    repeat_interval: 5m

  # Warning 알람 → Slack (5분 그룹화)
  - match:
      severity: warning
    receiver: 'slack-warnings'
    repeat_interval: 30m

receivers:
  - name: 'default'
    slack_configs:
      - channel: '#factory-ai-alerts'
        title: '{{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'

  - name: 'pagerduty'
    pagerduty_configs:
      - service_key: '{{pagerduty_service_key}}'
        description: '{{ .GroupLabels.alertname }}: {{ .CommonAnnotations.summary }}'

  - name: 'slack-warnings'
    slack_configs:
      - channel: '#factory-ai-warnings'
        title: '⚠️ Warning: {{ .GroupLabels.alertname }}'
        text: '{{ .CommonAnnotations.description }}'
```

---

## 6. 대시보드 (Grafana)

### 6.1 Judgment Performance Dashboard

**패널 구성**:

#### Panel 1: Requests Per Second
```promql
rate(judgment_executions_total[5m])
```

#### Panel 2: Latency (P50, P95, P99)
```promql
histogram_quantile(0.50, rate(judgment_duration_seconds_bucket[5m]))
histogram_quantile(0.95, rate(judgment_duration_seconds_bucket[5m]))
histogram_quantile(0.99, rate(judgment_duration_seconds_bucket[5m]))
```

#### Panel 3: Error Rate
```promql
rate(judgment_executions_total{status="error"}[5m])
```

#### Panel 4: Cache Hit Rate
```promql
rate(judgment_cache_hits_total[5m]) /
(rate(judgment_cache_hits_total[5m]) + rate(judgment_cache_misses_total[5m]))
```

#### Panel 5: Method Distribution (Pie Chart)
```promql
sum by (method) (judgment_executions_total)
```

#### Panel 6: LLM Cost (Daily)
```promql
increase(llm_cost_usd_total[1d])
```

**JSON Dashboard Export**:
```json
{
  "dashboard": {
    "title": "Judgment Service Performance",
    "panels": [
      {
        "title": "Requests Per Second",
        "targets": [
          {
            "expr": "rate(judgment_executions_total[5m])",
            "legendFormat": "RPS"
          }
        ],
        "type": "graph"
      },
      {
        "title": "Latency (P50, P95, P99)",
        "targets": [
          {
            "expr": "histogram_quantile(0.50, rate(judgment_duration_seconds_bucket[5m]))",
            "legendFormat": "P50"
          },
          {
            "expr": "histogram_quantile(0.95, rate(judgment_duration_seconds_bucket[5m]))",
            "legendFormat": "P95"
          },
          {
            "expr": "histogram_quantile(0.99, rate(judgment_duration_seconds_bucket[5m]))",
            "legendFormat": "P99"
          }
        ],
        "type": "graph"
      }
    ]
  }
}
```

---

## 결론

본 문서(D-2)는 **AI Factory Decision Engine** 의 모니터링 및 로깅 전략을 상세히 수립하였다.

### 주요 성과
1. **메트릭 정의**: Judgment, Workflow, BI, LLM, Cache, Infrastructure (30+ 메트릭)
2. **Prometheus 설정**: Scrape Config, Alert Rules
3. **Loki 로깅**: 구조화 로그 (JSON), Promtail 수집
4. **OpenTelemetry**: 분산 추적, Span 계측
5. **알람**: 6가지 주요 알람 규칙, Alertmanager 라우팅
6. **Grafana 대시보드**: Judgment Performance, Workflow Status, BI Analytics

### 다음 단계
1. Prometheus, Grafana, Loki 설치 (Helm)
2. 대시보드 생성 및 테스트
3. 알람 규칙 검증 (장애 주입 테스트)
4. On-call 프로세스 수립

---

## 문서 이력
| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2025-11-03 | DevOps Team | 초안 작성 |
| 2.0 | 2025-11-26 | DevOps Team | Enhanced 버전 (메트릭, 알람 규칙, 대시보드 상세 추가) |
