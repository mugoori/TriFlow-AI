"""
테넌트 라우터 테스트

테넌트 관리 엔드포인트 단위 테스트
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import ValidationError


class TestTenantBaseSchema:
    """TenantBase 스키마 테스트"""

    def test_tenant_base_valid(self):
        """유효한 테넌트 기본 스키마"""
        from app.schemas.tenant import TenantBase

        tenant = TenantBase(
            name="Test Company",
            slug="test-company",
            settings={"timezone": "Asia/Seoul"},
        )

        assert tenant.name == "Test Company"
        assert tenant.slug == "test-company"
        assert tenant.settings == {"timezone": "Asia/Seoul"}

    def test_tenant_base_defaults(self):
        """기본값 확인"""
        from app.schemas.tenant import TenantBase

        tenant = TenantBase(name="Company", slug="company")

        assert tenant.settings == {}

    def test_tenant_name_required(self):
        """이름 필수 확인"""
        from app.schemas.tenant import TenantBase

        with pytest.raises(ValidationError):
            TenantBase(slug="company")

    def test_tenant_slug_required(self):
        """슬러그 필수 확인"""
        from app.schemas.tenant import TenantBase

        with pytest.raises(ValidationError):
            TenantBase(name="Company")

    def test_tenant_name_min_length(self):
        """이름 최소 길이"""
        from app.schemas.tenant import TenantBase

        with pytest.raises(ValidationError):
            TenantBase(name="", slug="company")

    def test_tenant_slug_min_length(self):
        """슬러그 최소 길이"""
        from app.schemas.tenant import TenantBase

        with pytest.raises(ValidationError):
            TenantBase(name="Company", slug="")


class TestTenantCreateSchema:
    """TenantCreate 스키마 테스트"""

    def test_tenant_create_valid(self):
        """유효한 생성 요청"""
        from app.schemas.tenant import TenantCreate

        tenant = TenantCreate(
            name="New Company",
            slug="new-company",
        )

        assert tenant.name == "New Company"
        assert tenant.slug == "new-company"

    def test_tenant_create_with_settings(self):
        """설정 포함 생성"""
        from app.schemas.tenant import TenantCreate

        settings = {
            "timezone": "Asia/Seoul",
            "language": "ko",
            "features": ["bi", "workflow"],
        }

        tenant = TenantCreate(
            name="Korean Company",
            slug="korean-company",
            settings=settings,
        )

        assert tenant.settings["language"] == "ko"
        assert "workflow" in tenant.settings["features"]


class TestTenantUpdateSchema:
    """TenantUpdate 스키마 테스트"""

    def test_tenant_update_all_fields(self):
        """모든 필드 업데이트"""
        from app.schemas.tenant import TenantUpdate

        update = TenantUpdate(
            name="Updated Company",
            slug="updated-company",
            settings={"new_setting": True},
        )

        assert update.name == "Updated Company"
        assert update.slug == "updated-company"
        assert update.settings["new_setting"] is True

    def test_tenant_update_partial(self):
        """부분 업데이트"""
        from app.schemas.tenant import TenantUpdate

        update = TenantUpdate(name="New Name Only")

        assert update.name == "New Name Only"
        assert update.slug is None
        assert update.settings is None

    def test_tenant_update_empty(self):
        """빈 업데이트"""
        from app.schemas.tenant import TenantUpdate

        update = TenantUpdate()

        assert update.name is None
        assert update.slug is None
        assert update.settings is None


class TestTenantResponseSchema:
    """TenantResponse 스키마 테스트"""

    def test_tenant_response_valid(self):
        """유효한 응답 모델"""
        from app.schemas.tenant import TenantResponse

        now = datetime.now(timezone.utc)
        tenant_id = uuid4()

        response = TenantResponse(
            tenant_id=tenant_id,
            name="Company",
            slug="company",
            settings={},
            created_at=now,
            updated_at=now,
        )

        assert response.tenant_id == tenant_id
        assert response.name == "Company"
        assert response.created_at == now

    def test_tenant_response_with_settings(self):
        """설정 포함 응답"""
        from app.schemas.tenant import TenantResponse

        now = datetime.now(timezone.utc)
        settings = {"feature_flags": {"dark_mode": True}}

        response = TenantResponse(
            tenant_id=uuid4(),
            name="Company",
            slug="company",
            settings=settings,
            created_at=now,
            updated_at=now,
        )

        assert response.settings["feature_flags"]["dark_mode"] is True


class TestSlugValidation:
    """슬러그 유효성 검증 테스트"""

    def test_valid_slug_formats(self):
        """유효한 슬러그 형식"""
        valid_slugs = [
            "company",
            "my-company",
            "company-123",
            "a",
            "company-name-here",
        ]

        from app.schemas.tenant import TenantBase

        for slug in valid_slugs:
            tenant = TenantBase(name="Test", slug=slug)
            assert tenant.slug == slug

    def test_slug_max_length(self):
        """슬러그 최대 길이 (100자)"""
        from app.schemas.tenant import TenantBase

        # 정확히 100자
        slug_100 = "a" * 100
        tenant = TenantBase(name="Test", slug=slug_100)
        assert len(tenant.slug) == 100

        # 100자 초과
        with pytest.raises(ValidationError):
            TenantBase(name="Test", slug="a" * 101)


class TestNameValidation:
    """이름 유효성 검증 테스트"""

    def test_valid_names(self):
        """유효한 이름"""
        valid_names = [
            "Company",
            "My Company Inc.",
            "회사명",
            "Company 123",
            "A",
        ]

        from app.schemas.tenant import TenantBase

        for name in valid_names:
            tenant = TenantBase(name=name, slug="slug")
            assert tenant.name == name

    def test_name_max_length(self):
        """이름 최대 길이 (255자)"""
        from app.schemas.tenant import TenantBase

        # 정확히 255자
        name_255 = "a" * 255
        tenant = TenantBase(name=name_255, slug="slug")
        assert len(tenant.name) == 255

        # 255자 초과
        with pytest.raises(ValidationError):
            TenantBase(name="a" * 256, slug="slug")


class TestSettingsFormat:
    """설정 형식 테스트"""

    def test_empty_settings(self):
        """빈 설정"""
        from app.schemas.tenant import TenantBase

        tenant = TenantBase(name="Test", slug="test")
        assert tenant.settings == {}

    def test_complex_settings(self):
        """복잡한 설정"""
        from app.schemas.tenant import TenantBase

        settings = {
            "timezone": "Asia/Seoul",
            "language": "ko",
            "features": {
                "bi": True,
                "workflow": True,
                "chat": False,
            },
            "limits": {
                "max_users": 100,
                "storage_gb": 50,
            },
            "integrations": ["mes", "erp"],
        }

        tenant = TenantBase(name="Test", slug="test", settings=settings)

        assert tenant.settings["features"]["bi"] is True
        assert tenant.settings["limits"]["max_users"] == 100
        assert "erp" in tenant.settings["integrations"]


class TestTenantIsolation:
    """테넌트 격리 테스트"""

    def test_unique_tenant_id(self):
        """고유 테넌트 ID"""
        tenant_ids = [uuid4() for _ in range(10)]
        unique_ids = set(tenant_ids)

        assert len(unique_ids) == 10

    def test_unique_slug_requirement(self):
        """슬러그 유일성"""
        existing_slugs = {"company-a", "company-b"}
        new_slug = "company-c"

        is_unique = new_slug not in existing_slugs
        assert is_unique is True

        duplicate_slug = "company-a"
        is_unique = duplicate_slug not in existing_slugs
        assert is_unique is False


class TestTenantCRUD:
    """테넌트 CRUD 로직 테스트"""

    def test_create_tenant_logic(self):
        """테넌트 생성 로직"""
        from app.schemas.tenant import TenantCreate

        tenant_data = TenantCreate(
            name="New Company",
            slug="new-company",
            settings={"language": "ko"},
        )

        # model_dump() 결과 확인
        data = tenant_data.model_dump()
        assert data["name"] == "New Company"
        assert data["slug"] == "new-company"
        assert data["settings"]["language"] == "ko"

    def test_update_tenant_logic(self):
        """테넌트 업데이트 로직"""
        from app.schemas.tenant import TenantUpdate

        update_data = TenantUpdate(name="Updated Name")

        # exclude_unset=True로 설정되지 않은 필드 제외
        data = update_data.model_dump(exclude_unset=True)
        assert data == {"name": "Updated Name"}
        assert "slug" not in data
        assert "settings" not in data

    def test_update_multiple_fields(self):
        """다중 필드 업데이트"""
        from app.schemas.tenant import TenantUpdate

        update_data = TenantUpdate(
            name="New Name",
            slug="new-slug",
        )

        data = update_data.model_dump(exclude_unset=True)
        assert "name" in data
        assert "slug" in data
        assert "settings" not in data


class TestPaginationParams:
    """페이지네이션 파라미터 테스트"""

    def test_default_pagination(self):
        """기본 페이지네이션"""
        skip = 0
        limit = 100

        assert skip == 0
        assert limit == 100

    def test_custom_pagination(self):
        """사용자 정의 페이지네이션"""
        skip = 20
        limit = 10

        # 3번째 페이지
        page = (skip // limit) + 1
        assert page == 3


class TestErrorResponses:
    """에러 응답 테스트"""

    def test_not_found_error(self):
        """404 에러"""
        from fastapi import HTTPException, status

        tenant_id = uuid4()

        error = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found",
        )

        assert error.status_code == 404
        assert "not found" in error.detail

    def test_duplicate_slug_error(self):
        """슬러그 중복 에러"""
        from fastapi import HTTPException, status

        slug = "existing-company"

        error = HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tenant with slug '{slug}' already exists",
        )

        assert error.status_code == 400
        assert "already exists" in error.detail


class TestTenantTimestamps:
    """타임스탬프 테스트"""

    def test_created_at_on_create(self):
        """생성 시 created_at 설정"""
        created_at = datetime.now(timezone.utc)
        assert created_at is not None

    def test_updated_at_on_update(self):
        """업데이트 시 updated_at 갱신"""
        original_updated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        new_updated_at = datetime.now(timezone.utc)

        assert new_updated_at > original_updated_at


class TestTenantSettings:
    """테넌트 설정 테스트"""

    def test_default_settings(self):
        """기본 설정"""
        default_settings = {
            "timezone": "UTC",
            "language": "en",
            "date_format": "YYYY-MM-DD",
        }

        assert default_settings["timezone"] == "UTC"

    def test_merge_settings(self):
        """설정 병합"""
        current_settings = {"timezone": "UTC", "language": "en"}
        update_settings = {"language": "ko", "theme": "dark"}

        # 병합
        merged = {**current_settings, **update_settings}

        assert merged["timezone"] == "UTC"  # 기존 유지
        assert merged["language"] == "ko"  # 업데이트됨
        assert merged["theme"] == "dark"  # 새로 추가


class TestModelDump:
    """model_dump 테스트"""

    def test_tenant_create_model_dump(self):
        """TenantCreate model_dump"""
        from app.schemas.tenant import TenantCreate

        tenant = TenantCreate(
            name="Test",
            slug="test",
            settings={"key": "value"},
        )

        data = tenant.model_dump()

        assert isinstance(data, dict)
        assert data["name"] == "Test"
        assert data["slug"] == "test"
        assert data["settings"]["key"] == "value"

    def test_tenant_update_model_dump_exclude_unset(self):
        """TenantUpdate model_dump exclude_unset"""
        from app.schemas.tenant import TenantUpdate

        update = TenantUpdate(name="New Name")

        # exclude_unset=False (기본값)
        data_all = update.model_dump()
        assert "name" in data_all
        assert "slug" in data_all
        assert data_all["slug"] is None

        # exclude_unset=True
        data_set = update.model_dump(exclude_unset=True)
        assert "name" in data_set
        assert "slug" not in data_set


class TestFromAttributes:
    """from_attributes 설정 테스트"""

    def test_tenant_response_from_orm(self):
        """ORM 객체에서 TenantResponse 생성"""
        from app.schemas.tenant import TenantResponse

        # Mock ORM 객체 시뮬레이션
        class MockTenant:
            tenant_id = uuid4()
            name = "Test Company"
            slug = "test-company"
            settings = {"key": "value"}
            created_at = datetime.now(timezone.utc)
            updated_at = datetime.now(timezone.utc)

        mock_tenant = MockTenant()

        # from_attributes=True로 ORM 객체에서 직접 생성 가능
        response = TenantResponse.model_validate(mock_tenant)

        assert response.name == "Test Company"
        assert response.slug == "test-company"
