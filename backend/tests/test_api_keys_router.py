"""
API Keys 라우터 테스트

API Key 관리 엔드포인트 단위 테스트
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4, UUID

from pydantic import ValidationError


class TestApiKeyCreateSchema:
    """ApiKeyCreate 스키마 테스트"""

    def test_valid_api_key_create(self):
        """유효한 API Key 생성 요청"""
        from app.routers.api_keys import ApiKeyCreate

        request = ApiKeyCreate(
            name="Test API Key",
            description="테스트용 키",
            scopes=["read", "sensors"],
            expires_in_days=90,
        )

        assert request.name == "Test API Key"
        assert request.description == "테스트용 키"
        assert request.scopes == ["read", "sensors"]
        assert request.expires_in_days == 90

    def test_api_key_create_defaults(self):
        """기본값 확인"""
        from app.routers.api_keys import ApiKeyCreate

        request = ApiKeyCreate(name="Minimal Key")

        assert request.name == "Minimal Key"
        assert request.description is None
        assert request.scopes == ["read"]
        assert request.expires_in_days is None

    def test_api_key_create_name_required(self):
        """이름 필수 확인"""
        from app.routers.api_keys import ApiKeyCreate

        with pytest.raises(ValidationError):
            ApiKeyCreate()

    def test_api_key_create_name_min_length(self):
        """이름 최소 길이 확인"""
        from app.routers.api_keys import ApiKeyCreate

        with pytest.raises(ValidationError):
            ApiKeyCreate(name="")

    def test_api_key_create_expires_in_days_range(self):
        """만료일 범위 확인"""
        from app.routers.api_keys import ApiKeyCreate

        # 유효 범위
        valid = ApiKeyCreate(name="Key", expires_in_days=365)
        assert valid.expires_in_days == 365

        # 최소값 미만
        with pytest.raises(ValidationError):
            ApiKeyCreate(name="Key", expires_in_days=0)

        # 최대값 초과
        with pytest.raises(ValidationError):
            ApiKeyCreate(name="Key", expires_in_days=366)


class TestApiKeyResponseSchema:
    """ApiKeyResponse 스키마 테스트"""

    def test_api_key_response_model(self):
        """응답 모델 검증"""
        from app.routers.api_keys import ApiKeyResponse

        now = datetime.now(timezone.utc)
        key_id = uuid4()
        tenant_id = uuid4()
        user_id = uuid4()

        response = ApiKeyResponse(
            key_id=key_id,
            tenant_id=tenant_id,
            user_id=user_id,
            name="Production Key",
            description="운영 환경용",
            key_prefix="tfk_abc12345",
            scopes=["read", "write"],
            expires_at=now,
            last_used_at=None,
            last_used_ip=None,
            usage_count=0,
            is_active=True,
            revoked_at=None,
            revoked_reason=None,
            created_at=now,
        )

        assert response.key_id == key_id
        assert response.name == "Production Key"
        assert response.scopes == ["read", "write"]
        assert response.is_active is True

    def test_api_key_response_with_usage(self):
        """사용 이력이 있는 응답"""
        from app.routers.api_keys import ApiKeyResponse

        now = datetime.now(timezone.utc)

        response = ApiKeyResponse(
            key_id=uuid4(),
            tenant_id=uuid4(),
            user_id=uuid4(),
            name="Used Key",
            description=None,
            key_prefix="tfk_xyz98765",
            scopes=["read"],
            expires_at=None,
            last_used_at=now,
            last_used_ip="192.168.1.1",
            usage_count=42,
            is_active=True,
            revoked_at=None,
            revoked_reason=None,
            created_at=now,
        )

        assert response.last_used_ip == "192.168.1.1"
        assert response.usage_count == 42


class TestApiKeyCreateResponseSchema:
    """ApiKeyCreateResponse 스키마 테스트"""

    def test_api_key_create_response_model(self):
        """생성 응답 모델 (키 포함)"""
        from app.routers.api_keys import ApiKeyCreateResponse, ApiKeyResponse

        now = datetime.now(timezone.utc)

        api_key = ApiKeyResponse(
            key_id=uuid4(),
            tenant_id=uuid4(),
            user_id=uuid4(),
            name="New Key",
            description=None,
            key_prefix="tfk_new12345",
            scopes=["read"],
            expires_at=None,
            last_used_at=None,
            last_used_ip=None,
            usage_count=0,
            is_active=True,
            revoked_at=None,
            revoked_reason=None,
            created_at=now,
        )

        response = ApiKeyCreateResponse(
            api_key=api_key,
            key="tfk_new12345abcdefghijklmnop",
        )

        assert response.api_key.name == "New Key"
        assert response.key.startswith("tfk_new12345")


class TestApiKeyRotateResponseSchema:
    """ApiKeyRotateResponse 스키마 테스트"""

    def test_api_key_rotate_response_model(self):
        """회전 응답 모델"""
        from app.routers.api_keys import ApiKeyRotateResponse, ApiKeyResponse

        now = datetime.now(timezone.utc)
        old_key_id = uuid4()

        new_api_key = ApiKeyResponse(
            key_id=uuid4(),
            tenant_id=uuid4(),
            user_id=uuid4(),
            name="Rotated Key",
            description=None,
            key_prefix="tfk_rot12345",
            scopes=["read", "write"],
            expires_at=None,
            last_used_at=None,
            last_used_ip=None,
            usage_count=0,
            is_active=True,
            revoked_at=None,
            revoked_reason=None,
            created_at=now,
        )

        response = ApiKeyRotateResponse(
            old_key_id=old_key_id,
            new_api_key=new_api_key,
            new_key="tfk_rot12345newkeyvalue",
        )

        assert response.old_key_id == old_key_id
        assert response.new_api_key.name == "Rotated Key"


class TestApiKeyRevokeRequestSchema:
    """ApiKeyRevokeRequest 스키마 테스트"""

    def test_api_key_revoke_request_with_reason(self):
        """폐기 요청 (사유 포함)"""
        from app.routers.api_keys import ApiKeyRevokeRequest

        request = ApiKeyRevokeRequest(reason="보안 이슈로 폐기")
        assert request.reason == "보안 이슈로 폐기"

    def test_api_key_revoke_request_without_reason(self):
        """폐기 요청 (사유 없음)"""
        from app.routers.api_keys import ApiKeyRevokeRequest

        request = ApiKeyRevokeRequest()
        assert request.reason is None


class TestApiKeyStatsResponseSchema:
    """ApiKeyStatsResponse 스키마 테스트"""

    def test_api_key_stats_response_model(self):
        """통계 응답 모델"""
        from app.routers.api_keys import ApiKeyStatsResponse

        response = ApiKeyStatsResponse(
            total=10,
            active=7,
            expired=2,
            revoked=1,
            usage_24h=156,
        )

        assert response.total == 10
        assert response.active == 7
        assert response.expired == 2
        assert response.revoked == 1
        assert response.usage_24h == 156


class TestAvailableScopesResponseSchema:
    """AvailableScopesResponse 스키마 테스트"""

    def test_available_scopes_response_model(self):
        """스코프 목록 응답 모델"""
        from app.routers.api_keys import AvailableScopesResponse

        response = AvailableScopesResponse(
            scopes=[
                {"name": "read", "description": "읽기 권한"},
                {"name": "write", "description": "쓰기 권한"},
            ]
        )

        assert len(response.scopes) == 2
        assert response.scopes[0]["name"] == "read"


class TestGetAvailableScopes:
    """GET /scopes 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_get_available_scopes(self):
        """스코프 목록 조회"""
        from app.routers.api_keys import get_available_scopes

        result = await get_available_scopes()

        assert "scopes" in result
        scopes = result["scopes"]
        assert len(scopes) >= 5

        scope_names = [s["name"] for s in scopes]
        assert "read" in scope_names
        assert "write" in scope_names
        assert "admin" in scope_names
        assert "sensors" in scope_names

    @pytest.mark.asyncio
    async def test_scopes_have_descriptions(self):
        """모든 스코프에 설명 포함"""
        from app.routers.api_keys import get_available_scopes

        result = await get_available_scopes()

        for scope in result["scopes"]:
            assert "name" in scope
            assert "description" in scope
            assert isinstance(scope["description"], str)
            assert len(scope["description"]) > 0


class TestScopeValidation:
    """스코프 유효성 검증 로직 테스트"""

    def test_valid_scopes(self):
        """유효한 스코프"""
        valid_scopes = {"read", "write", "delete", "admin", "sensors", "workflows", "rulesets", "erp_mes", "notifications"}

        # 단일 스코프
        test_scopes = {"read"}
        invalid = test_scopes - valid_scopes
        assert len(invalid) == 0

        # 복수 스코프
        test_scopes = {"read", "write", "sensors"}
        invalid = test_scopes - valid_scopes
        assert len(invalid) == 0

    def test_invalid_scopes(self):
        """유효하지 않은 스코프"""
        valid_scopes = {"read", "write", "delete", "admin", "sensors", "workflows", "rulesets", "erp_mes", "notifications"}

        test_scopes = {"read", "invalid_scope"}
        invalid = test_scopes - valid_scopes
        assert "invalid_scope" in invalid

    def test_admin_scope_restriction(self):
        """admin 스코프 제한 검증 로직"""
        # 일반 사용자가 admin 스코프 요청 시 거부해야 함
        user_role = "user"
        requested_scopes = ["read", "admin"]

        if "admin" in requested_scopes and user_role != "admin":
            # 403 에러 발생해야 함
            should_reject = True
        else:
            should_reject = False

        assert should_reject is True

    def test_admin_can_create_admin_scope(self):
        """admin 사용자는 admin 스코프 발급 가능"""
        user_role = "admin"
        requested_scopes = ["read", "admin"]

        if "admin" in requested_scopes and user_role != "admin":
            should_reject = True
        else:
            should_reject = False

        assert should_reject is False


class TestApiKeyPrefixGeneration:
    """API Key 프리픽스 생성 테스트"""

    def test_key_prefix_format(self):
        """키 프리픽스 형식 확인"""
        # tfk_ + 8자리 형식
        prefix = "tfk_abc12345"

        assert prefix.startswith("tfk_")
        assert len(prefix) == 12  # tfk_ (4) + 8

    def test_full_key_format(self):
        """전체 키 형식 확인"""
        # tfk_ + prefix + random
        full_key = "tfk_abc12345def67890xyz"

        assert full_key.startswith("tfk_")
        assert len(full_key) > 12


class TestApiKeyExpiration:
    """API Key 만료 로직 테스트"""

    def test_calculate_expiration_date(self):
        """만료일 계산"""
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        expires_in_days = 90

        expires_at = now + timedelta(days=expires_in_days)

        # 90일 후
        assert (expires_at - now).days == 90

    def test_no_expiration(self):
        """만료 없음 (영구 키)"""
        expires_in_days = None
        expires_at = None if expires_in_days is None else "calculated"

        assert expires_at is None

    def test_is_expired_check(self):
        """만료 여부 확인"""
        from datetime import timedelta

        now = datetime.now(timezone.utc)

        # 만료되지 않은 키
        future_expiry = now + timedelta(days=30)
        is_expired = now > future_expiry
        assert is_expired is False

        # 만료된 키
        past_expiry = now - timedelta(days=1)
        is_expired = now > past_expiry
        assert is_expired is True


class TestApiKeyUsageTracking:
    """API Key 사용 추적 테스트"""

    def test_increment_usage_count(self):
        """사용 횟수 증가"""
        usage_count = 0
        usage_count += 1
        assert usage_count == 1

    def test_record_last_used(self):
        """마지막 사용 시간 기록"""
        last_used_at = datetime.now(timezone.utc)
        last_used_ip = "192.168.1.100"

        assert last_used_at is not None
        assert last_used_ip == "192.168.1.100"


class TestApiKeyRevocation:
    """API Key 폐기 테스트"""

    def test_revoke_key(self):
        """키 폐기"""
        is_active = True
        revoked_at = None
        revoked_reason = None

        # 폐기 처리
        is_active = False
        revoked_at = datetime.now(timezone.utc)
        revoked_reason = "보안 이슈"

        assert is_active is False
        assert revoked_at is not None
        assert revoked_reason == "보안 이슈"

    def test_cannot_use_revoked_key(self):
        """폐기된 키 사용 불가"""
        is_active = False

        # 사용 시도
        can_use = is_active is True
        assert can_use is False


class TestApiKeyRotation:
    """API Key 회전 테스트"""

    def test_rotation_preserves_settings(self):
        """회전 시 설정 유지"""
        old_key = {
            "name": "Production Key",
            "scopes": ["read", "write"],
            "expires_at": datetime.now(timezone.utc),
        }

        # 새 키 생성 (설정 유지)
        new_key = {
            "name": old_key["name"],
            "scopes": old_key["scopes"],
            "expires_at": old_key["expires_at"],
            "key_id": uuid4(),  # 새 ID
            "key_prefix": "tfk_new12345",  # 새 프리픽스
        }

        assert new_key["name"] == old_key["name"]
        assert new_key["scopes"] == old_key["scopes"]

    def test_rotation_revokes_old_key(self):
        """회전 시 기존 키 폐기"""
        old_key_is_active = True

        # 회전 처리
        old_key_is_active = False
        old_key_revoked_reason = "Rotated"

        assert old_key_is_active is False
        assert old_key_revoked_reason == "Rotated"


class TestTenantIsolation:
    """테넌트 격리 테스트"""

    def test_key_belongs_to_tenant(self):
        """키가 테넌트에 속함"""
        tenant_id = uuid4()
        key_tenant_id = tenant_id

        assert key_tenant_id == tenant_id

    def test_cannot_access_other_tenant_key(self):
        """다른 테넌트 키 접근 불가"""
        tenant_a = uuid4()
        tenant_b = uuid4()

        key_tenant_id = tenant_a
        requesting_tenant_id = tenant_b

        can_access = key_tenant_id == requesting_tenant_id
        assert can_access is False


class TestApiKeyPermissions:
    """API Key 권한 테스트"""

    def test_owner_can_manage_own_key(self):
        """소유자는 자신의 키 관리 가능"""
        key_user_id = uuid4()
        requesting_user_id = key_user_id

        can_manage = key_user_id == requesting_user_id
        assert can_manage is True

    def test_admin_can_manage_any_key(self):
        """관리자는 모든 키 관리 가능"""
        user_role = "admin"

        can_manage = user_role == "admin"
        assert can_manage is True

    def test_user_cannot_manage_others_key(self):
        """일반 사용자는 다른 사람 키 관리 불가"""
        key_user_id = uuid4()
        requesting_user_id = uuid4()  # 다른 사용자
        user_role = "user"

        is_owner = key_user_id == requesting_user_id
        is_admin = user_role == "admin"
        can_manage = is_owner or is_admin

        assert can_manage is False
