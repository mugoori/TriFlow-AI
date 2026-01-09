"""
SQLAlchemy ORM Models

스키마 구조:
- core: 핵심 테이블 (tenants, users, workflows, rulesets 등)
- core_extended: 확장 테이블 (workflow_steps, chat_sessions, mcp_servers 등)
- rag: RAG 및 메모리 테이블 (rag_documents, rag_embeddings, memories)
- aas: AAS 디지털 트윈 테이블 (aas_assets, aas_submodels, aas_elements)
- bi: BI 및 분석 테이블 (dim_*, fact_*, bi_*, etl_*, data_quality_*)
"""
from app.models.core import (
    # Core
    Tenant,
    User,
    Ruleset,
    RulesetVersion,
    Workflow,
    WorkflowInstance,
    JudgmentExecution,
    SensorData,
    FeedbackLog,
    ProposedRule,
    # Experiments
    Experiment,
    ExperimentVariant,
    ExperimentAssignment,
    ExperimentMetric,
    # ERP/MES
    ErpMesData,
    FieldMapping,
    DataSource,
    ApiKey,
    # Workflow Extended
    WorkflowStep,
    WorkflowExecutionLog,
    # Judgment Cache
    JudgmentCache,
    # Rule Management
    RuleScript,
    RuleConflict,
    RuleDeployment,
    # Learning
    LearningSample,
    AutoRuleCandidate,
    ModelTrainingJob,
    # Prompt Templates
    PromptTemplate,
    PromptTemplateBody,
    LlmCall,
    # Chat
    ChatSession,
    IntentLog,
    ChatMessage,
    # Data Connectors
    DataConnector,
    # MCP Integration
    McpServer,
    McpTool,
    McpCallLog,
    # Audit
    AuditLog,
    # V2.0 Trust Model
    TrustLevelHistory,
)

from app.models.tenant_config import (
    # Multi-Tenant Module Configuration
    IndustryProfile,
    ModuleDefinition,
    TenantModule,
)

from app.models.rag import (
    # RAG Documents
    RAGDocument,
    RAGDocumentVersion,
    RAGEmbedding,
    EmbeddingJob,
    # Memory
    Memory,
    # AAS
    AASAsset,
    AASSubmodel,
    AASElement,
    AASSourceMapping,
)

from app.models.canary import (
    # Canary Deployment
    CanaryAssignment,
    DeploymentMetrics,
    CanaryExecutionLog,
)

from app.models.sample import (
    # Sample Curation
    Sample,
    GoldenSampleSet,
    GoldenSampleSetMember,
)

from app.models.bi import (
    # RAW Layer
    RawMesProduction,
    RawErpOrder,
    RawInventory,
    RawEquipmentEvent,
    # DIM Layer
    DimDate,
    DimLine,
    DimProduct,
    DimEquipment,
    DimKpi,
    DimShift,
    # FACT Layer
    FactDailyProduction,
    FactDailyDefect,
    FactInventorySnapshot,
    FactEquipmentEvent,
    FactHourlyProduction,
    # BI Catalog
    BiDataset,
    BiMetric,
    BiDashboard,
    BiComponent,
    # ETL
    EtlJob,
    EtlJobExecution,
    # Data Quality
    DataQualityRule,
    DataQualityCheck,
)

__all__ = [
    # Core
    "Tenant",
    "User",
    "Ruleset",
    "RulesetVersion",
    "Workflow",
    "WorkflowInstance",
    "JudgmentExecution",
    "SensorData",
    "FeedbackLog",
    "ProposedRule",
    # Experiments
    "Experiment",
    "ExperimentVariant",
    "ExperimentAssignment",
    "ExperimentMetric",
    # ERP/MES
    "ErpMesData",
    "FieldMapping",
    "DataSource",
    "ApiKey",
    # Workflow Extended
    "WorkflowStep",
    "WorkflowExecutionLog",
    # Judgment Cache
    "JudgmentCache",
    # Rule Management
    "RuleScript",
    "RuleConflict",
    "RuleDeployment",
    # Learning
    "LearningSample",
    "AutoRuleCandidate",
    "ModelTrainingJob",
    # Prompt Templates
    "PromptTemplate",
    "PromptTemplateBody",
    "LlmCall",
    # Chat
    "ChatSession",
    "IntentLog",
    "ChatMessage",
    # Data Connectors
    "DataConnector",
    # MCP Integration
    "McpServer",
    "McpTool",
    "McpCallLog",
    # Audit
    "AuditLog",
    # V2.0 Trust Model
    "TrustLevelHistory",
    # Multi-Tenant Module Configuration
    "IndustryProfile",
    "ModuleDefinition",
    "TenantModule",
    # RAG
    "RAGDocument",
    "RAGDocumentVersion",
    "RAGEmbedding",
    "EmbeddingJob",
    "Memory",
    # AAS
    "AASAsset",
    "AASSubmodel",
    "AASElement",
    "AASSourceMapping",
    # BI - RAW Layer
    "RawMesProduction",
    "RawErpOrder",
    "RawInventory",
    "RawEquipmentEvent",
    # BI - DIM Layer
    "DimDate",
    "DimLine",
    "DimProduct",
    "DimEquipment",
    "DimKpi",
    "DimShift",
    # BI - FACT Layer
    "FactDailyProduction",
    "FactDailyDefect",
    "FactInventorySnapshot",
    "FactEquipmentEvent",
    "FactHourlyProduction",
    # BI - Catalog
    "BiDataset",
    "BiMetric",
    "BiDashboard",
    "BiComponent",
    # BI - ETL
    "EtlJob",
    "EtlJobExecution",
    # BI - Data Quality
    "DataQualityRule",
    "DataQualityCheck",
    # Canary Deployment
    "CanaryAssignment",
    "DeploymentMetrics",
    "CanaryExecutionLog",
    # Sample Curation
    "Sample",
    "GoldenSampleSet",
    "GoldenSampleSetMember",
]
