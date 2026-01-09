"""
TriFlow AI - Sensor Tests
==========================
Tests for sensor data endpoints (via /api/v1/sensors/*)
"""

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock
from datetime import datetime


class TestSensorPydanticModels:
    """Sensor Pydantic 모델 테스트"""

    def test_sensor_data_item_model(self):
        """SensorDataItem 모델"""
        from app.routers.sensors import SensorDataItem

        item = SensorDataItem(
            sensor_id="LINE_A_temperature",
            recorded_at=datetime.now(),
            line_code="LINE_A",
            sensor_type="temperature",
            value=85.5,
            unit="C",
        )

        assert item.line_code == "LINE_A"
        assert item.sensor_type == "temperature"
        assert item.value == 85.5

    def test_sensor_data_response_model(self):
        """SensorDataResponse 모델"""
        from app.routers.sensors import SensorDataResponse, SensorDataItem

        item = SensorDataItem(
            sensor_id="LINE_A_temperature",
            recorded_at=datetime.now(),
            line_code="LINE_A",
            sensor_type="temperature",
            value=85.5,
            unit="C",
        )

        response = SensorDataResponse(
            data=[item],
            total=1,
            page=1,
            page_size=10,
        )

        assert len(response.data) == 1
        assert response.total == 1
        assert response.page == 1

    def test_sensor_filter_options_model(self):
        """SensorFilterOptions 모델"""
        from app.routers.sensors import SensorFilterOptions

        options = SensorFilterOptions(
            lines=["LINE_A", "LINE_B"],
            sensor_types=["temperature", "humidity"],
        )

        assert len(options.lines) == 2
        assert len(options.sensor_types) == 2

    def test_line_summary_model(self):
        """LineSummary 모델"""
        from app.routers.sensors import LineSummary

        summary = LineSummary(
            line_code="LINE_A",
            avg_temperature=75.5,
            avg_pressure=1.2,
            avg_humidity=50.0,
            total_readings=100,
            last_updated="2024-01-01T00:00:00",
        )

        assert summary.line_code == "LINE_A"
        assert summary.total_readings == 100
        assert summary.avg_temperature == 75.5

    def test_sensor_summary_response_model(self):
        """SensorSummaryResponse 모델"""
        from app.routers.sensors import SensorSummaryResponse, LineSummary

        summary = LineSummary(
            line_code="LINE_A",
            total_readings=100,
        )

        response = SensorSummaryResponse(summary=[summary])

        assert len(response.summary) == 1

    def test_import_result_model(self):
        """ImportResult 모델"""
        from app.routers.sensors import ImportResult

        result = ImportResult(
            success=True,
            message="Import completed",
            total_rows=100,
            imported_rows=100,
            failed_rows=0,
            errors=[],
        )

        assert result.success is True
        assert result.imported_rows == 100


class TestConnectionManager:
    """ConnectionManager 테스트"""

    def test_connection_manager_init(self):
        """ConnectionManager 초기화"""
        from app.routers.sensors import ConnectionManager

        manager = ConnectionManager()

        assert isinstance(manager.active_connections, set)
        assert len(manager.active_connections) == 0

    @pytest.mark.asyncio
    async def test_connection_manager_connect(self):
        """ConnectionManager 연결"""
        from app.routers.sensors import ConnectionManager

        manager = ConnectionManager()
        mock_websocket = AsyncMock()

        await manager.connect(mock_websocket)

        assert mock_websocket in manager.active_connections
        mock_websocket.accept.assert_called_once()

    def test_connection_manager_disconnect(self):
        """ConnectionManager 연결 해제"""
        from app.routers.sensors import ConnectionManager

        manager = ConnectionManager()
        mock_websocket = AsyncMock()
        manager.active_connections.add(mock_websocket)

        manager.disconnect(mock_websocket)

        assert mock_websocket not in manager.active_connections

    @pytest.mark.asyncio
    async def test_connection_manager_broadcast(self):
        """ConnectionManager 브로드캐스트"""
        from app.routers.sensors import ConnectionManager

        manager = ConnectionManager()
        mock_websocket1 = AsyncMock()
        mock_websocket2 = AsyncMock()
        manager.active_connections.add(mock_websocket1)
        manager.active_connections.add(mock_websocket2)

        message = {"type": "sensor_update", "data": {"value": 85}}
        await manager.broadcast(message)

        mock_websocket1.send_json.assert_called_once_with(message)
        mock_websocket2.send_json.assert_called_once_with(message)


class TestGenerateSimulatedSensorData:
    """generate_simulated_sensor_data 테스트"""

    def test_generate_simulated_sensor_data(self):
        """시뮬레이션 데이터 생성"""
        from app.routers.sensors import generate_simulated_sensor_data

        result = generate_simulated_sensor_data()

        assert "timestamp" in result
        assert "data" in result
        assert "type" in result
        assert result["type"] == "sensor_update"
        assert isinstance(result["data"], list)
        assert len(result["data"]) > 0

    def test_simulated_sensor_has_required_fields(self):
        """시뮬레이션 센서 필수 필드"""
        from app.routers.sensors import generate_simulated_sensor_data

        result = generate_simulated_sensor_data()
        sensor = result["data"][0]

        assert "sensor_id" in sensor
        assert "line_code" in sensor
        assert "sensor_type" in sensor
        assert "value" in sensor
        assert "unit" in sensor
        assert "recorded_at" in sensor


class TestGetStreamStatus:
    """get_stream_status 테스트"""

    @pytest.mark.asyncio
    async def test_get_stream_status(self):
        """스트림 상태 조회"""
        from app.routers.sensors import get_stream_status, manager

        # Store original connections
        original = manager.active_connections.copy()

        # Add mock connections
        manager.active_connections = {AsyncMock(), AsyncMock()}

        result = await get_stream_status()

        assert "active_connections" in result
        assert result["active_connections"] == 2
        assert "websocket_url" in result

        # Restore original connections
        manager.active_connections = original


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
