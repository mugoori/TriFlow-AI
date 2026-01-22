# Advanced DataScope Filtering Guide

## 📋 목차

- [개요](#개요)
- [지원하는 필터](#지원하는-필터)
- [사용 방법](#사용-방법)
- [PostgreSQL RLS 정책](#postgresql-rls-정책)
- [테스트](#테스트)
- [보안 고려사항](#보안-고려사항)

---

## 개요

**Advanced DataScope Filtering**은 Triflow AI의 멀티테넌트 환경에서 사용자별 데이터 접근 범위를 세밀하게 제어하는 기능입니다.

### 핵심 기능

- ✅ **Factory Code 필터링**: 공장별 데이터 격리
- ✅ **Line Code 필터링**: 생산 라인별 데이터 격리
- ✅ **Product Family 필터링**: 제품군별 데이터 격리
- ✅ **Shift Code 필터링**: 근무 시프트별 데이터 격리
- ✅ **Equipment ID 필터링**: 설비별 데이터 격리
- ✅ **PostgreSQL RLS**: DB 레벨 보안 정책
- ✅ **Cross-Tenant 격리**: 테넌트 간 데이터 완전 격리

### 아키텍처

```
┌─────────────────────────────────────────────┐
│  Application Layer (FastAPI)               │
│  - DataScope Dependency                     │
│  - RBAC Service                             │
└─────────────┬───────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────┐
│  Service Layer                              │
│  - apply_line_filter()                      │
│  - apply_product_family_filter()            │
│  - apply_shift_filter()                     │
│  - apply_equipment_filter()                 │
│  - apply_data_scope_filter()                │
└─────────────┬───────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────┐
│  Database Layer (PostgreSQL RLS)            │
│  - Tenant isolation policy                  │
│  - Line code scope policy                   │
└─────────────────────────────────────────────┘
```

---

## 지원하는 필터

### 1. Factory Code 필터

공장별 데이터 접근 제어.

```python
from app.services.data_scope_service import DataScope

# 사용자 A: F001, F002 공장만 접근 가능
scope = DataScope(
    user_id="user-a",
    tenant_id="tenant-1",
    factory_codes={"F001", "F002"},
    all_access=False,
)

# 접근 권한 확인
scope.can_access_factory("F001")  # True
scope.can_access_factory("F003")  # False
```

### 2. Line Code 필터

생산 라인별 데이터 접근 제어.

```python
# 사용자 B: LINE_A, LINE_B만 접근 가능
scope = DataScope(
    user_id="user-b",
    tenant_id="tenant-1",
    line_codes={"LINE_A", "LINE_B"},
    all_access=False,
)

scope.can_access_line("LINE_A")  # True
scope.can_access_line("LINE_C")  # False
```

### 3. Product Family 필터

제품군별 데이터 접근 제어.

```python
# 사용자 C: FAMILY_A, FAMILY_B만 접근 가능
scope = DataScope(
    user_id="user-c",
    tenant_id="tenant-1",
    product_families={"FAMILY_A", "FAMILY_B"},
    all_access=False,
)

scope.can_access_product_family("FAMILY_A")  # True
scope.can_access_product_family("FAMILY_C")  # False
```

### 4. Shift Code 필터

근무 시프트별 데이터 접근 제어.

```python
# 사용자 D: DAY, EVENING 시프트만 접근 가능
scope = DataScope(
    user_id="user-d",
    tenant_id="tenant-1",
    shift_codes={"DAY", "EVENING"},
    all_access=False,
)

scope.can_access_shift("DAY")    # True
scope.can_access_shift("NIGHT")  # False
```

### 5. Equipment ID 필터

설비별 데이터 접근 제어.

```python
# 사용자 E: EQ001, EQ003 설비만 접근 가능
scope = DataScope(
    user_id="user-e",
    tenant_id="tenant-1",
    equipment_ids={"EQ001", "EQ003"},
    all_access=False,
)

scope.can_access_equipment("EQ001")  # True
scope.can_access_equipment("EQ002")  # False
```

### 6. Admin (전체 접근)

Admin 역할은 모든 데이터에 접근 가능.

```python
# Admin: 전체 접근
admin_scope = DataScope(
    user_id="admin-1",
    tenant_id="tenant-1",
    all_access=True,  # 전체 접근 권한
)

admin_scope.can_access_factory("F999")  # True
admin_scope.can_access_line("ANY_LINE")  # True
```

---

## 사용 방법

### 1. 사용자 메타데이터 설정

사용자 생성 시 `user_metadata`에 DataScope 정보를 설정합니다.

```python
from app.models import User

user = User(
    username="operator1",
    email="operator1@example.com",
    role="operator",
    tenant_id=tenant_id,
    user_metadata={
        "data_scope": {
            "factory_codes": ["F001", "F002"],
            "line_codes": ["LINE_A", "LINE_B", "LINE_C"],
            "product_families": ["FAMILY_A"],
            "shift_codes": ["DAY", "EVENING"],
            "equipment_ids": ["EQ001", "EQ003", "EQ005"],
            "all_access": False,
        }
    }
)
```

### 2. FastAPI Router에서 DataScope 사용

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.data_scope_service import DataScope, get_data_scope, apply_line_filter
from app.models import SensorData

router = APIRouter()

@router.get("/sensors")
async def get_sensors(
    db: Session = Depends(get_db),
    scope: DataScope = Depends(get_data_scope),  # 자동으로 현재 사용자의 DataScope 주입
):
    """센서 데이터 조회 (DataScope 필터 적용)"""

    # Base query
    query = db.query(SensorData)

    # DataScope 필터 적용 (사용자가 접근 가능한 라인만 조회)
    query = apply_line_filter(query, scope, SensorData.line_code)

    # 실행
    sensors = query.all()
    return sensors
```

### 3. 복합 필터 적용

여러 필터를 동시에 적용할 수 있습니다.

```python
from app.services.data_scope_service import apply_data_scope_filter
from app.models import Product

@router.get("/products")
async def get_products(
    db: Session = Depends(get_db),
    scope: DataScope = Depends(get_data_scope),
):
    """제품 조회 (Line Code + Product Family 필터)"""

    query = db.query(Product)

    # 복합 필터 적용
    query = apply_data_scope_filter(
        query,
        scope,
        line_code_column=Product.line_code,
        product_family_column=Product.family,
    )

    products = query.all()
    return products
```

### 4. In-Memory 리스트 필터링

DB 쿼리가 아닌 Python 리스트를 필터링할 때 사용합니다.

```python
from app.services.data_scope_service import filter_items_by_scope

@router.get("/dashboard")
async def get_dashboard(scope: DataScope = Depends(get_data_scope)):
    """대시보드 데이터 (In-memory 필터링)"""

    # 모든 제품 목록
    all_products = [
        {"id": "P001", "family": "FAMILY_A", "line": "LINE_A"},
        {"id": "P002", "family": "FAMILY_B", "line": "LINE_B"},
        {"id": "P003", "family": "FAMILY_A", "line": "LINE_C"},
    ]

    # DataScope 필터 적용
    accessible_products = filter_items_by_scope(
        all_products,
        scope,
        get_line_code=lambda x: x["line"],
        get_product_family=lambda x: x["family"],
    )

    return {"products": accessible_products}
```

---

## PostgreSQL RLS 정책

### 설치

PostgreSQL Row-Level Security 정책을 설치합니다.

```bash
psql -U postgres -d triflow_ai -f backend/sql/advanced_datascope_rls.sql
```

### 주요 정책

#### 1. Tenant 격리 정책

모든 테이블에 tenant_id 기반 격리 정책이 적용됩니다.

```sql
-- sensor_data 테이블 예시
CREATE POLICY sensor_data_tenant_isolation ON core.sensor_data
    USING (tenant_id::text = current_setting('app.current_tenant_id', true));
```

#### 2. Line Code 스코프 정책

Line Code 기반 데이터 접근 제어.

```sql
CREATE POLICY sensor_data_line_scope ON core.sensor_data
    FOR SELECT
    USING (
        current_setting('app.all_access', true)::boolean = true
        OR line_code = ANY(string_to_array(current_setting('app.line_codes', true), ','))
    );
```

### DataScope 세션 변수 설정

Application에서 PostgreSQL 세션 변수를 설정하여 RLS 정책을 제어합니다.

```python
from sqlalchemy import text

# DataScope 설정
db.execute(text("""
    SELECT core.set_data_scope(
        :tenant_id::uuid,
        ARRAY[:line_codes]::text[],
        :all_access
    )
"""), {
    "tenant_id": "tenant-a-uuid",
    "line_codes": "LINE_A,LINE_B",
    "all_access": False,
})

# 쿼리 실행 (RLS 정책 자동 적용)
sensors = db.query(SensorData).all()

# DataScope 초기화
db.execute(text("SELECT core.clear_data_scope()"))
```

---

## 테스트

### 단위 테스트 실행

```bash
cd backend
python test_advanced_datascope.py
```

### 테스트 항목

1. **Product Family 접근 제어**: Admin, Operator, Viewer 역할별 접근 권한
2. **Shift Code 접근 제어**: 시프트별 데이터 격리
3. **Equipment 접근 제어**: 설비별 데이터 격리
4. **In-memory 필터링**: Python 리스트 필터링
5. **복합 필터**: Line Code + Product Family 조합
6. **Cross-Tenant 격리**: 테넌트 간 데이터 격리

### 테스트 출력 예시

```
============================================================
Advanced DataScope Filtering Tests
============================================================

=== Test 1: Product Family Access Control ===
[OK] Admin has access to all product families
✅ Operator has limited access to product families
✅ Viewer has no product family access

=== Test 8: Cross-Tenant Isolation ===
✅ Cross-tenant isolation verified

============================================================
✅ ALL TESTS PASSED!
============================================================
```

---

## 보안 고려사항

### 1. 다층 방어 (Defense in Depth)

- **Application Layer**: DataScope 서비스
- **Database Layer**: PostgreSQL RLS 정책
- **Network Layer**: API Gateway, VPC

### 2. 최소 권한 원칙 (Least Privilege)

```python
# ❌ 나쁜 예: 모든 라인 접근 권한 부여
user_metadata = {
    "data_scope": {
        "all_access": True  # 불필요한 전체 접근
    }
}

# ✅ 좋은 예: 필요한 라인만 접근
user_metadata = {
    "data_scope": {
        "line_codes": ["LINE_A", "LINE_B"],  # 필요한 라인만
        "all_access": False
    }
}
```

### 3. Cross-Tenant 격리

```python
# 테넌트 A 사용자
tenant_a_scope = DataScope(
    user_id="user-1",
    tenant_id="tenant-a",  # 중요: 각 테넌트 ID 분리
    line_codes={"LINE_A"},
)

# 테넌트 B 사용자
tenant_b_scope = DataScope(
    user_id="user-2",
    tenant_id="tenant-b",  # 다른 테넌트 ID
    line_codes={"LINE_C"},
)

# tenant_a_scope로는 tenant-b 데이터 접근 불가
```

### 4. 감사 로그 (Audit Log)

모든 DataScope 필터링 작업은 audit_logs 테이블에 기록됩니다.

```python
from app.models import AuditLog

# DataScope 변경 시 감사 로그 생성
audit_log = AuditLog(
    tenant_id=tenant_id,
    actor_id=user_id,
    action="update",
    resource_type="data_scope",
    resource_id=str(user_id),
    after_state={
        "line_codes": ["LINE_A", "LINE_B"],
        "product_families": ["FAMILY_A"],
    }
)
db.add(audit_log)
db.commit()
```

---

## FAQ

### Q1. Admin도 DataScope 필터가 적용되나요?

A1. Admin은 `all_access=True`로 설정되어 모든 데이터에 접근 가능합니다.

```python
admin_scope = DataScope(
    user_id="admin-1",
    tenant_id="tenant-1",
    all_access=True,  # 전체 접근
)
```

### Q2. 여러 필터를 동시에 적용하면 AND인가요, OR인가요?

A2. 기본적으로 AND 조건입니다. 모든 필터를 만족해야 접근 가능합니다.

```python
# LINE_A AND FAMILY_A만 접근
scope = DataScope(
    line_codes={"LINE_A"},
    product_families={"FAMILY_A"},
    all_access=False,
)
```

### Q3. RLS 정책 없이도 DataScope가 작동하나요?

A3. 네, Application Layer의 DataScope 서비스만으로도 작동합니다. RLS는 추가 보안 계층입니다.

### Q4. 성능 영향은 없나요?

A4. PostgreSQL RLS는 인덱스를 활용하여 최적화됩니다. `line_code`, `tenant_id` 컬럼에 인덱스가 있으면 성능 영향이 미미합니다.

```sql
-- 인덱스 확인
CREATE INDEX IF NOT EXISTS idx_sensor_data_line_code ON core.sensor_data(line_code);
CREATE INDEX IF NOT EXISTS idx_sensor_data_tenant_id ON core.sensor_data(tenant_id);
```

---

## 참고 자료

- [REMAINING_TASKS_ROADMAP.md](../REMAINING_TASKS_ROADMAP.md) - Phase 1-2: Advanced DataScope Filtering
- [PROJECT_STATUS.md](../PROJECT_STATUS.md) - Top 5 과제: 멀티테넌트 격리
- [PostgreSQL RLS 공식 문서](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)

---

**작성일**: 2026-01-22
**버전**: 1.0.0
**작성자**: Triflow AI Team
