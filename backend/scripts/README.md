# TriFlow AI - Scripts & Batch Jobs

운영 자동화를 위한 스크립트 모음

---

## 📋 스크립트 목록

### 1. auto_partition.sh - 자동 파티셔닝 배치

**기능**:
- 미래 3개월 파티션 사전 생성 (INSERT 실패 방지)
- 2년 전 파티션 자동 삭제 (스토리지 관리)
- 파티션 상태 모니터링

**실행 방법**:
```bash
# 환경변수 설정
export DB_HOST=localhost
export DB_USER=postgres
export DB_PASSWORD=your_password
export DB_NAME=ai_factory

# 스크립트 실행
./auto_partition.sh
```

**Cron 등록**:
```bash
# 매월 1일 03:00 실행
0 3 1 * * /app/backend/scripts/auto_partition.sh >> /var/log/triflow/auto_partition.log 2>&1
```

**효과**:
- 쿼리 성능 10-20배 향상
- 파티션 미생성 장애 방지
- 스토리지 비용 절감

---

### 2. check_mv_performance.py - MV 성능 체크

**기능**:
- Materialized View 쿼리 성능 측정
- 리프레시 시간 측정
- 성능 저하 감지

**실행 방법**:
```bash
python check_mv_performance.py
```

---

### 3. seed_modules.py - 모듈 시드 데이터

**기능**:
- Industry Profile 시드 데이터 생성
- Module 메타데이터 생성

**실행 방법**:
```bash
python seed_modules.py
```

---

### 4. generate_recent_sensor_data.py - 센서 데이터 생성

**기능**:
- 테스트/데모용 센서 데이터 생성

**실행 방법**:
```bash
python generate_recent_sensor_data.py
```

---

## 🔧 Python 스케줄러 통합 (권장)

Shell 스크립트 대신 Python 스케줄러 사용 (이미 구현됨):

**backend/app/services/scheduler_service.py**:
```python
# 자동 파티션 생성 (7일마다)
scheduler.register_job(
    job_id="auto_create_partitions",
    name="자동 파티션 생성",
    interval_seconds=604800,  # 7일
    handler=auto_create_partitions,
    enabled=True,
)

# 만료 파티션 삭제 (30일마다)
scheduler.register_job(
    job_id="auto_delete_expired_partitions",
    name="만료 파티션 삭제",
    interval_seconds=2592000,  # 30일
    handler=auto_delete_expired_partitions,
    enabled=True,
)
```

**장점**:
- ✅ 환경변수 자동 인식
- ✅ 에러 처리 자동화
- ✅ 로그 통합 관리
- ✅ API로 상태 조회 가능

**API 엔드포인트**:
```bash
# 스케줄러 상태 조회
GET /api/v1/scheduler/jobs

# 즉시 실행
POST /api/v1/scheduler/jobs/{job_id}/run
```

---

## 🚀 배포 체크리스트

### 개발 환경
- [ ] Python 스케줄러 사용 (자동 실행)
- [ ] 로그 확인: `/api/v1/scheduler/jobs`

### 프로덕션 환경
- [ ] Cron 또는 Python 스케줄러 선택
- [ ] 로그 디렉토리 생성: `/var/log/triflow/`
- [ ] 권한 설정: `chmod +x auto_partition.sh`
- [ ] 환경변수 설정 (DB 접속 정보)
- [ ] 첫 실행 테스트: `./auto_partition.sh`
- [ ] 알람 설정 (파티션 미생성 시)

---

## 📊 모니터링

### 파티션 상태 확인
```sql
-- 테이블별 파티션 개수
SELECT
    parent.relname AS parent_table,
    COUNT(*) AS partition_count,
    pg_size_pretty(SUM(pg_total_relation_size(child.oid))) AS total_size
FROM pg_inherits
JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
JOIN pg_class child ON pg_inherits.inhrelid = child.oid
WHERE parent.relname IN ('judgment_executions', 'workflow_instances', 'fact_daily_production')
GROUP BY parent.relname;

-- 현재 월 파티션 존재 확인
SELECT tablename
FROM pg_tables
WHERE schemaname = 'core'
  AND tablename LIKE 'judgment_executions_y2026m%'
ORDER BY tablename;
```

### Grafana 알람 규칙
```yaml
- alert: PartitionMissing
  expr: partition_exists{table="judgment_executions", month="current"} == 0
  for: 1m
  annotations:
    summary: "Current month partition missing"
```

---

## 🆘 트러블슈팅

### 문제: 파티션 생성 실패
```
ERROR: function create_monthly_partition does not exist
```

**해결**:
```bash
# 파티션 함수 생성 (마이그레이션 재실행)
alembic upgrade head
```

### 문제: 권한 오류
```
ERROR: permission denied for table
```

**해결**:
```sql
-- DB 사용자 권한 부여
GRANT CREATE ON SCHEMA core TO postgres;
GRANT ALL ON ALL TABLES IN SCHEMA core TO postgres;
```

### 문제: 파티션 삭제 실패
```
ERROR: cannot drop table because other objects depend on it
```

**해결**:
```sql
-- CASCADE 옵션 사용 (주의!)
DROP TABLE core.judgment_executions_y2023m01 CASCADE;
```

---

## 📝 참고 문서

- 스펙: `docs/specs/B-design/B-3-4_Performance_Operations.md`
- 마이그레이션: `alembic/versions/001_core_schema_baseline.py`
- 스케줄러: `app/services/scheduler_service.py`
