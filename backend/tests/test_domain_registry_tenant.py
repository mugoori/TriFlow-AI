"""
DomainRegistry 테넌트 기반 필터링 테스트
"""
import pytest
from uuid import uuid4
from sqlalchemy.orm import Session

from app.services.domain_registry import DomainRegistry, DomainConfig
from app.models.tenant_config import TenantModule
from app.services.cache_service import CacheService, CacheKeys


@pytest.fixture
def domain_registry():
    """DomainRegistry 인스턴스"""
    return DomainRegistry()


@pytest.fixture
def mock_db(mocker):
    """Mock SQLAlchemy Session"""
    return mocker.MagicMock(spec=Session)


@pytest.fixture
def setup_test_modules(domain_registry):
    """테스트용 도메인 설정"""
    # korea_biopharm 모듈
    domain_registry.domains["korea_biopharm"] = DomainConfig(
        module_code="korea_biopharm",
        name="한국바이오팜",
        keywords=["비타민", "미네랄", "배합비"],
        schema_name="korea_biopharm",
        tables=["recipe_metadata"],
        route_to="BI_GUIDE",
        sample_queries=[],
        description="한국바이오팜 전용"
    )

    # usa_biopharm 모듈
    domain_registry.domains["usa_biopharm"] = DomainConfig(
        module_code="usa_biopharm",
        name="미국바이오팜",
        keywords=["비타민", "vitamin", "supplement"],
        schema_name="usa_biopharm",
        tables=["products"],
        route_to="BI_GUIDE",
        sample_queries=[],
        description="미국바이오팜 전용"
    )


def test_tenant_isolation(domain_registry, mock_db, setup_test_modules):
    """테넌트 격리 검증 - 같은 키워드라도 다른 도메인 반환"""
    tenant_a = str(uuid4())
    tenant_b = str(uuid4())

    # TenantA: korea_biopharm 활성화
    mock_modules_a = [
        TenantModule(
            tenant_id=tenant_a,
            module_code="korea_biopharm",
            is_enabled=True
        )
    ]

    # TenantB: usa_biopharm 활성화
    mock_modules_b = [
        TenantModule(
            tenant_id=tenant_b,
            module_code="usa_biopharm",
            is_enabled=True
        )
    ]

    # Mock DB 쿼리
    def query_side_effect(model):
        class MockQuery:
            def __init__(self, result):
                self.result = result

            def filter(self, *args, **kwargs):
                return self

            def all(self):
                return self.result

        # tenant_id에 따라 다른 결과 반환
        if hasattr(mock_db, '_current_tenant'):
            if mock_db._current_tenant == tenant_a:
                return MockQuery(mock_modules_a)
            elif mock_db._current_tenant == tenant_b:
                return MockQuery(mock_modules_b)
        return MockQuery([])

    mock_db.query = query_side_effect

    # 캐시 초기화
    CacheService.delete(CacheService.generate_key(CacheKeys.TENANT, f"{tenant_a}:modules"))
    CacheService.delete(CacheService.generate_key(CacheKeys.TENANT, f"{tenant_b}:modules"))

    # TenantA 테스트
    mock_db._current_tenant = tenant_a
    result_a = domain_registry.match_domain_for_tenant("비타민C 제품", tenant_a, mock_db)
    assert result_a is not None
    assert result_a.module_code == "korea_biopharm"

    # TenantB 테스트
    mock_db._current_tenant = tenant_b
    result_b = domain_registry.match_domain_for_tenant("비타민C 제품", tenant_b, mock_db)
    assert result_b is not None
    assert result_b.module_code == "usa_biopharm"


def test_no_enabled_modules_fallback(domain_registry, mock_db, setup_test_modules):
    """활성 모듈 없을 때 기존 로직 폴백"""
    tenant_id = str(uuid4())

    # Mock: 활성 모듈 없음
    def query_side_effect(model):
        class MockQuery:
            def filter(self, *args, **kwargs):
                return self

            def all(self):
                return []

        return MockQuery()

    mock_db.query = query_side_effect

    # 캐시 초기화
    CacheService.delete(CacheService.generate_key(CacheKeys.TENANT, f"{tenant_id}:modules"))

    # 기존 match_domain() 호출됨
    result = domain_registry.match_domain_for_tenant("비타민C 제품", tenant_id, mock_db)

    # 기존 로직으로 폴백되어 첫 번째 도메인 반환
    assert result is not None
    assert result.module_code in ["korea_biopharm", "usa_biopharm"]


@pytest.mark.skip(reason="Redis 연결 필요 - 실제 환경에서만 테스트")
def test_cache_hit_performance(domain_registry, mock_db, setup_test_modules, mocker):
    """캐싱 동작 검증 - 2차 호출 시 DB 쿼리 안 함"""
    tenant_id = str(uuid4())

    mock_modules = [
        TenantModule(
            tenant_id=tenant_id,
            module_code="korea_biopharm",
            is_enabled=True
        )
    ]

    query_call_count = 0

    def query_side_effect(model):
        nonlocal query_call_count
        query_call_count += 1

        class MockQuery:
            def filter(self, *args, **kwargs):
                return self

            def all(self):
                return mock_modules

        return MockQuery()

    mock_db.query = query_side_effect

    # 캐시 초기화
    cache_key = CacheService.generate_key(CacheKeys.TENANT, f"{tenant_id}:modules")
    CacheService.delete(cache_key)

    # 1차 호출: DB 쿼리 (cache miss)
    result_1 = domain_registry.match_domain_for_tenant("비타민C", tenant_id, mock_db)
    assert result_1 is not None
    assert query_call_count == 1

    # 2차 호출: 캐시 사용 (DB 쿼리 안 함)
    result_2 = domain_registry.match_domain_for_tenant("비타민C", tenant_id, mock_db)
    assert result_2 is not None
    assert query_call_count == 1  # 여전히 1 (DB 쿼리 안 함!)


def test_fallback_without_tenant_id(domain_registry, setup_test_modules):
    """tenant_id 없을 때 기존 match_domain() 동작 유지"""
    # 기존 메서드 호출
    result = domain_registry.match_domain("비타민C 제품")

    # 정상 동작
    assert result is not None
    assert result.module_code in ["korea_biopharm", "usa_biopharm"]


def test_keyword_not_in_enabled_modules(domain_registry, mock_db, setup_test_modules):
    """활성화된 모듈에 키워드가 없으면 매칭 안 됨"""
    tenant_id = str(uuid4())

    # 활성 모듈: korea_biopharm (키워드: 비타민, 미네랄, 배합비)
    mock_modules = [
        TenantModule(
            tenant_id=tenant_id,
            module_code="korea_biopharm",
            is_enabled=True
        )
    ]

    def query_side_effect(model):
        class MockQuery:
            def filter(self, *args, **kwargs):
                return self

            def all(self):
                return mock_modules

        return MockQuery()

    mock_db.query = query_side_effect

    # 캐시 초기화
    CacheService.delete(CacheService.generate_key(CacheKeys.TENANT, f"{tenant_id}:modules"))

    # "vitamin" 키워드는 usa_biopharm에만 있음 → 매칭 안 됨
    result = domain_registry.match_domain_for_tenant("find vitamin products", tenant_id, mock_db)
    assert result is None
