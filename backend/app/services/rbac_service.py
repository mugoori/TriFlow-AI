"""
RBAC (Role-Based Access Control) 서비스
역할 기반 접근 제어 로직
"""
import logging
from enum import Enum
from functools import wraps
from typing import Optional, Set

from fastapi import HTTPException, status, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)


class Role(str, Enum):
    """사용자 역할"""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class Resource(str, Enum):
    """리소스 타입"""
    WORKFLOWS = "workflows"
    RULESETS = "rulesets"
    SENSORS = "sensors"
    EXPERIMENTS = "experiments"
    USERS = "users"
    SETTINGS = "settings"
    AUDIT = "audit"
    FEEDBACK = "feedback"
    PROPOSALS = "proposals"
    AGENTS = "agents"


class Action(str, Enum):
    """액션 타입"""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"


# 역할별 기본 권한 정의 (DB 없이도 동작하도록 인메모리 정의)
ROLE_PERMISSIONS: dict[str, Set[str]] = {
    Role.ADMIN: {
        # Admin은 모든 권한
        f"{resource.value}:{action.value}"
        for resource in Resource
        for action in Action
    },
    Role.USER: {
        # User: CRUD + Execute (삭제 제외, 사용자/감사 관리 제외)
        "workflows:create", "workflows:read", "workflows:update", "workflows:execute",
        "rulesets:create", "rulesets:read", "rulesets:update", "rulesets:execute",
        "sensors:read",
        "experiments:create", "experiments:read", "experiments:update", "experiments:execute",
        "settings:read", "settings:update",
        "feedback:create", "feedback:read",
        "proposals:read", "proposals:update",
        "agents:execute",
    },
    Role.VIEWER: {
        # Viewer: 조회만
        "workflows:read",
        "rulesets:read",
        "sensors:read",
        "experiments:read",
        "settings:read",
        "feedback:read",
        "proposals:read",
        "agents:execute",  # 채팅은 허용
    },
}


def has_permission(user: User, resource: str, action: str) -> bool:
    """
    사용자가 특정 리소스/액션에 대한 권한이 있는지 확인

    Args:
        user: 사용자 객체
        resource: 리소스 타입
        action: 액션 타입

    Returns:
        권한 여부
    """
    if not user or not user.role:
        return False

    permission = f"{resource}:{action}"
    user_permissions = ROLE_PERMISSIONS.get(user.role, set())

    return permission in user_permissions


def check_permission(resource: str, action: str):
    """
    권한 체크 의존성 생성자

    사용법:
        @router.get("/items")
        async def get_items(
            _: None = Depends(check_permission("items", "read")),
            current_user: User = Depends(get_current_user)
        ):
            ...

    Args:
        resource: 리소스 타입
        action: 액션 타입

    Returns:
        FastAPI 의존성 함수
    """
    async def permission_checker(
        current_user: User = Depends(get_current_user),
    ):
        if not has_permission(current_user, resource, action):
            logger.warning(
                f"Permission denied: user={current_user.email}, "
                f"role={current_user.role}, permission={resource}:{action}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {resource}:{action} requires higher privileges",
            )
        return None

    return permission_checker


def require_role(*roles: str):
    """
    특정 역할 요구 의존성 생성자

    사용법:
        @router.delete("/users/{id}")
        async def delete_user(
            _: None = Depends(require_role("admin")),
            ...
        ):
            ...

    Args:
        roles: 허용되는 역할 목록

    Returns:
        FastAPI 의존성 함수
    """
    async def role_checker(
        current_user: User = Depends(get_current_user),
    ):
        if current_user.role not in roles:
            logger.warning(
                f"Role check failed: user={current_user.email}, "
                f"role={current_user.role}, required={roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of the following roles: {', '.join(roles)}",
            )
        return None

    return role_checker


def get_user_permissions(user: User) -> Set[str]:
    """
    사용자의 모든 권한 목록 조회

    Args:
        user: 사용자 객체

    Returns:
        권한 문자열 집합
    """
    if not user or not user.role:
        return set()

    return ROLE_PERMISSIONS.get(user.role, set())


# 편의를 위한 사전 정의된 의존성
require_admin = require_role(Role.ADMIN)
require_admin_or_user = require_role(Role.ADMIN, Role.USER)


class PermissionChecker:
    """
    클래스 기반 권한 체커
    라우터에서 재사용하기 편함
    """

    def __init__(self, resource: str, action: str):
        self.resource = resource
        self.action = action

    async def __call__(
        self,
        current_user: User = Depends(get_current_user),
    ):
        if not has_permission(current_user, self.resource, self.action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {self.resource}:{self.action}",
            )
        return current_user


# 리소스별 권한 체커 인스턴스
class WorkflowsPermission:
    create = PermissionChecker(Resource.WORKFLOWS, Action.CREATE)
    read = PermissionChecker(Resource.WORKFLOWS, Action.READ)
    update = PermissionChecker(Resource.WORKFLOWS, Action.UPDATE)
    delete = PermissionChecker(Resource.WORKFLOWS, Action.DELETE)
    execute = PermissionChecker(Resource.WORKFLOWS, Action.EXECUTE)


class RulesetsPermission:
    create = PermissionChecker(Resource.RULESETS, Action.CREATE)
    read = PermissionChecker(Resource.RULESETS, Action.READ)
    update = PermissionChecker(Resource.RULESETS, Action.UPDATE)
    delete = PermissionChecker(Resource.RULESETS, Action.DELETE)
    execute = PermissionChecker(Resource.RULESETS, Action.EXECUTE)


class ExperimentsPermission:
    create = PermissionChecker(Resource.EXPERIMENTS, Action.CREATE)
    read = PermissionChecker(Resource.EXPERIMENTS, Action.READ)
    update = PermissionChecker(Resource.EXPERIMENTS, Action.UPDATE)
    delete = PermissionChecker(Resource.EXPERIMENTS, Action.DELETE)
    execute = PermissionChecker(Resource.EXPERIMENTS, Action.EXECUTE)


class UsersPermission:
    create = PermissionChecker(Resource.USERS, Action.CREATE)
    read = PermissionChecker(Resource.USERS, Action.READ)
    update = PermissionChecker(Resource.USERS, Action.UPDATE)
    delete = PermissionChecker(Resource.USERS, Action.DELETE)
