# B-1-3. System Architecture Specification - Integration, Security, Scalability Architecture

## 문서 정보
- **문서 ID**: B-1-3
- **버전**: 1.0
- **최종 수정일**: 2025-11-26
- **상태**: Draft
- **선행 문서**: B-1-1, B-1-2

## 목차
1. [통합 아키텍처](#1-통합-아키텍처)
2. [보안 아키텍처](#2-보안-아키텍처)
3. [확장성 아키텍처](#3-확장성-아키텍처)
4. [가용성 및 재해 복구 아키텍처](#4-가용성-및-재해-복구-아키텍처)

---

## 1. 통합 아키텍처

### 1.1 개요
통합 아키텍처는 외부 시스템(ERP, MES, IoT, LLM, MCP 서버)과의 연동 방식을 정의한다.

### 1.2 통합 패턴

#### 1.2.1 MCP Protocol Integration (표준 프로토콜)

**MCP (Model Context Protocol)** 기반 도구 연동:

```
┌─────────────────────────────────────────────────────────────┐
│                      MCP ToolHub                            │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │   MCP      │  │   MCP      │  │   MCP      │           │
│  │ Registry   │  │   Proxy    │  │  Circuit   │           │
│  │            │  │            │  │  Breaker   │           │
│  └────────────┘  └────────────┘  └────────────┘           │
└─────────────────────────────────────────────────────────────┘
         │                  │                  │
         ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ MCP Server   │  │ MCP Server   │  │ MCP Server   │
│  (Excel)     │  │ (GDrive)     │  │  (Jira)      │
└──────────────┘  └──────────────┘  └──────────────┘
```

**MCP 호출 흐름**:
```
1. Workflow 노드 (MCP 타입) → MCP ToolHub API 호출
2. ToolHub: 도구 메타데이터 조회 (mcp_tools 테이블)
3. ToolHub: 입력 스키마 검증 (input_schema)
4. ToolHub: MCP 서버 base_url + auth 조회
5. ToolHub: HTTP POST 요청
   POST https://mcp-excel.factory-ai.com/mcp/tools/call
   Authorization: Bearer {{ api_key }}
   {
     "method": "read_excel",
     "params": { "file_path": "...", "sheet_name": "..." }
   }
6. MCP Server: 도구 실행 및 응답 반환
7. ToolHub: 응답 스키마 검증 (output_schema)
8. ToolHub: 결과 반환 (Workflow Executor)
```

**Circuit Breaker 적용**:
- MCP 서버별 실패율 추적
- 실패율 > 50% (최근 10회) → OPEN 상태
- OPEN 상태: 즉시 에러 반환, Fallback 응답 사용
- 30초 후 HALF_OPEN → 테스트 요청 허용

#### 1.2.2 Native DB Connector Integration (직접 연결)

**ERP/MES DB 직접 연결**:

```
┌─────────────────────────────────────────────────────────────┐
│                      Data Hub Service                       │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │ Connector  │  │   Health   │  │   Schema   │           │
│  │  Manager   │  │   Check    │  │   Sync     │           │
│  └────────────┘  └────────────┘  └────────────┘           │
└─────────────────────────────────────────────────────────────┘
         │                  │                  │
         ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ ERP DB       │  │ MES DB       │  │ Sensor DB    │
│ (PostgreSQL) │  │ (MySQL)      │  │ (InfluxDB)   │
└──────────────┘  └──────────────┘  └──────────────┘
```

**Connection Pool 설정**:
```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

# ERP DB 연결 (Read-only)
erp_engine = create_engine(
    'postgresql://readonly_user:***@erp-db.company.com:5432/erp_prod',
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=3600
)

# MES DB 연결
mes_engine = create_engine(
    'mysql+pymysql://readonly_user:***@mes-db.company.com:3306/mes_prod',
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10
)
```

#### 1.2.3 Event-Driven Integration (비동기 연동)

**MQTT 센서 데이터 수집**:

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   센서       │ ──> │ MQTT Broker  │ ──> │  Data Hub    │
│ (온도/습도)   │     │ (Mosquitto)  │     │  (Subscriber)│
└──────────────┘     └──────────────┘     └──────────────┘
                                                  │
                                                  ▼
                                          [PostgreSQL]
                                          (sensor_events)
```

**MQTT 구독 코드**:
```python
import paho.mqtt.client as mqtt

def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    client.subscribe("sensor/#")

def on_message(client, userdata, msg):
    topic = msg.topic  # 'sensor/LINE-A/temperature'
    payload = json.loads(msg.payload.decode())

    # DB 저장
    save_sensor_event(
        tenant_id=payload['tenant_id'],
        line_code=extract_line_code(topic),
        sensor_type=extract_sensor_type(topic),
        value=payload['value'],
        unit=payload['unit'],
        timestamp=payload['timestamp']
    )

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect("mqtt.company.com", 1883, 60)
client.loop_forever()
```

### 1.3 API Gateway 패턴

#### 1.3.1 Gateway Aggregation (게이트웨이 집계)

**목적**: 여러 서비스 호출을 하나의 요청으로 집계

**예시**: 대시보드 초기 로딩
```
Client → API Gateway → [Judgment Service, BI Service, Workflow Service]
                              ↓
                        [Aggregated Response]
```

**API Gateway 집계 로직** (Nginx Lua 또는 Kong):
```lua
local http = require "resty.http"
local cjson = require "cjson"

-- 병렬 요청
local judgment_response = http.get("http://judgment-service:8010/api/v1/judgment/recent")
local bi_response = http.get("http://bi-service:8020/api/v1/bi/dashboard")
local workflow_response = http.get("http://workflow-service:8003/api/v1/workflows/instances/active")

-- 결과 집계
local aggregated = {
  judgments = cjson.decode(judgment_response.body),
  bi_widgets = cjson.decode(bi_response.body),
  active_workflows = cjson.decode(workflow_response.body)
}

ngx.say(cjson.encode(aggregated))
```

#### 1.3.2 Backend for Frontend (BFF)

**목적**: 클라이언트 타입별 최적화된 API 제공

```
┌──────────────┐                ┌──────────────┐
│   Web UI     │ ───────────> │  Web BFF     │ ──┐
└──────────────┘                └──────────────┘   │
                                                   │
┌──────────────┐                ┌──────────────┐   │
│  Mobile App  │ ───────────> │  Mobile BFF  │ ──┤
└──────────────┘                └──────────────┘   │
                                                   │
┌──────────────┐                ┌──────────────┐   │
│  Slack Bot   │ ───────────> │  Slack BFF   │ ──┤
└──────────────┘                └──────────────┘   │
                                                   │
                                                   ▼
                              ┌────────────────────────────┐
                              │   Shared Backend Services  │
                              │ (Judgment, Workflow, BI)   │
                              └────────────────────────────┘
```

**BFF 책임**:
- 클라이언트 맞춤 데이터 포맷 (Web: 상세, Mobile: 간소)
- 여러 백엔드 호출 집계
- 캐싱 (클라이언트별)
- 에러 변환 (사용자 친화적 메시지)

---

## 2. 보안 아키텍처

### 2.1 개요
보안 아키텍처는 인증, 인가, 암호화, 감사 로깅을 통해 시스템을 보호한다.

### 2.2 인증 및 인가 아키텍처

#### 2.2.1 OAuth 2.0 + JWT 흐름

```
┌──────────┐                                  ┌──────────────┐
│  Client  │                                  │ Auth Service │
└──────────┘                                  └──────────────┘
     │                                                │
     │ 1. Login (username, password)                 │
     ├───────────────────────────────────────────────>│
     │                                                │
     │ 2. JWT Token (access + refresh)               │
     │<───────────────────────────────────────────────┤
     │                                                │
     │ 3. API Request (Authorization: Bearer token)  │
     ├───────────────────────────────────────────────>│
     │                                                │
     │ 4. Token Validation                           │
     │                                       ┌────────┴────────┐
     │                                       │ Verify Signature│
     │                                       │ Check Expiry    │
     │                                       │ Extract Claims  │
     │                                       └────────┬────────┘
     │                                                │
     │ 5. API Response                               │
     │<───────────────────────────────────────────────┤
     │                                                │
     │ 6. Token Expired → Refresh Token              │
     ├───────────────────────────────────────────────>│
     │                                                │
     │ 7. New Access Token                           │
     │<───────────────────────────────────────────────┤
     │                                                │
```

**JWT 구조**:
```json
{
  "header": {
    "alg": "RS256",
    "typ": "JWT"
  },
  "payload": {
    "sub": "user-123",
    "tenant_id": "tenant-456",
    "email": "user@company.com",
    "roles": ["manager", "analyst"],
    "permissions": ["workflow:create", "workflow:execute", "bi:query"],
    "iat": 1732608000,
    "exp": 1732694400
  },
  "signature": "..."
}
```

**Token 검증 미들웨어**:
```python
from fastapi import Request, HTTPException
from jose import jwt, JWTError

async def verify_token(request: Request):
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    token = auth_header.split(' ')[1]

    try:
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=['RS256'])
        request.state.user_id = payload['sub']
        request.state.tenant_id = payload['tenant_id']
        request.state.roles = payload['roles']
        request.state.permissions = payload['permissions']
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
```

#### 2.2.2 RBAC (Role-Based Access Control)

**역할 계층**:
```
Admin
  ├─ Manager
  │    ├─ Analyst
  │    │    └─ Viewer
  │    └─ Operator
  └─ AI Engineer
```

**권한 체크 데코레이터**:
```python
from functools import wraps

def require_permission(permission: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            if permission not in request.state.permissions:
                raise HTTPException(
                    status_code=403,
                    detail=f"Missing required permission: {permission}"
                )
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator

# 사용 예시
@app.post("/api/v1/workflows")
@require_permission("workflow:create")
async def create_workflow(request: Request, workflow_data: dict):
    tenant_id = request.state.tenant_id
    # ... workflow 생성 로직
```

### 2.3 암호화 아키텍처

#### 2.3.1 전송 암호화 (TLS)

**TLS 종료 지점**: AWS ALB 또는 Nginx

**Nginx TLS 설정**:
```nginx
server {
    listen 443 ssl http2;
    server_name api.factory-ai.com;

    # TLS 인증서
    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;

    # TLS 설정
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256';
    ssl_prefer_server_ciphers on;

    # HSTS
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # 프록시 설정
    location /api/v1/judgment {
        proxy_pass http://judgment-service:8010;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### 2.3.2 저장 암호화 (AES-256)

**암호화 대상**:
- 사용자 비밀번호: bcrypt (해시)
- API Key, DB 비밀번호: AES-256-GCM
- PII 데이터 (선택적): AES-256-GCM

**키 관리 (AWS KMS)**:
```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Application  │ ──> │  AWS KMS     │ ──> │  Encrypted   │
│              │     │ (CMK: 마스터  │     │    Data      │
│              │     │  암호화 키)   │     │  (DB/S3)     │
└──────────────┘     └──────────────┘     └──────────────┘
```

**암호화 코드 예시**:
```python
import boto3
import base64

kms_client = boto3.client('kms', region_name='us-east-1')

def encrypt_data(plaintext: str, key_id: str) -> str:
    response = kms_client.encrypt(
        KeyId=key_id,
        Plaintext=plaintext.encode()
    )
    ciphertext_blob = response['CiphertextBlob']
    return base64.b64encode(ciphertext_blob).decode()

def decrypt_data(ciphertext: str) -> str:
    ciphertext_blob = base64.b64decode(ciphertext.encode())
    response = kms_client.decrypt(
        CiphertextBlob=ciphertext_blob
    )
    return response['Plaintext'].decode()

# 사용 예시
api_key = "sk-1234567890abcdef"
encrypted_key = encrypt_data(api_key, key_id='arn:aws:kms:...')
# → "AQICAHh...encrypted..."

decrypted_key = decrypt_data(encrypted_key)
# → "sk-1234567890abcdef"
```

### 2.4 PII 마스킹 아키텍처

**마스킹 파이프라인**:
```
[User Input] → [PII Detector] → [Masking] → [LLM API / Logging]
                                     ↓
                              [Original Stored]
                              (암호화, 접근 제한)
```

**PII Detector**:
```python
import re

class PIIDetector:
    PATTERNS = {
        'email': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        'phone': r'\d{3}-\d{4}-\d{4}',
        'ssn': r'\d{6}-\d{7}',
        'korean_name': r'[가-힣]{2,4}',
    }

    def detect(self, text: str) -> list:
        detections = []
        for pii_type, pattern in self.PATTERNS.items():
            matches = re.finditer(pattern, text)
            for match in matches:
                detections.append({
                    'type': pii_type,
                    'value': match.group(),
                    'start': match.start(),
                    'end': match.end()
                })
        return detections

    def mask(self, text: str) -> str:
        # 이름
        text = re.sub(r'([가-힣])([가-힣]+)([가-힣])', r'\1*\3', text)
        # 이메일
        text = re.sub(r'([a-zA-Z0-9])([a-zA-Z0-9._%+-]+)(@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', r'\1***\3', text)
        # 전화
        text = re.sub(r'(\d{3})-(\d{4})-(\d{4})', r'\1-****-\3', text)
        # 주민번호
        text = re.sub(r'(\d{6})-(\d{7})', r'\1-*******', text)
        return text
```

---

## 3. 확장성 아키텍처

### 3.1 수평 확장 (Horizontal Scaling)

#### 3.1.1 Stateless 서비스 설계

**원칙**: 모든 애플리케이션 서비스는 상태를 저장하지 않는다.

- **세션**: Redis에 저장 (session:{session_id})
- **Workflow 인스턴스**: PostgreSQL에 저장 (workflow_instances)
- **캐시**: Redis 공유

**스케일아웃 시나리오**:
```
초기: Judgment Service 2 replicas
부하 증가 (CPU > 70%) → HPA 트리거
→ Judgment Service 3 replicas (+ 1개 추가)
→ Kubernetes가 신규 Pod 생성 및 Service에 자동 등록
→ 로드 밸런서가 트래픽 분산 (Round-robin)
```

**HPA 메트릭**:
```yaml
metrics:
- type: Resource
  resource:
    name: cpu
    target:
      type: Utilization
      averageUtilization: 70
- type: Pods
  pods:
    metric:
      name: request_queue_length
    target:
      type: AverageValue
      averageValue: "10"
```

#### 3.1.2 데이터베이스 샤딩 (향후 확장)

**Tenant 기반 샤딩** (사용자 증가 시):

```
┌──────────────────────────────────────────────────────────┐
│                    Application Layer                     │
└──────────────────────────────────────────────────────────┘
                         │
                         ▼ (Shard Router)
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Shard 1     │  │  Shard 2     │  │  Shard 3     │
│              │  │              │  │              │
│ Tenant 1-100 │  │Tenant 101-200│  │Tenant 201-300│
└──────────────┘  └──────────────┘  └──────────────┘
```

**샤딩 키**: `tenant_id` (해시 기반 샤딩)

**샤드 라우팅 로직**:
```python
def get_shard(tenant_id: str) -> DatabaseEngine:
    shard_index = hash(tenant_id) % NUM_SHARDS
    return SHARD_ENGINES[shard_index]

# 사용 예시
shard = get_shard(tenant_id)
result = shard.execute("SELECT * FROM judgment_executions WHERE tenant_id = %s", (tenant_id,))
```

### 3.2 캐시 계층화 (Cache Hierarchy)

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                        │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  L1 Cache (In-Memory)                       │
│  LRU Cache (최대 1000개, TTL 60s)                           │
└─────────────────────────────────────────────────────────────┘
                         │ (Cache MISS)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  L2 Cache (Redis)                           │
│  Distributed Cache (TTL 300~600s)                          │
└─────────────────────────────────────────────────────────────┘
                         │ (Cache MISS)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               PostgreSQL (Source of Truth)                  │
└─────────────────────────────────────────────────────────────┘
```

**L1 Cache (In-Memory)**:
```python
from cachetools import TTLCache

# 프로세스별 로컬 캐시 (최대 1000개, TTL 60초)
l1_cache = TTLCache(maxsize=1000, ttl=60)

def get_judgment_with_cache(workflow_id, input_data):
    cache_key = get_cache_key(workflow_id, input_data)

    # L1 캐시 조회
    if cache_key in l1_cache:
        return l1_cache[cache_key]

    # L2 캐시 조회 (Redis)
    cached = redis_client.get(cache_key)
    if cached:
        result = json.loads(cached)
        l1_cache[cache_key] = result  # L1에도 저장
        return result

    # DB 조회
    result = execute_judgment(workflow_id, input_data)

    # L2 캐시 저장
    redis_client.setex(cache_key, 300, json.dumps(result))

    # L1 캐시 저장
    l1_cache[cache_key] = result

    return result
```

---

## 4. 가용성 및 재해 복구 아키텍처

### 4.1 고가용성 설계

#### 4.1.1 Multi-AZ 배포 (AWS)

```
┌─────────────────────────────────────────────────────────────┐
│                      AWS Region (us-east-1)                 │
├─────────────────────────────────────────────────────────────┤
│  AZ-1 (us-east-1a)     │  AZ-2 (us-east-1b)     │ AZ-3     │
│  ┌────────────┐         │  ┌────────────┐        │          │
│  │ Judgment   │         │  │ Judgment   │        │          │
│  │ Service    │         │  │ Service    │        │          │
│  │ (Pod 1)    │         │  │ (Pod 2)    │        │          │
│  └────────────┘         │  └────────────┘        │          │
│  ┌────────────┐         │  ┌────────────┐        │          │
│  │PostgreSQL  │         │  │PostgreSQL  │        │          │
│  │ (Primary)  │ <──────────┤ (Replica)  │        │          │
│  └────────────┘         │  └────────────┘        │          │
└─────────────────────────────────────────────────────────────┘
```

**이점**: AZ-1 장애 시 AZ-2로 자동 Failover

#### 4.1.2 PostgreSQL Streaming Replication

```
┌──────────────────────────────────────────────────────────────┐
│                    PostgreSQL Architecture                   │
├──────────────────────────────────────────────────────────────┤
│  ┌────────────┐                                              │
│  │  Primary   │ (Write)                                      │
│  │  (Master)  │                                              │
│  └─────┬──────┘                                              │
│        │ WAL Streaming (Async)                               │
│        ├─────────────────┬─────────────────┐                 │
│        ▼                 ▼                 ▼                 │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐         │
│  │ Replica 1  │    │ Replica 2  │    │  Standby   │         │
│  │ (Read)     │    │ (Read)     │    │ (Failover) │         │
│  └────────────┘    └────────────┘    └────────────┘         │
│                                                              │
│  [Patroni] 또는 [PgPool] 기반 자동 Failover                  │
└──────────────────────────────────────────────────────────────┘
```

**Patroni 설정**:
```yaml
scope: factory-ai-postgres
name: postgresql-0

restapi:
  listen: 0.0.0.0:8008
  connect_address: postgresql-0:8008

postgresql:
  listen: 0.0.0.0:5432
  connect_address: postgresql-0:5432
  data_dir: /var/lib/postgresql/data
  parameters:
    max_connections: 200
    shared_buffers: 4GB
    effective_cache_size: 12GB
    wal_level: replica
    max_wal_senders: 5

bootstrap:
  dcs:
    ttl: 30
    loop_wait: 10
    retry_timeout: 10
    maximum_lag_on_failover: 1048576

  initdb:
  - encoding: UTF8
  - data-checksums

  pg_hba:
  - host replication replicator 0.0.0.0/0 md5
  - host all all 0.0.0.0/0 md5
```

**Failover 시나리오**:
```
1. Primary 장애 감지 (Patroni 헬스 체크 3회 실패)
2. Patroni가 Replica 1을 Primary로 승격
3. VIP (Virtual IP)를 새 Primary로 이동
4. 애플리케이션은 VIP 통해 자동 재연결
5. Replica 2는 새 Primary를 따르도록 재설정
6. 총 Failover 시간: 30초~2분
```

#### 4.1.3 Redis Sentinel (High Availability)

```
┌──────────────────────────────────────────────────────────────┐
│                      Redis Architecture                      │
├──────────────────────────────────────────────────────────────┤
│  ┌────────────┐                                              │
│  │  Master    │ (Write)                                      │
│  └─────┬──────┘                                              │
│        │ Replication (Async)                                 │
│        ├─────────────────┐                                   │
│        ▼                 ▼                                   │
│  ┌────────────┐    ┌────────────┐                           │
│  │ Replica 1  │    │ Replica 2  │                           │
│  │ (Read)     │    │ (Read)     │                           │
│  └────────────┘    └────────────┘                           │
│                                                              │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐         │
│  │ Sentinel 1 │    │ Sentinel 2 │    │ Sentinel 3 │         │
│  │            │    │            │    │            │         │
│  │  (Monitor) │    │  (Monitor) │    │  (Monitor) │         │
│  └────────────┘    └────────────┘    └────────────┘         │
│                                                              │
│  Sentinel Quorum: 2 (과반수)                                 │
└──────────────────────────────────────────────────────────────┘
```

**Sentinel 설정**:
```conf
# sentinel.conf
sentinel monitor factory-ai-redis redis-master 6379 2
sentinel down-after-milliseconds factory-ai-redis 5000
sentinel parallel-syncs factory-ai-redis 1
sentinel failover-timeout factory-ai-redis 60000
```

**Failover 시나리오**:
```
1. Master 장애 감지 (Sentinel 3개 중 2개 동의)
2. Sentinel이 Replica 1을 Master로 승격
3. 다른 Replica는 새 Master를 따르도록 재설정
4. 클라이언트 라이브러리가 새 Master 주소 수신 (Sentinel 통해)
5. 총 Failover 시간: 10초~30초
```

**Python 클라이언트 설정**:
```python
from redis.sentinel import Sentinel

sentinel = Sentinel([
    ('sentinel-1', 26379),
    ('sentinel-2', 26379),
    ('sentinel-3', 26379)
], socket_timeout=0.1)

# Master 자동 검색 및 연결
master = sentinel.master_for('factory-ai-redis', socket_timeout=0.1)
master.set('key', 'value')

# Replica 자동 검색 및 연결 (읽기 전용)
replica = sentinel.slave_for('factory-ai-redis', socket_timeout=0.1)
value = replica.get('key')
```

### 4.2 재해 복구 (Disaster Recovery)

#### 4.2.1 백업 전략

**PostgreSQL 백업**:
```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Primary DB  │ ──> │ WAL Archive  │ ──> │  S3 Bucket   │
│              │     │ (Continuous) │     │ (us-east-1)  │
└──────────────┘     └──────────────┘     └──────────────┘
       │
       │ (Daily Full Backup)
       ▼
┌──────────────┐     ┌──────────────┐
│  pg_dump     │ ──> │  S3 Bucket   │
│  (03:00 AM)  │     │ (Cross-Region│
└──────────────┘     │  us-west-2)  │
                     └──────────────┘
```

**백업 스크립트**:
```bash
#!/bin/bash
# backup_postgres.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/postgres"
S3_BUCKET="s3://factory-ai-backups"

# Full Backup
pg_dump -h $DB_HOST -U $DB_USER -d factory_ai -F c -f $BACKUP_DIR/factory_ai_$DATE.dump

# Compress
gzip $BACKUP_DIR/factory_ai_$DATE.dump

# Upload to S3 (us-east-1)
aws s3 cp $BACKUP_DIR/factory_ai_$DATE.dump.gz $S3_BUCKET/postgres/daily/

# Cross-Region Replication (us-east-1 → us-west-2)
aws s3 cp $S3_BUCKET/postgres/daily/factory_ai_$DATE.dump.gz $S3_BUCKET-dr/postgres/daily/ --region us-west-2

# Delete local file
rm $BACKUP_DIR/factory_ai_$DATE.dump.gz

# Delete old backups (30 days)
aws s3 ls $S3_BUCKET/postgres/daily/ | grep "factory_ai_" | awk '{print $4}' | sort -r | tail -n +31 | xargs -I {} aws s3 rm $S3_BUCKET/postgres/daily/{}
```

#### 4.2.2 DR 사이트 구성

**Primary Site (us-east-1)** ⇄ **DR Site (us-west-2)**

```
┌───────────────────────────────────────┐
│    Primary Site (us-east-1)           │
│  ┌────────────┐  ┌────────────┐       │
│  │ PostgreSQL │  │   Redis    │       │
│  │ (Primary)  │  │  (Master)  │       │
│  └────────────┘  └────────────┘       │
│  ┌────────────┐                       │
│  │    All     │                       │
│  │  Services  │                       │
│  └────────────┘                       │
└───────────────────────────────────────┘
         │
         │ (WAL Streaming, Backup Replication)
         ▼
┌───────────────────────────────────────┐
│       DR Site (us-west-2)             │
│  ┌────────────┐  ┌────────────┐       │
│  │ PostgreSQL │  │   Redis    │       │
│  │ (Standby)  │  │ (Standby)  │       │
│  └────────────┘  └────────────┘       │
│  ┌────────────┐                       │
│  │    All     │ (Idle, 준비 상태)     │
│  │  Services  │                       │
│  └────────────┘                       │
└───────────────────────────────────────┘
```

**DR Failover 절차** (수동):
1. Primary Site 장애 확인 (네트워크, 데이터센터 장애)
2. DR Site PostgreSQL Standby → Primary 승격
3. DR Site Redis Standby → Master 승격
4. DNS 변경 (api.factory-ai.com → DR ALB)
5. DR Site 서비스 활성화 (replicas 증가)
6. 총 RTO: 30분~4시간 (수동 작업 포함)

---

## 다음 파일로 계속

본 문서는 B-1-3로, 통합 아키텍처, 보안 아키텍처, 확장성 아키텍처, 가용성/재해복구 아키텍처를 포함한다.

**다음 파일**:
- **B-1-4**: 기술 스택 상세, 아키텍처 결정 기록 (ADR), 마이그레이션 전략

---

## 문서 이력
| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2025-11-26 | AI Factory Team | 초안 작성 |
