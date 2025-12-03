"""
TriFlow AI - Workflow Tests
============================
Tests for workflow endpoints
"""

import pytest
from httpx import AsyncClient


class TestWorkflowEndpoints:
    """Test workflow CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_list_workflows(self, authenticated_client: AsyncClient):
        """Test listing workflows."""
        response = await authenticated_client.get("/api/v1/workflows")
        assert response.status_code == 200
        data = response.json()
        assert "workflows" in data or isinstance(data, list)

    @pytest.mark.asyncio
    async def test_create_workflow(
        self,
        authenticated_client: AsyncClient,
        sample_workflow_data
    ):
        """Test creating a workflow."""
        response = await authenticated_client.post(
            "/api/v1/workflows",
            json=sample_workflow_data
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert "id" in data or "workflow_id" in data

    @pytest.mark.asyncio
    async def test_get_workflow(
        self,
        authenticated_client: AsyncClient,
        sample_workflow_data
    ):
        """Test getting a specific workflow."""
        # Create first
        create_response = await authenticated_client.post(
            "/api/v1/workflows",
            json=sample_workflow_data
        )
        assert create_response.status_code in [200, 201]
        workflow_id = create_response.json().get("id") or create_response.json().get("workflow_id")

        # Get
        response = await authenticated_client.get(f"/api/v1/workflows/{workflow_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == sample_workflow_data["name"]

    @pytest.mark.asyncio
    async def test_update_workflow(
        self,
        authenticated_client: AsyncClient,
        sample_workflow_data
    ):
        """Test updating a workflow."""
        # Create first
        create_response = await authenticated_client.post(
            "/api/v1/workflows",
            json=sample_workflow_data
        )
        workflow_id = create_response.json().get("id") or create_response.json().get("workflow_id")

        # Update (PATCH, not PUT)
        updated_data = {"name": "Updated Workflow Name"}
        response = await authenticated_client.patch(
            f"/api/v1/workflows/{workflow_id}",
            json=updated_data
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Workflow Name"

    @pytest.mark.asyncio
    async def test_delete_workflow(
        self,
        authenticated_client: AsyncClient,
        sample_workflow_data
    ):
        """Test deleting a workflow."""
        # Create first
        create_response = await authenticated_client.post(
            "/api/v1/workflows",
            json=sample_workflow_data
        )
        workflow_id = create_response.json().get("id") or create_response.json().get("workflow_id")

        # Delete
        response = await authenticated_client.delete(f"/api/v1/workflows/{workflow_id}")
        assert response.status_code in [200, 204]

        # Verify deleted
        get_response = await authenticated_client.get(f"/api/v1/workflows/{workflow_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_toggle_workflow_active(
        self,
        authenticated_client: AsyncClient,
        sample_workflow_data
    ):
        """Test toggling workflow active status."""
        # Create first
        create_response = await authenticated_client.post(
            "/api/v1/workflows",
            json=sample_workflow_data
        )
        workflow_id = create_response.json().get("id") or create_response.json().get("workflow_id")

        # Toggle (POST method)
        response = await authenticated_client.post(
            f"/api/v1/workflows/{workflow_id}/toggle"
        )
        assert response.status_code == 200
        data = response.json()
        assert "is_active" in data
        assert "message" in data
        # 최초 생성 시 is_active=True이므로 토글 후 False
        assert data["is_active"] is False

        # 다시 토글하면 True
        response2 = await authenticated_client.post(
            f"/api/v1/workflows/{workflow_id}/toggle"
        )
        assert response2.status_code == 200
        assert response2.json()["is_active"] is True


class TestWorkflowExecution:
    """Test workflow execution."""

    @pytest.mark.asyncio
    async def test_execute_workflow(
        self,
        authenticated_client: AsyncClient,
        sample_workflow_data
    ):
        """Test manual workflow execution."""
        # Create first
        create_response = await authenticated_client.post(
            "/api/v1/workflows",
            json=sample_workflow_data
        )
        workflow_id = create_response.json().get("id") or create_response.json().get("workflow_id")

        # Execute
        response = await authenticated_client.post(
            f"/api/v1/workflows/{workflow_id}/execute",
            json={"context": {"temperature": 85}}
        )
        assert response.status_code == 200
        data = response.json()
        assert "instance_id" in data
        assert "status" in data
        assert data["workflow_id"] == workflow_id

    @pytest.mark.asyncio
    async def test_get_workflow_history(
        self,
        authenticated_client: AsyncClient,
        sample_workflow_data
    ):
        """Test getting workflow execution history."""
        # Create first
        create_response = await authenticated_client.post(
            "/api/v1/workflows",
            json=sample_workflow_data
        )
        workflow_id = create_response.json().get("id") or create_response.json().get("workflow_id")

        # Get history
        response = await authenticated_client.get(
            f"/api/v1/workflows/{workflow_id}/history"
        )
        assert response.status_code in [200, 404]


class TestActionCatalog:
    """Test action catalog endpoints."""

    @pytest.mark.asyncio
    async def test_get_action_catalog(self, authenticated_client: AsyncClient):
        """Test getting available actions."""
        response = await authenticated_client.get("/api/v1/workflows/actions")
        assert response.status_code == 200
        data = response.json()
        assert "actions" in data
        assert "categories" in data

    @pytest.mark.asyncio
    async def test_action_catalog_structure(self, authenticated_client: AsyncClient):
        """Test action catalog has required fields."""
        response = await authenticated_client.get("/api/v1/workflows/actions")
        data = response.json()

        for action in data.get("actions", []):
            assert "name" in action
            assert "display_name" in action
            assert "category" in action
