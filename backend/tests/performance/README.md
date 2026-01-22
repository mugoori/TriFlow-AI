# TriFlow AI - 성능 테스트

Locust 기반 부하 테스트

---

## 📊 성능 목표 (스펙 NFR-PERF)

| 지표 | 목표 | 측정 |
|------|------|------|
| Judgment 응답 (Rule Only) | P95 < 800ms | ✓ |
| Judgment 응답 (Hybrid) | P95 < 2.5s | ✓ |
| BI 쿼리 응답 | P95 < 3s | ✓ |
| 처리량 (Judgment) | > 50 TPS | ✓ |
| 동시 사용자 | 500명 지원 | ✓ |
| 캐시 적중 응답 | P95 < 300ms | ✓ |

---

## 🚀 실행 방법

### 1. Locust 설치
```bash
pip install locust
```

### 2. 테스트 서버 실행
```bash
# 백엔드 서버 시작
cd backend
python -m app.main

# 또는 Docker
docker-compose up
```

### 3. Locust 실행
```bash
cd backend/tests/performance
locust -f locustfile.py --host=http://localhost:8000
```

### 4. 웹 UI 접속
브라우저에서 http://localhost:8089 접속

**설정 예시**:
- Number of users: 100 (동시 사용자)
- Spawn rate: 10 (초당 10명씩 증가)
- Host: http://localhost:8000

---

## 📈 테스트 시나리오

### 시나리오 1: 일반 부하 (Baseline)
- **사용자 수**: 100
- **지속 시간**: 5분
- **목표**: P95 < 2.5s 달성

```bash
locust -f locustfile.py \
  --host=http://localhost:8000 \
  --users=100 \
  --spawn-rate=10 \
  --run-time=5m \
  --headless
```

### 시나리오 2: 최대 부하 (Stress Test)
- **사용자 수**: 500
- **지속 시간**: 10분
- **목표**: 시스템 안정성 검증

```bash
locust -f locustfile.py \
  --host=http://localhost:8000 \
  --users=500 \
  --spawn-rate=20 \
  --run-time=10m \
  --headless
```

### 시나리오 3: 스파이크 테스트
- **사용자 수**: 200 → 1000 (급증)
- **목표**: Auto-scaling 동작 확인

```bash
# 먼저 200명으로 시작
locust -f locustfile.py --users=200 --spawn-rate=50

# 실행 중 웹 UI에서 1000명으로 증가
```

---

## 📊 결과 분석

### Locust 웹 UI
- **Statistics**: 요청별 응답 시간, 처리량
- **Charts**: 시간대별 응답 시간, RPS 추이
- **Failures**: 실패한 요청 분석
- **Download Data**: CSV 내보내기

### 성능 지표 확인
```bash
# P50, P95, P99 확인
# Statistics 탭에서 확인

# 처리량 (RPS) 확인
# Charts 탭 - Total Requests per Second

# 실패율 확인
# Failures 탭
```

---

## 🎯 성능 개선 팁

### 1. 캐시 활용
- Judgment 캐시 TTL 조정 (기본: 300초)
- BI 쿼리 캐시 TTL 조정 (기본: 600초)

### 2. DB 최적화
- Connection Pool 크기 증가
- 인덱스 추가
- Materialized View 리프레시

### 3. 스케일링
```bash
# Docker Compose에서 백엔드 스케일 아웃
docker-compose up --scale backend=3
```

### 4. 모니터링
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

---

## 🔍 트러블슈팅

### 문제: P95 > 5초
**원인**: DB 커넥션 부족, 느린 쿼리
**해결**:
```python
# app/database.py
engine = create_engine(
    DATABASE_URL,
    pool_size=20,  # 증가
    max_overflow=40,
)
```

### 문제: RPS < 50
**원인**: CPU 병목
**해결**:
- 백엔드 인스턴스 증가 (스케일 아웃)
- uvicorn workers 증가

```bash
uvicorn app.main:app --workers=4
```

### 문제: 메모리 부족
**원인**: Redis 캐시 비대화
**해결**:
```conf
# redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
```

---

## 📝 CI/CD 통합

### GitHub Actions
```yaml
# .github/workflows/performance.yml
name: Performance Test

on:
  push:
    branches: [main, develop]

jobs:
  performance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Locust
        run: |
          pip install locust
          locust -f tests/performance/locustfile.py \
            --host=http://localhost:8000 \
            --users=100 \
            --spawn-rate=10 \
            --run-time=3m \
            --headless \
            --html=performance_report.html
      - name: Upload Report
        uses: actions/upload-artifact@v3
        with:
          name: performance-report
          path: performance_report.html
```

---

## 참고 문서

- 스펙: `docs/specs/A-requirements/A-2-3_Non_Functional_Requirements.md`
- Locust 문서: https://docs.locust.io/
