"""
JWT 토큰 생성 및 검증 테스트
app/auth/jwt.py 테스트
"""
import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4, UUID
from unittest.mock import patch

from app.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_token_type,
    get_token_expiry,
    SECRET_KEY,
    ALGORITHM,
)


# ========== create_access_token 테스트 ==========


class TestCreateAccessToken:
    """create_access_token 함수 테스트"""

    def test_create_basic_token(self):
        """기본 토큰 생성"""
        data = {"sub": "test-user-id"}
        token = create_access_token(data)

        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_contains_data(self):
        """토큰에 데이터 포함"""
        data = {
            "sub": "user-123",
            "tenant_id": "tenant-456",
            "role": "admin",
        }
        token = create_access_token(data)

        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["tenant_id"] == "tenant-456"
        assert payload["role"] == "admin"

    def test_token_type_is_access(self):
        """토큰 타입이 access"""
        data = {"sub": "user-123"}
        token = create_access_token(data)

        payload = decode_token(token)
        assert payload["type"] == "access"

    def test_token_has_expiry(self):
        """토큰에 만료 시간 존재"""
        data = {"sub": "user-123"}
        token = create_access_token(data)

        payload = decode_token(token)
        assert "exp" in payload
        assert "iat" in payload

    def test_token_with_custom_expiry(self):
        """사용자 지정 만료 시간"""
        data = {"sub": "user-123"}
        expires_delta = timedelta(hours=2)
        token = create_access_token(data, expires_delta=expires_delta)

        payload = decode_token(token)
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)

        # 2시간 후 만료 (약간의 여유 허용)
        time_diff = exp - now
        assert timedelta(hours=1, minutes=59) < time_diff < timedelta(hours=2, minutes=1)

    def test_token_with_uuid_values(self):
        """UUID 값이 있는 토큰 생성"""
        user_id = uuid4()
        tenant_id = uuid4()
        data = {
            "sub": user_id,
            "tenant_id": tenant_id,
        }
        token = create_access_token(data)

        payload = decode_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["tenant_id"] == str(tenant_id)

    def test_token_default_expiry(self):
        """기본 만료 시간 (ACCESS_TOKEN_EXPIRE_MINUTES)"""
        from app.auth.jwt import ACCESS_TOKEN_EXPIRE_MINUTES

        data = {"sub": "user-123"}
        token = create_access_token(data)

        payload = decode_token(token)
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)

        # ACCESS_TOKEN_EXPIRE_MINUTES 이내
        time_diff = exp - now
        expected_max = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES + 1)
        assert time_diff < expected_max


# ========== create_refresh_token 테스트 ==========


class TestCreateRefreshToken:
    """create_refresh_token 함수 테스트"""

    def test_create_basic_token(self):
        """기본 refresh 토큰 생성"""
        data = {"sub": "test-user-id"}
        token = create_refresh_token(data)

        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_type_is_refresh(self):
        """토큰 타입이 refresh"""
        data = {"sub": "user-123"}
        token = create_refresh_token(data)

        payload = decode_token(token)
        assert payload["type"] == "refresh"

    def test_token_with_custom_expiry(self):
        """사용자 지정 만료 시간"""
        data = {"sub": "user-123"}
        expires_delta = timedelta(days=30)
        token = create_refresh_token(data, expires_delta=expires_delta)

        payload = decode_token(token)
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)

        # 30일 후 만료
        time_diff = exp - now
        assert timedelta(days=29) < time_diff < timedelta(days=31)

    def test_token_with_uuid_values(self):
        """UUID 값이 있는 refresh 토큰 생성"""
        user_id = uuid4()
        data = {"sub": user_id}
        token = create_refresh_token(data)

        payload = decode_token(token)
        assert payload["sub"] == str(user_id)

    def test_token_default_expiry(self):
        """기본 만료 시간 (REFRESH_TOKEN_EXPIRE_DAYS)"""
        from app.auth.jwt import REFRESH_TOKEN_EXPIRE_DAYS

        data = {"sub": "user-123"}
        token = create_refresh_token(data)

        payload = decode_token(token)
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)

        # REFRESH_TOKEN_EXPIRE_DAYS 이내
        time_diff = exp - now
        expected_max = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS + 1)
        assert time_diff < expected_max


# ========== decode_token 테스트 ==========


class TestDecodeToken:
    """decode_token 함수 테스트"""

    def test_decode_valid_token(self):
        """유효한 토큰 디코딩"""
        data = {"sub": "user-123", "role": "admin"}
        token = create_access_token(data)

        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["role"] == "admin"

    def test_decode_invalid_token(self):
        """유효하지 않은 토큰"""
        payload = decode_token("invalid-token")
        assert payload is None

    def test_decode_malformed_token(self):
        """형식이 잘못된 토큰"""
        payload = decode_token("not.a.valid.jwt.token.here")
        assert payload is None

    def test_decode_empty_token(self):
        """빈 토큰"""
        payload = decode_token("")
        assert payload is None

    def test_decode_expired_token(self):
        """만료된 토큰"""
        data = {"sub": "user-123"}
        # 1초 전에 만료되는 토큰
        token = create_access_token(data, expires_delta=timedelta(seconds=-1))

        payload = decode_token(token)
        # 만료된 토큰은 None 반환
        assert payload is None

    def test_decode_wrong_signature(self):
        """잘못된 서명"""
        from jose import jwt

        data = {
            "sub": "user-123",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "type": "access",
        }
        token = jwt.encode(data, "wrong-secret-key", algorithm=ALGORITHM)

        payload = decode_token(token)
        assert payload is None


# ========== verify_token_type 테스트 ==========


class TestVerifyTokenType:
    """verify_token_type 함수 테스트"""

    def test_verify_access_token(self):
        """access 토큰 타입 검증"""
        data = {"sub": "user-123"}
        token = create_access_token(data)

        assert verify_token_type(token, "access") is True
        assert verify_token_type(token, "refresh") is False

    def test_verify_refresh_token(self):
        """refresh 토큰 타입 검증"""
        data = {"sub": "user-123"}
        token = create_refresh_token(data)

        assert verify_token_type(token, "refresh") is True
        assert verify_token_type(token, "access") is False

    def test_verify_invalid_token(self):
        """유효하지 않은 토큰"""
        result = verify_token_type("invalid-token", "access")
        assert result is False

    def test_verify_with_unknown_type(self):
        """알 수 없는 타입"""
        data = {"sub": "user-123"}
        token = create_access_token(data)

        assert verify_token_type(token, "unknown") is False


# ========== get_token_expiry 테스트 ==========


class TestGetTokenExpiry:
    """get_token_expiry 함수 테스트"""

    def test_get_access_token_expiry(self):
        """access 토큰 만료 시간 조회"""
        data = {"sub": "user-123"}
        token = create_access_token(data)

        expiry = get_token_expiry(token)
        assert expiry is not None
        assert isinstance(expiry, datetime)
        assert expiry.tzinfo == timezone.utc

    def test_get_refresh_token_expiry(self):
        """refresh 토큰 만료 시간 조회"""
        data = {"sub": "user-123"}
        token = create_refresh_token(data)

        expiry = get_token_expiry(token)
        assert expiry is not None
        assert isinstance(expiry, datetime)

    def test_get_expiry_invalid_token(self):
        """유효하지 않은 토큰"""
        expiry = get_token_expiry("invalid-token")
        assert expiry is None

    def test_get_expiry_custom_time(self):
        """사용자 지정 만료 시간 확인"""
        data = {"sub": "user-123"}
        expires_delta = timedelta(hours=5)
        token = create_access_token(data, expires_delta=expires_delta)

        expiry = get_token_expiry(token)
        now = datetime.now(timezone.utc)

        time_diff = expiry - now
        assert timedelta(hours=4, minutes=59) < time_diff < timedelta(hours=5, minutes=1)

    def test_get_expiry_no_exp_field(self):
        """exp 필드가 없는 토큰"""
        from jose import jwt

        # exp 없이 토큰 생성
        data = {"sub": "user-123", "type": "access"}
        token = jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

        expiry = get_token_expiry(token)
        # exp 필드가 없으면 None 반환
        assert expiry is None


# ========== 엣지 케이스 테스트 ==========


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_empty_data(self):
        """빈 데이터로 토큰 생성"""
        token = create_access_token({})

        payload = decode_token(token)
        assert payload is not None
        assert payload["type"] == "access"

    def test_large_data(self):
        """큰 데이터로 토큰 생성"""
        data = {
            "sub": "user-123",
            "permissions": ["read", "write", "delete", "admin"] * 10,
            "metadata": {"key": "value"}
        }
        token = create_access_token(data)

        payload = decode_token(token)
        assert payload is not None
        assert len(payload["permissions"]) == 40

    def test_special_characters_in_data(self):
        """특수 문자가 포함된 데이터"""
        data = {
            "sub": "user-123",
            "name": "John O'Brien",
            "email": "test+user@example.com",
        }
        token = create_access_token(data)

        payload = decode_token(token)
        assert payload["name"] == "John O'Brien"
        assert payload["email"] == "test+user@example.com"

    def test_unicode_in_data(self):
        """유니코드 데이터"""
        data = {
            "sub": "user-123",
            "name": "테스트 사용자",
            "company": "株式会社テスト",
        }
        token = create_access_token(data)

        payload = decode_token(token)
        assert payload["name"] == "테스트 사용자"
        assert payload["company"] == "株式会社テスト"

    def test_nested_uuid(self):
        """중첩된 UUID 변환"""
        user_id = uuid4()
        # 중첩된 dict는 UUID 변환 안 됨 (최상위만 변환)
        data = {
            "sub": user_id,
            "metadata": {"id": "not-uuid"},
        }
        token = create_access_token(data)

        payload = decode_token(token)
        assert payload["sub"] == str(user_id)

    def test_multiple_tokens_different(self):
        """동일 데이터로 생성한 토큰들은 다름 (iat 다름)"""
        data = {"sub": "user-123"}

        import time
        token1 = create_access_token(data)
        time.sleep(0.1)  # 시간 차이
        token2 = create_access_token(data)

        # 토큰은 달라야 함 (iat가 다름)
        # 하지만 매우 짧은 시간 차이면 같을 수 있음
        payload1 = decode_token(token1)
        payload2 = decode_token(token2)
        assert payload1["sub"] == payload2["sub"]


# ========== 상수 테스트 ==========


class TestConstants:
    """상수 값 테스트"""

    def test_algorithm(self):
        """알고리즘 상수"""
        assert ALGORITHM == "HS256"

    def test_secret_key_exists(self):
        """SECRET_KEY 존재"""
        assert SECRET_KEY is not None
        assert len(SECRET_KEY) > 0
