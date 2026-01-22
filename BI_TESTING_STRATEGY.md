# 📊 BI 테스트 전략: Mock 데이터 활용

**핵심 질문**: MES/ERP 연결 안 되어 있는데 어떻게 테스트하는가?

**답변**: ✅ **Mock 데이터 생성 API를 사용합니다!**

---

## 🎯 현재 상황 정리

### 현재 상태
```
MES/ERP 시스템: ❌ 미연결 (V2 예정)
Mock 데이터 API: ✅ 완벽 구현됨!
BI 분석 엔진: ✅ 완벽 구현됨!
```

### 테스트 전략
```
실제 MES/ERP 대신 → Mock 데이터 생성 API 사용
```

---

## 🔧 Mock 데이터 생성 API

### 제공되는 Mock 데이터 타입

**파일**: `backend/app/routers/erp_mes.py:146-276`

#### ERP Mock 데이터 (3가지)
1. **`production_order`** - SAP 스타일 생산 오더
2. **`inventory`** - Oracle 스타일 재고
3. **`bom`** - 자재명세서 (Bill of Materials)

#### MES Mock 데이터 (3가지)
1. **`work_order`** - 작업 지시서
2. **`equipment_status`** - 설비 상태
3. **`quality_record`** - 품질 검사 기록

---

## 📝 Mock 데이터 생성 방법

### API 엔드포인트

```
POST /api/v1/erp-mes/mock/generate
```

### 사용 예시

#### 1. MES 작업 지시서 100개 생성

```bash
curl -X POST http://localhost:8000/api/v1/erp-mes/mock/generate \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "mes",
    "source_system": "mock_mes",
    "record_type": "work_order",
    "count": 100
  }'
```

**응답**:
```json
{
  "generated_count": 100,
  "source_type": "mes",
  "source_system": "mock_mes",
  "record_type": "work_order",
  "sample_data": [
    {
      "work_order_id": "WO20260122123",
      "production_line": "LINE-A",
      "product_code": "PROD-1234",
      "planned_quantity": 500,
      "produced_quantity": 450,
      "defect_quantity": 25,
      "status": "in_progress",
      "shift": "day"
    },
    ...
  ]
}
```

**저장 위치**: `core.erp_mes_data` 테이블

---

#### 2. ERP 재고 데이터 50개 생성

```bash
curl -X POST http://localhost:8000/api/v1/erp-mes/mock/generate \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "erp",
    "source_system": "Oracle_EBS",
    "record_type": "inventory",
    "count": 50
  }'
```

**생성되는 데이터**:
```json
{
  "INVENTORY_ITEM_ID": 12345,
  "ITEM_NUMBER": "ITEM-5678",
  "ON_HAND_QTY": 3500,
  "RESERVED_QTY": 500,
  "AVAILABLE_QTY": 3000,
  "UOM_CODE": "EA",
  "LOT_NUMBER": "LOT202601234",
  "EXPIRATION_DATE": "2026-12-31"
}
```

---

#### 3. MES 품질 검사 기록 200개 생성

```bash
curl -X POST http://localhost:8000/api/v1/erp-mes/mock/generate \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "mes",
    "source_system": "mock_mes",
    "record_type": "quality_record",
    "count": 200
  }'
```

**생성되는 데이터**:
```json
{
  "inspection_id": "QC20260122001",
  "product_code": "PROD-2345",
  "sample_size": 50,
  "passed_count": 45,
  "failed_count": 5,
  "defect_types": ["scratch", "dimension"],
  "result": "pass",
  "measurements": {
    "dimension_a": 99.87,
    "dimension_b": 50.12,
    "weight": 1.003
  }
}
```

---

## 🔄 BI 테스트 워크플로우

### Step 1: Mock 데이터 생성

```bash
# 1. MES 작업 지시서 생성 (최근 30일치)
POST /api/v1/erp-mes/mock/generate
{
  "source_type": "mes",
  "record_type": "work_order",
  "count": 300  // 30일 × 10개/일
}

# 2. ERP 재고 데이터 생성
POST /api/v1/erp-mes/mock/generate
{
  "source_type": "erp",
  "record_type": "inventory",
  "count": 50
}

# 3. MES 품질 검사 기록 생성
POST /api/v1/erp-mes/mock/generate
{
  "source_type": "mes",
  "record_type": "quality_record",
  "count": 500
}
```

**결과**: `core.erp_mes_data` 테이블에 850개 Mock 데이터 저장

---

### Step 2: Mock 데이터 → BI FACT 변환

**현재**: ❌ ETL 미구현

**해결 방법 A: 수동 SQL로 변환** (즉시 가능)
```sql
-- Mock 데이터 → fact_daily_production 변환
INSERT INTO bi.fact_daily_production (
    tenant_id, date, line_code, product_code, shift,
    total_qty, good_qty, defect_qty
)
SELECT
    tenant_id,
    DATE((raw_data->>'scheduled_start')::timestamp) AS date,
    raw_data->>'production_line' AS line_code,
    raw_data->>'product_code' AS product_code,
    raw_data->>'shift' AS shift,
    (raw_data->>'planned_quantity')::numeric AS total_qty,
    (raw_data->>'produced_quantity')::numeric AS good_qty,
    (raw_data->>'defect_quantity')::numeric AS defect_qty
FROM core.erp_mes_data
WHERE record_type = 'work_order'
  AND raw_data->>'status' = 'completed'
GROUP BY 1, 2, 3, 4, 5;
```

**해결 방법 B: Python ETL 스크립트** (1-2시간)
```python
# backend/scripts/convert_mock_to_fact.py (신규)

from app.database import SessionLocal
from app.models.core import ErpMesData
from app.models.bi import FactDailyProduction

db = SessionLocal()

# Mock 데이터 조회
mock_data = db.query(ErpMesData).filter(
    ErpMesData.record_type == 'work_order',
    ErpMesData.raw_data['status'] == 'completed'
).all()

# FACT로 변환
for data in mock_data:
    fact = FactDailyProduction(
        tenant_id=data.tenant_id,
        date=parse_date(data.raw_data['scheduled_start']),
        line_code=data.raw_data['production_line'],
        product_code=data.raw_data['product_code'],
        total_qty=data.raw_data['planned_quantity'],
        good_qty=data.raw_data['produced_quantity'],
        defect_qty=data.raw_data['defect_quantity'],
    )
    db.add(fact)

db.commit()
print(f"✅ Converted {len(mock_data)} records to FACT")
```

---

### Step 3: BI 분석 실행

```bash
# BI 채팅 분석
POST /api/v1/bi/chat
{
  "message": "최근 7일 불량률 추이 보여줘",
  "session_id": "session-123"
}

# 응답: Mock 데이터 기반 인사이트!
{
  "insight": "최근 7일 평균 불량률 5.2% (LINE-A가 가장 높음 8.5%)",
  "chart": {...},
  "recommendations": [...]
}
```

---

## 🎬 실제 테스트 시나리오

### Scenario: "불량률 분석 데모"

#### Step 1: 환경 준비 (5분)

```bash
# 1. 차원 데이터 생성
INSERT INTO bi.dim_line VALUES
('LINE-A', 'A 라인', 'Assembly', 1),
('LINE-B', 'B 라인', 'Assembly', 2),
('LINE-C', 'C 라인', 'Packaging', 3);

INSERT INTO bi.dim_product VALUES
('PROD-X', '제품X', '전자부품', 'Type-A'),
('PROD-Y', '제품Y', '기계부품', 'Type-B');

INSERT INTO bi.dim_date
SELECT generate_series(
    '2026-01-01'::date,
    '2026-01-31'::date,
    '1 day'::interval
)::date;
```

---

#### Step 2: Mock MES 데이터 생성 (1분)

```bash
# MES 작업 지시서 300개 생성 (30일치)
curl -X POST http://localhost:8000/api/v1/erp-mes/mock/generate \
  -d '{
    "source_type": "mes",
    "record_type": "work_order",
    "count": 300
  }'

# 결과:
# ✅ 300개 Mock Work Order 생성
```

---

#### Step 3: Mock → FACT 변환 (1분)

```sql
-- Python 스크립트 또는 SQL로 변환
INSERT INTO bi.fact_daily_production
SELECT ... FROM core.erp_mes_data WHERE record_type = 'work_order';

-- 결과:
-- ✅ fact_daily_production에 30일치 데이터 생성
```

---

#### Step 4: BI 분석 실행 (즉시)

```bash
# 불량률 추이 분석
curl -X POST http://localhost:8000/api/v1/bi/chat \
  -d '{
    "message": "최근 7일 불량률 추이 보여줘"
  }'

# 응답:
{
  "insight": "
    최근 7일 평균 불량률 5.2%
    LINE-A의 PROD-X가 가장 높음 (8.5%)
    지난 3일간 상승 추세 (+1.2%p)
  ",
  "chart": {
    "type": "line",
    "data": [
      {"date": "01-16", "LINE-A": 7.8, "LINE-B": 3.2},
      {"date": "01-17", "LINE-A": 8.1, "LINE-B": 3.5},
      ...
    ]
  },
  "recommendations": [
    "LINE-A 설비 점검",
    "PROD-X 공정 파라미터 검토"
  ]
}
```

**데이터 소스**: Mock MES 데이터! ✅

---

## 📊 Mock 데이터 품질

### 현실성 높은 Mock 데이터

**특징**:
1. **실제 시스템 스타일**
   - SAP 필드명 (AUFNR, MATNR, WERKS)
   - Oracle 필드명 (INVENTORY_ITEM_ID, ORGANIZATION_ID)
   - MES 실무 용어 (work_order_id, OEE, cycle_time)

2. **시간 분포**
   - 최근 30일간 분산 생성
   - 시프트별 분산 (day/evening/night)
   - 현실적인 시간 간격

3. **현실적인 값 범위**
   - 생산량: 100~10,000
   - 불량률: 0~5% (정상), 5~10% (주의)
   - OEE: 60~95%
   - 사이클 타임: 10~120초

4. **상관관계 시뮬레이션**
   - 특정 라인에 불량 집중
   - 특정 제품에 문제 집중
   - 설비 비가동 시 생산 감소

---

## 🚀 즉시 테스트 가능한 방법

### 방법 1: 간단한 Mock 데이터 (10분)

```bash
# 1. Mock 데이터 생성 API 호출
curl -X POST .../mock/generate -d '{
  "source_type": "mes",
  "record_type": "work_order",
  "count": 100
}'

# 2. Python으로 FACT 변환
python backend/scripts/convert_mock_to_fact.py

# 3. BI 분석 테스트
curl -X POST .../bi/chat -d '{"message": "불량률 보여줘"}'

# ✅ Mock 데이터 기반 인사이트 생성!
```

---

### 방법 2: 완전한 시드 데이터 (1시간)

**생성 스크립트**: `backend/sql/seed_bi_with_mock_data.sql` (신규 필요)

```sql
-- 1. 차원 데이터
INSERT INTO bi.dim_date SELECT ...;  -- 10년치
INSERT INTO bi.dim_line VALUES (...);  -- 3개 라인
INSERT INTO bi.dim_product VALUES (...);  -- 10개 제품
INSERT INTO bi.dim_equipment VALUES (...);  -- 20개 설비

-- 2. FACT 데이터 (Mock MES 시뮬레이션)
INSERT INTO bi.fact_daily_production
SELECT
    gen_random_uuid() AS tenant_id,
    d.date,
    'LINE-' || (ARRAY['A','B','C'])[floor(random()*3+1)::int] AS line_code,
    'PROD-' || floor(random()*10+1)::int AS product_code,
    (ARRAY['A','B','C'])[floor(random()*3+1)::int] AS shift,
    floor(random()*1000+500)::numeric AS total_qty,
    floor(random()*900+450)::numeric AS good_qty,
    floor(random()*100)::numeric AS defect_qty,
    floor(random()*420+60)::numeric AS runtime_minutes,
    floor(random()*60)::numeric AS downtime_minutes
FROM bi.dim_date d
WHERE d.date >= CURRENT_DATE - 30
CROSS JOIN generate_series(1, 3);  -- 라인 3개 × 30일 = 90개 레코드

-- 3. 불량 상세 (Mock)
INSERT INTO bi.fact_daily_defect
SELECT ... ;

-- 4. 재고 스냅샷 (Mock ERP)
INSERT INTO bi.fact_inventory_snapshot
SELECT ... ;
```

**실행**:
```bash
psql -U postgres triflow < backend/sql/seed_bi_with_mock_data.sql

# ✅ 완전한 테스트 환경 구축 완료!
```

---

### 방법 3: Python 시뮬레이터 (2시간)

**파일**: `backend/scripts/bi_data_simulator.py` (신규 필요)

```python
"""
BI 테스트 데이터 시뮬레이터
현실적인 생산 데이터를 시뮬레이션하여 생성
"""
import random
from datetime import datetime, timedelta
from app.database import SessionLocal
from app.models.bi import *

class BiDataSimulator:
    """BI 테스트 데이터 생성"""

    def simulate_production_month(self, year=2026, month=1):
        """1개월치 생산 데이터 시뮬레이션"""

        lines = ['LINE-A', 'LINE-B', 'LINE-C']
        products = ['PROD-X', 'PROD-Y', 'PROD-Z']
        shifts = ['A', 'B', 'C']

        for day in range(1, 32):
            date = f"{year}-{month:02d}-{day:02d}"

            for line in lines:
                for product in products:
                    for shift in shifts:
                        # 현실적인 데이터 생성
                        base_qty = random.randint(800, 1200)

                        # LINE-A에 불량 집중 (현실적 패턴)
                        if line == 'LINE-A' and product == 'PROD-X':
                            defect_rate = random.uniform(0.08, 0.12)  # 8-12% 불량
                        else:
                            defect_rate = random.uniform(0.01, 0.03)  # 1-3% 정상

                        total_qty = base_qty
                        defect_qty = int(base_qty * defect_rate)
                        good_qty = total_qty - defect_qty

                        # FACT 레코드 생성
                        fact = FactDailyProduction(
                            tenant_id=tenant_id,
                            date=date,
                            line_code=line,
                            product_code=product,
                            shift=shift,
                            total_qty=total_qty,
                            good_qty=good_qty,
                            defect_qty=defect_qty,
                            runtime_minutes=random.randint(400, 460),
                            downtime_minutes=random.randint(10, 80),
                        )
                        db.add(fact)

        db.commit()
        print(f"✅ Generated 1 month of production data")

# 실행
simulator = BiDataSimulator()
simulator.simulate_production_month(2026, 1)
```

**장점**:
- 현실적인 패턴 (특정 라인에 불량 집중)
- 상관관계 시뮬레이션 (설비 비가동 ↔ 불량)
- 계절성 반영 가능

---

## 🎯 추천 테스트 방법

### **즉시 테스트 (10분)** ⭐⭐⭐⭐⭐

```bash
# Step 1: Mock API로 데이터 생성 (1분)
curl -X POST .../mock/generate -d '{...}'

# Step 2: 간단한 SQL 변환 (2분)
psql -c "INSERT INTO bi.fact_daily_production SELECT ..."

# Step 3: BI 분석 테스트 (1분)
curl -X POST .../bi/chat -d '{"message": "불량률 보여줘"}'

# Step 4: 결과 확인
# ✅ Mock 데이터 기반 인사이트 생성됨!
```

**완료 후**:
- ✅ BI가 작동하는지 확인 가능
- ✅ GenBI 인사이트 품질 확인
- ✅ 데모 가능

---

### **완전한 시드 데이터 (1시간)** ⭐⭐⭐⭐⭐

```sql
-- backend/sql/seed_bi_complete.sql (신규 생성 필요)

-- 1. 차원 데이터 (10년치, 3개 라인, 10개 제품)
-- 2. FACT 데이터 (최근 90일, 현실적 패턴)
-- 3. Materialized Views 생성
-- 4. 인덱스 생성
```

**실행**:
```bash
psql -U postgres triflow < backend/sql/seed_bi_complete.sql

# ✅ 완전한 BI 테스트 환경 구축!
```

**완료 후**:
- ✅ 모든 BI 기능 테스트 가능
- ✅ 성능 테스트 가능
- ✅ 고객 데모 가능

---

## 💡 핵심 정리

### 질문: MES/ERP 연결 안 되어 있는데 어떻게 테스트?

**답변**:

**1. Mock 데이터 생성 API 사용** ✅
```
POST /api/v1/erp-mes/mock/generate
→ 실제 MES/ERP 데이터처럼 생성
→ SAP/Oracle 필드명 사용
→ 현실적인 값 범위
```

**2. Mock → FACT 변환** (필요)
```
Option A: SQL로 수동 변환 (즉시)
Option B: Python 스크립트 (1-2h)
Option C: ETL 서비스 구현 (6-8h)
```

**3. BI 분석 실행** ✅
```
POST /api/v1/bi/chat
→ Mock 데이터 기반 분석
→ 인사이트 생성
```

---

### 현재 상태

```
MES/ERP 연결: ❌ (V2 예정)
Mock API: ✅ (완벽 구현)
BI 엔진: ✅ (완벽 구현)
데이터: ❌ (비어있음)
```

**필요한 작업**:
```
1. Mock 데이터 생성 (API 호출)
2. Mock → FACT 변환 (SQL 또는 스크립트)
3. BI 테스트 (즉시 가능)
```

---

## 🚀 즉시 시작 방법

### 가장 빠른 방법 (10분)

```bash
# 1. Mock 생성
curl -X POST .../mock/generate -d '{...}'

# 2. 수동 SQL 변환
psql -c "INSERT INTO bi.fact_daily_production ..."

# 3. BI 테스트
curl .../bi/chat -d '{"message": "불량률"}'
```

**결과**: Mock 데이터로 BI 작동 확인! ✅

---

**Mock 데이터 생성 API가 이미 완벽하게 준비되어 있어서, 실제 MES/ERP 없이도 BI를 테스트할 수 있습니다!** ✅

시드 데이터 생성 스크립트를 만드시겠습니까?