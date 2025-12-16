"""
BI & Analytics Schema ORM Models
스펙 참조: B-3-2

데이터 계층:
- RAW Layer: 원본 데이터 보존 (raw_mes_production, raw_erp_order, raw_inventory, raw_equipment_event)
- DIM Layer: Dimension 테이블 (dim_date, dim_line, dim_product, dim_equipment, dim_kpi, dim_shift)
- FACT Layer: Fact 테이블 (fact_daily_production, fact_daily_defect, fact_inventory_snapshot, fact_equipment_event, fact_hourly_production)
- BI Catalog: BI 메타데이터 (bi_datasets, bi_metrics, bi_dashboards, bi_components)
- ETL: ETL 메타데이터 (etl_jobs, etl_job_executions)
- Data Quality: 품질 체크 (data_quality_rules, data_quality_checks)
"""
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    Boolean,
    DateTime,
    Date,
    Time,
    ForeignKey,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB, ARRAY
from sqlalchemy.orm import relationship

from app.database import Base


# ========== RAW Layer ==========


class RawMesProduction(Base):
    """MES 생산 데이터 RAW 테이블 (월별 파티션)

    스펙 참조: B-3-2 § 2.1
    - 원본 데이터 완전 보존
    - JSONB payload로 유연한 스키마 지원
    """

    __tablename__ = "raw_mes_production"
    __table_args__ = {"schema": "bi", "extend_existing": True}

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)

    src_system = Column(String(50), nullable=False, default="MES")
    src_table = Column(String(100), nullable=False)
    src_pk = Column(String(255), nullable=False)

    payload = Column(JSONB, nullable=False)  # 전체 원본 레코드
    event_time = Column(DateTime(timezone=True), nullable=False)
    ingested_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    processing_status = Column(
        String(20),
        nullable=False,
        default="pending"
    )  # pending, processed, error, duplicate
    error_message = Column(Text, nullable=True)
    raw_metadata = Column(JSONB, default={})

    def __repr__(self):
        return f"<RawMesProduction(id={self.id}, src={self.src_system}/{self.src_table})>"


class RawErpOrder(Base):
    """ERP 주문 데이터 RAW 테이블

    스펙 참조: B-3-2 § 2.2
    """

    __tablename__ = "raw_erp_order"
    __table_args__ = {"schema": "bi", "extend_existing": True}

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)

    src_system = Column(String(50), nullable=False, default="ERP")
    src_table = Column(String(100), nullable=False)
    src_pk = Column(String(255), nullable=False)

    payload = Column(JSONB, nullable=False)
    event_time = Column(DateTime(timezone=True), nullable=False)
    ingested_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    processing_status = Column(String(20), nullable=False, default="pending")
    error_message = Column(Text, nullable=True)
    raw_metadata = Column(JSONB, default={})

    def __repr__(self):
        return f"<RawErpOrder(id={self.id}, src={self.src_system}/{self.src_table})>"


class RawInventory(Base):
    """재고 데이터 RAW 테이블

    스펙 참조: B-3-2 § 2.3
    """

    __tablename__ = "raw_inventory"
    __table_args__ = {"schema": "bi", "extend_existing": True}

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)

    src_system = Column(String(50), nullable=False)
    src_table = Column(String(100), nullable=False)
    src_pk = Column(String(255), nullable=False)

    payload = Column(JSONB, nullable=False)
    event_time = Column(DateTime(timezone=True), nullable=False)
    ingested_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    processing_status = Column(String(20), nullable=False, default="pending")
    error_message = Column(Text, nullable=True)
    raw_metadata = Column(JSONB, default={})

    def __repr__(self):
        return f"<RawInventory(id={self.id}, src={self.src_system}/{self.src_table})>"


class RawEquipmentEvent(Base):
    """설비 이벤트 RAW 테이블

    스펙 참조: B-3-2 § 2.4
    - 설비 알람, 고장, 상태 변경 이벤트
    """

    __tablename__ = "raw_equipment_event"
    __table_args__ = {"schema": "bi", "extend_existing": True}

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)

    src_system = Column(String(50), nullable=False)
    src_table = Column(String(100), nullable=False)
    src_pk = Column(String(255), nullable=False)

    payload = Column(JSONB, nullable=False)  # equipment_code, event_type, alarm_code, severity 등
    event_time = Column(DateTime(timezone=True), nullable=False)
    ingested_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    processing_status = Column(String(20), nullable=False, default="pending")
    error_message = Column(Text, nullable=True)
    raw_metadata = Column(JSONB, default={})

    def __repr__(self):
        return f"<RawEquipmentEvent(id={self.id}, src={self.src_system}/{self.src_table})>"


# ========== DIM Layer ==========


class DimDate(Base):
    """날짜 차원 테이블

    스펙 참조: B-3-2 § 3.1
    - 날짜 기반 분석을 위한 차원 테이블
    - 2020-2030 시드 데이터
    """

    __tablename__ = "dim_date"
    __table_args__ = {"schema": "bi", "extend_existing": True}

    date = Column(Date, primary_key=True)
    year = Column(Integer, nullable=False)
    quarter = Column(Integer, nullable=False)  # 1-4
    month = Column(Integer, nullable=False)  # 1-12
    week = Column(Integer, nullable=False)  # 1-53
    day_of_year = Column(Integer, nullable=False)  # 1-366
    day_of_month = Column(Integer, nullable=False)  # 1-31
    day_of_week = Column(Integer, nullable=False)  # 0-6 (Sunday=0)
    day_name = Column(String(20), nullable=False)
    is_weekend = Column(Boolean, nullable=False)
    is_holiday = Column(Boolean, nullable=False, default=False)
    holiday_name = Column(String(100), nullable=True)

    # 회계연도 (Fiscal Year)
    fiscal_year = Column(Integer, nullable=True)
    fiscal_quarter = Column(Integer, nullable=True)
    fiscal_month = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<DimDate(date={self.date}, year={self.year})>"


class DimLine(Base):
    """생산 라인 차원 테이블

    스펙 참조: B-3-2 § 3.2
    """

    __tablename__ = "dim_line"
    __table_args__ = (
        UniqueConstraint("tenant_id", "line_code", name="uq_dim_line_code"),
        {"schema": "bi", "extend_existing": True}
    )

    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), primary_key=True)
    line_code = Column(String(50), primary_key=True)

    name = Column(String(255), nullable=False)
    category = Column(String(50), nullable=True)  # assembly, processing, packaging, inspection, warehouse
    capacity_per_hour = Column(Numeric(12, 2), nullable=True)
    capacity_unit = Column(String(20), nullable=True)
    timezone = Column(String(50), nullable=False, default="Asia/Seoul")

    plant_code = Column(String(50), nullable=True)
    department = Column(String(100), nullable=True)
    manager = Column(String(100), nullable=True)
    cost_center = Column(String(50), nullable=True)

    attributes = Column(JSONB, default={})  # shift_pattern, automation_level, target_oee 등

    is_active = Column(Boolean, nullable=False, default=True)
    activated_at = Column(Date, nullable=True)
    deactivated_at = Column(Date, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<DimLine(code={self.line_code}, name='{self.name}')>"


class DimProduct(Base):
    """제품 차원 테이블

    스펙 참조: B-3-2 § 3.3
    """

    __tablename__ = "dim_product"
    __table_args__ = (
        UniqueConstraint("tenant_id", "product_code", name="uq_dim_product_code"),
        {"schema": "bi", "extend_existing": True}
    )

    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), primary_key=True)
    product_code = Column(String(50), primary_key=True)

    name = Column(String(255), nullable=False)
    name_en = Column(String(255), nullable=True)
    spec = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    subcategory = Column(String(100), nullable=True)
    unit = Column(String(20), nullable=False, default="EA")

    standard_cost = Column(Numeric(12, 2), nullable=True)
    target_cycle_time_sec = Column(Numeric(8, 2), nullable=True)
    quality_standard = Column(Text, nullable=True)

    attributes = Column(JSONB, default={})

    is_active = Column(Boolean, nullable=False, default=True)
    activated_at = Column(Date, nullable=True)
    discontinued_at = Column(Date, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<DimProduct(code={self.product_code}, name='{self.name}')>"


class DimEquipment(Base):
    """설비 차원 테이블

    스펙 참조: B-3-2 § 3.4
    """

    __tablename__ = "dim_equipment"
    __table_args__ = (
        UniqueConstraint("tenant_id", "equipment_code", name="uq_dim_equipment_code"),
        {"schema": "bi", "extend_existing": True}
    )

    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), primary_key=True)
    equipment_code = Column(String(50), primary_key=True)
    line_code = Column(String(50), nullable=False)

    name = Column(String(255), nullable=False)
    equipment_type = Column(String(50), nullable=True)  # machine, robot, conveyor, inspection, utility
    vendor = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    serial_number = Column(String(100), nullable=True)

    install_date = Column(Date, nullable=True)
    warranty_expiry_date = Column(Date, nullable=True)

    # 유지보수 관련
    maintenance_cycle_days = Column(Integer, nullable=True)
    last_maintenance_date = Column(Date, nullable=True)
    next_maintenance_date = Column(Date, nullable=True)

    # 신뢰성 지표
    mtbf_hours = Column(Numeric(10, 2), nullable=True)  # Mean Time Between Failures
    mttr_hours = Column(Numeric(10, 2), nullable=True)  # Mean Time To Repair

    attributes = Column(JSONB, default={})

    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<DimEquipment(code={self.equipment_code}, name='{self.name}')>"


class DimKpi(Base):
    """KPI 정의 차원 테이블

    스펙 참조: B-3-2 § 3.5
    - KPI 정의 및 임계값 관리
    """

    __tablename__ = "dim_kpi"
    __table_args__ = (
        UniqueConstraint("tenant_id", "kpi_code", name="uq_dim_kpi_code"),
        {"schema": "bi", "extend_existing": True}
    )

    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), primary_key=True)
    kpi_code = Column(String(50), primary_key=True)

    name = Column(String(100), nullable=False)
    name_en = Column(String(100), nullable=True)
    category = Column(String(50), nullable=False)  # quality, production, efficiency, cost, safety, inventory
    unit = Column(String(20), nullable=True)
    description = Column(Text, nullable=True)
    calculation_method = Column(Text, nullable=True)  # 계산 방법 설명

    # 임계값
    default_target = Column(Numeric(12, 4), nullable=True)
    green_threshold = Column(Numeric(12, 4), nullable=True)  # 정상 기준
    yellow_threshold = Column(Numeric(12, 4), nullable=True)  # 주의 기준
    red_threshold = Column(Numeric(12, 4), nullable=True)  # 위험 기준

    higher_is_better = Column(Boolean, nullable=False, default=True)  # true: OEE, false: 불량률
    aggregation_method = Column(String(20), nullable=True)  # sum, avg, min, max, last

    attributes = Column(JSONB, default={})
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<DimKpi(code={self.kpi_code}, name='{self.name}')>"


class DimShift(Base):
    """교대 차원 테이블

    스펙 참조: B-3-2 § 3.6
    """

    __tablename__ = "dim_shift"
    __table_args__ = (
        UniqueConstraint("tenant_id", "shift_code", name="uq_dim_shift_code"),
        {"schema": "bi", "extend_existing": True}
    )

    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), primary_key=True)
    shift_code = Column(String(20), primary_key=True)

    name = Column(String(50), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    duration_hours = Column(Numeric(4, 2), nullable=False)
    is_night_shift = Column(Boolean, nullable=False, default=False)
    shift_order = Column(Integer, nullable=False)  # 순서

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<DimShift(code={self.shift_code}, name='{self.name}')>"


# ========== FACT Layer ==========


class FactDailyProduction(Base):
    """일일 생산 실적 FACT 테이블 (분기별 파티션)

    스펙 참조: B-3-2 § 4.1
    - 일/교대/라인/제품별 생산 실적 집계
    """

    __tablename__ = "fact_daily_production"
    __table_args__ = {"schema": "bi", "extend_existing": True}

    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), primary_key=True)
    date = Column(Date, primary_key=True)
    line_code = Column(String(50), primary_key=True)
    product_code = Column(String(50), primary_key=True)
    shift = Column(String(20), primary_key=True)

    # 수량 지표
    total_qty = Column(Numeric(12, 2), nullable=False, default=0)
    good_qty = Column(Numeric(12, 2), nullable=False, default=0)
    defect_qty = Column(Numeric(12, 2), nullable=False, default=0)
    rework_qty = Column(Numeric(12, 2), nullable=False, default=0)
    scrap_qty = Column(Numeric(12, 2), nullable=False, default=0)

    # 시간 지표
    cycle_time_avg = Column(Numeric(8, 2), nullable=True)  # 평균 사이클타임 (초)
    cycle_time_std = Column(Numeric(8, 2), nullable=True)  # 표준편차
    runtime_minutes = Column(Numeric(10, 2), nullable=False, default=0)
    downtime_minutes = Column(Numeric(10, 2), nullable=False, default=0)
    setup_time_minutes = Column(Numeric(10, 2), nullable=False, default=0)

    # 목표 지표
    planned_qty = Column(Numeric(12, 2), nullable=True)
    target_cycle_time = Column(Numeric(8, 2), nullable=True)

    # 기타
    work_order_count = Column(Integer, nullable=False, default=0)
    operator_count = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<FactDailyProduction(date={self.date}, line={self.line_code}, product={self.product_code})>"

    @property
    def yield_rate(self) -> float:
        """수율 계산"""
        if self.total_qty and self.total_qty > 0:
            return float(self.good_qty / self.total_qty)
        return 0.0

    @property
    def defect_rate(self) -> float:
        """불량률 계산"""
        if self.total_qty and self.total_qty > 0:
            return float(self.defect_qty / self.total_qty)
        return 0.0

    @property
    def availability(self) -> float:
        """가동률 계산"""
        total_time = float(self.runtime_minutes + self.downtime_minutes + self.setup_time_minutes)
        if total_time > 0:
            return float(self.runtime_minutes) / total_time
        return 0.0


class FactDailyDefect(Base):
    """일일 불량 상세 FACT 테이블

    스펙 참조: B-3-2 § 4.2
    - 불량 유형별 상세 집계
    """

    __tablename__ = "fact_daily_defect"
    __table_args__ = {"schema": "bi", "extend_existing": True}

    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), primary_key=True)
    date = Column(Date, primary_key=True)
    line_code = Column(String(50), primary_key=True)
    product_code = Column(String(50), primary_key=True)
    shift = Column(String(20), primary_key=True)
    defect_type = Column(String(50), primary_key=True)

    defect_qty = Column(Numeric(12, 2), nullable=False, default=0)
    defect_cost = Column(Numeric(12, 2), nullable=True)

    root_cause = Column(Text, nullable=True)
    countermeasure = Column(Text, nullable=True)
    responsible_dept = Column(String(100), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<FactDailyDefect(date={self.date}, type={self.defect_type}, qty={self.defect_qty})>"


class FactInventorySnapshot(Base):
    """일별 재고 스냅샷 FACT 테이블

    스펙 참조: B-3-2 § 4.3
    """

    __tablename__ = "fact_inventory_snapshot"
    __table_args__ = {"schema": "bi", "extend_existing": True}

    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), primary_key=True)
    date = Column(Date, primary_key=True)
    product_code = Column(String(50), primary_key=True)
    location = Column(String(50), primary_key=True)

    stock_qty = Column(Numeric(12, 2), nullable=False, default=0)
    safety_stock_qty = Column(Numeric(12, 2), nullable=False, default=0)
    reserved_qty = Column(Numeric(12, 2), nullable=False, default=0)
    available_qty = Column(Numeric(12, 2), nullable=False, default=0)
    in_transit_qty = Column(Numeric(12, 2), nullable=False, default=0)

    stock_value = Column(Numeric(14, 2), nullable=True)  # 재고 금액
    avg_daily_usage = Column(Numeric(10, 2), nullable=True)  # 일평균 사용량
    coverage_days = Column(Numeric(8, 2), nullable=True)  # 재고 커버리지 일수

    last_receipt_date = Column(Date, nullable=True)
    last_issue_date = Column(Date, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<FactInventorySnapshot(date={self.date}, product={self.product_code}, qty={self.stock_qty})>"

    @property
    def stock_status(self) -> str:
        """재고 상태 계산"""
        if self.stock_qty < self.safety_stock_qty:
            return "below_safety"
        elif self.stock_qty < self.safety_stock_qty * Decimal("1.5"):
            return "low"
        elif self.stock_qty > self.safety_stock_qty * Decimal("3"):
            return "excess"
        return "normal"


class FactEquipmentEvent(Base):
    """설비 이벤트 집계 FACT 테이블

    스펙 참조: B-3-2 § 4.4
    """

    __tablename__ = "fact_equipment_event"
    __table_args__ = {"schema": "bi", "extend_existing": True}

    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), primary_key=True)
    date = Column(Date, primary_key=True)
    equipment_code = Column(String(50), primary_key=True)
    event_type = Column(String(20), primary_key=True)  # alarm, breakdown, maintenance, setup, idle

    event_count = Column(Integer, nullable=False, default=0)
    total_duration_minutes = Column(Numeric(10, 2), nullable=False, default=0)
    avg_duration_minutes = Column(Numeric(10, 2), nullable=True)
    max_duration_minutes = Column(Numeric(10, 2), nullable=True)

    severity_distribution = Column(JSONB, nullable=True)  # {"info": 10, "warning": 5, "critical": 2}

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<FactEquipmentEvent(date={self.date}, equipment={self.equipment_code}, type={self.event_type})>"


class FactHourlyProduction(Base):
    """시간별 생산 실적 FACT 테이블 (실시간 모니터링용)

    스펙 참조: B-3-2 § 4.5
    """

    __tablename__ = "fact_hourly_production"
    __table_args__ = {"schema": "bi", "extend_existing": True}

    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), primary_key=True)
    hour_timestamp = Column(DateTime(timezone=True), primary_key=True)  # 시간 단위 정각
    line_code = Column(String(50), primary_key=True)
    product_code = Column(String(50), primary_key=True)

    total_qty = Column(Numeric(12, 2), nullable=False, default=0)
    good_qty = Column(Numeric(12, 2), nullable=False, default=0)
    defect_qty = Column(Numeric(12, 2), nullable=False, default=0)

    cycle_time_avg = Column(Numeric(8, 2), nullable=True)
    runtime_minutes = Column(Numeric(6, 2), nullable=False, default=0)  # 최대 60분
    downtime_minutes = Column(Numeric(6, 2), nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<FactHourlyProduction(hour={self.hour_timestamp}, line={self.line_code})>"


# ========== BI Catalog ==========


class BiDataset(Base):
    """BI 데이터셋 정의

    스펙 참조: B-3-2 § 6.1
    - BI 대시보드에서 사용할 데이터셋 메타데이터
    """

    __tablename__ = "bi_datasets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_bi_dataset_name"),
        {"schema": "bi", "extend_existing": True}
    )

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)

    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    source_type = Column(String(30), nullable=False)  # postgres_table, postgres_view, materialized_view, api_endpoint
    source_ref = Column(String(255), nullable=False)  # 테이블/뷰명 또는 API URL

    default_filters = Column(JSONB, nullable=True)  # 기본 필터 설정
    refresh_schedule = Column(String(50), nullable=True)  # cron 표현식
    last_refresh_at = Column(DateTime(timezone=True), nullable=True)
    row_count = Column(Integer, nullable=True)

    created_by = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    metrics = relationship("BiMetric", back_populates="dataset", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<BiDataset(name='{self.name}', source={self.source_type})>"


class BiMetric(Base):
    """BI 지표 정의

    스펙 참조: B-3-2 § 6.2
    """

    __tablename__ = "bi_metrics"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_bi_metric_name"),
        {"schema": "bi", "extend_existing": True}
    )

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    dataset_id = Column(PGUUID(as_uuid=True), ForeignKey("bi.bi_datasets.id", ondelete="CASCADE"), nullable=False)

    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    expression_sql = Column(Text, nullable=False)  # SQL 집계 표현식
    agg_type = Column(String(20), nullable=True)  # sum, avg, min, max, count, distinct_count, median, percentile

    format_type = Column(String(20), nullable=True)  # number, percent, currency, duration
    format_options = Column(JSONB, nullable=True)  # 포맷 옵션

    default_chart_type = Column(String(20), nullable=True)  # line, bar, pie, gauge 등

    created_by = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    dataset = relationship("BiDataset", back_populates="metrics")

    def __repr__(self):
        return f"<BiMetric(name='{self.name}', agg={self.agg_type})>"


class BiDashboard(Base):
    """BI 대시보드 정의

    스펙 참조: B-3-2 § 6.3
    """

    __tablename__ = "bi_dashboards"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_bi_dashboard_name"),
        {"schema": "bi", "extend_existing": True}
    )

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)

    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    layout = Column(JSONB, nullable=False)  # 컴포넌트 배치 정보

    is_public = Column(Boolean, nullable=False, default=False)
    owner_id = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id"), nullable=False)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<BiDashboard(name='{self.name}', is_public={self.is_public})>"


class BiComponent(Base):
    """BI 컴포넌트 템플릿

    스펙 참조: B-3-2 § 6.4
    """

    __tablename__ = "bi_components"
    __table_args__ = (
        UniqueConstraint("tenant_id", "component_type", "name", name="uq_bi_component"),
        {"schema": "bi", "extend_existing": True}
    )

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)

    component_type = Column(String(30), nullable=False)  # chart, table, kpi_card, gauge, heatmap, pivot
    name = Column(String(100), nullable=False)

    required_fields = Column(JSONB, nullable=False)  # 필수 필드 목록
    options_schema = Column(JSONB, nullable=False)  # 옵션 JSON Schema
    default_options = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<BiComponent(type={self.component_type}, name='{self.name}')>"


# ========== ETL Metadata ==========


class EtlJob(Base):
    """ETL 작업 정의

    스펙 참조: B-3-2 § 7.1
    """

    __tablename__ = "etl_jobs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_etl_job_name"),
        {"schema": "bi", "extend_existing": True}
    )

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)

    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    job_type = Column(String(30), nullable=False)  # raw_to_fact, fact_to_agg, refresh_mv, data_quality
    source_tables = Column(ARRAY(String), nullable=False)
    target_tables = Column(ARRAY(String), nullable=False)

    transform_logic = Column(Text, nullable=True)  # SQL 또는 Python 코드
    schedule_cron = Column(String(50), nullable=True)  # cron 표현식

    is_enabled = Column(Boolean, nullable=False, default=True)
    max_runtime_minutes = Column(Integer, nullable=False, default=60)
    retry_count = Column(Integer, nullable=False, default=3)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    executions = relationship("EtlJobExecution", back_populates="job", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<EtlJob(name='{self.name}', type={self.job_type})>"


class EtlJobExecution(Base):
    """ETL 실행 이력

    스펙 참조: B-3-2 § 7.2
    """

    __tablename__ = "etl_job_executions"
    __table_args__ = {"schema": "bi", "extend_existing": True}

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    job_id = Column(PGUUID(as_uuid=True), ForeignKey("bi.etl_jobs.id", ondelete="CASCADE"), nullable=False)

    status = Column(String(20), nullable=False, default="running")  # running, completed, failed, cancelled

    rows_processed = Column(Integer, nullable=True)
    rows_inserted = Column(Integer, nullable=True)
    rows_updated = Column(Integer, nullable=True)
    rows_deleted = Column(Integer, nullable=True)

    error_message = Column(Text, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    exec_metadata = Column(JSONB, default={})

    # Relationships
    job = relationship("EtlJob", back_populates="executions")

    def __repr__(self):
        return f"<EtlJobExecution(job_id={self.job_id}, status={self.status})>"


# ========== Data Quality ==========


class DataQualityRule(Base):
    """데이터 품질 규칙

    스펙 참조: B-3-2 § 8.1
    """

    __tablename__ = "data_quality_rules"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_dq_rule_name"),
        {"schema": "bi", "extend_existing": True}
    )

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)

    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    table_name = Column(String(100), nullable=False)
    rule_type = Column(String(30), nullable=False)  # not_null, range, uniqueness, referential_integrity, pattern, custom_sql
    rule_config = Column(JSONB, nullable=False)  # 규칙 설정

    severity = Column(String(20), nullable=False)  # info, warning, error, critical
    is_enabled = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    checks = relationship("DataQualityCheck", back_populates="rule", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<DataQualityRule(name='{self.name}', type={self.rule_type})>"


class DataQualityCheck(Base):
    """데이터 품질 체크 결과

    스펙 참조: B-3-2 § 8.2
    """

    __tablename__ = "data_quality_checks"
    __table_args__ = {"schema": "bi", "extend_existing": True}

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    rule_id = Column(PGUUID(as_uuid=True), ForeignKey("bi.data_quality_rules.id", ondelete="CASCADE"), nullable=False)

    status = Column(String(20), nullable=False)  # pass, fail, warning

    failed_row_count = Column(Integer, nullable=True)
    total_row_count = Column(Integer, nullable=True)
    sample_failed_rows = Column(JSONB, nullable=True)  # 실패 샘플

    executed_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    check_metadata = Column(JSONB, default={})

    # Relationships
    rule = relationship("DataQualityRule", back_populates="checks")

    def __repr__(self):
        return f"<DataQualityCheck(rule_id={self.rule_id}, status={self.status})>"
