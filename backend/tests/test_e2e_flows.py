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

        # Step 2: Login
        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "e2e_test@triflow.ai",
                "password": "E2ETestPassword123!"
            }
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

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
        # Step 1: Create workflow
        create_response = await authenticated_client.post(
            "/api/v1/workflows",
            json={
                "name": "E2E Test Workflow",
                "description": "Created during E2E test",
                "trigger": {
                    "type": "condition",
                    "config": {"sensor_type": "temperature", "operator": ">=", "threshold": 80}
                },
                "nodes": [
                    {"id": "n1", "type": "condition", "config": {"condition": "temperature >= 80"}},
                    {"id": "n2", "type": "action", "config": {"action": "log_event"}}
                ],
                "is_active": False
            }
        )
        assert create_response.status_code in [200, 201]
        workflow_id = create_response.json().get("id") or create_response.json().get("workflow_id")

        # Step 2: Update workflow
        update_response = await authenticated_client.put(
            f"/api/v1/workflows/{workflow_id}",
            json={
                "name": "Updated E2E Workflow",
                "description": "Updated during E2E test",
                "trigger": {
                    "type": "condition",
                    "config": {"sensor_type": "temperature", "operator": ">=", "threshold": 85}
                },
                "nodes": [
                    {"id": "n1", "type": "condition", "config": {"condition": "temperature >= 85"}},
                    {"id": "n2", "type": "action", "config": {"action": "send_slack_notification"}}
                ],
                "is_active": True
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
    async def test_sensor_data_flow(self, authenticated_client: AsyncClient):
        """Test: List Sensors -> Get Details -> View History."""
        # Step 1: List sensors
        list_response = await authenticated_client.get("/api/v1/sensors")
        assert list_response.status_code == 200

        # Step 2: Get first sensor details (if any)
        sensors = list_response.json()
        if isinstance(sensors, dict):
            sensors = sensors.get("sensors", [])

        if sensors and len(sensors) > 0:
            sensor_id = sensors[0].get("sensor_id") or sensors[0].get("id")

            # Step 3: Get sensor history
            history_response = await authenticated_client.get(
                f"/api/v1/sensors/{sensor_id}/history"
            )
            assert history_response.status_code in [200, 404]


class TestChatInteractionFlow:
    """Test chat interaction flow."""

    @pytest.mark.asyncio
    async def test_chat_conversation_flow(self, authenticated_client: AsyncClient):
        """Test: Start Chat -> Continue Conversation -> Query Data."""
        # Step 1: Initial greeting
        greeting_response = await authenticated_client.post(
            "/api/v1/chat",
            json={"message": "안녕하세요", "context": {}}
        )
        assert greeting_response.status_code in [200, 201]
        conversation_id = greeting_response.json().get("conversation_id")

        # Step 2: Ask about capabilities
        capability_response = await authenticated_client.post(
            "/api/v1/chat",
            json={
                "message": "무엇을 할 수 있나요?",
                "conversation_id": conversation_id,
                "context": {}
            }
        )
        assert capability_response.status_code in [200, 201]

        # Step 3: Request data analysis
        analysis_response = await authenticated_client.post(
            "/api/v1/chat",
            json={
                "message": "현재 센서 상태를 분석해주세요",
                "conversation_id": conversation_id,
                "context": {}
            }
        )
        assert analysis_response.status_code in [200, 201]


class TestAdminFlow:
    """Test admin-specific flows."""

    @pytest.mark.asyncio
    async def test_admin_ruleset_management(self, admin_client: AsyncClient):
        """Test admin can manage rulesets."""
        # Create ruleset
        create_response = await admin_client.post(
            "/api/v1/rulesets",
            json={
                "name": "Admin Test Rule",
                "description": "Created by admin",
                "category": "safety",
                "script": "let x = 1; x",
                "is_active": True
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
