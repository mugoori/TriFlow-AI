"""
JWT 토큰 생성 및 검증
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from uuid import UUID

from jose import JWTError, jwt

# JWT 설정 (환경변수에서 로드)
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "triflow-ai-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Access Token 생성

    Args:
        data: 토큰에 포함할 데이터 (sub: user_id, tenant_id, role 등)
        expires_delta: 만료 시간 (기본: ACCESS_TOKEN_EXPIRE_MINUTES)

    Returns:
        JWT access token 문자열
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "type": "access",
        "iat": datetime.now(timezone.utc),
    })

    # UUID를 문자열로 변환
    for key, value in to_encode.items():
        if isinstance(value, UUID):
            to_encode[key] = str(value)

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Refresh Token 생성

    Args:
        data: 토큰에 포함할 데이터 (sub: user_id)
        expires_delta: 만료 시간 (기본: REFRESH_TOKEN_EXPIRE_DAYS)

    Returns:
        JWT refresh token 문자열
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "iat": datetime.now(timezone.utc),
    })

    # UUID를 문자열로 변환
    for key, value in to_encode.items():
        if isinstance(value, UUID):
            to_encode[key] = str(value)

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    JWT 토큰 디코딩 및 검증

    Args:
        token: JWT 토큰 문자열

    Returns:
        디코딩된 페이로드 또는 None (검증 실패 시)
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def verify_token_type(token: str, expected_type: str) -> bool:
    """
    토큰 타입 검증

    Args:
        token: JWT 토큰
        expected_type: 예상 타입 ("access" 또는 "refresh")

    Returns:
        타입 일치 여부
    """
    payload = decode_token(token)
    if not payload:
        return False

    return payload.get("type") == expected_type


def get_token_expiry(token: str) -> Optional[datetime]:
    """
    토큰 만료 시간 조회

    Args:
        token: JWT 토큰

    Returns:
        만료 시간 또는 None
    """
    payload = decode_token(token)
    if not payload:
        return None

    exp = payload.get("exp")
    if exp:
        return datetime.fromtimestamp(exp, tz=timezone.utc)

    return None
