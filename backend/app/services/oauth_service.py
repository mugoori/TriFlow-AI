"""
OAuth2 서비스 모듈

- Google OAuth2 인증 지원
- Authorization Code Flow 구현
"""
import secrets
import logging
from typing import Optional
from urllib.parse import urlencode

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Google OAuth2 엔드포인트
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# OAuth2 스코프
GOOGLE_SCOPES = [
    "openid",
    "email",
    "profile",
]


def generate_state_token() -> str:
    """CSRF 방지용 state 토큰 생성"""
    return secrets.token_urlsafe(32)


def get_google_auth_url(state: Optional[str] = None) -> dict:
    """
    Google OAuth2 로그인 URL 생성

    Args:
        state: CSRF 방지용 state 토큰 (없으면 자동 생성)

    Returns:
        dict: {url: str, state: str}
    """
    if not settings.google_client_id:
        raise ValueError("Google Client ID is not configured")

    if not state:
        state = generate_state_token()

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "state": state,
        "access_type": "offline",  # refresh_token 받기 위해
        "prompt": "consent",  # 매번 동의 화면 표시 (refresh_token 보장)
    }

    url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    return {
        "url": url,
        "state": state,
    }


async def exchange_google_code(code: str) -> Optional[dict]:
    """
    Authorization code를 access_token으로 교환

    Args:
        code: Google에서 받은 authorization code

    Returns:
        dict: {access_token, refresh_token, expires_in, ...} 또는 None
    """
    if not settings.google_client_id or not settings.google_client_secret:
        raise ValueError("Google OAuth credentials are not configured")

    data = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": settings.google_redirect_uri,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if response.status_code != 200:
                logger.error(f"Google token exchange failed: {response.text}")
                return None

            return response.json()

    except Exception as e:
        logger.error(f"Google token exchange error: {e}")
        return None


async def get_google_user_info(access_token: str) -> Optional[dict]:
    """
    Google access_token으로 사용자 정보 조회

    Args:
        access_token: Google OAuth access token

    Returns:
        dict: {id, email, name, picture, ...} 또는 None
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code != 200:
                logger.error(f"Google userinfo request failed: {response.text}")
                return None

            return response.json()

    except Exception as e:
        logger.error(f"Google userinfo error: {e}")
        return None


async def verify_google_token(id_token: str) -> Optional[dict]:
    """
    Google ID Token 검증 (선택적 사용)

    Args:
        id_token: Google OAuth ID token

    Returns:
        dict: 검증된 토큰 정보 또는 None
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}"
            )

            if response.status_code != 200:
                logger.error(f"Google token verification failed: {response.text}")
                return None

            token_info = response.json()

            # 클라이언트 ID 검증
            if token_info.get("aud") != settings.google_client_id:
                logger.error("Google token audience mismatch")
                return None

            return token_info

    except Exception as e:
        logger.error(f"Google token verification error: {e}")
        return None
