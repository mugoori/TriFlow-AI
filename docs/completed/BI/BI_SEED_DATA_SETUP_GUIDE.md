# 📊 BI 시드 데이터 설정 가이드

**목적**: BI 분석을 즉시 사용 가능하도록 시드 데이터 생성
**소요 시간**: 10-15분
**효과**: BI 쿼리 즉시 작동 ✅

---

## 🚀 빠른 시작 (3단계)

### Step 1: Dimension 시드 데이터 생성 (5분)

```bash
# PostgreSQL 데이터베이스에 연결하여 실행
psql -U postgres -d triflow_dev -f backend/sql/seed_bi_dimensions.sql
```

**생성되는 데이터**:
- ✅ dim_date: 3,650개 (2020-2030, 10년치)
- ✅ dim_shift: 3개 (A/B/C 교대)
- ✅ dim_line: 3개 (샘플 라인)
- ✅ dim_product: 5개 (샘플 제품)
- ✅ dim_equipment: 5개 (샘플 설비)
- ✅ dim_kpi: 8개 (KPI 정의)

**확인**:
```sql
SELECT 'dim_date', COUNT(*) FROM bi.dim_date;
-- 결과: 3650 ✅

SELECT * FROM bi.dim_line;
-- 결과: LINE-A, LINE-B, LINE-C ✅
```

---

### Step 2: FACT 샘플 데이터 생성 (5분)

```bash
# FACT 테이블에 30일치 샘플 데이터 생성
psql -U postgres -d triflow_dev -f backend/sql/seed_bi_sample_facts.sql
```

**생성되는 데이터**:
- ✅ fact_daily_production: 약 1,350개 (30일 × 3라인 × 5제품 × 3교대)
- ✅ fact_daily_defect: 불량 상세 데이터
- ✅ fact_inventory_snapshot: 150개 (30일 × 5제품)
- ✅ fact_equipment_event: 설비 이벤트

**데이터 패턴** (현실적인 시나리오):
- LINE-A + PROD-X 조합: 불량률 7-10% (문제 있음) 🔴
- 야간 교대 (C): 불량률 4-6% (주의) 🟡
- 기타: 불량률 1-3% (정상) 🟢

**확인**:
```sql
SELECT COUNT(*) FROM bi.fact_daily_production;
-- 결과: ~1350 ✅

SELECT
    line_code,
    ROUND(AVG(defect_qty::numeric / NULLIF(total_qty, 0) * 100), 2) AS avg_defect_rate
FROM bi.fact_daily_production
GROUP BY line_code;

-- 결과:
-- LINE-A: 5.2%  (PROD-X 때문에 높음)
-- LINE-B: 2.1%
-- LINE-C: 1.8%
```

---

### Step 3: BI 쿼리 테스트 (1분)

```sql
-- 불량률 추이 쿼리
SELECT
    d.date,
    l.name AS line_name,
    ROUND(SUM(f.defect_qty)::numeric / NULLIF(SUM(f.total_qty), 0) * 100, 2) AS defect_rate
FROM bi.fact_daily_production f
JOIN bi.dim_date d ON f.date = d.date
JOIN bi.dim_line l ON f.tenant_id = l.tenant_id AND f.line_code = l.line_code
WHERE d.date >= CURRENT_DATE - 7
GROUP BY d.date, l.name
ORDER BY d.date, l.name;

-- 결과: 데이터 나옴! ✅
```

---

## 📋 상세 실행 방법

### 환경별 실행 방법

#### 1. 로컬 PostgreSQL

```bash
# 1. PostgreSQL 연결 확인
psql -U postgres -l

# 2. 데이터베이스 선택
psql -U postgres -d triflow_dev

# 3. Dimension 시드 생성
\i backend/sql/seed_bi_dimensions.sql

# 4. FACT 샘플 생성
\i backend/sql/seed_bi_sample_facts.sql

# 5. 확인
SELECT COUNT(*) FROM bi.dim_date;
SELECT COUNT(*) FROM bi.fact_daily_production;
```

---

#### 2. Docker 환경

```bash
# Docker 컨테이너 확인
docker ps | grep postgres

# Dimension 시드
docker exec -i triflow-db psql -U postgres -d triflow_dev < backend/sql/seed_bi_dimensions.sql

# FACT 샘플
docker exec -i triflow-db psql -U postgres -d triflow_dev < backend/sql/seed_bi_sample_facts.sql

# 확인
docker exec -it triflow-db psql -U postgres -d triflow_dev -c "SELECT COUNT(*) FROM bi.dim_date"
```

---

#### 3. Alembic Migration으로 실행

```python
# backend/alembic/versions/015_seed_bi_data.py (선택적)

def upgrade():
    """BI 시드 데이터 생성"""
    import os
    from sqlalchemy import text

    conn = op.get_bind()

    # SQL 파일 읽기
    sql_file = os.path.join(os.path.dirname(__file__), '../../sql/seed_bi_dimensions.sql')
    with open(sql_file, 'r', encoding='utf-8') as f:
        sql = f.read()

    # 실행
    conn.execute(text(sql))
    conn.commit()

# 실행
alembic upgrade head
```

---

## ✅ 생성된 데이터 확인

### 1. Dimension 테이블

```sql
-- dim_date 확인
SELECT
    date,
    year,
    quarter,
    day_name,
    is_weekend
FROM bi.dim_date
WHERE date >= '2026-01-20'
ORDER BY date
LIMIT 5;

-- 결과:
-- 2026-01-20 | 2026 | 1 | Tuesday   | false
-- 2026-01-21 | 2026 | 1 | Wednesday | false
-- 2026-01-22 | 2026 | 1 | Thursday  | false
-- ...

-- dim_shift 확인
SELECT * FROM bi.dim_shift;

-- 결과:
-- A | 주간 | 08:00 | 16:00 | false
-- B | 오후 | 16:00 | 00:00 | false
-- C | 야간 | 00:00 | 08:00 | true

-- dim_line 확인
SELECT * FROM bi.dim_line;

-- 결과:
-- LINE-A | A 라인 | Assembly   | 5000
-- LINE-B | B 라인 | Packaging  | 3000
-- LINE-C | C 라인 | Inspection | 2000
```

---

### 2. FACT 테이블

```sql
-- 최근 데이터 확인
SELECT
    date,
    line_code,
    product_code,
    shift,
    total_qty,
    defect_qty,
    ROUND(defect_qty::numeric / NULLIF(total_qty, 0) * 100, 2) AS defect_rate
FROM bi.fact_daily_production
WHERE date >= CURRENT_DATE - 3
ORDER BY date DESC, line_code, product_code
LIMIT 10;

-- LINE-A + PROD-X 조합이 불량률 높은지 확인
SELECT
    line_code,
    product_code,
    AVG(defect_qty::numeric / NULLIF(total_qty, 0) * 100) AS avg_defect_rate
FROM bi.fact_daily_production
WHERE date >= CURRENT_DATE - 30
GROUP BY line_code, product_code
HAVING AVG(defect_qty::numeric / NULLIF(total_qty, 0)) > 0.05  -- 5% 이상
ORDER BY avg_defect_rate DESC;

-- 결과:
-- LINE-A | PROD-X | 8.5%  ← 문제 있음!
-- LINE-A | PROD-Y | 5.2%
```

---

## 🎯 BI 기능 테스트

### 1. API로 불량률 분석

```bash
curl -X POST http://localhost:8000/api/v1/bi/chat \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "최근 7일 불량률 추이 보여줘",
    "session_id": "test-session"
  }'
```

**예상 응답**:
```json
{
  "insight": "최근 7일 평균 불량률 4.8%\nLINE-A의 PROD-X가 가장 높음 (8.5%)\n야간 교대가 주간 대비 2배 높음",
  "chart": {
    "type": "line",
    "data": [...]
  },
  "recommendations": [
    "LINE-A 설비 점검 필요",
    "PROD-X 공정 파라미터 재조정",
    "야간 교대 관리 강화"
  ]
}
```

**데이터 소스**: 방금 생성한 샘플 데이터! ✅

---

### 2. RANK 분석 테스트

```bash
curl -X POST http://localhost:8000/api/v1/bi/rank \
  -d '{
    "metric": "defect_rate",
    "dimension": "line",
    "top_n": 5,
    "order": "desc"
  }'
```

**예상 응답**:
```json
{
  "analysis_type": "rank",
  "results": [
    {"line": "LINE-A", "defect_rate": 0.085, "percentile": 95},
    {"line": "LINE-B", "defect_rate": 0.021, "percentile": 50},
    {"line": "LINE-C", "defect_rate": 0.018, "percentile": 25}
  ],
  "chart": {...}
}
```

---

## 🔍 트러블슈팅

### 문제 1: "No tenant found"

**증상**:
```
NOTICE: No tenant found. Create tenant first.
```

**해결**:
```sql
-- tenant 생성
INSERT INTO core.tenants (tenant_id, name, is_active)
VALUES (gen_random_uuid(), 'Demo Tenant', true);

-- 다시 실행
\i backend/sql/seed_bi_dimensions.sql
```

---

### 문제 2: "Relation does not exist"

**증상**:
```
ERROR: relation "bi.dim_date" does not exist
```

**해결**:
```bash
# Migration 먼저 실행
cd backend
alembic upgrade head

# 그 다음 시드 데이터
psql ... < seed_bi_dimensions.sql
```

---

### 문제 3: JOIN 결과 없음

**증상**:
```sql
SELECT ... FROM fact JOIN dim_date ...
-- 결과: 0 rows
```

**확인**:
```sql
-- 1. FACT에 데이터 있는지
SELECT COUNT(*) FROM bi.fact_daily_production;
-- 0이면: seed_bi_sample_facts.sql 실행

-- 2. DIM에 데이터 있는지
SELECT COUNT(*) FROM bi.dim_date;
-- 0이면: seed_bi_dimensions.sql 실행

-- 3. 날짜 범위 확인
SELECT MIN(date), MAX(date) FROM bi.fact_daily_production;
SELECT MIN(date), MAX(date) FROM bi.dim_date;
-- 범위가 겹치는지 확인
```

---

## 📊 생성된 데이터 통계

### Dimension 테이블

| 테이블 | 개수 | 내용 |
|--------|------|------|
| dim_date | 3,650 | 2020-2030 날짜 |
| dim_shift | 3 | A/B/C 교대 |
| dim_line | 3 | LINE-A/B/C |
| dim_product | 5 | PROD-X/Y/Z/W/V |
| dim_equipment | 5 | EQ-501~505 |
| dim_kpi | 8 | 불량률, OEE 등 |

---

### FACT 테이블 (30일치)

| 테이블 | 개수 | 내용 |
|--------|------|------|
| fact_daily_production | ~1,350 | 일일 생산 실적 |
| fact_daily_defect | ~500 | 불량 상세 |
| fact_inventory_snapshot | 150 | 일별 재고 |
| fact_equipment_event | ~100 | 설비 이벤트 |

---

## 🎯 시드 데이터 패턴

### 현실적인 문제 시나리오 포함

**1. LINE-A + PROD-X 조합 문제**
```
불량률: 7-10% (정상 3% 대비 높음) 🔴
→ BI 인사이트: "LINE-A의 PROD-X 불량률 높음, 원인 조사 필요"
```

**2. 야간 교대 문제**
```
야간 (C): 4-6% 불량
주간 (A): 2-3% 불량
→ BI 인사이트: "야간 교대 불량률 2배 높음, 관리 강화 필요"
```

**3. 설비 비가동 패턴**
```
EQ-501: 월 3-4회 비가동
→ BI 인사이트: "EQ-501 잦은 비가동, 예방 정비 필요"
```

---

## ✅ 실행 후 테스트

### 1. Dimension JOIN 테스트

```sql
-- 날짜 JOIN 테스트
SELECT
    f.date,
    d.year,
    d.quarter,
    d.day_name,
    COUNT(*)
FROM bi.fact_daily_production f
JOIN bi.dim_date d ON f.date = d.date
GROUP BY f.date, d.year, d.quarter, d.day_name
ORDER BY f.date DESC
LIMIT 5;

-- 결과 나오면 성공! ✅
```

---

### 2. BI API 테스트

```bash
# GenBI 테스트
curl -X POST http://localhost:8000/api/v1/bi/chat \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "오늘 생산 현황 보여줘",
    "session_id": "test-123"
  }'

# 응답 확인:
# ✅ 인사이트 생성됨
# ✅ 차트 데이터 있음
# ✅ 추천 사항 있음
```

---

### 3. 분석 기능 테스트

```bash
# RANK 분석
curl -X POST http://localhost:8000/api/v1/bi/rank \
  -d '{
    "metric": "defect_rate",
    "dimension": "line",
    "top_n": 3
  }'

# PREDICT 분석
curl -X POST http://localhost:8000/api/v1/bi/predict \
  -d '{
    "metric": "defect_rate",
    "time_dimension": "date",
    "prediction_periods": 7
  }'

# WHAT_IF 분석
curl -X POST http://localhost:8000/api/v1/bi/what-if \
  -d '{
    "target_metric": "production_qty",
    "scenarios": [
      {"factor": "line_downtime", "change": -20}
    ]
  }'
```

---

## 📝 다음 단계 (선택적)

### 1. Mock 데이터로 FACT 추가 (선택)

```bash
# Mock API로 추가 데이터 생성
curl -X POST http://localhost:8000/api/v1/erp-mes/mock/generate \
  -d '{
    "source_type": "mes",
    "record_type": "work_order",
    "count": 100
  }'

# Mock → FACT 변환 (수동 SQL 또는 ETL 서비스)
```

---

### 2. Materialized Views 생성 (성능 향상)

```sql
-- backend/sql/create_materialized_views.sql 생성 후
psql < backend/sql/create_materialized_views.sql

-- MV 리프레시
REFRESH MATERIALIZED VIEW bi.mv_defect_trend;
```

---

### 3. 캐싱 활성화 (성능 향상)

```python
# backend/app/services/bi_service.py 수정
# Redis 캐싱 주석 해제
```

---

## 🎉 완료 확인

### 체크리스트

- [ ] dim_date에 3,650개 레코드 있음
- [ ] dim_shift에 3개 레코드 있음
- [ ] dim_line에 3개 레코드 있음
- [ ] fact_daily_production에 ~1,350개 레코드 있음
- [ ] BI 쿼리 실행 시 결과 나옴 (0개 아님)
- [ ] BI Chat API 호출 시 인사이트 생성됨
- [ ] RANK/PREDICT/WHAT_IF 분석 작동함

**모두 체크되면**: ✅ BI 시스템 즉시 사용 가능!

---

## 🚀 실행 명령 요약

```bash
# 한 번에 실행
cd /c/dev/triflow-ai

# 1. Dimension 시드
psql -U postgres -d triflow_dev -f backend/sql/seed_bi_dimensions.sql

# 2. FACT 샘플
psql -U postgres -d triflow_dev -f backend/sql/seed_bi_sample_facts.sql

# 3. 확인
psql -U postgres -d triflow_dev -c "
    SELECT 'dim_date', COUNT(*) FROM bi.dim_date
    UNION ALL
    SELECT 'dim_line', COUNT(*) FROM bi.dim_line
    UNION ALL
    SELECT 'fact_daily_production', COUNT(*) FROM bi.fact_daily_production;
"

# 결과:
# dim_date                | 3650
# dim_line                | 3
# fact_daily_production   | 1350
```

---

**시드 데이터 생성 완료 후 BI 즉시 사용 가능!** ✅
