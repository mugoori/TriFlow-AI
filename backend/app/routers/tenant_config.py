"""
Tenant Configuration API Router
테넌트별 모듈 설정 및 기능 플래그 API

Multi-Tenant Customization:
- GET /tenant/config: 현재 테넌트 설정 조회
- GET /tenant/modules: 모든 모듈 목록
- POST /tenant/modules/enable: 모듈 활성화
- POST /tenant/modules/disable: 모듈 비활성화
- GET /tenant/features: 기능 플래그 조회
- GET /tenant/industries: 산업 프로필 목록
"""
import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.services.tenant_config_service import TenantConfigService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tenant", tags=["Tenant Configuration"])


# =====================================================
# Pydantic Schemas
# =====================================================

class IndustryInfo(BaseModel):
    """산업 프로필 정보"""
    code: str
    name: str
    icon: Optional[str] = None
    default_kpis: List[str] = []


class FeatureFlags(BaseModel):
    """기능 플래그"""
    can_use_rulesets: bool
    can_use_experiments: bool
    can_use_learning: bool
    can_use_mcp: bool
    max_workflows: int
    max_judgments_per_day: int
    max_users: int


class TenantConfigResponse(BaseModel):
    """테넌트 설정 응답"""
    tenant_id: str
    tenant_name: str
    subscription_plan: str
    enabled_modules: List[str]
    module_configs: Dict[str, Any]
    industry: Optional[IndustryInfo] = None
    features: FeatureFlags


class ModuleInfo(BaseModel):
    """모듈 정보"""
    module_code: str
    name: str
    description: Optional[str] = None
    category: str
    icon: Optional[str] = None
    default_enabled: bool
    requires_subscription: Optional[str] = None
    display_order: int
    is_enabled: bool
    config: Dict[str, Any] = {}


class ModuleEnableRequest(BaseModel):
    """모듈 활성화 요청"""
    module_code: str = Field(..., description="활성화할 모듈 코드")
    config: Optional[Dict[str, Any]] = Field(None, description="모듈 설정")


class ModuleDisableRequest(BaseModel):
    """모듈 비활성화 요청"""
    module_code: str = Field(..., description="비활성화할 모듈 코드")


class ModuleConfigUpdateRequest(BaseModel):
    """모듈 설정 업데이트 요청"""
    module_code: str = Field(..., description="모듈 코드")
    config: Dict[str, Any] = Field(..., description="업데이트할 설정")


class IndustryProfileResponse(BaseModel):
    """산업 프로필 응답"""
    industry_code: str
    name: str
    description: Optional[str] = None
    default_modules: List[str] = []
    default_kpis: List[str] = []
    sample_rulesets: List[str] = []
    icon: Optional[str] = None


class ChangeIndustryRequest(BaseModel):
    """산업 프로필 변경 요청"""
    industry_code: str = Field(..., description="새 산업 프로필 코드")
    reset_modules: bool = Field(False, description="모듈 설정 초기화 여부")


class SuccessResponse(BaseModel):
    """성공 응답"""
    success: bool
    message: Optional[str] = None


# =====================================================
# Endpoints
# =====================================================

@router.get("/config", response_model=TenantConfigResponse)
async def get_tenant_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    현재 테넌트의 설정 조회

    로그인 후 프론트엔드에서 호출하여 동적 UI 렌더링에 사용
    """
    service = TenantConfigService(db)
    config = service.get_tenant_config(current_user.tenant_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )

    return TenantConfigResponse(**config)


@router.get("/modules", response_model=List[ModuleInfo])
async def list_modules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    테넌트의 모든 모듈 목록 조회

    활성화 여부와 현재 설정 포함
    """
    service = TenantConfigService(db)
    modules = service.get_all_modules(current_user.tenant_id)

    return [ModuleInfo(**m) for m in modules]


@router.post("/modules/enable", response_model=SuccessResponse)
async def enable_module(
    request: ModuleEnableRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    모듈 활성화

    Admin 역할만 수행 가능
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can enable modules"
        )

    service = TenantConfigService(db)

    try:
        service.enable_module(
            tenant_id=current_user.tenant_id,
            module_code=request.module_code,
            user_id=current_user.user_id,
            config=request.config
        )
        logger.info(
            f"Module enabled: {request.module_code} for tenant {current_user.tenant_id} by {current_user.email}"
        )
        return SuccessResponse(success=True, message=f"Module '{request.module_code}' enabled")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/modules/disable", response_model=SuccessResponse)
async def disable_module(
    request: ModuleDisableRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    모듈 비활성화

    Admin 역할만 수행 가능
    Core 모듈(dashboard, chat, data, settings)은 비활성화 불가
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can disable modules"
        )

    service = TenantConfigService(db)

    try:
        success = service.disable_module(
            tenant_id=current_user.tenant_id,
            module_code=request.module_code
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Module '{request.module_code}' not found for this tenant"
            )

        logger.info(
            f"Module disabled: {request.module_code} for tenant {current_user.tenant_id} by {current_user.email}"
        )
        return SuccessResponse(success=True, message=f"Module '{request.module_code}' disabled")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.patch("/modules/config", response_model=SuccessResponse)
async def update_module_config(
    request: ModuleConfigUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    모듈 설정 업데이트

    Admin 역할만 수행 가능
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can update module config"
        )

    service = TenantConfigService(db)
    result = service.update_module_config(
        tenant_id=current_user.tenant_id,
        module_code=request.module_code,
        config=request.config
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module '{request.module_code}' not found for this tenant"
        )

    return SuccessResponse(success=True, message=f"Module '{request.module_code}' config updated")


@router.get("/features", response_model=FeatureFlags)
async def get_feature_flags(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    프론트엔드용 Feature Flag 목록

    구독 플랜 기반 기능 제한 정보
    """
    service = TenantConfigService(db)
    config = service.get_tenant_config(current_user.tenant_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )

    return FeatureFlags(**config["features"])


@router.get("/industries", response_model=List[IndustryProfileResponse])
async def list_industry_profiles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    모든 산업 프로필 목록 조회

    테넌트 생성 또는 프로필 변경 시 참조용
    """
    service = TenantConfigService(db)
    profiles = service.get_all_industry_profiles()

    return [
        IndustryProfileResponse(
            industry_code=p.industry_code,
            name=p.name,
            description=p.description,
            default_modules=p.default_modules or [],
            default_kpis=p.default_kpis or [],
            sample_rulesets=p.sample_rulesets or [],
            icon=p.icon
        )
        for p in profiles
    ]


@router.post("/industry", response_model=SuccessResponse)
async def change_industry_profile(
    request: ChangeIndustryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    테넌트의 산업 프로필 변경

    Admin 역할만 수행 가능
    reset_modules=True이면 기존 모듈 설정을 프로필 기본값으로 초기화
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can change industry profile"
        )

    service = TenantConfigService(db)

    try:
        result = service.change_industry_profile(
            tenant_id=current_user.tenant_id,
            industry_code=request.industry_code,
            user_id=current_user.user_id,
            reset_modules=request.reset_modules
        )

        logger.info(
            f"Industry profile changed: {result['old_industry']} -> {result['new_industry']} "
            f"for tenant {current_user.tenant_id} by {current_user.email}"
        )
        return SuccessResponse(
            success=True,
            message=f"Industry changed to '{request.industry_code}'"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/modules/{module_code}/enabled")
async def check_module_enabled(
    module_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, bool]:
    """
    특정 모듈이 활성화되어 있는지 확인

    프론트엔드에서 특정 기능 접근 전 체크용
    """
    service = TenantConfigService(db)
    is_enabled = service.is_module_enabled(current_user.tenant_id, module_code)

    return {"enabled": is_enabled}
