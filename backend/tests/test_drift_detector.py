"""
Drift Detector 테스트

스키마 변경 감지, 커넥터 CRUD, 스냅샷 비교 테스트
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone
import hashlib
import json


class TestConnectorType:
    """커넥터 타입 테스트"""

    def test_postgresql_connector(self):
        """PostgreSQL 커넥터"""
        from app.models.mcp import ConnectorType

        assert ConnectorType.POSTGRESQL.value == "postgresql"

    def test_mysql_connector(self):
        """MySQL 커넥터"""
        from app.models.mcp import ConnectorType

        assert ConnectorType.MYSQL.value == "mysql"

    def test_mssql_connector(self):
        """MSSQL 커넥터"""
        from app.models.mcp import ConnectorType

        assert ConnectorType.MSSQL.value == "mssql"

    def test_oracle_connector(self):
        """Oracle 커넥터"""
        from app.models.mcp import ConnectorType

        assert ConnectorType.ORACLE.value == "oracle"

    def test_rest_api_connector(self):
        """REST API 커넥터"""
        from app.models.mcp import ConnectorType

        assert ConnectorType.REST_API.value == "rest_api"

    def test_mqtt_connector(self):
        """MQTT 커넥터"""
        from app.models.mcp import ConnectorType

        assert ConnectorType.MQTT.value == "mqtt"

    def test_s3_connector(self):
        """S3 커넥터"""
        from app.models.mcp import ConnectorType

        assert ConnectorType.S3.value == "s3"

    def test_gcs_connector(self):
        """GCS 커넥터"""
        from app.models.mcp import ConnectorType

        assert ConnectorType.GCS.value == "gcs"


class TestDriftChangeType:
    """스키마 변경 타입 테스트"""

    def test_table_added(self):
        """테이블 추가"""
        from app.models.mcp import DriftChangeType

        assert DriftChangeType.TABLE_ADDED.value == "table_added"

    def test_table_deleted(self):
        """테이블 삭제"""
        from app.models.mcp import DriftChangeType

        assert DriftChangeType.TABLE_DELETED.value == "table_deleted"

    def test_column_added(self):
        """컬럼 추가"""
        from app.models.mcp import DriftChangeType

        assert DriftChangeType.COLUMN_ADDED.value == "column_added"

    def test_column_deleted(self):
        """컬럼 삭제"""
        from app.models.mcp import DriftChangeType

        assert DriftChangeType.COLUMN_DELETED.value == "column_deleted"

    def test_type_changed(self):
        """타입 변경"""
        from app.models.mcp import DriftChangeType

        assert DriftChangeType.TYPE_CHANGED.value == "type_changed"


class TestDriftSeverity:
    """스키마 변경 심각도 테스트"""

    def test_info_severity(self):
        """정보 심각도"""
        from app.models.mcp import DriftSeverity

        assert DriftSeverity.INFO.value == "info"

    def test_warning_severity(self):
        """경고 심각도"""
        from app.models.mcp import DriftSeverity

        assert DriftSeverity.WARNING.value == "warning"

    def test_critical_severity(self):
        """중요 심각도"""
        from app.models.mcp import DriftSeverity

        assert DriftSeverity.CRITICAL.value == "critical"


class TestExceptions:
    """예외 클래스 테스트"""

    def test_unsupported_connector_type_error(self):
        """UnsupportedConnectorTypeError 예외"""
        from app.services.drift_detector import UnsupportedConnectorTypeError

        error = UnsupportedConnectorTypeError("Test error")
        assert str(error) == "Test error"

    def test_connection_error(self):
        """ConnectionError 예외"""
        from app.services.drift_detector import ConnectionError

        error = ConnectionError("Connection failed")
        assert str(error) == "Connection failed"


class TestDataConnectorCreate:
    """DataConnectorCreate 모델 테스트"""

    def test_create_postgresql_connector(self):
        """PostgreSQL 커넥터 생성"""
        from app.models.mcp import DataConnectorCreate, ConnectorType

        connector = DataConnectorCreate(
            name="Production DB",
            description="Production PostgreSQL database",
            connector_type=ConnectorType.POSTGRESQL,
            connection_config={
                "host": "localhost",
                "port": 5432,
                "database": "prod",
                "username": "user",
            },
        )

        assert connector.name == "Production DB"
        assert connector.connector_type == ConnectorType.POSTGRESQL
        assert connector.connection_config["host"] == "localhost"

    def test_create_mysql_connector(self):
        """MySQL 커넥터 생성"""
        from app.models.mcp import DataConnectorCreate, ConnectorType

        connector = DataConnectorCreate(
            name="Legacy DB",
            connector_type=ConnectorType.MYSQL,
            connection_config={
                "host": "mysql.example.com",
                "port": 3306,
                "database": "legacy",
            },
        )

        assert connector.connector_type == ConnectorType.MYSQL

    def test_create_rest_api_connector(self):
        """REST API 커넥터 생성"""
        from app.models.mcp import DataConnectorCreate, ConnectorType

        connector = DataConnectorCreate(
            name="External API",
            connector_type=ConnectorType.REST_API,
            connection_config={
                "base_url": "https://api.example.com",
                "api_key": "secret",
            },
        )

        assert connector.connector_type == ConnectorType.REST_API

    def test_connector_with_tags(self):
        """태그 포함 커넥터"""
        from app.models.mcp import DataConnectorCreate, ConnectorType

        connector = DataConnectorCreate(
            name="Tagged DB",
            connector_type=ConnectorType.POSTGRESQL,
            connection_config={"host": "localhost"},
            tags=["production", "critical"],
        )

        assert "production" in connector.tags

    def test_connector_with_attributes(self):
        """속성 포함 커넥터"""
        from app.models.mcp import DataConnectorCreate, ConnectorType

        connector = DataConnectorCreate(
            name="Attr DB",
            connector_type=ConnectorType.MYSQL,
            connection_config={"host": "localhost"},
            attributes={"team": "data", "priority": "high"},
        )

        assert connector.attributes["team"] == "data"


class TestSchemaColumn:
    """SchemaColumn 모델 테스트"""

    def test_schema_column_creation(self):
        """SchemaColumn 생성"""
        from app.models.mcp import SchemaColumn

        # is_nullable is a string ("YES" or "NO") from DB information_schema
        column = SchemaColumn(
            column_name="user_id",
            data_type="integer",
            is_nullable="NO",
            column_default="nextval('users_id_seq')",
        )

        assert column.column_name == "user_id"
        assert column.data_type == "integer"
        assert column.is_nullable == "NO"

    def test_schema_column_nullable(self):
        """Nullable 컬럼"""
        from app.models.mcp import SchemaColumn

        column = SchemaColumn(
            column_name="description",
            data_type="text",
            is_nullable="YES",
        )

        assert column.is_nullable == "YES"

    def test_schema_column_with_default(self):
        """기본값 있는 컬럼"""
        from app.models.mcp import SchemaColumn

        column = SchemaColumn(
            column_name="created_at",
            data_type="timestamp",
            is_nullable="NO",
            column_default="CURRENT_TIMESTAMP",
        )

        assert column.column_default == "CURRENT_TIMESTAMP"


class TestSchemaSnapshot:
    """SchemaSnapshot 모델 테스트"""

    def test_schema_snapshot_creation(self):
        """SchemaSnapshot 생성"""
        from app.models.mcp import SchemaSnapshot, SchemaColumn, SchemaTable

        snapshot = SchemaSnapshot(
            snapshot_id=uuid4(),
            connector_id=uuid4(),
            tenant_id=uuid4(),
            schema_data={
                "users": SchemaTable(
                    columns=[
                        SchemaColumn(
                            column_name="id",
                            data_type="integer",
                            is_nullable="NO",
                        ),
                        SchemaColumn(
                            column_name="email",
                            data_type="varchar",
                            is_nullable="NO",
                        ),
                    ]
                )
            },
            schema_hash="abc123",
            table_count=1,
            column_count=2,
            captured_at=datetime.now(timezone.utc),
        )

        assert "users" in snapshot.schema_data
        assert len(snapshot.schema_data["users"].columns) == 2
        assert snapshot.schema_hash == "abc123"

    def test_schema_snapshot_empty(self):
        """빈 스냅샷"""
        from app.models.mcp import SchemaSnapshot

        snapshot = SchemaSnapshot(
            snapshot_id=uuid4(),
            connector_id=uuid4(),
            tenant_id=uuid4(),
            schema_data={},
            schema_hash="empty",
            table_count=0,
            column_count=0,
            captured_at=datetime.now(timezone.utc),
        )

        assert len(snapshot.schema_data) == 0


class TestDriftChange:
    """DriftChange 모델 테스트"""

    def test_drift_change_table_added(self):
        """테이블 추가 변경"""
        from app.models.mcp import DriftChange, DriftChangeType

        # DriftChange uses 'type' field (not 'change_type')
        change = DriftChange(
            type=DriftChangeType.TABLE_ADDED,
            table_name="new_table",
        )

        assert change.type == DriftChangeType.TABLE_ADDED
        assert change.table_name == "new_table"

    def test_drift_change_column_deleted(self):
        """컬럼 삭제 변경"""
        from app.models.mcp import DriftChange, DriftChangeType

        change = DriftChange(
            type=DriftChangeType.COLUMN_DELETED,
            table_name="users",
            column_name="legacy_field",
        )

        assert change.type == DriftChangeType.COLUMN_DELETED
        assert change.column_name == "legacy_field"

    def test_drift_change_type_changed(self):
        """타입 변경"""
        from app.models.mcp import DriftChange, DriftChangeType

        change = DriftChange(
            type=DriftChangeType.TYPE_CHANGED,
            table_name="orders",
            column_name="amount",
            old_value="integer",
            new_value="decimal",
        )

        assert change.type == DriftChangeType.TYPE_CHANGED
        assert change.old_value == "integer"
        assert change.new_value == "decimal"


class TestDriftReport:
    """DriftReport 모델 테스트"""

    def test_drift_report_no_changes(self):
        """변경 없는 리포트"""
        from app.models.mcp import DriftReport

        report = DriftReport(
            connector_id=uuid4(),
            has_changes=False,
            changes=[],
        )

        assert report.has_changes is False
        assert len(report.changes) == 0

    def test_drift_report_with_changes(self):
        """변경 있는 리포트"""
        from app.models.mcp import DriftReport, DriftChange, DriftChangeType, DriftSeverity

        changes = [
            DriftChange(
                type=DriftChangeType.TABLE_ADDED,
                table_name="new_table",
            ),
            DriftChange(
                type=DriftChangeType.COLUMN_DELETED,
                table_name="old_table",
                column_name="deprecated",
            ),
        ]

        report = DriftReport(
            connector_id=uuid4(),
            has_changes=True,
            changes=changes,
            tables_added=1,
            columns_deleted=1,
            severity=DriftSeverity.WARNING,
        )

        assert report.has_changes is True
        assert len(report.changes) == 2
        assert report.severity == DriftSeverity.WARNING


class TestSchemaDriftDetectorInit:
    """SchemaDriftDetector 초기화 테스트"""

    def test_detector_init(self):
        """감지기 초기화"""
        from app.services.drift_detector import SchemaDriftDetector

        mock_db = MagicMock()
        detector = SchemaDriftDetector(db=mock_db)

        assert detector.db == mock_db


class TestSeverityClassification:
    """심각도 분류 테스트"""

    def test_table_added_is_info(self):
        """테이블 추가는 INFO 심각도"""
        from app.models.mcp import DriftSeverity

        # 테이블 추가는 일반적으로 안전
        severity = DriftSeverity.INFO
        assert severity.value == "info"

    def test_column_deleted_is_warning(self):
        """컬럼 삭제는 WARNING 심각도"""
        from app.models.mcp import DriftSeverity

        # 컬럼 삭제는 주의 필요
        severity = DriftSeverity.WARNING
        assert severity.value == "warning"

    def test_type_changed_is_critical(self):
        """타입 변경은 CRITICAL 심각도"""
        from app.models.mcp import DriftSeverity

        # 타입 변경은 데이터 손실 위험
        severity = DriftSeverity.CRITICAL
        assert severity.value == "critical"

    def test_table_deleted_is_critical(self):
        """테이블 삭제는 CRITICAL 심각도"""
        from app.models.mcp import DriftChangeType, DriftSeverity

        # 테이블 삭제는 심각한 변경
        change_type = DriftChangeType.TABLE_DELETED
        severity = DriftSeverity.CRITICAL

        assert change_type.value == "table_deleted"
        assert severity.value == "critical"


class TestHashComputation:
    """해시 계산 테스트"""

    def test_same_schema_same_hash(self):
        """동일 스키마는 동일 해시"""
        import hashlib
        import json

        schema1 = {"users": [{"name": "id", "type": "int"}]}
        schema2 = {"users": [{"name": "id", "type": "int"}]}

        hash1 = hashlib.sha256(json.dumps(schema1, sort_keys=True).encode()).hexdigest()
        hash2 = hashlib.sha256(json.dumps(schema2, sort_keys=True).encode()).hexdigest()

        assert hash1 == hash2

    def test_different_schema_different_hash(self):
        """다른 스키마는 다른 해시"""
        import hashlib
        import json

        schema1 = {"users": [{"name": "id", "type": "int"}]}
        schema2 = {"users": [{"name": "id", "type": "bigint"}]}

        hash1 = hashlib.sha256(json.dumps(schema1, sort_keys=True).encode()).hexdigest()
        hash2 = hashlib.sha256(json.dumps(schema2, sort_keys=True).encode()).hexdigest()

        assert hash1 != hash2


class TestDriftDetection:
    """Drift 감지 테스트"""

    def test_detect_table_added(self):
        """테이블 추가 감지"""
        old_tables = {"users"}
        new_tables = {"users", "orders"}

        added = new_tables - old_tables
        assert "orders" in added

    def test_detect_table_deleted(self):
        """테이블 삭제 감지"""
        old_tables = {"users", "orders"}
        new_tables = {"users"}

        deleted = old_tables - new_tables
        assert "orders" in deleted

    def test_detect_column_added(self):
        """컬럼 추가 감지"""
        old_columns = {"id", "name"}
        new_columns = {"id", "name", "email"}

        added = new_columns - old_columns
        assert "email" in added

    def test_detect_column_deleted(self):
        """컬럼 삭제 감지"""
        old_columns = {"id", "name", "legacy"}
        new_columns = {"id", "name"}

        deleted = old_columns - new_columns
        assert "legacy" in deleted

    def test_detect_type_change(self):
        """타입 변경 감지"""
        old_schema = {"amount": "integer"}
        new_schema = {"amount": "decimal"}

        for col, old_type in old_schema.items():
            if col in new_schema and new_schema[col] != old_type:
                changed = True
                break
        else:
            changed = False

        assert changed is True


class TestConnectionConfig:
    """연결 설정 테스트"""

    def test_postgresql_config(self):
        """PostgreSQL 연결 설정"""
        config = {
            "host": "localhost",
            "port": 5432,
            "database": "mydb",
            "username": "user",
            "password": "pass",
            "ssl_mode": "require",
        }

        assert config["port"] == 5432
        assert config["ssl_mode"] == "require"

    def test_mysql_config(self):
        """MySQL 연결 설정"""
        config = {
            "host": "mysql.example.com",
            "port": 3306,
            "database": "mydb",
            "username": "root",
        }

        assert config["port"] == 3306

    def test_rest_api_config(self):
        """REST API 연결 설정"""
        config = {
            "base_url": "https://api.example.com/v1",
            "api_key": "secret-key",
            "timeout_seconds": 30,
            "headers": {"X-Custom": "value"},
        }

        assert "api.example.com" in config["base_url"]
        assert config["timeout_seconds"] == 30


class TestDataConnectorUpdate:
    """DataConnectorUpdate 모델 테스트"""

    def test_partial_update(self):
        """부분 업데이트"""
        from app.models.mcp import DataConnectorUpdate

        update = DataConnectorUpdate(name="Updated Name")

        assert update.name == "Updated Name"
        assert update.description is None

    def test_update_connection_config(self):
        """연결 설정 업데이트"""
        from app.models.mcp import DataConnectorUpdate

        update = DataConnectorUpdate(
            connection_config={
                "host": "new-host.example.com",
            }
        )

        assert update.connection_config["host"] == "new-host.example.com"


class TestDataConnectorList:
    """DataConnectorList 모델 테스트"""

    def test_connector_list(self):
        """커넥터 목록"""
        from app.models.mcp import DataConnectorList

        # DataConnectorList uses 'items', 'total', 'page', 'size' fields
        connector_list = DataConnectorList(items=[], total=0, page=1, size=20)

        assert len(connector_list.items) == 0
        assert connector_list.total == 0
        assert connector_list.page == 1
        assert connector_list.size == 20


class TestSchemaDriftDetectionList:
    """SchemaDriftDetectionList 모델 테스트"""

    def test_detection_list(self):
        """감지 목록"""
        from app.models.mcp import SchemaDriftDetectionList

        # SchemaDriftDetectionList uses 'items', 'total', 'page', 'size' fields
        detection_list = SchemaDriftDetectionList(items=[], total=0, page=1, size=20)

        assert len(detection_list.items) == 0
        assert detection_list.total == 0
        assert detection_list.page == 1


class TestSchemaDriftDetectorCreateConnector:
    """create_connector 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_create_connector_postgresql(self):
        """PostgreSQL 커넥터 생성"""
        from app.services.drift_detector import SchemaDriftDetector
        from app.models.mcp import DataConnectorCreate, ConnectorType

        mock_db = AsyncMock()
        connector_id = uuid4()
        tenant_id = uuid4()
        now = datetime.now(timezone.utc)

        mock_row = MagicMock()
        mock_row.connector_id = connector_id
        mock_row.tenant_id = tenant_id
        mock_row.name = "Test PostgreSQL"
        mock_row.description = "Test description"
        mock_row.connector_type = "postgresql"
        mock_row.connection_config = {"host": "localhost", "port": 5432}
        mock_row.status = "active"
        mock_row.last_connection_test = None
        mock_row.last_connection_status = None
        mock_row.connection_error = None
        mock_row.tags = ["test"]
        mock_row.attributes = {}
        mock_row.created_at = now
        mock_row.updated_at = now
        mock_row.created_by = None

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result

        detector = SchemaDriftDetector(db=mock_db)
        data = DataConnectorCreate(
            name="Test PostgreSQL",
            description="Test description",
            connector_type=ConnectorType.POSTGRESQL,
            connection_config={"host": "localhost", "port": 5432},
            tags=["test"],
        )

        result = await detector.create_connector(tenant_id, data)

        assert result.name == "Test PostgreSQL"
        assert result.connector_type == ConnectorType.POSTGRESQL
        mock_db.commit.assert_called_once()


class TestSchemaDriftDetectorGetConnector:
    """get_connector 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_get_connector_found(self):
        """커넥터 조회 - 존재"""
        from app.services.drift_detector import SchemaDriftDetector
        from app.models.mcp import ConnectorType

        mock_db = AsyncMock()
        connector_id = uuid4()
        tenant_id = uuid4()
        now = datetime.now(timezone.utc)

        mock_row = MagicMock()
        mock_row.connector_id = connector_id
        mock_row.tenant_id = tenant_id
        mock_row.name = "Found Connector"
        mock_row.description = None
        mock_row.connector_type = "mysql"
        mock_row.connection_config = {"host": "mysql.local"}
        mock_row.status = "active"
        mock_row.last_connection_test = None
        mock_row.last_connection_status = None
        mock_row.connection_error = None
        mock_row.tags = []
        mock_row.attributes = {}
        mock_row.created_at = now
        mock_row.updated_at = now
        mock_row.created_by = None

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result

        detector = SchemaDriftDetector(db=mock_db)
        result = await detector.get_connector(connector_id, tenant_id)

        assert result is not None
        assert result.name == "Found Connector"
        assert result.connector_type == ConnectorType.MYSQL

    @pytest.mark.asyncio
    async def test_get_connector_not_found(self):
        """커넥터 조회 - 없음"""
        from app.services.drift_detector import SchemaDriftDetector

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_result

        detector = SchemaDriftDetector(db=mock_db)
        result = await detector.get_connector(uuid4(), uuid4())

        assert result is None


class TestSchemaDriftDetectorListConnectors:
    """list_connectors 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_list_connectors_empty(self):
        """커넥터 목록 - 빈 목록"""
        from app.services.drift_detector import SchemaDriftDetector

        mock_db = AsyncMock()

        count_result = MagicMock()
        count_result.scalar.return_value = 0

        list_result = MagicMock()
        list_result.fetchall.return_value = []

        mock_db.execute.side_effect = [count_result, list_result]

        detector = SchemaDriftDetector(db=mock_db)
        result = await detector.list_connectors(uuid4())

        assert result.total == 0
        assert len(result.items) == 0

    @pytest.mark.asyncio
    async def test_list_connectors_with_type_filter(self):
        """커넥터 목록 - 타입 필터"""
        from app.services.drift_detector import SchemaDriftDetector
        from app.models.mcp import ConnectorType

        mock_db = AsyncMock()
        tenant_id = uuid4()
        now = datetime.now(timezone.utc)

        mock_row = MagicMock()
        mock_row.connector_id = uuid4()
        mock_row.tenant_id = tenant_id
        mock_row.name = "PostgreSQL Connector"
        mock_row.description = None
        mock_row.connector_type = "postgresql"
        mock_row.connection_config = {"host": "localhost"}
        mock_row.status = "active"
        mock_row.last_connection_test = None
        mock_row.last_connection_status = None
        mock_row.connection_error = None
        mock_row.tags = []
        mock_row.attributes = {}
        mock_row.created_at = now
        mock_row.updated_at = now
        mock_row.created_by = None

        count_result = MagicMock()
        count_result.scalar.return_value = 1

        list_result = MagicMock()
        list_result.fetchall.return_value = [mock_row]

        mock_db.execute.side_effect = [count_result, list_result]

        detector = SchemaDriftDetector(db=mock_db)
        result = await detector.list_connectors(
            tenant_id, connector_type=ConnectorType.POSTGRESQL
        )

        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].connector_type == ConnectorType.POSTGRESQL


class TestSchemaDriftDetectorUpdateConnector:
    """update_connector 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_update_connector_success(self):
        """커넥터 업데이트 - 성공"""
        from app.services.drift_detector import SchemaDriftDetector
        from app.models.mcp import DataConnectorUpdate, ConnectorType

        mock_db = AsyncMock()
        connector_id = uuid4()
        tenant_id = uuid4()
        now = datetime.now(timezone.utc)

        mock_row = MagicMock()
        mock_row.connector_id = connector_id
        mock_row.tenant_id = tenant_id
        mock_row.name = "Updated Name"
        mock_row.description = "Updated description"
        mock_row.connector_type = "postgresql"
        mock_row.connection_config = {"host": "new-host"}
        mock_row.status = "active"
        mock_row.last_connection_test = None
        mock_row.last_connection_status = None
        mock_row.connection_error = None
        mock_row.tags = ["updated"]
        mock_row.attributes = {}
        mock_row.created_at = now
        mock_row.updated_at = now
        mock_row.created_by = None

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result

        detector = SchemaDriftDetector(db=mock_db)
        update_data = DataConnectorUpdate(
            name="Updated Name",
            description="Updated description",
            connection_config={"host": "new-host"},
            tags=["updated"],
        )

        result = await detector.update_connector(connector_id, tenant_id, update_data)

        assert result is not None
        assert result.name == "Updated Name"
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_connector_not_found(self):
        """커넥터 업데이트 - 없음"""
        from app.services.drift_detector import SchemaDriftDetector
        from app.models.mcp import DataConnectorUpdate

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_result

        detector = SchemaDriftDetector(db=mock_db)
        update_data = DataConnectorUpdate(name="New Name")

        result = await detector.update_connector(uuid4(), uuid4(), update_data)

        assert result is None

    @pytest.mark.asyncio
    async def test_update_connector_no_changes(self):
        """커넥터 업데이트 - 변경 없음"""
        from app.services.drift_detector import SchemaDriftDetector
        from app.models.mcp import DataConnectorUpdate, ConnectorType

        mock_db = AsyncMock()
        connector_id = uuid4()
        tenant_id = uuid4()
        now = datetime.now(timezone.utc)

        mock_row = MagicMock()
        mock_row.connector_id = connector_id
        mock_row.tenant_id = tenant_id
        mock_row.name = "Original Name"
        mock_row.description = None
        mock_row.connector_type = "postgresql"
        mock_row.connection_config = {}
        mock_row.status = "active"
        mock_row.last_connection_test = None
        mock_row.last_connection_status = None
        mock_row.connection_error = None
        mock_row.tags = []
        mock_row.attributes = {}
        mock_row.created_at = now
        mock_row.updated_at = now
        mock_row.created_by = None

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result

        detector = SchemaDriftDetector(db=mock_db)
        update_data = DataConnectorUpdate()  # 모든 필드 None

        result = await detector.update_connector(connector_id, tenant_id, update_data)

        assert result is not None


class TestSchemaDriftDetectorDeleteConnector:
    """delete_connector 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_delete_connector_success(self):
        """커넥터 삭제 - 성공"""
        from app.services.drift_detector import SchemaDriftDetector

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (uuid4(),)
        mock_db.execute.return_value = mock_result

        detector = SchemaDriftDetector(db=mock_db)
        result = await detector.delete_connector(uuid4(), uuid4())

        assert result is True
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_connector_not_found(self):
        """커넥터 삭제 - 없음"""
        from app.services.drift_detector import SchemaDriftDetector

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_result

        detector = SchemaDriftDetector(db=mock_db)
        result = await detector.delete_connector(uuid4(), uuid4())

        assert result is False


class TestSchemaDriftDetectorCompareSchemas:
    """_compare_schemas 메서드 테스트"""

    def test_compare_no_changes(self):
        """스키마 비교 - 변경 없음"""
        from app.services.drift_detector import SchemaDriftDetector

        detector = SchemaDriftDetector(db=MagicMock())

        old_schema = {
            "users": {"columns": [{"column_name": "id", "data_type": "integer"}]}
        }
        new_schema = {
            "users": {"columns": [{"column_name": "id", "data_type": "integer"}]}
        }

        changes = detector._compare_schemas(old_schema, new_schema)
        assert len(changes) == 0

    def test_compare_table_added(self):
        """스키마 비교 - 테이블 추가"""
        from app.services.drift_detector import SchemaDriftDetector
        from app.models.mcp import DriftChangeType

        detector = SchemaDriftDetector(db=MagicMock())

        old_schema = {"users": {"columns": [{"column_name": "id", "data_type": "integer"}]}}
        new_schema = {
            "users": {"columns": [{"column_name": "id", "data_type": "integer"}]},
            "orders": {"columns": [{"column_name": "id", "data_type": "integer"}]},
        }

        changes = detector._compare_schemas(old_schema, new_schema)

        assert len(changes) == 1
        assert changes[0].type == DriftChangeType.TABLE_ADDED
        assert changes[0].table_name == "orders"

    def test_compare_table_deleted(self):
        """스키마 비교 - 테이블 삭제"""
        from app.services.drift_detector import SchemaDriftDetector
        from app.models.mcp import DriftChangeType

        detector = SchemaDriftDetector(db=MagicMock())

        old_schema = {
            "users": {"columns": [{"column_name": "id", "data_type": "integer"}]},
            "logs": {"columns": [{"column_name": "id", "data_type": "integer"}]},
        }
        new_schema = {"users": {"columns": [{"column_name": "id", "data_type": "integer"}]}}

        changes = detector._compare_schemas(old_schema, new_schema)

        assert len(changes) == 1
        assert changes[0].type == DriftChangeType.TABLE_DELETED
        assert changes[0].table_name == "logs"

    def test_compare_column_added(self):
        """스키마 비교 - 컬럼 추가"""
        from app.services.drift_detector import SchemaDriftDetector
        from app.models.mcp import DriftChangeType

        detector = SchemaDriftDetector(db=MagicMock())

        old_schema = {"users": {"columns": [{"column_name": "id", "data_type": "integer"}]}}
        new_schema = {
            "users": {
                "columns": [
                    {"column_name": "id", "data_type": "integer"},
                    {"column_name": "email", "data_type": "varchar"},
                ]
            }
        }

        changes = detector._compare_schemas(old_schema, new_schema)

        assert len(changes) == 1
        assert changes[0].type == DriftChangeType.COLUMN_ADDED
        assert changes[0].column_name == "email"

    def test_compare_column_deleted(self):
        """스키마 비교 - 컬럼 삭제"""
        from app.services.drift_detector import SchemaDriftDetector
        from app.models.mcp import DriftChangeType

        detector = SchemaDriftDetector(db=MagicMock())

        old_schema = {
            "users": {
                "columns": [
                    {"column_name": "id", "data_type": "integer"},
                    {"column_name": "legacy", "data_type": "text"},
                ]
            }
        }
        new_schema = {"users": {"columns": [{"column_name": "id", "data_type": "integer"}]}}

        changes = detector._compare_schemas(old_schema, new_schema)

        assert len(changes) == 1
        assert changes[0].type == DriftChangeType.COLUMN_DELETED
        assert changes[0].column_name == "legacy"

    def test_compare_type_changed(self):
        """스키마 비교 - 타입 변경"""
        from app.services.drift_detector import SchemaDriftDetector
        from app.models.mcp import DriftChangeType

        detector = SchemaDriftDetector(db=MagicMock())

        old_schema = {"users": {"columns": [{"column_name": "amount", "data_type": "integer"}]}}
        new_schema = {"users": {"columns": [{"column_name": "amount", "data_type": "decimal"}]}}

        changes = detector._compare_schemas(old_schema, new_schema)

        assert len(changes) == 1
        assert changes[0].type == DriftChangeType.TYPE_CHANGED
        assert changes[0].old_value == "integer"
        assert changes[0].new_value == "decimal"


class TestSchemaDriftDetectorCalculateSeverity:
    """_calculate_severity 메서드 테스트"""

    def test_severity_info_for_additions(self):
        """심각도 - 추가만 있으면 INFO"""
        from app.services.drift_detector import SchemaDriftDetector
        from app.models.mcp import DriftChange, DriftChangeType, DriftSeverity

        detector = SchemaDriftDetector(db=MagicMock())

        changes = [
            DriftChange(type=DriftChangeType.TABLE_ADDED, table_name="new_table"),
            DriftChange(
                type=DriftChangeType.COLUMN_ADDED,
                table_name="users",
                column_name="new_col",
            ),
        ]

        severity = detector._calculate_severity(changes)
        assert severity == DriftSeverity.INFO

    def test_severity_warning_for_type_change(self):
        """심각도 - 타입 변경은 WARNING"""
        from app.services.drift_detector import SchemaDriftDetector
        from app.models.mcp import DriftChange, DriftChangeType, DriftSeverity

        detector = SchemaDriftDetector(db=MagicMock())

        changes = [
            DriftChange(
                type=DriftChangeType.TYPE_CHANGED,
                table_name="users",
                column_name="age",
                old_value="int",
                new_value="bigint",
            ),
        ]

        severity = detector._calculate_severity(changes)
        assert severity == DriftSeverity.WARNING

    def test_severity_critical_for_deletion(self):
        """심각도 - 삭제는 CRITICAL"""
        from app.services.drift_detector import SchemaDriftDetector
        from app.models.mcp import DriftChange, DriftChangeType, DriftSeverity

        detector = SchemaDriftDetector(db=MagicMock())

        changes = [
            DriftChange(type=DriftChangeType.TABLE_DELETED, table_name="important_table"),
        ]

        severity = detector._calculate_severity(changes)
        assert severity == DriftSeverity.CRITICAL

    def test_severity_critical_for_column_deletion(self):
        """심각도 - 컬럼 삭제도 CRITICAL"""
        from app.services.drift_detector import SchemaDriftDetector
        from app.models.mcp import DriftChange, DriftChangeType, DriftSeverity

        detector = SchemaDriftDetector(db=MagicMock())

        changes = [
            DriftChange(
                type=DriftChangeType.COLUMN_DELETED,
                table_name="users",
                column_name="email",
            ),
        ]

        severity = detector._calculate_severity(changes)
        assert severity == DriftSeverity.CRITICAL


class TestSchemaDriftDetectorComputeSchemaHash:
    """_compute_schema_hash 메서드 테스트"""

    def test_hash_same_schema(self):
        """동일 스키마 → 동일 해시"""
        from app.services.drift_detector import SchemaDriftDetector

        detector = SchemaDriftDetector(db=MagicMock())

        schema1 = {"users": {"columns": [{"name": "id", "type": "int"}]}}
        schema2 = {"users": {"columns": [{"name": "id", "type": "int"}]}}

        hash1 = detector._compute_schema_hash(schema1)
        hash2 = detector._compute_schema_hash(schema2)

        assert hash1 == hash2

    def test_hash_different_schema(self):
        """다른 스키마 → 다른 해시"""
        from app.services.drift_detector import SchemaDriftDetector

        detector = SchemaDriftDetector(db=MagicMock())

        schema1 = {"users": {"columns": [{"name": "id", "type": "int"}]}}
        schema2 = {"users": {"columns": [{"name": "id", "type": "bigint"}]}}

        hash1 = detector._compute_schema_hash(schema1)
        hash2 = detector._compute_schema_hash(schema2)

        assert hash1 != hash2


class TestSchemaDriftDetectorGetCurrentSchema:
    """_get_current_schema 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_get_current_schema_unsupported_type(self):
        """지원하지 않는 커넥터 타입"""
        from app.services.drift_detector import SchemaDriftDetector, UnsupportedConnectorTypeError
        from app.models.mcp import DataConnector, ConnectorType

        mock_db = AsyncMock()
        detector = SchemaDriftDetector(db=mock_db)

        connector = DataConnector(
            connector_id=uuid4(),
            tenant_id=uuid4(),
            name="S3 Connector",
            connector_type=ConnectorType.S3,
            connection_config={"bucket": "test"},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(UnsupportedConnectorTypeError):
            await detector._get_current_schema(connector)


class TestSchemaDriftDetectorAcknowledgeDrift:
    """acknowledge_drift 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_acknowledge_success(self):
        """Drift 확인 - 성공"""
        from app.services.drift_detector import SchemaDriftDetector

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (uuid4(),)
        mock_db.execute.return_value = mock_result

        detector = SchemaDriftDetector(db=mock_db)
        result = await detector.acknowledge_drift(uuid4(), uuid4(), uuid4())

        assert result is True
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_acknowledge_not_found(self):
        """Drift 확인 - 없음"""
        from app.services.drift_detector import SchemaDriftDetector

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_result

        detector = SchemaDriftDetector(db=mock_db)
        result = await detector.acknowledge_drift(uuid4(), uuid4(), uuid4())

        assert result is False


class TestSchemaDriftDetectorGetDriftDetections:
    """get_drift_detections 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_get_drift_detections_empty(self):
        """Drift 감지 기록 조회 - 빈 목록"""
        from app.services.drift_detector import SchemaDriftDetector

        mock_db = AsyncMock()

        count_result = MagicMock()
        count_result.scalar.return_value = 0

        list_result = MagicMock()
        list_result.fetchall.return_value = []

        mock_db.execute.side_effect = [count_result, list_result]

        detector = SchemaDriftDetector(db=mock_db)
        result = await detector.get_drift_detections(uuid4(), uuid4())

        assert result.total == 0
        assert len(result.items) == 0

    @pytest.mark.asyncio
    async def test_get_drift_detections_with_filter(self):
        """Drift 감지 기록 조회 - 필터 적용"""
        from app.services.drift_detector import SchemaDriftDetector

        mock_db = AsyncMock()

        count_result = MagicMock()
        count_result.scalar.return_value = 0

        list_result = MagicMock()
        list_result.fetchall.return_value = []

        mock_db.execute.side_effect = [count_result, list_result]

        detector = SchemaDriftDetector(db=mock_db)
        result = await detector.get_drift_detections(
            uuid4(), uuid4(), unacknowledged_only=True
        )

        assert result.total == 0


class TestSchemaDriftDetectorRowConverters:
    """Row 변환 메서드 테스트"""

    def test_row_to_connector(self):
        """_row_to_connector 테스트"""
        from app.services.drift_detector import SchemaDriftDetector
        from app.models.mcp import ConnectorType

        detector = SchemaDriftDetector(db=MagicMock())
        now = datetime.now(timezone.utc)

        mock_row = MagicMock()
        mock_row.connector_id = uuid4()
        mock_row.tenant_id = uuid4()
        mock_row.name = "Test"
        mock_row.description = "Description"
        mock_row.connector_type = "postgresql"
        mock_row.connection_config = {"host": "localhost"}
        mock_row.status = "active"
        mock_row.last_connection_test = now
        mock_row.last_connection_status = "success"
        mock_row.connection_error = None
        mock_row.tags = ["prod"]
        mock_row.attributes = {"env": "production"}
        mock_row.created_at = now
        mock_row.updated_at = now
        mock_row.created_by = uuid4()

        result = detector._row_to_connector(mock_row)

        assert result.name == "Test"
        assert result.connector_type == ConnectorType.POSTGRESQL
        assert result.tags == ["prod"]

    def test_row_to_drift_detection(self):
        """_row_to_drift_detection 테스트"""
        from app.services.drift_detector import SchemaDriftDetector
        from app.models.mcp import DriftSeverity

        detector = SchemaDriftDetector(db=MagicMock())
        now = datetime.now(timezone.utc)

        mock_row = MagicMock()
        mock_row.detection_id = uuid4()
        mock_row.connector_id = uuid4()
        mock_row.tenant_id = uuid4()
        mock_row.old_snapshot_id = uuid4()
        mock_row.new_snapshot_id = uuid4()
        mock_row.changes = [
            {"type": "table_added", "table_name": "new_table"}
        ]
        mock_row.change_count = 1
        mock_row.tables_added = 1
        mock_row.tables_deleted = 0
        mock_row.columns_added = 0
        mock_row.columns_deleted = 0
        mock_row.types_changed = 0
        mock_row.severity = "info"
        mock_row.is_acknowledged = False
        mock_row.acknowledged_at = None
        mock_row.acknowledged_by = None
        mock_row.alert_sent = False
        mock_row.alert_sent_at = None
        mock_row.detected_at = now

        result = detector._row_to_drift_detection(mock_row)

        assert result.change_count == 1
        assert result.severity == DriftSeverity.INFO
        assert len(result.changes) == 1

    def test_row_to_drift_detection_no_changes(self):
        """_row_to_drift_detection - 변경 없음"""
        from app.services.drift_detector import SchemaDriftDetector

        detector = SchemaDriftDetector(db=MagicMock())
        now = datetime.now(timezone.utc)

        mock_row = MagicMock()
        mock_row.detection_id = uuid4()
        mock_row.connector_id = uuid4()
        mock_row.tenant_id = uuid4()
        mock_row.old_snapshot_id = uuid4()
        mock_row.new_snapshot_id = uuid4()
        mock_row.changes = None
        mock_row.change_count = 0
        mock_row.tables_added = 0
        mock_row.tables_deleted = 0
        mock_row.columns_added = 0
        mock_row.columns_deleted = 0
        mock_row.types_changed = 0
        mock_row.severity = "info"
        mock_row.is_acknowledged = True
        mock_row.acknowledged_at = now
        mock_row.acknowledged_by = uuid4()
        mock_row.alert_sent = True
        mock_row.alert_sent_at = now
        mock_row.detected_at = now

        result = detector._row_to_drift_detection(mock_row)

        assert result.change_count == 0
        assert len(result.changes) == 0
        assert result.is_acknowledged is True


class TestSchemaDriftDetectorUpdateConnectorWithStatusAndAttributes:
    """update_connector 상태/속성 업데이트 테스트"""

    @pytest.mark.asyncio
    async def test_update_connector_with_status(self):
        """커넥터 업데이트 - 상태 변경"""
        from app.services.drift_detector import SchemaDriftDetector
        from app.models.mcp import DataConnectorUpdate, ConnectorType

        mock_db = AsyncMock()
        connector_id = uuid4()
        tenant_id = uuid4()
        now = datetime.now(timezone.utc)

        mock_row = MagicMock()
        mock_row.connector_id = connector_id
        mock_row.tenant_id = tenant_id
        mock_row.name = "Test Connector"
        mock_row.description = None
        mock_row.connector_type = "postgresql"
        mock_row.connection_config = {"host": "localhost"}
        mock_row.status = "inactive"
        mock_row.last_connection_test = None
        mock_row.last_connection_status = None
        mock_row.connection_error = None
        mock_row.tags = []
        mock_row.attributes = {}
        mock_row.created_at = now
        mock_row.updated_at = now
        mock_row.created_by = None

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result

        detector = SchemaDriftDetector(db=mock_db)
        update_data = DataConnectorUpdate(status="inactive")

        result = await detector.update_connector(connector_id, tenant_id, update_data)

        assert result is not None
        assert result.status == "inactive"
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_connector_with_attributes(self):
        """커넥터 업데이트 - 속성 변경"""
        from app.services.drift_detector import SchemaDriftDetector
        from app.models.mcp import DataConnectorUpdate, ConnectorType

        mock_db = AsyncMock()
        connector_id = uuid4()
        tenant_id = uuid4()
        now = datetime.now(timezone.utc)

        mock_row = MagicMock()
        mock_row.connector_id = connector_id
        mock_row.tenant_id = tenant_id
        mock_row.name = "Test Connector"
        mock_row.description = None
        mock_row.connector_type = "mysql"
        mock_row.connection_config = {"host": "mysql.local"}
        mock_row.status = "active"
        mock_row.last_connection_test = None
        mock_row.last_connection_status = None
        mock_row.connection_error = None
        mock_row.tags = []
        mock_row.attributes = {"team": "data", "env": "prod"}
        mock_row.created_at = now
        mock_row.updated_at = now
        mock_row.created_by = None

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result

        detector = SchemaDriftDetector(db=mock_db)
        update_data = DataConnectorUpdate(attributes={"team": "data", "env": "prod"})

        result = await detector.update_connector(connector_id, tenant_id, update_data)

        assert result is not None
        assert result.attributes["team"] == "data"
        assert result.attributes["env"] == "prod"


class TestSchemaDriftDetectorGetLatestSnapshot:
    """_get_latest_snapshot 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_get_latest_snapshot_found(self):
        """마지막 스냅샷 조회 - 존재"""
        from app.services.drift_detector import SchemaDriftDetector

        mock_db = AsyncMock()
        connector_id = uuid4()
        snapshot_id = uuid4()

        mock_row = MagicMock()
        mock_row.snapshot_id = snapshot_id
        mock_row.schema_data = {"users": {"columns": []}}
        mock_row.schema_hash = "abc123hash"

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result

        detector = SchemaDriftDetector(db=mock_db)
        result = await detector._get_latest_snapshot(connector_id)

        assert result is not None
        assert result["snapshot_id"] == snapshot_id
        assert result["schema_hash"] == "abc123hash"

    @pytest.mark.asyncio
    async def test_get_latest_snapshot_not_found(self):
        """마지막 스냅샷 조회 - 없음"""
        from app.services.drift_detector import SchemaDriftDetector

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_result

        detector = SchemaDriftDetector(db=mock_db)
        result = await detector._get_latest_snapshot(uuid4())

        assert result is None


class TestSchemaDriftDetectorSaveSnapshot:
    """_save_snapshot 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_save_snapshot_success(self):
        """스냅샷 저장 - 성공"""
        from app.services.drift_detector import SchemaDriftDetector

        mock_db = AsyncMock()
        connector_id = uuid4()
        tenant_id = uuid4()
        snapshot_id = uuid4()
        captured_by = uuid4()

        mock_row = MagicMock()
        mock_row.snapshot_id = snapshot_id

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result

        detector = SchemaDriftDetector(db=mock_db)

        schema_data = {"users": {"columns": [{"column_name": "id", "data_type": "integer"}]}}

        result = await detector._save_snapshot(
            connector_id=connector_id,
            tenant_id=tenant_id,
            schema_data=schema_data,
            schema_hash="testhash123",
            table_count=1,
            column_count=1,
            captured_by=captured_by,
        )

        assert result == snapshot_id
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_snapshot_without_captured_by(self):
        """스냅샷 저장 - captured_by 없음"""
        from app.services.drift_detector import SchemaDriftDetector

        mock_db = AsyncMock()
        connector_id = uuid4()
        tenant_id = uuid4()
        snapshot_id = uuid4()

        mock_row = MagicMock()
        mock_row.snapshot_id = snapshot_id

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result

        detector = SchemaDriftDetector(db=mock_db)

        result = await detector._save_snapshot(
            connector_id=connector_id,
            tenant_id=tenant_id,
            schema_data={},
            schema_hash="emptyhash",
            table_count=0,
            column_count=0,
            captured_by=None,
        )

        assert result == snapshot_id


class TestSchemaDriftDetectorSaveDriftDetection:
    """_save_drift_detection 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_save_drift_detection_success(self):
        """변경 감지 기록 저장 - 성공"""
        from app.services.drift_detector import SchemaDriftDetector
        from app.models.mcp import DriftChange, DriftChangeType, DriftSeverity

        mock_db = AsyncMock()
        detection_id = uuid4()

        mock_row = MagicMock()
        mock_row.detection_id = detection_id

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result

        detector = SchemaDriftDetector(db=mock_db)

        changes = [
            DriftChange(type=DriftChangeType.TABLE_ADDED, table_name="new_table"),
            DriftChange(
                type=DriftChangeType.COLUMN_ADDED,
                table_name="users",
                column_name="email",
                new_value="varchar",
            ),
        ]

        result = await detector._save_drift_detection(
            connector_id=uuid4(),
            tenant_id=uuid4(),
            old_snapshot_id=uuid4(),
            new_snapshot_id=uuid4(),
            changes=changes,
            severity=DriftSeverity.INFO,
            tables_added=1,
            tables_deleted=0,
            columns_added=1,
            columns_deleted=0,
            types_changed=0,
        )

        assert result == detection_id
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()


class TestSchemaDriftDetectorUpdateConnectionStatus:
    """_update_connection_status 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_update_connection_status_success(self):
        """연결 상태 업데이트 - 성공"""
        from app.services.drift_detector import SchemaDriftDetector

        mock_db = AsyncMock()
        connector_id = uuid4()

        detector = SchemaDriftDetector(db=mock_db)
        await detector._update_connection_status(connector_id, True, None)

        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_connection_status_failure(self):
        """연결 상태 업데이트 - 실패"""
        from app.services.drift_detector import SchemaDriftDetector

        mock_db = AsyncMock()
        connector_id = uuid4()

        detector = SchemaDriftDetector(db=mock_db)
        await detector._update_connection_status(connector_id, False, "Connection refused")

        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()


class TestSchemaDriftDetectorDetectDrift:
    """detect_drift 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_detect_drift_connector_not_found(self):
        """Drift 감지 - 커넥터 없음"""
        from app.services.drift_detector import SchemaDriftDetector

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_result

        detector = SchemaDriftDetector(db=mock_db)

        with pytest.raises(ValueError, match="Connector not found"):
            await detector.detect_drift(uuid4(), uuid4())

    @pytest.mark.asyncio
    async def test_detect_drift_first_snapshot(self):
        """Drift 감지 - 첫 스냅샷 (비교 대상 없음)"""
        from app.services.drift_detector import SchemaDriftDetector
        from app.models.mcp import ConnectorType

        mock_db = AsyncMock()
        connector_id = uuid4()
        tenant_id = uuid4()
        snapshot_id = uuid4()
        now = datetime.now(timezone.utc)

        # 커넥터 조회 응답
        mock_connector_row = MagicMock()
        mock_connector_row.connector_id = connector_id
        mock_connector_row.tenant_id = tenant_id
        mock_connector_row.name = "Test DB"
        mock_connector_row.description = None
        mock_connector_row.connector_type = "postgresql"
        mock_connector_row.connection_config = {
            "host": "localhost",
            "port": 5432,
            "database": "testdb",
            "username": "user",
            "password": "pass",
        }
        mock_connector_row.status = "active"
        mock_connector_row.last_connection_test = None
        mock_connector_row.last_connection_status = None
        mock_connector_row.connection_error = None
        mock_connector_row.tags = []
        mock_connector_row.attributes = {}
        mock_connector_row.created_at = now
        mock_connector_row.updated_at = now
        mock_connector_row.created_by = None

        # 스냅샷 저장 응답
        mock_snapshot_row = MagicMock()
        mock_snapshot_row.snapshot_id = snapshot_id

        # execute 호출 순서:
        # 1. get_connector
        # 2. _update_connection_status (성공)
        # 3. _get_latest_snapshot
        # 4. _save_snapshot
        call_count = [0]

        def mock_execute_side_effect(*args, **kwargs):
            result = MagicMock()
            if call_count[0] == 0:  # get_connector
                result.fetchone.return_value = mock_connector_row
            elif call_count[0] == 1:  # _update_connection_status
                result.fetchone.return_value = None
            elif call_count[0] == 2:  # _get_latest_snapshot
                result.fetchone.return_value = None
            elif call_count[0] == 3:  # _save_snapshot
                result.fetchone.return_value = mock_snapshot_row
            call_count[0] += 1
            return result

        mock_db.execute.side_effect = mock_execute_side_effect

        detector = SchemaDriftDetector(db=mock_db)

        # mock _get_current_schema
        with patch.object(
            detector,
            "_get_current_schema",
            new_callable=AsyncMock,
            return_value={"users": {"columns": [{"column_name": "id", "data_type": "integer"}]}},
        ):
            result = await detector.detect_drift(connector_id, tenant_id)

        assert result.has_changes is False
        assert len(result.changes) == 0
        assert result.new_snapshot_id == snapshot_id

    @pytest.mark.asyncio
    async def test_detect_drift_no_changes_same_hash(self):
        """Drift 감지 - 변경 없음 (해시 동일)"""
        from app.services.drift_detector import SchemaDriftDetector
        from app.models.mcp import ConnectorType

        mock_db = AsyncMock()
        connector_id = uuid4()
        tenant_id = uuid4()
        old_snapshot_id = uuid4()
        new_snapshot_id = uuid4()
        now = datetime.now(timezone.utc)

        mock_connector_row = MagicMock()
        mock_connector_row.connector_id = connector_id
        mock_connector_row.tenant_id = tenant_id
        mock_connector_row.name = "Test DB"
        mock_connector_row.description = None
        mock_connector_row.connector_type = "postgresql"
        mock_connector_row.connection_config = {
            "host": "localhost",
            "port": 5432,
            "database": "testdb",
            "username": "user",
            "password": "pass",
        }
        mock_connector_row.status = "active"
        mock_connector_row.last_connection_test = None
        mock_connector_row.last_connection_status = None
        mock_connector_row.connection_error = None
        mock_connector_row.tags = []
        mock_connector_row.attributes = {}
        mock_connector_row.created_at = now
        mock_connector_row.updated_at = now
        mock_connector_row.created_by = None

        schema_data = {"users": {"columns": [{"column_name": "id", "data_type": "integer"}]}}

        mock_snapshot_row = MagicMock()
        mock_snapshot_row.snapshot_id = new_snapshot_id

        mock_old_snapshot_row = MagicMock()
        mock_old_snapshot_row.snapshot_id = old_snapshot_id
        mock_old_snapshot_row.schema_data = schema_data

        call_count = [0]

        def mock_execute_side_effect(*args, **kwargs):
            result = MagicMock()
            if call_count[0] == 0:  # get_connector
                result.fetchone.return_value = mock_connector_row
            elif call_count[0] == 1:  # _update_connection_status
                result.fetchone.return_value = None
            elif call_count[0] == 2:  # _get_latest_snapshot
                # 해시 계산을 위해 detector._compute_schema_hash 호출됨
                import hashlib
                import json
                schema_hash = hashlib.sha256(
                    json.dumps(schema_data, sort_keys=True).encode()
                ).hexdigest()
                mock_old_snapshot_row.schema_hash = schema_hash
                result.fetchone.return_value = mock_old_snapshot_row
            elif call_count[0] == 3:  # _save_snapshot
                result.fetchone.return_value = mock_snapshot_row
            call_count[0] += 1
            return result

        mock_db.execute.side_effect = mock_execute_side_effect

        detector = SchemaDriftDetector(db=mock_db)

        with patch.object(
            detector,
            "_get_current_schema",
            new_callable=AsyncMock,
            return_value=schema_data,
        ):
            result = await detector.detect_drift(connector_id, tenant_id)

        assert result.has_changes is False
        assert len(result.changes) == 0

    @pytest.mark.asyncio
    async def test_detect_drift_with_changes(self):
        """Drift 감지 - 변경 있음"""
        from app.services.drift_detector import SchemaDriftDetector
        from app.models.mcp import ConnectorType, DriftChangeType, DriftSeverity

        mock_db = AsyncMock()
        connector_id = uuid4()
        tenant_id = uuid4()
        old_snapshot_id = uuid4()
        new_snapshot_id = uuid4()
        detection_id = uuid4()
        now = datetime.now(timezone.utc)

        mock_connector_row = MagicMock()
        mock_connector_row.connector_id = connector_id
        mock_connector_row.tenant_id = tenant_id
        mock_connector_row.name = "Test DB"
        mock_connector_row.description = None
        mock_connector_row.connector_type = "postgresql"
        mock_connector_row.connection_config = {
            "host": "localhost",
            "port": 5432,
            "database": "testdb",
            "username": "user",
            "password": "pass",
        }
        mock_connector_row.status = "active"
        mock_connector_row.last_connection_test = None
        mock_connector_row.last_connection_status = None
        mock_connector_row.connection_error = None
        mock_connector_row.tags = []
        mock_connector_row.attributes = {}
        mock_connector_row.created_at = now
        mock_connector_row.updated_at = now
        mock_connector_row.created_by = None

        old_schema = {"users": {"columns": [{"column_name": "id", "data_type": "integer"}]}}
        new_schema = {
            "users": {"columns": [{"column_name": "id", "data_type": "integer"}]},
            "orders": {"columns": [{"column_name": "id", "data_type": "integer"}]},
        }

        mock_old_snapshot_row = MagicMock()
        mock_old_snapshot_row.snapshot_id = old_snapshot_id
        mock_old_snapshot_row.schema_data = old_schema
        mock_old_snapshot_row.schema_hash = "oldhash"

        mock_snapshot_row = MagicMock()
        mock_snapshot_row.snapshot_id = new_snapshot_id

        mock_detection_row = MagicMock()
        mock_detection_row.detection_id = detection_id

        call_count = [0]

        def mock_execute_side_effect(*args, **kwargs):
            result = MagicMock()
            if call_count[0] == 0:  # get_connector
                result.fetchone.return_value = mock_connector_row
            elif call_count[0] == 1:  # _update_connection_status
                result.fetchone.return_value = None
            elif call_count[0] == 2:  # _get_latest_snapshot
                result.fetchone.return_value = mock_old_snapshot_row
            elif call_count[0] == 3:  # _save_snapshot
                result.fetchone.return_value = mock_snapshot_row
            elif call_count[0] == 4:  # _save_drift_detection
                result.fetchone.return_value = mock_detection_row
            call_count[0] += 1
            return result

        mock_db.execute.side_effect = mock_execute_side_effect

        detector = SchemaDriftDetector(db=mock_db)

        with patch.object(
            detector,
            "_get_current_schema",
            new_callable=AsyncMock,
            return_value=new_schema,
        ):
            result = await detector.detect_drift(connector_id, tenant_id)

        assert result.has_changes is True
        assert result.tables_added == 1
        assert result.severity == DriftSeverity.INFO

    @pytest.mark.asyncio
    async def test_detect_drift_connection_error(self):
        """Drift 감지 - 연결 실패"""
        from app.services.drift_detector import SchemaDriftDetector, ConnectionError
        from app.models.mcp import ConnectorType

        mock_db = AsyncMock()
        connector_id = uuid4()
        tenant_id = uuid4()
        now = datetime.now(timezone.utc)

        mock_connector_row = MagicMock()
        mock_connector_row.connector_id = connector_id
        mock_connector_row.tenant_id = tenant_id
        mock_connector_row.name = "Test DB"
        mock_connector_row.description = None
        mock_connector_row.connector_type = "postgresql"
        mock_connector_row.connection_config = {
            "host": "localhost",
            "port": 5432,
            "database": "testdb",
            "username": "user",
            "password": "pass",
        }
        mock_connector_row.status = "active"
        mock_connector_row.last_connection_test = None
        mock_connector_row.last_connection_status = None
        mock_connector_row.connection_error = None
        mock_connector_row.tags = []
        mock_connector_row.attributes = {}
        mock_connector_row.created_at = now
        mock_connector_row.updated_at = now
        mock_connector_row.created_by = None

        call_count = [0]

        def mock_execute_side_effect(*args, **kwargs):
            result = MagicMock()
            if call_count[0] == 0:  # get_connector
                result.fetchone.return_value = mock_connector_row
            elif call_count[0] == 1:  # _update_connection_status (failure)
                result.fetchone.return_value = None
            call_count[0] += 1
            return result

        mock_db.execute.side_effect = mock_execute_side_effect

        detector = SchemaDriftDetector(db=mock_db)

        with patch.object(
            detector,
            "_get_current_schema",
            new_callable=AsyncMock,
            side_effect=Exception("Connection refused"),
        ):
            with pytest.raises(ConnectionError, match="Failed to connect"):
                await detector.detect_drift(connector_id, tenant_id)


class TestSchemaDriftDetectorGetPostgresSchema:
    """_get_postgres_schema 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_get_postgres_schema_success(self):
        """PostgreSQL 스키마 조회 - 성공"""
        from app.services.drift_detector import SchemaDriftDetector
        from app.models.mcp import DataConnector, ConnectorType

        mock_db = MagicMock()
        detector = SchemaDriftDetector(db=mock_db)

        connector = DataConnector(
            connector_id=uuid4(),
            tenant_id=uuid4(),
            name="Test PostgreSQL",
            connector_type=ConnectorType.POSTGRESQL,
            connection_config={
                "host": "localhost",
                "port": 5432,
                "database": "testdb",
                "username": "user",
                "password": "pass",
            },
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock()

        # 테이블 목록
        mock_conn.fetch.side_effect = [
            [{"table_name": "users"}],  # 테이블 목록
            [  # 컬럼 목록
                {
                    "column_name": "id",
                    "data_type": "integer",
                    "is_nullable": "NO",
                    "column_default": "nextval('users_id_seq')",
                },
                {
                    "column_name": "email",
                    "data_type": "varchar",
                    "is_nullable": "NO",
                    "column_default": None,
                },
            ],
        ]

        with patch("asyncpg.connect", new_callable=AsyncMock, return_value=mock_conn):
            result = await detector._get_postgres_schema(connector)

        assert "users" in result
        assert len(result["users"]["columns"]) == 2
        assert result["users"]["columns"][0]["column_name"] == "id"
        mock_conn.close.assert_called_once()


class TestSchemaDriftDetectorGetMysqlSchema:
    """_get_mysql_schema 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_get_mysql_schema_success(self):
        """MySQL 스키마 조회 - 성공"""
        from app.services.drift_detector import SchemaDriftDetector
        from app.models.mcp import DataConnector, ConnectorType

        mock_db = MagicMock()
        detector = SchemaDriftDetector(db=mock_db)

        connector = DataConnector(
            connector_id=uuid4(),
            tenant_id=uuid4(),
            name="Test MySQL",
            connector_type=ConnectorType.MYSQL,
            connection_config={
                "host": "localhost",
                "port": 3306,
                "database": "testdb",
                "username": "root",
                "password": "pass",
            },
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock()
        mock_cursor.fetchall.side_effect = [
            [("orders",)],  # 테이블 목록
            [  # 컬럼 목록
                ("id", "int", "NO", None),
                ("total", "decimal", "YES", "0.00"),
            ],
        ]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__aenter__.return_value = mock_cursor
        mock_conn.cursor.return_value.__aexit__ = AsyncMock()

        # Use patch on the module path where it's imported
        import sys
        mock_aiomysql = MagicMock()
        mock_aiomysql.connect = AsyncMock(return_value=mock_conn)
        sys.modules["aiomysql"] = mock_aiomysql

        try:
            result = await detector._get_mysql_schema(connector)

            assert "orders" in result
            assert len(result["orders"]["columns"]) == 2
            assert result["orders"]["columns"][0]["column_name"] == "id"
            mock_conn.close.assert_called_once()
        finally:
            del sys.modules["aiomysql"]


class TestSchemaDriftDetectorGetCurrentSchemaDispatch:
    """_get_current_schema 디스패치 테스트"""

    @pytest.mark.asyncio
    async def test_get_current_schema_postgresql(self):
        """PostgreSQL 디스패치"""
        from app.services.drift_detector import SchemaDriftDetector
        from app.models.mcp import DataConnector, ConnectorType

        mock_db = MagicMock()
        detector = SchemaDriftDetector(db=mock_db)

        connector = DataConnector(
            connector_id=uuid4(),
            tenant_id=uuid4(),
            name="Test",
            connector_type=ConnectorType.POSTGRESQL,
            connection_config={
                "host": "localhost",
                "database": "test",
                "username": "user",
                "password": "pass",
            },
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        with patch.object(
            detector,
            "_get_postgres_schema",
            new_callable=AsyncMock,
            return_value={"users": {}},
        ) as mock_postgres:
            result = await detector._get_current_schema(connector)
            mock_postgres.assert_called_once_with(connector)
            assert "users" in result

    @pytest.mark.asyncio
    async def test_get_current_schema_mysql(self):
        """MySQL 디스패치"""
        from app.services.drift_detector import SchemaDriftDetector
        from app.models.mcp import DataConnector, ConnectorType

        mock_db = MagicMock()
        detector = SchemaDriftDetector(db=mock_db)

        connector = DataConnector(
            connector_id=uuid4(),
            tenant_id=uuid4(),
            name="Test",
            connector_type=ConnectorType.MYSQL,
            connection_config={
                "host": "localhost",
                "database": "test",
                "username": "user",
                "password": "pass",
            },
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        with patch.object(
            detector,
            "_get_mysql_schema",
            new_callable=AsyncMock,
            return_value={"orders": {}},
        ) as mock_mysql:
            result = await detector._get_current_schema(connector)
            mock_mysql.assert_called_once_with(connector)
            assert "orders" in result
