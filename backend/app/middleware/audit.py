"""
Audit Log 미들웨어
모든 API 요청을 자동으로 기록
"""
import logging
import time
from typing import Callable, Optional
from uuid import UUID

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.database import SessionLocal
from app.services.audit_service import (
    create_audit_log,
    extract_resource_from_path,
    method_to_action,
)
from app.auth.jwt import decode_token

logger = logging.getLogger(__name__)

# 감사 로그에서 제외할 경로
EXCLUDED_PATHS = [
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/favicon.ico",
    "/api/v1/audit",  # 무한 루프 방지
    "/api/v1/auth/",  # 인증 경로는 별도 로깅 (본문 읽기 충돌 방지)
    "/api/v1/agents/",  # 에이전트 API는 처리 시간이 길어서 제외
]

# 로그 기록할 경로 패턴
AUDIT_PATH_PREFIXES = [
    "/api/v1/",
]


def should_audit(path: str) -> bool:
    """
    경로가 감사 대상인지 확인

    Args:
        path: API 경로

    Returns:
        감사 대상 여부
    """
    # 제외 경로 체크
    for excluded in EXCLUDED_PATHS:
        if path.startswith(excluded):
            return False

    # 감사 대상 경로 체크
    for prefix in AUDIT_PATH_PREFIXES:
        if path.startswith(prefix):
            return True

    return False


def get_client_ip(request: Request) -> Optional[str]:
    """
    클라이언트 IP 추출

    Args:
        request: FastAPI Request 객체

    Returns:
        클라이언트 IP
    """
    # X-Forwarded-For 헤더 확인 (프록시/로드밸런서 뒤에서)
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    # X-Real-IP 헤더 확인
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip

    # 직접 연결된 클라이언트 IP
    if request.client:
        return request.client.host

    return None


def extract_user_info(request: Request) -> tuple[Optional[UUID], Optional[UUID]]:
    """
    요청에서 사용자 정보 추출

    Args:
        request: FastAPI Request 객체

    Returns:
        (user_id, tenant_id) 튜플
    """
    auth_header = request.headers.get("authorization", "")

    if not auth_header.startswith("Bearer "):
        return None, None

    token = auth_header[7:]  # "Bearer " 제거
    payload = decode_token(token)

    if not payload:
        return None, None

    user_id = payload.get("sub")
    tenant_id = payload.get("tenant_id")

    try:
        user_uuid = UUID(user_id) if user_id else None
        tenant_uuid = UUID(tenant_id) if tenant_id else None
        return user_uuid, tenant_uuid
    except (ValueError, TypeError):
        return None, None


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Audit Log 미들웨어

    모든 API 요청을 자동으로 감사 로그에 기록
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        요청 처리 및 감사 로그 기록

        Args:
            request: 들어온 요청
            call_next: 다음 미들웨어/핸들러

        Returns:
            응답
        """
        path = request.url.path

        # 감사 대상이 아니면 바로 통과
        if not should_audit(path):
            return await call_next(request)

        # 요청 정보 추출
        start_time = time.time()
        method = request.method
        user_agent = request.headers.get("user-agent")
        ip_address = get_client_ip(request)
        user_id, tenant_id = extract_user_info(request)

        # 요청 본문 읽기 비활성화
        # BaseHTTPMiddleware에서 request.body()를 읽으면 body가 소비되어
        # 후속 endpoint에서 body를 읽을 수 없는 문제가 발생함
        # 감사 로그에는 본문 없이 기록
        request_body = None

        # 응답 처리
        response = await call_next(request)

        # 처리 시간 계산
        duration_ms = int((time.time() - start_time) * 1000)

        # 리소스 및 액션 추출
        resource, resource_id = extract_resource_from_path(path)
        action = method_to_action(method, path)

        # 응답 요약 생성
        response_summary = f"HTTP {response.status_code}"

        # 비동기로 감사 로그 기록 (응답 지연 최소화)
        try:
            db = SessionLocal()
            try:
                await create_audit_log(
                    db=db,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    action=action,
                    resource=resource,
                    resource_id=resource_id,
                    method=method,
                    path=path,
                    status_code=response.status_code,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    request_body=request_body,
                    response_summary=response_summary,
                    duration_ms=duration_ms,
                )
            finally:
                db.close()
        except Exception as e:
            # 감사 로그 실패가 응답에 영향을 주지 않도록
            logger.error(f"Audit log failed: {e}")

        return response
