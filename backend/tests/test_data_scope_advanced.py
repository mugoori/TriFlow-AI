# -*- coding: utf-8 -*-
"""
Advanced DataScope Filtering Tests

제품군, 시프트, 설비 필터링 기능 테스트
"""
import pytest
from unittest.mock import MagicMock

from app.services.data_scope_service import (
    DataScope,
    get_user_data_scope,
    apply_product_family_filter,
    apply_shift_filter,
    apply_equipment_filter,
    apply_data_scope_filter,
    filter_items_by_scope,
)
from app.services.rbac_service import Role


class TestDataScopeExtendedFields:
    """확장된 DataScope 필드 테스트"""

    def test_product_family_access(self):
        """제품군 접근 가능 확인"""
        scope = DataScope(
            user_id="user123",
            tenant_id="tenant123",
            product_families={"AUTOMOTIVE", "ELECTRONICS"},
        )

        assert scope.can_access_product_family("AUTOMOTIVE") is True
        assert scope.can_access_product_family("ELECTRONICS") is True
        assert scope.can_access_product_family("MEDICAL") is False

    def test_shift_code_access(self):
        """시프트 코드 접근 가능 확인"""
        scope = DataScope(
            user_id="user123",
            tenant_id="tenant123",
            shift_codes={"DAY", "NIGHT"},
        )

        assert scope.can_access_shift("DAY") is True
        assert scope.can_access_shift("NIGHT") is True
        assert scope.can_access_shift("SWING") is False

    def test_equipment_id_access(self):
        """설비 ID 접근 가능 확인"""
        scope = DataScope(
            user_id="user123",
            tenant_id="tenant123",
            equipment_ids={"EQ001", "EQ002", "EQ003"},
        )

        assert scope.can_access_equipment("EQ001") is True
        assert scope.can_access_equipment("EQ002") is True
        assert scope.can_access_equipment("EQ999") is False

    def test_all_access_overrides_restrictions(self):
        """all_access=True 시 모든 제약 무시"""
        scope = DataScope(
            user_id="admin123",
            tenant_id="tenant123",
            product_families=set(),  # 빈 집합이어도
            shift_codes=set(),
            equipment_ids=set(),
            all_access=True,
        )

        # 모든 접근 가능
        assert scope.can_access_product_family("ANY_FAMILY") is True
        assert scope.can_access_shift("ANY_SHIFT") is True
        assert scope.can_access_equipment("ANY_EQUIPMENT") is True


class TestGetUserDataScope:
    """get_user_data_scope 함수 테스트"""

    def test_extract_extended_fields_from_metadata(self):
        """user_metadata에서 확장 필드 추출"""
        user = MagicMock()
        user.user_id = "user123"
        user.tenant_id = "tenant123"
        user.role = "user"
        user.user_metadata = {
            "data_scope": {
                "factory_codes": ["F001"],
                "line_codes": ["L001", "L002"],
                "product_families": ["AUTOMOTIVE", "ELECTRONICS"],
                "shift_codes": ["DAY", "NIGHT"],
                "equipment_ids": ["EQ001", "EQ002"],
                "all_access": False,
            }
        }

        scope = get_user_data_scope(user)

        assert scope.factory_codes == {"F001"}
        assert scope.line_codes == {"L001", "L002"}
        assert scope.product_families == {"AUTOMOTIVE", "ELECTRONICS"}
        assert scope.shift_codes == {"DAY", "NIGHT"}
        assert scope.equipment_ids == {"EQ001", "EQ002"}
        assert scope.all_access is False

    def test_default_empty_for_missing_fields(self):
        """metadata에 필드가 없으면 빈 집합"""
        user = MagicMock()
        user.user_id = "user123"
        user.tenant_id = "tenant123"
        user.role = "user"
        user.user_metadata = {
            "data_scope": {
                "factory_codes": ["F001"],
                # product_families 등은 없음
            }
        }

        scope = get_user_data_scope(user)

        assert scope.factory_codes == {"F001"}
        assert scope.product_families == set()
        assert scope.shift_codes == set()
        assert scope.equipment_ids == set()


class TestApplyProductFamilyFilter:
    """apply_product_family_filter 함수 테스트"""

    def test_filter_with_product_families(self):
        """제품군 필터 적용"""
        from sqlalchemy import create_engine, Column, String
        from sqlalchemy.orm import sessionmaker, declarative_base

        Base = declarative_base()

        class Product(Base):
            __tablename__ = "products"
            product_id = Column(String, primary_key=True)
            family = Column(String)

        # 인메모리 DB
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        # 테스트 데이터
        session.add(Product(product_id="P001", family="AUTOMOTIVE"))
        session.add(Product(product_id="P002", family="ELECTRONICS"))
        session.add(Product(product_id="P003", family="MEDICAL"))
        session.commit()

        # DataScope: AUTOMOTIVE만 접근 가능
        scope = DataScope(
            user_id="user123",
            tenant_id="tenant123",
            product_families={"AUTOMOTIVE"},
        )

        # 필터 적용
        query = session.query(Product)
        filtered_query = apply_product_family_filter(query, scope, Product.family)
        results = filtered_query.all()

        # AUTOMOTIVE만 반환되어야 함
        assert len(results) == 1
        assert results[0].family == "AUTOMOTIVE"

        session.close()

    def test_filter_with_all_access(self):
        """all_access=True 시 필터 적용 안됨"""
        from sqlalchemy import create_engine, Column, String
        from sqlalchemy.orm import sessionmaker, declarative_base

        Base = declarative_base()

        class Product(Base):
            __tablename__ = "products"
            product_id = Column(String, primary_key=True)
            family = Column(String)

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        session.add(Product(product_id="P001", family="AUTOMOTIVE"))
        session.add(Product(product_id="P002", family="ELECTRONICS"))
        session.commit()

        # all_access=True
        scope = DataScope(
            user_id="admin123",
            tenant_id="tenant123",
            product_families=set(),  # 빈 집합이어도
            all_access=True,
        )

        query = session.query(Product)
        filtered_query = apply_product_family_filter(query, scope, Product.family)
        results = filtered_query.all()

        # 모든 제품 반환
        assert len(results) == 2

        session.close()


class TestApplyDataScopeFilterAdvanced:
    """apply_data_scope_filter 고급 필터링 테스트"""

    def test_combined_filters(self):
        """복합 필터 적용 (라인 + 제품군 + 시프트)"""
        from sqlalchemy import create_engine, Column, String
        from sqlalchemy.orm import sessionmaker, declarative_base

        Base = declarative_base()

        class Production(Base):
            __tablename__ = "production"
            id = Column(String, primary_key=True)
            line_code = Column(String)
            product_family = Column(String)
            shift_code = Column(String)

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        # 테스트 데이터
        session.add(Production(id="1", line_code="L001", product_family="AUTOMOTIVE", shift_code="DAY"))
        session.add(Production(id="2", line_code="L001", product_family="ELECTRONICS", shift_code="DAY"))
        session.add(Production(id="3", line_code="L002", product_family="AUTOMOTIVE", shift_code="NIGHT"))
        session.commit()

        # DataScope: L001 라인, AUTOMOTIVE 제품군, DAY 시프트만 접근 가능
        scope = DataScope(
            user_id="user123",
            tenant_id="tenant123",
            line_codes={"L001"},
            product_families={"AUTOMOTIVE"},
            shift_codes={"DAY"},
        )

        # 복합 필터 적용
        query = session.query(Production)
        filtered_query = apply_data_scope_filter(
            query,
            scope,
            line_code_column=Production.line_code,
            product_family_column=Production.product_family,
            shift_code_column=Production.shift_code,
        )
        results = filtered_query.all()

        # id=1만 모든 조건 충족 (L001 + AUTOMOTIVE + DAY)
        # 현재 구현은 AND 조건이므로 모든 필터를 통과해야 함
        assert len(results) == 1
        assert results[0].id == "1"

        session.close()


class TestFilterItemsByScopeAdvanced:
    """filter_items_by_scope 고급 필터링 테스트"""

    def test_filter_by_product_family(self):
        """제품군으로 인메모리 리스트 필터링"""
        from dataclasses import dataclass

        @dataclass
        class Product:
            product_id: str
            family: str

        items = [
            Product("P001", "AUTOMOTIVE"),
            Product("P002", "ELECTRONICS"),
            Product("P003", "MEDICAL"),
        ]

        scope = DataScope(
            user_id="user123",
            tenant_id="tenant123",
            product_families={"AUTOMOTIVE", "ELECTRONICS"},
        )

        filtered = filter_items_by_scope(
            items,
            scope,
            get_product_family=lambda x: x.family,
        )

        assert len(filtered) == 2
        assert filtered[0].family == "AUTOMOTIVE"
        assert filtered[1].family == "ELECTRONICS"

    def test_filter_by_shift_code(self):
        """시프트 코드로 인메모리 리스트 필터링"""
        from dataclasses import dataclass

        @dataclass
        class ShiftData:
            id: str
            shift_code: str

        items = [
            ShiftData("1", "DAY"),
            ShiftData("2", "NIGHT"),
            ShiftData("3", "SWING"),
        ]

        scope = DataScope(
            user_id="user123",
            tenant_id="tenant123",
            shift_codes={"DAY", "NIGHT"},
        )

        filtered = filter_items_by_scope(
            items,
            scope,
            get_shift_code=lambda x: x.shift_code,
        )

        assert len(filtered) == 2
        assert filtered[0].shift_code == "DAY"
        assert filtered[1].shift_code == "NIGHT"

    def test_filter_by_equipment_id(self):
        """설비 ID로 인메모리 리스트 필터링"""
        from dataclasses import dataclass

        @dataclass
        class Equipment:
            equipment_id: str
            name: str

        items = [
            Equipment("EQ001", "Machine A"),
            Equipment("EQ002", "Machine B"),
            Equipment("EQ999", "Machine C"),
        ]

        scope = DataScope(
            user_id="user123",
            tenant_id="tenant123",
            equipment_ids={"EQ001", "EQ002"},
        )

        filtered = filter_items_by_scope(
            items,
            scope,
            get_equipment_id=lambda x: x.equipment_id,
        )

        assert len(filtered) == 2
        assert filtered[0].equipment_id == "EQ001"
        assert filtered[1].equipment_id == "EQ002"

    def test_combined_filters_all_match(self):
        """복합 필터 - 모든 조건 일치"""
        from dataclasses import dataclass

        @dataclass
        class ProductionData:
            id: str
            line_code: str
            product_family: str
            shift_code: str
            equipment_id: str

        items = [
            ProductionData("1", "L001", "AUTOMOTIVE", "DAY", "EQ001"),
            ProductionData("2", "L001", "ELECTRONICS", "DAY", "EQ001"),
            ProductionData("3", "L002", "AUTOMOTIVE", "NIGHT", "EQ002"),
        ]

        scope = DataScope(
            user_id="user123",
            tenant_id="tenant123",
            line_codes={"L001"},
            product_families={"AUTOMOTIVE"},
            shift_codes={"DAY"},
            equipment_ids={"EQ001"},
        )

        filtered = filter_items_by_scope(
            items,
            scope,
            get_line_code=lambda x: x.line_code,
            get_product_family=lambda x: x.product_family,
            get_shift_code=lambda x: x.shift_code,
            get_equipment_id=lambda x: x.equipment_id,
        )

        # id=1만 모든 조건 충족
        assert len(filtered) == 1
        assert filtered[0].id == "1"

    def test_all_access_bypasses_all_filters(self):
        """all_access=True 시 모든 필터 무시"""
        from dataclasses import dataclass

        @dataclass
        class Item:
            id: str
            product_family: str

        items = [
            Item("1", "AUTOMOTIVE"),
            Item("2", "ELECTRONICS"),
            Item("3", "MEDICAL"),
        ]

        scope = DataScope(
            user_id="admin123",
            tenant_id="tenant123",
            product_families=set(),  # 빈 집합이어도
            all_access=True,
        )

        filtered = filter_items_by_scope(
            items,
            scope,
            get_product_family=lambda x: x.product_family,
        )

        # 모든 아이템 반환
        assert len(filtered) == 3


class TestBackwardCompatibility:
    """하위 호환성 테스트 - 기존 factory_code, line_code만 사용하는 경우"""

    def test_existing_filters_still_work(self):
        """기존 factory_code, line_code 필터는 계속 작동"""
        scope = DataScope(
            user_id="user123",
            tenant_id="tenant123",
            factory_codes={"F001"},
            line_codes={"L001", "L002"},
            # 새 필드는 비어있음
        )

        assert scope.can_access_factory("F001") is True
        assert scope.can_access_factory("F999") is False
        assert scope.can_access_line("L001") is True
        assert scope.can_access_line("L999") is False

    def test_old_metadata_format_compatible(self):
        """기존 metadata 포맷도 작동 (새 필드 없음)"""
        user = MagicMock()
        user.user_id = "user123"
        user.tenant_id = "tenant123"
        user.role = "user"
        user.user_metadata = {
            "data_scope": {
                "factory_codes": ["F001"],
                "line_codes": ["L001"],
                # product_families 등 신규 필드 없음
            }
        }

        scope = get_user_data_scope(user)

        # 기존 필드는 정상 작동
        assert scope.factory_codes == {"F001"}
        assert scope.line_codes == {"L001"}

        # 새 필드는 빈 집합
        assert scope.product_families == set()
        assert scope.shift_codes == set()
        assert scope.equipment_ids == set()


class TestAdvancedFilteringEdgeCases:
    """엣지 케이스 테스트"""

    def test_empty_scope_blocks_all_access(self):
        """빈 scope는 모든 접근 차단"""
        scope = DataScope(
            user_id="user123",
            tenant_id="tenant123",
            product_families=set(),
            shift_codes=set(),
            equipment_ids=set(),
        )

        assert scope.can_access_product_family("AUTOMOTIVE") is False
        assert scope.can_access_shift("DAY") is False
        assert scope.can_access_equipment("EQ001") is False

    def test_filter_with_none_values(self):
        """None 값 처리 테스트 - None은 통과시킴 (선택적 필드)"""
        from dataclasses import dataclass

        @dataclass
        class Item:
            id: str
            product_family: str

        items = [
            Item("1", "AUTOMOTIVE"),
            Item("2", None),  # None 값
        ]

        scope = DataScope(
            user_id="user123",
            tenant_id="tenant123",
            product_families={"AUTOMOTIVE"},
        )

        filtered = filter_items_by_scope(
            items,
            scope,
            get_product_family=lambda x: x.product_family,
        )

        # None은 필터링되지 않고 통과 (선택적 필드이므로)
        assert len(filtered) == 2
        assert filtered[0].product_family == "AUTOMOTIVE"
        assert filtered[1].product_family is None
