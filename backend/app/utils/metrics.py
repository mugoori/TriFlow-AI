# ===================================================
# TriFlow AI - Prometheus Custom Metrics
# HTTP, Agent, Token, DB, Cache Metrics
# ===================================================

from prometheus_client import Counter, Histogram, Gauge, Summary

# ========== HTTP Request Metrics ==========

# 총 HTTP 요청 수
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"]
)

# HTTP 요청 응답 시간
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# 활성 연결 수
http_active_connections = Gauge(
    "http_active_connections",
    "Current number of active HTTP connections"
)

# 요청 크기
http_request_size_bytes = Summary(
    "http_request_size_bytes",
    "HTTP request body size in bytes",
    ["method", "endpoint"]
)

# 응답 크기
http_response_size_bytes = Summary(
    "http_response_size_bytes",
    "HTTP response body size in bytes",
    ["method", "endpoint"]
)


# ========== Agent Metrics ==========

# 에이전트 호출 수
agent_calls_total = Counter(
    "agent_calls_total",
    "Total agent API calls",
    ["agent_type", "status"]  # agent_type: meta_router, judgment, workflow, bi, learning
)

# 에이전트 응답 시간
agent_response_duration_seconds = Histogram(
    "agent_response_duration_seconds",
    "Agent response duration in seconds",
    ["agent_type"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0]
)


# ========== LLM Token Metrics (User Request) ==========

# LLM API 호출 수
llm_calls_total = Counter(
    "llm_calls_total",
    "Total LLM API calls",
    ["model", "agent_type", "status"]
)

# Input 토큰 수
llm_input_tokens_total = Counter(
    "llm_input_tokens_total",
    "Total LLM input tokens consumed",
    ["model", "agent_type"]
)

# Output 토큰 수
llm_output_tokens_total = Counter(
    "llm_output_tokens_total",
    "Total LLM output tokens generated",
    ["model", "agent_type"]
)

# 토큰 비용 추정 (USD)
llm_cost_usd_total = Counter(
    "llm_cost_usd_total",
    "Estimated LLM API cost in USD",
    ["model"]
)

# LLM 응답 시간
llm_response_duration_seconds = Histogram(
    "llm_response_duration_seconds",
    "LLM API response duration in seconds",
    ["model"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)


# ========== Database Metrics ==========

# DB 쿼리 수
db_queries_total = Counter(
    "db_queries_total",
    "Total database queries",
    ["operation", "table"]  # operation: select, insert, update, delete
)

# DB 쿼리 응답 시간
db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["operation"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
)

# DB 연결 풀 상태
db_pool_size = Gauge(
    "db_pool_size",
    "Current database connection pool size"
)

db_pool_checked_in = Gauge(
    "db_pool_checked_in",
    "Database connections checked in (available)"
)

db_pool_checked_out = Gauge(
    "db_pool_checked_out",
    "Database connections checked out (in use)"
)


# ========== Cache (Redis) Metrics ==========

# 캐시 히트/미스
cache_hits_total = Counter(
    "cache_hits_total",
    "Total cache hits",
    ["operation"]
)

cache_misses_total = Counter(
    "cache_misses_total",
    "Total cache misses",
    ["operation"]
)

# 캐시 응답 시간
cache_operation_duration_seconds = Histogram(
    "cache_operation_duration_seconds",
    "Cache operation duration in seconds",
    ["operation"],
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1]
)


# ========== Authentication Metrics ==========

# 로그인 시도
auth_login_attempts_total = Counter(
    "auth_login_attempts_total",
    "Total login attempts",
    ["status", "method"]  # status: success, failure; method: jwt, api_key
)

# API Key 사용량
api_key_usage_total = Counter(
    "api_key_usage_total",
    "Total API key usage",
    ["scope", "status"]
)


# ========== Business Metrics ==========

# 센서 데이터 수집
sensor_data_collected_total = Counter(
    "sensor_data_collected_total",
    "Total sensor data points collected",
    ["sensor_type"]
)

# 워크플로우 실행
workflow_executions_total = Counter(
    "workflow_executions_total",
    "Total workflow executions",
    ["workflow_id", "status"]
)

# 룰셋 평가
ruleset_evaluations_total = Counter(
    "ruleset_evaluations_total",
    "Total ruleset evaluations",
    ["ruleset_id", "result"]  # result: triggered, not_triggered, error
)


# ========== Helper Functions ==========

# Claude Sonnet 토큰 가격 (USD, 2024년 기준)
LLM_PRICING = {
    "claude-sonnet-4-5-20250929": {
        "input": 0.003 / 1000,   # $3 per 1M tokens
        "output": 0.015 / 1000,  # $15 per 1M tokens
    },
    "claude-3-5-sonnet-20241022": {
        "input": 0.003 / 1000,
        "output": 0.015 / 1000,
    },
    "claude-3-haiku-20240307": {
        "input": 0.00025 / 1000,
        "output": 0.00125 / 1000,
    },
}


def record_llm_usage(
    model: str,
    agent_type: str,
    input_tokens: int,
    output_tokens: int,
    duration_seconds: float,
    status: str = "success"
):
    """
    LLM 사용량 메트릭 기록

    Args:
        model: 모델 이름 (예: claude-sonnet-4-5-20250929)
        agent_type: 에이전트 타입 (예: meta_router, judgment)
        input_tokens: 입력 토큰 수
        output_tokens: 출력 토큰 수
        duration_seconds: 응답 시간 (초)
        status: 상태 (success, error)
    """
    # 호출 수
    llm_calls_total.labels(model=model, agent_type=agent_type, status=status).inc()

    # 토큰 수
    llm_input_tokens_total.labels(model=model, agent_type=agent_type).inc(input_tokens)
    llm_output_tokens_total.labels(model=model, agent_type=agent_type).inc(output_tokens)

    # 비용 계산
    pricing = LLM_PRICING.get(model, LLM_PRICING["claude-sonnet-4-5-20250929"])
    cost = (input_tokens * pricing["input"]) + (output_tokens * pricing["output"])
    llm_cost_usd_total.labels(model=model).inc(cost)

    # 응답 시간
    llm_response_duration_seconds.labels(model=model).observe(duration_seconds)


def record_agent_call(agent_type: str, status: str, duration_seconds: float):
    """
    에이전트 호출 메트릭 기록

    Args:
        agent_type: 에이전트 타입
        status: 상태 (success, error)
        duration_seconds: 응답 시간 (초)
    """
    agent_calls_total.labels(agent_type=agent_type, status=status).inc()
    agent_response_duration_seconds.labels(agent_type=agent_type).observe(duration_seconds)
