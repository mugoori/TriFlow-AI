"""
Core Schema ORM Models
테넌트, 사용자, 룰셋, 워크플로, 센서 데이터 등
"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class Tenant(Base):
    """테넌트 (멀티테넌트 지원)"""

    __tablename__ = "tenants"
    __table_args__ = {"schema": "core"}

    tenant_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    settings = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    rulesets = relationship("Ruleset", back_populates="tenant", cascade="all, delete-orphan")
    workflows = relationship("Workflow", back_populates="tenant", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Tenant(id={self.tenant_id}, name='{self.name}')>"


class User(Base):
    """사용자"""

    __tablename__ = "users"
    __table_args__ = {"schema": "core"}

    user_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    username = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default="user")  # admin, user, viewer
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="users")

    def __repr__(self):
        return f"<User(id={self.user_id}, username='{self.username}')>"


class Ruleset(Base):
    """룰셋 (Rhai 스크립트 기반 규칙)"""

    __tablename__ = "rulesets"
    __table_args__ = {"schema": "core"}

    ruleset_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    rhai_script = Column("rhai_code", Text, nullable=False)  # DB column: rhai_code
    version = Column(String(50), default="1.0.0")
    is_active = Column(Boolean, default=True)
    created_by = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", back_populates="rulesets")
    versions = relationship("RulesetVersion", back_populates="ruleset", cascade="all, delete-orphan", order_by="desc(RulesetVersion.version_number)")

    def __repr__(self):
        return f"<Ruleset(id={self.ruleset_id}, name='{self.name}')>"


class RulesetVersion(Base):
    """룰셋 버전 히스토리"""

    __tablename__ = "ruleset_versions"
    __table_args__ = {"schema": "core"}

    version_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    ruleset_id = Column(PGUUID(as_uuid=True), ForeignKey("core.rulesets.ruleset_id", ondelete="CASCADE"), nullable=False)

    version_number = Column(Integer, nullable=False)  # 순차 증가 (1, 2, 3, ...)
    version_label = Column(String(50), nullable=False)  # 1.0.0, 1.0.1, ...
    rhai_script = Column(Text, nullable=False)  # 해당 버전의 스크립트
    description = Column(Text, nullable=True)  # 해당 버전의 설명
    change_summary = Column(String(500), nullable=True)  # 변경 사항 요약

    created_by = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    ruleset = relationship("Ruleset", back_populates="versions")

    def __repr__(self):
        return f"<RulesetVersion(ruleset_id={self.ruleset_id}, version={self.version_label})>"


class Workflow(Base):
    """워크플로 (JSON DSL 기반)"""

    __tablename__ = "workflows"
    __table_args__ = {"schema": "core"}

    workflow_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    dsl_definition = Column("dsl_json", JSONB, nullable=False)  # JSON DSL (DB column: dsl_json)
    version = Column(String(50), default="1.0.0")
    is_active = Column(Boolean, default=True)
    created_by = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", back_populates="workflows")
    instances = relationship("WorkflowInstance", back_populates="workflow")

    def __repr__(self):
        return f"<Workflow(id={self.workflow_id}, name='{self.name}')>"


class WorkflowInstance(Base):
    """워크플로 실행 인스턴스"""

    __tablename__ = "workflow_instances"
    __table_args__ = {"schema": "core"}

    instance_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    workflow_id = Column(PGUUID(as_uuid=True), ForeignKey("core.workflows.workflow_id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    input_data = Column(JSONB, default={})
    output_data = Column(JSONB, default={})
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    workflow = relationship("Workflow", back_populates="instances")

    def __repr__(self):
        return f"<WorkflowInstance(id={self.instance_id}, status='{self.status}')>"


class JudgmentExecution(Base):
    """판단 실행 로그 (Workflow/Ruleset 실행 결과)"""

    __tablename__ = "judgment_executions"
    __table_args__ = {"schema": "core"}

    execution_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    workflow_id = Column(PGUUID(as_uuid=True), ForeignKey("core.workflows.workflow_id", ondelete="SET NULL"), nullable=True)
    input_data = Column(JSONB, nullable=False)
    output_data = Column(JSONB, nullable=False)
    method_used = Column(String(50), nullable=False)  # RULE_ONLY, LLM_ONLY, HYBRID, etc.
    confidence = Column(Float, nullable=True)  # DB column: confidence
    execution_time_ms = Column(Integer, nullable=True)
    executed_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    workflow = relationship("Workflow", backref="executions")

    def __repr__(self):
        return f"<JudgmentExecution(id={self.execution_id}, confidence={self.confidence})>"


class SensorData(Base):
    """센서 데이터 (파티션 테이블)"""

    __tablename__ = "sensor_data"
    __table_args__ = {"schema": "core"}

    # 복합 PRIMARY KEY (sensor_id, recorded_at)
    sensor_id = Column(PGUUID(as_uuid=True), default=uuid4, primary_key=True)
    recorded_at = Column(DateTime, nullable=False, default=datetime.utcnow, primary_key=True)

    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    line_code = Column(String(100), nullable=False)
    sensor_type = Column(String(100), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=True)
    sensor_metadata = Column("metadata", JSONB, default={})  # 컬럼명 'metadata'이지만 속성명은 sensor_metadata

    def __repr__(self):
        return f"<SensorData(type='{self.sensor_type}', value={self.value}, recorded_at={self.recorded_at})>"


class FeedbackLog(Base):
    """피드백 로그 (Learning System용)"""

    __tablename__ = "feedback_logs"
    __table_args__ = {"schema": "core"}

    feedback_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    execution_id = Column(PGUUID(as_uuid=True), ForeignKey("core.judgment_executions.execution_id", ondelete="SET NULL"), nullable=True)

    feedback_type = Column(String(50), nullable=False)  # positive, negative, correction
    original_output = Column(JSONB, nullable=True)  # AI가 제안한 원래 출력
    corrected_output = Column(JSONB, nullable=True)  # 사용자가 수정한 출력
    feedback_text = Column(Text, nullable=True)  # 사용자 피드백 코멘트

    context_data = Column(JSONB, default={})  # 피드백 시점의 컨텍스트
    is_processed = Column(Boolean, default=False)  # 학습에 반영되었는지
    processed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<FeedbackLog(id={self.feedback_id}, type='{self.feedback_type}')>"


class ProposedRule(Base):
    """제안된 규칙 (Learning System이 생성)"""

    __tablename__ = "proposed_rules"
    __table_args__ = {"schema": "core"}

    proposal_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)

    rule_name = Column(String(255), nullable=False)
    rule_description = Column(Text, nullable=True)
    rhai_script = Column(Text, nullable=False)  # 제안된 Rhai 스크립트

    source_type = Column(String(50), nullable=False)  # feedback_analysis, pattern_detection, simulation
    source_data = Column(JSONB, default={})  # 제안 근거 데이터
    confidence = Column(Float, default=0.0)  # 제안 신뢰도 (0-1)

    status = Column(String(50), default="pending")  # pending, approved, rejected, deployed
    reviewed_by = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_comment = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ProposedRule(id={self.proposal_id}, name='{self.rule_name}', status='{self.status}')>"


class Experiment(Base):
    """A/B 테스트 실험"""

    __tablename__ = "experiments"
    __table_args__ = {"schema": "core"}

    experiment_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    hypothesis = Column(Text, nullable=True)  # 실험 가설

    status = Column(String(50), default="draft")  # draft, running, paused, completed, cancelled
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)

    # 트래픽 할당 설정
    traffic_percentage = Column(Integer, default=100)  # 전체 트래픽 중 실험에 참여할 비율 (%)

    # 통계적 유의성 설정
    min_sample_size = Column(Integer, default=100)  # 최소 샘플 크기
    confidence_level = Column(Float, default=0.95)  # 신뢰 수준 (95%)

    created_by = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    variants = relationship("ExperimentVariant", back_populates="experiment", cascade="all, delete-orphan")
    assignments = relationship("ExperimentAssignment", back_populates="experiment", cascade="all, delete-orphan")
    metrics = relationship("ExperimentMetric", back_populates="experiment", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Experiment(id={self.experiment_id}, name='{self.name}', status='{self.status}')>"


class ExperimentVariant(Base):
    """실험 변형 (Control/Treatment 그룹)"""

    __tablename__ = "experiment_variants"
    __table_args__ = {"schema": "core"}

    variant_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    experiment_id = Column(PGUUID(as_uuid=True), ForeignKey("core.experiments.experiment_id", ondelete="CASCADE"), nullable=False)

    name = Column(String(100), nullable=False)  # control, treatment_a, treatment_b, etc.
    description = Column(Text, nullable=True)
    is_control = Column(Boolean, default=False)  # 대조군 여부

    # 룰셋 연결
    ruleset_id = Column(PGUUID(as_uuid=True), ForeignKey("core.rulesets.ruleset_id", ondelete="SET NULL"), nullable=True)

    # 트래픽 배분 비율 (실험 내 비율, 합계 100%)
    traffic_weight = Column(Integer, default=50)  # %

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    experiment = relationship("Experiment", back_populates="variants")
    ruleset = relationship("Ruleset")
    assignments = relationship("ExperimentAssignment", back_populates="variant")
    metrics = relationship("ExperimentMetric", back_populates="variant")

    def __repr__(self):
        return f"<ExperimentVariant(id={self.variant_id}, name='{self.name}', is_control={self.is_control})>"


class ExperimentAssignment(Base):
    """사용자별 실험 그룹 할당"""

    __tablename__ = "experiment_assignments"
    __table_args__ = {"schema": "core"}

    assignment_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    experiment_id = Column(PGUUID(as_uuid=True), ForeignKey("core.experiments.experiment_id", ondelete="CASCADE"), nullable=False)
    variant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.experiment_variants.variant_id", ondelete="CASCADE"), nullable=False)

    # 할당 대상 (user_id 또는 session_id)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id", ondelete="SET NULL"), nullable=True)
    session_id = Column(String(255), nullable=True)  # 비로그인 사용자용

    assigned_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    experiment = relationship("Experiment", back_populates="assignments")
    variant = relationship("ExperimentVariant", back_populates="assignments")

    def __repr__(self):
        return f"<ExperimentAssignment(id={self.assignment_id}, variant_id={self.variant_id})>"


class ExperimentMetric(Base):
    """실험 메트릭 기록"""

    __tablename__ = "experiment_metrics"
    __table_args__ = {"schema": "core"}

    metric_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    experiment_id = Column(PGUUID(as_uuid=True), ForeignKey("core.experiments.experiment_id", ondelete="CASCADE"), nullable=False)
    variant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.experiment_variants.variant_id", ondelete="CASCADE"), nullable=False)

    metric_name = Column(String(100), nullable=False)  # success_rate, response_time, feedback_score, etc.
    metric_value = Column(Float, nullable=False)

    # 관련 실행 정보
    execution_id = Column(PGUUID(as_uuid=True), ForeignKey("core.judgment_executions.execution_id", ondelete="SET NULL"), nullable=True)
    context_data = Column(JSONB, default={})  # 추가 컨텍스트

    recorded_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    experiment = relationship("Experiment", back_populates="metrics")
    variant = relationship("ExperimentVariant", back_populates="metrics")

    def __repr__(self):
        return f"<ExperimentMetric(id={self.metric_id}, name='{self.metric_name}', value={self.metric_value})>"


# ========== ERP/MES 통합 모델 ==========


class ErpMesData(Base):
    """ERP/MES 데이터 (JSONB 기반 유연한 스키마)

    문서 참조: A-2-4 DATA-REQ-020
    - 확장 가능한 메타데이터는 JSONB 컬럼으로 저장
    - 스키마 변경 없이 다양한 기업의 데이터 수용 가능
    """

    __tablename__ = "erp_mes_data"
    __table_args__ = {"schema": "core"}

    data_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)

    # 소스 시스템 정보
    source_type = Column(String(20), nullable=False)  # 'erp' | 'mes'
    source_system = Column(String(100), nullable=False)  # 'sap', 'oracle', 'custom_erp', etc.

    # 레코드 분류
    record_type = Column(String(100), nullable=False)  # 'production_order', 'inventory', 'bom', 'work_order', etc.
    external_id = Column(String(255), nullable=True)  # 원본 시스템의 ID

    # 원본 데이터 (JSONB) - 기업마다 다른 스키마 수용
    raw_data = Column(JSONB, nullable=False, default={})

    # 정규화된 공통 필드 (BI 쿼리 최적화용)
    # - 자주 조회되는 필드만 별도 컬럼으로 추출
    normalized_quantity = Column(Float, nullable=True)  # 수량 (공통 필드)
    normalized_status = Column(String(50), nullable=True)  # 상태 (공통 필드)
    normalized_timestamp = Column(DateTime, nullable=True)  # 기준 시간 (공통 필드)

    # 메타데이터
    sync_status = Column(String(50), default="synced")  # synced, pending, error
    sync_error = Column(Text, nullable=True)
    synced_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ErpMesData(id={self.data_id}, source={self.source_type}/{self.source_system}, type='{self.record_type}')>"


class FieldMapping(Base):
    """필드 매핑 설정 (테넌트별 ERP/MES 필드 → 정규화 필드 매핑)

    기업마다 다른 ERP/MES 필드명을 정규화된 공통 필드로 매핑
    예: SAP의 'MENGE' → normalized_quantity
        Oracle의 'QTY' → normalized_quantity
    """

    __tablename__ = "field_mappings"
    __table_args__ = {"schema": "core"}

    mapping_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)

    # 소스 정보
    source_type = Column(String(20), nullable=False)  # 'erp' | 'mes'
    source_system = Column(String(100), nullable=False)  # 'sap', 'oracle', etc.
    record_type = Column(String(100), nullable=False)  # 'production_order', 'inventory', etc.

    # 매핑 정보
    source_field = Column(String(255), nullable=False)  # 원본 필드명 (예: 'MENGE', 'material.quantity')
    target_field = Column(String(255), nullable=False)  # 대상 필드명 (예: 'normalized_quantity', 'custom.qty')

    # 변환 규칙 (선택적)
    transform_type = Column(String(50), nullable=True)  # 'direct', 'multiply', 'date_format', 'lookup', etc.
    transform_config = Column(JSONB, default={})  # 변환 설정 (예: {"multiplier": 1000})

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<FieldMapping(id={self.mapping_id}, {self.source_field} → {self.target_field})>"


class DataSource(Base):
    """데이터 소스 연결 설정 (테넌트별 ERP/MES 연결 정보)

    문서 참조: B-1-3 Native DB Connector Integration
    - REST API, SOAP, DB Direct 연결 지원
    """

    __tablename__ = "data_sources"
    __table_args__ = {"schema": "core"}

    source_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # 소스 정보
    source_type = Column(String(20), nullable=False)  # 'erp' | 'mes'
    source_system = Column(String(100), nullable=False)  # 'sap', 'oracle', 'custom', etc.

    # 연결 방식
    connection_type = Column(String(50), nullable=False)  # 'rest_api', 'soap', 'db_direct', 'file'
    connection_config = Column(JSONB, default={})  # 연결 설정 (암호화 필요)
    # 예: {"base_url": "https://...", "auth_type": "oauth2", "client_id": "..."}

    # 동기화 설정
    sync_enabled = Column(Boolean, default=True)
    sync_interval_minutes = Column(Integer, default=60)  # 동기화 주기 (분)
    last_sync_at = Column(DateTime, nullable=True)
    last_sync_status = Column(String(50), nullable=True)  # success, error
    last_sync_error = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<DataSource(id={self.source_id}, name='{self.name}', type={self.source_type}/{self.source_system})>"
