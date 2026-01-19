# Load Testing Guide

TriFlow AI의 성능 및 부하 테스트 가이드입니다.

## Prerequisites

### k6 설치

**macOS:**
```bash
brew install k6
```

**Ubuntu/Debian:**
```bash
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update
sudo apt-get install k6
```

**Windows:**
```powershell
choco install k6
```

## Running Load Tests

### 1. Local 환경에서 실행

백엔드 서버가 실행 중이어야 합니다:

```bash
# Terminal 1: Start backend
cd backend
uvicorn app.main:app --reload

# Terminal 2: Run load test
k6 run tests/load/api-load-test.js
```

### 2. 커스텀 옵션으로 실행

**VUs(Virtual Users) 및 Duration 조정:**
```bash
k6 run --vus 50 --duration 5m tests/load/api-load-test.js
```

**환경 변수 설정:**
```bash
k6 run \
  -e BASE_URL=http://localhost:8000 \
  -e API_KEY=your_api_key_here \
  tests/load/api-load-test.js
```

### 3. CI/CD에서 실행

GitHub Actions에서 자동으로 실행됩니다:

- **Pull Request**: `main` 또는 `develop` 브랜치로 PR 생성 시
- **Scheduled**: 매일 오전 2시 (UTC)
- **Manual**: GitHub Actions 탭에서 수동 실행

## Test Scenarios

### 1. Dashboard Load (`testDashboardLoad`)
- **Endpoint**: `GET /api/v1/bi/statcards`
- **빈도**: 80% of users
- **임계값**: P95 < 2초

대시보드 통계 카드 로딩 성능 테스트

### 2. Sensor Data Query (`testSensorDataQuery`)
- **Endpoint**: `GET /api/v1/sensors`
- **빈도**: 60% of users
- **임계값**: P95 < 1.5초

센서 데이터 쿼리 성능 테스트 (다양한 필터 조합)

### 3. Agent Chat (`testAgentChat`)
- **Endpoint**: `POST /api/v1/agents/chat`
- **빈도**: 30% of users
- **임계값**: P95 < 5초

AI 에이전트 채팅 응답 시간 테스트

## Performance Thresholds

테스트 통과 조건:

| Metric | Threshold | Description |
|--------|-----------|-------------|
| **P95 Response Time** | < 2초 | 95%의 요청이 2초 이내 완료 |
| **P99 Response Time** | < 3초 | 99%의 요청이 3초 이내 완료 |
| **Error Rate** | < 5% | 실패한 요청이 5% 미만 |

## Load Test Stages

```
Stage 1 (0-2분):   0 → 50 users   (Warm-up)
Stage 2 (2-7분):   50 → 100 users (Sustained load)
Stage 3 (7-9분):   100 → 150 users (Spike test)
Stage 4 (9-12분):  150 → 100 users (Recovery)
Stage 5 (12-14분): 100 → 0 users   (Ramp-down)
```

총 소요 시간: **14분**

## Interpreting Results

### 성공적인 테스트
```
✓ http_req_duration..............: avg=850ms  p(95)=1800ms p(99)=2500ms
✓ http_req_failed................: 2.3% ✓ 0.05
✓ requests.......................: 12500
```

### 실패한 테스트
```
✗ http_req_duration..............: avg=3200ms p(95)=5800ms p(99)=8200ms
✗ http_req_failed................: 8.7% ✗ 0.05
  requests.......................: 9200
```

## Troubleshooting

### 높은 응답 시간 (P95 > 2s)

가능한 원인:
1. Database query가 비효율적 → EXPLAIN ANALYZE 확인
2. Materialized Views가 stale → Refresh 필요
3. 메모리 부족 → Docker/서버 리소스 확인
4. N+1 query 문제 → SQLAlchemy eager loading 사용

### 높은 에러율 (> 5%)

가능한 원인:
1. Database connection pool 부족 → pool size 증가
2. Rate limiting 발동 → limit 조정
3. Memory leak → 메모리 프로파일링 필요
4. Timeout 설정 부족 → timeout 증가

## Custom Metrics

스크립트에서 추가로 수집하는 메트릭:

- `errors`: 커스텀 에러율
- `request_duration`: 커스텀 응답 시간 트렌드
- `requests`: 총 요청 수

## Advanced Usage

### Smoke Test (빠른 검증)
```bash
k6 run --vus 10 --duration 1m tests/load/api-load-test.js
```

### Stress Test (한계 테스트)
```bash
k6 run --vus 500 --duration 10m tests/load/api-load-test.js
```

### Soak Test (장시간 안정성)
```bash
k6 run --vus 100 --duration 2h tests/load/api-load-test.js
```

## Results Storage

CI/CD 실행 결과는 GitHub Actions Artifacts에 저장됩니다:
- `load-test-results.json`: 상세 결과
- `load-test-summary.json`: 요약 메트릭

보관 기간: **30일**

## References

- [k6 Documentation](https://k6.io/docs/)
- [k6 Thresholds](https://k6.io/docs/using-k6/thresholds/)
- [k6 Metrics](https://k6.io/docs/using-k6/metrics/)
