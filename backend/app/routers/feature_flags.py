# -*- coding: utf-8 -*-
"""
Feature Flags Router - V2.0 Feature Flag Management API

V2 기능의 점진적 롤아웃을 관리하는 API 엔드포인트

엔드포인트:
- GET  /api/v2/feature-flags                 - 모든 플래그 상태 조회
- GET  /api/v2/feature-flags/{feature}       - 특정 플래그 상태 조회
- POST /api/v2/feature-flags/{feature}/enable  - 활성화
- POST /api/v2/feature-flags/{feature}/disable - 비활성화
- GET  /api/v2/feature-flags/{feature}/rollout - 롤아웃 비율 조회
- PUT  /api/v2/feature-flags/{feature}/rollout - 롤아웃 비율 설정
"""

import logging
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Header
from pydantic import BaseModel, Field

from app.services.feature_flag_service import (
    FeatureFlagService,
    V2Feature,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ============ Pydantic Models ============


class FeatureFlagStatus(BaseModel):
    """개별 기능 플래그 상태"""
    feature: str = Field(..., description="기능 이름")
    enabled: bool = Field(..., description="활성화 여부")
    rollout_percentage: int = Field(..., ge=0, le=100, description="롤아웃 비율")
    override: Optional[str] = Field(None, description="오버라이드 상태")
    description: str = Field("", description="기능 설명")


class AllFlagsResponse(BaseModel):
    """모든 플래그 조회 응답"""
    tenant_id: Optional[str] = Field(None, description="테넌트 ID")
    flags: Dict[str, FeatureFlagStatus] = Field(..., description="플래그 목록")


class SingleFlagResponse(BaseModel):
    """단일 플래그 조회 응답"""
    feature: str
    enabled: bool
    rollout_percentage: int
    override: Optional[str]
    description: str


class EnableDisableRequest(BaseModel):
    """활성화/비활성화 요청"""
    tenant_id: Optional[str] = Field(None, description="테넌트 ID (없으면 글로벌)")


class EnableDisableResponse(BaseModel):
    """활성화/비활성화 응답"""
    feature: str
    action: str  # "enabled" or "disabled"
    scope: str  # "global" or "tenant:{id}"
    success: bool


class RolloutRequest(BaseModel):
    """롤아웃 비율 설정 요청"""
    percentage: int = Field(..., ge=0, le=100, description="롤아웃 비율 (0-100)")


class RolloutResponse(BaseModel):
    """롤아웃 비율 응답"""
    feature: str
    rollout_percentage: int
    success: bool = True


class RemoveOverrideResponse(BaseModel):
    """오버라이드 제거 응답"""
    feature: str
    scope: str
    success: bool


# ============ Helper Functions ============


def _validate_feature(feature_name: str) -> V2Feature:
    """기능 이름 검증 및 V2Feature enum 반환"""
    try:
        return V2Feature(feature_name)
    except ValueError:
        valid_features = [f.value for f in V2Feature]
        raise HTTPException(
            status_code=404,
            detail={
                "error": True,
                "message": f"Unknown feature: {feature_name}",
                "valid_features": valid_features,
            }
        )


# ============ API Endpoints ============


@router.get(
    "",
    response_model=AllFlagsResponse,
    summary="모든 Feature Flag 조회",
    description="모든 V2 기능 플래그의 상태를 조회합니다.",
)
async def get_all_flags(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
):
    """
    모든 Feature Flag 상태 조회

    Args:
        x_tenant_id: 테넌트 ID (헤더, 선택)

    Returns:
        AllFlagsResponse: 모든 플래그 상태
    """
    all_flags = FeatureFlagService.get_all_flags(x_tenant_id)

    flags_status = {}
    for feature_name, info in all_flags.items():
        flags_status[feature_name] = FeatureFlagStatus(
            feature=feature_name,
            enabled=info["enabled"],
            rollout_percentage=info["rollout_percentage"],
            override=info["override"],
            description=info["description"],
        )

    return AllFlagsResponse(
        tenant_id=x_tenant_id,
        flags=flags_status,
    )


@router.get(
    "/{feature}",
    response_model=SingleFlagResponse,
    summary="특정 Feature Flag 조회",
    description="특정 V2 기능 플래그의 상태를 조회합니다.",
)
async def get_flag(
    feature: str,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
):
    """
    특정 Feature Flag 상태 조회

    Args:
        feature: 기능 이름 (예: v2_progressive_trust)
        x_tenant_id: 테넌트 ID (헤더, 선택)

    Returns:
        SingleFlagResponse: 플래그 상태
    """
    v2_feature = _validate_feature(feature)

    is_enabled = FeatureFlagService.is_enabled(v2_feature, x_tenant_id)
    rollout = FeatureFlagService.get_rollout_percentage(v2_feature)
    override = FeatureFlagService._get_override_status(v2_feature, x_tenant_id)
    description = FeatureFlagService._get_feature_description(v2_feature)

    return SingleFlagResponse(
        feature=feature,
        enabled=is_enabled,
        rollout_percentage=rollout,
        override=override,
        description=description,
    )


@router.post(
    "/{feature}/enable",
    response_model=EnableDisableResponse,
    summary="Feature Flag 활성화",
    description="V2 기능을 활성화합니다. 관리자 권한 필요.",
)
async def enable_flag(
    feature: str,
    request: Optional[EnableDisableRequest] = None,
):
    """
    Feature Flag 활성화

    Args:
        feature: 기능 이름
        request: 테넌트 ID (선택, 없으면 글로벌)

    Returns:
        EnableDisableResponse: 결과
    """
    v2_feature = _validate_feature(feature)
    tenant_id = request.tenant_id if request else None

    success = FeatureFlagService.enable(v2_feature, tenant_id)

    if not success:
        raise HTTPException(
            status_code=500,
            detail={"error": True, "message": "Failed to enable feature flag"}
        )

    scope = f"tenant:{tenant_id}" if tenant_id else "global"

    return EnableDisableResponse(
        feature=feature,
        action="enabled",
        scope=scope,
        success=True,
    )


@router.post(
    "/{feature}/disable",
    response_model=EnableDisableResponse,
    summary="Feature Flag 비활성화",
    description="V2 기능을 비활성화합니다. 관리자 권한 필요.",
)
async def disable_flag(
    feature: str,
    request: Optional[EnableDisableRequest] = None,
):
    """
    Feature Flag 비활성화

    Args:
        feature: 기능 이름
        request: 테넌트 ID (선택, 없으면 글로벌)

    Returns:
        EnableDisableResponse: 결과
    """
    v2_feature = _validate_feature(feature)
    tenant_id = request.tenant_id if request else None

    success = FeatureFlagService.disable(v2_feature, tenant_id)

    if not success:
        raise HTTPException(
            status_code=500,
            detail={"error": True, "message": "Failed to disable feature flag"}
        )

    scope = f"tenant:{tenant_id}" if tenant_id else "global"

    return EnableDisableResponse(
        feature=feature,
        action="disabled",
        scope=scope,
        success=True,
    )


@router.delete(
    "/{feature}/override",
    response_model=RemoveOverrideResponse,
    summary="Feature Flag 오버라이드 제거",
    description="기능의 오버라이드 설정을 제거하고 롤아웃 비율을 따르도록 합니다.",
)
async def remove_override(
    feature: str,
    tenant_id: Optional[str] = Query(None, description="테넌트 ID"),
):
    """
    Feature Flag 오버라이드 제거

    오버라이드를 제거하면 롤아웃 비율에 따라 결정됩니다.

    Args:
        feature: 기능 이름
        tenant_id: 테넌트 ID (선택)

    Returns:
        RemoveOverrideResponse: 결과
    """
    v2_feature = _validate_feature(feature)

    success = FeatureFlagService.remove_override(v2_feature, tenant_id)

    if not success:
        raise HTTPException(
            status_code=500,
            detail={"error": True, "message": "Failed to remove override"}
        )

    scope = f"tenant:{tenant_id}" if tenant_id else "global"

    return RemoveOverrideResponse(
        feature=feature,
        scope=scope,
        success=True,
    )


@router.get(
    "/{feature}/rollout",
    response_model=RolloutResponse,
    summary="롤아웃 비율 조회",
    description="기능의 점진적 롤아웃 비율을 조회합니다.",
)
async def get_rollout(
    feature: str,
):
    """
    롤아웃 비율 조회

    Args:
        feature: 기능 이름

    Returns:
        RolloutResponse: 롤아웃 비율
    """
    v2_feature = _validate_feature(feature)

    percentage = FeatureFlagService.get_rollout_percentage(v2_feature)

    return RolloutResponse(
        feature=feature,
        rollout_percentage=percentage,
    )


@router.put(
    "/{feature}/rollout",
    response_model=RolloutResponse,
    summary="롤아웃 비율 설정",
    description="기능의 점진적 롤아웃 비율을 설정합니다. 관리자 권한 필요.",
)
async def set_rollout(
    feature: str,
    request: RolloutRequest,
):
    """
    롤아웃 비율 설정

    Args:
        feature: 기능 이름
        request: 롤아웃 비율 (0-100)

    Returns:
        RolloutResponse: 결과
    """
    v2_feature = _validate_feature(feature)

    success = FeatureFlagService.set_rollout_percentage(
        v2_feature,
        request.percentage,
    )

    if not success:
        raise HTTPException(
            status_code=500,
            detail={"error": True, "message": "Failed to set rollout percentage"}
        )

    return RolloutResponse(
        feature=feature,
        rollout_percentage=request.percentage,
        success=True,
    )


# ============ Info Endpoints ============


@router.get(
    "/info/features",
    summary="사용 가능한 Feature 목록",
    description="모든 V2 기능 목록과 설명을 반환합니다.",
)
async def list_features():
    """사용 가능한 Feature 목록"""
    features = []
    for feature in V2Feature:
        features.append({
            "name": feature.value,
            "description": FeatureFlagService._get_feature_description(feature),
        })

    return {
        "features": features,
        "total": len(features),
    }
