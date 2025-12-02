"""
인증 관련 Pydantic 스키마
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ========== Request 스키마 ==========

class LoginRequest(BaseModel):
    """로그인 요청"""
    email: EmailStr = Field(..., description="이메일 주소")
    password: str = Field(..., min_length=4, description="비밀번호")


class RegisterRequest(BaseModel):
    """회원가입 요청"""
    email: EmailStr = Field(..., description="이메일 주소")
    password: str = Field(..., min_length=8, description="비밀번호 (최소 8자)")
    display_name: Optional[str] = Field(None, max_length=100, description="표시 이름")
    tenant_id: Optional[UUID] = Field(None, description="테넌트 ID (없으면 기본 테넌트)")


class RefreshTokenRequest(BaseModel):
    """토큰 갱신 요청"""
    refresh_token: str = Field(..., description="Refresh Token")


class ChangePasswordRequest(BaseModel):
    """비밀번호 변경 요청"""
    current_password: str = Field(..., description="현재 비밀번호")
    new_password: str = Field(..., min_length=8, description="새 비밀번호 (최소 8자)")


# ========== Response 스키마 ==========

class TokenResponse(BaseModel):
    """토큰 응답"""
    access_token: str = Field(..., description="JWT Access Token")
    refresh_token: str = Field(..., description="JWT Refresh Token")
    token_type: str = Field(default="bearer", description="토큰 타입")
    expires_in: int = Field(..., description="Access Token 만료 시간 (초)")


class UserResponse(BaseModel):
    """사용자 정보 응답"""
    user_id: UUID = Field(..., description="사용자 ID")
    email: str = Field(..., description="이메일")
    display_name: Optional[str] = Field(None, description="표시 이름")
    role: str = Field(..., description="역할 (admin, user 등)")
    tenant_id: UUID = Field(..., description="테넌트 ID")
    is_active: bool = Field(..., description="활성 상태")
    created_at: datetime = Field(..., description="생성 일시")
    oauth_provider: Optional[str] = Field(None, description="OAuth 제공자 (google, github 등)")
    profile_image_url: Optional[str] = Field(None, description="프로필 이미지 URL")

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    """로그인 응답"""
    user: UserResponse = Field(..., description="사용자 정보")
    tokens: TokenResponse = Field(..., description="인증 토큰")


class AuthStatusResponse(BaseModel):
    """인증 상태 응답"""
    authenticated: bool = Field(..., description="인증 여부")
    user: Optional[UserResponse] = Field(None, description="사용자 정보")


# ========== OAuth2 스키마 ==========

class GoogleAuthUrlResponse(BaseModel):
    """Google OAuth 로그인 URL 응답"""
    url: str = Field(..., description="Google OAuth 로그인 URL")
    state: str = Field(..., description="CSRF 방지용 state 토큰")


class OAuthCallbackRequest(BaseModel):
    """OAuth 콜백 요청"""
    code: str = Field(..., description="Authorization code")
    state: Optional[str] = Field(None, description="CSRF 방지용 state")


class OAuthLoginResponse(BaseModel):
    """OAuth 로그인 응답"""
    user: UserResponse = Field(..., description="사용자 정보")
    tokens: TokenResponse = Field(..., description="인증 토큰")
    is_new_user: bool = Field(..., description="신규 가입 여부")
