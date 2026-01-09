# -*- coding: utf-8 -*-
"""
Data Scope Service
사용자별 데이터 접근 범위 필터링

5-Tier RBAC의 Data Scope Filter 구현:
- admin: 전체 데이터 접근
- 기타 역할: user_metadata['data_scope']에 정의된 범위만 접근
"""
import logging
from dataclasses import dataclass, field
from typing import Set, Any, TypeVar, Optional

from fastapi import Depends
from sqlalchemy.orm import Query

from app.models import User
from app.auth.dependencies import get_current_user
from app.services.rbac_service import Role

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class DataScope:
    """
    사용자의 데이터 접근 범위

    Attributes:
        user_id: 사용자 ID
        tenant_id: 테넌트 ID
        factory_codes: 접근 가능한 공장 코드 집합
        line_codes: 접근 가능한 라인 코드 집합
        all_access: 전체 접근 권한 여부 (admin)
    """
    user_id: str
    tenant_id: str
    factory_codes: Set[str] = field(default_factory=set)
    line_codes: Set[str] = field(default_factory=set)
    all_access: bool = False

    def can_access_factory(self, factory_code: str) -> bool:
        """특정 공장에 접근 가능한지 확인"""
        if self.all_access:
            return True
        return factory_code in self.factory_codes

    def can_access_line(self, line_code: str) -> bool:
        """특정 라인에 접근 가능한지 확인"""
        if self.all_access:
            return True
        return line_code in self.line_codes


def get_user_data_scope(user: User) -> DataScope:
    """
    사용자의 데이터 접근 범위 조회

    user.user_metadata에서 data_scope 정보를 추출합니다.
    Expected metadata format:
    {
        "data_scope": {
            "factory_codes": ["F001", "F002"],
            "line_codes": ["L001", "L002", "L003"],
            "all_access": false
        }
    }

    Args:
        user: 사용자 객체

    Returns:
        DataScope 객체
    """
    user_id = str(user.user_id) if user.user_id else ""
    tenant_id = str(user.tenant_id) if user.tenant_id else ""

    # admin은 전체 접근
    if user.role == Role.ADMIN or user.role == "admin":
        return DataScope(
            user_id=user_id,
            tenant_id=tenant_id,
            all_access=True,
        )

    # user_metadata에서 data_scope 추출
    metadata = user.user_metadata or {}
    data_scope_config = metadata.get("data_scope", {})

    factory_codes = set(data_scope_config.get("factory_codes", []))
    line_codes = set(data_scope_config.get("line_codes", []))
    all_access = data_scope_config.get("all_access", False)

    return DataScope(
        user_id=user_id,
        tenant_id=tenant_id,
        factory_codes=factory_codes,
        line_codes=line_codes,
        all_access=all_access,
    )


async def get_data_scope(
    current_user: User = Depends(get_current_user),
) -> DataScope:
    """
    FastAPI 의존성: 현재 사용자의 DataScope 반환

    사용법:
        @router.get("/sensors")
        async def list_sensors(
            scope: DataScope = Depends(get_data_scope),
        ):
            # scope.line_codes 로 필터링
            ...
    """
    return get_user_data_scope(current_user)


def apply_factory_filter(
    query: Query,
    scope: DataScope,
    factory_code_column: Any,
) -> Query:
    """
    쿼리에 공장 코드 필터 적용

    Args:
        query: SQLAlchemy 쿼리
        scope: 데이터 범위
        factory_code_column: 공장 코드 컬럼 (e.g., SensorData.factory_code)

    Returns:
        필터링된 쿼리
    """
    if scope.all_access:
        return query

    if not scope.factory_codes:
        # 접근 가능한 공장이 없으면 빈 결과 반환
        return query.filter(False)

    return query.filter(factory_code_column.in_(scope.factory_codes))


def apply_line_filter(
    query: Query,
    scope: DataScope,
    line_code_column: Any,
) -> Query:
    """
    쿼리에 라인 코드 필터 적용

    Args:
        query: SQLAlchemy 쿼리
        scope: 데이터 범위
        line_code_column: 라인 코드 컬럼 (e.g., SensorData.line_code)

    Returns:
        필터링된 쿼리
    """
    if scope.all_access:
        return query

    if not scope.line_codes:
        # 접근 가능한 라인이 없으면 빈 결과 반환
        return query.filter(False)

    return query.filter(line_code_column.in_(scope.line_codes))


def apply_data_scope_filter(
    query: Query,
    scope: DataScope,
    factory_code_column: Optional[Any] = None,
    line_code_column: Optional[Any] = None,
) -> Query:
    """
    쿼리에 Data Scope 필터 적용 (통합 함수)

    공장 코드와 라인 코드 필터를 모두 적용합니다.
    둘 다 지정된 경우 OR 조건으로 적용됩니다.

    Args:
        query: SQLAlchemy 쿼리
        scope: 데이터 범위
        factory_code_column: 공장 코드 컬럼 (선택)
        line_code_column: 라인 코드 컬럼 (선택)

    Returns:
        필터링된 쿼리

    사용 예시:
        query = db.query(SensorData)
        query = apply_data_scope_filter(
            query,
            scope,
            line_code_column=SensorData.line_code,
        )
    """
    if scope.all_access:
        return query

    # 공장 코드로 필터링
    if factory_code_column is not None:
        query = apply_factory_filter(query, scope, factory_code_column)

    # 라인 코드로 필터링
    if line_code_column is not None:
        query = apply_line_filter(query, scope, line_code_column)

    return query


def filter_items_by_scope(
    items: list[T],
    scope: DataScope,
    get_factory_code: Optional[callable] = None,
    get_line_code: Optional[callable] = None,
) -> list[T]:
    """
    인메모리 리스트에 Data Scope 필터 적용

    DB 쿼리가 아닌 Python 리스트에서 필터링할 때 사용합니다.

    Args:
        items: 필터링할 아이템 리스트
        scope: 데이터 범위
        get_factory_code: 아이템에서 공장 코드를 추출하는 함수
        get_line_code: 아이템에서 라인 코드를 추출하는 함수

    Returns:
        필터링된 리스트

    사용 예시:
        filtered = filter_items_by_scope(
            items,
            scope,
            get_line_code=lambda x: x.line_code,
        )
    """
    if scope.all_access:
        return items

    def is_accessible(item: T) -> bool:
        # 공장 코드 체크
        if get_factory_code is not None:
            factory_code = get_factory_code(item)
            if factory_code and not scope.can_access_factory(factory_code):
                return False

        # 라인 코드 체크
        if get_line_code is not None:
            line_code = get_line_code(item)
            if line_code and not scope.can_access_line(line_code):
                return False

        return True

    return [item for item in items if is_accessible(item)]


class DataScopeChecker:
    """
    클래스 기반 Data Scope 체커

    특정 컬럼에 대해 재사용 가능한 필터를 제공합니다.

    사용 예시:
        sensor_scope = DataScopeChecker("line_code")

        @router.get("/sensors")
        async def list_sensors(
            db: Session = Depends(get_db),
            current_user: User = Depends(sensor_scope.check),
        ):
            query = db.query(SensorData)
            query = sensor_scope.apply_filter(query, current_user, SensorData.line_code)
            ...
    """

    def __init__(self, scope_type: str = "line_code"):
        """
        Args:
            scope_type: 필터 타입 ("line_code" 또는 "factory_code")
        """
        self.scope_type = scope_type

    async def check(
        self,
        current_user: User = Depends(get_current_user),
    ) -> User:
        """의존성 체커 - 사용자 반환"""
        return current_user

    def apply_filter(
        self,
        query: Query,
        user: User,
        column: Any,
    ) -> Query:
        """쿼리에 필터 적용"""
        scope = get_user_data_scope(user)

        if self.scope_type == "factory_code":
            return apply_factory_filter(query, scope, column)
        else:
            return apply_line_filter(query, scope, column)
