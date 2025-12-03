"""
TriFlow AI - Sensor Tests
==========================
Tests for sensor data endpoints (via /api/v1/sensors/*)
"""

import pytest
from httpx import AsyncClient


class TestSensorEndpoints:
    """Test sensor data endpoints."""

    @pytest.mark.asyncio
    async def test_get_sensor_data(self, client: AsyncClient):
        """Test getting sensor data."""
        response = await client.get("/api/v1/sensors/data")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data

    @pytest.mark.asyncio
    async def test_get_sensor_filters(self, client: AsyncClient):
        """Test getting sensor filter options."""
        response = await client.get("/api/v1/sensors/filters")
        assert response.status_code == 200
        data = response.json()
        assert "lines" in data
        assert "sensor_types" in data
        assert isinstance(data["lines"], list)
        assert isinstance(data["sensor_types"], list)

    @pytest.mark.asyncio
    async def test_get_sensor_summary(self, client: AsyncClient):
        """Test getting sensor summary."""
        response = await client.get("/api/v1/sensors/summary")
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert isinstance(data["summary"], list)

    @pytest.mark.asyncio
    async def test_sensor_data_with_filters(self, client: AsyncClient):
        """Test getting sensor data with filters."""
        response = await client.get(
            "/api/v1/sensors/data",
            params={
                "line_code": "LINE_A",
                "sensor_type": "temperature",
                "page": 1,
                "page_size": 10,
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    @pytest.mark.asyncio
    async def test_sensor_stream_status(self, client: AsyncClient):
        """Test WebSocket stream status endpoint."""
        response = await client.get("/api/v1/sensors/stream/status")
        assert response.status_code == 200
        data = response.json()
        assert "active_connections" in data
        assert "websocket_url" in data


class TestSensorImport:
    """Test sensor data import."""

    @pytest.mark.asyncio
    async def test_get_import_template(self, client: AsyncClient):
        """Test getting import template."""
        response = await client.get("/api/v1/sensors/import/template")
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_import_invalid_file_type(self, authenticated_client: AsyncClient):
        """Test importing with invalid file type."""
        # Create a fake txt file
        response = await authenticated_client.post(
            "/api/v1/sensors/import",
            files={"file": ("test.txt", b"invalid content", "text/plain")}
        )
        # Should reject non-CSV/Excel files
        assert response.status_code == 400
