"""
Core Schema ORM Models
테넌트, 사용자, 룰셋, 워크플로, 센서 데이터 등

B-3-1 Core Schema Design 스펙 기반 구현
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
    Numeric,
    LargeBinary,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB, INET, ARRAY
from sqlalchemy.orm import relationship

from app.database import Base


class Tenant(Base):
    """테넌트 (멀티테넌트 지원)

    B-3-1 스펙 섹션 2.1: 멀티테넌트 격리 기준 테이블
    """

    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint(
            "subscription_plan IN ('trial', 'standard', 'enterprise', 'custom')",
            name="ck_tenants_subscription_plan"
        ),
        CheckConstraint(
            "status IN ('active', 'suspended', 'deleted')",
            name="ck_tenants_status"
        ),
        {"schema": "core", "extend_existing": True}
    )

    tenant_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False, unique=True)
    slug = Column(String(100), unique=True, nullable=False)  # display_name 역할
    settings = Column(JSONB, default={}, nullable=False)

    # B-3-1 스펙 추가 컬럼
    subscription_plan = Column(String(20), default="standard", nullable=False)
    max_users = Column(Integer, default=10, nullable=False)
    max_workflows = Column(Integer, default=50, nullable=False)
    max_judgments_per_day = Column(Integer, default=10000, nullable=False)
    status = Column(String(20), default="active", nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    rulesets = relationship("Ruleset", back_populates="tenant", cascade="all, delete-orphan")
    workflows = relationship("Workflow", back_populates="tenant", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Tenant(id={self.tenant_id}, name='{self.name}')>"


class User(Base):
    """사용자

    B-3-1 스펙 섹션 2.2: 사용자 인증 및 권한 관리
    RBAC 역할: admin(전체), approver(승인), operator(실행), viewer(조회)
    """

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'approver', 'operator', 'viewer', 'user')",
            name="ck_users_role"
        ),
        CheckConstraint(
            "status IN ('active', 'inactive', 'locked')",
            name="ck_users_status"
        ),
        UniqueConstraint('tenant_id', 'email', name='uq_users_tenant_email'),
        UniqueConstraint('tenant_id', 'username', name='uq_users_tenant_username'),
        {"schema": "core", "extend_existing": True}
    )

    user_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    username = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=True)  # OAuth 사용자는 비밀번호 없음
    role = Column(String(50), default="user", nullable=False)  # admin, approver, operator, viewer, user

    # B-3-1 스펙 추가 컬럼
    permissions = Column(ARRAY(Text), default=[], nullable=False)  # RBAC 권한 배열
    user_metadata = Column("metadata", JSONB, default={}, nullable=False)  # 추가 메타데이터 (metadata는 예약어)
    status = Column(String(20), default="active", nullable=False)

    is_active = Column(Boolean, default=True)  # 호환성 유지
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)  # DB column: last_login

    # OAuth 관련 필드
    oauth_provider = Column(String(50), nullable=True)
    oauth_provider_id = Column(String(255), nullable=True)
    profile_image_url = Column(String(500), nullable=True)
    display_name = Column(String(255), nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="users")

    def __repr__(self):
        return f"<User(id={self.user_id}, username='{self.username}')>"


class Ruleset(Base):
    """룰셋 (Rhai 스크립트 기반 규칙)

    B-3-1 스펙 섹션 5.1: 룰 그룹 정의 (KPI별 룰 모음)
    """

    __tablename__ = "rulesets"
    __table_args__ = (
        CheckConstraint(
            "category IN ('quality', 'production', 'equipment', 'inventory', 'safety')",
            name="ck_rulesets_category"
        ),
        UniqueConstraint('tenant_id', 'name', name='uq_rulesets_tenant_name'),
        {"schema": "core", "extend_existing": True}
    )

    ruleset_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    rhai_script = Column("rhai_code", Text, nullable=False)  # DB column: rhai_code
    version = Column(String(50), default="1.0.0")
    is_active = Column(Boolean, default=False, nullable=False)

    # B-3-1 스펙 추가 컬럼
    target_kpi = Column(String(100), nullable=True)  # defect_rate, oee, cycle_time, inventory_cov 등
    category = Column(String(50), nullable=True)  # quality, production, equipment, inventory, safety
    priority = Column(Integer, default=100, nullable=False)
    ruleset_metadata = Column("metadata", JSONB, default={}, nullable=False)

    created_by = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    tenant = relationship("Tenant", back_populates="rulesets")
    versions = relationship("RulesetVersion", back_populates="ruleset", cascade="all, delete-orphan", order_by="desc(RulesetVersion.version_number)")
    scripts = relationship("RuleScript", back_populates="ruleset", cascade="all, delete-orphan")
    deployments = relationship("RuleDeployment", back_populates="ruleset", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Ruleset(id={self.ruleset_id}, name='{self.name}')>"


class RulesetVersion(Base):
    """룰셋 버전 히스토리"""

    __tablename__ = "ruleset_versions"
    __table_args__ = {"schema": "core", "extend_existing": True}

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
    """워크플로 (JSON DSL 기반)

    B-3-1 스펙 섹션 3.1: 판단 워크플로우 DSL 정의 및 버전 관리
    """

    __tablename__ = "workflows"
    __table_args__ = (
        UniqueConstraint('tenant_id', 'name', 'version', name='uq_workflows_tenant_name_version'),
        {"schema": "core", "extend_existing": True}
    )

    workflow_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    dsl_definition = Column("dsl_json", JSONB, nullable=False)  # JSON DSL (DB column: dsl_json)
    version = Column(Integer, default=1, nullable=False)  # B-3-1: version은 int
    is_active = Column(Boolean, default=False, nullable=False)

    # B-3-1 스펙 추가 컬럼
    dsl_digest = Column(String(64), nullable=True)  # SHA256(dsl_json) - 변경 추적용
    trigger_config = Column(JSONB, nullable=True)  # {type: schedule|event|webhook, cron, event_filter}
    timeout_seconds = Column(Integer, default=300, nullable=False)
    max_retry = Column(Integer, default=3, nullable=False)
    tags = Column(ARRAY(Text), default=[], nullable=False)
    workflow_metadata = Column("metadata", JSONB, default={}, nullable=False)

    created_by = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    activated_at = Column(DateTime, nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="workflows")
    instances = relationship("WorkflowInstance", back_populates="workflow", passive_deletes=True)
    steps = relationship("WorkflowStep", back_populates="workflow", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Workflow(id={self.workflow_id}, name='{self.name}')>"


class WorkflowInstance(Base):
    """워크플로 실행 인스턴스

    B-3-1 스펙 섹션 3.3: 워크플로우 실행 이력 및 상태 추적
    상태: pending, running, waiting, paused, completed, failed, cancelled, timeout
    """

    __tablename__ = "workflow_instances"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'waiting', 'paused', 'completed', 'failed', 'cancelled', 'timeout')",
            name="ck_workflow_instances_status"
        ),
        CheckConstraint(
            "trigger_type IN ('manual', 'schedule', 'event', 'webhook', 'api')",
            name="ck_workflow_instances_trigger_type"
        ),
        {"schema": "core", "extend_existing": True}
    )

    instance_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    workflow_id = Column(PGUUID(as_uuid=True), ForeignKey("core.workflows.workflow_id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), default="pending", nullable=False)

    # B-3-1 스펙 추가 컬럼
    trigger_type = Column(String(20), default="manual", nullable=False)
    triggered_by = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id"), nullable=True)
    input_context = Column("input_data", JSONB, default={}, nullable=False)  # input_context로 이름 변경
    runtime_context = Column("output_data", JSONB, default={}, nullable=False)  # runtime_context로 이름 변경
    checkpoint_data = Column(JSONB, nullable=True)  # 장기 실행 워크플로우 체크포인트
    current_step_id = Column(PGUUID(as_uuid=True), nullable=True)  # FK는 나중에 추가

    last_error = Column("error_message", Text, nullable=True)
    error_code = Column(String(50), nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)

    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column("completed_at", DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)

    trace_id = Column(String(64), nullable=False, default=lambda: uuid4().hex)
    parent_instance_id = Column(PGUUID(as_uuid=True), ForeignKey("core.workflow_instances.instance_id"), nullable=True)
    instance_metadata = Column("metadata", JSONB, default={}, nullable=False)

    # Relationships
    workflow = relationship("Workflow", back_populates="instances")
    parent_instance = relationship("WorkflowInstance", remote_side="WorkflowInstance.instance_id")
    execution_logs = relationship("WorkflowExecutionLog", back_populates="instance", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<WorkflowInstance(id={self.instance_id}, status='{self.status}')>"


class JudgmentExecution(Base):
    """판단 실행 로그 (Workflow/Ruleset 실행 결과)

    B-3-1 스펙 섹션 4.1: AI 판단 실행 이력 및 결과 저장 (이벤트 소싱)
    method_used: rule_only, llm_only, hybrid, cache
    result: normal, warning, critical, unknown
    """

    __tablename__ = "judgment_executions"
    __table_args__ = (
        CheckConstraint(
            "source IN ('workflow', 'api', 'manual', 'schedule')",
            name="ck_judgment_executions_source"
        ),
        CheckConstraint(
            "result IN ('normal', 'warning', 'critical', 'unknown')",
            name="ck_judgment_executions_result"
        ),
        CheckConstraint(
            "method_used IN ('rule_only', 'llm_only', 'hybrid', 'cache')",
            name="ck_judgment_executions_method"
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_judgment_executions_confidence"
        ),
        {"schema": "core", "extend_existing": True}
    )

    execution_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    workflow_instance_id = Column(PGUUID(as_uuid=True), ForeignKey("core.workflow_instances.instance_id"), nullable=True)
    workflow_id = Column(PGUUID(as_uuid=True), ForeignKey("core.workflows.workflow_id", ondelete="SET NULL"), nullable=True)

    # B-3-1 스펙 추가 컬럼
    source = Column(String(20), default="api", nullable=False)
    input_data = Column(JSONB, nullable=False)
    result = Column(String(20), default="unknown", nullable=False)  # normal, warning, critical, unknown
    confidence = Column(Float, nullable=True)
    method_used = Column(String(20), nullable=False)  # rule_only, llm_only, hybrid, cache

    explanation = Column(Text, nullable=True)
    recommended_actions = Column(JSONB, nullable=True)
    rule_trace = Column(JSONB, nullable=True)  # 룰 실행 추적 정보
    llm_metadata = Column(JSONB, nullable=True)  # LLM 호출 메타데이터
    evidence = Column(JSONB, nullable=True)  # 근거 데이터 (data_refs, urls, charts)
    feature_importance = Column(JSONB, nullable=True)

    cache_hit = Column(Boolean, default=False, nullable=False)
    cache_key = Column(String(100), nullable=True)

    latency_ms = Column("execution_time_ms", Integer, nullable=True)
    created_at = Column("executed_at", DateTime, default=datetime.utcnow, nullable=False)
    created_by = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id"), nullable=True)
    trace_id = Column(String(64), nullable=False, default=lambda: uuid4().hex)
    execution_metadata = Column("metadata", JSONB, default={}, nullable=False)

    # Relationships
    workflow = relationship("Workflow", backref="executions")
    workflow_instance = relationship("WorkflowInstance")
    feedbacks = relationship("FeedbackLog", back_populates="judgment_execution")

    def __repr__(self):
        return f"<JudgmentExecution(id={self.execution_id}, result={self.result}, confidence={self.confidence})>"


class SensorData(Base):
    """센서 데이터 (파티션 테이블)"""

    __tablename__ = "sensor_data"
    __table_args__ = {"schema": "core", "extend_existing": True}

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
    """피드백 로그 (Learning System용)

    B-3-1 스펙 섹션 6.1: 판단 결과에 대한 사용자 피드백 수집
    feedback_type: correct, incorrect, partial, helpful, not_helpful
    """

    __tablename__ = "feedback_logs"
    __table_args__ = (
        CheckConstraint(
            "feedback_type IN ('correct', 'incorrect', 'partial', 'helpful', 'not_helpful', 'positive', 'negative', 'correction')",
            name="ck_feedbacks_type"
        ),
        CheckConstraint(
            "rating >= 1 AND rating <= 5",
            name="ck_feedbacks_rating"
        ),
        CheckConstraint(
            "corrected_result IN ('normal', 'warning', 'critical')",
            name="ck_feedbacks_corrected_result"
        ),
        {"schema": "core", "extend_existing": True}
    )

    feedback_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    execution_id = Column("judgment_execution_id", PGUUID(as_uuid=True), ForeignKey("core.judgment_executions.execution_id", ondelete="SET NULL"), nullable=True)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id"), nullable=True)

    feedback_type = Column(String(50), nullable=False)  # correct, incorrect, partial, helpful, not_helpful
    rating = Column(Integer, nullable=True)  # 1-5 점수
    comment = Column("feedback_text", Text, nullable=True)  # 사용자 피드백 코멘트
    corrected_result = Column(String(20), nullable=True)  # normal, warning, critical

    # 기존 호환성 유지
    original_output = Column(JSONB, nullable=True)
    corrected_output = Column(JSONB, nullable=True)
    context_data = Column(JSONB, default={})
    is_processed = Column(Boolean, default=False)
    processed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    judgment_execution = relationship("JudgmentExecution", back_populates="feedbacks")

    def __repr__(self):
        return f"<FeedbackLog(id={self.feedback_id}, type='{self.feedback_type}')>"


class ProposedRule(Base):
    """제안된 규칙 (Learning System이 생성)"""

    __tablename__ = "proposed_rules"
    __table_args__ = {"schema": "core", "extend_existing": True}

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
    __table_args__ = {"schema": "core", "extend_existing": True}

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
    __table_args__ = {"schema": "core", "extend_existing": True}

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
    __table_args__ = {"schema": "core", "extend_existing": True}

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
    __table_args__ = {"schema": "core", "extend_existing": True}

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
    __table_args__ = {"schema": "core", "extend_existing": True}

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
    __table_args__ = {"schema": "core", "extend_existing": True}

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
    __table_args__ = {"schema": "core", "extend_existing": True}

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


# ========== API Key 관리 모델 ==========


class ApiKey(Base):
    """API Key 관리 (외부 시스템 연동용)

    - 테넌트별 API Key 발급/관리
    - Key 해시 저장 (보안)
    - 만료일 및 권한 스코프 지원
    """

    __tablename__ = "api_keys"
    __table_args__ = {"schema": "core", "extend_existing": True}

    key_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id", ondelete="CASCADE"), nullable=False)

    # Key 정보
    name = Column(String(255), nullable=False)  # Key 이름 (예: "Production API", "Dev Testing")
    description = Column(Text, nullable=True)
    key_prefix = Column(String(10), nullable=False)  # Key 앞 8자 (식별용, 예: "tfk_abc1")
    key_hash = Column(String(255), nullable=False)  # SHA-256 해시 (전체 Key는 발급 시에만 표시)

    # 권한 스코프
    scopes = Column(JSONB, default=["read"])  # ["read", "write", "admin", "sensors", "workflows", ...]

    # 만료 및 상태
    expires_at = Column(DateTime, nullable=True)  # null = 만료 없음
    last_used_at = Column(DateTime, nullable=True)
    last_used_ip = Column(String(45), nullable=True)  # IPv6 지원
    usage_count = Column(Integer, default=0)

    is_active = Column(Boolean, default=True)
    revoked_at = Column(DateTime, nullable=True)
    revoked_reason = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    user = relationship("User")

    def __repr__(self):
        return f"<ApiKey(id={self.key_id}, name='{self.name}', prefix='{self.key_prefix}')>"


# ========== B-3-1 스펙 신규 테이블 ==========


class WorkflowStep(Base):
    """워크플로우 단계 (DSL 노드 정규화)

    B-3-1 스펙 섹션 3.2: 워크플로우 DSL의 노드를 정규화된 단계로 저장
    노드 타입: DATA, BI, JUDGMENT, MCP, ACTION, APPROVAL, WAIT, SWITCH, PARALLEL, COMPENSATION, DEPLOY, ROLLBACK, SIMULATE
    """

    __tablename__ = "workflow_steps"
    __table_args__ = (
        CheckConstraint(
            "node_type IN ('DATA', 'BI', 'JUDGMENT', 'MCP', 'ACTION', 'APPROVAL', 'WAIT', 'SWITCH', 'PARALLEL', 'COMPENSATION', 'DEPLOY', 'ROLLBACK', 'SIMULATE')",
            name="ck_workflow_steps_node_type"
        ),
        UniqueConstraint('workflow_id', 'node_id', name='uq_workflow_steps_workflow_node'),
        UniqueConstraint('workflow_id', 'step_order', name='uq_workflow_steps_workflow_order'),
        {"schema": "core", "extend_existing": True}
    )

    step_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    workflow_id = Column(PGUUID(as_uuid=True), ForeignKey("core.workflows.workflow_id", ondelete="CASCADE"), nullable=False)

    step_order = Column(Integer, nullable=False)
    node_id = Column(String(100), nullable=False)  # DSL에서 정의한 노드 ID
    node_type = Column(String(20), nullable=False)  # 13가지 노드 타입
    config = Column(JSONB, nullable=False, default={})  # 노드 설정

    timeout_seconds = Column(Integer, default=60, nullable=False)
    retry_policy = Column(JSONB, nullable=True)  # {max_attempts, backoff_strategy, ...}

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    workflow = relationship("Workflow", back_populates="steps")

    def __repr__(self):
        return f"<WorkflowStep(id={self.step_id}, node_id='{self.node_id}', type='{self.node_type}')>"


class WorkflowExecutionLog(Base):
    """워크플로우 단계별 실행 로그

    B-3-1 스펙 섹션 3.4: 워크플로우 단계별 실행 로그
    """

    __tablename__ = "workflow_execution_logs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'SKIPPED', 'RETRYING')",
            name="ck_workflow_execution_logs_status"
        ),
        {"schema": "core", "extend_existing": True}
    )

    log_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    instance_id = Column(PGUUID(as_uuid=True), ForeignKey("core.workflow_instances.instance_id", ondelete="CASCADE"), nullable=False)
    step_id = Column(PGUUID(as_uuid=True), ForeignKey("core.workflow_steps.step_id"), nullable=False)

    node_id = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False)  # PENDING, RUNNING, COMPLETED, FAILED, SKIPPED, RETRYING

    input_data = Column(JSONB, nullable=True)
    output_data = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True)

    retry_attempt = Column(Integer, default=0, nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)

    log_metadata = Column("metadata", JSONB, default={}, nullable=False)

    # Relationships
    instance = relationship("WorkflowInstance", back_populates="execution_logs")
    step = relationship("WorkflowStep")

    def __repr__(self):
        return f"<WorkflowExecutionLog(id={self.log_id}, node='{self.node_id}', status='{self.status}')>"


class JudgmentCache(Base):
    """판단 캐시

    B-3-1 스펙 섹션 4.2: 동일 입력에 대한 판단 결과 캐시
    cache_key 형식: judgment:{workflow_id}:{sha256(input_data)}
    """

    __tablename__ = "judgment_cache"
    __table_args__ = (
        UniqueConstraint('tenant_id', 'cache_key', name='uq_judgment_cache_tenant_key'),
        {"schema": "core", "extend_existing": True}
    )

    cache_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)

    cache_key = Column(String(200), nullable=False)
    judgment_execution_id = Column(PGUUID(as_uuid=True), ForeignKey("core.judgment_executions.execution_id"), nullable=False)
    input_hash = Column(String(64), nullable=False)  # SHA256 hash

    result = Column(String(20), nullable=False)  # normal, warning, critical
    confidence = Column(Float, nullable=True)

    ttl_seconds = Column(Integer, default=3600, nullable=False)
    hit_count = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    last_hit_at = Column(DateTime, nullable=True)

    # Relationships
    judgment_execution = relationship("JudgmentExecution")

    def __repr__(self):
        return f"<JudgmentCache(key='{self.cache_key}', result='{self.result}', hits={self.hit_count})>"


class RuleScript(Base):
    """Rhai 룰 스크립트 버전 관리

    B-3-1 스펙 섹션 5.2: Rhai 룰 스크립트 버전 관리
    """

    __tablename__ = "rule_scripts"
    __table_args__ = (
        CheckConstraint(
            "compile_status IN ('pending', 'compiled', 'failed')",
            name="ck_rule_scripts_compile_status"
        ),
        UniqueConstraint('ruleset_id', 'version', name='uq_rule_scripts_ruleset_version'),
        {"schema": "core", "extend_existing": True}
    )

    script_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    ruleset_id = Column(PGUUID(as_uuid=True), ForeignKey("core.rulesets.ruleset_id", ondelete="CASCADE"), nullable=False)

    version = Column(Integer, nullable=False)
    language = Column(String(20), default="rhai", nullable=False)
    script = Column(Text, nullable=False)  # Rhai 스크립트 전체 텍스트
    script_hash = Column(String(64), nullable=False)  # SHA256 hash

    compile_status = Column(String(20), default="pending", nullable=False)
    compile_error = Column(Text, nullable=True)
    test_coverage = Column(Float, nullable=True)  # 0-1

    created_by = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    ruleset = relationship("Ruleset", back_populates="scripts")

    def __repr__(self):
        return f"<RuleScript(ruleset_id={self.ruleset_id}, version={self.version}, status='{self.compile_status}')>"


class RuleDeployment(Base):
    """룰 배포 이력

    B-3-1 스펙 섹션 5.3: 룰 배포 및 카나리 릴리즈 추적
    """

    __tablename__ = "rule_deployments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'canary', 'active', 'rolled_back', 'deprecated')",
            name="ck_rule_deployments_status"
        ),
        CheckConstraint(
            "canary_pct >= 0 AND canary_pct <= 1",
            name="ck_rule_deployments_canary_pct"
        ),
        {"schema": "core", "extend_existing": True}
    )

    deployment_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    ruleset_id = Column(PGUUID(as_uuid=True), ForeignKey("core.rulesets.ruleset_id", ondelete="CASCADE"), nullable=False)

    version = Column(Integer, nullable=False)
    status = Column(String(20), default="draft", nullable=False)

    canary_pct = Column(Float, nullable=True)  # 0.1 = 10% 트래픽
    canary_target_filter = Column(JSONB, nullable=True)  # {line_codes: [...], shift: "..."}
    rollback_to = Column(Integer, nullable=True)  # 롤백 대상 버전

    changelog = Column(Text, nullable=False)
    approver_id = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    deployed_at = Column(DateTime, nullable=True)
    rolled_back_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    deployment_metadata = Column("metadata", JSONB, default={}, nullable=False)

    # Relationships
    ruleset = relationship("Ruleset", back_populates="deployments")

    def __repr__(self):
        return f"<RuleDeployment(ruleset_id={self.ruleset_id}, version={self.version}, status='{self.status}')>"


class RuleConflict(Base):
    """룰 충돌 감지

    B-3-1 스펙 섹션 5.4: 룰 간 충돌 자동 감지 및 해결 이력
    """

    __tablename__ = "rule_conflicts"
    __table_args__ = (
        CheckConstraint(
            "conflict_type IN ('output_conflict', 'condition_overlap', 'circular_dependency')",
            name="ck_rule_conflicts_type"
        ),
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_rule_conflicts_severity"
        ),
        CheckConstraint(
            "resolution_status IN ('unresolved', 'investigating', 'resolved', 'accepted')",
            name="ck_rule_conflicts_resolution_status"
        ),
        {"schema": "core", "extend_existing": True}
    )

    conflict_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    ruleset_id = Column(PGUUID(as_uuid=True), ForeignKey("core.rulesets.ruleset_id", ondelete="CASCADE"), nullable=False)

    rule_version_1 = Column(Integer, nullable=False)
    rule_version_2 = Column(Integer, nullable=False)
    conflict_type = Column(String(30), nullable=False)  # output_conflict, condition_overlap, circular_dependency
    description = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False)  # low, medium, high, critical

    resolution_status = Column(String(20), default="unresolved", nullable=False)
    resolution_note = Column(Text, nullable=True)

    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id"), nullable=True)

    def __repr__(self):
        return f"<RuleConflict(ruleset_id={self.ruleset_id}, type='{self.conflict_type}', status='{self.resolution_status}')>"


class LearningSample(Base):
    """학습 샘플

    B-3-1 스펙 섹션 6.2: LLM/ML 학습용 샘플 자동 수집
    source: feedback, auto, manual, import
    """

    __tablename__ = "learning_samples"
    __table_args__ = (
        CheckConstraint(
            "source IN ('feedback', 'auto', 'manual', 'import')",
            name="ck_learning_samples_source"
        ),
        CheckConstraint(
            "quality_score >= 0 AND quality_score <= 1",
            name="ck_learning_samples_quality_score"
        ),
        {"schema": "core", "extend_existing": True}
    )

    sample_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    judgment_execution_id = Column(PGUUID(as_uuid=True), ForeignKey("core.judgment_executions.execution_id"), nullable=True)

    input_features = Column(JSONB, nullable=False)
    label = Column(JSONB, nullable=False)  # {result, confidence, explanation, ...}
    source = Column(String(20), nullable=False)  # feedback, auto, manual, import

    quality_score = Column(Float, nullable=True)  # 0-1
    is_validated = Column(Boolean, default=False, nullable=False)
    validated_by = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id"), nullable=True)
    validated_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    sample_metadata = Column("metadata", JSONB, default={}, nullable=False)

    def __repr__(self):
        return f"<LearningSample(id={self.sample_id}, source='{self.source}', validated={self.is_validated})>"


class AutoRuleCandidate(Base):
    """자동 룰 후보

    B-3-1 스펙 섹션 6.3: LLM이 생성한 룰 후보 저장 및 승인 관리
    """

    __tablename__ = "auto_rule_candidates"
    __table_args__ = (
        CheckConstraint(
            "generation_method IN ('llm', 'pattern_mining', 'ensemble')",
            name="ck_auto_rule_candidates_method"
        ),
        CheckConstraint(
            "approval_status IN ('pending', 'approved', 'rejected', 'testing')",
            name="ck_auto_rule_candidates_status"
        ),
        {"schema": "core", "extend_existing": True}
    )

    candidate_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    ruleset_id = Column(PGUUID(as_uuid=True), ForeignKey("core.rulesets.ruleset_id"), nullable=True)

    generated_rule = Column(Text, nullable=False)  # Rhai 코드
    rule_language = Column(String(20), default="rhai", nullable=False)
    generation_method = Column(String(20), nullable=False)  # llm, pattern_mining, ensemble

    # 성능 지표
    coverage = Column(Float, nullable=True)  # 0-1
    precision = Column(Float, nullable=True)  # 0-1
    recall = Column(Float, nullable=True)  # 0-1
    f1_score = Column(Float, nullable=True)
    conflict_with = Column(ARRAY(Text), default=[], nullable=False)

    # 승인 관리
    is_approved = Column(Boolean, default=False, nullable=False)
    approval_status = Column(String(20), default="pending", nullable=False)
    approver_id = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    test_results = Column(JSONB, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    candidate_metadata = Column("metadata", JSONB, default={}, nullable=False)

    def __repr__(self):
        return f"<AutoRuleCandidate(id={self.candidate_id}, status='{self.approval_status}')>"


class ModelTrainingJob(Base):
    """모델 학습 작업

    B-3-1 스펙 섹션 6.4: 주기적 모델 재학습 작업 추적
    """

    __tablename__ = "model_training_jobs"
    __table_args__ = (
        CheckConstraint(
            "job_type IN ('rule_learning', 'llm_finetuning', 'embedding_update')",
            name="ck_model_training_jobs_type"
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_model_training_jobs_status"
        ),
        {"schema": "core", "extend_existing": True}
    )

    job_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)

    job_type = Column(String(30), nullable=False)  # rule_learning, llm_finetuning, embedding_update
    status = Column(String(20), default="pending", nullable=False)

    dataset_size = Column(Integer, nullable=True)
    training_config = Column(JSONB, nullable=False)
    metrics = Column(JSONB, nullable=True)  # 학습 결과 메트릭
    model_artifact_url = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)

    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    triggered_by = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<ModelTrainingJob(id={self.job_id}, type='{self.job_type}', status='{self.status}')>"


class PromptTemplate(Base):
    """프롬프트 템플릿

    B-3-1 스펙 섹션 7.1: LLM 프롬프트 버전 관리 (B-6 참조)
    """

    __tablename__ = "prompt_templates"
    __table_args__ = (
        CheckConstraint(
            "template_type IN ('judgment', 'chat', 'reasoning', 'extraction')",
            name="ck_prompt_templates_type"
        ),
        UniqueConstraint('tenant_id', 'name', 'version', name='uq_prompt_templates_tenant_name_version'),
        {"schema": "core", "extend_existing": True}
    )

    template_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)

    name = Column(String(255), nullable=False)
    purpose = Column(Text, nullable=False)
    version = Column(Integer, nullable=False)
    template_type = Column(String(20), nullable=False)  # judgment, chat, reasoning, extraction

    model_config = Column(JSONB, nullable=False)  # {model, temperature, max_tokens, ...}
    variables = Column(JSONB, nullable=False)  # {required: [], optional: [], defaults: {}}

    is_active = Column(Boolean, default=False, nullable=False)
    a_b_test_group = Column(String(20), nullable=True)  # control, variant_a, variant_b

    created_by = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    bodies = relationship("PromptTemplateBody", back_populates="template", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PromptTemplate(id={self.template_id}, name='{self.name}', version={self.version})>"


class PromptTemplateBody(Base):
    """프롬프트 본문 (다국어)

    B-3-1 스펙 섹션 7.2: 다국어 프롬프트 본문 저장
    """

    __tablename__ = "prompt_template_bodies"
    __table_args__ = (
        UniqueConstraint('template_id', 'locale', name='uq_prompt_template_bodies_template_locale'),
        {"schema": "core", "extend_existing": True}
    )

    body_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    template_id = Column(PGUUID(as_uuid=True), ForeignKey("core.prompt_templates.template_id", ondelete="CASCADE"), nullable=False)

    locale = Column(String(10), default="ko-KR", nullable=False)
    system_prompt = Column(Text, nullable=False)
    user_prompt_template = Column(Text, nullable=False)
    few_shot_examples = Column(JSONB, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    template = relationship("PromptTemplate", back_populates="bodies")

    def __repr__(self):
        return f"<PromptTemplateBody(template_id={self.template_id}, locale='{self.locale}')>"


class LlmCall(Base):
    """LLM 호출 로그

    B-3-1 스펙 섹션 7.3: LLM API 호출 추적 및 비용 관리
    """

    __tablename__ = "llm_calls"
    __table_args__ = (
        CheckConstraint(
            "call_type IN ('judgment', 'chat', 'reasoning', 'embedding')",
            name="ck_llm_calls_type"
        ),
        {"schema": "core", "extend_existing": True}
    )

    call_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    judgment_execution_id = Column(PGUUID(as_uuid=True), ForeignKey("core.judgment_executions.execution_id"), nullable=True)
    prompt_template_id = Column(PGUUID(as_uuid=True), ForeignKey("core.prompt_templates.template_id"), nullable=True)

    call_type = Column(String(20), nullable=False)  # judgment, chat, reasoning, embedding
    model = Column(String(100), nullable=False)

    prompt_summary = Column(Text, nullable=True)
    prompt_tokens = Column(Integer, nullable=False)
    completion_tokens = Column(Integer, nullable=False)
    total_tokens = Column(Integer, nullable=False)
    cost_estimate_usd = Column(Numeric(10, 6), nullable=True)

    latency_ms = Column(Integer, nullable=True)
    success = Column(Boolean, default=True, nullable=False)
    validation_error = Column(Boolean, default=False, nullable=False)
    error_message = Column(Text, nullable=True)
    response_summary = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    trace_id = Column(String(64), nullable=True)
    call_metadata = Column("metadata", JSONB, default={}, nullable=False)

    def __repr__(self):
        return f"<LlmCall(id={self.call_id}, model='{self.model}', tokens={self.total_tokens})>"


class ChatSession(Base):
    """채팅 세션

    B-3-1 스펙 섹션 8.1: 사용자 채팅 세션 관리
    """

    __tablename__ = "chat_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'archived', 'deleted')",
            name="ck_chat_sessions_status"
        ),
        {"schema": "core", "extend_existing": True}
    )

    session_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id", ondelete="CASCADE"), nullable=False)

    title = Column(String(255), default="New Chat", nullable=False)
    status = Column(String(20), default="active", nullable=False)  # active, archived, deleted
    context = Column(JSONB, default={}, nullable=False)  # 세션 컨텍스트

    message_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_message_at = Column(DateTime, nullable=True)

    # Relationships
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ChatSession(id={self.session_id}, title='{self.title}')>"


class ChatMessage(Base):
    """채팅 메시지

    B-3-1 스펙 섹션 8.2: 채팅 메시지 이력
    """

    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant', 'system')",
            name="ck_chat_messages_role"
        ),
        {"schema": "core", "extend_existing": True}
    )

    message_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(PGUUID(as_uuid=True), ForeignKey("core.chat_sessions.session_id", ondelete="CASCADE"), nullable=False)

    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    intent_log_id = Column(PGUUID(as_uuid=True), ForeignKey("core.intent_logs.log_id"), nullable=True)

    message_metadata = Column("metadata", JSONB, default={}, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    session = relationship("ChatSession", back_populates="messages")
    intent_log = relationship("IntentLog")

    def __repr__(self):
        return f"<ChatMessage(id={self.message_id}, role='{self.role}')>"


class IntentLog(Base):
    """의도 분석 로그

    B-3-1 스펙 섹션 8.3: 사용자 의도 분석 로그
    """

    __tablename__ = "intent_logs"
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_intent_logs_confidence"
        ),
        CheckConstraint(
            "feedback_score >= 1 AND feedback_score <= 5",
            name="ck_intent_logs_feedback_score"
        ),
        {"schema": "core", "extend_existing": True}
    )

    log_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id"), nullable=True)

    user_query = Column(Text, nullable=False)
    predicted_intent = Column(String(100), nullable=False)  # query_defect_rate, run_workflow, check_oee 등
    confidence = Column(Float, nullable=True)

    extracted_slots = Column(JSONB, nullable=True)  # {line_code, date_range, kpi, ...}
    feedback_score = Column(Integer, nullable=True)  # 1-5
    feedback_comment = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<IntentLog(id={self.log_id}, intent='{self.predicted_intent}')>"


class McpServer(Base):
    """MCP 서버

    B-3-1 스펙 섹션 9.2: MCP (Model Context Protocol) 서버 연동 설정
    """

    __tablename__ = "mcp_servers"
    __table_args__ = (
        CheckConstraint(
            "protocol IN ('stdio', 'sse', 'websocket')",
            name="ck_mcp_servers_protocol"
        ),
        CheckConstraint(
            "status IN ('active', 'inactive', 'error')",
            name="ck_mcp_servers_status"
        ),
        CheckConstraint(
            "circuit_breaker_state IN ('closed', 'open', 'half_open')",
            name="ck_mcp_servers_circuit_breaker"
        ),
        UniqueConstraint('tenant_id', 'name', name='uq_mcp_servers_tenant_name'),
        {"schema": "core", "extend_existing": True}
    )

    server_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)

    name = Column(String(255), nullable=False)
    endpoint = Column(String(500), nullable=False)
    protocol = Column(String(20), default="stdio", nullable=False)  # stdio, sse, websocket

    config = Column(JSONB, nullable=False, default={})
    auth_config = Column(JSONB, nullable=True)

    status = Column(String(20), default="inactive", nullable=False)
    last_health_check_at = Column(DateTime, nullable=True)
    circuit_breaker_state = Column(String(20), default="closed", nullable=False)
    fail_count = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    tools = relationship("McpTool", back_populates="server", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<McpServer(id={self.server_id}, name='{self.name}', status='{self.status}')>"


class McpTool(Base):
    """MCP 도구

    B-3-1 스펙 섹션 9.3: MCP 서버가 제공하는 도구 목록
    """

    __tablename__ = "mcp_tools"
    __table_args__ = (
        UniqueConstraint('mcp_server_id', 'tool_name', name='uq_mcp_tools_server_name'),
        {"schema": "core", "extend_existing": True}
    )

    tool_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    mcp_server_id = Column(PGUUID(as_uuid=True), ForeignKey("core.mcp_servers.server_id", ondelete="CASCADE"), nullable=False)

    tool_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    input_schema = Column(JSONB, nullable=False)
    output_schema = Column(JSONB, nullable=True)

    is_enabled = Column(Boolean, default=True, nullable=False)
    usage_count = Column(Integer, default=0, nullable=False)
    avg_latency_ms = Column(Integer, nullable=True)
    last_used_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    server = relationship("McpServer", back_populates="tools")

    def __repr__(self):
        return f"<McpTool(id={self.tool_id}, name='{self.tool_name}')>"


class McpCallLog(Base):
    """MCP 호출 로그

    B-3-1 스펙 섹션 9.4: MCP 도구 호출 로그
    """

    __tablename__ = "mcp_call_logs"
    __table_args__ = {"schema": "core", "extend_existing": True}

    call_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    mcp_tool_id = Column(PGUUID(as_uuid=True), ForeignKey("core.mcp_tools.tool_id", ondelete="CASCADE"), nullable=False)
    workflow_instance_id = Column(PGUUID(as_uuid=True), ForeignKey("core.workflow_instances.instance_id"), nullable=True)

    input_data = Column(JSONB, nullable=False)
    output_data = Column(JSONB, nullable=True)

    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    trace_id = Column(String(64), nullable=True)

    # Relationships
    tool = relationship("McpTool")
    workflow_instance = relationship("WorkflowInstance")

    def __repr__(self):
        return f"<McpCallLog(id={self.call_id}, success={self.success})>"


class DataConnector(Base):
    """데이터 커넥터

    B-3-1 스펙 섹션 9.1: ERP/MES 등 외부 시스템 연동 설정
    """

    __tablename__ = "data_connectors"
    __table_args__ = (
        CheckConstraint(
            "type IN ('postgres', 'mysql', 'mssql', 'oracle', 'rest_api', 'graphql', 'kafka')",
            name="ck_data_connectors_type"
        ),
        CheckConstraint(
            "status IN ('active', 'inactive', 'error')",
            name="ck_data_connectors_status"
        ),
        UniqueConstraint('tenant_id', 'name', name='uq_data_connectors_tenant_name'),
        {"schema": "core", "extend_existing": True}
    )

    connector_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)

    name = Column(String(255), nullable=False)
    type = Column(String(20), nullable=False)  # postgres, mysql, mssql, oracle, rest_api, graphql, kafka
    engine = Column(String(50), nullable=True)

    config = Column(JSONB, nullable=False)  # {host, port, database, ssl_enabled, connection_pool{}}
    credentials_encrypted = Column(LargeBinary, nullable=True)  # 암호화된 자격 증명

    status = Column(String(20), default="inactive", nullable=False)
    last_health_check_at = Column(DateTime, nullable=True)
    last_health_status = Column(String(255), nullable=True)

    created_by = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<DataConnector(id={self.connector_id}, name='{self.name}', type='{self.type}')>"


class AuditLog(Base):
    """감사 로그

    B-3-1 스펙 섹션 10.1: 모든 중요 작업 감사 추적
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('user', 'system', 'api', 'webhook')",
            name="ck_audit_logs_actor_type"
        ),
        {"schema": "core", "extend_existing": True}
    )

    log_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    actor_id = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id"), nullable=True)
    actor_type = Column(String(20), nullable=False)  # user, system, api, webhook

    action = Column(String(50), nullable=False)  # create, update, delete, execute, approve, deploy, rollback
    resource_type = Column(String(50), nullable=False)  # workflow, ruleset, user, ...
    resource_id = Column(String(100), nullable=True)

    before_state = Column(JSONB, nullable=True)
    after_state = Column(JSONB, nullable=True)
    diff = Column(JSONB, nullable=True)

    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    trace_id = Column(String(64), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<AuditLog(id={self.log_id}, action='{self.action}', resource='{self.resource_type}')>"
