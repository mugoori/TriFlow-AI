# -*- coding: utf-8 -*-
"""
사용자 관리 API 라우터
테넌트 내 사용자 CRUD 및 RBAC/Data Scope 관리
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, SensorData
from app.auth.dependencies import get_current_user
from app.services.rbac_service import (
    Role,
    ROLE_HIERARCHY,
    ROLE_PERMISSIONS,
    require_role,
)
from app.schemas.user import (
    UserListResponse,
    UserDetailResponse,
    UserRoleUpdateRequest,
    DataScopeUpdateRequest,
    RoleListResponse,
    RoleInfo,
    RolePermissionsResponse,
    PermissionInfo,
    FactoryLineResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# 역할 메타데이터
ROLE_METADATA = {
    Role.ADMIN: {
        "label": "Admin",
        "description": "테넌트 전체 관리 권한. 모든 리소스에 대한 CRUD 및 사용자 관리 가능.",
    },
    Role.APPROVER: {
        "label": "Approver",
        "description": "규칙/워크플로우 승인 권한. 읽기, 실행, 승인 가능.",
    },
    Role.OPERATOR: {
        "label": "Operator",
        "description": "일상 운영 담당. 읽기, 실행, 센서 데이터 관리 가능.",
    },
    Role.USER: {
        "label": "User",
        "description": "기본 사용자. 생성/수정 가능, 삭제/승인 불가.",
    },
    Role.VIEWER: {
        "label": "Viewer",
        "description": "읽기 전용. 조회만 가능, 채팅 허용.",
    },
}


@router.get("/", response_model=UserListResponse)
async def list_users(
    skip: int = Query(0, ge=0, description="건너뛸 레코드 수"),
    limit: int = Query(50, ge=1, le=100, description="조회할 레코드 수"),
    search: Optional[str] = Query(None, description="이메일/이름 검색"),
    role_filter: Optional[str] = Query(None, description="역할 필터"),
    _: None = Depends(require_role(Role.ADMIN, Role.APPROVER)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    테넌트 내 사용자 목록 조회

    - admin, approver만 접근 가능
    - 같은 테넌트의 사용자만 조회
    """
    query = db.query(User).filter(User.tenant_id == current_user.tenant_id)

    # 검색 필터
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (User.email.ilike(search_term)) |
            (User.display_name.ilike(search_term)) |
            (User.username.ilike(search_term))
        )

    # 역할 필터
    if role_filter:
        query = query.filter(User.role == role_filter)

    # 전체 개수
    total = query.count()

    # 페이징
    users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()

    return UserListResponse(
        users=[UserDetailResponse.from_user(u) for u in users],
        total=total,
    )


@router.get("/roles", response_model=RoleListResponse)
async def list_roles(
    current_user: User = Depends(get_current_user),
):
    """
    역할 목록 조회

    - 모든 인증된 사용자 접근 가능
    - 5-Tier 역할 계층 정보 반환
    """
    roles = []
    for role in Role:
        metadata = ROLE_METADATA.get(role, {"label": role.value, "description": ""})
        roles.append(RoleInfo(
            role=role.value,
            level=ROLE_HIERARCHY.get(role, 0),
            label=metadata["label"],
            description=metadata["description"],
        ))

    # 레벨 내림차순 정렬
    roles.sort(key=lambda r: r.level, reverse=True)

    return RoleListResponse(roles=roles)


@router.get("/roles/{role}/permissions", response_model=RolePermissionsResponse)
async def get_role_permissions(
    role: str,
    current_user: User = Depends(get_current_user),
):
    """
    역할별 권한 조회

    - 모든 인증된 사용자 접근 가능
    - 해당 역할의 모든 권한 목록 반환
    """
    # 역할 유효성 검사
    try:
        role_enum = Role(role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {role}. Valid roles: {[r.value for r in Role]}",
        )

    permissions = ROLE_PERMISSIONS.get(role_enum, set())
    permissions_list = sorted(list(permissions))

    # 상세 정보 생성
    permissions_detail = []
    for perm in permissions_list:
        parts = perm.split(":")
        if len(parts) == 2:
            permissions_detail.append(PermissionInfo(
                resource=parts[0],
                action=parts[1],
                permission=perm,
            ))

    return RolePermissionsResponse(
        role=role,
        level=ROLE_HIERARCHY.get(role_enum, 0),
        permissions=permissions_list,
        permissions_detail=permissions_detail,
    )


@router.get("/factory-lines", response_model=FactoryLineResponse)
async def get_factory_lines(
    _: None = Depends(require_role(Role.ADMIN)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    공장/라인 코드 목록 조회

    - admin만 접근 가능
    - 센서 데이터에서 고유한 공장/라인 코드 추출
    """
    # 라인 코드 추출 (센서 데이터에서)
    line_codes_query = (
        db.query(SensorData.line_code)
        .filter(SensorData.tenant_id == current_user.tenant_id)
        .distinct()
    )
    line_codes = [row[0] for row in line_codes_query.all() if row[0]]

    # 공장 코드는 라인 코드에서 파생하거나 별도 테이블에서 조회
    # 현재는 라인 코드의 앞부분을 공장 코드로 가정 (예: L001 -> F001)
    # 실제 환경에서는 별도 마스터 테이블 사용 권장
    factory_codes = list(set([
        lc.split("-")[0] if "-" in lc else lc[:2] + "00"
        for lc in line_codes
    ])) if line_codes else []

    return FactoryLineResponse(
        factory_codes=sorted(factory_codes),
        line_codes=sorted(line_codes),
    )


@router.get("/{user_id}", response_model=UserDetailResponse)
async def get_user(
    user_id: UUID,
    _: None = Depends(require_role(Role.ADMIN, Role.APPROVER)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    사용자 상세 조회

    - admin, approver만 접근 가능
    - 같은 테넌트의 사용자만 조회
    """
    user = db.query(User).filter(
        User.user_id == user_id,
        User.tenant_id == current_user.tenant_id,
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserDetailResponse.from_user(user)


@router.patch("/{user_id}/role")
async def update_user_role(
    user_id: UUID,
    request: UserRoleUpdateRequest,
    _: None = Depends(require_role(Role.ADMIN)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    사용자 역할 변경

    - admin만 접근 가능
    - 자기 자신의 역할은 변경 불가
    """
    # 자기 자신 체크
    if user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role",
        )

    # 대상 사용자 조회
    target_user = db.query(User).filter(
        User.user_id == user_id,
        User.tenant_id == current_user.tenant_id,
    ).first()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # 역할 유효성 검사
    try:
        Role(request.role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {request.role}",
        )

    old_role = target_user.role
    target_user.role = request.role
    db.commit()

    logger.info(
        f"User role changed: user={target_user.email}, "
        f"old_role={old_role}, new_role={request.role}, "
        f"changed_by={current_user.email}"
    )

    return {
        "message": "Role updated successfully",
        "user_id": str(user_id),
        "old_role": old_role,
        "new_role": request.role,
    }


@router.patch("/{user_id}/data-scope")
async def update_user_data_scope(
    user_id: UUID,
    request: DataScopeUpdateRequest,
    _: None = Depends(require_role(Role.ADMIN)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    사용자 Data Scope 설정

    - admin만 접근 가능
    - user_metadata['data_scope']에 저장
    """
    # 대상 사용자 조회
    target_user = db.query(User).filter(
        User.user_id == user_id,
        User.tenant_id == current_user.tenant_id,
    ).first()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # user_metadata 업데이트
    metadata = target_user.user_metadata or {}
    old_scope = metadata.get("data_scope", {})

    metadata["data_scope"] = {
        "factory_codes": request.factory_codes,
        "line_codes": request.line_codes,
        "all_access": request.all_access,
    }

    target_user.user_metadata = metadata

    # SQLAlchemy가 JSONB 변경을 감지하도록 명시적 플래그 설정
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(target_user, "user_metadata")

    db.commit()

    logger.info(
        f"User data scope changed: user={target_user.email}, "
        f"old_scope={old_scope}, new_scope={metadata['data_scope']}, "
        f"changed_by={current_user.email}"
    )

    return {
        "message": "Data scope updated successfully",
        "user_id": str(user_id),
        "data_scope": metadata["data_scope"],
    }


@router.get("/me/data-scope", response_model=DataScopeUpdateRequest)
async def get_my_data_scope(
    current_user: User = Depends(get_current_user),
):
    """
    현재 사용자의 Data Scope 조회

    - 모든 인증된 사용자 접근 가능
    - 자신의 접근 범위 확인용
    """
    # admin은 전체 접근
    if current_user.role == "admin":
        return DataScopeUpdateRequest(
            factory_codes=[],
            line_codes=[],
            all_access=True,
        )

    metadata = current_user.user_metadata or {}
    data_scope = metadata.get("data_scope", {})

    return DataScopeUpdateRequest(
        factory_codes=data_scope.get("factory_codes", []),
        line_codes=data_scope.get("line_codes", []),
        all_access=data_scope.get("all_access", False),
    )


@router.get("/{user_id}/data-scope", response_model=DataScopeUpdateRequest)
async def get_user_data_scope(
    user_id: UUID,
    _: None = Depends(require_role(Role.ADMIN)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    사용자 Data Scope 조회

    - admin만 접근 가능
    """
    # 대상 사용자 조회
    target_user = db.query(User).filter(
        User.user_id == user_id,
        User.tenant_id == current_user.tenant_id,
    ).first()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    metadata = target_user.user_metadata or {}
    data_scope = metadata.get("data_scope", {})

    return DataScopeUpdateRequest(
        factory_codes=data_scope.get("factory_codes", []),
        line_codes=data_scope.get("line_codes", []),
        all_access=data_scope.get("all_access", False),
    )
