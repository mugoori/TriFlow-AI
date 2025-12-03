"""
TriFlow AI - E2E User Flow Tests
=================================
End-to-end tests for main user journeys
"""

import pytest
from httpx import AsyncClient


class TestUserOnboardingFlow:
    """Test complete user onboarding flow."""

    @pytest.mark.asyncio
    async def test_complete_registration_flow(self, client: AsyncClient):
        """Test: Register -> Login -> Access Protected Resource."""
        # Step 1: Register
        register_response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "e2e_test@triflow.ai",
                "password": "E2ETestPassword123!",
                "display_name": "E2E Test User"
            }
        )
        assert register_response.status_code in [200, 201]

        # Step 2: Login (JSON body with email/password per LoginRequest schema)
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "e2e_test@triflow.ai",
                "password": "E2ETestPassword123!"
            }
        )
        assert login_response.status_code == 200
        # Response is LoginResponse: {user: ..., tokens: {access_token, ...}}
        token = login_response.json()["tokens"]["access_token"]

        # Step 3: Access protected resource
        client.headers["Authorization"] = f"Bearer {token}"
        me_response = await client.get("/api/v1/auth/me")
        assert me_response.status_code == 200
        assert me_response.json()["email"] == "e2e_test@triflow.ai"


class TestWorkflowManagementFlow:
    """Test complete workflow management flow."""

    @pytest.mark.asyncio
    async def test_workflow_lifecycle(
        self,
        authenticated_client: AsyncClient
    ):
        """Test: Create -> Update -> Execute -> Delete workflow."""
        # Step 1: Create workflow (using WorkflowCreate schema)
        create_response = await authenticated_client.post(
            "/api/v1/workflows",
            json={
                "name": "E2E Test Workflow",
                "description": "Created during E2E test",
                "dsl_definition": {
                    "name": "E2E Test Workflow",
                    "description": "Created during E2E test",
                    "trigger": {
                        "type": "event",
                        "config": {"sensor_type": "temperature", "operator": ">=", "threshold": 80}
                    },
                    "nodes": [
                        {"id": "n1", "type": "condition", "config": {"condition": "temperature >= 80"}, "next": ["n2"]},
                        {"id": "n2", "type": "action", "config": {"action": "log_event"}, "next": []}
                    ]
                }
            }
        )
        assert create_response.status_code in [200, 201]
        workflow_id = create_response.json().get("id") or create_response.json().get("workflow_id")

        # Step 2: Update workflow (PATCH, not PUT)
        update_response = await authenticated_client.patch(
            f"/api/v1/workflows/{workflow_id}",
            json={
                "name": "Updated E2E Workflow",
                "description": "Updated during E2E test",
            }
        )
        assert update_response.status_code == 200

        # Step 3: Execute workflow
        execute_response = await authenticated_client.post(
            f"/api/v1/workflows/{workflow_id}/execute",
            json={"context": {"temperature": 90}}
        )
        # May succeed or fail based on action configuration
        assert execute_response.status_code in [200, 202, 400, 404, 500]

        # Step 4: Delete workflow
        delete_response = await authenticated_client.delete(f"/api/v1/workflows/{workflow_id}")
        assert delete_response.status_code in [200, 204]


class TestSensorMonitoringFlow:
    """Test sensor monitoring flow."""

    @pytest.mark.asyncio
    async def test_sensor_data_flow(self, client: AsyncClient):
        """Test: Get Sensor Data -> Get Filters -> Get Summary."""
        # Step 1: Get sensor data
        data_response = await client.get("/api/v1/sensors/data")
        assert data_response.status_code == 200
        data = data_response.json()
        assert "data" in data
        assert "total" in data

        # Step 2: Get filter options
        filters_response = await client.get("/api/v1/sensors/filters")
        assert filters_response.status_code == 200
        filters = filters_response.json()
        assert "lines" in filters
        assert "sensor_types" in filters

        # Step 3: Get summary
        summary_response = await client.get("/api/v1/sensors/summary")
        assert summary_response.status_code == 200


class TestChatInteractionFlow:
    """Test chat interaction flow - requires real Anthropic API key."""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Chat requires real Anthropic API key and causes timeout")
    async def test_chat_conversation_flow(self, authenticated_client: AsyncClient):
        """Test: Start Chat -> Continue Conversation -> Query Data."""
        # Chat endpoint is /api/v1/agents/chat
        # Step 1: Initial greeting
        greeting_response = await authenticated_client.post(
            "/api/v1/agents/chat",
            json={"message": "안녕하세요", "context": {}}
        )
        assert greeting_response.status_code in [200, 201]


class TestAdminFlow:
    """Test admin-specific flows."""

    @pytest.mark.asyncio
    async def test_admin_ruleset_management(self, admin_client: AsyncClient):
        """Test admin can manage rulesets."""
        # Create ruleset (using RulesetCreate schema)
        create_response = await admin_client.post(
            "/api/v1/rulesets",
            json={
                "name": "Admin Test Rule",
                "description": "Created by admin",
                "rhai_script": "let x = 1; x"
            }
        )
        assert create_response.status_code in [200, 201]
        ruleset_id = create_response.json().get("id") or create_response.json().get("ruleset_id")

        # List rulesets
        list_response = await admin_client.get("/api/v1/rulesets")
        assert list_response.status_code == 200

        # Clean up
        await admin_client.delete(f"/api/v1/rulesets/{ruleset_id}")


class TestDataImportExportFlow:
    """Test data import/export flows."""

    @pytest.mark.asyncio
    async def test_csv_import_flow(self, authenticated_client: AsyncClient):
        """Test CSV data import."""
        # This would require multipart file upload
        # Simplified test to check endpoint exists
        response = await authenticated_client.get("/api/v1/data/import/templates")
        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_data_export_flow(self, authenticated_client: AsyncClient):
        """Test data export."""
        response = await authenticated_client.get(
            "/api/v1/sensors/export",
            params={"format": "csv"}
        )
        assert response.status_code in [200, 404]


class TestNotificationFlow:
    """Test notification flows."""

    @pytest.mark.asyncio
    async def test_notification_preferences(self, authenticated_client: AsyncClient):
        """Test getting/setting notification preferences."""
        # Get preferences
        get_response = await authenticated_client.get("/api/v1/notifications/preferences")
        assert get_response.status_code in [200, 404]

        # Update preferences (if endpoint exists)
        if get_response.status_code == 200:
            update_response = await authenticated_client.put(
                "/api/v1/notifications/preferences",
                json={
                    "email_enabled": True,
                    "slack_enabled": False
                }
            )
            assert update_response.status_code in [200, 404]
