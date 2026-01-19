# Alert Runbook

TriFlow AI 운영 Alert 대응 가이드

---

## 📊 Alert 목록

### HTTP Alerts

#### 1. HighHTTPErrorRate (Critical)
**조건**: HTTP 5xx 에러율 > 5% (5분간)
**대응**:
1. Backend 로그 확인: `docker-compose logs backend --tail=100`
2. 에러 패턴 분석
3. 필요시 재시작: `docker-compose restart backend`

#### 2. SlowAPIResponse (Warning)
**조건**: API P95 응답시간 > 3초 (10분간)
**대응**:
1. MV 상태 확인: `python backend/scripts/check_mv_performance.py`
2. DB 쿼리 분석: Grafana → Database 패널
3. 느린 엔드포인트 확인: Prometheus → Metrics

---

### LLM Alerts

#### 3. HighLLMCost (Warning)
**조건**: LLM 비용 > $10/시간
**대응**:
1. API 키 사용량 체크
2. 비정상 트래픽 확인
3. Rate limiting 고려

#### 4. SlowAgentResponse (Warning)
**조건**: Agent P95 응답시간 > 5초 (10분간)
**대응**:
1. Agent 로그 확인
2. LLM API 응답시간 확인
3. Prompt 최적화 검토

---

### Database Alerts

#### 5. SlowDatabaseQuery (Warning)
**조건**: DB 쿼리 P95 > 1초 (10분간)
**대응**:
1. 느린 쿼리 로그 확인
2. EXPLAIN ANALYZE 실행
3. 인덱스 추가 검토

#### 6. DatabaseConnectionPoolNearLimit (Warning)
**조건**: DB 커넥션 사용률 > 80% (5분간)
**대응**:
1. 활성 커넥션 확인
2. 커넥션 누수 확인
3. Pool 크기 증가 검토

---

### Cache Alerts

#### 7. LowCacheHitRate (Info)
**조건**: 캐시 적중률 < 50% (15분간)
**대응**:
1. 캐시 키 패턴 확인
2. TTL 설정 검토
3. 캐시 전략 개선

---

### Materialized View Alerts

#### 8. MaterializedViewRefreshFailed (Critical)
**조건**: MV 리프레시 실패 (1시간 내)
**대응**:
1. MV 상태 확인: `GET /api/v1/bi/mv-status`
2. PostgreSQL 로그 확인
3. 수동 리프레시: `POST /api/v1/bi/mv-refresh`

#### 9. SlowMVRefresh (Warning)
**조건**: MV 리프레시 > 60초 (5분간)
**대응**:
1. MV 행 개수 확인
2. 인덱스 상태 확인
3. VACUUM ANALYZE 실행 검토

---

### System Alerts

#### 10. HighActiveConnections (Warning)
**조건**: 활성 HTTP 연결 > 100개 (10분간)
**대응**:
1. 트래픽 패턴 확인
2. 비정상 요청 확인
3. Rate limiting 활성화

---

## 🧪 Alert 테스트

### 수동 테스트

```bash
# Backend webhook 직접 호출
curl -X POST http://localhost:8000/api/v1/alerts/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "alerts": [{
      "status": "firing",
      "labels": {"alertname": "TestAlert", "severity": "warning"},
      "annotations": {
        "summary": "테스트 알림",
        "description": "Alert 시스템 테스트입니다"
      },
      "startsAt": "2026-01-19T10:00:00Z",
      "endsAt": "0001-01-01T00:00:00Z"
    }]
  }'
```

### 자동 테스트 스크립트

```bash
bash scripts/test-alerts.sh
```

---

## 📞 Alert 수신 확인

### Slack
- 채널: #alerts
- 메시지 형식: 🔥/✅ Alert FIRING/RESOLVED

### Email
- 수신자: admin@example.com
- 제목: 🚨 CRITICAL: [AlertName]

---

## 🚨 On-Call 가이드

### Alert Severity 우선순위

1. **Critical** (즉시 대응):
   - HighHTTPErrorRate
   - MaterializedViewRefreshFailed

2. **Warning** (30분 내 대응):
   - SlowAPIResponse
   - HighLLMCost
   - SlowDatabaseQuery
   - DatabaseConnectionPoolNearLimit
   - SlowMVRefresh
   - HighActiveConnections

3. **Info** (모니터링만):
   - LowCacheHitRate

### Escalation

1. Alert 발생 → Slack #alerts
2. 30분 미해결 → Email (Critical만)
3. 1시간 미해결 → On-call engineer
4. 2시간 미해결 → Manager escalation

---

## 📚 관련 문서

- [Prometheus 설정](../../monitoring/prometheus.yml)
- [Alert 규칙](../../monitoring/alerts.yml)
- [DEPLOYMENT.md](DEPLOYMENT.md) - 운영 가이드
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - 문제 해결
