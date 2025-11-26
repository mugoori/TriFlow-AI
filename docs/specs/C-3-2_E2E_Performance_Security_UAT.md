# C-3-2. Test Plan & QA Strategy - E2E, Performance, Security, UAT

## 문서 정보
- **문서 ID**: C-3-2
- **버전**: 2.0 (Enhanced)
- **최종 수정일**: 2025-11-26
- **상태**: Draft
- **선행 문서**: C-3-1

## 목차
1. [E2E 테스트 (End-to-End Testing)](#1-e2e-테스트-end-to-end-testing)
2. [성능 테스트 (Performance Testing)](#2-성능-테스트-performance-testing)
3. [보안 테스트 (Security Testing)](#3-보안-테스트-security-testing)
4. [UAT (User Acceptance Testing)](#4-uat-user-acceptance-testing)
5. [결함 관리 및 릴리스 게이트](#5-결함-관리-및-릴리스-게이트)

---

## 1. E2E 테스트 (End-to-End Testing)

### 1.1 개요
E2E 테스트는 사용자 관점에서 전체 시스템 흐름을 검증한다.

**목표**:
- 핵심 사용자 시나리오 10개 100% 통과
- 실제 환경과 유사한 조건 (Staging)
- UI 포함 전체 흐름 검증

### 1.2 E2E 테스트 프레임워크

**Playwright** (Python/TypeScript 지원)

**프로젝트 구조**:
```
tests/
└── e2e/
    ├── scenarios/
    │   ├── test_judgment_flow.py
    │   ├── test_workflow_rca.py
    │   ├── test_bi_query.py
    │   └── test_canary_deployment.py
    ├── pages/
    │   ├── login_page.py
    │   ├── dashboard_page.py
    │   ├── judgment_page.py
    │   └── workflow_page.py
    └── conftest.py
```

### 1.3 E2E 테스트 케이스

#### TC-E2E-001: 불량 판단 요청 (Slack → Judgment → 알림)

**시나리오**:
1. Slack Bot이 멘션 수신 (`@AI-Factory LINE-A 불량 판단`)
2. Intent 분류 (defect_inquiry)
3. Judgment 실행 (Rule + LLM)
4. Slack 알림 발송 (결과 카드)
5. 사용자 피드백 (👍)

**테스트 코드**:
```python
# tests/e2e/scenarios/test_slack_judgment.py
import pytest
from slack_sdk import WebClient

@pytest.mark.e2e
async def test_slack_mention_to_judgment(slack_client: WebClient, api_client):
    """Slack 멘션 → Judgment → 알림"""
    # 1. Slack 멘션 전송 (시뮬레이션)
    message = "@AI-Factory LINE-A 불량 판단"
    slack_response = await send_slack_mention(slack_client, message)

    # 2. Chat Service가 Intent 분류하는지 확인 (최대 5초 대기)
    await asyncio.sleep(2)

    # 3. Judgment 실행 로그 확인
    judgments = await api_client.get('/api/v1/judgment/recent?limit=1')
    assert len(judgments['data']) == 1

    latest_judgment = judgments['data'][0]
    assert latest_judgment['workflow_id'] == 'defect-judgment-001'
    assert latest_judgment['result']['status'] in ['HIGH_DEFECT', 'MODERATE_DEFECT', 'NORMAL']

    # 4. Slack 알림 확인 (Slack API 히스토리 조회)
    messages = await get_slack_messages(slack_client, channel='#factory-alerts', limit=1)
    assert len(messages) > 0

    last_message = messages[0]
    assert 'HIGH_DEFECT' in last_message['text'] or 'blocks' in last_message

    # 5. 피드백 전송 (버튼 클릭 시뮬레이션)
    feedback_response = await api_client.post('/api/v1/feedback', json={
        'execution_id': latest_judgment['execution_id'],
        'feedback_type': 'thumbs',
        'feedback_value': 'up'
    })
    assert feedback_response.status_code == 201
```

---

#### TC-E2E-002: RCA Workflow 실행

**시나리오**:
1. 사용자가 불량 이벤트 선택
2. RCA Workflow 실행 버튼 클릭
3. Workflow 실행 (데이터 수집 → 분석 → 보고서 생성)
4. RCA 보고서 표시 (추정 원인, 근거 차트)

**테스트 코드** (Playwright):
```python
# tests/e2e/scenarios/test_workflow_rca.py
from playwright.async_api import async_playwright

@pytest.mark.e2e
async def test_rca_workflow_execution():
    """RCA Workflow E2E"""
    async with async_playwright() as p:
        # 1. 브라우저 시작
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # 2. 로그인
        await page.goto('http://localhost:3000/login')
        await page.fill('input[name="email"]', 'test@factory-ai.com')
        await page.fill('input[name="password"]', 'test123')
        await page.click('button[type="submit"]')

        # 3. 불량 이벤트 페이지 이동
        await page.goto('http://localhost:3000/defects')
        await page.wait_for_selector('.defect-event-list')

        # 4. 첫 번째 불량 이벤트 선택
        await page.click('.defect-event-list .event-card:first-child')

        # 5. RCA 실행 버튼 클릭
        await page.click('button[data-testid="btn-run-rca"]')

        # 6. Workflow 실행 대기 (최대 60초)
        await page.wait_for_selector('.rca-report', timeout=60000)

        # 7. RCA 보고서 확인
        report_title = await page.text_content('.rca-report h2')
        assert '근본 원인 분석' in report_title

        # 8. 추정 원인 확인
        causes = await page.query_selector_all('.rca-report .estimated-cause')
        assert len(causes) >= 1
        assert len(causes) <= 3  # Top 3

        # 9. 스크린샷 (증거)
        await page.screenshot(path='screenshots/rca_report.png')

        await browser.close()
```

---

## 2. 성능 테스트 (Performance Testing)

### 2.1 개요
성능 테스트는 응답 시간, 처리량, 리소스 사용률을 검증한다.

**목표**:
- Judgment P50 < 1.5s, P95 < 2.5s
- BI P50 < 2s, P95 < 3s
- Workflow Simple P95 < 10s
- 동시 사용자 500명 지원

### 2.2 성능 테스트 도구

**Locust** (Python 기반 부하 테스트)

**프로젝트 구조**:
```
tests/
└── performance/
    ├── locustfile.py
    ├── judgment_load.py
    ├── bi_load.py
    └── workflow_load.py
```

### 2.3 성능 테스트 케이스

#### TC-PERF-001: Judgment 부하 테스트 (50 TPS)

**목적**: Judgment Service 50 TPS 처리 검증

```python
# tests/performance/judgment_load.py
from locust import HttpUser, task, between

class JudgmentLoadTest(HttpUser):
    wait_time = between(1, 3)  # 1~3초 대기

    @task(weight=7)
    def execute_judgment_cached(self):
        """캐시 적중 시나리오 (70%)"""
        # 동일한 입력 (캐시 적중 기대)
        self.client.post('/api/v1/judgment/execute', json={
            'workflow_id': 'test-workflow-001',
            'input_data': {
                'line_code': 'LINE-A',
                'defect_count': 5,
                'production_count': 100
            },
            'policy': 'RULE_ONLY'
        })

    @task(weight=3)
    def execute_judgment_uncached(self):
        """캐시 미스 시나리오 (30%)"""
        # 랜덤 입력 (캐시 미스)
        import random
        self.client.post('/api/v1/judgment/execute', json={
            'workflow_id': 'test-workflow-001',
            'input_data': {
                'line_code': 'LINE-A',
                'defect_count': random.randint(1, 10),
                'production_count': 100
            },
            'policy': 'HYBRID_WEIGHTED'
        })
```

**실행**:
```bash
# 50 TPS, 10분간 테스트
locust -f tests/performance/judgment_load.py \
  --host http://staging.factory-ai.com \
  --users 100 \
  --spawn-rate 10 \
  --run-time 10m \
  --headless
```

**검증 기준**:
- [ ] P50 < 1.5초
- [ ] P95 < 2.5초
- [ ] P99 < 5초
- [ ] 에러율 < 1%
- [ ] CPU < 80%, 메모리 < 80%

---

#### TC-PERF-020: BI 쿼리 부하 테스트

**목적**: BI Service 동시 쿼리 처리 검증

```python
# tests/performance/bi_load.py
from locust import HttpUser, task

class BILoadTest(HttpUser):
    @task
    def execute_nl_query(self):
        """자연어 BI 쿼리"""
        queries = [
            "지난 7일간 LINE-A 생산량",
            "오늘 전체 라인 불량률",
            "지난 달 OEE 트렌드",
            "라인별 평균 생산량 비교"
        ]

        import random
        query = random.choice(queries)

        self.client.post('/api/v1/bi/execute-nl-query', json={
            'query_text': query
        })
```

**검증 기준**:
- [ ] P50 < 2초
- [ ] P95 < 3초
- [ ] 캐시 적중률 > 30%
- [ ] Pre-agg 사용률 > 50%

---

#### TC-PERF-030: Stress Test (한계 테스트)

**목적**: 시스템 한계 파악 및 안정성 검증

```python
# tests/performance/stress_test.py
from locust import HttpUser, task, between

class StressTest(HttpUser):
    wait_time = between(0.1, 0.5)  # 짧은 대기 (부하 증가)

    @task
    def mixed_requests(self):
        """혼합 요청 (Judgment, Workflow, BI)"""
        import random
        endpoint = random.choice([
            '/api/v1/judgment/execute',
            '/api/v1/workflows/execute',
            '/api/v1/bi/execute-nl-query'
        ])

        self.client.post(endpoint, json={...})
```

**단계적 부하 증가**:
```
사용자 수: 100 → 200 → 300 → 400 → 500 → 600 (매 5분마다 증가)
```

**검증 기준**:
- [ ] 500 사용자까지 에러율 < 1%
- [ ] 600 사용자 시점에서 한계 파악 (에러율 급증, 응답 시간 폭증)
- [ ] 자동 스케일아웃 동작 (HPA)
- [ ] 한계 도달 후 복구 (부하 감소 시)

---

## 2.4 성능 테스트 결과 분석

**Locust 보고서 예시**:
```
Type     Name                  # reqs  # fails  Avg    Min    Max    Median  P95    P99    req/s
POST     /api/v1/judgment      5000    25       1200   300    8000   1100    2400   4500   50.2
POST     /api/v1/bi/execute    2000    10       1800   500    10000  1600    2800   5200   20.1

Total RPS: 70.3
Error Rate: 0.7%
```

**분석**:
- ✅ Judgment P95 2400ms < 2500ms (목표 달성)
- ✅ BI P95 2800ms < 3000ms (목표 달성)
- ✅ 에러율 0.7% < 1% (목표 달성)
- ⚠️ P99가 목표 대비 높음 → 타임아웃 최적화 필요

---

## 3. 보안 테스트 (Security Testing)

### 3.1 개요
보안 테스트는 취약점을 탐지하고 규제 준수를 검증한다.

**목표**:
- OWASP Top 10 취약점 제로
- Critical/High 취약점 0개
- PII 마스킹 100% 동작

### 3.2 보안 테스트 도구

| 도구 | 용도 | 실행 빈도 |
|------|------|----------|
| **OWASP ZAP** | 동적 분석 (DAST) | 스프린트 종료 |
| **Bandit** | 정적 분석 (SAST) - Python | 매 커밋 |
| **npm audit** | 의존성 취약점 - Node.js | 매 PR |
| **Trivy** | 컨테이너 이미지 스캔 | 매 빌드 |
| **SonarQube** | 코드 품질 및 보안 | 매 PR |

### 3.3 보안 테스트 케이스

#### TC-SEC-010: SQL Injection 방어

**목적**: SQL Injection 공격 차단 검증

```python
# tests/security/test_sql_injection.py
import pytest

@pytest.mark.security
async def test_sql_injection_defense(client):
    """SQL Injection 공격 차단"""
    # Arrange: 악의적 입력
    malicious_inputs = [
        "LINE-A' OR '1'='1",
        "LINE-A'; DROP TABLE judgment_executions; --",
        "LINE-A' UNION SELECT * FROM users --"
    ]

    for malicious_input in malicious_inputs:
        # Act
        response = await client.post('/api/v1/judgment/execute', json={
            'workflow_id': 'test-workflow-001',
            'input_data': {
                'line_code': malicious_input,  # SQL Injection 시도
                'defect_count': 5,
                'production_count': 100
            }
        })

        # Assert: 정상 처리 (Prepared Statement로 방어)
        assert response.status_code in [200, 400]

        # DB 무결성 확인
        tables = await db_session.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'core'")
        table_names = [row[0] for row in tables]
        assert 'judgment_executions' in table_names  # 테이블 삭제 안 됨
```

---

#### TC-SEC-020: PII 마스킹 검증

**목적**: LLM 입력 및 로그에 PII 마스킹 적용 확인

```python
# tests/security/test_pii_masking.py
@pytest.mark.security
async def test_pii_masking_in_llm_input(client, db_session):
    """PII 마스킹 (LLM 입력)"""
    # Arrange: PII 포함 입력
    input_with_pii = {
        'line_code': 'LINE-A',
        'comment': '고객 홍길동(010-1234-5678, hong@example.com)의 주문 제품에서 불량 발생'
    }

    # Act: Judgment 실행
    response = await client.post('/api/v1/judgment/execute', json={
        'workflow_id': 'test-workflow-001',
        'input_data': input_with_pii,
        'policy': 'LLM_ONLY'
    })

    # Assert: LLM 호출 로그 조회
    llm_logs = await db_session.execute(
        "SELECT input_data FROM llm_calls ORDER BY created_at DESC LIMIT 1"
    )
    llm_input = llm_logs.fetchone()[0]

    # PII 마스킹 확인
    assert '홍*동' in llm_input or '홍길동' not in llm_input
    assert '010-****-5678' in llm_input or '010-1234-5678' not in llm_input
    assert 'h***@example.com' in llm_input or 'hong@example.com' not in llm_input
```

---

#### TC-SEC-030: Webhook HMAC 서명 검증

**목적**: Webhook 서명 검증 및 위조 방어

```python
# tests/security/test_webhook_security.py
import hmac
import hashlib
import time

@pytest.mark.security
async def test_webhook_signature_verification(client):
    """Webhook HMAC 서명 검증"""
    # Arrange
    webhook_secret = 'test-secret-key'
    payload = {'event': 'approval.approved', 'instance_id': 'inst-123'}
    timestamp = int(time.time())

    # 올바른 서명 생성
    message = f"{timestamp}.{json.dumps(payload)}"
    signature = hmac.new(
        webhook_secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    # Act: 올바른 서명으로 Webhook 전송
    response = await client.post('/api/v1/webhooks/approval', json=payload, headers={
        'X-Signature': f'sha256={signature}',
        'X-Timestamp': str(timestamp)
    })

    # Assert: 성공
    assert response.status_code == 200

    # Act: 잘못된 서명으로 Webhook 전송
    response_invalid = await client.post('/api/v1/webhooks/approval', json=payload, headers={
        'X-Signature': 'sha256=invalid_signature',
        'X-Timestamp': str(timestamp)
    })

    # Assert: 실패 (401 Unauthorized)
    assert response_invalid.status_code == 401
```

---

## 4. UAT (User Acceptance Testing)

### 4.1 개요
UAT는 실제 사용자가 시스템을 검증하는 단계다.

**목표**:
- 핵심 사용자 시나리오 10개 100% 통과
- 사용성 검증 (UI/UX)
- 고객사 요구사항 충족 확인

### 4.2 UAT 시나리오

#### UAT-001: 불량 판단 요청 및 피드백

**사용자**: 제조 현장 관리자

**시나리오**:
1. Web Dashboard 로그인
2. 불량 판단 페이지 이동
3. 라인 코드, 날짜, 제품 코드 입력
4. "판단 실행" 버튼 클릭
5. 결과 확인 (상태, 조치사항, 근거)
6. 피드백 제공 (👍 또는 👎)

**수락 기준**:
- [ ] 평균 응답 시간 < 2초
- [ ] 결과가 명확하고 이해하기 쉬움
- [ ] 조치사항이 구체적이고 실행 가능함
- [ ] 피드백 버튼 클릭 시 즉시 반영

---

#### UAT-002: RCA Workflow 실행

**사용자**: 품질 관리자

**시나리오**:
1. 불량 이벤트 목록 조회
2. 특정 불량 이벤트 선택
3. "RCA 실행" 버튼 클릭
4. Workflow 실행 상태 확인 (진행률 표시)
5. RCA 보고서 확인 (추정 원인, 차트, 유사 케이스)
6. 조치 계획 수립 (Jira 이슈 생성)

**수락 기준**:
- [ ] RCA 실행 시간 < 60초
- [ ] 추정 원인 Top 3 표시
- [ ] 근거 차트가 명확함 (트렌드, 비교)
- [ ] 유사 과거 케이스 링크 제공

---

#### UAT-003: 자연어 BI 쿼리

**사용자**: 데이터 분석가

**시나리오**:
1. BI 분석 페이지 이동
2. 자연어 질의 입력: "지난 7일간 LINE-A 불량률 트렌드"
3. 엔터 키 또는 "실행" 버튼 클릭
4. 차트 확인 (Line Chart)
5. 대시보드에 추가
6. 동료와 공유

**수락 기준**:
- [ ] 평균 응답 시간 < 3초
- [ ] 차트가 정확함 (데이터 검증)
- [ ] 대시보드 추가 기능 동작
- [ ] 공유 링크 생성 및 접근 가능

---

#### UAT-004: Rule Canary 배포

**사용자**: AI 엔지니어

**시나리오**:
1. Learning Service → Rule 자동 추출
2. Rule 코드 검토 및 승인
3. "Canary 배포" 버튼 클릭
4. Canary 설정 (10%, 60분)
5. 실시간 메트릭 모니터링
6. 성공 기준 만족 확인
7. 100% 승격

**수락 기준**:
- [ ] Canary 배포 정상 동작 (10% 트래픽)
- [ ] 실시간 메트릭 정확 (에러율, 정확도)
- [ ] 자동 승격 동작 (성공 기준 만족 시)
- [ ] 수동 롤백 가능

---

### 4.3 UAT 체크리스트

#### 기능 검증
- [ ] Judgment 실행 (Rule, LLM, Hybrid)
- [ ] Workflow 생성 및 실행 (12 노드 타입)
- [ ] BI 자연어 쿼리 및 차트 생성
- [ ] Learning 피드백 및 Rule 추출
- [ ] Canary 배포 및 롤백
- [ ] Slack Bot 멘션 및 알림
- [ ] Admin Portal (사용자, 커넥터 관리)
- [ ] 대시보드 구성 및 공유
- [ ] Simulation (What-if)
- [ ] 헬스 체크 및 Drift 감지

#### 사용성 검증
- [ ] UI가 직관적이고 사용하기 쉬움
- [ ] 에러 메시지가 명확하고 해결 방법 제시
- [ ] 로딩 상태 표시 (스피너, 프로그레스바)
- [ ] 반응형 디자인 (모바일/태블릿/데스크톱)
- [ ] 접근성 (키보드 네비게이션, 스크린 리더)

#### 성능 검증
- [ ] Judgment 평균 < 1.5초
- [ ] BI 쿼리 평균 < 2초
- [ ] Workflow 실행 (Simple) < 10초
- [ ] 페이지 로딩 < 2초
- [ ] 차트 렌더링 < 1초

#### 보안 검증
- [ ] 로그인 필수 (미인증 시 401)
- [ ] 권한 체크 (Operator는 Workflow 생성 불가)
- [ ] TLS 연결 (HTTPS)
- [ ] PII 마스킹 동작
- [ ] Webhook 서명 검증

---

## 5. 결함 관리 및 릴리스 게이트

### 5.1 결함 관리 프로세스

#### 5.1.1 결함 심각도 분류

| 심각도 | 정의 | SLA | 예시 |
|--------|------|-----|------|
| **Critical** | 시스템 중단, 데이터 손실, 보안 취약점 | 24시간 내 임시 조치, 72시간 내 영구 해결 | Judgment Service 다운, DB 데이터 손실, SQL Injection |
| **High** | 주요 기능 동작 불가 | 3일 내 해결 | Workflow 실행 실패, BI 쿼리 에러 |
| **Medium** | 기능 제한적 동작, 우회 방법 존재 | 1주 내 해결 | 캐시 미동작, 차트 일부 깨짐 |
| **Low** | UI 오타, 사소한 불편 | 다음 릴리스 | 버튼 텍스트 오타, 툴팁 누락 |

#### 5.1.2 결함 라이프사이클

```
[New] → [Triaged] → [In Progress] → [Fixed] → [Verified] → [Closed]
           ↓
        [Won't Fix] (우선순위 낮음, 중복)
```

**Jira Workflow**:
1. **New**: QA가 버그 등록
2. **Triaged**: PM/SE가 심각도/우선순위 결정
3. **In Progress**: 개발자가 수정 시작
4. **Fixed**: 코드 수정 완료, PR 생성
5. **Verified**: QA가 수정 확인
6. **Closed**: 릴리스 완료

#### 5.1.3 결함 재현 스크립트

**필수 정보**:
- 재현 단계 (Step-by-step)
- 입력 데이터 (JSON, 스크린샷)
- 예상 결과 vs 실제 결과
- 로그 (trace_id, 에러 스택)
- 환경 (로컬/스테이징/프로덕션)

**예시** (Jira 티켓):
```
Title: Judgment 실행 시 LLM 파싱 에러

Severity: High
Priority: P1
Assignee: BE1

Description:
Judgment 실행 시 LLM 응답 파싱 실패로 500 에러 발생

Reproduction Steps:
1. POST /api/v1/judgment/execute
2. Body:
   {
     "workflow_id": "wf-001",
     "input_data": {"line_code": "LINE-A", "defect_count": 5, "production_count": 100},
     "policy": "LLM_ONLY"
   }
3. 응답: 500 Internal Server Error

Expected Result:
200 OK with judgment result

Actual Result:
500 Error: "Failed to parse LLM response: Expecting value: line 1 column 1 (char 0)"

Logs:
Trace ID: a1b2c3d4e5f6
Error Stack: [첨부]
LLM Response: [첨부]

Environment: Staging
```

### 5.2 릴리스 게이트 (Release Gate)

#### 5.2.1 MVP 릴리스 기준

**Functional Gates**:
- [ ] 모든 P0 요구사항 구현 완료 (35개)
- [ ] 주요 P1 요구사항 구현 완료 (15개 이상)
- [ ] 핵심 E2E 시나리오 10개 100% 통과

**Quality Gates**:
- [ ] 단위 테스트 커버리지 > 80%
- [ ] E2E 테스트 통과율 100%
- [ ] Critical/High 버그 0개
- [ ] Medium 버그 < 5개

**Performance Gates**:
- [ ] Judgment P95 < 2.5초
- [ ] BI P95 < 3초
- [ ] 부하 테스트 500 사용자 통과 (에러율 < 1%)

**Security Gates**:
- [ ] OWASP ZAP 스캔 Critical 취약점 0개
- [ ] PII 마스킹 100% 동작
- [ ] TLS 1.2+ 적용
- [ ] SQL Injection 방어 검증

**Operational Gates**:
- [ ] Monitoring 대시보드 동작 (Grafana)
- [ ] Backup 자동화 동작 (일 1회)
- [ ] 운영 매뉴얼 작성 (D-3)
- [ ] 사용자 가이드 작성 (D-4)

---

## 다음 파일로 계속

본 문서는 C-3-2로, E2E 테스트, 성능 테스트, 보안 테스트, UAT, 결함 관리를 포함한다.

---

## 문서 이력
| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2025-10-20 | QA Team | 초안 작성 |
| 2.0 | 2025-11-26 | QA Team | Enhanced 버전 (E2E, 성능, 보안 테스트 케이스 추가) |

---

**문서 끝**
