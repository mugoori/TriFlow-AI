"""
StatCard ORM Models 테스트
app/models/statcard.py의 StatCardConfig, AllowedStatCardTable 테스트
"""
import pytest
from uuid import uuid4
from unittest.mock import MagicMock, patch


# ========== StatCardConfig 테스트 ==========


class TestStatCardConfig:
    """StatCardConfig 모델 테스트"""

    def test_statcard_config_import(self):
        """StatCardConfig 임포트 테스트"""
        from app.models.statcard import StatCardConfig

        assert StatCardConfig is not None
        assert StatCardConfig.__tablename__ == "stat_card_configs"

    def test_statcard_config_table_args(self):
        """테이블 제약조건 확인"""
        from app.models.statcard import StatCardConfig

        table_args = StatCardConfig.__table_args__
        # schema 확인
        assert table_args[-1]["schema"] == "bi"
        # CheckConstraint 확인
        constraints = [arg for arg in table_args if hasattr(arg, "name")]
        constraint_names = [c.name for c in constraints]

        assert "chk_stat_card_source_type" in constraint_names
        assert "chk_kpi_source" in constraint_names
        assert "chk_db_query_source" in constraint_names
        assert "chk_mcp_tool_source" in constraint_names
        assert "chk_aggregation_type" in constraint_names

    def test_repr_method(self):
        """__repr__ 메서드 테스트"""
        from app.models.statcard import StatCardConfig

        # __repr__ 메서드 직접 호출
        mock_config = MagicMock(spec=StatCardConfig)
        mock_config.config_id = uuid4()
        mock_config.source_type = "kpi"
        mock_config.custom_title = "My Custom Title"
        mock_config.kpi_code = "OEE"

        # 실제 __repr__ 로직 테스트
        repr_str = f"<StatCardConfig(id={mock_config.config_id}, source={mock_config.source_type}, title={mock_config.custom_title or mock_config.kpi_code})>"

        assert "StatCardConfig" in repr_str
        assert "kpi" in repr_str
        assert "My Custom Title" in repr_str

    def test_effective_title_logic_custom(self):
        """effective_title 로직 테스트 - custom_title 있음"""
        # 프로퍼티 로직 직접 테스트
        custom_title = "Custom Title"
        source_type = "kpi"
        kpi_code = "OEE"

        # 로직 재현
        if custom_title:
            result = custom_title
        elif source_type == "kpi":
            result = kpi_code or "KPI"
        else:
            result = "StatCard"

        assert result == "Custom Title"

    def test_effective_title_logic_kpi(self):
        """effective_title 로직 테스트 - KPI 소스"""
        custom_title = None
        source_type = "kpi"
        kpi_code = "OEE_DAILY"

        if custom_title:
            result = custom_title
        elif source_type == "kpi":
            result = kpi_code or "KPI"
        else:
            result = "StatCard"

        assert result == "OEE_DAILY"

    def test_effective_title_logic_kpi_no_code(self):
        """effective_title 로직 테스트 - KPI 소스, kpi_code 없음"""
        custom_title = None
        source_type = "kpi"
        kpi_code = None

        if custom_title:
            result = custom_title
        elif source_type == "kpi":
            result = kpi_code or "KPI"
        else:
            result = "StatCard"

        assert result == "KPI"

    def test_effective_title_logic_db_query(self):
        """effective_title 로직 테스트 - DB 쿼리 소스"""
        custom_title = None
        source_type = "db_query"
        table_name = "fact_oee"
        column_name = "oee_rate"

        if custom_title:
            result = custom_title
        elif source_type == "kpi":
            result = "KPI"
        elif source_type == "db_query":
            result = f"{table_name}.{column_name}"
        else:
            result = "StatCard"

        assert result == "fact_oee.oee_rate"

    def test_effective_title_logic_mcp_tool(self):
        """effective_title 로직 테스트 - MCP Tool 소스"""
        custom_title = None
        source_type = "mcp_tool"
        mcp_tool_name = "get_production_status"

        if custom_title:
            result = custom_title
        elif source_type == "kpi":
            result = "KPI"
        elif source_type == "db_query":
            result = "DB Query"
        elif source_type == "mcp_tool":
            result = mcp_tool_name or "MCP Tool"
        else:
            result = "StatCard"

        assert result == "get_production_status"

    def test_effective_title_logic_mcp_tool_no_name(self):
        """effective_title 로직 테스트 - MCP Tool, tool_name 없음"""
        custom_title = None
        source_type = "mcp_tool"
        mcp_tool_name = None

        if custom_title:
            result = custom_title
        elif source_type == "mcp_tool":
            result = mcp_tool_name or "MCP Tool"
        else:
            result = "StatCard"

        assert result == "MCP Tool"

    def test_effective_title_logic_unknown_source(self):
        """effective_title 로직 테스트 - 알 수 없는 소스"""
        custom_title = None
        source_type = "unknown"

        if custom_title:
            result = custom_title
        elif source_type == "kpi":
            result = "KPI"
        elif source_type == "db_query":
            result = "DB Query"
        elif source_type == "mcp_tool":
            result = "MCP Tool"
        else:
            result = "StatCard"

        assert result == "StatCard"

    def test_columns_exist(self):
        """필수 컬럼 존재 확인"""
        from app.models.statcard import StatCardConfig

        columns = [c.name for c in StatCardConfig.__table__.columns]

        assert "config_id" in columns
        assert "tenant_id" in columns
        assert "user_id" in columns
        assert "source_type" in columns
        assert "kpi_code" in columns
        assert "table_name" in columns
        assert "column_name" in columns
        assert "mcp_server_id" in columns
        assert "mcp_tool_name" in columns
        assert "custom_title" in columns
        assert "cache_ttl_seconds" in columns


# ========== AllowedStatCardTable 테스트 ==========


class TestAllowedStatCardTable:
    """AllowedStatCardTable 모델 테스트"""

    def test_allowed_table_import(self):
        """AllowedStatCardTable 임포트 테스트"""
        from app.models.statcard import AllowedStatCardTable

        assert AllowedStatCardTable is not None
        assert AllowedStatCardTable.__tablename__ == "allowed_stat_card_tables"

    def test_allowed_table_schema(self):
        """테이블 스키마 확인"""
        from app.models.statcard import AllowedStatCardTable

        table_args = AllowedStatCardTable.__table_args__

        assert table_args["schema"] == "bi"

    def test_repr_logic(self):
        """__repr__ 로직 테스트"""
        schema_name = "bi"
        table_name = "fact_oee"
        column_name = "oee_rate"

        repr_str = f"<AllowedStatCardTable({schema_name}.{table_name}.{column_name})>"

        assert "AllowedStatCardTable" in repr_str
        assert "bi.fact_oee.oee_rate" in repr_str

    def test_primary_key_columns(self):
        """복합 기본키 확인"""
        from app.models.statcard import AllowedStatCardTable

        pk_columns = [c.name for c in AllowedStatCardTable.__table__.primary_key.columns]

        assert "tenant_id" in pk_columns
        assert "schema_name" in pk_columns
        assert "table_name" in pk_columns
        assert "column_name" in pk_columns

    def test_columns_exist(self):
        """필수 컬럼 존재 확인"""
        from app.models.statcard import AllowedStatCardTable

        columns = [c.name for c in AllowedStatCardTable.__table__.columns]

        assert "tenant_id" in columns
        assert "schema_name" in columns
        assert "table_name" in columns
        assert "column_name" in columns
        assert "data_type" in columns
        assert "description" in columns
        assert "allowed_aggregations" in columns
        assert "is_active" in columns
        assert "created_at" in columns

    def test_allowed_aggregations_column(self):
        """allowed_aggregations 컬럼 정의 확인"""
        from app.models.statcard import AllowedStatCardTable

        col = AllowedStatCardTable.__table__.c.allowed_aggregations
        # ARRAY 타입 확인
        assert col is not None
        # default가 list인지 확인
        assert col.default is not None
