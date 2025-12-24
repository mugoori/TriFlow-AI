"""
StatCard ORM Models
대시보드 StatCard 설정 DB 모델

스펙 참조: 024_stat_card_configs.sql
"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB, ARRAY
from sqlalchemy.orm import relationship

from app.database import Base


class StatCardConfig(Base):
    """StatCard 설정 테이블

    사용자별 대시보드 StatCard 커스터마이징 지원
    데이터 소스: KPI, DB Query, MCP Tool
    """

    __tablename__ = "stat_card_configs"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('kpi', 'db_query', 'mcp_tool')",
            name="chk_stat_card_source_type"
        ),
        CheckConstraint(
            "source_type != 'kpi' OR kpi_code IS NOT NULL",
            name="chk_kpi_source"
        ),
        CheckConstraint(
            "source_type != 'db_query' OR (table_name IS NOT NULL AND column_name IS NOT NULL AND aggregation IS NOT NULL)",
            name="chk_db_query_source"
        ),
        CheckConstraint(
            "source_type != 'mcp_tool' OR (mcp_server_id IS NOT NULL AND mcp_tool_name IS NOT NULL)",
            name="chk_mcp_tool_source"
        ),
        CheckConstraint(
            "aggregation IS NULL OR aggregation IN ('sum', 'avg', 'min', 'max', 'count', 'last')",
            name="chk_aggregation_type"
        ),
        {"schema": "bi", "extend_existing": True}
    )

    config_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("core.users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # 표시 순서 및 가시성
    display_order = Column(Integer, nullable=False, default=0)
    is_visible = Column(Boolean, nullable=False, default=True)

    # 데이터 소스 유형
    source_type = Column(String(20), nullable=False)  # kpi, db_query, mcp_tool

    # KPI 소스 (source_type = 'kpi')
    kpi_code = Column(String(50), nullable=True)  # bi.dim_kpi.kpi_code 참조

    # DB Query 소스 (source_type = 'db_query')
    table_name = Column(String(100), nullable=True)
    column_name = Column(String(100), nullable=True)
    aggregation = Column(String(20), nullable=True)  # sum, avg, min, max, count, last
    filter_condition = Column(JSONB, nullable=True)  # {"line_code": "L1"}

    # MCP Tool 소스 (source_type = 'mcp_tool')
    mcp_server_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("core.mcp_servers.server_id", ondelete="SET NULL"),
        nullable=True
    )
    mcp_tool_name = Column(String(100), nullable=True)
    mcp_params = Column(JSONB, nullable=True)  # 도구 호출 파라미터
    mcp_result_key = Column(String(255), nullable=True)  # 응답에서 추출할 키

    # 표시 설정 (커스텀 오버라이드)
    custom_title = Column(String(100), nullable=True)
    custom_icon = Column(String(50), nullable=True)  # Lucide 아이콘명
    custom_unit = Column(String(20), nullable=True)

    # 임계값 (DB Query, MCP용 - KPI는 dim_kpi에서 가져옴)
    green_threshold = Column(Numeric(12, 4), nullable=True)
    yellow_threshold = Column(Numeric(12, 4), nullable=True)
    red_threshold = Column(Numeric(12, 4), nullable=True)
    higher_is_better = Column(Boolean, nullable=False, default=True)

    # 캐시 설정
    cache_ttl_seconds = Column(Integer, nullable=False, default=60)

    # 메타데이터
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    mcp_server = relationship("MCPServer", backref="stat_cards", lazy="select")

    def __repr__(self):
        return f"<StatCardConfig(id={self.config_id}, source={self.source_type}, title={self.custom_title or self.kpi_code})>"

    @property
    def effective_title(self) -> str:
        """실제 사용할 제목 반환"""
        if self.custom_title:
            return self.custom_title
        if self.source_type == "kpi":
            return self.kpi_code or "KPI"
        if self.source_type == "db_query":
            return f"{self.table_name}.{self.column_name}"
        if self.source_type == "mcp_tool":
            return self.mcp_tool_name or "MCP Tool"
        return "StatCard"


class AllowedStatCardTable(Base):
    """StatCard DB 쿼리에서 사용 가능한 테이블/컬럼 화이트리스트"""

    __tablename__ = "allowed_stat_card_tables"
    __table_args__ = {"schema": "bi", "extend_existing": True}

    tenant_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"),
        primary_key=True
    )
    schema_name = Column(String(50), primary_key=True, default="bi")
    table_name = Column(String(100), primary_key=True)
    column_name = Column(String(100), primary_key=True)

    data_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    allowed_aggregations = Column(
        ARRAY(String),
        nullable=False,
        default=["sum", "avg", "min", "max", "count", "last"]
    )
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<AllowedStatCardTable({self.schema_name}.{self.table_name}.{self.column_name})>"
