"""
TriFlow AI - Authentication Tests
==================================
Tests for authentication endpoints
"""

import pytest
from httpx import AsyncClient


class TestAuthEndpoints:
    """Test authentication endpoints."""

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """Test health check endpoint."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_register_user(self, client: AsyncClient):
        """Test user registration."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@triflow.ai",
                "password": "SecurePassword123!",
                "display_name": "New User"
            }
        )
        assert response.status_code in [200, 201]
        data = response.json()
        # Response is LoginResponse with user and tokens
        assert "user" in data
        assert "tokens" in data
        assert "access_token" in data["tokens"]

    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_register_duplicate_email(self, client: AsyncClient):
        """Test registration with duplicate email."""
        # First registration
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "duplicate@triflow.ai",
                "password": "SecurePassword123!",
                "display_name": "First User"
            }
        )

        # Second registration with same email
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "duplicate@triflow.ai",
                "password": "DifferentPassword123!",
                "display_name": "Second User"
            }
        )
        assert response.status_code in [400, 409]

    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_login_success(self, client: AsyncClient):
        """Test successful login."""
        # Register first
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "logintest@triflow.ai",
                "password": "LoginPassword123!",
                "display_name": "Login Test"
            }
        )

        # Login - use JSON body with email/password (per LoginRequest schema)
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "logintest@triflow.ai",
                "password": "LoginPassword123!"
            }
        )
        assert response.status_code == 200
        data = response.json()
        # Response is LoginResponse
        assert "tokens" in data
        assert "access_token" in data["tokens"]
        assert data["tokens"]["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, client: AsyncClient):
        """Test login with invalid credentials."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@triflow.ai",
                "password": "WrongPassword123!"
            }
        )
        assert response.status_code in [401, 403]

    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_get_current_user(self, authenticated_client: AsyncClient):
        """Test getting current user info."""
        response = await authenticated_client.get("/api/v1/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert "email" in data

    @pytest.mark.asyncio
    async def test_protected_endpoint_without_auth(self, client: AsyncClient):
        """Test accessing protected endpoint without authentication."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code in [401, 403]

    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_refresh_token(self, client: AsyncClient):
        """Test token refresh."""
        # First register and get tokens
        reg_response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "refresh@triflow.ai",
                "password": "RefreshPassword123!",
                "display_name": "Refresh Test"
            }
        )

        if reg_response.status_code not in [200, 201]:
            pytest.skip("Registration failed")

        tokens = reg_response.json().get("tokens", {})
        refresh_token = tokens.get("refresh_token")

        if not refresh_token:
            pytest.skip("No refresh token returned")

        # Try refresh
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )

        # Refresh endpoint exists
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, client: AsyncClient):
        """Test token refresh with invalid token."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid_token"}
        )
        assert response.status_code in [401, 403]

    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_auth_status_authenticated(self, authenticated_client: AsyncClient):
        """Test auth status when authenticated."""
        response = await authenticated_client.get("/api/v1/auth/status")
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert "user" in data

    @pytest.mark.asyncio
    async def test_auth_status_not_authenticated(self, client: AsyncClient):
        """Test auth status when not authenticated."""
        response = await client.get("/api/v1/auth/status")
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is False
        assert data["user"] is None

    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_change_password_success(self, client: AsyncClient):
        """Test password change."""
        # Register
        reg_response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "pwchange@triflow.ai",
                "password": "OldPassword123!",
                "display_name": "PW Change"
            }
        )
        if reg_response.status_code not in [200, 201]:
            pytest.skip("Registration failed")

        tokens = reg_response.json().get("tokens", {})
        token = tokens.get("access_token")

        # Change password
        response = await client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "OldPassword123!",
                "new_password": "NewPassword456!"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_change_password_wrong_current(self, client: AsyncClient):
        """Test password change with wrong current password."""
        # Register
        reg_response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "pwwrong@triflow.ai",
                "password": "CorrectPassword123!",
                "display_name": "PW Wrong"
            }
        )
        if reg_response.status_code not in [200, 201]:
            pytest.skip("Registration failed")

        tokens = reg_response.json().get("tokens", {})
        token = tokens.get("access_token")

        # Try change with wrong current password
        response = await client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "WrongPassword!",
                "new_password": "NewPassword456!"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_login_inactive_user(self, client: AsyncClient, db_session):
        """Test login with inactive user."""
        from app.models import User, Tenant
        from app.auth.password import get_password_hash
        from uuid import uuid4

        # Create tenant
        tenant = Tenant(
            tenant_id=uuid4(),
            name="Test Tenant",
            slug="test-tenant",
        )
        db_session.add(tenant)
        db_session.commit()

        # Create inactive user
        user = User(
            user_id=uuid4(),
            tenant_id=tenant.tenant_id,
            username="inactive",
            email="inactive@triflow.ai",
            password_hash=get_password_hash("InactivePassword123!"),
            display_name="Inactive User",
            role="user",
            is_active=False,
        )
        db_session.add(user)
        db_session.commit()

        # Try login
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "inactive@triflow.ai",
                "password": "InactivePassword123!"
            }
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient):
        """Test login with wrong password."""
        # Register first
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "wrongpw@triflow.ai",
                "password": "CorrectPassword123!",
                "display_name": "Wrong PW Test"
            }
        )

        # Try login with wrong password
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "wrongpw@triflow.ai",
                "password": "WrongPassword123!"
            }
        )
        assert response.status_code == 401


class TestGoogleOAuth:
    """Google OAuth 테스트"""

    @pytest.mark.asyncio
    async def test_google_login_not_configured(self, client: AsyncClient):
        """Test Google login when not configured."""
        from unittest.mock import patch

        with patch("app.config.settings.google_client_id", ""):
            response = await client.get("/api/v1/auth/google/login")
            # Should return 503 when not configured
            assert response.status_code in [503, 500]

    @pytest.mark.asyncio
    async def test_google_callback_invalid_code(self, client: AsyncClient):
        """Test Google callback with invalid code."""
        from unittest.mock import patch, AsyncMock

        with patch("app.services.oauth_service.exchange_google_code", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = None
            response = await client.get("/api/v1/auth/google/callback?code=invalid_code")
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_google_callback_no_access_token(self, client: AsyncClient):
        """Test Google callback with no access token in response."""
        from unittest.mock import patch, AsyncMock

        with patch("app.services.oauth_service.exchange_google_code", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = {"id_token": "some_token"}  # No access_token
            response = await client.get("/api/v1/auth/google/callback?code=test_code")
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_google_callback_invalid_user_info(self, client: AsyncClient):
        """Test Google callback with invalid user info."""
        from unittest.mock import patch, AsyncMock

        with patch("app.services.oauth_service.exchange_google_code", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = {"access_token": "valid_token"}
            with patch("app.services.oauth_service.get_google_user_info", new_callable=AsyncMock) as mock_user:
                mock_user.return_value = None
                response = await client.get("/api/v1/auth/google/callback?code=test_code")
                assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_google_callback_missing_email(self, client: AsyncClient):
        """Test Google callback with missing email in user info."""
        from unittest.mock import patch, AsyncMock

        with patch("app.services.oauth_service.exchange_google_code", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = {"access_token": "valid_token"}
            with patch("app.services.oauth_service.get_google_user_info", new_callable=AsyncMock) as mock_user:
                mock_user.return_value = {"id": "123"}  # No email
                response = await client.get("/api/v1/auth/google/callback?code=test_code")
                assert response.status_code == 400


class TestTokenFunctions:
    """토큰 관련 함수 테스트"""

    def test_create_tokens(self):
        """_create_tokens 함수 테스트"""
        from unittest.mock import MagicMock
        from uuid import uuid4
        from app.routers.auth import _create_tokens

        user = MagicMock()
        user.user_id = uuid4()
        user.email = "test@triflow.ai"
        user.role = "user"
        user.tenant_id = uuid4()

        tokens = _create_tokens(user)

        assert tokens.access_token is not None
        assert tokens.refresh_token is not None
        assert tokens.token_type == "bearer"
        assert tokens.expires_in > 0

    @pytest.mark.asyncio
    async def test_refresh_token_wrong_type(self, client: AsyncClient):
        """Test refresh with access token (wrong type)."""
        from app.auth.jwt import create_access_token

        # Create access token
        access_token = create_access_token({
            "sub": "test-user-id",
            "email": "test@triflow.ai",
            "role": "user",
            "tenant_id": "test-tenant-id",
        })

        # Try to use access token as refresh token
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token}
        )
        assert response.status_code == 401
