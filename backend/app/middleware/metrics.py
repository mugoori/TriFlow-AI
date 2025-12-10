# ===================================================
# TriFlow AI - Metrics Collection Middleware
# Prometheus 메트릭 자동 수집
# ===================================================

import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.utils.metrics import (
    http_requests_total,
    http_request_duration_seconds,
    http_active_connections,
    http_request_size_bytes,
    http_response_size_bytes,
)


# 메트릭 수집 제외 경로
EXCLUDE_PATHS = {
    "/metrics",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
}


def _normalize_endpoint(path: str) -> str:
    """
    엔드포인트 정규화 (카디널리티 제어)

    UUID, 숫자 ID 등을 플레이스홀더로 변환하여
    메트릭 레이블의 카디널리티를 줄임

    예: /api/v1/sensors/123 -> /api/v1/sensors/{id}
    """
    parts = path.split("/")
    normalized = []

    for part in parts:
        if not part:
            continue

        # UUID 패턴 (8-4-4-4-12)
        if len(part) == 36 and part.count("-") == 4:
            normalized.append("{id}")
        # 숫자 ID
        elif part.isdigit():
            normalized.append("{id}")
        else:
            normalized.append(part)

    return "/" + "/".join(normalized) if normalized else "/"


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    HTTP 요청/응답 메트릭 수집 미들웨어

    수집 항목:
    - 요청 수 (method, endpoint, status_code)
    - 응답 시간 (method, endpoint)
    - 활성 연결 수
    - 요청/응답 크기
    """

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        # 제외 경로 확인
        path = request.url.path
        if path in EXCLUDE_PATHS or path.startswith("/metrics"):
            return await call_next(request)

        # 엔드포인트 정규화
        endpoint = _normalize_endpoint(path)
        method = request.method

        # 활성 연결 수 증가
        http_active_connections.inc()

        # 요청 크기 기록
        content_length = request.headers.get("content-length")
        if content_length:
            http_request_size_bytes.labels(
                method=method, endpoint=endpoint
            ).observe(int(content_length))

        # 시작 시간
        start_time = time.perf_counter()

        try:
            # 요청 처리
            response = await call_next(request)

            # 응답 시간 기록
            duration = time.perf_counter() - start_time
            http_request_duration_seconds.labels(
                method=method, endpoint=endpoint
            ).observe(duration)

            # 요청 수 기록
            status_code = str(response.status_code)
            http_requests_total.labels(
                method=method, endpoint=endpoint, status_code=status_code
            ).inc()

            # 응답 크기 기록
            response_size = response.headers.get("content-length")
            if response_size:
                http_response_size_bytes.labels(
                    method=method, endpoint=endpoint
                ).observe(int(response_size))

            return response

        except Exception as exc:
            # 에러 발생 시에도 메트릭 기록
            duration = time.perf_counter() - start_time
            http_request_duration_seconds.labels(
                method=method, endpoint=endpoint
            ).observe(duration)

            http_requests_total.labels(
                method=method, endpoint=endpoint, status_code="500"
            ).inc()

            raise exc

        finally:
            # 활성 연결 수 감소
            http_active_connections.dec()
