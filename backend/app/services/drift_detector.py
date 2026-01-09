"""
Schema Drift Detector

스펙 참조: B-2-3_MCP_DataHub_Chat_Design.md

외부 데이터 소스의 스키마 변경을 감지하고 알림을 보냄
- PostgreSQL, MySQL information_schema 쿼리
- 스키마 스냅샷 저장 및 비교
- 변경 감지 및 심각도 분류
"""

import hashlib
import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp import (
    ConnectorType,
    DataConnector,
    DataConnectorCreate,
    DataConnectorList,
    DataConnectorUpdate,
    DriftChange,
    DriftChangeType,
    DriftReport,
    DriftSeverity,
    SchemaDriftDetection,
    SchemaDriftDetectionList,
)

logger = logging.getLogger(__name__)


class UnsupportedConnectorTypeError(Exception):
    """지원하지 않는 커넥터 타입"""

    pass


class ConnectionError(Exception):
    """커넥터 연결 실패"""

    pass


class SchemaDriftDetector:
    """
    스키마 변경 감지 서비스

    외부 DB의 스키마를 주기적으로 수집하고 변경을 감지
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================
    # Data Connector CRUD
    # =========================================
    async def create_connector(
        self,
        tenant_id: UUID,
        data: DataConnectorCreate,
        created_by: UUID | None = None,
    ) -> DataConnector:
        """데이터 커넥터 생성"""
        query = text("""
            INSERT INTO core.data_connectors (
                tenant_id, name, description, connector_type,
                connection_config, tags, attributes, created_by
            )
            VALUES (
                :tenant_id, :name, :description, :connector_type,
                :connection_config, :tags, :attributes, :created_by
            )
            RETURNING connector_id, tenant_id, name, description, connector_type,
                      connection_config, status, last_connection_test, last_connection_status,
                      connection_error, tags, attributes, created_at, updated_at, created_by
        """)

        result = await self.db.execute(
            query,
            {
                "tenant_id": str(tenant_id),
                "name": data.name,
                "description": data.description,
                "connector_type": data.connector_type.value,
                "connection_config": json.dumps(data.connection_config),
                "tags": data.tags,
                "attributes": json.dumps(data.attributes),
                "created_by": str(created_by) if created_by else None,
            },
        )
        await self.db.commit()

        row = result.fetchone()
        return self._row_to_connector(row)

    async def get_connector(
        self,
        connector_id: UUID,
        tenant_id: UUID,
    ) -> DataConnector | None:
        """데이터 커넥터 조회"""
        query = text("""
            SELECT connector_id, tenant_id, name, description, connector_type,
                   connection_config, status, last_connection_test, last_connection_status,
                   connection_error, tags, attributes, created_at, updated_at, created_by
            FROM core.data_connectors
            WHERE connector_id = :connector_id AND tenant_id = :tenant_id
        """)

        result = await self.db.execute(
            query,
            {"connector_id": str(connector_id), "tenant_id": str(tenant_id)},
        )
        row = result.fetchone()

        if not row:
            return None

        return self._row_to_connector(row)

    async def list_connectors(
        self,
        tenant_id: UUID,
        page: int = 1,
        size: int = 20,
        connector_type: ConnectorType | None = None,
    ) -> DataConnectorList:
        """데이터 커넥터 목록 조회"""
        conditions = ["tenant_id = :tenant_id"]
        params: dict[str, Any] = {"tenant_id": str(tenant_id)}

        if connector_type:
            conditions.append("connector_type = :connector_type")
            params["connector_type"] = connector_type.value

        where_clause = " AND ".join(conditions)

        # 카운트
        count_query = text(f"""
            SELECT COUNT(*)
            FROM core.data_connectors
            WHERE {where_clause}
        """)
        count_result = await self.db.execute(count_query, params)
        total = count_result.scalar() or 0

        # 목록
        offset = (page - 1) * size
        params["limit"] = size
        params["offset"] = offset

        list_query = text(f"""
            SELECT connector_id, tenant_id, name, description, connector_type,
                   connection_config, status, last_connection_test, last_connection_status,
                   connection_error, tags, attributes, created_at, updated_at, created_by
            FROM core.data_connectors
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """)
        list_result = await self.db.execute(list_query, params)
        rows = list_result.fetchall()

        items = [self._row_to_connector(row) for row in rows]

        return DataConnectorList(items=items, total=total, page=page, size=size)

    async def update_connector(
        self,
        connector_id: UUID,
        tenant_id: UUID,
        data: DataConnectorUpdate,
    ) -> DataConnector | None:
        """데이터 커넥터 수정"""
        updates = []
        params: dict[str, Any] = {
            "connector_id": str(connector_id),
            "tenant_id": str(tenant_id),
        }

        if data.name is not None:
            updates.append("name = :name")
            params["name"] = data.name

        if data.description is not None:
            updates.append("description = :description")
            params["description"] = data.description

        if data.connection_config is not None:
            updates.append("connection_config = :connection_config")
            params["connection_config"] = json.dumps(data.connection_config)

        if data.status is not None:
            updates.append("status = :status")
            params["status"] = data.status

        if data.tags is not None:
            updates.append("tags = :tags")
            params["tags"] = data.tags

        if data.attributes is not None:
            updates.append("attributes = :attributes")
            params["attributes"] = json.dumps(data.attributes)

        if not updates:
            return await self.get_connector(connector_id, tenant_id)

        update_clause = ", ".join(updates)

        query = text(f"""
            UPDATE core.data_connectors
            SET {update_clause}
            WHERE connector_id = :connector_id AND tenant_id = :tenant_id
            RETURNING connector_id, tenant_id, name, description, connector_type,
                      connection_config, status, last_connection_test, last_connection_status,
                      connection_error, tags, attributes, created_at, updated_at, created_by
        """)

        result = await self.db.execute(query, params)
        await self.db.commit()

        row = result.fetchone()
        if not row:
            return None

        return self._row_to_connector(row)

    async def delete_connector(self, connector_id: UUID, tenant_id: UUID) -> bool:
        """데이터 커넥터 삭제"""
        query = text("""
            DELETE FROM core.data_connectors
            WHERE connector_id = :connector_id AND tenant_id = :tenant_id
            RETURNING connector_id
        """)

        result = await self.db.execute(
            query,
            {"connector_id": str(connector_id), "tenant_id": str(tenant_id)},
        )
        await self.db.commit()

        return result.fetchone() is not None

    # =========================================
    # Schema Drift Detection
    # =========================================
    async def detect_drift(
        self,
        connector_id: UUID,
        tenant_id: UUID,
        captured_by: UUID | None = None,
    ) -> DriftReport:
        """
        스키마 변경 감지

        1. 현재 스키마 조회
        2. 마지막 스냅샷과 비교
        3. 변경 감지 결과 저장
        """
        # 커넥터 조회
        connector = await self.get_connector(connector_id, tenant_id)
        if not connector:
            raise ValueError(f"Connector not found: {connector_id}")

        # 현재 스키마 조회
        try:
            current_schema = await self._get_current_schema(connector)
        except Exception as e:
            logger.error(f"Failed to get current schema: {e}")
            await self._update_connection_status(connector_id, False, str(e))
            raise ConnectionError(f"Failed to connect: {e}")

        # 연결 상태 업데이트
        await self._update_connection_status(connector_id, True, None)

        # 마지막 스냅샷 조회
        last_snapshot = await self._get_latest_snapshot(connector_id)

        # 스키마 해시 계산
        schema_hash = self._compute_schema_hash(current_schema)
        table_count = len(current_schema)
        column_count = sum(len(t["columns"]) for t in current_schema.values())

        # 새 스냅샷 저장
        new_snapshot_id = await self._save_snapshot(
            connector_id=connector_id,
            tenant_id=tenant_id,
            schema_data=current_schema,
            schema_hash=schema_hash,
            table_count=table_count,
            column_count=column_count,
            captured_by=captured_by,
        )

        # 첫 스냅샷이면 변경 없음
        if not last_snapshot:
            return DriftReport(
                connector_id=connector_id,
                has_changes=False,
                changes=[],
                new_snapshot_id=new_snapshot_id,
            )

        # 해시 비교 (빠른 체크)
        if last_snapshot["schema_hash"] == schema_hash:
            return DriftReport(
                connector_id=connector_id,
                has_changes=False,
                changes=[],
                old_snapshot_id=last_snapshot["snapshot_id"],
                new_snapshot_id=new_snapshot_id,
            )

        # 상세 비교
        changes = self._compare_schemas(last_snapshot["schema_data"], current_schema)

        if not changes:
            return DriftReport(
                connector_id=connector_id,
                has_changes=False,
                changes=[],
                old_snapshot_id=last_snapshot["snapshot_id"],
                new_snapshot_id=new_snapshot_id,
            )

        # 심각도 계산
        severity = self._calculate_severity(changes)

        # 카운트 계산
        tables_added = sum(1 for c in changes if c.type == DriftChangeType.TABLE_ADDED)
        tables_deleted = sum(1 for c in changes if c.type == DriftChangeType.TABLE_DELETED)
        columns_added = sum(1 for c in changes if c.type == DriftChangeType.COLUMN_ADDED)
        columns_deleted = sum(1 for c in changes if c.type == DriftChangeType.COLUMN_DELETED)
        types_changed = sum(1 for c in changes if c.type == DriftChangeType.TYPE_CHANGED)

        # 변경 감지 기록 저장
        await self._save_drift_detection(
            connector_id=connector_id,
            tenant_id=tenant_id,
            old_snapshot_id=last_snapshot["snapshot_id"],
            new_snapshot_id=new_snapshot_id,
            changes=changes,
            severity=severity,
            tables_added=tables_added,
            tables_deleted=tables_deleted,
            columns_added=columns_added,
            columns_deleted=columns_deleted,
            types_changed=types_changed,
        )

        logger.warning(
            f"Schema drift detected for connector {connector_id}: "
            f"{len(changes)} changes, severity={severity}"
        )

        return DriftReport(
            connector_id=connector_id,
            has_changes=True,
            changes=changes,
            tables_added=tables_added,
            tables_deleted=tables_deleted,
            columns_added=columns_added,
            columns_deleted=columns_deleted,
            types_changed=types_changed,
            severity=severity,
            old_snapshot_id=last_snapshot["snapshot_id"],
            new_snapshot_id=new_snapshot_id,
        )

    async def get_drift_detections(
        self,
        connector_id: UUID,
        tenant_id: UUID,
        page: int = 1,
        size: int = 20,
        unacknowledged_only: bool = False,
    ) -> SchemaDriftDetectionList:
        """스키마 변경 감지 기록 조회"""
        conditions = ["connector_id = :connector_id", "tenant_id = :tenant_id"]
        params: dict[str, Any] = {
            "connector_id": str(connector_id),
            "tenant_id": str(tenant_id),
        }

        if unacknowledged_only:
            conditions.append("NOT is_acknowledged")

        where_clause = " AND ".join(conditions)

        # 카운트
        count_query = text(f"""
            SELECT COUNT(*)
            FROM core.schema_drift_detections
            WHERE {where_clause}
        """)
        count_result = await self.db.execute(count_query, params)
        total = count_result.scalar() or 0

        # 목록
        offset = (page - 1) * size
        params["limit"] = size
        params["offset"] = offset

        list_query = text(f"""
            SELECT detection_id, connector_id, tenant_id,
                   old_snapshot_id, new_snapshot_id,
                   changes, change_count,
                   tables_added, tables_deleted, columns_added, columns_deleted, types_changed,
                   severity, is_acknowledged, acknowledged_at, acknowledged_by,
                   alert_sent, alert_sent_at, detected_at
            FROM core.schema_drift_detections
            WHERE {where_clause}
            ORDER BY detected_at DESC
            LIMIT :limit OFFSET :offset
        """)
        list_result = await self.db.execute(list_query, params)
        rows = list_result.fetchall()

        items = [self._row_to_drift_detection(row) for row in rows]

        return SchemaDriftDetectionList(items=items, total=total, page=page, size=size)

    async def acknowledge_drift(
        self,
        detection_id: UUID,
        tenant_id: UUID,
        acknowledged_by: UUID,
    ) -> bool:
        """스키마 변경 확인 처리"""
        query = text("""
            UPDATE core.schema_drift_detections
            SET is_acknowledged = true,
                acknowledged_at = now(),
                acknowledged_by = :acknowledged_by
            WHERE detection_id = :detection_id AND tenant_id = :tenant_id
            RETURNING detection_id
        """)

        result = await self.db.execute(
            query,
            {
                "detection_id": str(detection_id),
                "tenant_id": str(tenant_id),
                "acknowledged_by": str(acknowledged_by),
            },
        )
        await self.db.commit()

        return result.fetchone() is not None

    # =========================================
    # Schema Retrieval
    # =========================================
    async def _get_current_schema(self, connector: DataConnector) -> dict[str, Any]:
        """현재 스키마 조회 (DB 타입별)"""
        if connector.connector_type == ConnectorType.POSTGRESQL:
            return await self._get_postgres_schema(connector)
        elif connector.connector_type == ConnectorType.MYSQL:
            return await self._get_mysql_schema(connector)
        else:
            raise UnsupportedConnectorTypeError(
                f"Unsupported connector type: {connector.connector_type}"
            )

    async def _get_postgres_schema(self, connector: DataConnector) -> dict[str, Any]:
        """PostgreSQL 스키마 조회"""
        import asyncpg

        config = connector.connection_config

        # 연결
        conn = await asyncpg.connect(
            host=config["host"],
            port=config.get("port", 5432),
            database=config["database"],
            user=config["username"],
            password=config["password"],
            ssl=config.get("ssl_mode", "prefer"),
        )

        try:
            # 테이블 목록
            tables_query = """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """
            tables = await conn.fetch(tables_query)

            schema = {}
            for table_row in tables:
                table_name = table_row["table_name"]

                # 컬럼 정보
                columns_query = """
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = $1
                    ORDER BY ordinal_position
                """
                columns = await conn.fetch(columns_query, table_name)

                schema[table_name] = {
                    "columns": [
                        {
                            "column_name": col["column_name"],
                            "data_type": col["data_type"],
                            "is_nullable": col["is_nullable"],
                            "column_default": col["column_default"],
                        }
                        for col in columns
                    ]
                }

            return schema

        finally:
            await conn.close()

    async def _get_mysql_schema(self, connector: DataConnector) -> dict[str, Any]:
        """MySQL 스키마 조회"""
        import aiomysql

        config = connector.connection_config

        # 연결
        conn = await aiomysql.connect(
            host=config["host"],
            port=config.get("port", 3306),
            db=config["database"],
            user=config["username"],
            password=config["password"],
        )

        try:
            async with conn.cursor() as cursor:
                # 테이블 목록
                await cursor.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """)
                tables = await cursor.fetchall()

                schema = {}
                for (table_name,) in tables:
                    # 컬럼 정보
                    await cursor.execute(
                        """
                        SELECT column_name, data_type, is_nullable, column_default
                        FROM information_schema.columns
                        WHERE table_schema = DATABASE() AND table_name = %s
                        ORDER BY ordinal_position
                    """,
                        (table_name,),
                    )
                    columns = await cursor.fetchall()

                    schema[table_name] = {
                        "columns": [
                            {
                                "column_name": col[0],
                                "data_type": col[1],
                                "is_nullable": col[2],
                                "column_default": col[3],
                            }
                            for col in columns
                        ]
                    }

                return schema

        finally:
            conn.close()

    # =========================================
    # Schema Comparison
    # =========================================
    def _compare_schemas(
        self,
        old_schema: dict[str, Any],
        new_schema: dict[str, Any],
    ) -> list[DriftChange]:
        """스키마 비교"""
        changes = []

        # 삭제된 테이블
        for table_name in old_schema:
            if table_name not in new_schema:
                changes.append(
                    DriftChange(
                        type=DriftChangeType.TABLE_DELETED,
                        table_name=table_name,
                    )
                )

        # 추가된 테이블
        for table_name in new_schema:
            if table_name not in old_schema:
                changes.append(
                    DriftChange(
                        type=DriftChangeType.TABLE_ADDED,
                        table_name=table_name,
                        details={"columns": new_schema[table_name]["columns"]},
                    )
                )

        # 공통 테이블의 컬럼 비교
        for table_name in old_schema:
            if table_name not in new_schema:
                continue

            old_columns = {c["column_name"]: c for c in old_schema[table_name]["columns"]}
            new_columns = {c["column_name"]: c for c in new_schema[table_name]["columns"]}

            # 삭제된 컬럼
            for col_name in old_columns:
                if col_name not in new_columns:
                    changes.append(
                        DriftChange(
                            type=DriftChangeType.COLUMN_DELETED,
                            table_name=table_name,
                            column_name=col_name,
                            old_value=old_columns[col_name]["data_type"],
                        )
                    )

            # 추가된 컬럼
            for col_name in new_columns:
                if col_name not in old_columns:
                    changes.append(
                        DriftChange(
                            type=DriftChangeType.COLUMN_ADDED,
                            table_name=table_name,
                            column_name=col_name,
                            new_value=new_columns[col_name]["data_type"],
                            details=new_columns[col_name],
                        )
                    )

            # 타입 변경
            for col_name in old_columns:
                if col_name not in new_columns:
                    continue

                old_type = old_columns[col_name]["data_type"]
                new_type = new_columns[col_name]["data_type"]

                if old_type != new_type:
                    changes.append(
                        DriftChange(
                            type=DriftChangeType.TYPE_CHANGED,
                            table_name=table_name,
                            column_name=col_name,
                            old_value=old_type,
                            new_value=new_type,
                        )
                    )

        return changes

    def _calculate_severity(self, changes: list[DriftChange]) -> DriftSeverity:
        """변경 심각도 계산"""
        # 테이블 삭제 또는 컬럼 삭제가 있으면 CRITICAL
        for change in changes:
            if change.type in (DriftChangeType.TABLE_DELETED, DriftChangeType.COLUMN_DELETED):
                return DriftSeverity.CRITICAL

        # 타입 변경이 있으면 WARNING
        for change in changes:
            if change.type == DriftChangeType.TYPE_CHANGED:
                return DriftSeverity.WARNING

        # 그 외 (추가만)는 INFO
        return DriftSeverity.INFO

    def _compute_schema_hash(self, schema: dict[str, Any]) -> str:
        """스키마 해시 계산"""
        # 정렬된 JSON으로 변환 후 SHA256
        sorted_json = json.dumps(schema, sort_keys=True)
        return hashlib.sha256(sorted_json.encode()).hexdigest()

    # =========================================
    # Database Operations
    # =========================================
    async def _get_latest_snapshot(self, connector_id: UUID) -> dict | None:
        """마지막 스냅샷 조회"""
        query = text("""
            SELECT snapshot_id, connector_id, tenant_id,
                   schema_data, schema_hash,
                   table_count, column_count,
                   captured_at, captured_by
            FROM core.schema_snapshots
            WHERE connector_id = :connector_id
            ORDER BY captured_at DESC
            LIMIT 1
        """)

        result = await self.db.execute(query, {"connector_id": str(connector_id)})
        row = result.fetchone()

        if not row:
            return None

        return {
            "snapshot_id": row.snapshot_id,
            "schema_data": row.schema_data,
            "schema_hash": row.schema_hash,
        }

    async def _save_snapshot(
        self,
        connector_id: UUID,
        tenant_id: UUID,
        schema_data: dict,
        schema_hash: str,
        table_count: int,
        column_count: int,
        captured_by: UUID | None,
    ) -> UUID:
        """스냅샷 저장"""
        query = text("""
            INSERT INTO core.schema_snapshots (
                connector_id, tenant_id, schema_data, schema_hash,
                table_count, column_count, captured_by
            )
            VALUES (
                :connector_id, :tenant_id, :schema_data, :schema_hash,
                :table_count, :column_count, :captured_by
            )
            RETURNING snapshot_id
        """)

        result = await self.db.execute(
            query,
            {
                "connector_id": str(connector_id),
                "tenant_id": str(tenant_id),
                "schema_data": json.dumps(schema_data),
                "schema_hash": schema_hash,
                "table_count": table_count,
                "column_count": column_count,
                "captured_by": str(captured_by) if captured_by else None,
            },
        )
        await self.db.commit()

        row = result.fetchone()
        return row.snapshot_id

    async def _save_drift_detection(
        self,
        connector_id: UUID,
        tenant_id: UUID,
        old_snapshot_id: UUID,
        new_snapshot_id: UUID,
        changes: list[DriftChange],
        severity: DriftSeverity,
        tables_added: int,
        tables_deleted: int,
        columns_added: int,
        columns_deleted: int,
        types_changed: int,
    ) -> UUID:
        """변경 감지 기록 저장"""
        query = text("""
            INSERT INTO core.schema_drift_detections (
                connector_id, tenant_id, old_snapshot_id, new_snapshot_id,
                changes, change_count,
                tables_added, tables_deleted, columns_added, columns_deleted, types_changed,
                severity
            )
            VALUES (
                :connector_id, :tenant_id, :old_snapshot_id, :new_snapshot_id,
                :changes, :change_count,
                :tables_added, :tables_deleted, :columns_added, :columns_deleted, :types_changed,
                :severity
            )
            RETURNING detection_id
        """)

        changes_json = [c.model_dump() for c in changes]

        result = await self.db.execute(
            query,
            {
                "connector_id": str(connector_id),
                "tenant_id": str(tenant_id),
                "old_snapshot_id": str(old_snapshot_id),
                "new_snapshot_id": str(new_snapshot_id),
                "changes": json.dumps(changes_json),
                "change_count": len(changes),
                "tables_added": tables_added,
                "tables_deleted": tables_deleted,
                "columns_added": columns_added,
                "columns_deleted": columns_deleted,
                "types_changed": types_changed,
                "severity": severity.value,
            },
        )
        await self.db.commit()

        row = result.fetchone()
        return row.detection_id

    async def _update_connection_status(
        self,
        connector_id: UUID,
        success: bool,
        error: str | None,
    ) -> None:
        """연결 상태 업데이트"""
        query = text("""
            UPDATE core.data_connectors
            SET last_connection_test = now(),
                last_connection_status = :status,
                connection_error = :error
            WHERE connector_id = :connector_id
        """)

        await self.db.execute(
            query,
            {
                "connector_id": str(connector_id),
                "status": "success" if success else "failure",
                "error": error,
            },
        )
        await self.db.commit()

    # =========================================
    # Row Converters
    # =========================================
    def _row_to_connector(self, row) -> DataConnector:
        """DB row → DataConnector"""
        return DataConnector(
            connector_id=row.connector_id,
            tenant_id=row.tenant_id,
            name=row.name,
            description=row.description,
            connector_type=ConnectorType(row.connector_type),
            connection_config=row.connection_config or {},
            status=row.status,
            last_connection_test=row.last_connection_test,
            last_connection_status=row.last_connection_status,
            connection_error=row.connection_error,
            tags=row.tags or [],
            attributes=row.attributes or {},
            created_at=row.created_at,
            updated_at=row.updated_at,
            created_by=row.created_by,
        )

    def _row_to_drift_detection(self, row) -> SchemaDriftDetection:
        """DB row → SchemaDriftDetection"""
        changes = []
        if row.changes:
            for c in row.changes:
                changes.append(
                    DriftChange(
                        type=DriftChangeType(c["type"]),
                        table_name=c["table_name"],
                        column_name=c.get("column_name"),
                        old_value=c.get("old_value"),
                        new_value=c.get("new_value"),
                        details=c.get("details"),
                    )
                )

        return SchemaDriftDetection(
            detection_id=row.detection_id,
            connector_id=row.connector_id,
            tenant_id=row.tenant_id,
            old_snapshot_id=row.old_snapshot_id,
            new_snapshot_id=row.new_snapshot_id,
            changes=changes,
            change_count=row.change_count,
            tables_added=row.tables_added,
            tables_deleted=row.tables_deleted,
            columns_added=row.columns_added,
            columns_deleted=row.columns_deleted,
            types_changed=row.types_changed,
            severity=DriftSeverity(row.severity),
            is_acknowledged=row.is_acknowledged,
            acknowledged_at=row.acknowledged_at,
            acknowledged_by=row.acknowledged_by,
            alert_sent=row.alert_sent,
            alert_sent_at=row.alert_sent_at,
            detected_at=row.detected_at,
        )
