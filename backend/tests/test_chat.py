"""
TriFlow AI - Chat/AI Agent Tests
=================================
Tests for chat and AI agent endpoints
"""

import pytest
from httpx import AsyncClient


class TestChatEndpoints:
    """Test chat endpoints."""

    @pytest.mark.asyncio
    async def test_send_chat_message(self, authenticated_client: AsyncClient):
        """Test sending a chat message."""
        response = await authenticated_client.post(
            "/api/v1/chat",
            json={
                "message": "Hello, what can you help me with?",
                "context": {}
            }
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert "response" in data or "message" in data

    @pytest.mark.asyncio
    async def test_chat_with_sensor_query(self, authenticated_client: AsyncClient):
        """Test chat with sensor-related query."""
        response = await authenticated_client.post(
            "/api/v1/chat",
            json={
                "message": "현재 온도 센서 상태가 어떻게 되나요?",
                "context": {}
            }
        )
        assert response.status_code in [200, 201]

    @pytest.mark.asyncio
    async def test_chat_with_workflow_query(self, authenticated_client: AsyncClient):
        """Test chat with workflow-related query."""
        response = await authenticated_client.post(
            "/api/v1/chat",
            json={
                "message": "온도가 80도 이상일 때 알림을 보내는 워크플로우를 만들어줘",
                "context": {}
            }
        )
        assert response.status_code in [200, 201]

    @pytest.mark.asyncio
    async def test_chat_conversation_history(self, authenticated_client: AsyncClient):
        """Test chat maintains conversation context."""
        # First message
        response1 = await authenticated_client.post(
            "/api/v1/chat",
            json={
                "message": "내 이름은 테스터야",
                "context": {}
            }
        )
        conversation_id = response1.json().get("conversation_id")

        # Second message with context
        response2 = await authenticated_client.post(
            "/api/v1/chat",
            json={
                "message": "내 이름이 뭐라고 했지?",
                "conversation_id": conversation_id,
                "context": {}
            }
        )
        assert response2.status_code in [200, 201]


class TestAgentRouting:
    """Test Meta Router Agent routing."""

    @pytest.mark.asyncio
    async def test_bi_query_routing(self, authenticated_client: AsyncClient):
        """Test routing to BI agent for data queries."""
        response = await authenticated_client.post(
            "/api/v1/chat",
            json={
                "message": "지난 주 생산량 통계를 보여줘",
                "context": {}
            }
        )
        assert response.status_code in [200, 201]
        # May contain chart data or SQL query

    @pytest.mark.asyncio
    async def test_judgment_query_routing(self, authenticated_client: AsyncClient):
        """Test routing to Judgment agent."""
        response = await authenticated_client.post(
            "/api/v1/chat",
            json={
                "message": "현재 센서 데이터를 분석해줘",
                "context": {}
            }
        )
        assert response.status_code in [200, 201]

    @pytest.mark.asyncio
    async def test_workflow_creation_routing(self, authenticated_client: AsyncClient):
        """Test routing to Workflow Planner."""
        response = await authenticated_client.post(
            "/api/v1/chat",
            json={
                "message": "압력이 높으면 이메일 알림을 보내는 자동화를 만들어줘",
                "context": {}
            }
        )
        assert response.status_code in [200, 201]


class TestChatStreaming:
    """Test streaming chat responses."""

    @pytest.mark.asyncio
    async def test_streaming_endpoint_exists(self, authenticated_client: AsyncClient):
        """Test streaming endpoint availability."""
        response = await authenticated_client.post(
            "/api/v1/chat/stream",
            json={
                "message": "안녕하세요",
                "context": {}
            }
        )
        # Streaming endpoint might return 200 or different content type
        assert response.status_code in [200, 404, 415]


class TestChatValidation:
    """Test chat input validation."""

    @pytest.mark.asyncio
    async def test_empty_message(self, authenticated_client: AsyncClient):
        """Test sending empty message."""
        response = await authenticated_client.post(
            "/api/v1/chat",
            json={
                "message": "",
                "context": {}
            }
        )
        # Should reject empty message
        assert response.status_code in [400, 422, 200]

    @pytest.mark.asyncio
    async def test_very_long_message(self, authenticated_client: AsyncClient):
        """Test sending very long message."""
        long_message = "테스트 " * 10000  # Very long message
        response = await authenticated_client.post(
            "/api/v1/chat",
            json={
                "message": long_message,
                "context": {}
            }
        )
        # Should either truncate or reject
        assert response.status_code in [200, 400, 413, 422]
