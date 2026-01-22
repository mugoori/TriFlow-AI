# 🤔 시드 데이터가 왜 필요한가?

**핵심 답변**: Star Schema의 **JOIN이 작동하려면** Dimension 테이블에 데이터가 필요합니다!

---

## 📊 문제 상황 시뮬레이션

### Scenario: "최근 7일 불량률 추이 보여줘"

#### BI가 실행하는 SQL

```sql
SELECT
    d.date,           -- ← dim_date에서 날짜 정보
    l.line_name,      -- ← dim_line에서 라인 이름
    SUM(f.defect_qty)::float / NULLIF(SUM(f.total_qty), 0) AS defect_rate
FROM bi.fact_daily_production f
JOIN bi.dim_date d ON f.date = d.date          -- ❌ 여기서 문제!
JOIN bi.dim_line l ON f.line_code = l.line_code -- ❌ 여기서도 문제!
WHERE d.date >= CURRENT_DATE - 7
GROUP BY d.date, l.line_name
ORDER BY d.date
```

---

## ❌ 시드 데이터 없을 때

### 1. FACT 테이블 상태

```sql
SELECT * FROM bi.fact_daily_production;
```

**결과**:
```
date       | line_code | total_qty | defect_qty
-----------+-----------+-----------+------------
2026-01-22 | LINE-A    | 1000      | 80
2026-01-21 | LINE-A    | 1000      | 75
2026-01-20 | LINE-B    | 800       | 24
```

**데이터 있음!** ✅

---

### 2. DIM 테이블 상태

```sql
SELECT * FROM bi.dim_date;
```

**결과**:
```
(0 rows)  ❌ 비어있음!
```

```sql
SELECT * FROM bi.dim_line;
```

**결과**:
```
(0 rows)  ❌ 비어있음!
```

---

### 3. JOIN 실행

```sql
-- Step 1: FACT 테이블 조회
FROM bi.fact_daily_production f
-- 결과: 3개 행

-- Step 2: dim_date와 JOIN
JOIN bi.dim_date d ON f.date = d.date
-- f.date = 2026-01-22
-- dim_date에서 2026-01-22 찾기
-- → 0개 (dim_date가 비어있음!) ❌

-- JOIN 결과: 0개 행
```

**최종 결과**:
```
date | line_name | defect_rate
-----+-----------+-------------
(0 rows)  ❌ 데이터 없음!
```

**사용자에게 표시**:
```
"데이터가 없습니다"  ← FACT에는 있는데!
```

---

## ✅ 시드 데이터 있을 때

### 1. DIM 테이블 상태 (시드 후)

```sql
SELECT * FROM bi.dim_date WHERE date >= '2026-01-20';
```

**결과**:
```
date       | year | quarter | month | week | day_name
-----------+------+---------+-------+------+----------
2026-01-20 | 2026 | 1       | 1     | 4    | Tuesday
2026-01-21 | 2026 | 1       | 1     | 4    | Wednesday
2026-01-22 | 2026 | 1       | 1     | 4    | Thursday
```

**데이터 있음!** ✅

```sql
SELECT * FROM bi.dim_line;
```

**결과**:
```
line_code | line_name | line_type
----------+-----------+-----------
LINE-A    | A 라인    | Assembly
LINE-B    | B 라인    | Packaging
```

**데이터 있음!** ✅

---

### 2. JOIN 실행

```sql
-- Step 1: FACT 테이블
FROM bi.fact_daily_production f
-- 결과: 3개 행

-- Step 2: dim_date와 JOIN
JOIN bi.dim_date d ON f.date = d.date
-- f.date = 2026-01-22
-- dim_date에서 2026-01-22 찾기
-- → 1개 매칭됨! ✅

-- Step 3: dim_line과 JOIN
JOIN bi.dim_line l ON f.line_code = l.line_code
-- f.line_code = LINE-A
-- dim_line에서 LINE-A 찾기
-- → 1개 매칭됨! ✅

-- JOIN 결과: 3개 행 (성공!)
```

**최종 결과**:
```
date       | line_name | defect_rate
-----------+-----------+-------------
2026-01-20 | B 라인    | 0.03
2026-01-21 | A 라인    | 0.075
2026-01-22 | A 라인    | 0.08
```

**사용자에게 표시**:
```
불량률 분석 결과:
- 2026-01-22: A 라인 8.0%
- 2026-01-21: A 라인 7.5%
- 2026-01-20: B 라인 3.0%

A 라인 불량률 상승 추세!
```

---

## 🔍 왜 dim_date가 필요한가?

### 이유 1: JOIN 매칭

```sql
-- FACT 테이블
fact_daily_production
  date: 2026-01-22  (날짜만)

-- DIM 테이블
dim_date
  date: 2026-01-22
  year: 2026
  quarter: 1
  month: 1
  week: 4
  day_name: Thursday
  is_weekend: false

-- JOIN 후
date: 2026-01-22
year: 2026        ← dim_date에서!
quarter: 1        ← dim_date에서!
day_name: Thursday ← dim_date에서!
```

**활용**:
```sql
-- 분기별 집계
SELECT quarter, SUM(defect_qty) FROM ... GROUP BY quarter

-- 주말 제외
WHERE is_weekend = false

-- 요일별 패턴
GROUP BY day_name
```

---

### 이유 2: 연속된 날짜 보장

```sql
-- fact_daily_production에 데이터가 있는 날짜만:
2026-01-15  ✅
2026-01-16  ✅
2026-01-17  ❌ 휴무일 (데이터 없음)
2026-01-18  ✅
2026-01-19  ✅

-- dim_date가 없으면:
SELECT date, defect_rate FROM ...
결과:
2026-01-15  0.08
2026-01-16  0.07
2026-01-18  0.09  ← 17일이 빠짐!
2026-01-19  0.06

-- 차트가 이상함 (날짜 건너뜀)
```

**dim_date가 있으면**:
```sql
-- LEFT JOIN으로 연속된 날짜 보장
SELECT
    d.date,
    COALESCE(SUM(f.defect_qty) / NULLIF(SUM(f.total_qty), 0), 0) AS defect_rate
FROM bi.dim_date d
LEFT JOIN bi.fact_daily_production f ON d.date = f.date
WHERE d.date >= CURRENT_DATE - 7
GROUP BY d.date

결과:
2026-01-15  0.08
2026-01-16  0.07
2026-01-17  0.00  ← 휴무일 (0으로 표시)
2026-01-18  0.09
2026-01-19  0.06

-- 차트가 정상 (연속된 날짜)
```

---

## 🔍 왜 dim_line이 필요한가?

### FACT에 line_code만 있는 이유

```sql
-- fact_daily_production
line_code: "LINE-A"  ← 코드만 (저장 공간 절약)

-- dim_line
line_code: "LINE-A"
line_name: "A 라인"   ← 사람이 읽을 수 있는 이름
line_type: "Assembly"
capacity_per_day: 5000
is_active: true
```

**시드 데이터 없으면**:
```
사용자에게 표시:
"LINE-A의 불량률: 8%"  ← 알아보기 어려움
```

**시드 데이터 있으면**:
```
사용자에게 표시:
"A 라인 (조립)의 불량률: 8%"  ← 명확함!
```

---

## 🔍 왜 dim_shift가 필요한가?

### 교대별 분석

```sql
-- fact_daily_production
shift: "A"  ← 코드만

-- dim_shift
shift_code: "A"
name: "주간"
start_time: "08:00"
end_time: "16:00"
is_night_shift: false
```

**시드 데이터 없으면**:
```sql
SELECT shift, AVG(defect_rate) FROM ... GROUP BY shift

결과:
shift | avg_defect_rate
------+-----------------
A     | 0.05
B     | 0.08  ← 교대 B가 왜 높은지 모름
C     | 0.12

사용자: "B가 뭐지? 오후인가? 야간인가?"
```

**시드 데이터 있으면**:
```sql
SELECT
    s.name,
    s.start_time,
    s.is_night_shift,
    AVG(f.defect_qty / f.total_qty) AS avg_defect_rate
FROM fact_daily_production f
JOIN dim_shift s ON f.shift = s.shift_code
GROUP BY s.name, s.start_time, s.is_night_shift

결과:
name   | start_time | is_night_shift | avg_defect_rate
-------+------------+----------------+-----------------
주간   | 08:00      | false          | 0.05
오후   | 16:00      | false          | 0.08
야간   | 00:00      | true           | 0.12  ← 야간이 가장 높음!

인사이트:
"야간 교대의 불량률이 12%로 가장 높습니다"
"주간 대비 2배 이상 높음"
"야간 작업 관리 강화 필요"
```

---

## 💡 실제 사용 시나리오

### Case 1: BI 채팅

**사용자 질의**: "오늘 불량률 어때?"

#### 시드 데이터 없으면 ❌

```
BI 쿼리 실행:
SELECT ... FROM fact JOIN dim_date ...
→ JOIN 결과 0개 (dim_date 비어있음)

사용자에게 응답:
"데이터가 없습니다"

사용자 반응:
"뭐야, BI가 작동 안 하네?"
```

#### 시드 데이터 있으면 ✅

```
BI 쿼리 실행:
SELECT ... FROM fact JOIN dim_date ...
→ JOIN 결과 3개

사용자에게 응답:
"오늘 전체 불량률 5.2%
 - A 라인: 8.0% (주의 필요)
 - B 라인: 3.2% (정상)
 - C 라인: 2.1% (양호)"

사용자 반응:
"오! BI가 잘 작동하네!"
```

---

### Case 2: 차트 생성

**사용자**: "최근 7일 추이 차트"

#### 시드 데이터 없으면 ❌

```
차트 데이터:
[]  (비어있음)

화면:
┌─────────────────┐
│ 차트            │
│                 │
│ (데이터 없음)   │
│                 │
└─────────────────┘
```

#### 시드 데이터 있으면 ✅

```
차트 데이터:
[
  {date: "01-16", defect_rate: 0.05},
  {date: "01-17", defect_rate: 0.06},
  {date: "01-18", defect_rate: 0.07},
  ...
]

화면:
┌─────────────────┐
│ 불량률 추이     │
│      ╱          │
│    ╱            │
│  ╱              │
│╱________________│
│01-16 → 01-22    │
└─────────────────┘
```

---

## 🎯 Star Schema의 원리

### Star Schema 구조

```
        dim_date (시간 차원)
            ↓ JOIN
fact_daily_production (중심)
            ↓ JOIN
        dim_line (라인 차원)
            ↓ JOIN
        dim_product (제품 차원)
```

### FACT는 "사실"만 저장

```sql
-- fact_daily_production
date: 2026-01-22      ← 날짜 코드만
line_code: "LINE-A"   ← 라인 코드만
product_code: "PROD-X" ← 제품 코드만
total_qty: 1000
defect_qty: 80
```

### DIM은 "설명"을 저장

```sql
-- dim_date
date: 2026-01-22
year: 2026            ← 연도 (집계용)
quarter: 1            ← 분기 (집계용)
month: 1              ← 월 (집계용)
day_name: "Thursday"  ← 요일 (패턴 분석)
is_weekend: false     ← 주말 여부
is_holiday: false     ← 휴일 여부

-- dim_line
line_code: "LINE-A"
line_name: "A 라인"         ← 사람이 읽을 이름
line_type: "Assembly"        ← 라인 유형
capacity_per_day: 5000       ← 생산 능력
location: "Building A, Floor 2" ← 위치
```

### JOIN하면 완전한 정보

```sql
SELECT
    d.date,
    d.year,          ← dim_date
    d.quarter,       ← dim_date
    d.day_name,      ← dim_date
    l.line_name,     ← dim_line
    l.line_type,     ← dim_line
    f.total_qty,     ← fact
    f.defect_qty,    ← fact
    f.defect_rate    ← fact (계산)
FROM fact f
JOIN dim_date d ON f.date = d.date
JOIN dim_line l ON f.line_code = l.line_code
```

**결과**: 완전한 분석 가능!
- 연도별, 분기별, 월별 집계
- 요일별 패턴 분석
- 주말/평일 비교
- 라인 유형별 비교

---

## 📋 시드 데이터 종류

### 필수 시드 (없으면 작동 안 함)

#### 1. dim_date (2020-2030, 10년치)

**이유**:
- 모든 BI 쿼리가 날짜로 필터링
- 연도/분기/월별 집계 필수
- 연속된 날짜 보장 (차트용)

**예시**:
```
2026-01-01, 2026-01-02, ..., 2030-12-31
총 3,650개 레코드
```

---

#### 2. dim_shift (3교대 기본값)

**이유**:
- 교대별 성과 비교 필수
- 야간/주간 패턴 분석
- FACT의 shift 필드와 JOIN

**예시**:
```
A: 주간 (08:00-16:00)
B: 오후 (16:00-00:00)
C: 야간 (00:00-08:00)
```

---

### 선택적 시드 (있으면 편리)

#### 3. dim_line (샘플 라인)

**없어도**: SQL 에러는 안 남 (LEFT JOIN 가능)
**있으면**: 라인 이름 표시, 유형별 분석

**예시**:
```
LINE-A: A 라인 (조립)
LINE-B: B 라인 (포장)
LINE-C: C 라인 (검사)
```

---

#### 4. dim_product (샘플 제품)

**없어도**: 제품 코드로 표시 가능
**있으면**: 제품 이름, 카테고리별 분석

**예시**:
```
PROD-X: 제품X (전자부품)
PROD-Y: 제품Y (기계부품)
```

---

## 🚀 시드 데이터 생성 방법

### Option 1: SQL로 생성 (권장, 1시간)

```sql
-- backend/sql/seed_bi_dimensions.sql

-- 1. dim_date (2020-2030, 3,650개)
INSERT INTO bi.dim_date (date, year, quarter, ...)
SELECT d::date, EXTRACT(year FROM d), ...
FROM generate_series('2020-01-01'::date, '2030-12-31'::date, '1 day') d;

-- 2. dim_shift (3개)
INSERT INTO bi.dim_shift VALUES
('A', '주간', '08:00', '16:00'),
('B', '오후', '16:00', '00:00'),
('C', '야간', '00:00', '08:00');

-- 3. dim_line 샘플 (3개)
INSERT INTO bi.dim_line VALUES
('LINE-A', 'A 라인', 'Assembly', 5000),
('LINE-B', 'B 라인', 'Packaging', 3000),
('LINE-C', 'C 라인', 'Inspection', 2000);

-- 4. dim_product 샘플 (5개)
INSERT INTO bi.dim_product VALUES
('PROD-X', '제품X', '전자부품', 'Type-A'),
('PROD-Y', '제품Y', '기계부품', 'Type-B'),
...;
```

**실행**:
```bash
psql -U postgres -d triflow < backend/sql/seed_bi_dimensions.sql

# 결과:
# ✅ dim_date: 3,650개
# ✅ dim_shift: 3개
# ✅ dim_line: 3개
# ✅ dim_product: 5개
```

---

### Option 2: Python으로 생성 (2시간)

```python
# backend/scripts/seed_bi_data.py

from datetime import date, timedelta
from app.database import SessionLocal
from app.models.bi import DimDate, DimShift, DimLine, DimProduct

db = SessionLocal()

# 1. dim_date
start = date(2020, 1, 1)
end = date(2030, 12, 31)
current = start

while current <= end:
    dim_date = DimDate(
        date=current,
        year=current.year,
        quarter=(current.month - 1) // 3 + 1,
        month=current.month,
        day_of_week=current.weekday(),
        is_weekend=(current.weekday() >= 5),
    )
    db.add(dim_date)
    current += timedelta(days=1)

db.commit()
print(f"✅ Created {(end - start).days + 1} dim_date records")

# 2. dim_shift, dim_line, dim_product도 동일
```

---

## 💡 결론

### 시드 데이터가 필요한 이유

1. **JOIN 매칭** - FACT와 DIM을 연결
2. **완전한 정보** - 코드 → 이름, 속성
3. **연속성 보장** - 빠진 날짜 없이 연속
4. **집계 기능** - 연도/분기/월별 집계
5. **패턴 분석** - 요일/교대별 패턴

---

### 시드 데이터 없으면

```
FACT에 데이터 있어도
  ↓
JOIN 실패
  ↓
BI 쿼리 결과 0개
  ↓
"데이터 없음"
```

---

### 시드 데이터 있으면

```
FACT에 데이터 있고
  ↓
JOIN 성공 (DIM과 매칭)
  ↓
BI 쿼리 결과 정상
  ↓
"A 라인 불량률 8%" (인사이트 생성!)
```

---

## 🚀 즉시 해결 방법

### 가장 빠른 방법 (10분)

```sql
-- 수동으로 최소 시드 생성
INSERT INTO bi.dim_date VALUES
('2026-01-15', 2026, 1, 1, 3, 15, 15, 2, 'Tuesday', false, false),
('2026-01-16', 2026, 1, 1, 3, 16, 16, 3, 'Wednesday', false, false),
...
('2026-01-22', 2026, 1, 1, 4, 22, 22, 3, 'Wednesday', false, false);

INSERT INTO bi.dim_line VALUES
('LINE-A', 'A 라인', 'Assembly', 5000, true),
('LINE-B', 'B 라인', 'Packaging', 3000, true);

INSERT INTO bi.dim_product VALUES
('PROD-X', '제품X', '전자부품', 'Type-A'),
('PROD-Y', '제품Y', '기계부품', 'Type-B');

-- 이제 BI 쿼리 작동!
```

---

### 완전한 방법 (1시간)

```bash
# SQL 스크립트 생성 후 실행
psql < backend/sql/seed_bi_dimensions.sql

# ✅ 10년치 dim_date
# ✅ 3교대 dim_shift
# ✅ 샘플 dim_line, dim_product
```

---

## 🎯 핵심 정리

**시드 데이터 = DIM 테이블의 기본값**

**없으면**:
- JOIN 실패
- BI 쿼리 결과 없음
- "데이터 없음" 에러

**있으면**:
- JOIN 성공
- BI 쿼리 정상 작동
- 인사이트 생성!

---

**시드 데이터는 Star Schema의 "뼈대"입니다!**
**FACT(고기)는 있어도 뼈대(DIM)가 없으면 쿼리가 작동하지 않습니다!** ⚠️

시드 데이터를 생성하시겠습니까? (1시간)
