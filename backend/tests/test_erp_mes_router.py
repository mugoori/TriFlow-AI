"""
ERP/MES Router 테스트
erp_mes.py의 모든 엔드포인트에 대한 테스트
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4
from datetime import datetime, timedelta
from io import BytesIO

from httpx import AsyncClient


# ========== Mock Data Generators Tests ==========


class TestMockDataGenerators:
    """Mock 데이터 생성 함수 테스트"""

    def test_generate_erp_production_order(self):
        """ERP 생산 오더 생성"""
        from app.routers.erp_mes import generate_erp_production_order

        data = generate_erp_production_order()

        assert "AUFNR" in data
        assert data["AUFNR"].startswith("PO")
        assert "MATNR" in data
        assert "WERKS" in data
        assert "GAMNG" in data
        assert "MEINS" in data
        assert "STATUS" in data
        assert "PRIO" in data

    def test_generate_erp_inventory(self):
        """ERP 재고 데이터 생성"""
        from app.routers.erp_mes import generate_erp_inventory

        data = generate_erp_inventory()

        assert "INVENTORY_ITEM_ID" in data
        assert "ORGANIZATION_ID" in data
        assert "ITEM_NUMBER" in data
        assert "ON_HAND_QTY" in data
        assert "RESERVED_QTY" in data
        assert "AVAILABLE_QTY" in data
        assert "UOM_CODE" in data
        assert "LOT_NUMBER" in data

    def test_generate_erp_bom(self):
        """ERP BOM 데이터 생성"""
        from app.routers.erp_mes import generate_erp_bom

        data = generate_erp_bom()

        assert "BOM_ID" in data
        assert "PARENT_ITEM" in data
        assert "COMPONENT_ITEM" in data
        assert "COMPONENT_QTY" in data
        assert "UOM" in data
        assert "OPERATION_SEQ" in data
        assert "BOM_LEVEL" in data

    def test_generate_mes_work_order(self):
        """MES 작업 지시서 생성"""
        from app.routers.erp_mes import generate_mes_work_order

        data = generate_mes_work_order()

        assert "work_order_id" in data
        assert data["work_order_id"].startswith("WO")
        assert "production_line" in data
        assert "product_code" in data
        assert "planned_quantity" in data
        assert "produced_quantity" in data
        assert "defect_quantity" in data
        assert "status" in data
        assert "priority" in data
        assert "shift" in data

    def test_generate_mes_equipment_status(self):
        """MES 설비 상태 생성"""
        from app.routers.erp_mes import generate_mes_equipment_status

        data = generate_mes_equipment_status()

        assert "equipment_id" in data
        assert "equipment_name" in data
        assert "equipment_type" in data
        assert "status" in data
        assert "current_oee" in data
        assert "availability" in data
        assert "performance" in data
        assert "quality" in data
        assert "power_consumption" in data

    def test_generate_mes_quality_record(self):
        """MES 품질 기록 생성"""
        from app.routers.erp_mes import generate_mes_quality_record

        data = generate_mes_quality_record()

        assert "inspection_id" in data
        assert "work_order_id" in data
        assert "lot_number" in data
        assert "inspection_type" in data
        assert "sample_size" in data
        assert "passed_count" in data
        assert "failed_count" in data
        assert "result" in data
        assert "measurements" in data


class TestNormalizeData:
    """데이터 정규화 함수 테스트"""

    def test_normalize_erp_production_order(self):
        """ERP 생산 오더 정규화"""
        from app.routers.erp_mes import normalize_data

        raw_data = {
            "GAMNG": 100.5,
            "STATUS": "REL",
            "GSTRP": "2024-01-15T10:00:00"
        }

        quantity, status, timestamp = normalize_data(raw_data, "production_order")

        assert quantity == 100.5
        assert status == "REL"
        assert timestamp == datetime(2024, 1, 15, 10, 0, 0)

    def test_normalize_erp_inventory(self):
        """ERP 재고 정규화"""
        from app.routers.erp_mes import normalize_data

        raw_data = {
            "ON_HAND_QTY": 500.0,
            "LAST_UPDATE_DATE": "2024-01-15T10:00:00"
        }

        quantity, status, timestamp = normalize_data(raw_data, "inventory")

        assert quantity == 500.0
        assert status is None
        assert timestamp == datetime(2024, 1, 15, 10, 0, 0)

    def test_normalize_mes_work_order(self):
        """MES 작업 지시서 정규화"""
        from app.routers.erp_mes import normalize_data

        raw_data = {
            "planned_quantity": 200,
            "status": "in_progress",
            "scheduled_start": "2024-01-15T08:00:00"
        }

        quantity, status, timestamp = normalize_data(raw_data, "work_order")

        assert quantity == 200
        assert status == "in_progress"
        assert timestamp == datetime(2024, 1, 15, 8, 0, 0)

    def test_normalize_mes_equipment_status(self):
        """MES 설비 상태 정규화"""
        from app.routers.erp_mes import normalize_data

        raw_data = {
            "current_oee": 85.5,
            "status": "running",
            "last_update": "2024-01-15T10:30:00"
        }

        quantity, status, timestamp = normalize_data(raw_data, "equipment_status")

        assert quantity == 85.5
        assert status == "running"
        assert timestamp == datetime(2024, 1, 15, 10, 30, 0)

    def test_normalize_mes_quality_record(self):
        """MES 품질 기록 정규화"""
        from app.routers.erp_mes import normalize_data

        raw_data = {
            "sample_size": 50,
            "result": "pass",
            "inspection_date": "2024-01-15T14:00:00"
        }

        quantity, status, timestamp = normalize_data(raw_data, "quality_record")

        assert quantity == 50
        assert status == "pass"
        assert timestamp == datetime(2024, 1, 15, 14, 0, 0)

    def test_normalize_unknown_data(self):
        """알 수 없는 데이터 정규화"""
        from app.routers.erp_mes import normalize_data

        raw_data = {"some_field": "value"}

        quantity, status, timestamp = normalize_data(raw_data, "unknown")

        assert quantity is None
        assert status is None
        assert timestamp is None

    def test_normalize_invalid_timestamp(self):
        """잘못된 타임스탬프 처리"""
        from app.routers.erp_mes import normalize_data

        raw_data = {
            "GAMNG": 100,
            "GSTRP": "invalid-date"
        }

        quantity, status, timestamp = normalize_data(raw_data, "production_order")

        assert quantity == 100
        assert timestamp is None


class TestParseCSV:
    """CSV 파싱 테스트"""

    def test_parse_csv_content(self):
        """CSV 콘텐츠 파싱"""
        from app.routers.erp_mes import parse_csv_content

        csv_content = "id,name,value\n1,Item1,100\n2,Item2,200"
        rows = parse_csv_content(csv_content)

        assert len(rows) == 2
        assert rows[0]["id"] == "1"
        assert rows[0]["name"] == "Item1"
        assert rows[0]["value"] == "100"

    def test_parse_csv_empty(self):
        """빈 CSV 파싱"""
        from app.routers.erp_mes import parse_csv_content

        csv_content = "id,name\n"
        rows = parse_csv_content(csv_content)

        assert len(rows) == 0


# ========== API Endpoint Tests ==========


class TestErpMesDataEndpoints:
    """ERP/MES 데이터 API 테스트"""

    @pytest.mark.asyncio
    async def test_list_erp_mes_data(self, authenticated_client: AsyncClient):
        """ERP/MES 데이터 목록 조회"""
        response = await authenticated_client.get("/api/v1/erp-mes/data")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_list_erp_mes_data_with_filters(self, authenticated_client: AsyncClient):
        """필터로 ERP/MES 데이터 목록 조회"""
        response = await authenticated_client.get(
            "/api/v1/erp-mes/data",
            params={
                "source_type": "erp",
                "source_system": "sap",
                "record_type": "production_order",
                "limit": 10,
                "offset": 0
            }
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_create_erp_mes_data(self, authenticated_client: AsyncClient):
        """ERP/MES 데이터 생성"""
        response = await authenticated_client.post(
            "/api/v1/erp-mes/data",
            json={
                "source_type": "erp",
                "source_system": "sap",
                "record_type": "production_order",
                "external_id": "PO123456",
                "raw_data": {"AUFNR": "PO123456", "STATUS": "REL"},
                "normalized_quantity": 100.0,
                "normalized_status": "REL"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["source_type"] == "erp"
        assert data["source_system"] == "sap"
        assert data["external_id"] == "PO123456"

    @pytest.mark.asyncio
    async def test_get_erp_mes_data(self, authenticated_client: AsyncClient):
        """ERP/MES 데이터 상세 조회"""
        # 먼저 데이터 생성
        create_response = await authenticated_client.post(
            "/api/v1/erp-mes/data",
            json={
                "source_type": "mes",
                "source_system": "custom",
                "record_type": "work_order",
                "raw_data": {"work_order_id": "WO001"}
            }
        )
        data_id = create_response.json()["data_id"]

        # 상세 조회
        response = await authenticated_client.get(f"/api/v1/erp-mes/data/{data_id}")
        assert response.status_code == 200
        assert response.json()["data_id"] == data_id

    @pytest.mark.asyncio
    async def test_get_erp_mes_data_not_found(self, authenticated_client: AsyncClient):
        """존재하지 않는 ERP/MES 데이터 조회"""
        fake_id = uuid4()
        response = await authenticated_client.get(f"/api/v1/erp-mes/data/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_erp_mes_data(self, authenticated_client: AsyncClient):
        """ERP/MES 데이터 삭제"""
        # 먼저 데이터 생성
        create_response = await authenticated_client.post(
            "/api/v1/erp-mes/data",
            json={
                "source_type": "erp",
                "source_system": "oracle",
                "record_type": "inventory",
                "raw_data": {"ITEM_NUMBER": "ITEM-001"}
            }
        )
        data_id = create_response.json()["data_id"]

        # 삭제
        response = await authenticated_client.delete(f"/api/v1/erp-mes/data/{data_id}")
        assert response.status_code == 200
        assert response.json()["message"] == "Data deleted successfully"

        # 삭제 확인
        get_response = await authenticated_client.get(f"/api/v1/erp-mes/data/{data_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_erp_mes_data_not_found(self, authenticated_client: AsyncClient):
        """존재하지 않는 ERP/MES 데이터 삭제"""
        fake_id = uuid4()
        response = await authenticated_client.delete(f"/api/v1/erp-mes/data/{fake_id}")
        assert response.status_code == 404


class TestMockDataGeneration:
    """Mock 데이터 생성 API 테스트"""

    @pytest.mark.asyncio
    async def test_generate_mock_erp_production_order(self, authenticated_client: AsyncClient):
        """ERP 생산 오더 Mock 데이터 생성"""
        response = await authenticated_client.post(
            "/api/v1/erp-mes/mock/generate",
            json={
                "source_type": "erp",
                "source_system": "mock_sap",
                "record_type": "production_order",
                "count": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["generated_count"] == 5
        assert data["source_type"] == "erp"
        assert len(data["sample_data"]) <= 3

    @pytest.mark.asyncio
    async def test_generate_mock_erp_inventory(self, authenticated_client: AsyncClient):
        """ERP 재고 Mock 데이터 생성"""
        response = await authenticated_client.post(
            "/api/v1/erp-mes/mock/generate",
            json={
                "source_type": "erp",
                "record_type": "inventory",
                "count": 3
            }
        )
        assert response.status_code == 200
        assert response.json()["generated_count"] == 3

    @pytest.mark.asyncio
    async def test_generate_mock_erp_bom(self, authenticated_client: AsyncClient):
        """ERP BOM Mock 데이터 생성"""
        response = await authenticated_client.post(
            "/api/v1/erp-mes/mock/generate",
            json={
                "source_type": "erp",
                "record_type": "bom",
                "count": 2
            }
        )
        assert response.status_code == 200
        assert response.json()["generated_count"] == 2

    @pytest.mark.asyncio
    async def test_generate_mock_mes_work_order(self, authenticated_client: AsyncClient):
        """MES 작업 지시서 Mock 데이터 생성"""
        response = await authenticated_client.post(
            "/api/v1/erp-mes/mock/generate",
            json={
                "source_type": "mes",
                "record_type": "work_order",
                "count": 4
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["generated_count"] == 4
        assert data["source_type"] == "mes"

    @pytest.mark.asyncio
    async def test_generate_mock_mes_equipment_status(self, authenticated_client: AsyncClient):
        """MES 설비 상태 Mock 데이터 생성"""
        response = await authenticated_client.post(
            "/api/v1/erp-mes/mock/generate",
            json={
                "source_type": "mes",
                "record_type": "equipment_status",
                "count": 3
            }
        )
        assert response.status_code == 200
        assert response.json()["generated_count"] == 3

    @pytest.mark.asyncio
    async def test_generate_mock_mes_quality_record(self, authenticated_client: AsyncClient):
        """MES 품질 기록 Mock 데이터 생성"""
        response = await authenticated_client.post(
            "/api/v1/erp-mes/mock/generate",
            json={
                "source_type": "mes",
                "record_type": "quality_record",
                "count": 2
            }
        )
        assert response.status_code == 200
        assert response.json()["generated_count"] == 2

    @pytest.mark.asyncio
    async def test_generate_mock_invalid_record_type(self, authenticated_client: AsyncClient):
        """잘못된 record_type으로 Mock 데이터 생성"""
        response = await authenticated_client.post(
            "/api/v1/erp-mes/mock/generate",
            json={
                "source_type": "erp",
                "record_type": "invalid_type",
                "count": 1
            }
        )
        assert response.status_code == 400
        assert "Unknown record_type" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_available_mock_types(self, authenticated_client: AsyncClient):
        """사용 가능한 Mock 데이터 타입 조회"""
        response = await authenticated_client.get("/api/v1/erp-mes/mock/types")
        assert response.status_code == 200
        data = response.json()
        assert "erp" in data
        assert "mes" in data
        assert "production_order" in data["erp"]["record_types"]
        assert "work_order" in data["mes"]["record_types"]


class TestFieldMappingEndpoints:
    """필드 매핑 API 테스트"""

    @pytest.mark.asyncio
    async def test_list_field_mappings(self, authenticated_client: AsyncClient):
        """필드 매핑 목록 조회"""
        response = await authenticated_client.get("/api/v1/erp-mes/mappings")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_list_field_mappings_with_filters(self, authenticated_client: AsyncClient):
        """필터로 필드 매핑 목록 조회"""
        response = await authenticated_client.get(
            "/api/v1/erp-mes/mappings",
            params={
                "source_type": "erp",
                "source_system": "sap"
            }
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_create_field_mapping(self, authenticated_client: AsyncClient):
        """필드 매핑 생성"""
        response = await authenticated_client.post(
            "/api/v1/erp-mes/mappings",
            json={
                "source_type": "erp",
                "source_system": "sap",
                "record_type": "production_order",
                "source_field": "AUFNR",
                "target_field": "order_id",
                "transform_type": "direct",
                "transform_config": {}
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["source_field"] == "AUFNR"
        assert data["target_field"] == "order_id"
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_delete_field_mapping(self, authenticated_client: AsyncClient):
        """필드 매핑 삭제"""
        # 먼저 매핑 생성
        create_response = await authenticated_client.post(
            "/api/v1/erp-mes/mappings",
            json={
                "source_type": "mes",
                "source_system": "custom",
                "record_type": "work_order",
                "source_field": "work_order_id",
                "target_field": "id"
            }
        )
        mapping_id = create_response.json()["mapping_id"]

        # 삭제
        response = await authenticated_client.delete(f"/api/v1/erp-mes/mappings/{mapping_id}")
        assert response.status_code == 200
        assert response.json()["message"] == "Mapping deleted successfully"

    @pytest.mark.asyncio
    async def test_delete_field_mapping_not_found(self, authenticated_client: AsyncClient):
        """존재하지 않는 필드 매핑 삭제"""
        fake_id = uuid4()
        response = await authenticated_client.delete(f"/api/v1/erp-mes/mappings/{fake_id}")
        assert response.status_code == 404


class TestDataSourceEndpoints:
    """데이터 소스 API 테스트"""

    @pytest.mark.asyncio
    async def test_list_data_sources(self, authenticated_client: AsyncClient):
        """데이터 소스 목록 조회"""
        response = await authenticated_client.get("/api/v1/erp-mes/sources")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_list_data_sources_with_filter(self, authenticated_client: AsyncClient):
        """필터로 데이터 소스 목록 조회"""
        response = await authenticated_client.get(
            "/api/v1/erp-mes/sources",
            params={"source_type": "erp"}
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_create_data_source(self, authenticated_client: AsyncClient):
        """데이터 소스 생성"""
        response = await authenticated_client.post(
            "/api/v1/erp-mes/sources",
            json={
                "name": "Test SAP Source",
                "description": "Test SAP ERP connection",
                "source_type": "erp",
                "source_system": "sap",
                "connection_type": "rest_api",
                "connection_config": {
                    "base_url": "https://sap.example.com/api",
                    "auth_type": "basic"
                },
                "sync_enabled": True,
                "sync_interval_minutes": 30
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test SAP Source"
        assert data["source_type"] == "erp"
        assert data["sync_enabled"] is True

    @pytest.mark.asyncio
    async def test_get_data_source(self, authenticated_client: AsyncClient):
        """데이터 소스 상세 조회"""
        # 먼저 생성
        create_response = await authenticated_client.post(
            "/api/v1/erp-mes/sources",
            json={
                "name": "Detail Test Source",
                "source_type": "mes",
                "source_system": "mes_system",
                "connection_type": "db_direct",
                "connection_config": {}
            }
        )
        source_id = create_response.json()["source_id"]

        # 상세 조회
        response = await authenticated_client.get(f"/api/v1/erp-mes/sources/{source_id}")
        assert response.status_code == 200
        assert response.json()["source_id"] == source_id

    @pytest.mark.asyncio
    async def test_get_data_source_not_found(self, authenticated_client: AsyncClient):
        """존재하지 않는 데이터 소스 조회"""
        fake_id = uuid4()
        response = await authenticated_client.get(f"/api/v1/erp-mes/sources/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_data_source(self, authenticated_client: AsyncClient):
        """데이터 소스 삭제"""
        # 먼저 생성
        create_response = await authenticated_client.post(
            "/api/v1/erp-mes/sources",
            json={
                "name": "Delete Test Source",
                "source_type": "erp",
                "source_system": "test",
                "connection_type": "file"
            }
        )
        source_id = create_response.json()["source_id"]

        # 삭제
        response = await authenticated_client.delete(f"/api/v1/erp-mes/sources/{source_id}")
        assert response.status_code == 200
        assert response.json()["message"] == "Data source deleted successfully"

    @pytest.mark.asyncio
    async def test_delete_data_source_not_found(self, authenticated_client: AsyncClient):
        """존재하지 않는 데이터 소스 삭제"""
        fake_id = uuid4()
        response = await authenticated_client.delete(f"/api/v1/erp-mes/sources/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_test_data_source_connection_mock(self, authenticated_client: AsyncClient):
        """데이터 소스 연결 테스트 (Mock - DB Direct)"""
        # 먼저 db_direct 타입으로 생성
        create_response = await authenticated_client.post(
            "/api/v1/erp-mes/sources",
            json={
                "name": "Connection Test Source",
                "source_type": "erp",
                "source_system": "test",
                "connection_type": "db_direct",
                "connection_config": {}
            }
        )
        source_id = create_response.json()["source_id"]

        # 연결 테스트
        response = await authenticated_client.post(f"/api/v1/erp-mes/sources/{source_id}/test")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Mock" in data["message"]

    @pytest.mark.asyncio
    async def test_test_data_source_connection_not_found(self, authenticated_client: AsyncClient):
        """존재하지 않는 데이터 소스 연결 테스트"""
        fake_id = uuid4()
        response = await authenticated_client.post(f"/api/v1/erp-mes/sources/{fake_id}/test")
        assert response.status_code == 404


class TestDataSourceMCPTools:
    """DataSource MCP 도구 API 테스트"""

    @pytest.mark.asyncio
    async def test_get_datasource_tools(self, authenticated_client: AsyncClient):
        """DataSource 도구 목록 조회"""
        # 먼저 데이터 소스 생성
        create_response = await authenticated_client.post(
            "/api/v1/erp-mes/sources",
            json={
                "name": "Tools Test Source",
                "source_type": "erp",
                "source_system": "test",
                "connection_type": "rest_api",
                "connection_config": {"base_url": "http://test.local"}
            }
        )
        source_id = create_response.json()["source_id"]

        # 도구 목록 조회
        response = await authenticated_client.get(f"/api/v1/erp-mes/sources/{source_id}/tools")
        assert response.status_code == 200
        data = response.json()
        assert "source_id" in data
        assert "tools" in data
        assert isinstance(data["tools"], list)

    @pytest.mark.asyncio
    async def test_get_datasource_tools_not_found(self, authenticated_client: AsyncClient):
        """존재하지 않는 DataSource 도구 목록 조회"""
        fake_id = uuid4()
        response = await authenticated_client.get(f"/api/v1/erp-mes/sources/{fake_id}/tools")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_all_datasource_tools(self, authenticated_client: AsyncClient):
        """모든 DataSource 도구 목록 조회"""
        response = await authenticated_client.get("/api/v1/erp-mes/tools")
        assert response.status_code == 200
        data = response.json()
        assert "sources" in data
        assert "total_sources" in data
        assert "total_tools" in data


class TestStatisticsEndpoint:
    """통계 API 테스트"""

    @pytest.mark.asyncio
    async def test_get_erp_mes_stats(self, authenticated_client: AsyncClient):
        """ERP/MES 통계 조회"""
        response = await authenticated_client.get("/api/v1/erp-mes/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_records" in data
        assert "by_source_type" in data
        assert "by_record_type" in data
        assert "data_sources" in data
        assert "field_mappings" in data


class TestImportEndpoint:
    """Import API 테스트"""

    @pytest.mark.asyncio
    async def test_import_csv_file(self, authenticated_client: AsyncClient):
        """CSV 파일 Import"""
        csv_content = "id,name,quantity,status\n1,Item1,100,active\n2,Item2,200,inactive"

        response = await authenticated_client.post(
            "/api/v1/erp-mes/import",
            files={"file": ("test.csv", csv_content.encode("utf-8"), "text/csv")},
            data={
                "source_type": "erp",
                "record_type": "inventory",
                "source_system": "csv_import"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["imported_count"] == 2
        assert data["failed_count"] == 0

    @pytest.mark.asyncio
    async def test_import_csv_file_empty(self, authenticated_client: AsyncClient):
        """빈 CSV 파일 Import"""
        csv_content = "id,name\n"

        response = await authenticated_client.post(
            "/api/v1/erp-mes/import",
            files={"file": ("empty.csv", csv_content.encode("utf-8"), "text/csv")},
            data={
                "source_type": "erp",
                "record_type": "test"
            }
        )
        assert response.status_code == 400
        assert "데이터가 없습니다" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_import_unsupported_file_format(self, authenticated_client: AsyncClient):
        """지원하지 않는 파일 형식 Import"""
        content = "some text content"

        response = await authenticated_client.post(
            "/api/v1/erp-mes/import",
            files={"file": ("test.txt", content.encode("utf-8"), "text/plain")},
            data={
                "source_type": "erp",
                "record_type": "test"
            }
        )
        assert response.status_code == 400
        assert "지원하지 않는 파일 형식" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_import_csv_with_korean_encoding(self, authenticated_client: AsyncClient):
        """한글 인코딩 CSV 파일 Import"""
        csv_content = "id,name,quantity\n1,제품1,100\n2,제품2,200"

        response = await authenticated_client.post(
            "/api/v1/erp-mes/import",
            files={"file": ("korean.csv", csv_content.encode("utf-8"), "text/csv")},
            data={
                "source_type": "mes",
                "record_type": "work_order"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["imported_count"] == 2


class TestAuthorizationRequired:
    """인증 필요 테스트"""

    @pytest.mark.asyncio
    async def test_list_data_without_auth(self, client: AsyncClient):
        """인증 없이 데이터 목록 조회"""
        response = await client.get("/api/v1/erp-mes/data")
        assert response.status_code in [401, 403]

    @pytest.mark.asyncio
    async def test_create_data_without_auth(self, client: AsyncClient):
        """인증 없이 데이터 생성"""
        response = await client.post(
            "/api/v1/erp-mes/data",
            json={
                "source_type": "erp",
                "source_system": "test",
                "record_type": "test",
                "raw_data": {}
            }
        )
        assert response.status_code in [401, 403]

    @pytest.mark.asyncio
    async def test_generate_mock_without_auth(self, client: AsyncClient):
        """인증 없이 Mock 데이터 생성"""
        response = await client.post(
            "/api/v1/erp-mes/mock/generate",
            json={
                "source_type": "erp",
                "record_type": "production_order",
                "count": 1
            }
        )
        assert response.status_code in [401, 403]

    @pytest.mark.asyncio
    async def test_get_stats_without_auth(self, client: AsyncClient):
        """인증 없이 통계 조회"""
        response = await client.get("/api/v1/erp-mes/stats")
        assert response.status_code in [401, 403]
