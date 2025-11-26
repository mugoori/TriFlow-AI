# A-2-4. System Requirements Specification - Data, Interface, Traceability

## 문서 정보
- **문서 ID**: A-2-4
- **버전**: 1.0
- **최종 수정일**: 2025-11-26
- **상태**: Draft
- **선행 문서**: A-2-1, A-2-2, A-2-3

## 목차
1. [데이터 요구사항 (Data Requirements)](#1-데이터-요구사항-data-requirements)
2. [인터페이스 요구사항 (Interface Requirements)](#2-인터페이스-요구사항-interface-requirements)
3. [요구사항 추적성 매트릭스 (Traceability Matrix)](#3-요구사항-추적성-매트릭스-traceability-matrix)
4. [우선순위 및 릴리스 계획 (Priority & Release Plan)](#4-우선순위-및-릴리스-계획-priority--release-plan)
5. [수락 기준 요약 (Acceptance Criteria Summary)](#5-수락-기준-요약-acceptance-criteria-summary)

---

## 1. 데이터 요구사항 (Data Requirements)

### 1.1 개요
시스템이 생성, 저장, 처리하는 데이터의 구조, 제약조건, 생명주기를 정의한다.

### 1.2 데이터 구조 요구사항

#### DATA-REQ-010: 테넌트 격리 (tenant_id)

**요구사항 설명**:
- 모든 데이터 테이블은 `tenant_id` 컬럼을 포함하여 멀티테넌트 격리를 지원해야 한다.

**상세 기준**:
- **필수 컬럼**: `tenant_id UUID NOT NULL`
- **인덱스**: `tenant_id`를 포함하는 복합 인덱스
- **제약조건**: Foreign Key → tenants(id)
- **RLS (Row-Level Security)**: 선택적 적용 (고보안 요구 시)

**테이블 예시**:
```sql
CREATE TABLE judgment_executions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  workflow_id UUID NOT NULL,
  -- ... 기타 컬럼 ...
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_judgment_executions_tenant_workflow
ON judgment_executions(tenant_id, workflow_id);
```

**수락 기준**:
- [ ] 모든 비즈니스 테이블에 tenant_id 포함
- [ ] tenant_id 복합 인덱스 생성
- [ ] Foreign Key 제약조건 적용
- [ ] 쿼리 성능 저하 없음 (인덱스 활용)

**우선순위**: P0 (Critical)
**관련 문서**: B-3-1 Core Schema

---

#### DATA-REQ-020: JSONB 메타데이터 저장

**요구사항 설명**:
- 확장 가능한 메타데이터는 JSONB 컬럼으로 저장하여 스키마 변경 없이 데이터를 추가할 수 있어야 한다.

**상세 기준**:
- **JSONB 사용 사례**:
  - workflow_instances.context
  - judgment_executions.metadata
  - llm_calls.response_metadata
  - users.preferences
- **인덱싱**: GIN 인덱스로 JSON 쿼리 최적화
- **스키마 검증**: JSON Schema로 구조 검증 (선택적)
- **마이그레이션**: JSON 스키마 변경은 애플리케이션 레벨에서 처리

**JSONB 인덱스 예시**:
```sql
CREATE TABLE llm_calls (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  response_metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- GIN 인덱스로 JSONB 쿼리 최적화
CREATE INDEX idx_llm_calls_response_metadata_gin
ON llm_calls USING GIN (response_metadata);

-- 특정 키 추출 인덱스
CREATE INDEX idx_llm_calls_model
ON llm_calls ((response_metadata->>'model'));
```

**JSONB 쿼리 예시**:
```sql
-- JSON 필드 조회
SELECT * FROM llm_calls
WHERE response_metadata->>'model' = 'gpt-4';

-- JSON 배열 포함 여부
SELECT * FROM llm_calls
WHERE response_metadata @> '{"features": ["chat"]}'::jsonb;
```

**수락 기준**:
- [ ] 확장 가능한 메타데이터 JSONB 사용
- [ ] GIN 인덱스로 쿼리 성능 최적화
- [ ] JSON Schema 검증 (선택적)
- [ ] JSONB 쿼리 평균 < 500ms

**우선순위**: P1 (High)
**관련 문서**: B-3-1, B-3-2, B-3-3

---

#### DATA-REQ-030: 시계열 데이터 파티셔닝

**요구사항 설명**:
- 시계열 데이터는 날짜 기반 파티셔닝을 적용하여 쿼리 성능을 최적화하고 관리를 용이하게 해야 한다.

**상세 기준**:
- **파티셔닝 전략**:
  - `judgment_executions`: 월별 파티션
  - `workflow_instances`: 월별 파티션
  - `fact_daily_production`: 분기별 파티션
  - `llm_calls`: 월별 파티션
- **자동 파티션 생성**: 미래 3개월 파티션 사전 생성
- **파티션 삭제**: 보존 기간 초과 파티션 자동 삭제
- **파티션 프루닝**: 쿼리 시 불필요한 파티션 제외

**파티션 테이블 예시**:
```sql
CREATE TABLE judgment_executions (
  id UUID NOT NULL,
  tenant_id UUID NOT NULL,
  executed_at TIMESTAMPTZ NOT NULL,
  -- ... 기타 컬럼 ...
  PRIMARY KEY (id, executed_at)
) PARTITION BY RANGE (executed_at);

-- 월별 파티션 생성
CREATE TABLE judgment_executions_y2025m11
PARTITION OF judgment_executions
FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');

CREATE TABLE judgment_executions_y2025m12
PARTITION OF judgment_executions
FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');
```

**자동 파티션 생성 함수** (B-3-4 참조):
```sql
SELECT create_monthly_partition(
  'judgment_executions',
  'executed_at',
  '2026-01-01'::date
);
```

**수락 기준**:
- [ ] 시계열 테이블 파티셔닝 적용
- [ ] 자동 파티션 생성 함수 동작
- [ ] 파티션 프루닝으로 쿼리 성능 향상
- [ ] 보존 기간 초과 파티션 자동 삭제

**우선순위**: P1 (High)
**관련 문서**: B-3-4 Performance & Operations

---

### 1.3 데이터 마이그레이션 요구사항

#### DATA-REQ-040: 스키마 마이그레이션 관리

**요구사항 설명**:
- 데이터베이스 스키마 변경은 버전 관리 도구(Alembic/Flyway)로 관리되어야 한다.

**상세 기준**:
- **마이그레이션 도구**: Alembic (Python) 또는 Flyway (Java)
- **버전 명명**: `V{YYYYMMDD}_{HHMM}__{description}.sql`
- **Up/Down 스크립트**: 모든 마이그레이션에 Rollback 스크립트 포함
- **테스트**: Staging 환경 먼저 적용 후 Production 배포
- **백업**: 마이그레이션 전 DB 백업 필수

**Alembic 마이그레이션 예시**:
```python
# alembic/versions/20251126_1600__add_judgment_confidence.py
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('judgment_executions',
        sa.Column('confidence', sa.Float, nullable=True)
    )
    # 기존 데이터 기본값 설정
    op.execute("UPDATE judgment_executions SET confidence = 0.5 WHERE confidence IS NULL")
    op.alter_column('judgment_executions', 'confidence', nullable=False)

def downgrade():
    op.drop_column('judgment_executions', 'confidence')
```

**마이그레이션 실행**:
```bash
# Upgrade to latest
alembic upgrade head

# Rollback one version
alembic downgrade -1

# Show current version
alembic current
```

**수락 기준**:
- [ ] Alembic/Flyway로 마이그레이션 관리
- [ ] 모든 마이그레이션에 Rollback 스크립트
- [ ] Staging 먼저 테스트 후 Production 배포
- [ ] 마이그레이션 전 자동 백업

**우선순위**: P0 (Critical)
**관련 문서**: B-3-4, D-3 Operation Runbook

---

#### DATA-REQ-050: 데이터 시딩 (초기 데이터)

**요구사항 설명**:
- 시스템 초기 구동에 필요한 기본 데이터(Seed Data)를 자동으로 생성해야 한다.

**상세 기준**:
- **시딩 대상**:
  - 기본 Tenant (데모용)
  - Admin 사용자 (초기 관리자)
  - Intent 정의 (기본 5개)
  - BI Dataset/Metric (기본 3개)
- **시딩 방법**: 마이그레이션 스크립트 또는 별도 시딩 스크립트
- **멱등성**: 여러 번 실행해도 중복 생성 안 됨

**시딩 스크립트 예시**:
```sql
-- seed_data.sql
INSERT INTO tenants (id, name, status)
VALUES ('00000000-0000-0000-0000-000000000001', 'Demo Tenant', 'active')
ON CONFLICT (id) DO NOTHING;

INSERT INTO users (id, tenant_id, email, role, password_hash)
VALUES (
  '00000000-0000-0000-0000-000000000002',
  '00000000-0000-0000-0000-000000000001',
  'admin@factory-ai.com',
  'admin',
  '$2b$12$...' -- bcrypt hash
) ON CONFLICT (email) DO NOTHING;

INSERT INTO intents (id, tenant_id, name, description)
VALUES
  (gen_random_uuid(), '00000000-0000-0000-0000-000000000001', 'production_inquiry', '생산량 조회'),
  (gen_random_uuid(), '00000000-0000-0000-0000-000000000001', 'defect_inquiry', '불량 조회')
ON CONFLICT (tenant_id, name) DO NOTHING;
```

**수락 기준**:
- [ ] 초기 데이터 시딩 스크립트 작성
- [ ] 멱등성 보장 (중복 실행 안전)
- [ ] 기본 Tenant, Admin 사용자 생성
- [ ] 기본 Intent, BI Catalog 생성

**우선순위**: P1 (High)
**관련 문서**: B-3-1, D-3

---

## 2. 인터페이스 요구사항 (Interface Requirements)

### 2.1 개요
시스템과 외부 시스템, 사용자, 다른 모듈 간의 인터페이스를 정의한다.

### 2.2 외부 시스템 인터페이스

#### INT-REQ-010: ERP/MES 연동

**요구사항 설명**:
- ERP/MES 시스템과 연동하여 생산 계획, 자재 정보, 생산 실적 데이터를 조회해야 한다.

**상세 기준**:
- **연동 방식**:
  - REST API (JSON)
  - SOAP API (XML)
  - DB 직접 연결 (Read-only)
- **지원 ERP**: SAP, Oracle ERP, 기타 REST API 제공 ERP
- **지원 MES**: Siemens MES, Rockwell MES, 기타 REST API 제공 MES
- **인증**: OAuth 2.0, API Key, DB 계정
- **데이터 동기화**: 실시간 또는 배치 (15분 간격)

**ERP API 호출 예시**:
```http
GET https://erp.company.com/api/v1/production/orders?date=2025-11-26
Authorization: Bearer {{ token }}

Response:
{
  "orders": [
    {
      "order_id": "ORD-12345",
      "product_code": "PROD-123",
      "quantity": 1000,
      "due_date": "2025-11-30"
    }
  ]
}
```

**MES DB 직접 연결 예시**:
```python
import psycopg2

conn = psycopg2.connect(
    host="mes-db.company.com",
    port=5432,
    database="mes_prod",
    user="readonly_user",
    password="***"
)

cur = conn.cursor()
cur.execute("""
    SELECT line_code, production_count, defect_count, timestamp
    FROM production_log
    WHERE DATE(timestamp) = %s
""", ('2025-11-26',))

rows = cur.fetchall()
```

**수락 기준**:
- [ ] ERP API 연동 성공 (SAP, Oracle)
- [ ] MES API 또는 DB 연동 성공
- [ ] 데이터 동기화 정상 동작
- [ ] 연동 에러 시 재시도 및 알람

**우선순위**: P0 (Critical)
**관련 문서**: B-2, INT-FR-030

---

#### INT-REQ-020: 센서/IoT 데이터 수집

**요구사항 설명**:
- MQTT 또는 OPC UA 프로토콜로 센서 데이터를 실시간 수집해야 한다.

**상세 기준**:
- **지원 프로토콜**: MQTT, OPC UA
- **데이터 타입**: 온도, 습도, 압력, 진동, 전류, 전압 등
- **수집 주기**: 1초~1분 (센서별 설정)
- **버퍼링**: 네트워크 장애 시 로컬 버퍼에 저장 후 재전송
- **데이터 저장**: 시계열 DB (InfluxDB, TimescaleDB) 또는 PostgreSQL

**MQTT 구독 예시**:
```python
import paho.mqtt.client as mqtt

def on_message(client, userdata, message):
    topic = message.topic  # 'sensor/LINE-A/temperature'
    payload = message.payload.decode()  # '{"value": 25.3, "unit": "celsius", "timestamp": "..."}'

    data = json.loads(payload)
    save_sensor_data(topic, data)

client = mqtt.Client()
client.on_message = on_message
client.connect("mqtt.company.com", 1883)
client.subscribe("sensor/#")
client.loop_forever()
```

**OPC UA 읽기 예시**:
```python
from opcua import Client

client = Client("opc.tcp://plc.company.com:4840")
client.connect()

# 노드 읽기
node = client.get_node("ns=2;s=LINE-A.Temperature")
value = node.get_value()

print(f"Temperature: {value} °C")
```

**수락 기준**:
- [ ] MQTT 브로커 연결 및 구독
- [ ] OPC UA 서버 연결 및 노드 읽기
- [ ] 실시간 데이터 수집 (지연 < 5초)
- [ ] 네트워크 장애 시 버퍼링 및 재전송

**우선순위**: P1 (High)
**관련 문서**: INT-FR-030

---

#### INT-REQ-030: LLM API 연동

**요구사항 설명**:
- OpenAI, Anthropic 등 LLM 제공자 API와 연동하여 자연어 처리 기능을 제공해야 한다.

**상세 기준**:
- **지원 LLM**:
  - OpenAI: GPT-4, GPT-4o, GPT-4o-mini
  - Anthropic: Claude-3-Opus, Claude-3-Sonnet, Claude-3-Haiku
  - 기타: Azure OpenAI, AWS Bedrock
- **인증**: API Key (환경변수 또는 Vault)
- **타임아웃**: 기본 30초, 모델별 조정 가능
- **재시도**: 네트워크 에러, 5xx 에러 시 최대 3회
- **비용 추적**: 토큰 수 및 비용 로깅

**OpenAI API 호출 예시**:
```python
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "You are a manufacturing expert."},
        {"role": "user", "content": "What is the defect rate?"}
    ],
    temperature=0.7,
    max_tokens=500,
    response_format={"type": "json_object"}
)

result = response.choices[0].message.content
tokens = response.usage.total_tokens
```

**Anthropic API 호출 예시**:
```python
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

response = client.messages.create(
    model="claude-3-sonnet-20240229",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Analyze the defect data..."}
    ]
)

result = response.content[0].text
tokens = response.usage.input_tokens + response.usage.output_tokens
```

**수락 기준**:
- [ ] OpenAI API 연동 (GPT-4, GPT-4o)
- [ ] Anthropic API 연동 (Claude-3)
- [ ] API 호출 성공률 > 98%
- [ ] 토큰 수 및 비용 로깅

**우선순위**: P0 (Critical)
**관련 문서**: B-6, JUD-FR-030, CHAT-FR-040

---

### 2.3 사용자 인터페이스 요구사항

#### UI-REQ-010: 웹 대시보드

**요구사항 설명**:
- React 기반 SPA 웹 대시보드를 제공하여 Judgment, Workflow, BI 기능을 사용할 수 있어야 한다.

**상세 기준**:
- **기술 스택**: React 18+, TypeScript, Tailwind CSS
- **상태 관리**: Redux Toolkit 또는 Zustand
- **라우팅**: React Router v6
- **차트 라이브러리**: Chart.js 또는 ECharts
- **반응형**: 모바일/태블릿/데스크톱 대응
- **브라우저 지원**: Chrome 최신, Edge 최신, Firefox 최신

**주요 화면**:
- **대시보드**: 실시간 생산 지표, 불량률, OEE
- **Judgment**: 판단 실행, 결과 조회, 피드백
- **Workflow**: 워크플로우 생성/수정, 실행 이력
- **BI 분석**: 자연어 쿼리, 차트 생성, 대시보드 구성
- **설정**: 사용자 관리, 커넥터 설정, Rule 배포

**UI 컴포넌트 예시**:
```tsx
// Judgment Result Card
interface JudgmentResultProps {
  judgment: Judgment;
  onFeedback: (feedback: Feedback) => void;
}

const JudgmentResultCard: React.FC<JudgmentResultProps> = ({ judgment, onFeedback }) => {
  return (
    <Card>
      <CardHeader>
        <Badge color={getSeverityColor(judgment.result.severity)}>
          {judgment.result.status}
        </Badge>
        <Text>Confidence: {judgment.confidence.toFixed(2)}</Text>
      </CardHeader>
      <CardBody>
        <Text>{judgment.explanation}</Text>
        <List>
          {judgment.result.recommended_actions.map(action => (
            <ListItem key={action}>{action}</ListItem>
          ))}
        </List>
      </CardBody>
      <CardFooter>
        <Button onClick={() => onFeedback({ type: 'thumbs_up' })}>👍</Button>
        <Button onClick={() => onFeedback({ type: 'thumbs_down' })}>👎</Button>
      </CardFooter>
    </Card>
  );
};
```

**수락 기준**:
- [ ] React SPA 구현
- [ ] 주요 화면 5개 구현
- [ ] 반응형 디자인 동작 확인
- [ ] Chrome, Edge, Firefox 호환

**우선순위**: P0 (Critical)
**관련 문서**: A-3, B-4

---

#### UI-REQ-020: Slack Bot

**요구사항 설명**:
- Slack Bot을 통해 자연어 명령을 수신하고, 판단 결과 및 알림을 Slack 채널로 발송해야 한다.

**상세 기준**:
- **Slack 기능**:
  - 멘션 수신: `@AI-Factory 어제 LINE-A 생산량 알려줘`
  - 슬래시 커맨드: `/ai-factory production LINE-A yesterday`
  - Interactive 버튼: 피드백, 승인
- **응답 형식**: Slack Block Kit (카드, 버튼, 차트)
- **알림 발송**: 판단 결과, 알람, 승인 요청

**Slack Bot 응답 예시**:
```json
{
  "blocks": [
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*🚨 High Defect Detected*\n\nLine: LINE-A\nDefect Rate: 5.0%\nConfidence: 0.92"
      }
    },
    {
      "type": "section",
      "fields": [
        {
          "type": "mrkdwn",
          "text": "*Recommended Actions:*\n- Stop LINE-A\n- Inspect equipment"
        }
      ]
    },
    {
      "type": "actions",
      "elements": [
        {
          "type": "button",
          "text": {
            "type": "plain_text",
            "text": "👍 Helpful"
          },
          "value": "thumbs_up",
          "action_id": "feedback_up"
        },
        {
          "type": "button",
          "text": {
            "type": "plain_text",
            "text": "👎 Not Helpful"
          },
          "value": "thumbs_down",
          "action_id": "feedback_down"
        }
      ]
    }
  ]
}
```

**수락 기준**:
- [ ] Slack 멘션 수신 및 응답
- [ ] Slack Block Kit 응답 형식
- [ ] Interactive 버튼 동작 확인
- [ ] 알림 발송 성공률 > 98%

**우선순위**: P1 (High)
**관련 문서**: CHAT-FR-*, WF-FR-040

---

## 3. 요구사항 추적성 매트릭스 (Traceability Matrix)

### 3.1 개요
요구사항과 설계, 구현, 테스트 간의 매핑을 제공하여 추적 가능성을 보장한다.

### 3.2 기능 요구사항 추적성

#### Judgment Engine 추적성

| 요구사항 ID | 요구사항 명 | 설계 문서 | DB 스키마 | API | 테스트 케이스 | 우선순위 |
|------------|------------|----------|----------|-----|--------------|---------|
| JUD-FR-010 | Input Validation | B-2 Judgment Engine | workflows, workflow_steps | POST /judgment/execute | C-3-TC-JUD-010-* | P0 |
| JUD-FR-020 | Rule Execution | B-2, B-5 | rulesets, rule_scripts | - (Internal) | C-3-TC-JUD-020-* | P0 |
| JUD-FR-030 | LLM Fallback | B-2, B-6 | prompt_templates, llm_calls | - (Internal) | C-3-TC-JUD-030-* | P0 |
| JUD-FR-040 | Hybrid Aggregation | B-2 | judgment_executions | - (Internal) | C-3-TC-JUD-040-* | P1 |
| JUD-FR-050 | Explanation | B-2, B-6 | judgment_executions | - (Internal) | C-3-TC-JUD-050-* | P1 |
| JUD-FR-060 | Caching | B-2 | Redis | - (Internal) | C-3-TC-JUD-060-* | P1 |
| JUD-FR-070 | Simulation | B-2 | judgment_executions | POST /judgment/simulate | C-3-TC-JUD-070-* | P2 |

#### Workflow Engine 추적성

| 요구사항 ID | 요구사항 명 | 설계 문서 | DB 스키마 | API | 테스트 케이스 | 우선순위 |
|------------|------------|----------|----------|-----|--------------|---------|
| WF-FR-010 | DSL Parsing | B-2, B-5 | workflows, workflow_steps | POST /workflow/validate | C-3-TC-WF-010-* | P0 |
| WF-FR-020 | Node - Data | B-2, B-5 | fact_*, dim_* | - (Internal) | C-3-TC-WF-020-* | P0 |
| WF-FR-030 | Node - Judgment | B-2, B-5 | judgment_executions | - (Internal) | C-3-TC-WF-030-* | P0 |
| WF-FR-040 | Node - Action | B-2, B-5 | - | - (External: Slack/Email) | C-3-TC-WF-040-* | P1 |
| WF-FR-050 | Flow Control | B-2, B-5 | workflow_instances | - (Internal) | C-3-TC-WF-050-* | P1 |
| WF-FR-060 | State Persistence | B-2, B-5 | workflow_instances | GET /workflow/instance/{id} | C-3-TC-WF-060-* | P0 |
| WF-FR-070 | Circuit Breaker | B-2 | Redis | - (Internal) | C-3-TC-WF-070-* | P1 |

#### BI Engine 추적성

| 요구사항 ID | 요구사항 명 | 설계 문서 | DB 스키마 | API | 테스트 케이스 | 우선순위 |
|------------|------------|----------|----------|-----|--------------|---------|
| BI-FR-010 | NL Understanding | B-2, B-6 | bi_datasets, bi_metrics | POST /bi/plan | C-3-TC-BI-010-* | P0 |
| BI-FR-020 | Plan Execution | B-2 | fact_*, mv_* | POST /bi/execute | C-3-TC-BI-020-* | P0 |
| BI-FR-030 | Catalog Mgmt | B-2 | bi_datasets, bi_metrics, bi_components | GET/POST /bi/catalog | C-3-TC-BI-030-* | P1 |
| BI-FR-040 | Chart Rendering | B-2 | - | - (Internal) | C-3-TC-BI-040-* | P1 |
| BI-FR-050 | Caching | B-2 | Redis | - (Internal) | C-3-TC-BI-050-* | P1 |

#### Integration/MCP 추적성

| 요구사항 ID | 요구사항 명 | 설계 문서 | DB 스키마 | API | 테스트 케이스 | 우선순위 |
|------------|------------|----------|----------|-----|--------------|---------|
| INT-FR-010 | MCP Registry | B-2 | mcp_servers, mcp_tools | GET/POST /mcp/registry | C-3-TC-INT-010-* | P0 |
| INT-FR-020 | Tool Execution | B-2 | mcp_tool_executions | POST /mcp/tools/call | C-3-TC-INT-020-* | P0 |
| INT-FR-030 | Connector Mgmt | B-2 | data_connectors | GET/POST /connectors | C-3-TC-INT-030-* | P1 |
| INT-FR-040 | Drift Detection | B-2 | schema_snapshots | GET /connectors/drift | C-3-TC-INT-040-* | P2 |

#### Learning/Rule Ops 추적성

| 요구사항 ID | 요구사항 명 | 설계 문서 | DB 스키마 | API | 테스트 케이스 | 우선순위 |
|------------|------------|----------|----------|-----|--------------|---------|
| LRN-FR-010 | Feedback | B-2 | feedbacks | POST /feedback | C-3-TC-LRN-010-* | P1 |
| LRN-FR-020 | Sample Curation | B-2 | learning_samples | GET /learning/samples | C-3-TC-LRN-020-* | P1 |
| LRN-FR-030 | Rule Extraction | B-2 | auto_rule_candidates | POST /learning/extract-rules | C-3-TC-LRN-030-* | P2 |
| LRN-FR-040 | Prompt Tuning | B-2, B-6 | prompt_versions | POST /learning/tune-prompts | C-3-TC-LRN-040-* | P2 |
| LRN-FR-050 | Deployment | B-2 | rule_deployments | POST /learning/deploy | C-3-TC-LRN-050-* | P1 |

#### Chat/Intent 추적성

| 요구사항 ID | 요구사항 명 | 설계 문서 | DB 스키마 | API | 테스트 케이스 | 우선순위 |
|------------|------------|----------|----------|-----|--------------|---------|
| CHAT-FR-010 | Intent Recog | B-2, B-6 | intents, intent_logs | POST /chat/intent | C-3-TC-CHAT-010-* | P0 |
| CHAT-FR-020 | Slot Filling | B-2, B-6 | - | - (Internal) | C-3-TC-CHAT-020-* | P0 |
| CHAT-FR-030 | Ambiguity | B-2, B-6 | chat_sessions | - (Internal) | C-3-TC-CHAT-030-* | P1 |
| CHAT-FR-040 | Model Routing | B-2, B-6 | llm_calls | - (Internal) | C-3-TC-CHAT-040-* | P2 |

### 3.3 비기능 요구사항 추적성

#### 성능 요구사항 추적성

| 요구사항 ID | 요구사항 명 | 목표 | 모니터링 | 테스트 | 우선순위 |
|------------|------------|------|---------|--------|---------|
| NFR-PERF-010 | Judgment 응답 시간 | P50 < 1.5s | Prometheus | C-3-TC-NFR-PERF-010-* | P0 |
| NFR-PERF-020 | BI 플래너 응답 시간 | P50 < 2s | Prometheus | C-3-TC-NFR-PERF-020-* | P0 |
| NFR-PERF-030 | Workflow 실행 시간 | Simple P95 < 10s | Prometheus | C-3-TC-NFR-PERF-030-* | P1 |
| NFR-PERF-040 | MCP 호출 시간 | 기본 5초 타임아웃 | Prometheus | C-3-TC-NFR-PERF-040-* | P1 |
| NFR-PERF-050 | 동시 요청 처리량 | 50 TPS (Judgment) | Prometheus | C-3-TC-NFR-PERF-050-* | P1 |
| NFR-PERF-060 | 리소스 사용률 | CPU < 80% | Prometheus | C-3-TC-NFR-PERF-060-* | P1 |
| NFR-PERF-070 | LLM 파싱 실패율 | < 0.5% | Prometheus | C-3-TC-NFR-PERF-070-* | P1 |

#### 보안 요구사항 추적성

| 요구사항 ID | 요구사항 명 | 구현 | 검증 | 테스트 | 우선순위 |
|------------|------------|------|------|--------|---------|
| NFR-SEC-010 | 전송 암호화 (TLS) | Nginx TLS 1.2+ | SSL Labs | C-3-TC-NFR-SEC-010-* | P0 |
| NFR-SEC-020 | 저장 암호화 | AES-256 | 코드 리뷰 | C-3-TC-NFR-SEC-020-* | P0 |
| NFR-SEC-030 | Webhook 서명 | HMAC SHA-256 | 통합 테스트 | C-3-TC-NFR-SEC-030-* | P1 |
| NFR-SEC-040 | SQL Injection 방어 | Prepared Statement | OWASP ZAP | C-3-TC-NFR-SEC-040-* | P0 |
| NFR-SEC-050 | XSS/CSRF 방어 | CSP, CSRF Token | OWASP ZAP | C-3-TC-NFR-SEC-050-* | P1 |
| SEC-FR-010 | AuthN/AuthZ | JWT + RBAC | 통합 테스트 | C-3-TC-SEC-010-* | P0 |
| SEC-FR-020 | PII Masking | 정규표현식 | 단위 테스트 | C-3-TC-SEC-020-* | P1 |
| SEC-FR-030 | Audit Log | audit_logs 테이블 | 통합 테스트 | C-3-TC-SEC-030-* | P1 |

#### 가용성 요구사항 추적성

| 요구사항 ID | 요구사항 명 | 목표 | 구현 | 테스트 | 우선순위 |
|------------|------------|------|------|--------|---------|
| NFR-HA-010 | 핵심 서비스 이중화 | 99.9% 가용성 | Kubernetes ≥2 replicas | C-3-TC-NFR-HA-010-* | P0 |
| NFR-HA-020 | DB 복제 | Failover < 5분 | Streaming Replication | C-3-TC-NFR-HA-020-* | P1 |
| NFR-HA-030 | Redis 복제 | 데이터 손실 < 1초 | Redis Sentinel + AOF | C-3-TC-NFR-HA-030-* | P1 |
| NFR-DR-010 | 백업 전략 | 일 1회 Full Backup | Cron + S3 | C-3-TC-NFR-DR-010-* | P0 |
| NFR-DR-020 | RTO/RPO | RTO 4시간, RPO 30분 | DR 절차서 | C-3-TC-NFR-DR-020-* | P1 |

---

## 4. 우선순위 및 릴리스 계획 (Priority & Release Plan)

### 4.1 개요
요구사항 우선순위에 따라 릴리스 단계를 계획한다.

### 4.2 우선순위 정의

| 우선순위 | 정의 | 비율 |
|---------|------|------|
| **P0 (Critical)** | 시스템 핵심 기능, 없으면 시스템 동작 불가 | 35% |
| **P1 (High)** | 주요 기능, 사용자 경험에 큰 영향 | 40% |
| **P2 (Medium)** | 중요하지만 우선순위 낮음, 향후 릴리스 | 20% |
| **P3 (Low)** | Nice-to-have, 선택적 기능 | 5% |

### 4.3 릴리스 계획

#### Release 1.0 (MVP - 3개월)

**목표**: 핵심 Judgment, Workflow 기능 제공

**포함 요구사항**:
- **P0 요구사항 전체** (35%)
  - Judgment Engine: JUD-FR-010~030
  - Workflow Engine: WF-FR-010~030, WF-FR-060
  - BI Engine: BI-FR-010~020
  - Integration: INT-FR-010~020
  - Chat: CHAT-FR-010~020
  - Security: SEC-FR-010, NFR-SEC-010~040
  - Performance: NFR-PERF-010~020
  - Availability: NFR-HA-010, NFR-DR-010
  - Data: DATA-REQ-010~040
  - Interface: INT-REQ-010, INT-REQ-030, UI-REQ-010

**예상 일정**:
- Week 1-4: 인프라 구축, DB 스키마 설계
- Week 5-8: Judgment/Workflow 엔진 개발
- Week 9-10: BI 엔진 개발
- Week 11: 통합 테스트
- Week 12: UAT 및 배포

---

#### Release 1.1 (확장 - 2개월)

**목표**: 학습, 배포, 고급 기능 추가

**포함 요구사항**:
- **P1 요구사항 선택** (20%)
  - Judgment: JUD-FR-040~060
  - Workflow: WF-FR-040~050, WF-FR-070
  - BI: BI-FR-030~050
  - Integration: INT-FR-030
  - Learning: LRN-FR-010~020, LRN-FR-050
  - Chat: CHAT-FR-030
  - Performance: NFR-PERF-030~060
  - Availability: NFR-HA-020~030, NFR-DR-020
  - Interface: INT-REQ-020, UI-REQ-020

**예상 일정**:
- Week 13-16: 학습 파이프라인, Rule 배포 기능
- Week 17-18: 센서 연동, Slack Bot
- Week 19-20: 성능 최적화, 부하 테스트

---

#### Release 1.2 (고도화 - 2개월)

**목표**: AI 고도화, 자동화, 품질 개선

**포함 요구사항**:
- **P1 나머지 + P2 선택** (15%)
  - Judgment: JUD-FR-070
  - Learning: LRN-FR-030~040
  - Chat: CHAT-FR-040
  - Integration: INT-FR-040
  - Quality: NFR-QUAL-010~030
  - Performance: NFR-PERF-070
  - Audit: NFR-AUDIT-010~030
  - I18N: NFR-I18N-010~020

**예상 일정**:
- Week 21-24: Rule 자동 추출, Prompt 튜닝
- Week 25-26: Drift 감지, ETL 연동
- Week 27-28: 품질 모니터링, 알람 시스템

---

### 4.4 릴리스 주요 메트릭

| 릴리스 | 기능 수 | P0/P1/P2 | 개발 기간 | 목표 사용자 | 주요 지표 |
|-------|---------|----------|-----------|------------|----------|
| **1.0 (MVP)** | 45개 | 35/10/0 | 3개월 | 10명 (파일럿) | Judgment 정확도 > 80% |
| **1.1 (확장)** | 65개 | 35/25/5 | 2개월 | 50명 | 학습 샘플 > 500개 |
| **1.2 (고도화)** | 80개 | 35/35/10 | 2개월 | 100명 | 자동 Rule 정확도 > 85% |

---

## 5. 수락 기준 요약 (Acceptance Criteria Summary)

### 5.1 개요
주요 요구사항의 수락 기준을 요약한다.

### 5.2 기능별 수락 기준

#### Judgment Engine

| 기능 | 수락 기준 |
|------|----------|
| **Input Validation** | 필수 필드 누락 시 400 에러, 검증 실패율 < 0.1%, 검증 시간 < 50ms |
| **Rule Execution** | Rule 실행 성공률 > 99.9%, 평균 < 100ms, 타임아웃 < 500ms |
| **LLM Fallback** | LLM 호출 성공률 > 98%, JSON 파싱 > 99.5%, 평균 < 5초 |
| **Hybrid Aggregation** | 가중치 설정 가능, 병합 로직 커버리지 > 90%, method_used 필드 명시 |
| **Explanation** | need_explanation=false 시 생략, 생성 시간 < 200ms, 다국어 지원 |
| **Caching** | 캐시 적중 시 < 300ms, 적중률 > 40%, from_cache 필드 명시 |
| **Simulation** | 과거 execution_id 재실행 가능, 버전 지정 가능, diff 제공 |

#### Workflow Engine

| 기능 | 수락 기준 |
|------|----------|
| **DSL Parsing** | JSON Schema 검증, 순환/고아 노드 탐지, 시작 노드 1개 확인 |
| **Node - Data** | SQL 생성 정확도 100%, SQL Injection 없음, 평균 < 500ms |
| **Node - Judgment** | Judgment API 호출 성공률 > 99%, 평균 < 2초, 재시도 동작 |
| **Node - Action** | Slack/Email 전송 성공률 > 98%, 템플릿 치환 100%, 멱등성 보장 |
| **Flow Control** | SWITCH 평가 100%, PARALLEL 조인 동작, WAIT 정확도 ±100ms |
| **State Persistence** | 모든 상태 전이 저장, 복구 후 중복 없음, context < 1MB |
| **Circuit Breaker** | 실패율 추적 100%, 임계 초과 시 차단, Fallback 성공률 > 99% |

#### BI Engine

| 기능 | 수락 기준 |
|------|----------|
| **NL Understanding** | 파싱 성공률 > 90%, analysis_plan 스키마 100%, 평균 < 3초 |
| **Plan Execution** | SQL 생성 > 95%, Pre-agg 적용 > 50%, 평균 < 2초 |
| **Catalog Mgmt** | CRUD API 동작, 스키마 검증, 중복 검사, RBAC 적용 |
| **Chart Rendering** | 6가지 차트 타입, JSON 스키마 100%, 반응형 동작 |
| **Caching** | 캐시 적중 < 500ms, 적중률 > 30%, 자동 무효화 |

#### Performance

| 메트릭 | 목표 | 수락 기준 |
|--------|------|----------|
| **Judgment 응답** | P50 < 1.5s (Hybrid) | P95 < 3s, P99 < 5s, 캐시 P95 < 300ms |
| **BI 플래너** | P50 < 2s (E2E) | P95 < 3s, Pre-agg < 500ms, 캐시 > 30% |
| **Workflow** | Simple P95 < 10s | Complex P95 < 120s, 노드별 목표 달성 |
| **처리량** | 50 TPS (Judgment) | 500 동시 사용자, 부하 테스트 에러율 < 1% |
| **LLM 파싱** | 실패율 < 0.5% | 재시도 동작, 자동 보정, 실패 로그 |

#### Security

| 기능 | 수락 기준 |
|------|----------|
| **TLS** | TLS 1.2+, 안전한 암호화 스위트, SSL Labs A+ |
| **저장 암호화** | AES-256, 키 안전 저장, 키 로테이션 절차 |
| **Webhook 서명** | HMAC SHA-256, 멱등성 키, 타임스탬프 검증 |
| **SQL Injection** | Prepared Statement, 보안 스캔 통과 |
| **XSS/CSRF** | CSP 헤더, CSRF 토큰, 보안 스캔 통과 |
| **AuthN/AuthZ** | OAuth 2.0/JWT, RBAC, 권한 부족 시 403 |
| **PII Masking** | 5가지 패턴 탐지 > 95%, 자동 마스킹 |
| **Audit Log** | 로그 불변성, old/new 값 명시, 2년 보존 |

---

## 결론

본 문서(A-2)는 **제조업 AI 플랫폼 (AI Factory Decision Engine)** 의 시스템 요구사항을 포괄적으로 명세하였다.

### 문서 구성 요약

- **A-2-1**: 개요, 컨텍스트, 코어 엔진 요구사항 (Judgment, Workflow, BI)
- **A-2-2**: 통합/학습/챗봇 요구사항 (Integration, Learning, Chat, Security, Observability)
- **A-2-3**: 비기능 요구사항 (성능, 확장성, 가용성, 보안, 감사, 국제화, 품질)
- **A-2-4**: 데이터/인터페이스 요구사항 및 추적성 매트릭스

### 주요 성과

1. **80개 이상의 상세 요구사항** 정의 (기능/비기능)
2. **추적성 매트릭스** 제공 (요구사항 ↔ 설계 ↔ 구현 ↔ 테스트)
3. **수락 기준** 명시 (정량적 목표 및 검증 방법)
4. **릴리스 계획** 수립 (MVP 3개월, 확장 2개월, 고도화 2개월)
5. **우선순위 기반** 개발 로드맵 (P0 35%, P1 40%, P2 20%, P3 5%)

### 다음 단계

1. **요구사항 리뷰**: 고객사, 제품 책임자, 개발팀과 함께 요구사항 검토
2. **설계 상세화**: B-1 (아키텍처), B-2 (모듈 설계) 문서 작성
3. **테스트 계획**: C-3 (테스트 계획) 문서 작성 및 테스트 케이스 정의
4. **개발 착수**: 릴리스 1.0 (MVP) 개발 시작

---

## 문서 이력

| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2025-11-26 | AI Factory Team | 초안 작성 (A-2-1~A-2-4 통합) |

---

**문서 끝**
