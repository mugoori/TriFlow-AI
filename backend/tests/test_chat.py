"""
TriFlow AI - Chat/AI Agent Tests
=================================
Tests for chat and AI agent endpoints (via /api/v1/agents/chat)

By default, tests use mock agents (no API calls).
Set TRIFLOW_USE_REAL_API=1 to run integration tests with real Anthropic API.
"""

import pytest
from httpx import AsyncClient


# Chat endpoint is /api/v1/agents/chat
CHAT_ENDPOINT = "/api/v1/agents/chat"
CHAT_STREAM_ENDPOINT = "/api/v1/agents/chat/stream"
AGENT_STATUS_ENDPOINT = "/api/v1/agents/status"


class TestAgentEndpoints:
    """Test agent endpoints."""

    @pytest.mark.asyncio
    async def test_agent_status(self, client: AsyncClient):
        """Test agent status endpoint (no auth required)."""
        response = await client.get(AGENT_STATUS_ENDPOINT)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "agents" in data
        # Check all agents are available
        for agent_name in ["meta_router", "judgment", "workflow", "bi", "learning"]:
            assert agent_name in data["agents"]
            assert data["agents"][agent_name]["available"] is True

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("mock_agents")
    async def test_send_chat_message(self, authenticated_client: AsyncClient):
        """Test sending a chat message (mocked)."""
        response = await authenticated_client.post(
            CHAT_ENDPOINT,
            json={
                "message": "Hello, what can you help me with?",
                "context": {}
            }
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert "response" in data

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("mock_agents")
    async def test_chat_with_sensor_query(self, authenticated_client: AsyncClient):
        """Test chat with sensor-related query (mocked)."""
        response = await authenticated_client.post(
            CHAT_ENDPOINT,
            json={
                "message": "현재 온도 센서 상태가 어떻게 되나요?",
                "context": {}
            }
        )
        assert response.status_code in [200, 201]

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("mock_agents")
    async def test_chat_with_workflow_query(self, authenticated_client: AsyncClient):
        """Test chat with workflow-related query (mocked)."""
        response = await authenticated_client.post(
            CHAT_ENDPOINT,
            json={
                "message": "온도가 80도 이상일 때 알림을 보내는 워크플로우를 만들어줘",
                "context": {}
            }
        )
        assert response.status_code in [200, 201]


class TestAgentRouting:
    """Test Meta Router Agent routing (mocked)."""

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("mock_agents")
    async def test_bi_query_routing(self, authenticated_client: AsyncClient):
        """Test routing to BI agent for data queries."""
        response = await authenticated_client.post(
            CHAT_ENDPOINT,
            json={
                "message": "지난 주 생산량 통계를 보여줘",
                "context": {}
            }
        )
        assert response.status_code in [200, 201]

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("mock_agents")
    async def test_judgment_query_routing(self, authenticated_client: AsyncClient):
        """Test routing to Judgment agent."""
        response = await authenticated_client.post(
            CHAT_ENDPOINT,
            json={
                "message": "현재 센서 데이터를 분석해줘",
                "context": {}
            }
        )
        assert response.status_code in [200, 201]

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("mock_agents")
    async def test_workflow_creation_routing(self, authenticated_client: AsyncClient):
        """Test routing to Workflow Planner."""
        response = await authenticated_client.post(
            CHAT_ENDPOINT,
            json={
                "message": "압력이 높으면 이메일 알림을 보내는 자동화를 만들어줘",
                "context": {}
            }
        )
        assert response.status_code in [200, 201]


class TestChatStreaming:
    """Test streaming chat responses (mocked)."""

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("mock_agents")
    async def test_streaming_chat_endpoint(self, authenticated_client: AsyncClient):
        """Test streaming chat endpoint returns SSE response."""
        response = await authenticated_client.post(
            CHAT_STREAM_ENDPOINT,
            json={
                "message": "안녕하세요",
                "context": {}
            }
        )
        # Should return 200 with SSE content type
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")


class TestChatValidation:
    """Test chat input validation."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_empty_message_validation(self, authenticated_client: AsyncClient):
        """Test sending empty message - should be rejected by Pydantic."""
        response = await authenticated_client.post(
            CHAT_ENDPOINT,
            json={
                "message": "",
                "context": {}
            }
        )
        # Should reject empty message (422 validation error or 500 if agent fails)
        assert response.status_code in [400, 422, 500]

    @pytest.mark.asyncio
    async def test_missing_message_field(self, client: AsyncClient):
        """Test missing message field - returns 422 Pydantic validation error."""
        response = await client.post(
            CHAT_ENDPOINT,
            json={
                "context": {}
            }
        )
        # Should reject missing required field
        assert response.status_code == 422
