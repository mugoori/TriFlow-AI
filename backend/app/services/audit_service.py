"""
Audit Log 서비스
API 호출 기록 및 조회
"""
import json
import logging
import re
from datetime import datetime
from typing import Optional, List, Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# 민감 정보 마스킹 패턴
SENSITIVE_FIELDS = [
    "password", "password_hash", "token", "access_token", "refresh_token",
    "secret", "api_key", "authorization", "credit_card", "ssn",
]


def mask_sensitive_data(data: Any, depth: int = 0) -> Any:
    """
    민감 정보 마스킹

    Args:
        data: 마스킹할 데이터
        depth: 재귀 깊이 (무한 루프 방지)

    Returns:
        마스킹된 데이터
    """
    if depth > 10:
        return "[TRUNCATED]"

    if isinstance(data, dict):
        masked = {}
        for key, value in data.items():
            lower_key = key.lower()
            if any(field in lower_key for field in SENSITIVE_FIELDS):
                masked[key] = "***MASKED***"
            else:
                masked[key] = mask_sensitive_data(value, depth + 1)
        return masked
    elif isinstance(data, list):
        return [mask_sensitive_data(item, depth + 1) for item in data[:100]]  # 최대 100개
    elif isinstance(data, str) and len(data) > 1000:
        return data[:500] + "...[TRUNCATED]..."
    else:
        return data


def extract_resource_from_path(path: str) -> tuple[str, Optional[str]]:
    """
    API 경로에서 리소스 타입과 ID 추출

    Args:
        path: API 경로 (예: /api/v1/workflows/123)

    Returns:
        (리소스 타입, 리소스 ID) 튜플
    """
    # /api/v1/{resource}/{id} 패턴 매칭
    pattern = r"/api/v1/([^/]+)(?:/([^/]+))?"
    match = re.match(pattern, path)

    if match:
        resource = match.group(1)
        resource_id = match.group(2) if match.lastindex >= 2 else None
        return resource, resource_id

    return "unknown", None


def method_to_action(method: str, path: str) -> str:
    """
    HTTP 메서드를 액션으로 변환

    Args:
        method: HTTP 메서드
        path: API 경로

    Returns:
        액션 문자열
    """
    method_actions = {
        "GET": "read",
        "POST": "create",
        "PUT": "update",
        "PATCH": "update",
        "DELETE": "delete",
    }

    action = method_actions.get(method.upper(), "unknown")

    # 특수 경로 처리
    if "/login" in path:
        return "login"
    elif "/logout" in path:
        return "logout"
    elif "/execute" in path or "/run" in path:
        return "execute"
    elif "/test" in path:
        return "test"

    return action


async def create_audit_log(
    db: Session,
    user_id: Optional[UUID],
    tenant_id: Optional[UUID],
    action: str,
    resource: str,
    resource_id: Optional[str],
    method: str,
    path: str,
    status_code: int,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    request_body: Optional[dict] = None,
    response_summary: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> Optional[UUID]:
    """
    감사 로그 생성

    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        tenant_id: 테넌트 ID
        action: 액션 (create, read, update, delete, login 등)
        resource: 리소스 타입
        resource_id: 리소스 ID
        method: HTTP 메서드
        path: API 경로
        status_code: HTTP 상태 코드
        ip_address: 클라이언트 IP
        user_agent: User-Agent
        request_body: 요청 본문 (마스킹됨)
        response_summary: 응답 요약
        duration_ms: 처리 시간

    Returns:
        생성된 로그 ID
    """
    try:
        log_id = uuid4()

        # 민감 정보 마스킹
        masked_body = mask_sensitive_data(request_body) if request_body else None

        query = text("""
            INSERT INTO audit.audit_logs (
                log_id, user_id, tenant_id, action, resource, resource_type, resource_id,
                method, path, status_code, ip_address, user_agent,
                request_body, response_summary, duration_ms, created_at
            ) VALUES (
                :log_id, :user_id, :tenant_id, :action, :resource, :resource_type, :resource_id,
                :method, :path, :status_code, :ip_address, :user_agent,
                :request_body, :response_summary, :duration_ms, :created_at
            )
        """)

        db.execute(query, {
            "log_id": log_id,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "action": action,
            "resource": resource,
            "resource_type": resource,  # resource_type에도 동일한 값 사용
            "resource_id": resource_id,
            "method": method,
            "path": path[:500],  # 경로 길이 제한
            "status_code": status_code,
            "ip_address": ip_address,
            "user_agent": user_agent[:500] if user_agent else None,
            "request_body": json.dumps(masked_body) if masked_body else None,
            "response_summary": response_summary[:500] if response_summary else None,
            "duration_ms": duration_ms,
            "created_at": datetime.utcnow(),
        })
        db.commit()

        return log_id

    except Exception as e:
        logger.error(f"Failed to create audit log: {e}")
        db.rollback()
        return None


async def get_audit_logs(
    db: Session,
    user_id: Optional[UUID] = None,
    tenant_id: Optional[UUID] = None,
    resource: Optional[str] = None,
    action: Optional[str] = None,
    status_code: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[dict]:
    """
    감사 로그 조회

    Args:
        db: 데이터베이스 세션
        user_id: 필터 - 사용자 ID
        tenant_id: 필터 - 테넌트 ID
        resource: 필터 - 리소스 타입
        action: 필터 - 액션
        status_code: 필터 - HTTP 상태 코드
        start_date: 필터 - 시작 일시
        end_date: 필터 - 종료 일시
        limit: 최대 결과 수
        offset: 시작 위치

    Returns:
        감사 로그 목록
    """
    try:
        conditions = ["1=1"]
        params = {"limit": limit, "offset": offset}

        if user_id:
            conditions.append("user_id = :user_id")
            params["user_id"] = user_id

        if tenant_id:
            conditions.append("tenant_id = :tenant_id")
            params["tenant_id"] = tenant_id

        if resource:
            conditions.append("resource = :resource")
            params["resource"] = resource

        if action:
            conditions.append("action = :action")
            params["action"] = action

        if status_code:
            conditions.append("status_code = :status_code")
            params["status_code"] = status_code

        if start_date:
            conditions.append("created_at >= :start_date")
            params["start_date"] = start_date

        if end_date:
            conditions.append("created_at <= :end_date")
            params["end_date"] = end_date

        where_clause = " AND ".join(conditions)

        query = text(f"""
            SELECT
                log_id, user_id, tenant_id, action, resource, resource_id,
                method, path, status_code, ip_address, user_agent,
                request_body, response_summary, duration_ms, created_at
            FROM audit.audit_logs
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """)

        result = db.execute(query, params)
        rows = result.fetchall()

        return [
            {
                "log_id": str(row[0]),
                "user_id": str(row[1]) if row[1] else None,
                "tenant_id": str(row[2]) if row[2] else None,
                "action": row[3],
                "resource": row[4],
                "resource_id": row[5],
                "method": row[6],
                "path": row[7],
                "status_code": row[8],
                "ip_address": row[9],
                "user_agent": row[10],
                "request_body": row[11],
                "response_summary": row[12],
                "duration_ms": row[13],
                "created_at": row[14].isoformat() if row[14] else None,
            }
            for row in rows
        ]

    except Exception as e:
        logger.error(f"Failed to get audit logs: {e}")
        return []


async def get_audit_stats(
    db: Session,
    tenant_id: Optional[UUID] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> dict:
    """
    감사 로그 통계 조회

    Args:
        db: 데이터베이스 세션
        tenant_id: 필터 - 테넌트 ID
        start_date: 필터 - 시작 일시
        end_date: 필터 - 종료 일시

    Returns:
        통계 정보
    """
    try:
        conditions = ["1=1"]
        params = {}

        if tenant_id:
            conditions.append("tenant_id = :tenant_id")
            params["tenant_id"] = tenant_id

        if start_date:
            conditions.append("created_at >= :start_date")
            params["start_date"] = start_date

        if end_date:
            conditions.append("created_at <= :end_date")
            params["end_date"] = end_date

        where_clause = " AND ".join(conditions)

        # 전체 통계
        total_query = text(f"""
            SELECT COUNT(*) FROM audit.audit_logs WHERE {where_clause}
        """)
        total = db.execute(total_query, params).scalar()

        # 리소스별 통계
        resource_query = text(f"""
            SELECT resource, COUNT(*) as count
            FROM audit.audit_logs
            WHERE {where_clause}
            GROUP BY resource
            ORDER BY count DESC
        """)
        resource_result = db.execute(resource_query, params)
        by_resource = {row[0]: row[1] for row in resource_result.fetchall()}

        # 액션별 통계
        action_query = text(f"""
            SELECT action, COUNT(*) as count
            FROM audit.audit_logs
            WHERE {where_clause}
            GROUP BY action
            ORDER BY count DESC
        """)
        action_result = db.execute(action_query, params)
        by_action = {row[0]: row[1] for row in action_result.fetchall()}

        # 상태 코드별 통계
        status_query = text(f"""
            SELECT
                CASE
                    WHEN status_code >= 200 AND status_code < 300 THEN 'success'
                    WHEN status_code >= 400 AND status_code < 500 THEN 'client_error'
                    WHEN status_code >= 500 THEN 'server_error'
                    ELSE 'other'
                END as status_group,
                COUNT(*) as count
            FROM audit.audit_logs
            WHERE {where_clause}
            GROUP BY status_group
        """)
        status_result = db.execute(status_query, params)
        by_status = {row[0]: row[1] for row in status_result.fetchall()}

        return {
            "total": total,
            "by_resource": by_resource,
            "by_action": by_action,
            "by_status": by_status,
        }

    except Exception as e:
        logger.error(f"Failed to get audit stats: {e}")
        return {"total": 0, "by_resource": {}, "by_action": {}, "by_status": {}}
