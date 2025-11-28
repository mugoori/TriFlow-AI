"""
인증 API 라우터
로그인, 회원가입, 토큰 갱신
"""
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Tenant
from app.auth.password import verify_password, get_password_hash
from app.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from app.auth.dependencies import get_current_user, get_optional_user
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    RefreshTokenRequest,
    ChangePasswordRequest,
    TokenResponse,
    UserResponse,
    LoginResponse,
    AuthStatusResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _create_tokens(user: User) -> TokenResponse:
    """사용자에 대한 토큰 쌍 생성"""
    token_data = {
        "sub": str(user.user_id),
        "email": user.email,
        "role": user.role,
        "tenant_id": str(user.tenant_id),
    }

    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token({"sub": str(user.user_id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    로그인

    이메일과 비밀번호로 인증 후 JWT 토큰 발급
    """
    # 사용자 조회
    user = db.query(User).filter(User.email == request.email).first()

    if not user:
        logger.warning(f"Login failed: user not found - {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    # 비밀번호 검증
    if not verify_password(request.password, user.password_hash):
        logger.warning(f"Login failed: incorrect password - {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    # 비활성 사용자 체크
    if not user.is_active:
        logger.warning(f"Login failed: inactive user - {request.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    logger.info(f"Login successful: {request.email}")

    # 토큰 생성
    tokens = _create_tokens(user)

    return LoginResponse(
        user=UserResponse.model_validate(user),
        tokens=tokens,
    )


@router.post("/register", response_model=LoginResponse)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    """
    회원가입

    새 사용자 계정 생성 및 JWT 토큰 발급
    """
    # 이메일 중복 체크
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # 테넌트 확인 (없으면 기본 테넌트 사용)
    tenant_id = request.tenant_id
    if not tenant_id:
        # 기본 테넌트 조회 또는 생성
        default_tenant = db.query(Tenant).filter(Tenant.name == "Default").first()
        if not default_tenant:
            default_tenant = Tenant(
                tenant_id=uuid4(),
                name="Default",
                description="Default tenant for MVP",
            )
            db.add(default_tenant)
            db.commit()
            db.refresh(default_tenant)
        tenant_id = default_tenant.tenant_id

    # 사용자 생성
    new_user = User(
        user_id=uuid4(),
        tenant_id=tenant_id,
        email=request.email,
        password_hash=get_password_hash(request.password),
        display_name=request.display_name or request.email.split("@")[0],
        role="user",
        is_active=True,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info(f"User registered: {request.email}")

    # 토큰 생성
    tokens = _create_tokens(new_user)

    return LoginResponse(
        user=UserResponse.model_validate(new_user),
        tokens=tokens,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    """
    토큰 갱신

    Refresh Token으로 새 Access Token 발급
    """
    # Refresh 토큰 디코딩
    payload = decode_token(request.refresh_token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # 토큰 타입 검증
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    # 사용자 조회
    user_id = payload.get("sub")
    user = db.query(User).filter(User.user_id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    # 새 토큰 발급
    tokens = _create_tokens(user)

    return tokens


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    비밀번호 변경
    """
    # 현재 비밀번호 검증
    if not verify_password(request.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password",
        )

    # 새 비밀번호 저장
    current_user.password_hash = get_password_hash(request.new_password)
    db.commit()

    logger.info(f"Password changed: {current_user.email}")

    return {"message": "Password changed successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """
    현재 사용자 정보 조회
    """
    return UserResponse.model_validate(current_user)


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status(
    current_user: User = Depends(get_optional_user),
):
    """
    인증 상태 확인

    토큰이 있으면 사용자 정보 반환, 없으면 미인증 상태 반환
    """
    if current_user:
        return AuthStatusResponse(
            authenticated=True,
            user=UserResponse.model_validate(current_user),
        )

    return AuthStatusResponse(
        authenticated=False,
        user=None,
    )
