"""
Auth Dependencies 테스트
app/auth/dependencies.py의 인증 의존성 테스트
"""
import pytest
from uuid import uuid4
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials


# ========== 상수 테스트 ==========


class TestConstants:
    """상수 테스트"""

    def test_api_key_prefix(self):
        """API Key 접두사"""
        from app.auth.dependencies import API_KEY_PREFIX

        assert API_KEY_PREFIX == "tfk_"

    def test_valid_scopes(self):
        """유효한 스코프 목록"""
        from app.auth.dependencies import VALID_SCOPES

        assert "read" in VALID_SCOPES
        assert "write" in VALID_SCOPES
        assert "delete" in VALID_SCOPES
        assert "admin" in VALID_SCOPES
        assert "sensors" in VALID_SCOPES
        assert "workflows" in VALID_SCOPES
        assert "rulesets" in VALID_SCOPES
        assert "erp_mes" in VALID_SCOPES
        assert "notifications" in VALID_SCOPES

    def test_security_scheme(self):
        """Bearer 토큰 스키마"""
        from app.auth.dependencies import security

        assert security is not None
        assert security.auto_error is False


# ========== _authenticate_with_jwt 테스트 ==========


class TestAuthenticateWithJWT:
    """_authenticate_with_jwt 테스트"""

    @pytest.mark.asyncio
    async def test_invalid_token(self):
        """유효하지 않은 토큰"""
        from app.auth.dependencies import _authenticate_with_jwt

        mock_db = MagicMock()

        with patch("app.auth.dependencies.decode_token", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await _authenticate_with_jwt("invalid-token", mock_db)

            assert exc_info.value.status_code == 401
            assert "Invalid or expired token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_wrong_token_type(self):
        """잘못된 토큰 타입"""
        from app.auth.dependencies import _authenticate_with_jwt

        mock_db = MagicMock()

        with patch(
            "app.auth.dependencies.decode_token",
            return_value={"type": "refresh", "sub": str(uuid4())},
        ):
            with pytest.raises(HTTPException) as exc_info:
                await _authenticate_with_jwt("refresh-token", mock_db)

            assert exc_info.value.status_code == 401
            assert "Invalid token type" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_missing_sub(self):
        """sub 필드 누락"""
        from app.auth.dependencies import _authenticate_with_jwt

        mock_db = MagicMock()

        with patch(
            "app.auth.dependencies.decode_token", return_value={"type": "access"}
        ):
            with pytest.raises(HTTPException) as exc_info:
                await _authenticate_with_jwt("token", mock_db)

            assert exc_info.value.status_code == 401
            assert "Invalid token payload" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invalid_user_id_format(self):
        """잘못된 사용자 ID 형식"""
        from app.auth.dependencies import _authenticate_with_jwt

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.side_effect = Exception(
            "Invalid UUID"
        )

        with patch(
            "app.auth.dependencies.decode_token",
            return_value={"type": "access", "sub": "not-a-uuid"},
        ):
            with pytest.raises(HTTPException) as exc_info:
                await _authenticate_with_jwt("token", mock_db)

            assert exc_info.value.status_code == 401
            assert "Invalid user ID format" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_user_not_found(self):
        """사용자 없음"""
        from app.auth.dependencies import _authenticate_with_jwt

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        user_id = str(uuid4())
        with patch(
            "app.auth.dependencies.decode_token",
            return_value={"type": "access", "sub": user_id},
        ):
            with pytest.raises(HTTPException) as exc_info:
                await _authenticate_with_jwt("token", mock_db)

            assert exc_info.value.status_code == 401
            assert "User not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_success(self):
        """JWT 인증 성공"""
        from app.auth.dependencies import _authenticate_with_jwt

        mock_user = MagicMock()
        mock_user.user_id = uuid4()

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        user_id = str(mock_user.user_id)
        with patch(
            "app.auth.dependencies.decode_token",
            return_value={"type": "access", "sub": user_id},
        ):
            result = await _authenticate_with_jwt("valid-token", mock_db)

            assert result == mock_user


# ========== _authenticate_with_api_key 테스트 ==========


class TestAuthenticateWithApiKey:
    """_authenticate_with_api_key 테스트"""

    @pytest.mark.asyncio
    async def test_invalid_api_key(self):
        """유효하지 않은 API Key"""
        from app.auth.dependencies import _authenticate_with_api_key

        mock_db = MagicMock()
        mock_request = MagicMock()
        mock_request.headers.get.return_value = ""
        mock_request.client.host = "127.0.0.1"

        with patch(
            "app.services.api_key_service.validate_api_key", return_value=None
        ):
            with pytest.raises(HTTPException) as exc_info:
                await _authenticate_with_api_key("tfk_invalid", mock_request, mock_db)

            assert exc_info.value.status_code == 401
            assert "Invalid or expired API Key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_api_key_owner_not_found(self):
        """API Key 소유자 없음"""
        from app.auth.dependencies import _authenticate_with_api_key

        mock_api_key = MagicMock()
        mock_api_key.user_id = uuid4()

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        mock_request = MagicMock()
        mock_request.headers.get.return_value = ""
        mock_request.client.host = "127.0.0.1"

        with patch(
            "app.services.api_key_service.validate_api_key", return_value=mock_api_key
        ):
            with pytest.raises(HTTPException) as exc_info:
                await _authenticate_with_api_key("tfk_valid", mock_request, mock_db)

            assert exc_info.value.status_code == 401
            assert "API Key owner not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_success(self):
        """API Key 인증 성공"""
        from app.auth.dependencies import _authenticate_with_api_key

        mock_user = MagicMock()
        mock_user.user_id = uuid4()

        mock_api_key = MagicMock()
        mock_api_key.user_id = mock_user.user_id

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        mock_request = MagicMock()
        mock_request.headers.get.return_value = "192.168.1.1"
        mock_request.client.host = "127.0.0.1"

        with patch(
            "app.services.api_key_service.validate_api_key", return_value=mock_api_key
        ):
            result = await _authenticate_with_api_key("tfk_valid", mock_request, mock_db)

            assert result == mock_user

    @pytest.mark.asyncio
    async def test_ip_extraction_from_forwarded_header(self):
        """X-Forwarded-For 헤더에서 IP 추출"""
        from app.auth.dependencies import _authenticate_with_api_key

        mock_user = MagicMock()
        mock_api_key = MagicMock()
        mock_api_key.user_id = uuid4()

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        mock_request = MagicMock()
        mock_request.headers.get.return_value = "10.0.0.1, 192.168.1.1"
        mock_request.client.host = "127.0.0.1"

        with patch(
            "app.services.api_key_service.validate_api_key", return_value=mock_api_key
        ) as mock_validate:
            await _authenticate_with_api_key("tfk_valid", mock_request, mock_db)

            # validate_api_key가 첫 번째 IP로 호출되었는지 확인
            mock_validate.assert_called_once()
            call_kwargs = mock_validate.call_args[1]
            assert call_kwargs["client_ip"] == "10.0.0.1"

    @pytest.mark.asyncio
    async def test_ip_extraction_from_client_host(self):
        """client.host에서 IP 추출"""
        from app.auth.dependencies import _authenticate_with_api_key

        mock_user = MagicMock()
        mock_api_key = MagicMock()
        mock_api_key.user_id = uuid4()

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        mock_request = MagicMock()
        mock_request.headers.get.return_value = ""
        mock_request.client.host = "192.168.1.100"

        with patch(
            "app.services.api_key_service.validate_api_key", return_value=mock_api_key
        ) as mock_validate:
            await _authenticate_with_api_key("tfk_valid", mock_request, mock_db)

            call_kwargs = mock_validate.call_args[1]
            assert call_kwargs["client_ip"] == "192.168.1.100"

    @pytest.mark.asyncio
    async def test_no_request(self):
        """Request 없음"""
        from app.auth.dependencies import _authenticate_with_api_key

        mock_user = MagicMock()
        mock_api_key = MagicMock()
        mock_api_key.user_id = uuid4()

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        with patch(
            "app.services.api_key_service.validate_api_key", return_value=mock_api_key
        ) as mock_validate:
            await _authenticate_with_api_key("tfk_valid", None, mock_db)

            call_kwargs = mock_validate.call_args[1]
            assert call_kwargs["client_ip"] is None


# ========== get_current_user 테스트 ==========


class TestGetCurrentUser:
    """get_current_user 테스트"""

    @pytest.mark.asyncio
    async def test_no_credentials(self):
        """인증 정보 없음"""
        from app.auth.dependencies import get_current_user

        mock_db = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                credentials=None, x_api_key=None, request=None, db=mock_db
            )

        assert exc_info.value.status_code == 401
        assert "Not authenticated" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_api_key_header(self):
        """X-API-Key 헤더로 인증"""
        from app.auth.dependencies import get_current_user

        mock_user = MagicMock()
        mock_db = MagicMock()
        mock_request = MagicMock()

        with patch(
            "app.auth.dependencies._authenticate_with_api_key",
            return_value=mock_user,
        ) as mock_auth:
            result = await get_current_user(
                credentials=None,
                x_api_key="tfk_test_key",
                request=mock_request,
                db=mock_db,
            )

            assert result == mock_user
            mock_auth.assert_called_once_with("tfk_test_key", mock_request, mock_db)

    @pytest.mark.asyncio
    async def test_bearer_jwt_token(self):
        """Bearer JWT 토큰으로 인증"""
        from app.auth.dependencies import get_current_user

        mock_user = MagicMock()
        mock_db = MagicMock()

        credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        credentials.credentials = "jwt_token_here"

        with patch(
            "app.auth.dependencies._authenticate_with_jwt",
            return_value=mock_user,
        ) as mock_auth:
            result = await get_current_user(
                credentials=credentials, x_api_key=None, request=None, db=mock_db
            )

            assert result == mock_user
            mock_auth.assert_called_once_with("jwt_token_here", mock_db)

    @pytest.mark.asyncio
    async def test_bearer_api_key(self):
        """Bearer 토큰으로 API Key 전달"""
        from app.auth.dependencies import get_current_user

        mock_user = MagicMock()
        mock_db = MagicMock()
        mock_request = MagicMock()

        credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        credentials.credentials = "tfk_bearer_api_key"

        with patch(
            "app.auth.dependencies._authenticate_with_api_key",
            return_value=mock_user,
        ) as mock_auth:
            result = await get_current_user(
                credentials=credentials,
                x_api_key=None,
                request=mock_request,
                db=mock_db,
            )

            assert result == mock_user
            mock_auth.assert_called_once_with(
                "tfk_bearer_api_key", mock_request, mock_db
            )

    @pytest.mark.asyncio
    async def test_api_key_without_prefix(self):
        """접두사 없는 X-API-Key (무시됨)"""
        from app.auth.dependencies import get_current_user

        mock_db = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                credentials=None,
                x_api_key="invalid_key_no_prefix",
                request=None,
                db=mock_db,
            )

        assert exc_info.value.status_code == 401


# ========== get_current_active_user 테스트 ==========


class TestGetCurrentActiveUser:
    """get_current_active_user 테스트"""

    @pytest.mark.asyncio
    async def test_active_user(self):
        """활성 사용자"""
        from app.auth.dependencies import get_current_active_user

        mock_user = MagicMock()
        mock_user.is_active = True

        result = await get_current_active_user(mock_user)

        assert result == mock_user

    @pytest.mark.asyncio
    async def test_inactive_user(self):
        """비활성 사용자"""
        from app.auth.dependencies import get_current_active_user

        mock_user = MagicMock()
        mock_user.is_active = False

        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(mock_user)

        assert exc_info.value.status_code == 403
        assert "Inactive user" in exc_info.value.detail


# ========== get_optional_user 테스트 ==========


class TestGetOptionalUser:
    """get_optional_user 테스트"""

    @pytest.mark.asyncio
    async def test_no_credentials_returns_none(self):
        """인증 정보 없으면 None 반환"""
        from app.auth.dependencies import get_optional_user

        mock_db = MagicMock()

        result = await get_optional_user(
            credentials=None, x_api_key=None, request=None, db=mock_db
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_valid_credentials(self):
        """유효한 인증 정보"""
        from app.auth.dependencies import get_optional_user

        mock_user = MagicMock()
        mock_db = MagicMock()
        mock_request = MagicMock()

        with patch(
            "app.auth.dependencies.get_current_user",
            return_value=mock_user,
        ):
            result = await get_optional_user(
                credentials=None,
                x_api_key="tfk_test",
                request=mock_request,
                db=mock_db,
            )

            assert result == mock_user

    @pytest.mark.asyncio
    async def test_invalid_credentials_returns_none(self):
        """유효하지 않은 인증 정보는 None 반환"""
        from app.auth.dependencies import get_optional_user

        mock_db = MagicMock()

        with patch(
            "app.auth.dependencies.get_current_user",
            side_effect=HTTPException(status_code=401, detail="Invalid"),
        ):
            result = await get_optional_user(
                credentials=None, x_api_key="tfk_invalid", request=None, db=mock_db
            )

            assert result is None


# ========== require_admin 테스트 ==========


class TestRequireAdmin:
    """require_admin 테스트"""

    @pytest.mark.asyncio
    async def test_admin_user(self):
        """관리자 사용자"""
        from app.auth.dependencies import require_admin

        mock_user = MagicMock()
        mock_user.role = "admin"

        result = await require_admin(mock_user)

        assert result == mock_user

    @pytest.mark.asyncio
    async def test_non_admin_user(self):
        """일반 사용자"""
        from app.auth.dependencies import require_admin

        mock_user = MagicMock()
        mock_user.role = "user"

        with pytest.raises(HTTPException) as exc_info:
            await require_admin(mock_user)

        assert exc_info.value.status_code == 403
        assert "Admin privileges required" in exc_info.value.detail


# ========== require_scope 테스트 ==========


class TestRequireScope:
    """require_scope 테스트"""

    def test_returns_callable(self):
        """Callable 반환"""
        from app.auth.dependencies import require_scope

        checker = require_scope(["read"])

        assert callable(checker)

    @pytest.mark.asyncio
    async def test_jwt_auth_bypasses_scope_check(self):
        """JWT 인증은 스코프 검증 우회"""
        from app.auth.dependencies import require_scope

        mock_user = MagicMock()
        mock_db = MagicMock()

        credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        credentials.credentials = "jwt_token"

        checker = require_scope(["read", "write"])

        with patch(
            "app.auth.dependencies.get_current_user",
            return_value=mock_user,
        ):
            result = await checker(
                credentials=credentials, x_api_key=None, request=None, db=mock_db
            )

            assert result == mock_user

    @pytest.mark.asyncio
    async def test_api_key_with_valid_scopes(self):
        """유효한 스코프를 가진 API Key"""
        from app.auth.dependencies import require_scope

        mock_user = MagicMock()
        mock_api_key = MagicMock()
        mock_api_key.user_id = uuid4()
        mock_api_key.scopes = ["read", "write", "sensors"]

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        mock_request = MagicMock()
        mock_request.headers.get.return_value = ""
        mock_request.client.host = "127.0.0.1"

        checker = require_scope(["read", "sensors"])

        with patch(
            "app.services.api_key_service.validate_api_key",
            return_value=mock_api_key,
        ):
            result = await checker(
                credentials=None,
                x_api_key="tfk_test",
                request=mock_request,
                db=mock_db,
            )

            assert result == mock_user

    @pytest.mark.asyncio
    async def test_api_key_with_missing_scopes(self):
        """스코프 누락된 API Key"""
        from app.auth.dependencies import require_scope

        mock_api_key = MagicMock()
        mock_api_key.user_id = uuid4()
        mock_api_key.scopes = ["read"]

        mock_db = MagicMock()

        mock_request = MagicMock()
        mock_request.headers.get.return_value = ""
        mock_request.client.host = "127.0.0.1"

        checker = require_scope(["read", "write"])

        with patch(
            "app.services.api_key_service.validate_api_key",
            return_value=mock_api_key,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await checker(
                    credentials=None,
                    x_api_key="tfk_test",
                    request=mock_request,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 403
            assert "Missing required scopes" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_api_key_with_admin_scope(self):
        """admin 스코프는 모든 스코프 포함"""
        from app.auth.dependencies import require_scope

        mock_user = MagicMock()
        mock_api_key = MagicMock()
        mock_api_key.user_id = uuid4()
        mock_api_key.scopes = ["admin"]

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        mock_request = MagicMock()
        mock_request.headers.get.return_value = ""
        mock_request.client.host = "127.0.0.1"

        checker = require_scope(["read", "write", "delete", "sensors", "workflows"])

        with patch(
            "app.services.api_key_service.validate_api_key",
            return_value=mock_api_key,
        ):
            result = await checker(
                credentials=None,
                x_api_key="tfk_test",
                request=mock_request,
                db=mock_db,
            )

            assert result == mock_user

    @pytest.mark.asyncio
    async def test_invalid_api_key(self):
        """유효하지 않은 API Key"""
        from app.auth.dependencies import require_scope

        mock_db = MagicMock()

        mock_request = MagicMock()
        mock_request.headers.get.return_value = ""
        mock_request.client.host = "127.0.0.1"

        checker = require_scope(["read"])

        with patch(
            "app.services.api_key_service.validate_api_key",
            return_value=None,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await checker(
                    credentials=None,
                    x_api_key="tfk_invalid",
                    request=mock_request,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_api_key_owner_not_found(self):
        """API Key 소유자 없음"""
        from app.auth.dependencies import require_scope

        mock_api_key = MagicMock()
        mock_api_key.user_id = uuid4()
        mock_api_key.scopes = ["read"]

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        mock_request = MagicMock()
        mock_request.headers.get.return_value = ""
        mock_request.client.host = "127.0.0.1"

        checker = require_scope(["read"])

        with patch(
            "app.services.api_key_service.validate_api_key",
            return_value=mock_api_key,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await checker(
                    credentials=None,
                    x_api_key="tfk_test",
                    request=mock_request,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 401
            assert "API Key owner not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_bearer_api_key(self):
        """Bearer 토큰으로 API Key 전달"""
        from app.auth.dependencies import require_scope

        mock_user = MagicMock()
        mock_api_key = MagicMock()
        mock_api_key.user_id = uuid4()
        mock_api_key.scopes = ["read"]

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        credentials.credentials = "tfk_bearer_key"

        mock_request = MagicMock()
        mock_request.headers.get.return_value = ""
        mock_request.client.host = "127.0.0.1"

        checker = require_scope(["read"])

        with patch(
            "app.services.api_key_service.validate_api_key",
            return_value=mock_api_key,
        ):
            result = await checker(
                credentials=credentials,
                x_api_key=None,
                request=mock_request,
                db=mock_db,
            )

            assert result == mock_user


# ========== require_any_scope 테스트 ==========


class TestRequireAnyScope:
    """require_any_scope 테스트"""

    def test_returns_callable(self):
        """Callable 반환"""
        from app.auth.dependencies import require_any_scope

        checker = require_any_scope(["read", "admin"])

        assert callable(checker)

    @pytest.mark.asyncio
    async def test_jwt_auth_bypasses_scope_check(self):
        """JWT 인증은 스코프 검증 우회"""
        from app.auth.dependencies import require_any_scope

        mock_user = MagicMock()
        mock_db = MagicMock()

        credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        credentials.credentials = "jwt_token"

        checker = require_any_scope(["read", "admin"])

        with patch(
            "app.auth.dependencies.get_current_user",
            return_value=mock_user,
        ):
            result = await checker(
                credentials=credentials, x_api_key=None, request=None, db=mock_db
            )

            assert result == mock_user

    @pytest.mark.asyncio
    async def test_api_key_with_one_matching_scope(self):
        """하나의 스코프만 일치해도 통과"""
        from app.auth.dependencies import require_any_scope

        mock_user = MagicMock()
        mock_api_key = MagicMock()
        mock_api_key.user_id = uuid4()
        mock_api_key.scopes = ["read"]  # read만 있음

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        mock_request = MagicMock()
        mock_request.headers.get.return_value = ""
        mock_request.client.host = "127.0.0.1"

        checker = require_any_scope(["read", "write", "admin"])

        with patch(
            "app.services.api_key_service.validate_api_key",
            return_value=mock_api_key,
        ):
            result = await checker(
                credentials=None,
                x_api_key="tfk_test",
                request=mock_request,
                db=mock_db,
            )

            assert result == mock_user

    @pytest.mark.asyncio
    async def test_api_key_with_no_matching_scope(self):
        """일치하는 스코프 없음"""
        from app.auth.dependencies import require_any_scope

        mock_api_key = MagicMock()
        mock_api_key.user_id = uuid4()
        mock_api_key.scopes = ["sensors", "workflows"]

        mock_db = MagicMock()

        mock_request = MagicMock()
        mock_request.headers.get.return_value = ""
        mock_request.client.host = "127.0.0.1"

        checker = require_any_scope(["read", "write"])

        with patch(
            "app.services.api_key_service.validate_api_key",
            return_value=mock_api_key,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await checker(
                    credentials=None,
                    x_api_key="tfk_test",
                    request=mock_request,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 403
            assert "Requires one of" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_api_key_with_admin_scope(self):
        """admin 스코프는 모든 스코프 포함"""
        from app.auth.dependencies import require_any_scope

        mock_user = MagicMock()
        mock_api_key = MagicMock()
        mock_api_key.user_id = uuid4()
        mock_api_key.scopes = ["admin"]

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        mock_request = MagicMock()
        mock_request.headers.get.return_value = ""
        mock_request.client.host = "127.0.0.1"

        checker = require_any_scope(["read", "write"])

        with patch(
            "app.services.api_key_service.validate_api_key",
            return_value=mock_api_key,
        ):
            result = await checker(
                credentials=None,
                x_api_key="tfk_test",
                request=mock_request,
                db=mock_db,
            )

            assert result == mock_user

    @pytest.mark.asyncio
    async def test_invalid_api_key(self):
        """유효하지 않은 API Key"""
        from app.auth.dependencies import require_any_scope

        mock_db = MagicMock()

        mock_request = MagicMock()
        mock_request.headers.get.return_value = ""
        mock_request.client.host = "127.0.0.1"

        checker = require_any_scope(["read"])

        with patch(
            "app.services.api_key_service.validate_api_key",
            return_value=None,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await checker(
                    credentials=None,
                    x_api_key="tfk_invalid",
                    request=mock_request,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_api_key_owner_not_found(self):
        """API Key 소유자 없음"""
        from app.auth.dependencies import require_any_scope

        mock_api_key = MagicMock()
        mock_api_key.user_id = uuid4()
        mock_api_key.scopes = ["read"]

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        mock_request = MagicMock()
        mock_request.headers.get.return_value = ""
        mock_request.client.host = "127.0.0.1"

        checker = require_any_scope(["read"])

        with patch(
            "app.services.api_key_service.validate_api_key",
            return_value=mock_api_key,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await checker(
                    credentials=None,
                    x_api_key="tfk_test",
                    request=mock_request,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 401
            assert "API Key owner not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_bearer_api_key(self):
        """Bearer 토큰으로 API Key 전달"""
        from app.auth.dependencies import require_any_scope

        mock_user = MagicMock()
        mock_api_key = MagicMock()
        mock_api_key.user_id = uuid4()
        mock_api_key.scopes = ["write"]

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        credentials.credentials = "tfk_bearer_key"

        mock_request = MagicMock()
        mock_request.headers.get.return_value = ""
        mock_request.client.host = "127.0.0.1"

        checker = require_any_scope(["read", "write"])

        with patch(
            "app.services.api_key_service.validate_api_key",
            return_value=mock_api_key,
        ):
            result = await checker(
                credentials=credentials,
                x_api_key=None,
                request=mock_request,
                db=mock_db,
            )

            assert result == mock_user
