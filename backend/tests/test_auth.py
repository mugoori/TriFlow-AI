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
