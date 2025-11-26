# D-3. Operation Runbook - Enhanced

## 문서 정보
- **문서 ID**: D-3
- **버전**: 2.0 (Enhanced)
- **최종 수정일**: 2025-11-26
- **상태**: Draft
- **관련 문서**:
  - D-1 DevOps & Infrastructure
  - D-2 Monitoring & Logging
  - C-5 Security & Compliance
  - C-4 Performance & Capacity

## 목차
1. [정기 점검 체크리스트](#1-정기-점검-체크리스트)
2. [배포 절차](#2-배포-절차)
3. [롤백 절차](#3-롤백-절차)
4. [장애 대응 플레이북](#4-장애-대응-플레이북)
5. [DR (Disaster Recovery) 절차](#5-dr-disaster-recovery-절차)
6. [LLMOps 운영 가이드](#6-llmops-운영-가이드)

---

## 1. 정기 점검 체크리스트

### 1.1 일일 점검 (매일 오전 09:00)

**담당**: DevOps, SRE

**체크리스트**:
- [ ] Grafana 알람 대시보드 확인 (활성 알람 0개 목표)
- [ ] 서비스 상태 확인 (Judgment, Workflow, BI, MCP Hub, Chat)
  ```bash
  kubectl get pods -n production
  kubectl get hpa -n production
  ```
- [ ] LLM 실패율 및 비용 확인
  ```promql
  rate(llm_parsing_failures_total[24h])
  increase(llm_cost_usd_total[24h])
  ```
- [ ] Workflow DLQ (Dead Letter Queue) 확인
  ```sql
  SELECT count(*) FROM workflow_instances WHERE status = 'FAILED' AND created_at >= NOW() - INTERVAL '1 day';
  ```
- [ ] MCP 타임아웃 및 Circuit Breaker 상태
  ```promql
  rate(mcp_call_timeouts_total[1h])
  circuit_breaker_state{state="OPEN"}
  ```
- [ ] DB 및 Redis 상태
  ```bash
  # PostgreSQL 연결 수
  psql -h $DB_HOST -U postgres -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"

  # Redis 메모리 사용량
  redis-cli INFO memory | grep used_memory_human
  ```

**이상 발견 시 조치**:
- 알람 발생: D-2 알람 규칙 확인 후 담당자 할당
- 서비스 다운: D-3 장애 대응 플레이북 참조
- LLM 비용 80% 초과: 저가형 모델 전환 검토

---

### 1.2 주간 점검 (매주 월요일 오전 10:00)

**담당**: DevOps, Backend Lead

**체크리스트**:
- [ ] 슬로우 쿼리 리뷰 (pg_stat_statements)
  ```sql
  SELECT
    query,
    calls,
    mean_exec_time,
    max_exec_time
  FROM pg_stat_statements
  WHERE mean_exec_time > 500
  ORDER BY mean_exec_time DESC
  LIMIT 20;
  ```
- [ ] 인덱스 사용률 확인 및 조정
  ```sql
  SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan
  FROM pg_stat_user_indexes
  WHERE idx_scan = 0 AND pg_relation_size(indexrelid) > 100000
  ORDER BY pg_relation_size(indexrelid) DESC;
  ```
- [ ] 캐시 적중률 확인 (목표 > 40%)
  ```promql
  rate(judgment_cache_hits_total[7d]) /
  (rate(judgment_cache_hits_total[7d]) + rate(judgment_cache_misses_total[7d]))
  ```
- [ ] 로그 보존 및 스토리지 사용량
  ```bash
  # Loki 스토리지 사용량
  du -sh /var/lib/loki/

  # 로그 아카이빙 상태 (S3)
  aws s3 ls s3://factory-ai-logs/archive/ --recursive --human-readable
  ```
- [ ] DB 파티션 확인 (미래 3개월 파티션 존재 확인)
  ```sql
  SELECT tablename FROM pg_tables
  WHERE schemaname = 'core' AND tablename LIKE 'judgment_executions_y%'
  ORDER BY tablename DESC
  LIMIT 5;
  ```

**조치 사항**:
- 슬로우 쿼리: 인덱스 추가, 쿼리 최적화
- 캐시 적중률 낮음: TTL 조정, 프리워밍
- 파티션 부족: 파티션 생성 스크립트 실행

---

### 1.3 월간 점검 (매월 1일 오전 10:00)

**담당**: DevOps Lead, PM

**체크리스트**:
- [ ] 백업 복구 리허설
  ```bash
  # 최신 백업 다운로드
  aws s3 cp s3://factory-ai-backups/postgres/daily/$(date +%Y%m%d).dump.gz /tmp/

  # 테스트 DB 복구
  gunzip /tmp/factory_ai_*.dump.gz
  pg_restore -h test-db -U postgres -d test_db /tmp/factory_ai_*.dump
  ```
- [ ] 권한 및 Secret 검토
  ```bash
  # 만료 예정 Secret 확인
  kubectl get secrets -n production -o json | jq '.items[] | select(.metadata.creationTimestamp < "30 days ago") | .metadata.name'
  ```
- [ ] Rule/Prompt/DSL 변경 이력 리뷰
  ```sql
  SELECT
    deployment_id,
    target_type,
    old_version,
    new_version,
    deployed_at,
    status,
    rollback_occurred
  FROM rule_deployments
  WHERE deployed_at >= NOW() - INTERVAL '30 days'
  ORDER BY deployed_at DESC;
  ```
- [ ] 사용자 활동 로그 검토 (비정상 접근 패턴)
  ```sql
  SELECT
    user_id,
    COUNT(*) as login_count,
    COUNT(DISTINCT ip_address) as distinct_ips
  FROM access_logs
  WHERE created_at >= NOW() - INTERVAL '30 days'
  GROUP BY user_id
  HAVING COUNT(DISTINCT ip_address) > 5
  ORDER BY login_count DESC;
  ```

---

### 1.4 분기 점검 (분기 첫 주)

**담당**: 전체 팀 (DevOps, Backend, QA)

**체크리스트**:
- [ ] DR 리허설 (Full Failover)
  - DR 사이트로 전환
  - 데이터 정합성 검증
  - 서비스 기능 스모크 테스트
  - 원 사이트로 복구
- [ ] Circuit Breaker 및 알람 정책 재점검
  - 알람 발생 이력 분석
  - 임계값 조정 (너무 많이 또는 적게 발생)
- [ ] 보안 키 로테이션
  - JWT Secret 교체 (90일마다)
  - API Key 로테이션
  - DB 비밀번호 변경
- [ ] 의존성 업데이트
  ```bash
  # Python 의존성 취약점 확인
  pip-audit

  # npm 의존성 취약점 확인
  npm audit

  # 컨테이너 이미지 스캔
  trivy image factory-ai/judgment-service:latest
  ```

---

## 2. 배포 절차

### 2.1 표준 배포 흐름

```
[코드 커밋] → [CI 실행] → [Staging 배포] → [스모크 테스트] → [승인] → [Canary 배포] → [모니터링] → [Full 배포]
```

### 2.2 상세 배포 단계

#### Step 1: Staging 배포

**담당**: DevOps

**절차**:
1. Git에 코드 푸시 (main 브랜치)
   ```bash
   git push origin main
   ```
2. CI 파이프라인 자동 실행 (GitHub Actions)
   - Lint, Test, Security Scan
   - Docker 이미지 빌드 및 푸시
3. Staging 배포 (ArgoCD 자동)
   ```bash
   # ArgoCD 상태 확인
   argocd app get judgment-service-staging
   argocd app sync judgment-service-staging
   ```
4. 배포 완료 확인
   ```bash
   kubectl rollout status deployment/judgment-service -n staging
   ```

#### Step 2: 스모크 테스트

**담당**: QA

**테스트 케이스**:
- [ ] Judgment 실행 (Rule Only, LLM Only, Hybrid)
- [ ] Workflow 실행 (Simple, Complex)
- [ ] BI 쿼리 실행 (자연어 → 차트)
- [ ] Slack Bot 응답
- [ ] 피드백 제출

**자동 스모크 테스트**:
```bash
# Postman Collection 실행
newman run tests/e2e/smoke-tests.postman_collection.json \
  --environment staging.postman_environment.json
```

#### Step 3: Production Canary 배포

**담당**: DevOps, Backend Lead

**절차**:
1. Canary 배포 시작 (Helm)
   ```bash
   # Canary 설정 (10% 트래픽)
   helm upgrade judgment-service ./helm/judgment-service \
     --set canary.enabled=true \
     --set canary.weight=10 \
     --set image.tag=$NEW_VERSION \
     -n production
   ```
2. 메트릭 모니터링 (10~20분)
   - Grafana 대시보드: Canary Deployment
   - 주요 메트릭:
     - 에러율: < 1%
     - P95 지연: < 2.5초
     - LLM 파싱 실패율: < 0.5%
3. 자동 또는 수동 승격
   - 성공 기준 만족: 100% 배포
   - 실패: 자동 롤백

**성공 기준**:
```yaml
canary_success_criteria:
  error_rate_max: 0.01  # 1%
  latency_p95_max_ms: 2500
  llm_parsing_failure_rate_max: 0.005  # 0.5%
  duration_minutes: 20
```

---

## 3. 롤백 절차

### 3.1 애플리케이션 롤백

**시나리오**: 신규 배포 후 에러율 급증

**절차**:
1. 롤백 결정 (DevOps Lead)
2. Helm 롤백 실행
   ```bash
   # 이전 버전 확인
   helm history judgment-service -n production

   # 롤백 (Revision 3으로)
   helm rollback judgment-service 3 -n production
   ```
3. 배포 상태 확인
   ```bash
   kubectl rollout status deployment/judgment-service -n production
   ```
4. 메트릭 확인 (5분)
   - 에러율 정상화 확인
   - P95 지연 정상화 확인
5. 사후 분석
   - 롤백 원인 기록
   - RCA (Root Cause Analysis)
   - 재발 방지 계획

**롤백 스크립트**:
```bash
#!/bin/bash
# rollback.sh

SERVICE_NAME=$1
REVISION=$2

if [ -z "$SERVICE_NAME" ] || [ -z "$REVISION" ]; then
  echo "Usage: ./rollback.sh <service-name> <revision>"
  exit 1
fi

echo "Rolling back $SERVICE_NAME to revision $REVISION..."
helm rollback $SERVICE_NAME $REVISION -n production

echo "Waiting for rollout to complete..."
kubectl rollout status deployment/$SERVICE_NAME -n production

echo "Rollback completed. Checking metrics..."
# Prometheus 쿼리로 에러율 확인
# ...

echo "Rollback successful!"
```

### 3.2 데이터베이스 마이그레이션 롤백

**시나리오**: 마이그레이션 후 데이터 오류 발생

**절차**:
1. 마이그레이션 중단
   ```bash
   # 현재 버전 확인
   alembic current

   # 이전 버전으로 다운그레이드
   alembic downgrade -1
   ```
2. 데이터 정합성 확인
   ```sql
   -- 주요 테이블 row count
   SELECT
     'judgment_executions' AS table_name,
     COUNT(*) AS row_count
   FROM judgment_executions
   UNION ALL
   SELECT 'workflow_instances', COUNT(*) FROM workflow_instances;
   ```
3. 애플리케이션 재시작 (이전 버전)
4. 마이그레이션 실패 원인 분석

---

## 4. 장애 대응 플레이북

### 4.1 Judgment Service 다운

**증상**:
- Health Check 실패
- 503 에러 반환
- Grafana 알람: JudgmentServiceDown

**조치**:
1. Pod 상태 확인
   ```bash
   kubectl get pods -n production -l app=judgment-service
   kubectl describe pod <pod-name> -n production
   kubectl logs <pod-name> -n production --tail=100
   ```
2. Pod 재시작 (필요 시)
   ```bash
   kubectl delete pod <pod-name> -n production
   ```
3. 리소스 확인 (OOM, CPU Throttling)
   ```bash
   kubectl top pods -n production -l app=judgment-service
   ```
4. HPA 스케일아웃 확인
   ```bash
   kubectl get hpa -n production
   ```
5. DB 연결 확인
   ```sql
   SELECT 1;
   ```
6. Redis 연결 확인
   ```bash
   redis-cli PING
   ```

**근본 원인 후보**:
- OOM (Out of Memory) → 메모리 Limit 증가
- DB Connection Pool 고갈 → Pool Size 증가
- LLM API 장애 → Fallback to Rule Only
- 코드 버그 → 롤백

---

### 4.2 LLM API 장애 또는 타임아웃 증가

**증상**:
- LLM 호출 실패율 > 5%
- LLM 응답 시간 > 30초
- Grafana 알람: LLMHighFailureRate

**조치**:
1. LLM API 상태 확인
   ```bash
   curl https://status.openai.com/
   ```
2. 모델 전환 (GPT-4 → GPT-4o-mini)
   ```python
   # 환경변수 업데이트
   kubectl set env deployment/judgment-service \
     DEFAULT_LLM_MODEL=gpt-4o-mini \
     -n production
   ```
3. Fallback Policy 활성화 (RULE_FALLBACK)
   ```sql
   UPDATE workflows
   SET policy = 'RULE_FALLBACK'
   WHERE policy = 'LLM_ONLY';
   ```
4. 타임아웃 조정 (15초 → 10초)
5. 재시도 횟수 조정 (3회 → 2회)

**복구 확인**:
- LLM 호출 성공률 > 98%
- Judgment 실행 정상 (Fallback 사용)

---

### 4.3 PostgreSQL 성능 저하

**증상**:
- 쿼리 응답 시간 > 2초
- DB CPU > 90%
- Grafana 알람: DatabaseHighCPU

**조치**:
1. 활성 쿼리 확인
   ```sql
   SELECT
     pid,
     now() - query_start AS duration,
     state,
     query
   FROM pg_stat_activity
   WHERE state = 'active'
   ORDER BY duration DESC
   LIMIT 10;
   ```
2. 슬로우 쿼리 Kill (필요 시)
   ```sql
   SELECT pg_terminate_backend(pid)
   FROM pg_stat_activity
   WHERE state = 'active' AND now() - query_start > INTERVAL '30 seconds';
   ```
3. Lock 확인
   ```sql
   SELECT
     locktype,
     database,
     relation::regclass,
     mode,
     granted
   FROM pg_locks
   WHERE NOT granted;
   ```
4. Connection 수 확인
   ```sql
   SELECT count(*) FROM pg_stat_activity;
   SHOW max_connections;
   ```
5. VACUUM 실행 (필요 시)
   ```bash
   vacuumdb -h $DB_HOST -U postgres -d factory_ai --analyze
   ```

**임시 완화 조치**:
- 캐시 TTL 증가 (부하 감소)
- Read Replica로 읽기 부하 분산
- 비필수 쿼리 비활성화 (대시보드 리프레시)

---

### 4.4 Rule 배포 후 오경보 급증

**증상**:
- Judgment 결과 부정 피드백 > 20%
- Slack 알람 폭증
- 사용자 클레임

**조치**:
1. 피드백 분석
   ```sql
   SELECT
     execution_id,
     result,
     feedback_value,
     comment
   FROM feedbacks f
   JOIN judgment_executions j ON f.execution_id = j.id
   WHERE f.created_at >= NOW() - INTERVAL '1 hour'
     AND f.feedback_value = 'thumbs_down'
   LIMIT 20;
   ```
2. 최근 배포 확인
   ```sql
   SELECT * FROM rule_deployments
   ORDER BY deployed_at DESC
   LIMIT 1;
   ```
3. 롤백 결정
   ```bash
   # Learning Service API 호출
   curl -X POST https://api.factory-ai.com/api/v1/learning/rollback \
     -H "Authorization: Bearer $TOKEN" \
     -d '{"deployment_id": "deploy-123"}'
   ```
4. Zwave Simulation 실행 (What-if)
   ```bash
   # 구버전 vs 신버전 비교
   curl -X POST https://api.factory-ai.com/api/v1/judgment/simulate \
     -d '{
       "execution_id": "jud-456",
       "override_versions": {
         "ruleset": "v1.3.0"  # 이전 버전
       }
     }'
   ```

**복구 확인**:
- 부정 피드백 비율 < 10% (정상 수준)
- 알람 빈도 정상화

---

## 5. DR (Disaster Recovery) 절차

### 5.1 DR 트리거 조건

| 시나리오 | 트리거 | RTO | RPO |
|---------|--------|-----|-----|
| **리전 장애** | AWS 리전 전체 중단 | 4시간 | 30분 |
| **DB 손상** | 데이터 손실, 복구 불가 | 2시간 | 15분 (WAL) |
| **대규모 데이터 오염** | 잘못된 Rule 배포 → 대량 오판 | 1시간 | 5분 |

### 5.2 DR 복구 절차

#### Phase 1: 선언 및 소집 (15분)

**조치**:
1. DR 선언 (DevOps Lead)
2. On-call 팀 소집 (Slack, 전화)
3. 커뮤니케이션 채널 오픈 (#incident-dr)
4. 타임라인 기록 시작

#### Phase 2: 백업 무결성 확인 (30분)

**조치**:
1. 최신 백업 다운로드
   ```bash
   aws s3 cp s3://factory-ai-backups/postgres/daily/latest.dump.gz /tmp/
   ```
2. 백업 SHA 검증
   ```bash
   sha256sum /tmp/latest.dump.gz
   # 백업 메타데이터와 비교
   ```
3. PITR 시점 결정
   - RPO 목표: 30분 이내
   - WAL 아카이브 최신 시각 확인

#### Phase 3: DB 복구 (1~2시간)

**조치**:
1. DR 사이트 PostgreSQL Standby → Primary 승격
   ```sql
   SELECT pg_promote();
   ```
2. WAL 아카이브 재생 (PITR)
   ```bash
   # postgresql.conf
   restore_command = 'aws s3 cp s3://factory-ai-backups/postgres/wal/%f %p'

   # 특정 시점까지 복구
   recovery_target_time = '2025-11-26 15:45:00'
   ```
3. DB 헬스 체크
   ```sql
   SELECT 1;
   SELECT pg_is_in_recovery();  -- false (Primary)
   ```

#### Phase 4: 서비스 복구 (30분)

**조치**:
1. DR 사이트 서비스 활성화
   ```bash
   kubectl scale deployment/judgment-service --replicas=3 -n production-dr
   ```
2. DNS 전환 (Route53)
   ```bash
   aws route53 change-resource-record-sets \
     --hosted-zone-id Z1234567890ABC \
     --change-batch file://dns-change-dr.json
   ```
3. 서비스 헬스 확인
   ```bash
   curl https://api.factory-ai.com/health
   ```

#### Phase 5: 데이터 정합성 검증 (30분)

**SQL 검증 체크리스트**:
```sql
-- 1. 최근 1일 Judgment 로그 건수
SELECT COUNT(*) FROM judgment_executions
WHERE executed_at >= NOW() - INTERVAL '1 day';
-- 기대: ~1000건 (평소 수준)

-- 2. Workflow 인스턴스 상태 분포
SELECT status, COUNT(*) FROM workflow_instances
WHERE started_at >= NOW() - INTERVAL '1 day'
GROUP BY status;
-- 기대: COMPLETED > 95%

-- 3. Rule 버전 일치
SELECT DISTINCT ruleset_version FROM judgment_executions
WHERE executed_at >= NOW() - INTERVAL '1 hour';
-- 기대: v1.4.0 (최신 버전)

-- 4. 캐시 클리어 확인
-- Redis 연결 후
FLUSHALL
-- 재빌드 확인 (첫 요청 시 Cache MISS)
```

#### Phase 6: 비즈니스 검증 (30분)

**스모크 테스트**:
- [ ] Judgment 실행 (대표 3개 Workflow)
- [ ] Workflow 실행 (RCA, 알림)
- [ ] BI 쿼리 (대시보드 로딩)
- [ ] Slack Bot 응답
- [ ] Canary 배포 기능

**고객사 통지**:
```
Subject: [긴급] AI Factory 서비스 복구 완료

고객사 담당자님,

일시적인 시스템 장애로 인해 DR 복구를 진행하였습니다.

장애 기간: 2025-11-26 15:00 ~ 16:30 (1.5시간)
영향 범위: 모든 서비스 (Judgment, Workflow, BI)
복구 완료: 2025-11-26 16:30
데이터 손실: 없음 (RPO 15분 이내 복구)

현재 모든 서비스가 정상 동작 중입니다.
불편을 드려 죄송합니다.

AI Factory 운영팀
```

---

## 6. LLMOps 운영 가이드

### 6.1 Intent Rule 승격 (주간 작업)

**목적**: Intent 분류 정확도 향상

**절차**:
1. 저신뢰도 + 긍정 피드백 로그 추출
   ```sql
   SELECT
     i.utterance,
     i.intent,
     i.confidence,
     f.feedback_value
   FROM intent_logs i
   JOIN feedbacks f ON f.execution_id = i.id
   WHERE i.confidence < 0.8
     AND f.feedback_value = 'thumbs_up'
     AND i.created_at >= NOW() - INTERVAL '7 days'
   ORDER BY i.confidence ASC
   LIMIT 20;
   ```
2. 빈도수 상위 패턴 식별
3. Learning UI에서 Rule 후보 등록
4. Zwave Simulation 실행 (영향도 확인)
5. 승인 후 배포

---

## 결론

본 문서(D-3)는 **AI Factory Decision Engine** 의 운영 매뉴얼 및 장애 대응 플레이북을 상세히 수립하였다.

### 주요 성과
1. **정기 점검**: 일일, 주간, 월간, 분기 체크리스트
2. **배포 절차**: Staging → Canary → Full 배포 (단계별 상세)
3. **롤백 절차**: 애플리케이션, DB 마이그레이션 롤백
4. **장애 대응**: 5가지 주요 장애 시나리오 및 플레이북
5. **DR 절차**: 6단계 복구 절차 (RTO 4h, RPO 30m)
6. **LLMOps**: Intent Rule 승격, Prompt 튜닝 (주간/월간)

### 다음 단계
1. 운영 팀 교육 (Runbook 숙지)
2. DR 리허설 실시 (분기 1회)
3. 장애 대응 훈련 (GameDay)
4. On-call 일정 수립

---

## 문서 이력
| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2025-11-05 | DevOps Team | 초안 작성 |
| 2.0 | 2025-11-26 | DevOps Team | Enhanced 버전 (배포/롤백/DR 상세 절차 추가) |
