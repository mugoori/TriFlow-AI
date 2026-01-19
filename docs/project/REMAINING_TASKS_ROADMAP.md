# TriFlow AI 남은 작업 로드맵

**작성일**: 2026-01-19
**기준**: 전체 문서 검토 (36개 Spec Review + 코드 파일 검증)
**현재 완성도**: 80% (기능), 60% (스펙 준수)

---

## 📊 Executive Summary

### 프로젝트 현황
- **기능 구현**: 80% ✅ (Core 완료, Advanced 일부)
- **인프라**: 35% ⚠️ (HA 미구현)
- **문서**: 87% ✅ (최근 대폭 개선)
- **테스트**: 77% 🟡 (Backend 양호, Frontend 부족)
- **프로덕션 준비도**: 60%

### 최근 완료 (2026-01-09 ~ 2026-01-19)
- ✅ Learning Pipeline 100%
- ✅ Canary Deployment 100%
- ✅ 5-Tier RBAC 90%
- ✅ Materialized Views 100%
- ✅ Prometheus Alerting 100%
- ✅ AWS Infrastructure (Terraform) 100%

### 남은 작업량
- **기능 완성**: 21개 작업, 12-18일
- **HA 인프라**: 6개 작업, 13일
- **총 예상**: **25-31일** (1명 기준)

---

## 🎯 작업 우선순위 순서 (상세)

## Phase 1: 기능 완성도 향상 (Week 1-2)

**목표**: Core Features 80% → 98%
**예상 기간**: 3-4일 (23-32시간)

### 1-1. Intent-Role RBAC 매핑 구현 ⭐⭐⭐⭐⭐

**우선순위**: 1위 (최우선)
**예상 시간**: 4-6시간
**난이도**: 중간

#### 현재 상태
- ✅ RBAC 역할 5개 존재: ADMIN, APPROVER, OPERATOR, USER, VIEWER
- ✅ Intent 분류기 14개 카테고리 존재
- ❌ Intent와 Role 간 매핑 없음 → 보안 취약점

#### 작업 내용

**Step 1**: Intent-Role 매핑 서비스 생성 (2h)
```python
# backend/app/services/intent_role_mapper.py
from app.services.rbac_service import Role

INTENT_ROLE_MATRIX = {
    "CHECK": Role.VIEWER,
    "TREND": Role.VIEWER,
    "COMPARE": Role.VIEWER,
    "RANK": Role.USER,
    "FIND_CAUSE": Role.USER,
    "DETECT_ANOMALY": Role.OPERATOR,
    "PREDICT": Role.OPERATOR,
    "WHAT_IF": Role.OPERATOR,
    "REPORT": Role.APPROVER,
    "NOTIFY": Role.APPROVER,
    "CONTINUE": Role.VIEWER,
    "CLARIFY": Role.VIEWER,
    "STOP": Role.VIEWER,
    "SYSTEM": Role.ADMIN,
}

def check_intent_permission(intent: str, user_role: Role) -> bool:
    required_role = INTENT_ROLE_MATRIX.get(intent, Role.ADMIN)
    return user_role.value >= required_role.value
```

**Step 2**: meta_router.py 통합 (1-2h)
```python
# agents/meta_router.py 수정
from app.services.intent_role_mapper import check_intent_permission

# Intent 분류 후
if not check_intent_permission(detected_intent, current_user.role):
    return {
        "agent": "error",
        "error": f"권한 부족: {detected_intent}는 {required_role} 이상 필요"
    }
```

**Step 3**: 테스트 작성 (1-2h)
```python
# tests/test_intent_role_mapper.py
def test_viewer_can_check():
    assert check_intent_permission("CHECK", Role.VIEWER) == True

def test_viewer_cannot_notify():
    assert check_intent_permission("NOTIFY", Role.VIEWER) == False
```

#### 검증 방법
```bash
# 1. 테스트 실행
pytest tests/test_intent_role_mapper.py -v

# 2. VIEWER 로그인 후 "알림 설정해줘" → 권한 에러 확인
# 3. OPERATOR 로그인 후 "불량 예측해줘" → 성공 확인
```

#### 영향 범위
- **파일**: 2개 (신규 1, 수정 1)
- **라인 수**: ~150줄 추가
- **Breaking Change**: 없음 (기존 동작 유지)

---

### 1-2. Advanced DataScope Filtering 확장

**우선순위**: 2위
**예상 시간**: 3-4시간
**난이도**: 중간

#### 현재 상태
- ✅ factory_code, line_code 필터링
- ❌ product_family, shift_code, equipment_id 미지원

#### 작업 내용

**Step 1**: DataScope 모델 확장 (1h)
```python
# models/core.py - DataScope 확장
class DataScope:
    factory_codes: List[str]
    line_codes: List[str]
    product_families: List[str]  # 신규
    shift_codes: List[str]        # 신규
    equipment_ids: List[str]      # 신규
```

**Step 2**: data_scope_service.py 필터 로직 (1-2h)
```python
def apply_advanced_filters(query, scope: DataScope):
    if scope.product_families:
        query = query.filter(Product.family.in_(scope.product_families))
    if scope.shift_codes:
        query = query.filter(Shift.shift_code.in_(scope.shift_codes))
    if scope.equipment_ids:
        query = query.filter(Equipment.equipment_id.in_(scope.equipment_ids))
    return query
```

**Step 3**: PostgreSQL RLS 정책 (1h)
```sql
-- Row-Level Security
CREATE POLICY product_family_filter ON fact_daily_production
  USING (product_id IN (
    SELECT product_id FROM dim_product
    WHERE family = ANY(current_setting('app.allowed_product_families')::text[])
  ));
```

#### 검증 방법
```bash
# 1. DataScope 생성 시 product_family 포함
# 2. BI 쿼리 실행 → 해당 제품군만 반환 확인
# 3. Cross-tenant 테스트 → 다른 tenant 데이터 접근 불가 확인
```

---

### 1-3. Settings UI Learning Config 완전 통합

**우선순위**: 3위
**예상 시간**: 2-3시간
**난이도**: 낮음

#### 현재 상태
- ✅ LearningConfigSection.tsx 컴포넌트 존재 (373줄)
- ✅ SettingsPage에 렌더링됨
- ❌ Form validation 없음
- ❌ Error handling 부족

#### 작업 내용

**Step 1**: Form validation 추가 (1h)
```typescript
// yup schema
const learningSettingsSchema = yup.object({
  learning_min_quality_score: yup.number().min(0).max(1).required(),
  learning_auto_extract_interval_hours: yup.number().min(1).max(24),
  learning_max_tree_depth: yup.number().min(3).max(10),
});
```

**Step 2**: Error boundary (0.5h)
```typescript
<ErrorBoundary fallback={<LearningConfigError />}>
  <LearningConfigSection isAdmin={isAdmin()} />
</ErrorBoundary>
```

**Step 3**: Success feedback (0.5-1h)
- Toast notification on save
- Validation error display
- Settings reload on success

#### 검증 방법
```bash
# 1. Settings 페이지 열기
# 2. 잘못된 값 입력 (quality score = 1.5) → Validation 에러
# 3. 올바른 값 입력 → 저장 성공 Toast
# 4. 페이지 새로고침 → 저장된 값 유지 확인
```

---

### 1-4. Load Testing CI/CD 통합

**우선순위**: 4위
**예상 시간**: 3-4시간
**난이도**: 중간

#### 작업 내용

**Step 1**: k6 load test 스크립트 (1-2h)
```javascript
// tests/load/api-load-test.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  stages: [
    { duration: '2m', target: 50 },   // Ramp-up
    { duration: '5m', target: 100 },  // Stay at 100 users
    { duration: '2m', target: 0 },    // Ramp-down
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000'], // P95 < 2초
    http_req_failed: ['rate<0.05'],    // 에러율 < 5%
  },
};

export default function () {
  let res = http.get('http://localhost:8000/api/v1/bi/statcards');
  check(res, { 'status is 200': (r) => r.status === 200 });
  sleep(1);
}
```

**Step 2**: GitHub Actions workflow (1-2h)
```yaml
# .github/workflows/load-test.yml
name: Load Test

on:
  pull_request:
    branches: [main, develop]
  schedule:
    - cron: '0 2 * * *'  # Daily at 2am

jobs:
  load-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Start services
        run: docker-compose up -d
      - name: Run k6
        uses: grafana/k6-action@v0.3.0
        with:
          filename: tests/load/api-load-test.js
      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: k6-results
          path: summary.json
```

#### 검증 방법
```bash
# 로컬 실행
k6 run tests/load/api-load-test.js

# CI/CD
git push → GitHub Actions 자동 실행 → P95 확인
```

---

### 1-5. Learning Pipeline Prompt Tuning

**우선순위**: 5위
**예상 시간**: 6-8시간
**난이도**: 높음

#### 작업 내용

**Step 1**: Prompt versioning (2-3h)
```python
# models/core.py
class PromptVersion:
    prompt_id: UUID
    version: int
    template: str
    few_shot_examples: List[Dict]
    performance_metrics: Dict  # accuracy, token_count
```

**Step 2**: Few-shot example selector (2-3h)
```python
# services/prompt_tuning_service.py
def select_few_shot_examples(intent: str, n: int = 3):
    # Golden sample set에서 intent별 best examples 선택
    # Diversity + Quality score 기반
```

**Step 3**: Prompt quality 평가 (2h)
- A/B 테스트로 variant 비교
- 토큰 효율성 측정
- 응답 품질 점수

---

### 1-6. Monitoring Auto-remediation

**우선순위**: 6위
**예상 시간**: 5-7시간
**난이도**: 높음

#### 작업 내용

**Step 1**: Auto-remediation 서비스 (3-4h)
```python
# services/auto_remediation_service.py
class AutoRemediationService:
    async def handle_alert(self, alert: Alert):
        if alert.name == "HighHTTPErrorRate":
            await self.restart_backend()
        elif alert.name == "DatabaseConnectionPoolNearLimit":
            await self.increase_pool_size()
        elif alert.name == "MaterializedViewRefreshFailed":
            await self.manual_mv_refresh()
```

**Step 2**: Alert webhook 통합 (1-2h)
- alert_handler.py에 remediation 로직 추가
- Slack 알림에 remediation 액션 표시

**Step 3**: Dry-run 모드 및 로깅 (1h)

---

## Phase 2: Enterprise 기능 완성 (Week 3-4)

**목표**: Enterprise Features 완성
**예상 기간**: 4-5일 (33-43시간)

### 2-1. Enterprise Tenant Customization

**우선순위**: 7위
**예상 시간**: 8-10시간

#### 작업 내용
- Tenant 설정 CRUD API
- Tenant 테마/로고 업로드
- Feature flag per tenant
- UI: TenantSettingsPage.tsx

---

### 2-2. Prompt A/B Testing Framework

**우선순위**: 8위
**예상 시간**: 6-8시간

#### 작업 내용
- Prompt variant 관리
- A/B 실험 생성 (intent별)
- Statistical significance 계산
- Winner 자동 선택

---

### 2-3. Slack Bot Integration

**우선순위**: 9위
**예상 시간**: 6-8시간

#### 작업 내용
- Slack /commands 처리
- Bidirectional chat
- 규칙/실험 조회 명령어
- 알림 interactive 버튼

---

### 2-4. MQTT/OPC-UA Sensor Integration

**우선순위**: 10위
**예상 시간**: 8-10시간

#### 작업 내용
- MQTT broker 연결
- OPC-UA server 연결
- Real-time 센서 데이터 수집
- Buffering & retry 로직

---

### 2-5. Operational Runbook Automation

**우선순위**: 11위
**예상 시간**: 5-7시간

#### 작업 내용
- Runbook playbook 스크립트
- 자동 복구 절차
- On-call escalation
- Incident timeline 로깅

---

## Phase 3: Infrastructure HA (Week 5-8)

**목표**: 프로덕션 배포 준비
**예상 기간**: 13일

### 3-1. PostgreSQL Streaming Replication

**우선순위**: 12위
**예상 시간**: 3일

#### 작업 내용

**Day 1**: Primary-Standby 설정
```yaml
# docker-compose.ha.yml
services:
  postgres-primary:
    # Master 설정
  postgres-standby:
    # Slave 설정 (Streaming Replication)
```

**Day 2**: Patroni/PgPool 설정
- Automatic failover
- Health check & monitoring

**Day 3**: Failover 테스트
- Primary 강제 종료 → Standby 승격
- RTO < 30초 검증
- RPO = 0 검증

---

### 3-2. Redis Sentinel (3-node)

**우선순위**: 13위
**예상 시간**: 2일

#### 작업 내용

**Day 1**: Sentinel 클러스터 구성
```yaml
# docker-compose.ha.yml
services:
  redis-master:
  redis-replica-1:
  redis-replica-2:
  redis-sentinel-1:
  redis-sentinel-2:
  redis-sentinel-3:
```

**Day 2**: Failover 테스트
- Master 강제 종료 → Replica 승격
- Sentinel election 검증

---

### 3-3. Nginx API Gateway + Rate Limiting

**우선순위**: 14위
**예상 시간**: 2일

#### 작업 내용

**Day 1**: Nginx 설정
```nginx
# nginx/nginx.conf
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=100r/m;
limit_req_zone $http_x_api_key zone=key_limit:10m rate=1000r/m;

location /api/ {
    limit_req zone=api_limit burst=20 nodelay;
    proxy_pass http://backend:8000;
}
```

**Day 2**: DDoS 방어 & 테스트
- Connection limits
- Slow attack 방어
- Rate limit 테스트

---

### 3-4. Backup & Recovery 검증

**우선순위**: 15위
**예상 시간**: 2일

#### 작업 내용
- 자동 백업 스케줄 (cron)
- Point-in-time recovery 테스트
- Restore 절차 문서화
- RTO < 4h, RPO < 15min 검증

---

### 3-5. Data Encryption at Rest

**우선순위**: 16위
**예상 시간**: 3일

#### 작업 내용
- AWS KMS 또는 HashiCorp Vault
- API Key/Secret 암호화
- Key rotation 전략

---

### 3-6. TLS/HTTPS 완전 적용

**우선순위**: 17위
**예상 시간**: 1일

#### 작업 내용
- Let's Encrypt 자동 갱신
- SSL Labs A+ 달성
- HSTS 헤더 검증

---

## Phase 4: Advanced Features (Week 9-12)

### 4-1. Advanced Analytics & Forecasting

**우선순위**: 18위
**예상 시간**: 6-8시간

#### 작업 내용
- Time series forecasting (Prophet)
- Anomaly detection (Z-score, IQR)
- Predictive maintenance

---

### 4-2. GraphQL API Support

**우선순위**: 19위
**예상 시간**: 6-8시간

#### 작업 내용
- Strawberry GraphQL
- Schema 정의
- Complex query resolver

---

### 4-3. Desktop Native Features

**우선순위**: 20위
**예상 시간**: 4-6시간

#### 작업 내용
- File dialogs (Tauri)
- System notifications
- OS shortcuts

---

### 4-4. Frontend E2E Tests

**우선순위**: 21위
**예상 시간**: 1주

#### 작업 내용
- Playwright 설정
- Login, Chat, Builder flow 테스트
- Visual regression

---

## Phase 5: Documentation & Polish (Week 13-16)

### 5-1. Grafana Dashboards

**예상 시간**: 4-6시간

#### 작업 내용
- Dashboard JSON 4개 생성:
  - System Overview (existing)
  - Database Performance (new)
  - Learning Pipeline Metrics (new)
  - Business KPIs (new)

---

### 5-2. API Documentation Auto-generation

**예상 시간**: 2-3시간

#### 작업 내용
- OpenAPI schema 완성
- Swagger UI 커스터마이징
- Example responses

---

### 5-3. User Manuals

**예상 시간**: 1주

#### 작업 내용
- Admin Console 매뉴얼
- Operator SOP
- End-user 튜토리얼
- Video tutorials (선택)

---

## 📅 Timeline Summary

| Phase | 기간 | 작업 | 예상 시간 |
|-------|------|------|----------|
| **Phase 1** | Week 1-2 | 기능 완성도 향상 (6개) | 3-4일 |
| **Phase 2** | Week 3-4 | Enterprise 기능 (5개) | 4-5일 |
| **Phase 3** | Week 5-8 | Infrastructure HA (6개) | 13일 |
| **Phase 4** | Week 9-12 | Advanced Features (4개) | 4-5일 |
| **Phase 5** | Week 13-16 | Documentation & Polish | 2-3일 |
| **총 예상** | 4개월 | 21개 작업 | **26-30일** |

---

## 🎯 즉시 시작 가능한 작업 (AWS 작업과 무관)

### 이 세션에서 바로 가능

1. **Intent-Role RBAC 매핑** (4-6h) - Backend만
2. **Advanced DataScope 필터링** (3-4h) - Backend만
3. **Settings UI 통합** (2-3h) - Frontend만
4. **Load Testing CI/CD** (3-4h) - CI/CD만
5. **Grafana Dashboards** (4-6h) - Monitoring만

**총**: 16-23시간 (2-3일)

### AWS Terraform 작업 후 가능

1. **PostgreSQL HA** (3일)
2. **Redis Sentinel** (2일)
3. **Nginx Rate Limiting** (2일)
4. **Data Encryption** (3일)
5. **Backup/Recovery** (2일)

---

## 📊 작업별 ROI (투자 대비 효과)

| 작업 | 시간 | 효과 | ROI |
|------|:----:|:----:|:---:|
| Intent-Role RBAC | 4-6h | 보안 강화 ⭐⭐⭐⭐⭐ | **높음** |
| Load Testing CI/CD | 3-4h | 품질 보증 ⭐⭐⭐⭐⭐ | **높음** |
| Settings UI 통합 | 2-3h | UX 개선 ⭐⭐⭐⭐ | **매우 높음** |
| Advanced DataScope | 3-4h | Enterprise 필수 ⭐⭐⭐⭐ | **높음** |
| PostgreSQL HA | 3일 | 가용성 99.9% ⭐⭐⭐⭐⭐ | **중간** |
| Redis Sentinel | 2일 | 캐시 안정성 ⭐⭐⭐⭐ | **중간** |
| Prompt Tuning | 6-8h | AI 품질 향상 ⭐⭐⭐ | **중간** |

---

## 🚀 추천 작업 순서 (이 세션)

**다른 세션에서 AWS Terraform 작업 중**이므로:

### Option A: 빠른 성과 (1일)
1. Settings UI 통합 (2-3h)
2. Load Testing CI/CD (3-4h)
3. Grafana Dashboards (4-6h)

**총**: 9-13시간 → 즉시 효과

### Option B: 보안 강화 (1일)
1. Intent-Role RBAC 매핑 (4-6h)
2. Advanced DataScope 필터링 (3-4h)

**총**: 7-10시간 → 보안 완성도 85% → 95%

### Option C: AI 품질 향상 (1-2일)
1. Prompt Tuning (6-8h)
2. Learning Pipeline E2E 테스트 실행 (2-3h)

**총**: 8-11시간 → Learning 완성도 향상

---

## 📝 결론

**현재 프로젝트는 기능적으로 80% 완성**되어 있으며, **나머지 20%는 보안/성능/인프라 강화** 작업입니다.

**즉시 시작 가능한 고효율 작업**:
1. Intent-Role RBAC 매핑 (4-6h)
2. Settings UI 통합 (2-3h)
3. Load Testing CI/CD (3-4h)

**총 9-13시간으로 Core Features 98% 달성 가능**합니다.

---

이 로드맵은 모든 스펙 문서와 실제 코드를 교차 검증하여 작성되었습니다.
