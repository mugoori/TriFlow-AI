# -*- coding: utf-8 -*-
"""
사용자 관리 관련 Pydantic 스키마
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


# ========== Request 스키마 ==========


class UserRoleUpdateRequest(BaseModel):
    """사용자 역할 변경 요청"""
    role: str = Field(
        ...,
        description="변경할 역할 (admin, approver, operator, user, viewer)",
        pattern="^(admin|approver|operator|user|viewer)$",
    )


class DataScopeUpdateRequest(BaseModel):
    """Data Scope 설정 요청"""
    factory_codes: List[str] = Field(
        default_factory=list,
        description="접근 가능한 공장 코드 목록",
    )
    line_codes: List[str] = Field(
        default_factory=list,
        description="접근 가능한 라인 코드 목록",
    )
    product_families: List[str] = Field(
        default_factory=list,
        description="접근 가능한 제품군 목록",
    )
    shift_codes: List[str] = Field(
        default_factory=list,
        description="접근 가능한 시프트 코드 목록",
    )
    equipment_ids: List[str] = Field(
        default_factory=list,
        description="접근 가능한 설비 ID 목록",
    )
    all_access: bool = Field(
        default=False,
        description="전체 접근 권한 (admin 전용)",
    )


# ========== Response 스키마 ==========


class DataScopeResponse(BaseModel):
    """Data Scope 응답"""
    factory_codes: List[str] = Field(default_factory=list)
    line_codes: List[str] = Field(default_factory=list)
    product_families: List[str] = Field(default_factory=list)
    shift_codes: List[str] = Field(default_factory=list)
    equipment_ids: List[str] = Field(default_factory=list)
    all_access: bool = False


class UserDetailResponse(BaseModel):
    """사용자 상세 정보 응답"""
    user_id: UUID = Field(..., description="사용자 ID")
    tenant_id: UUID = Field(..., description="테넌트 ID")
    email: str = Field(..., description="이메일")
    username: str = Field(..., description="사용자명")
    display_name: Optional[str] = Field(None, description="표시 이름")
    role: str = Field(..., description="역할")
    is_active: bool = Field(..., description="활성 상태")
    status: str = Field(..., description="상태 (active, inactive, locked)")
    created_at: datetime = Field(..., description="생성 일시")
    last_login: Optional[datetime] = Field(None, description="마지막 로그인")
    data_scope: DataScopeResponse = Field(
        default_factory=DataScopeResponse,
        description="데이터 접근 범위",
    )
    oauth_provider: Optional[str] = Field(None, description="OAuth 제공자")
    profile_image_url: Optional[str] = Field(None, description="프로필 이미지 URL")

    class Config:
        from_attributes = True

    @classmethod
    def from_user(cls, user) -> "UserDetailResponse":
        """User 모델에서 응답 생성"""
        metadata = user.user_metadata or {}
        data_scope_config = metadata.get("data_scope", {})

        return cls(
            user_id=user.user_id,
            tenant_id=user.tenant_id,
            email=user.email,
            username=user.username,
            display_name=user.display_name,
            role=user.role,
            is_active=user.is_active,
            status=user.status,
            created_at=user.created_at,
            last_login=user.last_login,
            data_scope=DataScopeResponse(
                factory_codes=data_scope_config.get("factory_codes", []),
                line_codes=data_scope_config.get("line_codes", []),
                product_families=data_scope_config.get("product_families", []),
                shift_codes=data_scope_config.get("shift_codes", []),
                equipment_ids=data_scope_config.get("equipment_ids", []),
                all_access=data_scope_config.get("all_access", False),
            ),
            oauth_provider=user.oauth_provider,
            profile_image_url=user.profile_image_url,
        )


class UserListResponse(BaseModel):
    """사용자 목록 응답"""
    users: List[UserDetailResponse] = Field(..., description="사용자 목록")
    total: int = Field(..., description="전체 사용자 수")


class RoleInfo(BaseModel):
    """역할 정보"""
    role: str = Field(..., description="역할 코드")
    level: int = Field(..., description="역할 레벨 (높을수록 권한 많음)")
    label: str = Field(..., description="표시 이름")
    description: str = Field(..., description="역할 설명")


class RoleListResponse(BaseModel):
    """역할 목록 응답"""
    roles: List[RoleInfo] = Field(..., description="역할 목록")


class PermissionInfo(BaseModel):
    """권한 정보"""
    resource: str = Field(..., description="리소스")
    action: str = Field(..., description="액션")
    permission: str = Field(..., description="권한 문자열 (resource:action)")


class RolePermissionsResponse(BaseModel):
    """역할별 권한 응답"""
    role: str = Field(..., description="역할")
    level: int = Field(..., description="역할 레벨")
    permissions: List[str] = Field(..., description="권한 목록")
    permissions_detail: List[PermissionInfo] = Field(
        ...,
        description="권한 상세 목록",
    )


class FactoryLineResponse(BaseModel):
    """공장/라인 코드 목록 응답"""
    factory_codes: List[str] = Field(..., description="공장 코드 목록")
    line_codes: List[str] = Field(..., description="라인 코드 목록")
