"""
API Key Service 테스트
api_key_service.py의 함수들 테스트
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4


# ========== generate_api_key 테스트 ==========


class TestGenerateApiKey:
    """generate_api_key 함수 테스트"""

    def test_generates_key_with_prefix(self):
        """tfk_ 접두사로 키 생성"""
        from app.services.api_key_service import generate_api_key, API_KEY_PREFIX

        full_key, key_prefix, key_hash = generate_api_key()

        assert full_key.startswith(API_KEY_PREFIX)
        assert key_prefix.startswith(API_KEY_PREFIX)

    def test_key_prefix_length(self):
        """키 접두사 길이 확인"""
        from app.services.api_key_service import generate_api_key

        full_key, key_prefix, key_hash = generate_api_key()

        assert len(key_prefix) == 12  # "tfk_" + 8자

    def test_key_hash_is_sha256(self):
        """SHA-256 해시 길이 확인"""
        from app.services.api_key_service import generate_api_key

        full_key, key_prefix, key_hash = generate_api_key()

        assert len(key_hash) == 64  # SHA-256은 64자 hex

    def test_generates_unique_keys(self):
        """고유한 키 생성"""
        from app.services.api_key_service import generate_api_key

        keys = set()
        for _ in range(100):
            full_key, _, _ = generate_api_key()
            keys.add(full_key)

        assert len(keys) == 100


# ========== hash_api_key 테스트 ==========


class TestHashApiKey:
    """hash_api_key 함수 테스트"""

    def test_hash_is_consistent(self):
        """동일한 키에 대해 동일한 해시"""
        from app.services.api_key_service import hash_api_key

        api_key = "tfk_test123456789"

        hash1 = hash_api_key(api_key)
        hash2 = hash_api_key(api_key)

        assert hash1 == hash2

    def test_different_keys_different_hashes(self):
        """다른 키는 다른 해시"""
        from app.services.api_key_service import hash_api_key

        hash1 = hash_api_key("tfk_key1")
        hash2 = hash_api_key("tfk_key2")

        assert hash1 != hash2

    def test_hash_length(self):
        """해시 길이 확인"""
        from app.services.api_key_service import hash_api_key

        result = hash_api_key("tfk_anykey")

        assert len(result) == 64


# ========== create_api_key 테스트 ==========


class TestCreateApiKey:
    """create_api_key 함수 테스트"""

    def test_create_key_basic(self):
        """기본 키 생성"""
        from app.services.api_key_service import create_api_key

        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.tenant_id = uuid4()
        mock_user.user_id = uuid4()

        api_key, full_key = create_api_key(
            db=mock_db,
            user=mock_user,
            name="테스트 키"
        )

        assert api_key.name == "테스트 키"
        assert api_key.scopes == ["read"]
        assert api_key.expires_at is None
        assert full_key.startswith("tfk_")
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_create_key_with_expiry(self):
        """만료일 있는 키 생성"""
        from app.services.api_key_service import create_api_key

        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.tenant_id = uuid4()
        mock_user.user_id = uuid4()

        api_key, full_key = create_api_key(
            db=mock_db,
            user=mock_user,
            name="만료키",
            expires_in_days=30
        )

        assert api_key.expires_at is not None
        # 만료일은 30일 후 근처여야 함
        expected = datetime.utcnow() + timedelta(days=30)
        diff = abs((api_key.expires_at - expected).total_seconds())
        assert diff < 60  # 1분 이내

    def test_create_key_with_custom_scopes(self):
        """커스텀 스코프 키 생성"""
        from app.services.api_key_service import create_api_key

        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.tenant_id = uuid4()
        mock_user.user_id = uuid4()

        api_key, full_key = create_api_key(
            db=mock_db,
            user=mock_user,
            name="어드민 키",
            scopes=["admin", "read", "write"]
        )

        assert api_key.scopes == ["admin", "read", "write"]

    def test_create_key_with_description(self):
        """설명 포함 키 생성"""
        from app.services.api_key_service import create_api_key

        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.tenant_id = uuid4()
        mock_user.user_id = uuid4()

        api_key, full_key = create_api_key(
            db=mock_db,
            user=mock_user,
            name="설명키",
            description="이 키는 테스트용입니다"
        )

        assert api_key.description == "이 키는 테스트용입니다"


# ========== validate_api_key 테스트 ==========


class TestValidateApiKey:
    """validate_api_key 함수 테스트"""

    def test_validate_invalid_prefix(self):
        """잘못된 접두사"""
        from app.services.api_key_service import validate_api_key

        mock_db = MagicMock()

        result = validate_api_key(mock_db, "invalid_key_prefix")

        assert result is None

    def test_validate_key_not_found(self):
        """키가 없는 경우"""
        from app.services.api_key_service import validate_api_key

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = validate_api_key(mock_db, "tfk_nonexistent_key")

        assert result is None

    def test_validate_expired_key(self):
        """만료된 키"""
        from app.services.api_key_service import validate_api_key

        mock_db = MagicMock()
        mock_key = MagicMock()
        mock_key.expires_at = datetime.utcnow() - timedelta(days=1)  # 어제 만료
        mock_db.query.return_value.filter.return_value.first.return_value = mock_key

        result = validate_api_key(mock_db, "tfk_expired_key_here")

        assert result is None

    def test_validate_missing_scope(self):
        """필요한 스코프 없음"""
        from app.services.api_key_service import validate_api_key

        mock_db = MagicMock()
        mock_key = MagicMock()
        mock_key.expires_at = None
        mock_key.scopes = ["read"]  # write 없음
        mock_db.query.return_value.filter.return_value.first.return_value = mock_key

        result = validate_api_key(mock_db, "tfk_limited_scope_key", required_scope="write")

        assert result is None

    def test_validate_admin_scope_bypasses(self):
        """admin 스코프는 모든 권한 우회"""
        from app.services.api_key_service import validate_api_key

        mock_db = MagicMock()
        mock_key = MagicMock()
        mock_key.expires_at = None
        mock_key.scopes = ["admin"]
        mock_key.last_used_at = None
        mock_key.usage_count = 0
        mock_db.query.return_value.filter.return_value.first.return_value = mock_key

        result = validate_api_key(mock_db, "tfk_admin_key_12345", required_scope="write")

        assert result is mock_key

    def test_validate_updates_usage(self):
        """사용량 업데이트 확인"""
        from app.services.api_key_service import validate_api_key

        mock_db = MagicMock()
        mock_key = MagicMock()
        mock_key.expires_at = None
        mock_key.scopes = ["read"]
        mock_key.usage_count = 5
        mock_db.query.return_value.filter.return_value.first.return_value = mock_key

        result = validate_api_key(mock_db, "tfk_valid_key_12345", client_ip="192.168.1.1")

        assert result.usage_count == 6
        assert result.last_used_ip == "192.168.1.1"
        mock_db.commit.assert_called_once()

    def test_validate_valid_key(self):
        """유효한 키 검증"""
        from app.services.api_key_service import validate_api_key

        mock_db = MagicMock()
        mock_key = MagicMock()
        mock_key.expires_at = datetime.utcnow() + timedelta(days=30)  # 30일 후 만료
        mock_key.scopes = ["read", "write"]
        mock_key.usage_count = 0
        mock_db.query.return_value.filter.return_value.first.return_value = mock_key

        result = validate_api_key(mock_db, "tfk_valid_key_12345", required_scope="read")

        assert result is mock_key


# ========== rotate_api_key 테스트 ==========


class TestRotateApiKey:
    """rotate_api_key 함수 테스트"""

    def test_rotate_key_not_found(self):
        """회전할 키가 없는 경우"""
        from app.services.api_key_service import rotate_api_key

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_user = MagicMock()
        mock_user.tenant_id = uuid4()

        new_key, full_key = rotate_api_key(mock_db, uuid4(), mock_user)

        assert new_key is None
        assert full_key is None

    def test_rotate_key_success(self):
        """키 회전 성공"""
        from app.services.api_key_service import rotate_api_key

        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.tenant_id = uuid4()
        mock_user.user_id = uuid4()

        old_key = MagicMock()
        old_key.name = "원래 키"
        old_key.description = "설명"
        old_key.scopes = ["read", "write"]
        old_key.expires_at = None
        old_key.is_active = True

        mock_db.query.return_value.filter.return_value.first.return_value = old_key

        new_key, full_key = rotate_api_key(mock_db, uuid4(), mock_user)

        assert new_key is not None
        assert full_key.startswith("tfk_")
        assert old_key.is_active is False
        assert old_key.revoked_at is not None

    def test_rotate_key_with_expiry(self):
        """만료일 있는 키 회전"""
        from app.services.api_key_service import rotate_api_key

        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.tenant_id = uuid4()
        mock_user.user_id = uuid4()

        old_key = MagicMock()
        old_key.name = "만료키"
        old_key.description = None
        old_key.scopes = ["read"]
        old_key.expires_at = datetime.utcnow() + timedelta(days=15)
        old_key.is_active = True

        mock_db.query.return_value.filter.return_value.first.return_value = old_key

        new_key, full_key = rotate_api_key(mock_db, uuid4(), mock_user)

        assert new_key is not None


# ========== revoke_api_key 테스트 ==========


class TestRevokeApiKey:
    """revoke_api_key 함수 테스트"""

    def test_revoke_key_not_found(self):
        """폐기할 키가 없는 경우"""
        from app.services.api_key_service import revoke_api_key

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_user = MagicMock()
        mock_user.tenant_id = uuid4()

        result = revoke_api_key(mock_db, uuid4(), mock_user)

        assert result is False

    def test_revoke_key_success(self):
        """키 폐기 성공"""
        from app.services.api_key_service import revoke_api_key

        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.tenant_id = uuid4()

        mock_key = MagicMock()
        mock_key.is_active = True
        mock_db.query.return_value.filter.return_value.first.return_value = mock_key

        result = revoke_api_key(mock_db, uuid4(), mock_user, reason="테스트 폐기")

        assert result is True
        assert mock_key.is_active is False
        assert mock_key.revoked_reason == "테스트 폐기"
        mock_db.commit.assert_called_once()

    def test_revoke_key_default_reason(self):
        """기본 폐기 사유"""
        from app.services.api_key_service import revoke_api_key

        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.tenant_id = uuid4()

        mock_key = MagicMock()
        mock_key.is_active = True
        mock_db.query.return_value.filter.return_value.first.return_value = mock_key

        result = revoke_api_key(mock_db, uuid4(), mock_user)

        assert mock_key.revoked_reason == "Revoked by user"


# ========== list_api_keys 테스트 ==========


class TestListApiKeys:
    """list_api_keys 함수 테스트"""

    def test_list_keys_active_only(self):
        """활성 키만 조회"""
        from app.services.api_key_service import list_api_keys

        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.tenant_id = uuid4()

        mock_keys = [MagicMock(), MagicMock()]
        mock_db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = mock_keys

        result = list_api_keys(mock_db, mock_user)

        assert len(result) == 2

    def test_list_keys_include_revoked(self):
        """폐기된 키 포함 조회"""
        from app.services.api_key_service import list_api_keys

        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.tenant_id = uuid4()

        mock_keys = [MagicMock(), MagicMock(), MagicMock()]
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_keys

        result = list_api_keys(mock_db, mock_user, include_revoked=True)

        assert len(result) == 3


# ========== get_api_key_stats 테스트 ==========


class TestGetApiKeyStats:
    """get_api_key_stats 함수 테스트"""

    def test_get_stats(self):
        """통계 조회"""
        from app.services.api_key_service import get_api_key_stats

        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.tenant_id = uuid4()

        # 각 쿼리 결과 설정
        mock_db.query.return_value.filter.return_value.scalar.side_effect = [
            10,   # total
            5,    # active
            2,    # expired
            3,    # revoked
            100,  # usage_24h
        ]

        result = get_api_key_stats(mock_db, mock_user)

        assert result["total"] == 10
        assert result["active"] == 5
        assert result["expired"] == 2
        assert result["revoked"] == 3
        assert result["usage_24h"] == 100

    def test_get_stats_no_usage(self):
        """사용량 없는 경우"""
        from app.services.api_key_service import get_api_key_stats

        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.tenant_id = uuid4()

        mock_db.query.return_value.filter.return_value.scalar.side_effect = [
            5,     # total
            5,     # active
            0,     # expired
            0,     # revoked
            None,  # usage_24h (None)
        ]

        result = get_api_key_stats(mock_db, mock_user)

        assert result["usage_24h"] == 0


# ========== API_KEY_PREFIX, API_KEY_LENGTH 상수 테스트 ==========


class TestApiKeyConstants:
    """API Key 상수 테스트"""

    def test_api_key_prefix(self):
        """접두사 확인"""
        from app.services.api_key_service import API_KEY_PREFIX

        assert API_KEY_PREFIX == "tfk_"

    def test_api_key_length(self):
        """키 길이 확인"""
        from app.services.api_key_service import API_KEY_LENGTH

        assert API_KEY_LENGTH == 32
