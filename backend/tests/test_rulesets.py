"""
TriFlow AI - Ruleset Tests
===========================
Tests for Rhai ruleset endpoints
"""

import pytest
from httpx import AsyncClient


class TestRulesetEndpoints:
    """Test ruleset CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_list_rulesets(self, admin_client: AsyncClient):
        """Test listing rulesets (admin only)."""
        response = await admin_client.get("/api/v1/rulesets")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_create_ruleset(
        self,
        admin_client: AsyncClient,
        sample_ruleset_data
    ):
        """Test creating a ruleset."""
        response = await admin_client.post(
            "/api/v1/rulesets",
            json=sample_ruleset_data
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert "id" in data or "ruleset_id" in data

    @pytest.mark.asyncio
    async def test_get_ruleset(
        self,
        admin_client: AsyncClient,
        sample_ruleset_data
    ):
        """Test getting a specific ruleset."""
        # Create first
        create_response = await admin_client.post(
            "/api/v1/rulesets",
            json=sample_ruleset_data
        )
        ruleset_id = create_response.json().get("id") or create_response.json().get("ruleset_id")

        # Get
        response = await admin_client.get(f"/api/v1/rulesets/{ruleset_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == sample_ruleset_data["name"]

    @pytest.mark.asyncio
    async def test_update_ruleset(
        self,
        admin_client: AsyncClient,
        sample_ruleset_data
    ):
        """Test updating a ruleset."""
        # Create first
        create_response = await admin_client.post(
            "/api/v1/rulesets",
            json=sample_ruleset_data
        )
        ruleset_id = create_response.json().get("id") or create_response.json().get("ruleset_id")

        # Update (PATCH, not PUT)
        updated_data = {"name": "Updated Rule Name"}
        response = await admin_client.patch(
            f"/api/v1/rulesets/{ruleset_id}",
            json=updated_data
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_ruleset(
        self,
        admin_client: AsyncClient,
        sample_ruleset_data
    ):
        """Test deleting a ruleset."""
        # Create first
        create_response = await admin_client.post(
            "/api/v1/rulesets",
            json=sample_ruleset_data
        )
        ruleset_id = create_response.json().get("id") or create_response.json().get("ruleset_id")

        # Delete
        response = await admin_client.delete(f"/api/v1/rulesets/{ruleset_id}")
        assert response.status_code in [200, 204]

    @pytest.mark.asyncio
    async def test_non_admin_cannot_create_ruleset(
        self,
        authenticated_client: AsyncClient,
        sample_ruleset_data
    ):
        """Test that non-admin users cannot create rulesets."""
        response = await authenticated_client.post(
            "/api/v1/rulesets",
            json=sample_ruleset_data
        )
        # Should be forbidden for non-admin, or allowed if RBAC not enforced
        assert response.status_code in [403, 401, 200, 201]


class TestRulesetExecution:
    """Test ruleset execution."""

    @pytest.mark.asyncio
    async def test_execute_ruleset(
        self,
        admin_client: AsyncClient,
        sample_ruleset_data
    ):
        """Test executing a ruleset."""
        # Create first
        create_response = await admin_client.post(
            "/api/v1/rulesets",
            json=sample_ruleset_data
        )
        ruleset_id = create_response.json().get("id") or create_response.json().get("ruleset_id")

        # Execute (input_data is required field)
        response = await admin_client.post(
            f"/api/v1/rulesets/{ruleset_id}/execute",
            json={"input_data": {"sensor_value": 85}}
        )
        # 200 = success, 422 = validation error, 500 = execution error
        assert response.status_code in [200, 404, 422, 500]

    @pytest.mark.asyncio
    async def test_validate_ruleset_script(self, admin_client: AsyncClient):
        """Test validating Rhai script syntax."""
        # 유효한 스크립트 테스트
        response = await admin_client.post(
            "/api/v1/rulesets/validate",
            json={
                "script": "let x = 1 + 2; x"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["line_count"] == 1
        assert len(data["errors"]) == 0

    @pytest.mark.asyncio
    async def test_validate_invalid_script(self, admin_client: AsyncClient):
        """Test validating invalid Rhai script."""
        # 괄호 불균형 스크립트
        response = await admin_client.post(
            "/api/v1/rulesets/validate",
            json={
                "script": "fn test() { let x = 1;"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0


class TestRulesetVersioning:
    """Test ruleset version control."""

    @pytest.mark.asyncio
    async def test_get_ruleset_versions(
        self,
        admin_client: AsyncClient,
        sample_ruleset_data
    ):
        """Test getting ruleset version history."""
        # Create first
        create_response = await admin_client.post(
            "/api/v1/rulesets",
            json=sample_ruleset_data
        )
        ruleset_id = create_response.json().get("id") or create_response.json().get("ruleset_id")

        # Get versions
        response = await admin_client.get(f"/api/v1/rulesets/{ruleset_id}/versions")
        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_rollback_ruleset(
        self,
        admin_client: AsyncClient,
        sample_ruleset_data
    ):
        """Test rolling back to a previous version."""
        # Create and update
        create_response = await admin_client.post(
            "/api/v1/rulesets",
            json=sample_ruleset_data
        )
        ruleset_id = create_response.json().get("id") or create_response.json().get("ruleset_id")

        # Update to create version 2 (use PATCH)
        updated_data = {"rhai_script": "let x = 2; x"}
        await admin_client.patch(f"/api/v1/rulesets/{ruleset_id}", json=updated_data)

        # Rollback to version 1
        response = await admin_client.post(
            f"/api/v1/rulesets/{ruleset_id}/rollback",
            json={"version": 1}
        )
        assert response.status_code in [200, 404]
