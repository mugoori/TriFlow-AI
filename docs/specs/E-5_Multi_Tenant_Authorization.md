# E-5. Multi-Tenant 권한 관리 설계서

## 문서 정보
- **문서 ID**: E-5
- **버전**: 2.0 (V7 Intent + Orchestrator)
- **최종 수정일**: 2025-12-16
- **상태**: Active Development
- **관련 문서**:
  - B-3-3 V7 Intent Router 설계
  - B-3-4 Orchestrator 설계
  - B-6 AI/Agent Architecture
  - C-5 Security Compliance Enhanced
  - E-6 Enterprise Customization Guide

---

## 1. 개요

### 1.1 목적
본 문서는 AI Factory Decision Engine의 Multi-Tenant 환경에서 기업별, 역할별 접근 권한을 관리하는 체계를 정의합니다. RBAC(Role-Based Access Control)와 ABAC(Attribute-Based Access Control)를 결합한 하이브리드 권한 모델을 적용합니다.

### 1.2 설계 원칙
- **최소 권한 원칙**: 업무 수행에 필요한 최소한의 권한만 부여
- **역할 기반 접근**: 개인이 아닌 역할에 권한 부여
- **계층적 상속**: 상위 역할은 하위 역할의 권한 포함
- **감사 추적성**: 모든 권한 변경 및 접근 이력 기록
- **유연한 확장**: 기업별 커스텀 역할 및 권한 정의 지원

### 1.3 권한 관리 범위

```
┌─────────────────────────────────────────────────────────────────┐
│                    권한 관리 4계층 구조                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [Layer 1] Platform Level                                       │
│  └── 플랫폼 전체 관리 권한 (SaaS 운영사)                        │
│                                                                 │
│  [Layer 2] Tenant Level                                         │
│  └── 기업 내 역할 및 조직 구조 기반 권한                        │
│                                                                 │
│  [Layer 3] Data Scope Level                                     │
│  └── 데이터 접근 범위 (조직/시간/민감도)                        │
│                                                                 │
│  [Layer 4] Feature Level                                        │
│  └── 기능별 세부 권한 (Intent/Action/Export)                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 권한 모델 아키텍처

### 2.1 전체 구조

```
┌─────────────────────────────────────────────────────────────────┐
│                    Authorization Architecture                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │   User      │───▶│  Session    │───▶│  Context    │         │
│  │   Login     │    │  Token      │    │  Builder    │         │
│  └─────────────┘    └─────────────┘    └──────┬──────┘         │
│                                               │                 │
│                                               ▼                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  Authorization Service                   │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐           │   │
│  │  │   Role    │  │   Data    │  │  Feature  │           │   │
│  │  │  Checker  │  │  Scope    │  │  Permission│           │   │
│  │  │           │  │  Filter   │  │  Checker   │           │   │
│  │  └───────────┘  └───────────┘  └───────────┘           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Intent Router                         │   │
│  │    (권한 검증 통과 후 Intent 분류 및 라우팅)             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Data Access Layer                     │   │
│  │    (권한 범위 내 데이터만 조회/반환)                     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 권한 검증 흐름

```
┌─────────────────────────────────────────────────────────────────┐
│                    Authorization Flow                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. 사용자 요청                                                 │
│     │                                                           │
│     ▼                                                           │
│  2. JWT 토큰 검증 ──────────────────────▶ 실패 → 401 Unauthorized│
│     │                                                           │
│     ▼ (성공)                                                    │
│  3. User Context 로드                                           │
│     ├── 테넌트 정보                                             │
│     ├── 역할 정보                                               │
│     ├── 권한 목록                                               │
│     └── 데이터 범위                                             │
│     │                                                           │
│     ▼                                                           │
│  4. Intent 분류 (IntentRouter)                                  │
│     │                                                           │
│     ▼                                                           │
│  5. Intent 권한 검증 ───────────────────▶ 실패 → 403 Forbidden  │
│     │                                                           │
│     ▼ (성공)                                                    │
│  6. Slot 권한 필터링                                            │
│     ├── 라인/설비 제한 적용                                     │
│     └── 시간 범위 제한 적용                                     │
│     │                                                           │
│     ▼                                                           │
│  7. Agent 라우팅 & 데이터 조회                                  │
│     │                                                           │
│     ▼                                                           │
│  8. 응답 데이터 필터링                                          │
│     └── 민감도 기반 필드 마스킹                                 │
│     │                                                           │
│     ▼                                                           │
│  9. 최종 응답 반환                                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 역할 체계 설계

### 3.1 플랫폼 레벨 역할

| 역할 | 코드 | 설명 | 주요 권한 |
|------|------|------|----------|
| **슈퍼 관리자** | `super_admin` | SaaS 운영사 최고 관리자 | 전체 시스템 관리, 테넌트 생성/삭제 |
| **테넌트 관리자** | `tenant_admin` | 특정 기업 전담 관리자 | 해당 테넌트 전체 관리 |
| **기술 지원** | `support` | 기술 지원 담당자 | 읽기 전용 접근, 로그 조회 |

### 3.2 테넌트 레벨 역할 (기업 내)

```yaml
# 역할 계층 구조 (hierarchy_level: 1이 최상위)
role_hierarchy:
  executive:        # Level 1
    └── manager:    # Level 2
        └── supervisor:   # Level 3
            └── operator: # Level 5
        └── office_worker: # Level 4
```

### 3.3 역할별 상세 정의

#### 3.3.1 경영진 (Executive)

```yaml
executive:
  code: "executive"
  name_ko: "경영진"
  hierarchy_level: 1
  description: "기업 전체 데이터에 대한 완전한 접근 권한"

  data_scope:
    organization: "all"                    # 전체 조직
    time_range: "unlimited"                # 무제한
    sensitivity:
      - public
      - internal
      - confidential
      - restricted

  allowed_intents:
    - "*"                                  # 모든 Intent

  excluded_intents: []

  permissions:
    view:
      - "all_data"
      - "financial_metrics"
      - "hr_metrics"
      - "competitor_analysis"
      - "strategic_reports"
    action:
      - "approve_workflow"
      - "override_alerts"
      - "system_configuration"
    export:
      - "all_reports"
      - "raw_data"
      - "executive_summary"
    admin:
      - "manage_roles"
      - "view_audit_logs"

  features:
    - executive_dashboard
    - strategic_analytics
    - cross_factory_comparison
    - financial_impact_analysis
    - trend_forecasting
```

#### 3.3.2 관리자 (Manager)

```yaml
manager:
  code: "manager"
  name_ko: "관리자"
  hierarchy_level: 2
  description: "담당 부서/공장의 데이터 관리 및 분석 권한"

  data_scope:
    organization: "department"             # 담당 부서
    time_range: "365d"                     # 최근 1년
    sensitivity:
      - public
      - internal
      - confidential

  allowed_intents:
    - quality_check
    - defect_analysis
    - equipment_status
    - equipment_anomaly
    - production_status
    - bi_summary
    - bi_chart
    - bi_comparison
    - workflow_create
    - workflow_manage
    - alert_configure

  excluded_intents:
    - "admin_*"                            # 관리 기능 제외
    - "financial_*"                        # 재무 데이터 제외

  permissions:
    view:
      - "department_data"
      - "quality_metrics"
      - "equipment_metrics"
      - "production_metrics"
      - "team_performance"
    action:
      - "create_workflow"
      - "manage_alerts"
      - "acknowledge_issues"
      - "assign_tasks"
    export:
      - "department_reports"
      - "quality_reports"
      - "production_reports"

  features:
    - department_dashboard
    - detailed_analysis
    - workflow_management
    - team_monitoring
    - report_builder
```

#### 3.3.3 현장감독 (Supervisor)

```yaml
supervisor:
  code: "supervisor"
  name_ko: "현장감독"
  hierarchy_level: 3
  description: "담당 라인의 실시간 모니터링 및 즉각 대응 권한"

  data_scope:
    organization: "line"                   # 담당 라인
    time_range: "30d"                      # 최근 30일
    sensitivity:
      - public
      - internal

  allowed_intents:
    - quality_check
    - defect_analysis
    - equipment_status
    - equipment_anomaly
    - production_status
    - ccp_status
    - workflow_create                      # 담당 라인만
    - alert_acknowledge

  excluded_intents:
    - "bi_*"                               # BI 기능 제외
    - "admin_*"
    - "financial_*"
    - "workflow_manage"                    # 생성만, 관리는 불가

  permissions:
    view:
      - "line_data"
      - "realtime_status"
      - "quality_metrics"
      - "equipment_status"
    action:
      - "acknowledge_alert"
      - "create_line_workflow"
      - "report_issue"
      - "request_maintenance"
    export:
      - "line_reports"
      - "shift_summary"

  features:
    - line_dashboard
    - realtime_monitoring
    - alert_management
    - shift_handover
```

#### 3.3.4 사무직 (Office Worker)

```yaml
office_worker:
  code: "office_worker"
  name_ko: "사무직"
  hierarchy_level: 4
  description: "리포트 조회 및 집계 데이터 접근 권한"

  data_scope:
    organization: "department"             # 소속 부서
    time_range: "90d"                      # 최근 90일
    sensitivity:
      - public
      - internal

  allowed_intents:
    - quality_check
    - production_status
    - bi_summary
    - bi_chart
    - help
    - greeting

  excluded_intents:
    - "equipment_*"                        # 설비 관련 제외
    - "workflow_*"                         # 워크플로우 제외
    - "defect_analysis"                    # 원인 분석 제외
    - "admin_*"

  permissions:
    view:
      - "summary_data"
      - "aggregated_reports"
      - "quality_summary"
      - "production_summary"
    action: []                             # 조회만, 액션 없음
    export:
      - "basic_reports"
      - "summary_exports"

  features:
    - summary_dashboard
    - report_viewer
    - data_export_basic
```

#### 3.3.5 생산직 (Operator)

```yaml
operator:
  code: "operator"
  name_ko: "생산직"
  hierarchy_level: 5
  description: "담당 라인/설비의 실시간 상태 확인 권한"

  data_scope:
    organization: "assigned_line"          # 배정된 라인만
    time_range: "7d"                       # 최근 7일
    sensitivity:
      - public

  allowed_intents:
    - quality_check                        # 담당 라인만
    - equipment_status                     # 담당 설비만
    - ccp_status
    - production_status
    - help
    - greeting

  excluded_intents:
    - "defect_analysis"                    # 원인 분석 제외
    - "bi_*"                               # BI 제외
    - "workflow_*"                         # 워크플로우 제외
    - "admin_*"
    - "equipment_anomaly"                  # 이상 탐지는 감독자만

  permissions:
    view:
      - "assigned_line_data"
      - "realtime_status"
      - "my_equipment_status"
    action:
      - "report_issue"                     # 이슈 보고만
    export: []                             # 내보내기 없음

  features:
    - operator_dashboard
    - simple_status_check
    - issue_reporter
```

### 3.4 역할별 권한 매트릭스 요약

| 기능/데이터 | 경영진 | 관리자 | 현장감독 | 사무직 | 생산직 |
|-------------|:------:|:------:|:--------:|:------:|:------:|
| **조직 범위** | 전체 | 부서 | 라인 | 부서 | 배정라인 |
| **시간 범위** | 무제한 | 1년 | 30일 | 90일 | 7일 |
| **품질 현황 조회** | ✅ | ✅ | ✅ | ✅ | ✅(라인) |
| **불량 원인 분석** | ✅ | ✅ | ✅ | ❌ | ❌ |
| **설비 상태 조회** | ✅ | ✅ | ✅ | ❌ | ✅(설비) |
| **설비 이상 탐지** | ✅ | ✅ | ✅ | ❌ | ❌ |
| **BI 리포트** | ✅ | ✅ | ❌ | ✅ | ❌ |
| **워크플로우 생성** | ✅ | ✅ | ✅(라인) | ❌ | ❌ |
| **워크플로우 관리** | ✅ | ✅ | ❌ | ❌ | ❌ |
| **재무 데이터** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **데이터 내보내기** | ✅(전체) | ✅(부서) | ✅(라인) | ✅(요약) | ❌ |
| **역할 관리** | ✅ | ❌ | ❌ | ❌ | ❌ |

---

## 4. 데이터베이스 스키마

### 4.1 핵심 테이블

```sql
-- =====================================================
-- 1. 플랫폼 레벨 역할
-- =====================================================
CREATE TABLE platform_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    permissions JSONB DEFAULT '[]',
    is_system BOOLEAN DEFAULT true,        -- 시스템 기본 역할 여부
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 기본 플랫폼 역할 삽입
INSERT INTO platform_roles (code, name, description, permissions) VALUES
('super_admin', 'Super Administrator', '플랫폼 전체 관리자', '["*"]'),
('tenant_admin', 'Tenant Administrator', '테넌트 전담 관리자', '["tenant:*"]'),
('support', 'Technical Support', '기술 지원 (읽기 전용)', '["read:*"]');

-- =====================================================
-- 2. 테넌트 역할 템플릿
-- =====================================================
CREATE TABLE tenant_role_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    name_ko VARCHAR(100),
    description TEXT,
    hierarchy_level INT NOT NULL,

    -- 기본 권한 설정 (JSONB)
    default_data_scope JSONB NOT NULL,
    default_permissions JSONB NOT NULL,
    default_intents JSONB NOT NULL,
    default_features JSONB DEFAULT '[]',

    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =====================================================
-- 3. 테넌트별 커스텀 역할
-- =====================================================
CREATE TABLE tenant_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    template_id UUID REFERENCES tenant_role_templates(id),

    code VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    name_ko VARCHAR(100),
    description TEXT,

    -- Override 설정 (템플릿 기본값 덮어쓰기)
    data_scope_override JSONB DEFAULT '{}',
    permissions_override JSONB DEFAULT '{}',
    intents_override JSONB DEFAULT '{}',
    features_override JSONB DEFAULT '{}',

    is_custom BOOLEAN DEFAULT false,       -- 완전 커스텀 역할 여부
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(tenant_id, code)
);

-- 인덱스
CREATE INDEX idx_tenant_roles_tenant ON tenant_roles(tenant_id);
CREATE INDEX idx_tenant_roles_template ON tenant_roles(template_id);

-- =====================================================
-- 4. 사용자
-- =====================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 기본 정보
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    employee_id VARCHAR(50),               -- 사번 (기업 내 식별자)

    -- 플랫폼 역할 (SaaS 운영 관련)
    platform_role_id UUID REFERENCES platform_roles(id),

    -- 인증 정보
    password_hash VARCHAR(255),            -- 로컬 인증용
    auth_provider VARCHAR(50) DEFAULT 'local',
    external_id VARCHAR(255),              -- SSO/OAuth 연동 ID

    -- 상태
    is_active BOOLEAN DEFAULT true,
    email_verified BOOLEAN DEFAULT false,
    last_login_at TIMESTAMP,
    password_changed_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 인덱스
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_platform_role ON users(platform_role_id);

-- =====================================================
-- 5. 사용자-테넌트-역할 매핑
-- =====================================================
CREATE TABLE user_tenant_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES tenant_roles(id) ON DELETE CASCADE,

    -- 추가 제한 (역할 기본값보다 좁은 범위로 제한)
    scope_restriction JSONB DEFAULT '{}',
    intent_restriction JSONB DEFAULT '{}',

    -- 권한 부여 정보
    granted_by UUID REFERENCES users(id),
    granted_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,                  -- 임시 권한용

    -- 상태
    is_active BOOLEAN DEFAULT true,
    is_primary BOOLEAN DEFAULT false,      -- 기본 역할 여부

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(user_id, tenant_id, role_id)
);

-- 인덱스
CREATE INDEX idx_utr_user ON user_tenant_roles(user_id);
CREATE INDEX idx_utr_tenant ON user_tenant_roles(tenant_id);
CREATE INDEX idx_utr_active ON user_tenant_roles(is_active) WHERE is_active = true;

-- =====================================================
-- 6. 조직 구조 (계층형)
-- =====================================================
CREATE TABLE organization_units (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    parent_id UUID REFERENCES organization_units(id),

    code VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    name_ko VARCHAR(100),
    unit_type VARCHAR(30) NOT NULL,        -- 'company', 'factory', 'department', 'line'

    -- 계층 정보 (Materialized Path)
    path VARCHAR(500),                     -- '/company/factory1/dept1/line1'
    depth INT NOT NULL DEFAULT 0,

    -- 메타데이터
    metadata JSONB DEFAULT '{}',
    sort_order INT DEFAULT 0,

    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(tenant_id, code)
);

-- 인덱스
CREATE INDEX idx_org_tenant ON organization_units(tenant_id);
CREATE INDEX idx_org_parent ON organization_units(parent_id);
CREATE INDEX idx_org_path ON organization_units(path);
CREATE INDEX idx_org_type ON organization_units(unit_type);

-- =====================================================
-- 7. 사용자 조직 범위 할당
-- =====================================================
CREATE TABLE user_org_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    org_unit_id UUID NOT NULL REFERENCES organization_units(id) ON DELETE CASCADE,

    include_children BOOLEAN DEFAULT true, -- 하위 조직 포함 여부
    assignment_type VARCHAR(30) DEFAULT 'primary', -- 'primary', 'additional', 'temporary'

    valid_from TIMESTAMP DEFAULT NOW(),
    valid_until TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(user_id, tenant_id, org_unit_id)
);

-- 인덱스
CREATE INDEX idx_uoa_user_tenant ON user_org_assignments(user_id, tenant_id);

-- =====================================================
-- 8. 권한 정의
-- =====================================================
CREATE TABLE permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(100) UNIQUE NOT NULL,     -- 'view:quality_metrics'
    category VARCHAR(50) NOT NULL,         -- 'view', 'action', 'export', 'admin'
    resource VARCHAR(50) NOT NULL,         -- 'quality_metrics', 'workflow', etc.
    name VARCHAR(100) NOT NULL,
    description TEXT,

    requires_audit BOOLEAN DEFAULT false,
    risk_level VARCHAR(20) DEFAULT 'low',  -- 'low', 'medium', 'high', 'critical'

    created_at TIMESTAMP DEFAULT NOW()
);

-- 인덱스
CREATE INDEX idx_permissions_category ON permissions(category);

-- =====================================================
-- 9. Intent 권한 매핑
-- =====================================================
CREATE TABLE intent_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intent_id VARCHAR(50) UNIQUE NOT NULL,

    -- 접근 조건
    min_hierarchy_level INT NOT NULL DEFAULT 5,
    required_permissions JSONB DEFAULT '[]',

    -- 데이터 민감도
    data_sensitivity VARCHAR(20) DEFAULT 'internal',

    -- 추가 제한
    requires_scope_check BOOLEAN DEFAULT true,
    scope_type VARCHAR(30),                -- 'line', 'department', 'factory', etc.

    created_at TIMESTAMP DEFAULT NOW()
);

-- =====================================================
-- 10. 감사 로그
-- =====================================================
CREATE TABLE authorization_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 주체
    user_id UUID REFERENCES users(id),
    tenant_id UUID REFERENCES tenants(id),
    session_id VARCHAR(100),

    -- 행위
    action_type VARCHAR(50) NOT NULL,      -- 'access', 'modify', 'export', 'denied'
    resource_type VARCHAR(50) NOT NULL,    -- 'intent', 'data', 'workflow', etc.
    resource_id VARCHAR(100),

    -- 상세
    request_data JSONB,
    result VARCHAR(20) NOT NULL,           -- 'allowed', 'denied', 'filtered'
    denial_reason TEXT,

    -- 메타
    ip_address INET,
    user_agent TEXT,

    created_at TIMESTAMP DEFAULT NOW()
);

-- 파티셔닝 (월별)
CREATE INDEX idx_audit_created ON authorization_audit_logs(created_at);
CREATE INDEX idx_audit_user ON authorization_audit_logs(user_id, created_at);
CREATE INDEX idx_audit_tenant ON authorization_audit_logs(tenant_id, created_at);
```

### 4.2 뷰 및 함수

```sql
-- =====================================================
-- 사용자 권한 요약 뷰
-- =====================================================
CREATE OR REPLACE VIEW v_user_permissions AS
SELECT
    u.id as user_id,
    u.email,
    u.name,
    t.id as tenant_id,
    t.code as tenant_code,
    tr.code as role_code,
    tr.name_ko as role_name,
    trt.hierarchy_level,

    -- 병합된 권한 (템플릿 + override)
    COALESCE(tr.data_scope_override, '{}') || trt.default_data_scope as data_scope,
    COALESCE(tr.permissions_override, '{}') || trt.default_permissions as permissions,
    COALESCE(tr.intents_override, '{}') || trt.default_intents as intents

FROM users u
JOIN user_tenant_roles utr ON u.id = utr.user_id
JOIN tenants t ON utr.tenant_id = t.id
JOIN tenant_roles tr ON utr.role_id = tr.id
LEFT JOIN tenant_role_templates trt ON tr.template_id = trt.id
WHERE utr.is_active = true
  AND (utr.expires_at IS NULL OR utr.expires_at > NOW());

-- =====================================================
-- 사용자 조직 범위 조회 함수
-- =====================================================
CREATE OR REPLACE FUNCTION get_user_org_scope(
    p_user_id UUID,
    p_tenant_id UUID
) RETURNS TABLE (org_unit_id UUID, org_path VARCHAR) AS $$
BEGIN
    RETURN QUERY
    WITH assigned_orgs AS (
        SELECT
            ou.id,
            ou.path,
            uoa.include_children
        FROM user_org_assignments uoa
        JOIN organization_units ou ON uoa.org_unit_id = ou.id
        WHERE uoa.user_id = p_user_id
          AND uoa.tenant_id = p_tenant_id
          AND (uoa.valid_until IS NULL OR uoa.valid_until > NOW())
    )
    SELECT DISTINCT
        ou.id as org_unit_id,
        ou.path as org_path
    FROM organization_units ou
    JOIN assigned_orgs ao ON (
        ou.id = ao.id
        OR (ao.include_children AND ou.path LIKE ao.path || '/%')
    )
    WHERE ou.tenant_id = p_tenant_id
      AND ou.is_active = true;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- Intent 접근 권한 검증 함수
-- =====================================================
CREATE OR REPLACE FUNCTION check_intent_permission(
    p_user_id UUID,
    p_tenant_id UUID,
    p_intent_id VARCHAR
) RETURNS TABLE (
    allowed BOOLEAN,
    reason TEXT,
    filtered_scope JSONB
) AS $$
DECLARE
    v_user_level INT;
    v_user_intents JSONB;
    v_intent_min_level INT;
    v_intent_sensitivity VARCHAR;
BEGIN
    -- 사용자 역할 레벨 및 허용 Intent 조회
    SELECT
        trt.hierarchy_level,
        COALESCE(tr.intents_override, trt.default_intents)
    INTO v_user_level, v_user_intents
    FROM user_tenant_roles utr
    JOIN tenant_roles tr ON utr.role_id = tr.id
    JOIN tenant_role_templates trt ON tr.template_id = trt.id
    WHERE utr.user_id = p_user_id
      AND utr.tenant_id = p_tenant_id
      AND utr.is_active = true
    LIMIT 1;

    -- Intent 권한 요구사항 조회
    SELECT min_hierarchy_level, data_sensitivity
    INTO v_intent_min_level, v_intent_sensitivity
    FROM intent_permissions
    WHERE intent_id = p_intent_id;

    -- 레벨 검증
    IF v_user_level > COALESCE(v_intent_min_level, 5) THEN
        RETURN QUERY SELECT false, 'Insufficient role level', NULL::JSONB;
        RETURN;
    END IF;

    -- Intent 목록 검증
    IF NOT (
        v_user_intents->>'allowed' = 'all' OR
        v_user_intents->'allowed' ? p_intent_id
    ) THEN
        RETURN QUERY SELECT false, 'Intent not in allowed list', NULL::JSONB;
        RETURN;
    END IF;

    -- 제외 목록 검증
    IF v_user_intents->'excluded' ? p_intent_id THEN
        RETURN QUERY SELECT false, 'Intent is excluded', NULL::JSONB;
        RETURN;
    END IF;

    RETURN QUERY SELECT true, NULL::TEXT, '{}'::JSONB;
END;
$$ LANGUAGE plpgsql;
```

---

## 5. 권한 검증 서비스 구현

### 5.1 UserContext 모델

```python
# src/auth/models.py
from dataclasses import dataclass, field
from typing import List, Set, Optional, Dict, Any
from enum import Enum
from datetime import datetime

class DataSensitivity(Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


@dataclass
class DataScope:
    """데이터 접근 범위"""
    organization_type: str          # 'all', 'factory', 'department', 'line', 'assigned_line'
    organization_ids: List[str]     # 접근 가능 조직 ID 목록
    time_range_days: int            # 조회 가능 기간 (일)
    sensitivity_levels: List[str]   # 접근 가능 민감도 레벨

    def can_access_org(self, org_id: str) -> bool:
        """조직 접근 가능 여부"""
        if self.organization_type == 'all':
            return True
        return org_id in self.organization_ids

    def can_access_sensitivity(self, level: str) -> bool:
        """민감도 레벨 접근 가능 여부"""
        return level in self.sensitivity_levels


@dataclass
class UserContext:
    """사용자 권한 컨텍스트"""
    # 기본 정보
    user_id: str
    tenant_id: str
    email: str
    name: str

    # 역할 정보
    role_code: str
    role_name: str
    hierarchy_level: int

    # 권한
    permissions: Set[str]
    allowed_intents: Set[str]
    excluded_intents: Set[str]
    features: Set[str]

    # 데이터 범위
    data_scope: DataScope

    # 추가 제한
    line_restriction: Optional[List[str]] = None
    equipment_restriction: Optional[List[str]] = None

    # 메타
    session_id: Optional[str] = None
    login_at: Optional[datetime] = None

    def has_permission(self, permission: str) -> bool:
        """권한 보유 여부 확인"""
        if '*' in self.permissions:
            return True

        # 정확한 매칭
        if permission in self.permissions:
            return True

        # 와일드카드 매칭 (예: 'view:*')
        parts = permission.split(':')
        if len(parts) == 2:
            wildcard = f"{parts[0]}:*"
            if wildcard in self.permissions:
                return True

        return False

    def can_access_intent(self, intent_id: str) -> tuple[bool, Optional[str]]:
        """Intent 접근 가능 여부"""
        # 제외 목록 확인 (우선)
        if intent_id in self.excluded_intents:
            return False, f"Intent '{intent_id}' is explicitly excluded"

        # 와일드카드 제외 확인
        for excluded in self.excluded_intents:
            if excluded.endswith('*') and intent_id.startswith(excluded[:-1]):
                return False, f"Intent matches excluded pattern '{excluded}'"

        # 허용 목록 확인
        if 'all' in self.allowed_intents or '*' in self.allowed_intents:
            return True, None

        if intent_id in self.allowed_intents:
            return True, None

        # 와일드카드 허용 확인
        for allowed in self.allowed_intents:
            if allowed.endswith('*') and intent_id.startswith(allowed[:-1]):
                return True, None

        return False, f"Intent '{intent_id}' not in allowed list"
```

### 5.2 Authorization Service

```python
# src/auth/service.py
import asyncpg
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import structlog

from src.auth.models import UserContext, DataScope

logger = structlog.get_logger()


class AuthorizationService:
    """권한 검증 서비스"""

    def __init__(self, db_pool: asyncpg.Pool):
        self.db = db_pool
        self._context_cache: Dict[str, tuple[UserContext, datetime]] = {}
        self._cache_ttl = timedelta(minutes=5)

    async def get_user_context(
        self,
        user_id: str,
        tenant_id: str,
        session_id: Optional[str] = None
    ) -> UserContext:
        """사용자 권한 컨텍스트 로드"""

        # 캐시 확인
        cache_key = f"{user_id}:{tenant_id}"
        if cache_key in self._context_cache:
            ctx, cached_at = self._context_cache[cache_key]
            if datetime.utcnow() - cached_at < self._cache_ttl:
                ctx.session_id = session_id
                return ctx

        # DB에서 로드
        ctx = await self._load_from_db(user_id, tenant_id)
        ctx.session_id = session_id

        # 캐시 저장
        self._context_cache[cache_key] = (ctx, datetime.utcnow())

        return ctx

    async def _load_from_db(self, user_id: str, tenant_id: str) -> UserContext:
        """DB에서 사용자 컨텍스트 로드"""

        # 1. 사용자 및 역할 정보 조회
        user_role = await self.db.fetchrow("""
            SELECT
                u.email,
                u.name,
                tr.code as role_code,
                tr.name_ko as role_name,
                trt.hierarchy_level,
                trt.default_data_scope,
                trt.default_permissions,
                trt.default_intents,
                trt.default_features,
                tr.data_scope_override,
                tr.permissions_override,
                tr.intents_override,
                tr.features_override,
                utr.scope_restriction,
                utr.intent_restriction
            FROM users u
            JOIN user_tenant_roles utr ON u.id = utr.user_id
            JOIN tenant_roles tr ON utr.role_id = tr.id
            JOIN tenant_role_templates trt ON tr.template_id = trt.id
            WHERE u.id = $1
              AND utr.tenant_id = $2
              AND utr.is_active = true
              AND (utr.expires_at IS NULL OR utr.expires_at > NOW())
            ORDER BY utr.is_primary DESC
            LIMIT 1
        """, user_id, tenant_id)

        if not user_role:
            raise PermissionError(f"No active role found for user {user_id} in tenant {tenant_id}")

        # 2. 권한 병합 (기본 + override)
        permissions = self._merge_json(
            user_role['default_permissions'],
            user_role['permissions_override']
        )

        intents = self._merge_intents(
            user_role['default_intents'],
            user_role['intents_override'],
            user_role['intent_restriction']
        )

        features = self._merge_json(
            user_role['default_features'],
            user_role['features_override']
        )

        # 3. 데이터 범위 계산
        data_scope_config = self._merge_json(
            user_role['default_data_scope'],
            user_role['data_scope_override']
        )

        # 4. 조직 범위 조회
        org_ids = await self._get_org_scope(user_id, tenant_id)

        data_scope = DataScope(
            organization_type=data_scope_config.get('organization', 'assigned_line'),
            organization_ids=org_ids,
            time_range_days=self._parse_time_range(data_scope_config.get('time_range', '7d')),
            sensitivity_levels=data_scope_config.get('sensitivity', ['public'])
        )

        # 5. 추가 제한 적용
        scope_restriction = user_role['scope_restriction'] or {}

        return UserContext(
            user_id=user_id,
            tenant_id=tenant_id,
            email=user_role['email'],
            name=user_role['name'],
            role_code=user_role['role_code'],
            role_name=user_role['role_name'],
            hierarchy_level=user_role['hierarchy_level'],
            permissions=set(permissions),
            allowed_intents=set(intents.get('allowed', [])),
            excluded_intents=set(intents.get('excluded', [])),
            features=set(features),
            data_scope=data_scope,
            line_restriction=scope_restriction.get('lines'),
            equipment_restriction=scope_restriction.get('equipment')
        )

    async def _get_org_scope(self, user_id: str, tenant_id: str) -> List[str]:
        """사용자 조직 범위 조회"""
        rows = await self.db.fetch("""
            SELECT org_unit_id::text
            FROM get_user_org_scope($1, $2)
        """, user_id, tenant_id)
        return [row['org_unit_id'] for row in rows]

    def _merge_json(self, base: dict, override: dict) -> Any:
        """JSON 병합 (override가 base를 덮어씀)"""
        if not override:
            return base or {}
        if not base:
            return override

        if isinstance(base, list):
            # 리스트는 override가 완전 대체
            return override if override else base

        # dict는 병합
        result = base.copy()
        result.update(override)
        return result

    def _merge_intents(
        self,
        base: dict,
        override: dict,
        restriction: dict
    ) -> dict:
        """Intent 권한 병합"""
        result = {
            'allowed': set(base.get('allowed', [])),
            'excluded': set(base.get('excluded', []))
        }

        # Override 적용
        if override:
            if override.get('allowed'):
                result['allowed'] = set(override['allowed'])
            if override.get('excluded'):
                result['excluded'].update(override['excluded'])

        # 추가 제한 적용
        if restriction:
            if restriction.get('excluded'):
                result['excluded'].update(restriction['excluded'])
            if restriction.get('allowed_only'):
                # 특정 Intent만 허용
                result['allowed'] = result['allowed'] & set(restriction['allowed_only'])

        return {
            'allowed': list(result['allowed']),
            'excluded': list(result['excluded'])
        }

    def _parse_time_range(self, time_range: str) -> int:
        """시간 범위 문자열을 일수로 변환"""
        if time_range == 'unlimited':
            return 36500  # 100년

        if time_range.endswith('d'):
            return int(time_range[:-1])
        elif time_range.endswith('w'):
            return int(time_range[:-1]) * 7
        elif time_range.endswith('m'):
            return int(time_range[:-1]) * 30
        elif time_range.endswith('y'):
            return int(time_range[:-1]) * 365

        return 7  # 기본값

    def invalidate_cache(self, user_id: str, tenant_id: str):
        """캐시 무효화"""
        cache_key = f"{user_id}:{tenant_id}"
        if cache_key in self._context_cache:
            del self._context_cache[cache_key]

    async def check_intent_access(
        self,
        user_ctx: UserContext,
        intent_id: str
    ) -> tuple[bool, Optional[str]]:
        """Intent 접근 권한 검증"""

        # 1. UserContext 기반 검증
        allowed, reason = user_ctx.can_access_intent(intent_id)
        if not allowed:
            await self._log_access_denied(user_ctx, 'intent', intent_id, reason)
            return False, reason

        # 2. Intent별 추가 조건 검증
        intent_perm = await self.db.fetchrow("""
            SELECT min_hierarchy_level, required_permissions, data_sensitivity
            FROM intent_permissions
            WHERE intent_id = $1
        """, intent_id)

        if intent_perm:
            # 레벨 검증
            if user_ctx.hierarchy_level > intent_perm['min_hierarchy_level']:
                reason = f"Requires hierarchy level {intent_perm['min_hierarchy_level']} or higher"
                await self._log_access_denied(user_ctx, 'intent', intent_id, reason)
                return False, reason

            # 추가 권한 검증
            required = intent_perm['required_permissions'] or []
            for perm in required:
                if not user_ctx.has_permission(perm):
                    reason = f"Missing required permission: {perm}"
                    await self._log_access_denied(user_ctx, 'intent', intent_id, reason)
                    return False, reason

            # 민감도 검증
            if not user_ctx.data_scope.can_access_sensitivity(intent_perm['data_sensitivity']):
                reason = f"Cannot access {intent_perm['data_sensitivity']} level data"
                await self._log_access_denied(user_ctx, 'intent', intent_id, reason)
                return False, reason

        return True, None

    def filter_slots_by_permission(
        self,
        user_ctx: UserContext,
        slots: Dict[str, Any]
    ) -> Dict[str, Any]:
        """권한에 따른 Slot 필터링"""
        filtered = slots.copy()

        # 라인 제한
        if user_ctx.line_restriction and 'line' in filtered:
            if filtered['line'] not in user_ctx.line_restriction:
                # 권한 없는 라인 요청 → 첫 번째 허용 라인으로 대체
                logger.warning(
                    "Line access restricted",
                    requested=filtered['line'],
                    allowed=user_ctx.line_restriction
                )
                filtered['line'] = user_ctx.line_restriction[0]

        # 설비 제한
        if user_ctx.equipment_restriction and 'equipment' in filtered:
            if filtered['equipment'] not in user_ctx.equipment_restriction:
                filtered['equipment'] = user_ctx.equipment_restriction[0]

        # 시간 범위 제한
        if 'time_range' in filtered:
            filtered['time_range'] = self._cap_time_range(
                filtered['time_range'],
                user_ctx.data_scope.time_range_days
            )

        return filtered

    def _cap_time_range(self, requested: str, max_days: int) -> str:
        """시간 범위 제한 적용"""
        range_map = {
            'today': 1,
            'yesterday': 2,
            'last_week': 7,
            'last_7d': 7,
            'last_month': 30,
            'last_30d': 30,
            'last_90d': 90,
            'last_year': 365,
            'last_365d': 365
        }

        requested_days = range_map.get(requested, 7)

        if requested_days <= max_days:
            return requested

        # 허용 범위 내 최대값으로 대체
        for range_name, days in sorted(range_map.items(), key=lambda x: -x[1]):
            if days <= max_days:
                return range_name

        return 'today'

    async def _log_access_denied(
        self,
        user_ctx: UserContext,
        resource_type: str,
        resource_id: str,
        reason: str
    ):
        """접근 거부 로깅"""
        await self.db.execute("""
            INSERT INTO authorization_audit_logs
            (user_id, tenant_id, session_id, action_type, resource_type, resource_id, result, denial_reason)
            VALUES ($1, $2, $3, 'access', $4, $5, 'denied', $6)
        """, user_ctx.user_id, user_ctx.tenant_id, user_ctx.session_id,
             resource_type, resource_id, reason)
```

### 5.3 Intent Router 통합

```python
# src/core/authorized_router.py
from typing import Optional
from src.core.router import IntentRouter, IntentRequest, IntentResponse
from src.auth.service import AuthorizationService
from src.auth.models import UserContext
import structlog

logger = structlog.get_logger()


class AuthorizedIntentRouter:
    """권한 검증 통합 Intent Router"""

    def __init__(
        self,
        router: IntentRouter,
        auth_service: AuthorizationService
    ):
        self.router = router
        self.auth = auth_service

    async def classify(
        self,
        request: IntentRequest,
        user_ctx: UserContext
    ) -> IntentResponse:
        """권한 검증 포함 Intent 분류"""

        # 1. 기본 Intent 분류
        result = await self.router.classify(request)

        logger.info(
            "Intent classified",
            user_id=user_ctx.user_id,
            intent=result.intent,
            confidence=result.confidence
        )

        # 2. Intent 접근 권한 검증
        allowed, reason = await self.auth.check_intent_access(
            user_ctx, result.intent
        )

        if not allowed:
            logger.warning(
                "Intent access denied",
                user_id=user_ctx.user_id,
                intent=result.intent,
                reason=reason
            )

            return IntentResponse(
                request_id=result.request_id,
                intent="permission_denied",
                confidence=1.0,
                slots={},
                ask_back=self._generate_denial_message(result.intent, user_ctx),
                route_to="fallback",
                method="auth_blocked",
                processing_time_ms=result.processing_time_ms,
                metadata={
                    "blocked_intent": result.intent,
                    "reason": reason,
                    "user_role": user_ctx.role_code
                }
            )

        # 3. Slot 권한 필터링
        filtered_slots = self.auth.filter_slots_by_permission(
            user_ctx, result.slots
        )

        # Slot이 변경되었으면 로깅
        if filtered_slots != result.slots:
            logger.info(
                "Slots filtered by permission",
                original=result.slots,
                filtered=filtered_slots
            )

        # 4. 데이터 범위 검증
        data_scope_warning = self._check_data_scope(user_ctx, filtered_slots)
        if data_scope_warning:
            result.ask_back = data_scope_warning

        result.slots = filtered_slots
        return result

    def _generate_denial_message(
        self,
        intent: str,
        user_ctx: UserContext
    ) -> str:
        """권한 거부 메시지 생성"""

        intent_names = {
            "defect_analysis": "불량 원인 분석",
            "equipment_anomaly": "설비 이상 탐지",
            "bi_summary": "BI 요약 리포트",
            "bi_chart": "BI 차트",
            "workflow_create": "워크플로우 생성",
            "workflow_manage": "워크플로우 관리",
            "financial_report": "재무 보고서",
        }

        intent_name = intent_names.get(intent, intent)

        return (
            f"죄송합니다. '{intent_name}' 기능은 "
            f"{user_ctx.role_name} 권한으로 접근할 수 없습니다. "
            f"필요하시면 관리자에게 문의해 주세요."
        )

    def _check_data_scope(
        self,
        user_ctx: UserContext,
        slots: dict
    ) -> Optional[str]:
        """데이터 범위 경고 메시지"""
        warnings = []

        # 라인 범위 확인
        if user_ctx.line_restriction and 'line' in slots:
            if len(user_ctx.line_restriction) == 1:
                warnings.append(
                    f"현재 {user_ctx.line_restriction[0]} 라인 데이터만 조회 가능합니다."
                )

        # 시간 범위 확인
        if user_ctx.data_scope.time_range_days < 30:
            warnings.append(
                f"최근 {user_ctx.data_scope.time_range_days}일 데이터만 조회 가능합니다."
            )

        return " ".join(warnings) if warnings else None
```

---

## 6. API 엔드포인트

### 6.1 인증/인가 API

```python
# src/api/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional, List
import jwt
from datetime import datetime, timedelta

from src.auth.service import AuthorizationService
from src.auth.models import UserContext

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    tenant_id: str
    role: str


class UserInfo(BaseModel):
    user_id: str
    email: str
    name: str
    tenant_id: str
    tenant_name: str
    role_code: str
    role_name: str
    permissions: List[str]
    allowed_intents: List[str]
    data_scope: dict


@router.post("/token", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    tenant_code: str = None
):
    """로그인 및 토큰 발급"""
    # 인증 로직 (생략)
    # ...

    return TokenResponse(
        access_token=token,
        expires_in=3600,
        tenant_id=tenant_id,
        role=role_code
    )


@router.get("/me", response_model=UserInfo)
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    auth_service: AuthorizationService = Depends()
):
    """현재 사용자 정보 조회"""
    # 토큰 검증
    payload = verify_token(token)

    # 사용자 컨텍스트 로드
    ctx = await auth_service.get_user_context(
        payload['user_id'],
        payload['tenant_id']
    )

    return UserInfo(
        user_id=ctx.user_id,
        email=ctx.email,
        name=ctx.name,
        tenant_id=ctx.tenant_id,
        tenant_name="",  # 별도 조회
        role_code=ctx.role_code,
        role_name=ctx.role_name,
        permissions=list(ctx.permissions),
        allowed_intents=list(ctx.allowed_intents),
        data_scope={
            "organization_type": ctx.data_scope.organization_type,
            "time_range_days": ctx.data_scope.time_range_days,
            "sensitivity_levels": ctx.data_scope.sensitivity_levels
        }
    )


@router.get("/permissions/check")
async def check_permission(
    permission: str,
    token: str = Depends(oauth2_scheme),
    auth_service: AuthorizationService = Depends()
):
    """권한 확인"""
    payload = verify_token(token)
    ctx = await auth_service.get_user_context(
        payload['user_id'],
        payload['tenant_id']
    )

    return {
        "permission": permission,
        "allowed": ctx.has_permission(permission)
    }


@router.get("/intents/accessible")
async def get_accessible_intents(
    token: str = Depends(oauth2_scheme),
    auth_service: AuthorizationService = Depends()
):
    """접근 가능한 Intent 목록"""
    payload = verify_token(token)
    ctx = await auth_service.get_user_context(
        payload['user_id'],
        payload['tenant_id']
    )

    return {
        "allowed": list(ctx.allowed_intents),
        "excluded": list(ctx.excluded_intents)
    }
```

### 6.2 관리자 API

```python
# src/api/admin/roles.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID

router = APIRouter(prefix="/api/v1/admin/roles", tags=["Role Management"])


class RoleCreate(BaseModel):
    code: str
    name: str
    name_ko: Optional[str]
    template_id: UUID
    description: Optional[str]
    data_scope_override: Optional[dict]
    permissions_override: Optional[dict]
    intents_override: Optional[dict]


class RoleAssignment(BaseModel):
    user_id: UUID
    role_id: UUID
    scope_restriction: Optional[dict]
    expires_at: Optional[datetime]


@router.post("/")
async def create_role(
    role: RoleCreate,
    tenant_id: UUID = Depends(get_current_tenant)
):
    """커스텀 역할 생성"""
    # 권한 검증: tenant_admin 이상만
    # ...
    pass


@router.post("/assign")
async def assign_role(
    assignment: RoleAssignment,
    tenant_id: UUID = Depends(get_current_tenant)
):
    """사용자에게 역할 할당"""
    # 권한 검증
    # 감사 로그 기록
    # ...
    pass


@router.get("/templates")
async def list_role_templates():
    """역할 템플릿 목록 조회"""
    pass


@router.get("/{role_id}/users")
async def list_role_users(role_id: UUID):
    """역할에 할당된 사용자 목록"""
    pass
```

---

## 7. 역할별 화면 예시

### 7.1 권한별 응답 차이

```
┌─────────────────────────────────────────────────────────────────┐
│  [경영진 질문] "전체 공장 불량률 추이 분석해줘"                  │
├─────────────────────────────────────────────────────────────────┤
│  ✅ Intent: defect_analysis                                     │
│  ✅ Scope: 전체 공장 (5개)                                      │
│  ✅ 시간: 1년 추이                                              │
│  ✅ 응답: 전체 공장 비교 분석 + 비용 영향 + 전략 제안           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  [관리자 질문] "전체 공장 불량률 추이 분석해줘"                  │
├─────────────────────────────────────────────────────────────────┤
│  ⚠️ Intent: defect_analysis                                     │
│  ⚠️ Scope: 담당 부서로 제한됨                                   │
│  ✅ 시간: 1년 추이                                              │
│  ⚠️ 응답: "담당 부서(제조1팀) 데이터만 조회 가능합니다."        │
│           + 제조1팀 불량률 분석 결과                             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  [현장감독 질문] "전체 공장 불량률 추이 분석해줘"                │
├─────────────────────────────────────────────────────────────────┤
│  ⚠️ Intent: defect_analysis → 허용됨 (담당 라인 범위)           │
│  ⚠️ Scope: 담당 라인(L01, L02)으로 제한                         │
│  ⚠️ 시간: 30일로 제한                                           │
│  ⚠️ 응답: "L01, L02 라인의 최근 30일 데이터만 조회 가능합니다." │
│           + 담당 라인 불량률 분석                                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  [생산직 질문] "불량률 왜 올랐어?"                               │
├─────────────────────────────────────────────────────────────────┤
│  ❌ Intent: defect_analysis → 권한 없음                         │
│  ❌ 응답: "죄송합니다. '불량 원인 분석' 기능은 생산직 권한으로  │
│           접근할 수 없습니다. 품질 상태 확인은 가능합니다.      │
│           '품질 상태 알려줘'라고 말씀해 주세요."                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. 보안 고려사항

### 8.1 보안 원칙

| 원칙 | 설명 | 구현 방법 |
|------|------|----------|
| **최소 권한** | 필요한 최소한의 권한만 부여 | 기본 역할은 제한적, 필요 시 확장 |
| **권한 분리** | 민감 작업은 복수 권한 필요 | `required_permissions` 복수 설정 |
| **감사 추적** | 모든 권한 관련 활동 기록 | `authorization_audit_logs` 테이블 |
| **시간 제한** | 임시 권한은 만료일 설정 | `expires_at` 필드 활용 |
| **세션 관리** | 비활성 세션 자동 종료 | JWT 만료 + 세션 타임아웃 |

### 8.2 민감 데이터 마스킹

```python
# src/auth/data_masking.py

class DataMasker:
    """민감 데이터 마스킹"""

    MASKING_RULES = {
        'financial': {
            'fields': ['cost', 'revenue', 'profit', 'salary'],
            'min_level': 1,  # executive only
            'mask_value': '***'
        },
        'personal': {
            'fields': ['employee_name', 'phone', 'address'],
            'min_level': 2,  # manager+
            'mask_value': '***'
        },
        'strategic': {
            'fields': ['competitor_data', 'market_share', 'forecast'],
            'min_level': 1,
            'mask_value': '[Restricted]'
        }
    }

    def mask_response(
        self,
        data: dict,
        user_level: int
    ) -> dict:
        """응답 데이터 마스킹"""
        masked = data.copy()

        for category, rules in self.MASKING_RULES.items():
            if user_level > rules['min_level']:
                for field in rules['fields']:
                    if field in masked:
                        masked[field] = rules['mask_value']

        return masked
```

---

## 9. 관련 문서

- [E-3_Intent_Router_Prototype.md](E-3_Intent_Router_Prototype.md) - Intent Router 설계
- [E-6_Enterprise_Customization_Guide.md](E-6_Enterprise_Customization_Guide.md) - 기업별 커스터마이징
- [B-6_AI_Agent_Architecture_Prompt_Spec.md](B-6_AI_Agent_Architecture_Prompt_Spec.md) - Agent 아키텍처

---

## 문서 이력

| 버전 | 일자 | 작성자 | 변경 내용 |
|------|------|--------|-----------|
| 1.0 | 2025-12-14 | Security Team | 초기 Multi-Tenant 권한 설계 (RBAC+ABAC 하이브리드) |
| 2.0 | 2025-12-16 | Security Team | V7 Intent + Orchestrator 권한 통합: V7 Intent 14개별 권한 정책, Orchestrator Plan 실행 권한 계층, 15노드 타입별 접근 권한 매트릭스, Claude API 호출 권한 및 비용 할당, Route Target별 역할 기반 접근 제어 |
