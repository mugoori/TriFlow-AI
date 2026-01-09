"""
Tenant API Router
테넌트 관리 엔드포인트

권한:
- tenants:* - admin만 (테넌트 전체 관리)
"""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.core import Tenant
from app.schemas.tenant import TenantCreate, TenantUpdate, TenantResponse
from app.services.rbac_service import require_admin

router = APIRouter(tags=["tenants"])


@router.get("/", response_model=List[TenantResponse])
def list_tenants(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    """
    테넌트 목록 조회 (admin만)

    Args:
        skip: 건너뛸 레코드 수
        limit: 최대 반환 레코드 수
        db: DB 세션
    """
    tenants = db.query(Tenant).offset(skip).limit(limit).all()
    return tenants


@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    """
    테넌트 상세 조회 (admin만)

    Args:
        tenant_id: 테넌트 ID
        db: DB 세션
    """
    tenant = db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found",
        )

    return tenant


@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
def create_tenant(
    tenant_data: TenantCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    """
    테넌트 생성 (admin만)

    Args:
        tenant_data: 테넌트 생성 데이터
        db: DB 세션
    """
    # Slug 중복 체크
    existing_tenant = db.query(Tenant).filter(Tenant.slug == tenant_data.slug).first()
    if existing_tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tenant with slug '{tenant_data.slug}' already exists",
        )

    # 테넌트 생성
    tenant = Tenant(**tenant_data.model_dump())
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    return tenant


@router.patch("/{tenant_id}", response_model=TenantResponse)
def update_tenant(
    tenant_id: UUID,
    tenant_data: TenantUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    """
    테넌트 업데이트 (admin만)

    Args:
        tenant_id: 테넌트 ID
        tenant_data: 업데이트 데이터
        db: DB 세션
    """
    tenant = db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found",
        )

    # 업데이트할 필드만 적용
    update_data = tenant_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tenant, field, value)

    db.commit()
    db.refresh(tenant)

    return tenant


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tenant(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    """
    테넌트 삭제 (admin만)

    Args:
        tenant_id: 테넌트 ID
        db: DB 세션
    """
    tenant = db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found",
        )

    db.delete(tenant)
    db.commit()

    return None
