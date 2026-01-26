"""
인증 API 라우터
로그인, 회원가입, 토큰 갱신
"""
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User, Tenant
from app.auth.password import verify_password, get_password_hash
from app.repositories import UserRepository
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
    GoogleAuthUrlResponse,
    OAuthLoginResponse,
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
    # 사용자 조회 - Repository 패턴 적용
    user_repo = UserRepository(db)
    user = user_repo.get_by_email(request.email)

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
    # 이메일 중복 체크 - Repository 패턴 적용
    user_repo = UserRepository(db)
    if user_repo.email_exists(request.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # 테넌트 확인 (없으면 기본 테넌트 사용)
    tenant_id = request.tenant_id
    if not tenant_id:
        # 기본 테넌트 조회 또는 생성
        default_tenant = db.query(Tenant).filter(Tenant.name == settings.default_tenant_name).first()
        if not default_tenant:
            default_tenant = Tenant(
                tenant_id=uuid4(),
                name=settings.default_tenant_name,
                slug="default",
            )
            db.add(default_tenant)
            db.commit()
            db.refresh(default_tenant)
        tenant_id = default_tenant.tenant_id

    # 사용자 생성
    new_user = User(
        user_id=uuid4(),
        tenant_id=tenant_id,
        username=request.email.split("@")[0],
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


# ========== Google OAuth2 ==========


@router.get("/google/login", response_model=GoogleAuthUrlResponse)
async def google_login():
    """
    Google OAuth 로그인 시작

    Google 로그인 페이지 URL과 CSRF 방지용 state 토큰을 반환합니다.
    Frontend에서 이 URL로 리다이렉트하세요.
    """
    from app.services import oauth_service
    from app.config import settings

    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured",
        )

    try:
        result = oauth_service.get_google_auth_url()
        return GoogleAuthUrlResponse(
            url=result["url"],
            state=result["state"],
        )
    except Exception as e:
        logger.error(f"Failed to generate Google auth URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate Google auth URL",
        )


@router.get("/google/callback", response_model=OAuthLoginResponse)
async def google_callback(
    code: str,
    state: str = None,
    db: Session = Depends(get_db),
):
    """
    Google OAuth 콜백 처리

    Google에서 리다이렉트된 후 authorization code를 처리하여
    사용자 인증 및 JWT 토큰을 발급합니다.
    """
    from app.services import oauth_service

    # 1. Authorization code를 access token으로 교환
    token_data = await oauth_service.exchange_google_code(code)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to exchange authorization code",
        )

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No access token received from Google",
        )

    # 2. Access token으로 사용자 정보 조회
    google_user = await oauth_service.get_google_user_info(access_token)
    if not google_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to get user info from Google",
        )

    google_id = google_user.get("id")
    email = google_user.get("email")
    name = google_user.get("name", email.split("@")[0] if email else "User")
    picture = google_user.get("picture")

    if not google_id or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user info from Google",
        )

    # 3. 기존 사용자 조회 (OAuth provider_id 또는 이메일로)
    existing_user = db.query(User).filter(
        (User.oauth_provider == "google") & (User.oauth_provider_id == google_id)
    ).first()

    is_new_user = False

    if not existing_user:
        # 이메일로 기존 계정 조회 (이메일 연동 케이스)
        existing_user = db.query(User).filter(User.email == email).first()

        if existing_user:
            # 기존 계정에 Google OAuth 연동
            existing_user.oauth_provider = "google"
            existing_user.oauth_provider_id = google_id
            existing_user.profile_image_url = picture
            if not existing_user.display_name:
                existing_user.display_name = name
            db.commit()
            db.refresh(existing_user)
            logger.info(f"Linked Google account to existing user: {email}")
        else:
            # 새 사용자 생성
            is_new_user = True

            # 기본 테넌트 조회 또는 생성
            default_tenant = db.query(Tenant).filter(Tenant.name == settings.default_tenant_name).first()
            if not default_tenant:
                default_tenant = Tenant(
                    tenant_id=uuid4(),
                    name=settings.default_tenant_name,
                    slug="default",
                )
                db.add(default_tenant)
                db.commit()
                db.refresh(default_tenant)

            # 새 사용자 생성
            new_user = User(
                user_id=uuid4(),
                tenant_id=default_tenant.tenant_id,
                username=email.split("@")[0],
                email=email,
                password_hash=None,  # OAuth 사용자는 비밀번호 없음
                display_name=name,
                role="user",
                is_active=True,
                oauth_provider="google",
                oauth_provider_id=google_id,
                profile_image_url=picture,
            )

            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            existing_user = new_user

            logger.info(f"Created new user via Google OAuth: {email}")

    user = existing_user

    # 4. JWT 토큰 발급
    tokens = _create_tokens(user)

    return OAuthLoginResponse(
        user=UserResponse.model_validate(user),
        tokens=tokens,
        is_new_user=is_new_user,
    )
