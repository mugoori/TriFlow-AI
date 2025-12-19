"""
MCP ToolHub Pydantic Models

스펙 참조: B-2-3_MCP_DataHub_Chat_Design.md

MCP ToolHub: 외부 MCP 서버 호출을 표준화하는 게이트웨이
- MCP 서버 레지스트리 관리
- 도구 메타데이터 저장
- 도구 호출 프록시 (인증, 타임아웃, 재시도)
- Circuit Breaker
- 커넥터 헬스 체크
- Drift 감지
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# =====================================================
# Enums
# =====================================================
class AuthType(str, Enum):
    """MCP 서버 인증 타입"""

    NONE = "none"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    BASIC = "basic"


class MCPServerStatus(str, Enum):
    """MCP 서버 상태"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class HealthStatus(str, Enum):
    """헬스체크 상태"""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CircuitBreakerStateEnum(str, Enum):
    """Circuit Breaker 상태"""

    CLOSED = "CLOSED"  # 정상 - 모든 요청 통과
    OPEN = "OPEN"  # 차단 - 모든 요청 거부
    HALF_OPEN = "HALF_OPEN"  # 테스트 - 일부 요청만 통과


class MCPCallStatus(str, Enum):
    """MCP 호출 결과 상태"""

    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    CIRCUIT_OPEN = "circuit_open"


class ConnectorType(str, Enum):
    """데이터 커넥터 타입"""

    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MSSQL = "mssql"
    ORACLE = "oracle"
    REST_API = "rest_api"
    MQTT = "mqtt"
    S3 = "s3"
    GCS = "gcs"


class DriftChangeType(str, Enum):
    """스키마 변경 타입"""

    TABLE_ADDED = "table_added"
    TABLE_DELETED = "table_deleted"
    COLUMN_ADDED = "column_added"
    COLUMN_DELETED = "column_deleted"
    TYPE_CHANGED = "type_changed"


class DriftSeverity(str, Enum):
    """스키마 변경 심각도"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# =====================================================
# OAuth2 Config
# =====================================================
class OAuth2Config(BaseModel):
    """OAuth2 인증 설정"""

    model_config = ConfigDict(extra="forbid")

    token_url: str = Field(..., description="OAuth2 토큰 엔드포인트 URL")
    client_id: str = Field(..., description="OAuth2 Client ID")
    client_secret: str = Field(..., description="OAuth2 Client Secret")
    scope: str | None = Field(None, description="OAuth2 Scope (공백 구분)")


class BasicAuthConfig(BaseModel):
    """Basic 인증 설정"""

    model_config = ConfigDict(extra="forbid")

    username: str
    password: str


# =====================================================
# MCP Server Models
# =====================================================
class MCPServerBase(BaseModel):
    """MCP 서버 기본 모델"""

    name: str = Field(..., min_length=1, max_length=100, description="서버 이름")
    description: str | None = Field(None, max_length=500)
    base_url: str = Field(..., description="MCP 서버 기본 URL")

    auth_type: AuthType = Field(AuthType.NONE, description="인증 타입")
    api_key: str | None = Field(None, description="API Key (auth_type=api_key)")
    oauth_config: OAuth2Config | None = Field(None, description="OAuth2 설정")
    basic_auth_config: BasicAuthConfig | None = Field(None, description="Basic 인증 설정")

    timeout_ms: int = Field(30000, ge=1000, le=300000, description="타임아웃 (ms)")
    retry_count: int = Field(3, ge=0, le=10, description="재시도 횟수")
    retry_delay_ms: int = Field(1000, ge=100, le=30000, description="재시도 대기 (ms)")

    tags: list[str] = Field(default_factory=list, description="태그 목록")
    attributes: dict[str, Any] = Field(default_factory=dict, description="추가 속성")

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        return v.rstrip("/")


class MCPServerCreate(MCPServerBase):
    """MCP 서버 생성 요청"""

    pass


class MCPServerUpdate(BaseModel):
    """MCP 서버 수정 요청"""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    base_url: str | None = None

    auth_type: AuthType | None = None
    api_key: str | None = None
    oauth_config: OAuth2Config | None = None
    basic_auth_config: BasicAuthConfig | None = None

    timeout_ms: int | None = Field(None, ge=1000, le=300000)
    retry_count: int | None = Field(None, ge=0, le=10)
    retry_delay_ms: int | None = Field(None, ge=100, le=30000)

    status: MCPServerStatus | None = None
    tags: list[str] | None = None
    attributes: dict[str, Any] | None = None


class MCPServer(MCPServerBase):
    """MCP 서버 응답 모델"""

    model_config = ConfigDict(from_attributes=True)

    server_id: UUID
    tenant_id: UUID

    status: MCPServerStatus = MCPServerStatus.ACTIVE
    last_health_check: datetime | None = None
    last_health_status: HealthStatus | None = None
    health_check_error: str | None = None

    created_at: datetime
    updated_at: datetime
    created_by: UUID | None = None


# =====================================================
# MCP Tool Models
# =====================================================
class MCPToolBase(BaseModel):
    """MCP 도구 기본 모델"""

    name: str = Field(..., min_length=1, max_length=100, description="도구 이름")
    description: str | None = Field(None, max_length=500)
    method: str = Field(..., description="JSON-RPC method 이름 (예: tools/read_file)")

    input_schema: dict[str, Any] = Field(default_factory=dict, description="입력 JSON Schema")
    output_schema: dict[str, Any] = Field(default_factory=dict, description="출력 JSON Schema")

    is_enabled: bool = Field(True, description="활성화 여부")
    tags: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


class MCPToolCreate(MCPToolBase):
    """MCP 도구 생성 요청"""

    server_id: UUID


class MCPToolUpdate(BaseModel):
    """MCP 도구 수정 요청"""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    method: str | None = None

    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None

    is_enabled: bool | None = None
    tags: list[str] | None = None
    attributes: dict[str, Any] | None = None


class MCPTool(MCPToolBase):
    """MCP 도구 응답 모델"""

    model_config = ConfigDict(from_attributes=True)

    tool_id: UUID
    server_id: UUID
    tenant_id: UUID

    # 사용 통계
    call_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    avg_latency_ms: float | None = None
    last_called_at: datetime | None = None

    created_at: datetime
    updated_at: datetime


# =====================================================
# MCP Call Models
# =====================================================
class MCPCallRequest(BaseModel):
    """MCP 도구 호출 요청"""

    server_id: UUID = Field(..., description="MCP 서버 ID")
    tool_name: str = Field(..., description="도구 이름")
    args: dict[str, Any] = Field(default_factory=dict, description="도구 인자")

    correlation_id: str | None = Field(None, description="연관 요청 추적 ID")


class MCPCallResponse(BaseModel):
    """MCP 도구 호출 응답"""

    request_id: str = Field(..., description="JSON-RPC request ID")
    status: MCPCallStatus = Field(..., description="호출 결과 상태")

    result: dict[str, Any] | None = Field(None, description="성공 시 결과")
    error_message: str | None = Field(None, description="실패 시 에러 메시지")
    error_code: str | None = Field(None, description="에러 코드")

    latency_ms: int = Field(..., description="응답 시간 (ms)")
    retry_count: int = Field(0, description="재시도 횟수")


# =====================================================
# Circuit Breaker Models
# =====================================================
class CircuitBreakerConfig(BaseModel):
    """Circuit Breaker 설정"""

    failure_threshold: int = Field(5, ge=1, le=100, description="OPEN 전환 실패 임계값")
    success_threshold: int = Field(2, ge=1, le=50, description="CLOSED 전환 성공 임계값")
    timeout_seconds: int = Field(60, ge=10, le=600, description="OPEN 상태 타임아웃 (초)")


class CircuitBreakerState(BaseModel):
    """Circuit Breaker 상태 응답"""

    model_config = ConfigDict(from_attributes=True)

    server_id: UUID
    state: CircuitBreakerStateEnum = CircuitBreakerStateEnum.CLOSED

    failure_count: int = 0
    success_count: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0

    failure_threshold: int = 5
    success_threshold: int = 2
    timeout_seconds: int = 60

    last_failure_at: datetime | None = None
    last_success_at: datetime | None = None
    opened_at: datetime | None = None
    half_opened_at: datetime | None = None

    updated_at: datetime


# =====================================================
# Data Connector Models
# =====================================================
class PostgreSQLConnectionConfig(BaseModel):
    """PostgreSQL 연결 설정"""

    host: str
    port: int = 5432
    database: str
    username: str
    password: str
    ssl_mode: str = "prefer"


class MySQLConnectionConfig(BaseModel):
    """MySQL 연결 설정"""

    host: str
    port: int = 3306
    database: str
    username: str
    password: str
    ssl: bool = False


class RestAPIConnectionConfig(BaseModel):
    """REST API 연결 설정"""

    base_url: str
    auth_type: AuthType = AuthType.NONE
    api_key: str | None = None
    oauth_config: OAuth2Config | None = None


class S3ConnectionConfig(BaseModel):
    """S3 연결 설정"""

    bucket: str
    region: str
    access_key: str
    secret_key: str
    prefix: str | None = None


class DataConnectorBase(BaseModel):
    """데이터 커넥터 기본 모델"""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    connector_type: ConnectorType

    connection_config: dict[str, Any] = Field(..., description="타입별 연결 설정")

    tags: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


class DataConnectorCreate(DataConnectorBase):
    """데이터 커넥터 생성 요청"""

    pass


class DataConnectorUpdate(BaseModel):
    """데이터 커넥터 수정 요청"""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None

    connection_config: dict[str, Any] | None = None
    status: str | None = None

    tags: list[str] | None = None
    attributes: dict[str, Any] | None = None


class DataConnector(DataConnectorBase):
    """데이터 커넥터 응답 모델"""

    model_config = ConfigDict(from_attributes=True)

    connector_id: UUID
    tenant_id: UUID

    status: str = "active"
    last_connection_test: datetime | None = None
    last_connection_status: str | None = None
    connection_error: str | None = None

    created_at: datetime
    updated_at: datetime
    created_by: UUID | None = None


# =====================================================
# Schema Drift Models
# =====================================================
class SchemaColumn(BaseModel):
    """스키마 컬럼 정보"""

    column_name: str
    data_type: str
    is_nullable: str
    column_default: str | None = None


class SchemaTable(BaseModel):
    """스키마 테이블 정보"""

    columns: list[SchemaColumn]


class SchemaSnapshotBase(BaseModel):
    """스키마 스냅샷 기본 모델"""

    schema_data: dict[str, SchemaTable] = Field(..., description="테이블별 컬럼 정보")


class SchemaSnapshotCreate(SchemaSnapshotBase):
    """스키마 스냅샷 생성 요청"""

    connector_id: UUID


class SchemaSnapshot(SchemaSnapshotBase):
    """스키마 스냅샷 응답 모델"""

    model_config = ConfigDict(from_attributes=True)

    snapshot_id: UUID
    connector_id: UUID
    tenant_id: UUID

    schema_hash: str
    table_count: int = 0
    column_count: int = 0

    captured_at: datetime
    captured_by: UUID | None = None


class DriftChange(BaseModel):
    """스키마 변경 항목"""

    type: DriftChangeType
    table_name: str
    column_name: str | None = None
    old_value: str | None = None
    new_value: str | None = None
    details: dict[str, Any] | None = None


class DriftReport(BaseModel):
    """스키마 변경 감지 리포트"""

    connector_id: UUID
    has_changes: bool = False
    changes: list[DriftChange] = Field(default_factory=list)

    # 카운트
    tables_added: int = 0
    tables_deleted: int = 0
    columns_added: int = 0
    columns_deleted: int = 0
    types_changed: int = 0

    severity: DriftSeverity = DriftSeverity.INFO

    old_snapshot_id: UUID | None = None
    new_snapshot_id: UUID | None = None

    detected_at: datetime = Field(default_factory=datetime.utcnow)


class SchemaDriftDetection(BaseModel):
    """스키마 변경 감지 응답 모델"""

    model_config = ConfigDict(from_attributes=True)

    detection_id: UUID
    connector_id: UUID
    tenant_id: UUID

    old_snapshot_id: UUID | None = None
    new_snapshot_id: UUID | None = None

    changes: list[DriftChange]
    change_count: int = 0

    tables_added: int = 0
    tables_deleted: int = 0
    columns_added: int = 0
    columns_deleted: int = 0
    types_changed: int = 0

    severity: DriftSeverity = DriftSeverity.INFO
    is_acknowledged: bool = False
    acknowledged_at: datetime | None = None
    acknowledged_by: UUID | None = None

    alert_sent: bool = False
    alert_sent_at: datetime | None = None

    detected_at: datetime


# =====================================================
# Health Check Models
# =====================================================
class MCPHealthCheckResponse(BaseModel):
    """MCP 서버 헬스체크 응답"""

    server_id: UUID
    status: HealthStatus
    latency_ms: int | None = None
    error: str | None = None
    checked_at: datetime = Field(default_factory=datetime.utcnow)


# =====================================================
# List Response Models
# =====================================================
class MCPServerList(BaseModel):
    """MCP 서버 목록 응답"""

    items: list[MCPServer]
    total: int
    page: int
    size: int


class MCPToolList(BaseModel):
    """MCP 도구 목록 응답"""

    items: list[MCPTool]
    total: int
    page: int
    size: int


class DataConnectorList(BaseModel):
    """데이터 커넥터 목록 응답"""

    items: list[DataConnector]
    total: int
    page: int
    size: int


class SchemaDriftDetectionList(BaseModel):
    """스키마 변경 감지 목록 응답"""

    items: list[SchemaDriftDetection]
    total: int
    page: int
    size: int
