# C-5. Security & Compliance Design - Enhanced

## 문서 정보
- **문서 ID**: C-5
- **버전**: 3.0 (V7 Intent + Orchestrator)
- **최종 수정일**: 2025-12-16
- **상태**: Active Development
- **관련 문서**:
  - A-2 System Requirements (SEC-FR-*, NFR-SEC-*)
  - B-1 System Architecture (보안 아키텍처)
  - B-3-3 V7 Intent Router 설계
  - B-3-4 Orchestrator 설계
  - C-3 Test Plan (보안 테스트)
  - D-3 Operation Runbook (보안 사고 대응)

## 목차
1. [보안 개요 및 목표](#1-보안-개요-및-목표)
2. [인증 및 인가 (AuthN & AuthZ)](#2-인증-및-인가-authn--authz)
3. [데이터 보안 (Encryption & PII)](#3-데이터-보안-encryption--pii)
4. [네트워크 보안](#4-네트워크-보안)
5. [애플리케이션 보안](#5-애플리케이션-보안)
6. [V7 Intent Router & Orchestrator 보안](#6-v7-intent-router--orchestrator-보안)
7. [감사 및 로깅](#7-감사-및-로깅)
8. [규제 준수 (Compliance)](#8-규제-준수-compliance)
9. [보안 사고 대응](#9-보안-사고-대응)

---

## 1. 보안 개요 및 목표

### 1.1 보안 목표

| 목표 | 설명 | 측정 지표 |
|------|------|----------|
| **기밀성** | 무단 접근 및 데이터 유출 방지 | 데이터 유출 사고 0건 |
| **무결성** | 데이터 무단 변경 방지 | 무단 변경 사고 0건 |
| **가용성** | 서비스 지속성 보장 | 가용성 > 99.9% |
| **추적성** | 모든 변경 기록 및 추적 | 감사 로그 100% |
| **규제 준수** | HACCP, ISO, GDPR 준수 | 규제 위반 0건 |

### 1.2 보안 원칙

1. **Defense in Depth** (심층 방어): 여러 보안 계층 적용
2. **Least Privilege** (최소 권한): 필요한 최소 권한만 부여
3. **Fail-Safe Defaults** (안전한 기본값): 기본적으로 접근 거부
4. **Zero Trust** (제로 트러스트): 모든 요청 검증
5. **Privacy by Design** (설계 단계 프라이버시): PII 최소화, 마스킹

---

## 2. 인증 및 인가 (AuthN & AuthZ)

### 2.1 인증 (Authentication)

#### 2.1.1 OAuth 2.0 + JWT

**인증 흐름**:
```
┌──────────┐                                  ┌──────────────┐
│  Client  │                                  │ Auth Service │
└──────────┘                                  └──────────────┘
     │                                                │
     │ 1. POST /auth/login                          │
     │    {email, password}                          │
     ├──────────────────────────────────────────────>│
     │                                                │
     │ 2. Validate credentials (DB, bcrypt)          │
     │                                       ┌────────┴────────┐
     │                                       │ Check password  │
     │                                       │ hash (bcrypt)   │
     │                                       └────────┬────────┘
     │                                                │
     │ 3. Generate JWT Tokens                        │
     │    - Access Token (15분 TTL)                  │
     │    - Refresh Token (7일 TTL)                  │
     │                                                │
     │<───────────────────────────────────────────────┤
     │ {access_token, refresh_token}                 │
     │                                                │
     │ 4. API Request                                │
     │    Authorization: Bearer {access_token}       │
     ├──────────────────────────────────────────────>│
     │                                                │
     │ 5. Verify Token (RS256 signature)            │
     │                                       ┌────────┴────────┐
     │                                       │ Check signature │
     │                                       │ Check expiry    │
     │                                       │ Extract claims  │
     │                                       └────────┬────────┘
     │                                                │
     │ 6. API Response                               │
     │<───────────────────────────────────────────────┤
     │                                                │
```

**JWT Payload 구조**:
```json
{
  "sub": "user-123",
  "tenant_id": "tenant-456",
  "email": "user@company.com",
  "roles": ["manager", "analyst"],
  "permissions": [
    "workflow:create",
    "workflow:execute",
    "bi:query",
    "judgment:execute"
  ],
  "iat": 1732608000,
  "exp": 1732608900,
  "iss": "https://auth.factory-ai.com",
  "aud": "https://api.factory-ai.com"
}
```

**Token 검증 구현**:
```python
from jose import jwt, JWTError
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """JWT 토큰 검증"""
    token = credentials.credentials

    try:
        # RS256 서명 검증 (공개 키)
        payload = jwt.decode(
            token,
            PUBLIC_KEY,
            algorithms=['RS256'],
            audience='https://api.factory-ai.com',
            issuer='https://auth.factory-ai.com'
        )

        # 만료 시간 자동 확인됨
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token expired"
        )
    except JWTError as e:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid token: {str(e)}"
        )
```

### 2.2 인가 (Authorization)

#### 2.2.1 RBAC (Role-Based Access Control)

**역할 정의**:

| 역할 | 상속 | 권한 |
|------|------|------|
| **Admin** | - | 전체 시스템 설정, 사용자 관리 |
| **Manager** | Analyst | Workflow 생성, Rule 승인, 배포 |
| **Analyst** | Viewer | BI 분석, 대시보드 생성 |
| **Operator** | Viewer | Workflow 실행, Judgment 실행 |
| **Viewer** | - | 읽기 전용 |
| **Approver** | Viewer | 승인 전용 (Rule, Workflow) |

**권한 매트릭스**:

| 리소스 | Admin | Manager | Analyst | Operator | Viewer | Approver |
|--------|-------|---------|---------|----------|--------|----------|
| **Workflow 생성** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Workflow 수정** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Workflow 실행** | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| **Workflow 승인** | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| **Rule 생성** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Rule 배포** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Rule 승인** | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| **Judgment 실행** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **BI 분석 생성** | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **BI 분석 조회** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **V7 Intent 실행** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Orchestrator Plan 조회** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Orchestrator Plan 생성** | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **15 노드 Workflow 생성** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **P2 노드 사용 (DEPLOY, ROLLBACK)** | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| **사용자 관리** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **감사 로그 조회** | ✅ | ✅ | 제한적 | 제한적 | 제한적 | 제한적 |

**권한 체크 구현**:
```python
from functools import wraps
from fastapi import Request, HTTPException

def require_permission(permission: str):
    """권한 체크 데코레이터"""
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user = request.state.user

            if permission not in user.get('permissions', []):
                raise HTTPException(
                    status_code=403,
                    detail={
                        'error': 'insufficient_permissions',
                        'message': f'Missing required permission: {permission}',
                        'required_permission': permission,
                        'user_roles': user.get('roles', [])
                    }
                )

            return await func(request, *args, **kwargs)
        return wrapper
    return decorator

# 사용 예시
@app.post("/api/v1/workflows")
@require_permission("workflow:create")
async def create_workflow(request: Request, workflow_data: dict):
    tenant_id = request.state.user['tenant_id']
    # ... workflow 생성 로직
```

---

## 3. 데이터 보안 (Encryption & PII)

### 3.1 전송 암호화 (TLS)

**TLS 1.2 이상 적용**:
- **외부 통신**: 모든 외부 API HTTPS (ALB → Nginx)
- **내부 통신**: Kubernetes Service Mesh (선택적, mTLS)

**TLS 설정 (Nginx)**:
```nginx
server {
    listen 443 ssl http2;
    server_name api.factory-ai.com;

    # 인증서
    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;

    # 프로토콜
    ssl_protocols TLSv1.2 TLSv1.3;

    # 암호화 스위트 (안전한 것만)
    ssl_ciphers 'ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256:!aNULL:!MD5:!DSS';
    ssl_prefer_server_ciphers on;

    # HSTS (Strict Transport Security)
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # OCSP Stapling
    ssl_stapling on;
    ssl_stapling_verify on;
    ssl_trusted_certificate /etc/nginx/ssl/chain.pem;

    location / {
        proxy_pass http://api-gateway:8080;
    }
}
```

### 3.2 저장 암호화 (Encryption at Rest)

#### 3.2.1 데이터베이스 암호화

**PostgreSQL Transparent Data Encryption** (AWS RDS):
- RDS 인스턴스 생성 시 Encryption 활성화
- KMS 키 사용 (AWS Managed 또는 Customer Managed)

**민감 컬럼 추가 암호화** (Application-Level):
```python
from cryptography.fernet import Fernet

class FieldEncryption:
    def __init__(self, key: bytes):
        self.fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        """필드 암호화"""
        return self.fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """필드 복호화"""
        return self.fernet.decrypt(ciphertext.encode()).decode()

# 사용 예시 (SQLAlchemy)
from sqlalchemy import TypeDecorator, String

class EncryptedString(TypeDecorator):
    impl = String
    cache_ok = True

    def __init__(self, key: bytes, *args, **kwargs):
        self.encryptor = FieldEncryption(key)
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value, dialect):
        """저장 시 암호화"""
        if value is not None:
            return self.encryptor.encrypt(value)

    def process_result_value(self, value, dialect):
        """조회 시 복호화"""
        if value is not None:
            return self.encryptor.decrypt(value)

# Model 정의
class DataConnector(Base):
    __tablename__ = 'data_connectors'

    id = Column(UUID, primary_key=True)
    name = Column(String(100))
    password = Column(EncryptedString(ENCRYPTION_KEY, 255))  # 암호화된 컬럼
```

### 3.3 PII 마스킹 (Personal Identifiable Information)

#### 3.3.1 PII 탐지 및 마스킹

**PII 패턴**:

| PII 타입 | 정규표현식 | 마스킹 예시 |
|---------|-----------|------------|
| **이름** | `[가-힣]{2,4}` | 홍길동 → 홍\*동 |
| **이메일** | `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}` | hong@example.com → h\*\*\*@example.com |
| **전화번호** | `\d{3}-\d{4}-\d{4}` | 010-1234-5678 → 010-\*\*\*\*-5678 |
| **주민등록번호** | `\d{6}-\d{7}` | 801201-1234567 → 801201-\*\*\*\*\*\*\* |
| **신용카드** | `\d{4}-\d{4}-\d{4}-\d{4}` | 1234-5678-9012-3456 → 1234-\*\*\*\*-\*\*\*\*-3456 |

**마스킹 게이트웨이**:
```python
import re
from typing import Any, Dict

class PIIMaskingGateway:
    PATTERNS = {
        'korean_name': (r'([가-힣])([가-힣]+)([가-힣])', r'\1*\3'),
        'email': (r'([a-zA-Z0-9])([a-zA-Z0-9._%+-]+)(@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', r'\1***\3'),
        'phone': (r'(\d{3})-(\d{4})-(\d{4})', r'\1-****-\3'),
        'ssn': (r'(\d{6})-(\d{7})', r'\1-*******'),
        'credit_card': (r'(\d{4})-(\d{4})-(\d{4})-(\d{4})', r'\1-****-****-\4'),
    }

    def mask(self, text: str) -> str:
        """PII 마스킹"""
        masked = text
        for pii_type, (pattern, replacement) in self.PATTERNS.items():
            masked = re.sub(pattern, replacement, masked)
        return masked

    def mask_dict(self, data: Dict[str, Any], sensitive_fields: list = None) -> Dict[str, Any]:
        """dict PII 마스킹 (재귀)"""
        if sensitive_fields is None:
            sensitive_fields = ['name', 'email', 'phone', 'address', 'comment']

        masked_data = {}
        for key, value in data.items():
            if key in sensitive_fields and isinstance(value, str):
                masked_data[key] = self.mask(value)
            elif isinstance(value, dict):
                masked_data[key] = self.mask_dict(value, sensitive_fields)
            elif isinstance(value, list):
                masked_data[key] = [
                    self.mask_dict(item, sensitive_fields) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                masked_data[key] = value

        return masked_data

# LLM 호출 전 마스킹
pii_gateway = PIIMaskingGateway()

def call_llm_with_masking(input_data: dict) -> dict:
    # 1. PII 마스킹
    masked_input = pii_gateway.mask_dict(input_data)

    # 2. LLM 호출
    response = llm_client.call(masked_input)

    return response
```

---

## 4. 네트워크 보안

### 4.1 네트워크 분리 (VPC Subnets)

```
┌─────────────────────────────────────────────────────────┐
│                    Public Subnet (DMZ)                  │
│  ┌────────────┐  ┌────────────┐                        │
│  │    ALB     │  │  Bastion   │                        │
│  │ (Internet) │  │    Host    │                        │
│  └────────────┘  └────────────┘                        │
└─────────────────────────────────────────────────────────┘
                       │
                       ▼ (Private Routing)
┌─────────────────────────────────────────────────────────┐
│              Private Subnet (Application)               │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐       │
│  │  Services  │  │  Services  │  │  Services  │       │
│  │ (Judgment) │  │ (Workflow) │  │    (BI)    │       │
│  └────────────┘  └────────────┘  └────────────┘       │
└─────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│               Private Subnet (Database)                 │
│  ┌────────────┐  ┌────────────┐                        │
│  │PostgreSQL  │  │   Redis    │                        │
│  │            │  │            │                        │
│  └────────────┘  └────────────┘                        │
│  (외부 접근 불가)                                        │
└─────────────────────────────────────────────────────────┘
```

### 4.2 방화벽 및 Security Groups

#### 4.2.1 Security Group 규칙

**ALB Security Group**:
```
Inbound:
- 0.0.0.0/0 → 443 (HTTPS)

Outbound:
- Application SG → 8000-8099
```

**Application Security Group**:
```
Inbound:
- ALB SG → 8000-8099
- Monitoring SG → 8080/metrics

Outbound:
- Database SG → 5432
- Redis SG → 6379
- Internet (via NAT) → 443 (LLM API, MCP)
```

**Database Security Group**:
```
Inbound:
- Application SG → 5432 (PostgreSQL)
- Application SG → 6379 (Redis)
- Bastion SG → 5432 (Admin 접근)

Outbound:
- None (완전 격리)
```

### 4.3 WAF (Web Application Firewall)

**AWS WAF 규칙**:
- **SQL Injection 방어**: SQL 키워드 패턴 차단
- **XSS 방어**: 스크립트 태그 패턴 차단
- **Rate Limiting**: IP당 100 req/min
- **Geo Blocking**: 특정 국가 차단 (선택적)

---

## 5. 애플리케이션 보안

### 5.1 OWASP Top 10 대응

| 순위 | 취약점 | 대응 방안 | 검증 방법 |
|------|--------|----------|----------|
| **A01** | Broken Access Control | RBAC, JWT 검증, 리소스별 권한 체크 | 권한 우회 테스트 |
| **A02** | Cryptographic Failures | TLS 1.2+, AES-256, bcrypt | SSL Labs, 암호화 검증 |
| **A03** | Injection | Prepared Statement, ORM, 입력 검증 | SQL Injection 테스트 |
| **A04** | Insecure Design | Threat Modeling, 보안 리뷰 | 아키텍처 리뷰 |
| **A05** | Security Misconfiguration | 기본값 변경, 불필요 서비스 비활성화 | 보안 스캔 (Bandit) |
| **A06** | Vulnerable Components | 의존성 스캔 (npm audit, pip-audit) | CI/CD 자동 스캔 |
| **A07** | Authentication Failures | Strong Password, MFA (선택적), JWT | Brute Force 테스트 |
| **A08** | Software Integrity | 서명된 컨테이너 이미지, SBOM | 이미지 스캔 (Trivy) |
| **A09** | Logging Failures | 구조화 로깅, 감사 로그 불변 | 로그 검증 |
| **A10** | SSRF | 외부 URL 화이트리스트, 내부 IP 차단 | SSRF 테스트 |

### 5.2 Secure Coding Practices

#### 5.2.1 입력 검증

**원칙**: Trust No Input (모든 입력 검증)

```python
from pydantic import BaseModel, Field, validator

class JudgmentRequest(BaseModel):
    workflow_id: str = Field(..., regex=r'^[a-f0-9-]{36}$')  # UUID 형식
    input_data: dict
    policy: str = Field(..., regex=r'^(RULE_ONLY|LLM_ONLY|HYBRID_WEIGHTED|HYBRID_GATE)$')

    @validator('input_data')
    def validate_input_data(cls, v):
        """입력 데이터 크기 제한"""
        import json
        if len(json.dumps(v)) > 10000:  # 10KB 제한
            raise ValueError('input_data too large (max 10KB)')
        return v

    @validator('workflow_id')
    def validate_workflow_exists(cls, v):
        """Workflow 존재 여부 확인"""
        # DB 조회 (선택적)
        return v
```

#### 5.2.2 출력 인코딩 (XSS 방어)

**React 자동 이스케이프**:
```typescript
// ✅ 안전 (React 자동 이스케이프)
function JudgmentResult({ result }: { result: string }) {
  return <div>{result}</div>;
}

// ❌ 위험 (dangerouslySetInnerHTML)
function UnsafeResult({ htmlContent }: { htmlContent: string }) {
  return <div dangerouslySetInnerHTML={{ __html: htmlContent }} />;
}

// ✅ 안전 (DOMPurify로 정제)
import DOMPurify from 'dompurify';

function SafeHTMLResult({ htmlContent }: { htmlContent: string }) {
  const clean = DOMPurify.sanitize(htmlContent);
  return <div dangerouslySetInnerHTML={{ __html: clean }} />;
}
```

---

## 6. V7 Intent Router & Orchestrator 보안

### 6.1 V7 Intent 분류 보안

#### 6.1.1 Intent 입력 검증

**V7 Intent 체계 (14개)**:

| 카테고리 | V7 Intent | Route Target | 보안 수준 |
|----------|-----------|--------------|----------|
| **정보 조회** | CHECK, TREND, COMPARE, RANK | DATA_LAYER, JUDGMENT_ENGINE | 낮음 (읽기 전용) |
| **분석** | FIND_CAUSE, DETECT_ANOMALY, PREDICT, WHAT_IF | JUDGMENT_ENGINE, RULE_ENGINE | 중간 (분석 권한 필요) |
| **액션** | REPORT, NOTIFY | BI_GUIDE, WORKFLOW_GUIDE | 높음 (생성/실행 권한 필요) |
| **대화 제어** | CONTINUE, CLARIFY, STOP, SYSTEM | CONTEXT_DEPENDENT, ASK_BACK, DIRECT_RESPONSE | 낮음 (시스템 제어) |

**Intent 입력 검증**:
```python
from pydantic import BaseModel, Field, validator
from enum import Enum
from typing import Optional, Dict, Any

class V7Intent(str, Enum):
    """V7 Intent 체계 (14개)"""
    # 정보 조회
    CHECK = "CHECK"
    TREND = "TREND"
    COMPARE = "COMPARE"
    RANK = "RANK"
    # 분석
    FIND_CAUSE = "FIND_CAUSE"
    DETECT_ANOMALY = "DETECT_ANOMALY"
    PREDICT = "PREDICT"
    WHAT_IF = "WHAT_IF"
    # 액션
    REPORT = "REPORT"
    NOTIFY = "NOTIFY"
    # 대화 제어
    CONTINUE = "CONTINUE"
    CLARIFY = "CLARIFY"
    STOP = "STOP"
    SYSTEM = "SYSTEM"

class IntentRequest(BaseModel):
    """Intent 분류 요청 검증"""
    utterance: str = Field(..., min_length=1, max_length=500)
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    tenant_id: str = Field(..., regex=r'^[a-f0-9-]{36}$')

    @validator('utterance')
    def sanitize_utterance(cls, v):
        """발화 입력 정제 (Injection 방지)"""
        import re
        # 위험 패턴 필터링
        dangerous_patterns = [
            r'<script>.*</script>',  # XSS
            r'{{.*}}',  # Template injection
            r'\$\{.*\}',  # Expression injection
        ]
        for pattern in dangerous_patterns:
            v = re.sub(pattern, '', v, flags=re.IGNORECASE)
        return v.strip()

    @validator('context')
    def validate_context_size(cls, v):
        """컨텍스트 크기 제한 (DoS 방지)"""
        import json
        if len(json.dumps(v)) > 10000:  # 10KB 제한
            raise ValueError('Context too large (max 10KB)')
        return v
```

#### 6.1.2 LLM 호출 보안 (Claude 모델)

**Claude API 호출 보안**:
```python
import anthropic
from typing import Optional

class SecureLLMClient:
    """Claude 모델 보안 클라이언트"""

    # API Key 환경변수에서 로드 (코드에 하드코딩 금지)
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

    # 모델별 토큰 한도
    MODEL_TOKEN_LIMITS = {
        "claude-3-haiku-20240307": 500,   # Intent 분류용
        "claude-3-5-sonnet-20241022": 1500,  # Plan 생성용
        "claude-3-opus-20240229": 3000,   # 복잡한 분석용
    }

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=self.ANTHROPIC_API_KEY)

    async def call_with_pii_masking(
        self,
        prompt: str,
        model: str = "claude-3-haiku-20240307",
        max_tokens: Optional[int] = None
    ) -> str:
        """PII 마스킹 후 Claude 호출"""
        from security.pii_gateway import PIIMaskingGateway

        # 1. PII 마스킹
        pii_gateway = PIIMaskingGateway()
        masked_prompt = pii_gateway.mask(prompt)

        # 2. 토큰 한도 적용
        token_limit = max_tokens or self.MODEL_TOKEN_LIMITS.get(model, 500)

        # 3. Claude API 호출
        response = self.client.messages.create(
            model=model,
            max_tokens=token_limit,
            messages=[{"role": "user", "content": masked_prompt}]
        )

        # 4. 응답 검증 (유해 콘텐츠 필터링)
        return self._validate_response(response.content[0].text)

    def _validate_response(self, response: str) -> str:
        """LLM 응답 검증"""
        # 유해 콘텐츠 필터링
        if self._contains_harmful_content(response):
            return "[응답이 보안 정책에 의해 필터링되었습니다]"
        return response
```

**V7 Intent별 Claude 모델 할당**:

| V7 Intent | 기본 모델 | 복잡도 높을 때 | 토큰 한도 | 보안 수준 |
|-----------|----------|--------------|----------|----------|
| CHECK, TREND | Claude Haiku | Haiku | 500 | 낮음 |
| COMPARE, RANK | Claude Haiku | Sonnet | 800 | 낮음 |
| FIND_CAUSE, DETECT_ANOMALY | Claude Sonnet | Opus | 1,500 | 중간 |
| PREDICT, WHAT_IF | Claude Sonnet | Opus | 2,000 | 중간 |
| REPORT, NOTIFY | Claude Sonnet | Sonnet | 1,200 | 높음 |
| CONTINUE, CLARIFY, STOP, SYSTEM | Claude Haiku | Haiku | 300 | 낮음 |

### 6.2 Orchestrator Plan 보안

#### 6.2.1 Plan 생성 권한 검증

**Route Target별 노드 접근 제어**:
```python
from typing import List, Dict

class OrchestratorSecurityPolicy:
    """Orchestrator Plan 보안 정책"""

    # Route Target → 허용 노드 타입 매핑
    ROUTE_TO_NODE_MAP: Dict[str, List[str]] = {
        "DATA_LAYER": ["DATA", "CODE"],
        "JUDGMENT_ENGINE": ["DATA", "JUDGMENT", "CODE"],
        "RULE_ENGINE": ["DATA", "CODE", "SWITCH"],
        "BI_GUIDE": ["DATA", "BI", "CODE"],
        "WORKFLOW_GUIDE": ["TRIGGER", "DATA", "JUDGMENT", "ACTION", "WAIT"],
        "CONTEXT_DEPENDENT": [],
        "ASK_BACK": [],
        "DIRECT_RESPONSE": [],
    }

    # 노드 타입별 권한 요구 수준
    NODE_PERMISSION_LEVEL: Dict[str, str] = {
        # P0 (핵심) - 5개
        "DATA": "viewer",
        "JUDGMENT": "viewer",
        "CODE": "analyst",
        "SWITCH": "analyst",
        "ACTION": "operator",
        # P1 (확장) - 5개
        "BI": "analyst",
        "MCP": "analyst",
        "TRIGGER": "manager",
        "WAIT": "operator",
        "APPROVAL": "approver",
        # P2 (고급) - 5개
        "PARALLEL": "manager",
        "COMPENSATION": "manager",
        "DEPLOY": "admin",
        "ROLLBACK": "admin",
        "SIMULATE": "analyst",
    }

    @classmethod
    def validate_plan_nodes(
        cls,
        route_target: str,
        plan_nodes: List[str],
        user_role: str
    ) -> bool:
        """Plan 노드 접근 권한 검증"""
        allowed_nodes = cls.ROUTE_TO_NODE_MAP.get(route_target, [])

        for node_type in plan_nodes:
            # 1. Route에서 허용하는 노드인지 확인
            if node_type not in allowed_nodes:
                raise SecurityError(f"Node {node_type} not allowed for route {route_target}")

            # 2. 사용자 권한 수준 확인
            required_level = cls.NODE_PERMISSION_LEVEL.get(node_type, "admin")
            if not cls._has_permission(user_role, required_level):
                raise SecurityError(f"Insufficient permission for node {node_type}")

        return True
```

#### 6.2.2 15 노드 타입 보안 분류

**노드 타입별 보안 정책**:

| 우선순위 | 노드 타입 | 보안 수준 | 감사 로깅 | 승인 필요 |
|---------|----------|----------|----------|----------|
| **P0 (핵심)** | DATA | 낮음 | 선택적 | ❌ |
| P0 | JUDGMENT | 중간 | 필수 | ❌ |
| P0 | CODE | 중간 | 필수 | ❌ |
| P0 | SWITCH | 낮음 | 선택적 | ❌ |
| P0 | ACTION | 높음 | 필수 | ✅ (외부 연동) |
| **P1 (확장)** | BI | 중간 | 필수 | ❌ |
| P1 | MCP | 중간 | 필수 | ❌ |
| P1 | TRIGGER | 높음 | 필수 | ✅ (스케줄 생성) |
| P1 | WAIT | 낮음 | 선택적 | ❌ |
| P1 | APPROVAL | 높음 | 필수 | ✅ (승인 흐름) |
| **P2 (고급)** | PARALLEL | 중간 | 필수 | ❌ |
| P2 | COMPENSATION | 높음 | 필수 | ✅ (롤백 연관) |
| P2 | DEPLOY | 최고 | 필수 | ✅ (운영 배포) |
| P2 | ROLLBACK | 최고 | 필수 | ✅ (운영 롤백) |
| P2 | SIMULATE | 중간 | 필수 | ❌ |

### 6.3 Legacy Intent 매핑 보안

**하위 호환 Intent 변환 보안**:
```python
class LegacyIntentSecurityMapper:
    """Legacy Intent → V7 Intent 보안 매핑"""

    # Legacy Intent → V7 Intent 매핑 (15개)
    LEGACY_INTENT_MAP = {
        "production_status": "CHECK",
        "quality_status": "CHECK",
        "inventory_status": "CHECK",
        "defect_analysis": "FIND_CAUSE",
        "trend_analysis": "TREND",
        "production_analysis": "FIND_CAUSE",
        "realtime_check": "CHECK",
        "threshold_alert": "DETECT_ANOMALY",
        "sensor_check": "CHECK",
        "bi_chart": "REPORT",
        "bi_report": "REPORT",
        "workflow_create": "NOTIFY",
        "greeting": "SYSTEM",
        "help": "SYSTEM",
        "unknown": "CLARIFY",
    }

    @classmethod
    def convert_with_audit(cls, legacy_intent: str, user_id: str) -> str:
        """Legacy Intent 변환 및 감사 로그"""
        v7_intent = cls.LEGACY_INTENT_MAP.get(legacy_intent, legacy_intent)

        # 변환 감사 로그
        if legacy_intent != v7_intent:
            audit_logger.info(
                "Legacy intent converted",
                extra={
                    "legacy_intent": legacy_intent,
                    "v7_intent": v7_intent,
                    "user_id": user_id,
                    "conversion_type": "legacy_to_v7"
                }
            )

        return v7_intent
```

---

## 7. 감사 및 로깅

### 7.1 감사 로그 (Audit Log)

#### 7.1.1 로깅 대상

**모든 변경 작업 로깅**:

| 액션 | 대상 | 로그 필드 |
|------|------|----------|
| **생성** | Workflow, Rule, User | user_id, tenant_id, resource_type, resource_id, new_value |
| **수정** | Workflow, Rule, Connector | old_value, new_value, changed_fields |
| **삭제** | Workflow, Rule, User | old_value, deletion_reason |
| **배포** | Rule, Prompt | version, strategy (canary), traffic_percentage |
| **롤백** | Rule, Prompt | rollback_reason, metrics |
| **승인** | Workflow, Rule | approver_id, approved_at |

**audit_logs 테이블**:
```sql
CREATE TABLE audit.audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  user_id UUID NOT NULL,
  action_type TEXT NOT NULL,  -- create, update, delete, deploy, rollback, approve
  resource_type TEXT NOT NULL,  -- workflow, ruleset, prompt, user
  resource_id UUID NOT NULL,
  old_value JSONB,
  new_value JSONB,
  timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ip_address INET,
  user_agent TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'
);

-- 인덱스
CREATE INDEX idx_audit_logs_tenant_time ON audit.audit_logs(tenant_id, timestamp DESC);
CREATE INDEX idx_audit_logs_resource ON audit.audit_logs(resource_type, resource_id);

-- 로그 불변성 (RLS)
ALTER TABLE audit.audit_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY audit_logs_insert_only ON audit.audit_logs
  FOR ALL
  TO PUBLIC
  USING (false)  -- 읽기 제한 (Admin만)
  WITH CHECK (true);  -- 쓰기만 허용
```

#### 7.1.2 감사 로그 보존

**보존 기간**:
- **Hot Storage** (PostgreSQL): 90일
- **Cold Storage** (S3): 90일~2년
- **Archival**: 2년 후 삭제 (규제에 따라 조정)

**아카이빙 스크립트**:
```bash
#!/bin/bash
# archive_audit_logs.sh

# 90일 이전 로그를 S3로 이동
psql -h $DB_HOST -U postgres -d factory_ai -c "
  COPY (
    SELECT * FROM audit.audit_logs
    WHERE timestamp < NOW() - INTERVAL '90 days'
  ) TO STDOUT WITH CSV HEADER
" | gzip | aws s3 cp - s3://factory-ai-audit-logs/$(date +%Y%m%d).csv.gz

# DB에서 삭제
psql -h $DB_HOST -U postgres -d factory_ai -c "
  DELETE FROM audit.audit_logs
  WHERE timestamp < NOW() - INTERVAL '90 days'
"
```

---

## 8. 규제 준수 (Compliance)

### 8.1 HACCP / ISO 22000 준수

#### 8.1.1 CCP (Critical Control Point) 기록

**요구사항**:
- 모든 CCP 판단 로그 2년 보존
- 로그 변경 불가 (Immutable)
- LOT 추적 100%

**구현**:
```sql
-- CCP 로그 테이블
CREATE TABLE core.ccp_logs (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  lot_number TEXT NOT NULL,
  ccp_name TEXT NOT NULL,  -- 온도, pH, 시간 등
  measured_value NUMERIC NOT NULL,
  threshold_min NUMERIC,
  threshold_max NUMERIC,
  status TEXT NOT NULL,  -- in_control, out_of_control
  corrective_action TEXT,
  recorded_by UUID NOT NULL REFERENCES users(id),
  recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- RLS (수정 방지)
ALTER TABLE core.ccp_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY ccp_logs_append_only ON core.ccp_logs
  FOR ALL
  USING (false)  -- 읽기는 관리자만
  WITH CHECK (true);  -- 쓰기만 허용 (삭제/수정 불가)
```

### 8.2 GDPR / 개인정보보호법 준수

#### 8.2.1 개인정보 처리 원칙

| 원칙 | 구현 |
|------|------|
| **최소 수집** | 필수 필드만 수집 (email, name), 선택 필드 최소화 |
| **목적 외 사용 금지** | 명시된 용도로만 사용, 다른 용도 시 재동의 |
| **보관 기간 제한** | 90일 후 익명화, 2년 후 삭제 |
| **안전한 보관** | AES-256 암호화, 접근 제어 (RBAC) |
| **열람/정정/삭제 권리** | API 제공 (GET /users/me, DELETE /users/me) |

#### 8.2.2 개인정보 삭제 요청 처리

```python
@app.delete("/api/v1/users/me")
@require_permission("user:delete_self")
async def delete_my_account(request: Request):
    """개인정보 삭제 요청"""
    user_id = request.state.user['sub']

    # 1. 개인정보 익명화
    await anonymize_user_data(user_id)

    # 2. 계정 비활성화
    await deactivate_user(user_id)

    # 3. 감사 로그 기록
    await save_audit_log(
        user_id=user_id,
        action_type='delete_account',
        resource_type='user',
        resource_id=user_id
    )

    return {"message": "Account deleted successfully"}

async def anonymize_user_data(user_id: str):
    """개인정보 익명화"""
    await db.execute("""
        UPDATE users
        SET
          email = CONCAT('deleted-', id, '@anonymized.com'),
          name = 'Deleted User',
          phone = NULL,
          deleted_at = NOW()
        WHERE id = :user_id
    """, {'user_id': user_id})

    # 관련 데이터도 익명화 (Judgment 로그는 유지, user_id만 NULL)
    await db.execute("""
        UPDATE judgment_executions
        SET created_by = NULL
        WHERE created_by = :user_id
    """, {'user_id': user_id})
```

---

## 9. 보안 사고 대응

### 9.1 사고 대응 프로세스

```
[탐지] → [분류] → [격리] → [조사] → [복구] → [사후 분석]
```

#### 9.1.1 탐지 (Detection)

**자동 탐지**:
- 비정상 로그인 시도 (5회 연속 실패)
- 권한 에러 급증 (403 에러)
- 데이터 유출 의심 (대량 다운로드)
- SQL Injection 시도 (패턴 매칭)

**알람 발송**: Slack, PagerDuty

#### 9.1.2 분류 및 격리

**심각도 분류**:

| 심각도 | 정의 | 대응 시간 | 예시 |
|--------|------|----------|------|
| **P0 (Critical)** | 데이터 유출, 시스템 침해 | 즉시 (15분) | SQL Injection 성공, 권한 상승 |
| **P1 (High)** | 보안 취약점 발견 | 4시간 | XSS 취약점, 암호화 누락 |
| **P2 (Medium)** | 비정상 활동 탐지 | 24시간 | 비정상 로그인 패턴 |
| **P3 (Low)** | 정책 위반 | 3일 | 약한 비밀번호 사용 |

**격리 조치**:
- 의심 계정 비활성화
- 의심 IP 차단 (WAF/Security Group)
- 영향받은 서비스 격리 (Network Policy)

#### 9.1.3 조사 및 복구

**조사**:
1. 로그 분석 (audit_logs, access_logs, application_logs)
2. 타임라인 재구성
3. 영향 범위 파악 (데이터 유출, 권한 변경)
4. 근본 원인 분석 (RCA)

**복구**:
1. 취약점 패치
2. 비밀번호/키 교체
3. 권한 리셋
4. 데이터 복원 (백업)

#### 9.1.4 사후 분석 (Post-Mortem)

**보고서 작성**:
- 사고 개요 (언제, 무엇, 어떻게)
- 타임라인
- 영향 범위
- 근본 원인
- 복구 조치
- 재발 방지 계획

---

## 결론

본 문서(C-5)는 **AI Factory Decision Engine** 의 보안 및 규제 준수 설계를 상세히 수립하였다.

### 주요 성과
1. **인증/인가**: OAuth 2.0 + JWT, RBAC (6개 역할, 권한 매트릭스)
2. **데이터 보안**: TLS 1.2+, AES-256, PII 마스킹 (5가지 패턴)
3. **네트워크 보안**: VPC 3계층 분리, Security Group, WAF
4. **애플리케이션 보안**: OWASP Top 10 대응, Secure Coding
5. **V7 Intent Router 보안**: 14개 V7 Intent 입력 검증, Claude 모델 토큰 한도 적용
6. **Orchestrator 보안**: Route Target별 노드 접근 제어, 15노드 타입별 보안 등급 (P0/P1/P2)
7. **감사 로깅**: 모든 변경 기록, 2년 보존, 불변성 보장, Legacy Intent 변환 감사
8. **규제 준수**: HACCP/ISO (CCP 로그), GDPR (개인정보 삭제)
9. **사고 대응**: 탐지 → 격리 → 복구 프로세스

### 다음 단계
1. 보안 스캔 도구 설치 (OWASP ZAP, Bandit)
2. 침투 테스트 계획 수립
3. 보안 교육 실시 (Secure Coding)
4. 규제 준수 체크리스트 검증

---

## 문서 이력
| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2025-10-28 | Security Team | 초안 작성 |
| 2.0 | 2025-11-26 | Security Team | Enhanced 버전 (OWASP 대응, PII 마스킹, 사고 대응 추가) |
| 3.0 | 2025-12-16 | Security Team | V7 Intent + Orchestrator 보안 설계 추가: V7 Intent 입력 검증, Claude 모델 PII 마스킹 및 토큰 한도, Orchestrator Plan 권한 검증, 15노드 타입별 보안 정책 (P0/P1/P2), Legacy Intent 변환 감사, 권한 매트릭스 확장 |
