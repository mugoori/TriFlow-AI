"""
RAG & AAS Schema ORM Models
RAG (Retrieval-Augmented Generation) 및 AAS (Asset Administration Shell) 모델

스펙 참조: B-3-3_RAG_AAS_Schema.md
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
    CheckConstraint,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB, ARRAY
from sqlalchemy.orm import relationship

from app.database import Base

# Note: pgvector 타입은 alembic migration에서 raw SQL로 처리
# SQLAlchemy에서는 String으로 선언하고 실제 DB에서는 vector(1536)으로 생성


# ========== RAG 문서 모델 ==========


class RAGDocument(Base):
    """RAG 문서 청크 (벡터 검색용)

    목적: 문서를 청크 단위로 저장하여 벡터 검색 지원
    청킹 전략: 500 토큰, 50 토큰 오버랩
    """

    __tablename__ = "rag_documents"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "source_type", "source_id", "chunk_index", "version",
            name="uq_rag_documents_chunk"
        ),
        CheckConstraint(
            "source_type IN ('manual', 'sop', 'wiki', 'faq', 'judgment_log', 'feedback', 'external_doc')",
            name="ck_rag_documents_source_type"
        ),
        Index("idx_rag_docs_tenant_active", "tenant_id", "is_active", postgresql_where="is_active = true"),
        Index("idx_rag_docs_source", "source_type", "source_id"),
        {"schema": "rag", "extend_existing": True},
    )

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)

    # 문서 소스 정보
    source_type = Column(String(50), nullable=False)  # manual, sop, wiki, faq, judgment_log, feedback, external_doc
    source_id = Column(String(255), nullable=False)  # 원본 문서 ID
    parent_id = Column(PGUUID(as_uuid=True), ForeignKey("rag.rag_documents.id", ondelete="SET NULL"), nullable=True)

    # 문서 구조
    title = Column(String(500), nullable=False)
    section = Column(String(255), nullable=True)
    subsection = Column(String(255), nullable=True)

    # 청크 정보
    chunk_index = Column(Integer, nullable=False)  # 청크 순서 (0부터 시작)
    chunk_total = Column(Integer, nullable=False)  # 전체 청크 수

    # 텍스트 콘텐츠
    text = Column(Text, nullable=False)
    text_hash = Column(String(64), nullable=False)  # SHA256(text) - 중복 제거용
    word_count = Column(Integer, nullable=False)
    char_count = Column(Integer, nullable=False)
    language = Column(String(10), nullable=False, default="ko")

    # 메타데이터 (SQLAlchemy 예약어 회피를 위해 doc_metadata 사용)
    doc_metadata = Column("metadata", JSONB, nullable=False, default={})
    tags = Column(ARRAY(String), default=[])

    # 상태 및 버전
    is_active = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)

    # 타임스탬프
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    embedding = relationship("RAGEmbedding", back_populates="document", uselist=False, cascade="all, delete-orphan")
    versions = relationship("RAGDocumentVersion", back_populates="document", cascade="all, delete-orphan")
    children = relationship("RAGDocument", backref="parent", remote_side=[id])

    def __repr__(self):
        return f"<RAGDocument(id={self.id}, title='{self.title}', chunk={self.chunk_index}/{self.chunk_total})>"


class RAGDocumentVersion(Base):
    """RAG 문서 버전 이력

    목적: 문서 변경 이력 추적
    """

    __tablename__ = "rag_document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version", name="uq_rag_doc_versions"),
        CheckConstraint(
            "change_type IN ('create', 'update', 'delete', 'restore')",
            name="ck_rag_doc_versions_change_type"
        ),
        Index("idx_rag_doc_versions_document", "document_id", "version"),
        {"schema": "rag", "extend_existing": True},
    )

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id = Column(PGUUID(as_uuid=True), ForeignKey("rag.rag_documents.id", ondelete="CASCADE"), nullable=False)

    version = Column(Integer, nullable=False)
    change_type = Column(String(20), nullable=False)  # create, update, delete, restore
    changed_by = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id", ondelete="SET NULL"), nullable=True)
    change_summary = Column(Text, nullable=True)
    diff = Column(JSONB, nullable=True)  # 변경 diff

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    document = relationship("RAGDocument", back_populates="versions")

    def __repr__(self):
        return f"<RAGDocumentVersion(doc_id={self.document_id}, version={self.version}, type='{self.change_type}')>"


class RAGEmbedding(Base):
    """RAG 임베딩 벡터 (pgvector)

    목적: 문서 청크의 임베딩 벡터 저장
    벡터 차원: 1536 (OpenAI text-embedding-3-small)
    인덱스: IVFFlat (lists=100)

    Note: embedding 컬럼은 실제 DB에서 vector(1536) 타입으로 생성됨
          SQLAlchemy에서는 Text로 선언하고 migration에서 타입 변환
    """

    __tablename__ = "rag_embeddings"
    __table_args__ = (
        # pgvector 인덱스는 migration에서 raw SQL로 생성
        {"schema": "rag", "extend_existing": True},
    )

    doc_id = Column(PGUUID(as_uuid=True), ForeignKey("rag.rag_documents.id", ondelete="CASCADE"), primary_key=True)

    # 임베딩 벡터 - 실제 DB에서는 vector(1536) 타입
    # Alembic migration에서 pgvector 확장 및 컬럼 타입 설정
    embedding = Column(Text, nullable=False)  # vector(1536) in actual DB

    model = Column(String(100), nullable=False, default="text-embedding-3-small")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    document = relationship("RAGDocument", back_populates="embedding")

    def __repr__(self):
        return f"<RAGEmbedding(doc_id={self.doc_id}, model='{self.model}')>"


class EmbeddingJob(Base):
    """임베딩 생성 배치 작업

    목적: 임베딩 생성 작업 추적
    """

    __tablename__ = "embedding_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_embedding_jobs_status"
        ),
        Index("idx_embedding_jobs_tenant", "tenant_id", "created_at"),
        Index("idx_embedding_jobs_status", "status", postgresql_where="status IN ('pending', 'running')"),
        {"schema": "rag", "extend_existing": True},
    )

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)

    status = Column(String(20), nullable=False, default="pending")  # pending, running, completed, failed
    document_count = Column(Integer, nullable=False)
    embeddings_generated = Column(Integer, nullable=False, default=0)

    model = Column(String(100), nullable=False)
    total_tokens = Column(Integer, nullable=True)
    cost_estimate_usd = Column(Float, nullable=True)

    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<EmbeddingJob(id={self.id}, status='{self.status}', progress={self.embeddings_generated}/{self.document_count})>"


# ========== 메모리 시스템 모델 ==========


class Memory(Base):
    """AI 에이전트 장단기 메모리

    목적: AI 에이전트의 다양한 타입의 메모리 저장
    메모리 타입:
    - short_term: 단기 (1일 TTL) - 세션 내 임시 정보
    - long_term: 장기 (영구) - 학습된 패턴
    - episodic: 에피소드 (30일 TTL) - 과거 사건 기억
    - semantic: 시맨틱 (영구) - 일반 지식
    - procedural: 절차적 (영구) - 절차적 지식
    """

    __tablename__ = "memories"
    __table_args__ = (
        UniqueConstraint("tenant_id", "type", "key", name="uq_memories_tenant_type_key"),
        CheckConstraint(
            "type IN ('short_term', 'long_term', 'episodic', 'semantic', 'procedural')",
            name="ck_memories_type"
        ),
        CheckConstraint("importance >= 0 AND importance <= 1", name="ck_memories_importance"),
        Index("idx_memories_tenant_type", "tenant_id", "type"),
        Index("idx_memories_expires", "expires_at", postgresql_where="expires_at IS NOT NULL"),
        Index("idx_memories_importance", "importance"),
        {"schema": "rag", "extend_existing": True},
    )

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)

    type = Column(String(20), nullable=False)  # short_term, long_term, episodic, semantic, procedural
    key = Column(String(255), nullable=False)  # 메모리 식별 키
    value = Column(JSONB, nullable=False)  # 메모리 내용

    importance = Column(Float, nullable=False, default=0.5)  # 0.0 ~ 1.0
    access_count = Column(Integer, nullable=False, default=0)
    last_accessed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)  # null = 만료 없음

    context = Column(JSONB, nullable=True)  # 추가 컨텍스트 정보

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Memory(id={self.id}, type='{self.type}', key='{self.key}', importance={self.importance})>"


# ========== AAS (Asset Administration Shell) 모델 ==========


class AASAsset(Base):
    """AAS 자산 정의 (IEC 63278-1)

    목적: 생산 라인, 설비 등 자산 정의
    자산 타입: line, equipment, product, process, system
    """

    __tablename__ = "aas_assets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "asset_id", name="uq_aas_assets_tenant_asset"),
        CheckConstraint(
            "asset_type IN ('line', 'equipment', 'product', 'process', 'system')",
            name="ck_aas_assets_type"
        ),
        Index("idx_aas_assets_tenant", "tenant_id"),
        Index("idx_aas_assets_ref", "ref_code"),
        Index("idx_aas_assets_type", "asset_type"),
        {"schema": "aas", "extend_existing": True},
    )

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)

    asset_id = Column(String(255), nullable=False)  # 예: 'line:L01', 'equipment:E01-M01'
    asset_type = Column(String(20), nullable=False)  # line, equipment, product, process, system
    ref_code = Column(String(100), nullable=False)  # 실제 시스템 코드 (line_code, equipment_code 등)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    manufacturer = Column(String(255), nullable=True)
    model = Column(String(255), nullable=True)
    serial_number = Column(String(255), nullable=True)

    asset_metadata = Column("metadata", JSONB, nullable=False, default={})
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    submodels = relationship("AASSubmodel", back_populates="asset", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<AASAsset(id={self.id}, asset_id='{self.asset_id}', name='{self.name}')>"


class AASSubmodel(Base):
    """AAS 서브모델 (자산의 다양한 측면)

    목적: 자산의 다양한 측면 표현 (생산, 품질, 유지보수 등)
    카테고리: production, quality, maintenance, energy, cost, technical_data
    """

    __tablename__ = "aas_submodels"
    __table_args__ = (
        UniqueConstraint("asset_id", "submodel_id", name="uq_aas_submodels_asset_submodel"),
        CheckConstraint(
            "category IN ('production', 'quality', 'maintenance', 'energy', 'cost', 'technical_data')",
            name="ck_aas_submodels_category"
        ),
        Index("idx_aas_submodels_asset", "asset_id"),
        Index("idx_aas_submodels_category", "category"),
        {"schema": "aas", "extend_existing": True},
    )

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    asset_id = Column(PGUUID(as_uuid=True), ForeignKey("aas.aas_assets.id", ondelete="CASCADE"), nullable=False)

    submodel_id = Column(String(255), nullable=False)  # 예: 'ProductionQuality', 'OEE'
    name = Column(String(255), nullable=False)
    category = Column(String(50), nullable=False)  # production, quality, maintenance, energy, cost, technical_data
    description = Column(Text, nullable=True)
    semantic_id = Column(String(500), nullable=True)  # IEC CDD 또는 ECLASS 참조

    submodel_metadata = Column("metadata", JSONB, nullable=False, default={})

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    asset = relationship("AASAsset", back_populates="submodels")
    elements = relationship("AASElement", back_populates="submodel", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<AASSubmodel(id={self.id}, submodel_id='{self.submodel_id}', category='{self.category}')>"


class AASElement(Base):
    """AAS 요소 (데이터 포인트)

    목적: 서브모델 내 개별 데이터 요소
    데이터 타입: int, float, string, boolean, datetime, json
    """

    __tablename__ = "aas_elements"
    __table_args__ = (
        UniqueConstraint("submodel_id", "element_id", name="uq_aas_elements_submodel_element"),
        CheckConstraint(
            "datatype IN ('int', 'float', 'string', 'boolean', 'datetime', 'json')",
            name="ck_aas_elements_datatype"
        ),
        Index("idx_aas_elements_submodel", "submodel_id"),
        {"schema": "aas", "extend_existing": True},
    )

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    submodel_id = Column(PGUUID(as_uuid=True), ForeignKey("aas.aas_submodels.id", ondelete="CASCADE"), nullable=False)

    element_id = Column(String(255), nullable=False)  # 예: 'daily_defect_rate', 'oee'
    name = Column(String(255), nullable=False)
    datatype = Column(String(20), nullable=False)  # int, float, string, boolean, datetime, json
    unit = Column(String(50), nullable=True)  # 예: '%', 'mm', 'kg'
    description = Column(Text, nullable=True)

    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)
    enum_values = Column(ARRAY(String), nullable=True)  # 허용된 enum 값

    element_metadata = Column("metadata", JSONB, nullable=False, default={})

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    submodel = relationship("AASSubmodel", back_populates="elements")
    source_mappings = relationship("AASSourceMapping", back_populates="element", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<AASElement(id={self.id}, element_id='{self.element_id}', datatype='{self.datatype}')>"


class AASSourceMapping(Base):
    """AAS 소스 매핑 (요소 → 데이터 소스)

    목적: AAS 요소를 실제 데이터 소스에 매핑
    소스 타입: postgres_table, postgres_view, api_endpoint, mcp_tool, calculation
    """

    __tablename__ = "aas_source_mappings"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('postgres_table', 'postgres_view', 'api_endpoint', 'mcp_tool', 'calculation')",
            name="ck_aas_source_mappings_source_type"
        ),
        CheckConstraint(
            "aggregation IS NULL OR aggregation IN ('sum', 'avg', 'min', 'max', 'count', 'last', 'first')",
            name="ck_aas_source_mappings_aggregation"
        ),
        Index("idx_aas_mappings_element", "element_id"),
        Index("idx_aas_mappings_tenant", "tenant_id"),
        {"schema": "aas", "extend_existing": True},
    )

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    element_id = Column(PGUUID(as_uuid=True), ForeignKey("aas.aas_elements.id", ondelete="CASCADE"), nullable=False)

    source_type = Column(String(50), nullable=False)  # postgres_table, postgres_view, api_endpoint, mcp_tool, calculation
    source_table = Column(String(255), nullable=True)  # 테이블/뷰 이름
    source_column = Column(String(500), nullable=True)  # 컬럼 또는 SQL 표현식
    filter_expr = Column(Text, nullable=True)  # WHERE 절 (예: 'line_code = :line AND date = :date')
    aggregation = Column(String(20), nullable=True)  # sum, avg, min, max, count, last, first
    transform_expr = Column(Text, nullable=True)  # SQL 변환 표현식 (예: 'value * 100')

    cache_ttl_seconds = Column(Integer, default=60)  # 캐시 TTL
    description = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    element = relationship("AASElement", back_populates="source_mappings")

    def __repr__(self):
        return f"<AASSourceMapping(id={self.id}, source_type='{self.source_type}', table='{self.source_table}')>"
