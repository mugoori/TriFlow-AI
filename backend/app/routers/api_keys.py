"""
API Key 관리 라우터

- API Key 발급/조회/회전/폐기
- 관리자 및 본인 키만 관리 가능
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.models.core import ApiKey
from app.auth.dependencies import get_current_user
from app.services import api_key_service

router = APIRouter()


# ========== Pydantic Schemas ==========


class ApiKeyCreate(BaseModel):
    """API Key 생성 요청"""
    name: str = Field(..., min_length=1, max_length=255, description="키 이름")
    description: Optional[str] = Field(None, max_length=1000, description="설명")
    scopes: list[str] = Field(default=["read"], description="권한 스코프")
    expires_in_days: Optional[int] = Field(None, ge=1, le=365, description="만료일 (일 단위)")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Production API Key",
                "description": "센서 데이터 조회용",
                "scopes": ["read", "sensors"],
                "expires_in_days": 90
            }
        }


class ApiKeyResponse(BaseModel):
    """API Key 응답 (키 값 제외)"""
    key_id: UUID
    tenant_id: UUID
    user_id: UUID
    name: str
    description: Optional[str]
    key_prefix: str
    scopes: list[str]
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    last_used_ip: Optional[str]
    usage_count: int
    is_active: bool
    revoked_at: Optional[datetime]
    revoked_reason: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ApiKeyCreateResponse(BaseModel):
    """API Key 생성 응답 (키 값 포함 - 최초 1회만)"""
    api_key: ApiKeyResponse
    key: str = Field(..., description="전체 API Key (이 응답에서만 표시됨, 안전하게 보관하세요)")

    class Config:
        json_schema_extra = {
            "example": {
                "api_key": {
                    "key_id": "...",
                    "name": "Production API Key",
                    "key_prefix": "tfk_abc12345",
                    "scopes": ["read", "sensors"],
                },
                "key": "tfk_abc12345def67890xyz..."
            }
        }


class ApiKeyRotateResponse(BaseModel):
    """API Key 회전 응답"""
    old_key_id: UUID
    new_api_key: ApiKeyResponse
    new_key: str = Field(..., description="새 API Key (이 응답에서만 표시됨)")


class ApiKeyRevokeRequest(BaseModel):
    """API Key 폐기 요청"""
    reason: Optional[str] = Field(None, max_length=255, description="폐기 사유")


class ApiKeyStatsResponse(BaseModel):
    """API Key 통계 응답"""
    total: int
    active: int
    expired: int
    revoked: int
    usage_24h: int


class AvailableScopesResponse(BaseModel):
    """사용 가능한 스코프 목록"""
    scopes: list[dict]


# ========== Endpoints ==========


@router.get("/scopes", response_model=AvailableScopesResponse)
async def get_available_scopes():
    """사용 가능한 API Key 스코프 목록 조회"""
    scopes = [
        {"name": "read", "description": "데이터 조회 권한"},
        {"name": "write", "description": "데이터 생성/수정 권한"},
        {"name": "delete", "description": "데이터 삭제 권한"},
        {"name": "admin", "description": "모든 권한 (관리자용)"},
        {"name": "sensors", "description": "센서 데이터 접근"},
        {"name": "workflows", "description": "워크플로우 관리"},
        {"name": "rulesets", "description": "룰셋 관리"},
        {"name": "erp_mes", "description": "ERP/MES 데이터 접근"},
        {"name": "notifications", "description": "알림 전송"},
    ]
    return {"scopes": scopes}


@router.get("", response_model=list[ApiKeyResponse])
async def list_api_keys(
    include_revoked: bool = Query(False, description="폐기된 키 포함 여부"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """API Key 목록 조회"""
    keys = api_key_service.list_api_keys(
        db=db,
        user=current_user,
        include_revoked=include_revoked,
    )
    return keys


@router.get("/stats", response_model=ApiKeyStatsResponse)
async def get_api_key_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """API Key 통계 조회"""
    stats = api_key_service.get_api_key_stats(db=db, user=current_user)
    return stats


@router.post("", response_model=ApiKeyCreateResponse)
async def create_api_key(
    request: ApiKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    새 API Key 생성

    **중요**: 응답에 포함된 `key` 값은 이 요청에서만 확인 가능합니다.
    안전한 곳에 저장하세요. 분실 시 회전(rotate)하여 새 키를 발급받아야 합니다.
    """
    # 스코프 유효성 검증
    valid_scopes = {"read", "write", "delete", "admin", "sensors", "workflows", "rulesets", "erp_mes", "notifications"}
    invalid_scopes = set(request.scopes) - valid_scopes
    if invalid_scopes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scopes: {', '.join(invalid_scopes)}"
        )

    # admin 스코프는 admin 역할만 발급 가능
    if "admin" in request.scopes and current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only admin users can create keys with admin scope"
        )

    api_key, full_key = api_key_service.create_api_key(
        db=db,
        user=current_user,
        name=request.name,
        description=request.description,
        scopes=request.scopes,
        expires_in_days=request.expires_in_days,
    )

    return {
        "api_key": api_key,
        "key": full_key,
    }


@router.get("/{key_id}", response_model=ApiKeyResponse)
async def get_api_key(
    key_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """API Key 상세 조회"""
    api_key = db.query(ApiKey).filter(
        ApiKey.key_id == key_id,
        ApiKey.tenant_id == current_user.tenant_id,
    ).first()

    if not api_key:
        raise HTTPException(status_code=404, detail="API Key not found")

    return api_key


@router.post("/{key_id}/rotate", response_model=ApiKeyRotateResponse)
async def rotate_api_key(
    key_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    API Key 회전

    기존 키를 폐기하고 새 키를 발급합니다.
    기존 설정(이름, 스코프, 만료일)이 유지됩니다.
    """
    new_key, full_key = api_key_service.rotate_api_key(
        db=db,
        key_id=key_id,
        user=current_user,
    )

    if not new_key:
        raise HTTPException(status_code=404, detail="API Key not found or already revoked")

    return {
        "old_key_id": key_id,
        "new_api_key": new_key,
        "new_key": full_key,
    }


@router.post("/{key_id}/revoke")
async def revoke_api_key(
    key_id: UUID,
    request: ApiKeyRevokeRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """API Key 폐기"""
    reason = request.reason if request else None

    success = api_key_service.revoke_api_key(
        db=db,
        key_id=key_id,
        user=current_user,
        reason=reason,
    )

    if not success:
        raise HTTPException(status_code=404, detail="API Key not found")

    return {"message": "API Key revoked successfully"}


@router.delete("/{key_id}")
async def delete_api_key(
    key_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    API Key 삭제

    주의: 완전히 삭제되며 복구할 수 없습니다.
    폐기(revoke)를 권장합니다.
    """
    api_key = db.query(ApiKey).filter(
        ApiKey.key_id == key_id,
        ApiKey.tenant_id == current_user.tenant_id,
    ).first()

    if not api_key:
        raise HTTPException(status_code=404, detail="API Key not found")

    db.delete(api_key)
    db.commit()

    return {"message": "API Key deleted successfully"}
