# -*- coding: utf-8 -*-
"""Samples Router

샘플 큐레이션 API.

엔드포인트:
# 샘플 관리
- POST   /samples                      # 샘플 생성 (수동)
- GET    /samples                      # 샘플 목록
- GET    /samples/{id}                 # 샘플 조회
- PUT    /samples/{id}                 # 샘플 수정
- DELETE /samples/{id}                 # 샘플 삭제
- POST   /samples/{id}/approve         # 샘플 승인
- POST   /samples/{id}/reject          # 샘플 거부
- POST   /samples/extract              # 피드백에서 자동 추출
- GET    /samples/stats                # 샘플 통계

# 골든 샘플셋
- POST   /golden-sets                  # 셋 생성
- GET    /golden-sets                  # 셋 목록
- GET    /golden-sets/{id}             # 셋 조회
- PUT    /golden-sets/{id}             # 셋 수정
- DELETE /golden-sets/{id}             # 셋 삭제
- POST   /golden-sets/{id}/samples     # 샘플 추가
- DELETE /golden-sets/{id}/samples/{sample_id}  # 샘플 제거
- GET    /golden-sets/{id}/samples     # 샘플 목록
- POST   /golden-sets/{id}/auto-update # 자동 업데이트
- GET    /golden-sets/{id}/export      # 내보내기
"""
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User
from app.services.sample_curation_service import SampleCurationService
from app.services.golden_sample_set_service import GoldenSampleSetService
from app.services.rbac_service import Role, require_role
from app.schemas.sample import (
    # Sample
    SampleCreate,
    SampleUpdate,
    SampleRejectRequest,
    SampleExtractRequest,
    SampleResponse,
    SampleListResponse,
    SampleExtractResponse,
    SampleStats,
    # Golden Set
    GoldenSetCreate,
    GoldenSetUpdate,
    GoldenSetAddSampleRequest,
    GoldenSetAutoUpdateRequest,
    GoldenSetResponse,
    GoldenSetListResponse,
    GoldenSetSampleListResponse,
    GoldenSetAutoUpdateResponse,
    ExportFormat,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/samples", tags=["samples"])
golden_router = APIRouter(prefix="/golden-sets", tags=["golden-sets"])


# ============================================
# 샘플 관리
# ============================================

@router.post("", response_model=SampleResponse)
async def create_sample(
    request: SampleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_role(Role.USER, Role.OPERATOR, Role.APPROVER, Role.ADMIN)),
):
    """샘플 생성 (수동)"""
    service = SampleCurationService(db)
    try:
        sample = service.create_sample(
            tenant_id=current_user.tenant_id,
            request=request,
        )
        return SampleResponse.model_validate(sample)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=SampleListResponse)
async def list_samples(
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    source_type: Optional[str] = Query(None),
    min_quality: Optional[float] = Query(None, ge=0, le=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """샘플 목록"""
    service = SampleCurationService(db)
    samples, total = service.list_samples(
        tenant_id=current_user.tenant_id,
        category=category,
        status=status,
        source_type=source_type,
        min_quality=min_quality,
        page=page,
        page_size=page_size,
    )
    return SampleListResponse(
        samples=[SampleResponse.model_validate(s) for s in samples],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/stats", response_model=SampleStats)
async def get_sample_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """샘플 통계"""
    service = SampleCurationService(db)
    return service.get_sample_stats(current_user.tenant_id)


@router.post("/extract", response_model=SampleExtractResponse)
async def extract_samples(
    request: SampleExtractRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_role(Role.OPERATOR, Role.APPROVER, Role.ADMIN)),
):
    """피드백에서 샘플 자동 추출"""
    service = SampleCurationService(db)
    samples, skipped = service.extract_samples_from_feedback(
        tenant_id=current_user.tenant_id,
        request=request,
    )
    return SampleExtractResponse(
        extracted_count=len(samples),
        skipped_duplicates=skipped,
        samples=[SampleResponse.model_validate(s) for s in samples],
        dry_run=request.dry_run,
    )


@router.get("/{sample_id}", response_model=SampleResponse)
async def get_sample(
    sample_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """샘플 조회"""
    service = SampleCurationService(db)
    sample = service.get_sample(sample_id)
    if not sample or sample.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="샘플을 찾을 수 없습니다")
    return SampleResponse.model_validate(sample)


@router.put("/{sample_id}", response_model=SampleResponse)
async def update_sample(
    sample_id: UUID,
    request: SampleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """샘플 수정"""
    service = SampleCurationService(db)
    sample = service.get_sample(sample_id)
    if not sample or sample.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="샘플을 찾을 수 없습니다")

    try:
        updated = service.update_sample(sample_id, request)
        return SampleResponse.model_validate(updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{sample_id}")
async def delete_sample(
    sample_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_role(Role.ADMIN)),
):
    """샘플 삭제"""
    service = SampleCurationService(db)
    sample = service.get_sample(sample_id)
    if not sample or sample.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="샘플을 찾을 수 없습니다")

    service.delete_sample(sample_id)
    return {"success": True}


@router.post("/{sample_id}/approve", response_model=SampleResponse)
async def approve_sample(
    sample_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_role(Role.APPROVER, Role.ADMIN)),
):
    """샘플 승인"""
    service = SampleCurationService(db)
    sample = service.get_sample(sample_id)
    if not sample or sample.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="샘플을 찾을 수 없습니다")

    try:
        approved = service.approve_sample(sample_id, current_user.user_id)
        return SampleResponse.model_validate(approved)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{sample_id}/reject", response_model=SampleResponse)
async def reject_sample(
    sample_id: UUID,
    request: SampleRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """샘플 거부"""
    service = SampleCurationService(db)
    sample = service.get_sample(sample_id)
    if not sample or sample.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="샘플을 찾을 수 없습니다")

    try:
        rejected = service.reject_sample(sample_id, request.reason)
        return SampleResponse.model_validate(rejected)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================
# 골든 샘플셋
# ============================================

@golden_router.post("", response_model=GoldenSetResponse)
async def create_golden_set(
    request: GoldenSetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_role(Role.APPROVER, Role.ADMIN)),
):
    """골든 샘플셋 생성"""
    service = GoldenSampleSetService(db)
    sample_set = service.create_set(
        tenant_id=current_user.tenant_id,
        request=request,
        created_by=current_user.user_id,
    )
    return GoldenSetResponse.model_validate(sample_set)


@golden_router.get("", response_model=GoldenSetListResponse)
async def list_golden_sets(
    is_active: Optional[bool] = Query(None),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """골든 샘플셋 목록"""
    service = GoldenSampleSetService(db)
    sets = service.list_sets(
        tenant_id=current_user.tenant_id,
        is_active=is_active,
        category=category,
    )
    return GoldenSetListResponse(
        sets=[GoldenSetResponse.model_validate(s) for s in sets],
        total=len(sets),
    )


@golden_router.get("/{set_id}", response_model=GoldenSetResponse)
async def get_golden_set(
    set_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """골든 샘플셋 조회"""
    service = GoldenSampleSetService(db)
    sample_set = service.get_set(set_id)
    if not sample_set or sample_set.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="골든 샘플셋을 찾을 수 없습니다")
    return GoldenSetResponse.model_validate(sample_set)


@golden_router.put("/{set_id}", response_model=GoldenSetResponse)
async def update_golden_set(
    set_id: UUID,
    request: GoldenSetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """골든 샘플셋 수정"""
    service = GoldenSampleSetService(db)
    sample_set = service.get_set(set_id)
    if not sample_set or sample_set.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="골든 샘플셋을 찾을 수 없습니다")

    try:
        updated = service.update_set(set_id, request)
        return GoldenSetResponse.model_validate(updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@golden_router.delete("/{set_id}")
async def delete_golden_set(
    set_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """골든 샘플셋 삭제"""
    service = GoldenSampleSetService(db)
    sample_set = service.get_set(set_id)
    if not sample_set or sample_set.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="골든 샘플셋을 찾을 수 없습니다")

    service.delete_set(set_id)
    return {"success": True}


@golden_router.get("/{set_id}/samples", response_model=GoldenSetSampleListResponse)
async def list_golden_set_samples(
    set_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """골든 샘플셋 샘플 목록"""
    service = GoldenSampleSetService(db)
    sample_set = service.get_set(set_id)
    if not sample_set or sample_set.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="골든 샘플셋을 찾을 수 없습니다")

    samples, total = service.get_samples(set_id, page, page_size)
    return GoldenSetSampleListResponse(
        set_id=set_id,
        samples=[SampleResponse.model_validate(s) for s in samples],
        total=total,
        page=page,
        page_size=page_size,
    )


@golden_router.post("/{set_id}/samples")
async def add_sample_to_golden_set(
    set_id: UUID,
    request: GoldenSetAddSampleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """골든 샘플셋에 샘플 추가"""
    service = GoldenSampleSetService(db)
    sample_set = service.get_set(set_id)
    if not sample_set or sample_set.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="골든 샘플셋을 찾을 수 없습니다")

    try:
        added = service.add_sample(
            set_id=set_id,
            sample_id=request.sample_id,
            added_by=current_user.user_id,
        )
        return {"success": True, "added": added}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@golden_router.delete("/{set_id}/samples/{sample_id}")
async def remove_sample_from_golden_set(
    set_id: UUID,
    sample_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """골든 샘플셋에서 샘플 제거"""
    service = GoldenSampleSetService(db)
    sample_set = service.get_set(set_id)
    if not sample_set or sample_set.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="골든 샘플셋을 찾을 수 없습니다")

    removed = service.remove_sample(set_id, sample_id)
    return {"success": True, "removed": removed}


@golden_router.post("/{set_id}/auto-update", response_model=GoldenSetAutoUpdateResponse)
async def auto_update_golden_set(
    set_id: UUID,
    request: Optional[GoldenSetAutoUpdateRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_role(Role.APPROVER, Role.ADMIN)),
):
    """골든 샘플셋 자동 업데이트"""
    service = GoldenSampleSetService(db)
    sample_set = service.get_set(set_id)
    if not sample_set or sample_set.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="골든 샘플셋을 찾을 수 없습니다")

    result = service.auto_update_set(set_id, request)
    return GoldenSetAutoUpdateResponse(
        set_id=set_id,
        added_count=result["added_count"],
        removed_count=result["removed_count"],
        current_sample_count=result["current_sample_count"],
    )


@golden_router.get("/{set_id}/export")
async def export_golden_set(
    set_id: UUID,
    format: ExportFormat = Query("json"),
    include_metadata: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """골든 샘플셋 내보내기"""
    service = GoldenSampleSetService(db)
    sample_set = service.get_set(set_id)
    if not sample_set or sample_set.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="골든 샘플셋을 찾을 수 없습니다")

    try:
        data, sample_count = service.export_set(
            set_id=set_id,
            format=format,
            include_metadata=include_metadata,
        )

        # Content-Type 결정
        if format == "json":
            media_type = "application/json"
            filename = f"{sample_set.name}_{datetime.utcnow().strftime('%Y%m%d')}.json"
        else:
            media_type = "text/csv"
            filename = f"{sample_set.name}_{datetime.utcnow().strftime('%Y%m%d')}.csv"

        return Response(
            content=data,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Sample-Count": str(sample_count),
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
