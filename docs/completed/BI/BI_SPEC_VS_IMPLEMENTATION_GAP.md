# 📊 BI 스펙 vs 구현 갭 분석 및 구현 항목

**분석 일시**: 2026-01-22
**결론**: BI 엔진은 완벽하지만, **데이터 파이프라인**이 부족합니다.

---

## 🎯 핵심 결론

### ✅ 완벽하게 구현된 것 (스펙 초과!)

1. **GenBI (대화형 BI)** - AWS QuickSight 수준 ⭐⭐⭐⭐⭐
2. **RANK/PREDICT/WHAT_IF 분석** - 고급 통계 분석 ⭐⭐⭐⭐⭐
3. **Star Schema** - 23개 테이블 모두 구현 ⭐⭐⭐⭐⭐
4. **Text-to-SQL** - 자연어 → SQL 변환 ⭐⭐⭐⭐⭐

### ❌ 구현해야 할 것 (데이터 파이프라인)

1. **시드 데이터** - dim_date, dim_shift 등
2. **ETL 파이프라인** - RAW → FACT 변환
3. **Materialized Views** - 성능 최적화
4. **캐싱 연동** - Redis 활성화

---

## 📋 구현해야 할 항목 (우선순위별)

### 🔴 P0 - 즉시 구현 필요 (BI 작동 필수)

#### 1. 시드 데이터 생성 ⭐⭐⭐⭐⭐

**스펙 요구**:
- B-3-2 § 3.1: dim_date (2020-2030, 10년치)
- B-3-2 § 3.6: dim_shift (3교대 기본값)

**현재 상태**:
```sql
-- dim_date, dim_shift 테이블 비어있음
SELECT COUNT(*) FROM bi.dim_date;
-- 결과: 0 ❌

SELECT COUNT(*) FROM bi.dim_shift;
-- 결과: 0 ❌
```

**문제**:
```sql
-- BI 쿼리 실패!
SELECT
    d.date,
    SUM(f.total_qty)
FROM bi.fact_daily_production f
JOIN bi.dim_date d ON f.date = d.date  -- ❌ dim_date 비어있어서 결과 없음!
```

**구현 방법**:
```sql
-- 파일: backend/sql/seed_bi_dimensions.sql

-- dim_date (2020-2030)
INSERT INTO bi.dim_date (
    date, year, quarter, month, week,
    day_of_year, day_of_month, day_of_week, day_name,
    is_weekend, is_holiday
)
SELECT
    d::date,
    EXTRACT(year FROM d)::int,
    EXTRACT(quarter FROM d)::int,
    EXTRACT(month FROM d)::int,
    EXTRACT(week FROM d)::int,
    EXTRACT(doy FROM d)::int,
    EXTRACT(day FROM d)::int,
    EXTRACT(dow FROM d)::int,
    TRIM(to_char(d, 'Day')),
    EXTRACT(dow FROM d) IN (0, 6),
    FALSE
FROM generate_series('2020-01-01'::date, '2030-12-31'::date, '1 day') d
ON CONFLICT (date) DO NOTHING;

-- 10년 × 365일 = 3,650개 레코드

-- dim_shift (3교대)
-- 각 tenant별로 실행
INSERT INTO bi.dim_shift (tenant_id, shift_code, name, start_time, end_time, ...)
VALUES
    (:tenant_id, 'A', '주간', '08:00', '16:00', 8.0, FALSE, 1),
    (:tenant_id, 'B', '오후', '16:00', '00:00', 8.0, FALSE, 2),
    (:tenant_id, 'C', '야간', '00:00', '08:00', 8.0, TRUE, 3)
ON CONFLICT DO NOTHING;
```

**예상 시간**: 1시간
**우선순위**: ⭐⭐⭐⭐⭐ (최우선)

---

#### 2. RAW → FACT ETL 파이프라인 ⭐⭐⭐⭐⭐

**스펙 요구**:
- B-3-2 § 7.3: RAW → FACT 변환 로직
- B-3-2 § 8.2: ETL 실행 및 모니터링

**현재 상태**:
```python
# ETL 메타데이터 테이블만 존재
class EtlJob(Base):  # ✅ 존재
class EtlJobExecution(Base):  # ✅ 존재

# 하지만 실제 ETL 실행 서비스 없음
# backend/app/services/etl_service.py ❌ 없음!
```

**문제**:
```
Mock API로 생성한 데이터:
core.erp_mes_data (300개 work_order)
   ↓
❌ RAW → FACT 변환 로직 없음!
   ↓
bi.fact_daily_production (비어있음)
   ↓
BI 쿼리 실패 (데이터 없음)
```

**구현 방법**:
```python
# 파일: backend/app/services/etl_service.py (신규)

class ETLService:
    async def run_raw_to_fact_daily_production(
        self,
        tenant_id: UUID,
        target_date: date,
    ):
        """
        core.erp_mes_data (work_order) → bi.fact_daily_production
        """
        # 1. erp_mes_data 조회 (record_type='work_order')
        raw_data = db.query(ErpMesData).filter(
            ErpMesData.tenant_id == tenant_id,
            ErpMesData.record_type == 'work_order',
            ErpMesData.raw_data['status'] == 'completed',
            # date 필터
        ).all()

        # 2. FACT로 변환
        for data in raw_data:
            fact = FactDailyProduction(
                tenant_id=tenant_id,
                date=parse_date(data.raw_data['scheduled_start']),
                line_code=data.raw_data['production_line'],
                product_code=data.raw_data['product_code'],
                shift=data.raw_data['shift'],
                total_qty=data.raw_data['planned_quantity'],
                good_qty=data.raw_data['produced_quantity'],
                defect_qty=data.raw_data['defect_quantity'],
                # ... (모든 필드 매핑)
            )
            db.merge(fact)  # INSERT or UPDATE

        db.commit()
        return {"rows_processed": len(raw_data)}
```

**예상 시간**: 4-6시간
**우선순위**: ⭐⭐⭐⭐⭐ (필수)

---

### 🟡 P1 - 성능/완성도 향상

#### 3. Materialized Views 생성 ⭐⭐⭐⭐

**스펙 요구**:
- B-3-2 § 5: 4개 MV 필수
  - `mv_defect_trend` (불량률 추이)
  - `mv_oee_daily` (일일 OEE)
  - `mv_inventory_coverage` (재고 커버리지)
  - `mv_line_performance` (라인 성과)

**현재 상태**:
```sql
-- MV DDL이 스펙에만 있고 실제 생성 안 됨
SELECT * FROM bi.mv_defect_trend;
-- ERROR: relation "bi.mv_defect_trend" does not exist ❌
```

**문제**:
```sql
-- BI 쿼리가 매번 FACT 집계 (느림)
SELECT
    date,
    SUM(defect_qty) / SUM(total_qty) AS defect_rate
FROM bi.fact_daily_production
WHERE date >= CURRENT_DATE - 90
GROUP BY date;  -- ❌ 매번 90일치 집계!

-- 목표: p95 < 2초
-- 실제: 5-10초 (느림)
```

**구현 방법**:
```sql
-- 파일: backend/sql/create_materialized_views.sql

CREATE MATERIALIZED VIEW bi.mv_defect_trend AS
SELECT
    f.tenant_id,
    f.date,
    f.line_code,
    l.name AS line_name,
    f.product_code,
    p.name AS product_name,
    f.shift,
    SUM(f.total_qty) AS total_qty,
    SUM(f.defect_qty) AS defect_qty,
    CASE
        WHEN SUM(f.total_qty) > 0
        THEN SUM(f.defect_qty)::numeric / SUM(f.total_qty)
        ELSE 0
    END AS defect_rate,
    -- 7일 이동평균
    AVG(SUM(f.defect_qty)::numeric / NULLIF(SUM(f.total_qty), 0))
        OVER (
            PARTITION BY f.tenant_id, f.line_code, f.product_code
            ORDER BY f.date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS defect_rate_ma7
FROM bi.fact_daily_production f
JOIN bi.dim_line l ON f.tenant_id = l.tenant_id AND f.line_code = l.line_code
JOIN bi.dim_product p ON f.tenant_id = p.tenant_id AND f.product_code = p.product_code
WHERE f.date >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY f.tenant_id, f.date, f.line_code, l.name, f.product_code, p.name, f.shift;

-- 인덱스
CREATE UNIQUE INDEX idx_mv_defect_trend_pk
ON bi.mv_defect_trend (tenant_id, date, line_code, product_code, shift);

-- 리프레시 (1시간 주기)
-- cron: 0 * * * * psql -c "REFRESH MATERIALIZED VIEW CONCURRENTLY bi.mv_defect_trend;"
```

**예상 시간**: 3-4시간 (4개 MV + 리프레시 스케줄)
**우선순위**: ⭐⭐⭐⭐ (성능 목표 달성 필수)

---

#### 4. POST /api/v1/bi/plan API 구현 ⭐⭐⭐⭐

**스펙 요구**:
- B-4 § 6.1: 분석 계획 생성 API

**스펙 정의**:
```http
POST /api/v1/bi/plan

Request:
{
  "query": "지난 30일간 L01 라인의 불량률 추이와 주요 불량 유형별 분포를 보여줘",
  "context": {
    "user_role": "quality_manager",
    "current_page": "quality_dashboard"
  },
  "options": {
    "max_widgets": 4,
    "include_recommendations": true
  }
}

Response:
{
  "plan_id": "plan_abc123",
  "interpretation": {
    "intent": "trend_analysis",
    "entities": {
      "metric": "defect_rate",
      "dimension": "line",
      "time_grain": "day",
      "time_range": "last_30_days",
      "filters": {"line_code": "L01"}
    }
  },
  "analysis_plan": {
    "widgets": [
      {
        "widget_id": "w1",
        "widget_type": "line_chart",
        "title": "L01 라인 불량률 추이",
        "data_source": {
          "table": "fact_daily_production",
          "metrics": ["defect_rate"],
          "dimensions": ["date"],
          "filters": {...}
        }
      },
      {
        "widget_id": "w2",
        "widget_type": "pie_chart",
        "title": "불량 유형별 분포"
      }
    ]
  },
  "estimated_execution_time_ms": 500
}
```

**현재 상태**:
```python
# backend/app/routers/bi.py
# ❌ POST /plan 엔드포인트 없음!

# 대신 직접 실행 API만 있음:
# GET /analytics/defect-trend
# GET /analytics/oee
```

**차이점**:
- 스펙: 2단계 (plan 생성 → execute 실행)
- 구현: 1단계 (직접 실행)

**구현 방법**:
```python
# backend/app/routers/bi.py

from app.schemas.bi import AnalysisPlanRequest, AnalysisPlanResponse

@router.post("/plan", response_model=AnalysisPlanResponse)
async def create_analysis_plan(
    request: AnalysisPlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    자연어 쿼리 → 분석 계획 생성

    Args:
        query: 자연어 질의
        context: 사용자 컨텍스트
        options: 옵션 (max_widgets 등)

    Returns:
        분석 계획 (widgets, SQL, 차트 설정)
    """
    # 1. BI 카탈로그 조회
    datasets = db.query(BiDataset).filter(...).all()
    metrics = db.query(BiMetric).filter(...).all()

    # 2. LLM 호출 (자연어 → JSON 분석 계획)
    from app.agents.bi_planner import BIPlannerAgent

    planner = BIPlannerAgent()
    plan = await planner.create_plan(
        query=request.query,
        catalog={"datasets": datasets, "metrics": metrics},
        context=request.context,
    )

    # 3. plan_id 생성 및 저장 (캐싱용)
    plan_id = str(uuid4())

    return AnalysisPlanResponse(
        plan_id=plan_id,
        interpretation=plan["interpretation"],
        analysis_plan=plan["widgets"],
        estimated_execution_time_ms=500,
    )
```

**예상 시간**: 4-5시간
**우선순위**: ⭐⭐⭐⭐ (스펙 준수)

---

#### 5. POST /api/v1/bi/execute API 구현 ⭐⭐⭐⭐

**스펙 요구**:
- B-4 § 6.2: 분석 실행 API

**스펙 정의**:
```http
POST /api/v1/bi/execute

Request:
{
  "plan_id": "plan_abc123",  // 또는
  "analysis_plan": {...}      // 직접 전달
}

Response:
{
  "execution_id": "exec_xyz789",
  "results": {
    "w1": {
      "data": [...],
      "chart_config": {...}
    },
    "w2": {...}
  },
  "execution_time_ms": 450,
  "from_cache": false
}
```

**현재 상태**:
```python
# ❌ POST /execute 엔드포인트 없음!
```

**구현 방법**:
```python
@router.post("/execute", response_model=AnalysisExecutionResponse)
async def execute_analysis(
    request: AnalysisExecutionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """분석 계획 실행"""
    # 1. plan 조회 (plan_id 또는 직접 전달)
    # 2. widget별로 SQL 실행
    # 3. 차트 데이터 생성
    # 4. 캐싱 (Redis)
    # 5. 결과 반환
    pass
```

**예상 시간**: 3-4시간
**우선순위**: ⭐⭐⭐⭐ (스펙 준수)

---

#### 6. 캐싱 Redis 연동 ⭐⭐⭐⭐

**스펙 요구**:
- B-2-2 § 1.3.1: 캐싱 전략 (TTL 600초)

**스펙 정의**:
```python
# 스펙 예시
cache_key = hash(analysis_plan + tenant_id)
cached_result = await cache_manager.get(cache_key)

if cached_result:
    return {"from_cache": True, **cached_result}

# 캐시 저장
await cache_manager.set(cache_key, result, ttl=600)
```

**현재 상태**:
```python
# bi_service.py:94-102
cache_key = self._generate_cache_key(plan)  # ✅ 키 생성 구현됨

# 하지만 실제 Redis 연동은 주석 처리
# cached = await cache_manager.get(cache_key)  # ❌ 주석
# await cache_manager.set(cache_key, result, ttl=600)  # ❌ 주석
```

**구현 방법**:
```python
# bi_service.py 수정

async def analyze_rank(self, ...):
    # 캐시 키 생성
    cache_key = self._generate_cache_key({
        "type": "rank",
        "metric": metric,
        "dimension": dimension,
        "tenant_id": str(tenant_id)
    })

    # ✅ Redis 캐시 조회
    from app.services.redis_client import get_redis_client
    redis = await get_redis_client()

    cached = await redis.get(f"bi:cache:{cache_key}")
    if cached:
        logger.info(f"Cache HIT: {cache_key}")
        return json.loads(cached)

    # 분석 실행
    result = await self._execute_rank_analysis(...)

    # ✅ Redis 캐시 저장 (TTL 600초)
    await redis.setex(f"bi:cache:{cache_key}", 600, json.dumps(result))

    return result
```

**예상 시간**: 2-3시간
**우선순위**: ⭐⭐⭐⭐ (성능 개선)

---

#### 7. 파티션 자동 생성 함수 ⭐⭐⭐

**스펙 요구**:
- B-3-2 § 9.2: 파티션 관리 함수

**스펙 정의**:
```sql
CREATE OR REPLACE FUNCTION bi.create_monthly_partitions(
    p_table_name text,
    p_start_date date,
    p_end_date date
)
RETURNS void AS $$
DECLARE
    v_partition_name text;
    v_start_date date;
    v_end_date date;
BEGIN
    v_start_date := date_trunc('month', p_start_date);
    WHILE v_start_date < p_end_date LOOP
        v_end_date := v_start_date + INTERVAL '1 month';
        v_partition_name := p_table_name || '_' || to_char(v_start_date, 'YYYYMM');

        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)',
            v_partition_name, p_table_name, v_start_date, v_end_date
        );

        v_start_date := v_end_date;
    END LOOP;
END;
$$ LANGUAGE plpgsql;
```

**현재 상태**:
```python
# models/bi.py
class FactDailyProduction(Base):
    __table_args__ = {
        "postgresql_partition_by": "RANGE (date)",  # ✅ 파티션 정의됨
        ...
    }

# 하지만 실제 파티션 생성 함수 없음 ❌
```

**구현 방법**:
```sql
-- 파일: backend/sql/create_partition_function.sql
-- (스펙 함수 그대로 구현)

-- 실행 예시:
SELECT bi.create_monthly_partitions(
    'bi.raw_mes_production',
    '2025-01-01'::date,
    '2026-12-31'::date
);
-- 24개 파티션 자동 생성
```

**예상 시간**: 2시간
**우선순위**: ⭐⭐⭐ (운영 자동화)

---

### 🟢 P2 - 운영 편의성

#### 8. Data Quality Checks 실행 ⭐⭐⭐

**스펙 요구**:
- B-3-2 § 8: 품질 규칙 실행

**스펙 정의**:
```python
# 품질 규칙 예시
rules = [
    {
        "rule_type": "not_null",
        "table": "fact_daily_production",
        "column": "total_qty"
    },
    {
        "rule_type": "range",
        "table": "fact_daily_production",
        "column": "defect_rate",
        "min": 0,
        "max": 1
    }
]
```

**현재 상태**:
```python
# 테이블만 존재
class DataQualityRule(Base):  # ✅
class DataQualityCheck(Base):  # ✅

# 실행 서비스 없음 ❌
```

**구현 방법**:
```python
# backend/app/services/data_quality_service.py (신규)

class DataQualityService:
    async def execute_check(self, rule_id: UUID):
        rule = db.query(DataQualityRule).get(rule_id)

        if rule.rule_type == "not_null":
            sql = f"SELECT COUNT(*) FROM {rule.table_name} WHERE {rule.column_name} IS NULL"
            failed_count = db.execute(text(sql)).scalar()

        elif rule.rule_type == "range":
            sql = f"SELECT COUNT(*) FROM {rule.table_name} WHERE {rule.column_name} NOT BETWEEN {rule.min_value} AND {rule.max_value}"
            failed_count = db.execute(text(sql)).scalar()

        # DataQualityCheck 저장
        check = DataQualityCheck(
            rule_id=rule_id,
            passed=(failed_count == 0),
            failed_row_count=failed_count,
        )
        db.add(check)
        db.commit()
```

**예상 시간**: 4-5시간
**우선순위**: ⭐⭐⭐ (데이터 무결성)

---

#### 9. 카탈로그 CRUD API ⭐⭐

**스펙 요구**:
- B-4 § 6.3: 카탈로그 관리 API

**스펙 정의**:
```http
POST /api/v1/bi/catalog/datasets
PUT /api/v1/bi/catalog/datasets/{dataset_id}
DELETE /api/v1/bi/catalog/datasets/{dataset_id}

POST /api/v1/bi/catalog/metrics
PUT /api/v1/bi/catalog/metrics/{metric_id}
```

**현재 상태**:
```python
# GET만 있음
GET /api/v1/bi/catalog/datasets  # ✅
GET /api/v1/bi/catalog/metrics   # ✅

# POST/PUT/DELETE 없음 ❌
```

**구현 방법**:
```python
# backend/app/routers/bi.py

@router.post("/catalog/datasets")
async def create_dataset(...):
    # BiDataset 생성

@router.put("/catalog/datasets/{dataset_id}")
async def update_dataset(...):
    # BiDataset 수정

@router.delete("/catalog/datasets/{dataset_id}")
async def delete_dataset(...):
    # BiDataset 삭제 (soft delete)
```

**예상 시간**: 3-4시간
**우선순위**: ⭐⭐ (UI 편의성)

---

## 📊 구현 항목 요약표

| 순위 | 항목 | 스펙 위치 | 현재 상태 | 예상 시간 |
|------|------|----------|----------|----------|
| **P0-1** | 시드 데이터 생성 | B-3-2 § 3.1, 3.6 | ❌ 없음 | 1h |
| **P0-2** | ETL 파이프라인 | B-3-2 § 7.3, 8.2 | ❌ 메타만 | 4-6h |
| **P1-1** | Materialized Views | B-3-2 § 5 | ❌ DDL만 | 3-4h |
| **P1-2** | POST /plan API | B-4 § 6.1 | ❌ 없음 | 4-5h |
| **P1-3** | POST /execute API | B-4 § 6.2 | ❌ 없음 | 3-4h |
| **P1-4** | 캐싱 Redis 연동 | B-2-2 § 1.3.1 | ⚠️ 주석 | 2-3h |
| **P1-5** | 파티션 함수 | B-3-2 § 9.2 | ❌ 없음 | 2h |
| **P2-1** | Data Quality | B-3-2 § 8 | ❌ 메타만 | 4-5h |
| **P2-2** | 카탈로그 CRUD | B-4 § 6.3 | ⚠️ GET만 | 3-4h |

**총 예상 시간**: **26-36시간** (약 3-4일)

---

## 🎯 즉시 시작 추천

### **Option 1: 최소 작동 (5-7시간)** ⭐⭐⭐⭐⭐

```
Day 1:
1. 시드 데이터 (1h)
2. ETL 파이프라인 기본 (4-6h)

완료 후:
✅ BI 즉시 사용 가능
✅ Mock 데이터 → FACT 변환
✅ GenBI 인사이트 생성
```

---

### **Option 2: 성능 최적화 (8-11시간)** ⭐⭐⭐⭐

```
Day 1:
1. 시드 데이터 (1h)
2. Materialized Views (3-4h)
3. 캐싱 Redis (2-3h)
4. 파티션 함수 (2h)

완료 후:
✅ BI 사용 가능
✅ 쿼리 성능 10배 향상
✅ p95 < 2초 목표 달성
```

---

### **Option 3: 스펙 완전 준수 (15-20시간)** ⭐⭐⭐⭐⭐

```
Day 1-2:
1. 시드 데이터 (1h)
2. ETL 파이프라인 (4-6h)
3. Materialized Views (3-4h)
4. POST /plan, /execute API (7-9h)

완료 후:
✅ 스펙 100% 준수
✅ 2단계 API (plan → execute)
✅ 성능 최적화
```

---

## 💡 제 추천: **Option 1 (최소 작동)**

**이유**:
1. ✅ **가장 빠름** (5-7시간, 1일)
2. ✅ **즉시 BI 사용 가능**
3. ✅ **GenBI 데모 가능**
4. ✅ **고객에게 보여줄 수 있음**

**완료 후 다음 단계**:
```
Week 1: 시드 + ETL (5-7h) → BI 작동 ✅
Week 2: MV + 캐싱 (5-7h) → 성능 향상 ✅
Week 3: API 스펙 준수 (7-9h) → 완성 ✅
```

---

## 📝 최종 정리

### 구현해야 할 것 (스펙 vs 현재)

**P0 (필수)**:
1. ❌ 시드 데이터 (dim_date, dim_shift)
2. ❌ ETL 파이프라인 (RAW → FACT)

**P1 (성능/완성도)**:
3. ❌ Materialized Views (4개)
4. ❌ POST /plan API
5. ❌ POST /execute API
6. ⚠️ 캐싱 Redis 연동 (코드만 있음)
7. ❌ 파티션 자동 생성 함수

**P2 (운영)**:
8. ❌ Data Quality 실행
9. ⚠️ 카탈로그 CRUD (GET만 있음)

---

**BI 엔진은 완벽하지만, 데이터 파이프라인이 부족합니다!**
**P0 항목 구현하면 즉시 사용 가능합니다!** ✅

어떤 작업을 진행하시겠습니까?
1. **시드 데이터 생성** (1h) - 가장 빠름 ⭐⭐⭐⭐⭐
2. **ETL 파이프라인** (4-6h) - 자동화 ⭐⭐⭐⭐
3. **전체 완성** (26-36h, 3-4일) - 100% ⭐⭐⭐⭐⭐
