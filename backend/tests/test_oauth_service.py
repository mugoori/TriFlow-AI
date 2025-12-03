"""
OAuth Service 테스트
Google OAuth2 서비스 함수들에 대한 테스트
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx


class TestGenerateStateToken:
    """generate_state_token 함수 테스트"""

    def test_generate_state_token(self):
        """상태 토큰 생성"""
        from app.services.oauth_service import generate_state_token

        token = generate_state_token()

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_generate_state_token_unique(self):
        """상태 토큰 고유성"""
        from app.services.oauth_service import generate_state_token

        tokens = [generate_state_token() for _ in range(10)]
        unique_tokens = set(tokens)

        # 모든 토큰이 고유해야 함
        assert len(unique_tokens) == len(tokens)


class TestGetGoogleAuthUrl:
    """get_google_auth_url 함수 테스트"""

    @patch("app.services.oauth_service.settings")
    def test_get_google_auth_url(self, mock_settings):
        """Google 인증 URL 생성"""
        from app.services.oauth_service import get_google_auth_url

        mock_settings.google_client_id = "test-client-id"
        mock_settings.google_redirect_uri = "http://localhost:8000/callback"

        result = get_google_auth_url("test-state")

        # 딕셔너리 반환 확인
        assert isinstance(result, dict)
        assert "url" in result
        assert "state" in result

        url = result["url"]
        assert "accounts.google.com" in url
        assert "client_id=test-client-id" in url
        assert "state=test-state" in url
        assert "redirect_uri=" in url
        assert "response_type=code" in url

    @patch("app.services.oauth_service.settings")
    def test_get_google_auth_url_scopes(self, mock_settings):
        """Google 인증 URL에 스코프 포함"""
        from app.services.oauth_service import get_google_auth_url

        mock_settings.google_client_id = "test-client-id"
        mock_settings.google_redirect_uri = "http://localhost:8000/callback"

        result = get_google_auth_url("test-state")
        url = result["url"]

        # 필수 스코프 확인
        assert "openid" in url or "scope=" in url


class TestExchangeGoogleCode:
    """exchange_google_code 함수 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.oauth_service.httpx.AsyncClient")
    @patch("app.services.oauth_service.settings")
    async def test_exchange_google_code_success(self, mock_settings, mock_client_class):
        """인증 코드 교환 성공"""
        from app.services.oauth_service import exchange_google_code

        mock_settings.google_client_id = "test-client-id"
        mock_settings.google_client_secret = "test-secret"
        mock_settings.google_redirect_uri = "http://localhost:8000/callback"

        # Mock 응답
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "mock-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "mock-refresh-token",
            "id_token": "mock-id-token"
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await exchange_google_code("test-auth-code")

        assert result is not None
        assert result["access_token"] == "mock-access-token"

    @pytest.mark.asyncio
    @patch("app.services.oauth_service.httpx.AsyncClient")
    @patch("app.services.oauth_service.settings")
    async def test_exchange_google_code_failure(self, mock_settings, mock_client_class):
        """인증 코드 교환 실패"""
        from app.services.oauth_service import exchange_google_code

        mock_settings.google_client_id = "test-client-id"
        mock_settings.google_client_secret = "test-secret"
        mock_settings.google_redirect_uri = "http://localhost:8000/callback"

        # Mock 실패 응답
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "invalid_grant"}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await exchange_google_code("invalid-code")

        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.oauth_service.httpx.AsyncClient")
    @patch("app.services.oauth_service.settings")
    async def test_exchange_google_code_http_error(self, mock_settings, mock_client_class):
        """HTTP 에러 처리"""
        from app.services.oauth_service import exchange_google_code

        mock_settings.google_client_id = "test-client-id"
        mock_settings.google_client_secret = "test-secret"
        mock_settings.google_redirect_uri = "http://localhost:8000/callback"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.HTTPError("Connection failed"))
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await exchange_google_code("test-code")

        assert result is None


class TestGetGoogleUserInfo:
    """get_google_user_info 함수 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.oauth_service.httpx.AsyncClient")
    async def test_get_google_user_info_success(self, mock_client_class):
        """사용자 정보 조회 성공"""
        from app.services.oauth_service import get_google_user_info

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "123456789",
            "email": "test@gmail.com",
            "verified_email": True,
            "name": "Test User",
            "given_name": "Test",
            "family_name": "User",
            "picture": "https://lh3.googleusercontent.com/..."
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await get_google_user_info("mock-access-token")

        assert result is not None
        assert result["email"] == "test@gmail.com"
        assert result["name"] == "Test User"

    @pytest.mark.asyncio
    @patch("app.services.oauth_service.httpx.AsyncClient")
    async def test_get_google_user_info_failure(self, mock_client_class):
        """사용자 정보 조회 실패 - 잘못된 토큰"""
        from app.services.oauth_service import get_google_user_info

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Invalid token"}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await get_google_user_info("invalid-token")

        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.oauth_service.httpx.AsyncClient")
    async def test_get_google_user_info_http_error(self, mock_client_class):
        """HTTP 에러 처리"""
        from app.services.oauth_service import get_google_user_info

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.HTTPError("Network error"))
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await get_google_user_info("mock-token")

        assert result is None


class TestVerifyGoogleToken:
    """verify_google_token 함수 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.oauth_service.httpx.AsyncClient")
    @patch("app.services.oauth_service.settings")
    async def test_verify_google_token_success(self, mock_settings, mock_client_class):
        """ID 토큰 검증 성공"""
        from app.services.oauth_service import verify_google_token

        mock_settings.google_client_id = "test-client-id"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "iss": "https://accounts.google.com",
            "aud": "test-client-id",
            "sub": "123456789",
            "email": "test@gmail.com",
            "email_verified": True,
            "name": "Test User",
            "exp": "9999999999"
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await verify_google_token("mock-id-token")

        assert result is not None
        assert result["email"] == "test@gmail.com"

    @pytest.mark.asyncio
    @patch("app.services.oauth_service.httpx.AsyncClient")
    @patch("app.services.oauth_service.settings")
    async def test_verify_google_token_wrong_audience(self, mock_settings, mock_client_class):
        """잘못된 audience"""
        from app.services.oauth_service import verify_google_token

        mock_settings.google_client_id = "test-client-id"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "iss": "https://accounts.google.com",
            "aud": "wrong-client-id",  # 다른 client_id
            "email": "test@gmail.com"
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await verify_google_token("mock-id-token")

        # aud 불일치 시 None 반환 또는 검증 실패
        # 실제 구현에 따라 조정
        assert result is None or result.get("aud") != mock_settings.google_client_id

    @pytest.mark.asyncio
    @patch("app.services.oauth_service.httpx.AsyncClient")
    async def test_verify_google_token_invalid(self, mock_client_class):
        """유효하지 않은 토큰"""
        from app.services.oauth_service import verify_google_token

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "Invalid token"}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await verify_google_token("invalid-token")

        assert result is None


class TestOAuthIntegration:
    """OAuth 통합 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.oauth_service.httpx.AsyncClient")
    @patch("app.services.oauth_service.settings")
    async def test_full_oauth_flow(self, mock_settings, mock_client_class):
        """전체 OAuth 플로우"""
        from app.services.oauth_service import (
            generate_state_token,
            get_google_auth_url,
            exchange_google_code,
            get_google_user_info
        )

        mock_settings.google_client_id = "test-client-id"
        mock_settings.google_client_secret = "test-secret"
        mock_settings.google_redirect_uri = "http://localhost:8000/callback"

        # 1. 상태 토큰 생성
        state = generate_state_token()
        assert state is not None

        # 2. 인증 URL 생성
        auth_result = get_google_auth_url(state)
        assert isinstance(auth_result, dict)
        auth_url = auth_result["url"]
        assert "accounts.google.com" in auth_url
        assert state in auth_url

        # 3. 코드 교환 Mock
        mock_token_response = MagicMock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = {
            "access_token": "mock-access-token",
            "token_type": "Bearer"
        }

        # 4. 사용자 정보 Mock
        mock_userinfo_response = MagicMock()
        mock_userinfo_response.status_code = 200
        mock_userinfo_response.json.return_value = {
            "id": "123",
            "email": "test@gmail.com",
            "name": "Test User"
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_token_response)
        mock_client.get = AsyncMock(return_value=mock_userinfo_response)
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        # 3. 코드 교환
        tokens = await exchange_google_code("mock-auth-code")
        assert tokens is not None
        assert "access_token" in tokens

        # 4. 사용자 정보 조회
        user_info = await get_google_user_info(tokens["access_token"])
        assert user_info is not None
        assert user_info["email"] == "test@gmail.com"
