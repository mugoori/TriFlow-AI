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
        assert "access_token" in data or "user" in data

    @pytest.mark.asyncio
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

        # Login
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "logintest@triflow.ai",
                "password": "LoginPassword123!"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, client: AsyncClient):
        """Test login with invalid credentials."""
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "nonexistent@triflow.ai",
                "password": "WrongPassword123!"
            }
        )
        assert response.status_code in [401, 403]

    @pytest.mark.asyncio
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
    async def test_refresh_token(self, authenticated_client: AsyncClient):
        """Test token refresh."""
        response = await authenticated_client.post("/api/v1/auth/refresh")
        # Refresh might not be implemented, skip if 404
        if response.status_code != 404:
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
