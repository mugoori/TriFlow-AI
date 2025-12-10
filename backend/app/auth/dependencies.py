"""
FastAPI 인증 의존성
Depends(get_current_user) 형태로 사용
JWT Bearer 토큰 또는 API Key 인증 지원
"""
from typing import Optional, List, Callable
from uuid import UUID

from fastapi import Depends, HTTPException, status, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from .jwt import decode_token

# Bearer 토큰 스키마
security = HTTPBearer(auto_error=False)

# API Key 접두사
API_KEY_PREFIX = "tfk_"


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    request: Request = None,
    db: Session = Depends(get_db),
) -> User:
    """
    현재 인증된 사용자 조회

    지원하는 인증 방식:
    1. Bearer 토큰 (JWT) - Authorization: Bearer <token>
    2. API Key - X-API-Key: tfk_xxxxx

    Args:
        credentials: Bearer 토큰
        x_api_key: API Key 헤더
        request: FastAPI Request (클라이언트 IP 추출용)
        db: 데이터베이스 세션

    Returns:
        User 객체

    Raises:
        HTTPException 401: 인증 실패
    """
    # API Key 인증 시도
    if x_api_key and x_api_key.startswith(API_KEY_PREFIX):
        return await _authenticate_with_api_key(x_api_key, request, db)

    # Bearer 토큰 인증 시도
    if credentials:
        token = credentials.credentials
        # API Key가 Bearer로 전달된 경우
        if token.startswith(API_KEY_PREFIX):
            return await _authenticate_with_api_key(token, request, db)
        # JWT 토큰 인증
        return await _authenticate_with_jwt(token, db)

    # 인증 정보 없음
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def _authenticate_with_jwt(token: str, db: Session) -> User:
    """JWT 토큰으로 인증"""
    # 토큰 디코딩
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 토큰 타입 검증 (access token만 허용)
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 사용자 ID 추출
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # DB에서 사용자 조회
    try:
        user = db.query(User).filter(User.user_id == UUID(user_id)).first()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def _authenticate_with_api_key(api_key: str, request: Request, db: Session) -> User:
    """API Key로 인증"""
    from app.services.api_key_service import validate_api_key

    # 클라이언트 IP 추출
    client_ip = None
    if request:
        client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if not client_ip:
            client_ip = request.client.host if request.client else None

    # API Key 검증
    api_key_obj = validate_api_key(db=db, api_key=api_key, client_ip=client_ip)

    if not api_key_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # API Key 소유자 조회
    user = db.query(User).filter(User.user_id == api_key_obj.user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key owner not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    현재 활성 사용자 조회 (비활성 사용자 제외)

    Args:
        current_user: 인증된 사용자

    Returns:
        활성 User 객체

    Raises:
        HTTPException 403: 비활성 사용자
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return current_user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    request: Request = None,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    선택적 사용자 인증 (인증 없이도 접근 가능하지만, 인증 시 사용자 정보 제공)

    Args:
        credentials: Bearer 토큰 (선택)
        x_api_key: API Key 헤더 (선택)
        request: FastAPI Request
        db: 데이터베이스 세션

    Returns:
        User 객체 또는 None
    """
    if not credentials and not x_api_key:
        return None

    try:
        return await get_current_user(credentials, x_api_key, request, db)
    except HTTPException:
        return None


async def require_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    관리자 권한 확인

    Args:
        current_user: 인증된 활성 사용자

    Returns:
        관리자 User 객체

    Raises:
        HTTPException 403: 관리자 권한 없음
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )

    return current_user


# ========== API Key 스코프 검증 ==========

# 유효한 스코프 목록
VALID_SCOPES = {
    "read",       # 데이터 조회
    "write",      # 데이터 생성/수정
    "delete",     # 데이터 삭제
    "admin",      # 모든 권한 (관리자용)
    "sensors",    # 센서 데이터
    "workflows",  # 워크플로우
    "rulesets",   # 룰셋
    "erp_mes",    # ERP/MES 데이터
    "notifications",  # 알림 전송
}


def require_scope(required_scopes: List[str]) -> Callable:
    """
    API Key 스코프 검증 의존성 팩토리

    사용법:
        @router.get("/sensors")
        async def list_sensors(
            user: User = Depends(require_scope(["read", "sensors"]))
        ):
            ...

    Args:
        required_scopes: 필요한 스코프 목록 (모두 충족해야 함)

    Returns:
        FastAPI Dependency 함수
    """
    async def scope_checker(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        request: Request = None,
        db: Session = Depends(get_db),
    ) -> User:
        """스코프 검증 의존성"""
        # API Key 추출
        api_key = None
        if x_api_key and x_api_key.startswith(API_KEY_PREFIX):
            api_key = x_api_key
        elif credentials and credentials.credentials.startswith(API_KEY_PREFIX):
            api_key = credentials.credentials

        # API Key 인증인 경우 스코프 검증
        if api_key:
            from app.services.api_key_service import validate_api_key

            # 클라이언트 IP 추출
            client_ip = None
            if request:
                client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                if not client_ip:
                    client_ip = request.client.host if request.client else None

            # API Key 검증 (스코프 포함)
            api_key_obj = validate_api_key(
                db=db,
                api_key=api_key,
                client_ip=client_ip,
                required_scopes=required_scopes,
            )

            if not api_key_obj:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired API Key",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # 스코프 검증
            if api_key_obj.scopes:
                key_scopes = set(api_key_obj.scopes)
                required_set = set(required_scopes)

                # admin 스코프는 모든 스코프를 포함
                if "admin" not in key_scopes:
                    missing_scopes = required_set - key_scopes
                    if missing_scopes:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Missing required scopes: {', '.join(missing_scopes)}",
                        )

            # API Key 소유자 조회
            user = db.query(User).filter(User.user_id == api_key_obj.user_id).first()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API Key owner not found",
                )
            return user

        # JWT 인증인 경우 (스코프 검증 없이 통과 - JWT는 전체 권한)
        return await get_current_user(credentials, x_api_key, request, db)

    return scope_checker


def require_any_scope(required_scopes: List[str]) -> Callable:
    """
    API Key 스코프 검증 (하나라도 충족하면 통과)

    사용법:
        @router.get("/data")
        async def get_data(
            user: User = Depends(require_any_scope(["read", "admin"]))
        ):
            ...

    Args:
        required_scopes: 필요한 스코프 목록 (하나라도 충족하면 통과)

    Returns:
        FastAPI Dependency 함수
    """
    async def scope_checker(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        request: Request = None,
        db: Session = Depends(get_db),
    ) -> User:
        """스코프 검증 의존성 (OR 조건)"""
        # API Key 추출
        api_key = None
        if x_api_key and x_api_key.startswith(API_KEY_PREFIX):
            api_key = x_api_key
        elif credentials and credentials.credentials.startswith(API_KEY_PREFIX):
            api_key = credentials.credentials

        # API Key 인증인 경우 스코프 검증
        if api_key:
            from app.services.api_key_service import validate_api_key

            # 클라이언트 IP 추출
            client_ip = None
            if request:
                client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                if not client_ip:
                    client_ip = request.client.host if request.client else None

            # API Key 검증
            api_key_obj = validate_api_key(
                db=db,
                api_key=api_key,
                client_ip=client_ip,
            )

            if not api_key_obj:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired API Key",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # 스코프 검증 (하나라도 있으면 통과)
            if api_key_obj.scopes:
                key_scopes = set(api_key_obj.scopes)
                required_set = set(required_scopes)

                # admin 스코프는 모든 스코프를 포함
                if "admin" not in key_scopes and not (key_scopes & required_set):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Requires one of: {', '.join(required_scopes)}",
                    )

            # API Key 소유자 조회
            user = db.query(User).filter(User.user_id == api_key_obj.user_id).first()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API Key owner not found",
                )
            return user

        # JWT 인증인 경우 (스코프 검증 없이 통과)
        return await get_current_user(credentials, x_api_key, request, db)

    return scope_checker
