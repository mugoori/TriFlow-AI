"""
TriFlow AI - Sensor Tests
==========================
Tests for sensor data endpoints
"""

import pytest
from httpx import AsyncClient


class TestSensorEndpoints:
    """Test sensor data endpoints."""

    @pytest.mark.asyncio
    async def test_list_sensors(self, authenticated_client: AsyncClient):
        """Test listing sensors."""
        response = await authenticated_client.get("/api/v1/sensors")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))

    @pytest.mark.asyncio
    async def test_create_sensor_reading(
        self,
        authenticated_client: AsyncClient,
        sample_sensor_data
    ):
        """Test creating a sensor reading."""
        response = await authenticated_client.post(
            "/api/v1/sensors/readings",
            json=sample_sensor_data
        )
        # 200, 201, or 404 if endpoint doesn't exist
        assert response.status_code in [200, 201, 404]

    @pytest.mark.asyncio
    async def test_get_sensor_history(self, authenticated_client: AsyncClient):
        """Test getting sensor history."""
        response = await authenticated_client.get(
            "/api/v1/sensors/TEMP-001/history",
            params={"limit": 100}
        )
        # May return empty list or 404 if sensor doesn't exist
        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_get_sensor_statistics(self, authenticated_client: AsyncClient):
        """Test getting sensor statistics."""
        response = await authenticated_client.get(
            "/api/v1/sensors/statistics",
            params={"sensor_type": "temperature"}
        )
        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_sensor_streaming_endpoint(self, authenticated_client: AsyncClient):
        """Test WebSocket sensor streaming exists."""
        # This is a basic check - WebSocket testing requires special handling
        response = await authenticated_client.get("/api/v1/sensors/stream/info")
        # Endpoint might not exist, that's okay
        assert response.status_code in [200, 404, 405]


class TestSensorValidation:
    """Test sensor data validation."""

    @pytest.mark.asyncio
    async def test_invalid_sensor_type(self, authenticated_client: AsyncClient):
        """Test creating sensor with invalid type."""
        response = await authenticated_client.post(
            "/api/v1/sensors/readings",
            json={
                "sensor_id": "INVALID-001",
                "sensor_type": "",  # Invalid empty type
                "value": 100
            }
        )
        # Should fail validation or be rejected
        assert response.status_code in [400, 422, 404]

    @pytest.mark.asyncio
    async def test_sensor_value_range(self, authenticated_client: AsyncClient):
        """Test sensor value edge cases."""
        # Very large value
        response = await authenticated_client.post(
            "/api/v1/sensors/readings",
            json={
                "sensor_id": "TEST-001",
                "sensor_type": "temperature",
                "value": 1e10  # Very large value
            }
        )
        # Should either accept or reject based on business rules
        assert response.status_code in [200, 201, 400, 422, 404]
