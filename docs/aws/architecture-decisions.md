# AWS 아키텍처 결정 문서 (ADR)
**프로젝트**: TriFlow AI
**작성일**: 2026년 1월 20일
**작성자**: Solution Architecture Team
**버전**: 1.0
**상태**: 초안 (검토 필요)

---

## 📋 Executive Summary

본 문서는 TriFlow AI 프로젝트의 AWS 클라우드 인프라 아키텍처 설계 결정사항을 정리합니다.

**주요 결정**:
- **컴퓨팅**: ECS Fargate (Serverless 컨테이너)
- **데이터베이스**: RDS PostgreSQL db.t4g.medium (Multi-AZ)
- **스토리지**: S3 단일 버킷 (폴더 분리)
- **네트워킹**: Public + Private Subnet (2 AZ)
- **모니터링**: CloudWatch Logs + Prometheus

**예상 월 비용**: ₩313,000 (Reserved Instances 적용 시)

---

## 1️⃣ 컴퓨팅 플랫폼 결정

### 결정: **AWS ECS Fargate**

### 비교 분석

| 항목 | EC2 | ECS Fargate ⭐ | Lambda |
|------|-----|---------------|--------|
| **관리 복잡도** | 높음 (OS 패치, 보안) | 낮음 (Serverless) | 매우 낮음 |
| **Auto Scaling** | 수동 설정 복잡 | 자동 (CPU/Mem 기반) | 자동 (무제한) |
| **고가용성** | 수동 구성 | 기본 제공 | 기본 제공 |
| **비용 (소규모)** | ₩120,000/월 | ₩40,000/월 ⭐ | ₩5,000/월 |
| **비용 (중규모)** | ₩120,000/월 | ₩120,000/월 | ₩50,000/월 |
| **배포 속도** | 5-10분 | 2-3분 ⭐ | 즉시 |
| **Cold Start** | 없음 ⭐ | 없음 ⭐ | 5-10초 ❌ |
| **실행 시간 제한** | 없음 ⭐ | 없음 ⭐ | 15분 ❌ |
| **현재 코드 호환** | 100% ⭐ | 100% ⭐ | 30% (전환 필요) |

### 선택 근거

**ECS Fargate를 선택한 이유**:
1. ✅ **서버 관리 부담 제거**: OS 패치, 보안 업데이트 자동
2. ✅ **Auto Scaling 자동화**: CPU/Memory 기반 자동 확장
3. ✅ **고가용성 기본 제공**: Multi-AZ 배포 자동
4. ✅ **비용 효율**: 소규모 시작 시 EC2보다 66% 저렴
5. ✅ **Dockerfile 재사용**: 현재 Docker 이미지 그대로 사용
6. ✅ **무중단 배포**: Rolling Update 기본 지원

**EC2를 제외한 이유**:
- ❌ 서버 관리 오버헤드 (OS 패치, 보안 업데이트)
- ❌ Auto Scaling 설정 복잡 (Launch Template, ASG, CloudWatch Alarms)
- ❌ 최소 2개 인스턴스 필요 (비용 2배)

**Lambda를 제외한 이유**:
- ❌ FastAPI → Lambda 전환 필요 (Mangum 어댑터, 코드 수정)
- ❌ Cold Start 문제 (첫 요청 5-10초 지연)
- ❌ 15분 실행 시간 제한 (워크플로우 장시간 실행 불가)
- ❌ WebSocket 지원 불가 (API Gateway WebSocket 별도 필요)

### ECS Fargate 사양

| 항목 | 값 | 근거 |
|------|---|------|
| **vCPU** | 1 vCPU | FastAPI 경량, CPU 사용률 ~30% 예상 |
| **Memory** | 2 GB | 현재 Docker 메모리 사용률 ~1.5GB |
| **Task 수 (최소)** | 2 | Multi-AZ 고가용성 (2a, 2c) |
| **Task 수 (최대)** | 5 | 피크 타임 대응 |
| **Auto Scaling 정책** | CPU > 70% → Scale Out | 성능 유지 |
|  | CPU < 30% → Scale In | 비용 절감 |
| **Platform Version** | LATEST | 자동 업데이트 |

### 비용 계산 (ECS Fargate)

```
기본 요금:
- vCPU: $0.04048/시간 × 1 vCPU = $0.04048/시간
- Memory: $0.004445/GB/시간 × 2GB = $0.00889/시간
- 합계: $0.04937/시간 × 730시간 = $36.03/월

Task 2개 상시:
- $36.03 × 2 = $72.06/월
- 환율: ×1,300원 = ₩93,678/월

Auto Scaling (평균 3 tasks):
- $36.03 × 3 = $108.09/월 = ₩140,517/월

최종: ₩93,678 ~ ₩140,517/월 (평균 ₩117,000/월)
```

**절감**: EC2 (₩120,000/월) 대비 거의 동일하지만 관리 부담 ₩0

---

## 2️⃣ 데이터베이스 (RDS) 결정

### 결정: **RDS PostgreSQL 14, db.t4g.medium (Multi-AZ)**

### 비교 분석

| 인스턴스 | vCPU | Memory | 비용/월 (Multi-AZ, RI) | 적합 규모 | 선택 |
|----------|------|--------|----------------------:|----------|:----:|
| db.t4g.micro | 2 | 1GB | ₩100,000 | Dev/Test | ❌ |
| db.t4g.small | 2 | 2GB | ₩160,000 | <100 users | 🟡 |
| **db.t4g.medium** | 2 | 4GB | **₩192,000** | 100~500 users | ✅ |
| db.t4g.large | 2 | 8GB | ₩384,000 | 500~2000 users | ❌ |

### 선택 근거

**db.t4g.medium을 선택한 이유**:
1. ✅ **pgvector 성능**: 4GB 메모리로 벡터 검색 충분 (현재 임베딩 ~1000개)
2. ✅ **확장 여지**: 500명까지 확장 가능 (현재 목표 100명)
3. ✅ **동시 연결**: 최대 100 connections (현재 예상 50개)
4. ✅ **Buffer Pool**: 메모리 여유로 인덱스 캐싱 효율적
5. ✅ **비용 균형**: small 대비 20% 추가 비용으로 2배 성능

**db.t4g.small을 제외한 이유**:
- ❌ pgvector 메모리 부족 위험 (임베딩 증가 시)
- ❌ 6월 납품 시 확장 필요 (업그레이드 다운타임 발생)

**db.t4g.large를 제외한 이유**:
- ❌ 초기 과다 투자 (8GB 중 4GB만 사용 예상)
- ❌ 비용 2배 (₩384,000/월 vs ₩192,000/월)

### RDS 상세 사양

| 항목 | 값 | 근거 |
|------|---|------|
| **Engine** | PostgreSQL 14.10 | pgvector 호환 최신 안정 버전 |
| **Instance Class** | db.t4g.medium | ARM 기반 (성능/가격 최적) |
| **Multi-AZ** | Enabled | 고가용성 (SLA 99.95%) |
| **Storage Type** | gp3 | gp2 대비 20% 저렴, IOPS 조정 가능 |
| **Storage Size** | 100 GB | 초기 데이터 ~10GB, 10배 여유 |
| **IOPS** | 3,000 (기본) | 일반 워크로드 충분 |
| **Throughput** | 125 MiB/s | 기본값 사용 |
| **Auto Scaling** | 200 GB (Max) | 자동 확장 (85% 사용 시) |
| **Backup Retention** | 7 days | 주간 복구 가능 |
| **Backup Window** | 03:00-04:00 KST | 사용량 최소 시간대 |
| **Maintenance Window** | Mon 04:00-05:00 KST | 백업 직후 |
| **Deletion Protection** | Enabled | 실수 삭제 방지 |

### PostgreSQL Extensions

```sql
CREATE EXTENSION IF NOT EXISTS vector;           -- pgvector (임베딩)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";      -- UUID 생성
CREATE EXTENSION IF NOT EXISTS pg_trgm;          -- 텍스트 유사도 검색
CREATE EXTENSION IF NOT EXISTS pg_stat_statements; -- 쿼리 모니터링
```

### 백업 전략

1. **자동 백업** (RDS 기본 기능):
   - 보관 기간: 7일
   - 백업 윈도우: 03:00-04:00 KST (새벽)
   - Point-in-Time Recovery: 5분 단위
   - 비용: 포함 (₩0 추가)

2. **수동 스냅샷** (주간):
   - 매주 일요일 새벽 자동 실행
   - 보관 기간: 30일
   - 비용: 100GB × ₩0.095/GB = ₩9,500/월

3. **재해 복구 (DR)**:
   - RTO (Recovery Time Objective): 4시간
   - RPO (Recovery Point Objective): 5분 (PITR)
   - Cross-Region Replica: 고려 중 (비용 2배)

### 보안 설정

```hcl
# Security Group
ingress {
  from_port       = 5432
  to_port         = 5432
  protocol        = "tcp"
  security_groups = [aws_security_group.ecs.id]  # ECS만 접근
}

# Encryption
storage_encrypted = true  # AES-256 at rest
kms_key_id       = "alias/aws/rds"  # AWS 관리형 키

# Network
publicly_accessible = false  # Private Subnet만
```

### 모니터링

**CloudWatch Logs 활성화**:
- `postgresql` 로그 (에러, 슬로우 쿼리)

**CloudWatch Alarms**:
- CPU > 80% (5분 연속) → Critical
- FreeStorageSpace < 10GB → Critical
- DatabaseConnections > 80 → Warning

---

## 3️⃣ 스토리지 (S3) 결정

### 결정: **단일 S3 버킷 (폴더 분리 방식)**

### 버킷 구조

```
s3://triflow-ai-prod/
├─ tenants/
│  ├─ tenant-{uuid}/
│  │  ├─ workflows/           # 워크플로우 실행 결과
│  │  │  └─ {workflow_id}/
│  │  │     ├─ execution_{timestamp}.json
│  │  │     └─ output_{timestamp}.csv
│  │  ├─ uploads/             # 사용자 업로드 파일
│  │  │  └─ {file_id}.{ext}
│  │  ├─ exports/             # 데이터 내보내기
│  │  │  └─ export_{timestamp}.xlsx
│  │  └─ logs/                # 애플리케이션 로그 (선택)
│  │     └─ {date}/app.log.gz
│  └─ tenant-{uuid}/...
├─ shared/
│  ├─ templates/              # 워크플로우 템플릿
│  ├─ industry-profiles/      # 산업별 프로필
│  └─ system/                 # 시스템 파일
└─ backups/                   # DB 백업 (선택)
   └─ {date}/snapshot.sql.gz
```

### Lifecycle 정책

| Rule | 대상 | 동작 | 이유 |
|------|------|------|------|
| **Archive Old Files** | `*/workflows/*`, `*/exports/*` | 90일 후 Glacier | 장기 보관, 비용 80% 절감 |
| **Delete Logs** | `*/logs/*` | 365일 후 삭제 | 로그는 1년만 보관 |
| **Clean Uploads** | `*/uploads/*` (삭제된 파일만) | 30일 후 삭제 | 임시 파일 정리 |
| **Abort Multipart** | All | 7일 후 정리 | 미완성 업로드 정리 |

**비용 절감 효과**:
- Standard: $0.023/GB/월
- Glacier: $0.004/GB/월 (83% 절감)
- 예상: 50GB → 90일 후 40GB Glacier 이동 → 월 ₩1,500 → ₩500

### Versioning

**전략**: **선택적 Versioning**

- ✅ **Enabled**: `*/workflows/*`, `*/exports/*` (중요 데이터)
- ❌ **Disabled**: `*/uploads/*`, `*/logs/*` (임시 데이터)

**이유**:
- 워크플로우 실행 결과는 감사 목적으로 버전 관리 필요
- 업로드 파일은 덮어쓰기 거의 없음 (비용 절감)

**비용 영향**:
- Versioning 활성화: +20% 스토리지 비용 예상
- 중요 파일만 적용: +5% (₩500 → ₩525/월)

### 암호화

| 항목 | 선택 | 비용 | 이유 |
|------|------|-----:|------|
| **At Rest** | SSE-S3 (AES-256) | ₩0 | 무료, 충분한 보안 |
| **In Transit** | TLS 1.2+ | ₩0 | HTTPS 강제 |
| **KMS 암호화** | 미사용 | ₩5,000/월 | 규제 요구 없음 |

### 권한 관리 (IAM Policy)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::triflow-ai-prod/tenants/${tenant_id}/*"
    },
    {
      "Effect": "Deny",
      "Action": "s3:*",
      "Resource": "arn:aws:s3:::triflow-ai-prod/tenants/*",
      "Condition": {
        "StringNotLike": {
          "s3:prefix": "tenants/${tenant_id}/*"
        }
      }
    }
  ]
}
```

**테넌트 격리**: IAM Policy Variables로 `${tenant_id}` 기반 접근 제어

### 비용 예상

```
스토리지:
- Standard: 10GB × $0.023 = $0.23/월
- Glacier: 40GB × $0.004 = $0.16/월
- 합계: $0.39/월 ≈ ₩507/월

요청:
- PUT: 10,000 req × $0.005/1000 = $0.05/월
- GET: 50,000 req × $0.0004/1000 = $0.02/월
- 합계: $0.07/월 ≈ ₩91/월

총 비용: ₩507 + ₩91 ≈ ₩600/월
```

---

## 4️⃣ 네트워킹 (VPC) 결정

### 결정: **Public + Private Subnet (2 AZ)**

### VPC 설계

```
VPC: triflow-prod-vpc
CIDR: 10.0.0.0/16 (65,536 IPs)

┌────────────────────────────────────────────────────┐
│ VPC: 10.0.0.0/16                                   │
│                                                    │
│ ┌──────────────────┐  ┌──────────────────┐        │
│ │ ap-northeast-2a  │  │ ap-northeast-2c  │        │
│ │                  │  │                  │        │
│ │ Public Subnet    │  │ Public Subnet    │        │
│ │ 10.0.1.0/24      │  │ 10.0.2.0/24      │        │
│ │ - ALB            │  │ - ALB (standby)  │        │
│ │ - NAT Gateway    │  │                  │        │
│ └────────┬─────────┘  └──────────────────┘        │
│          │                                         │
│ ┌────────┴─────────┐  ┌──────────────────┐        │
│ │ Private Subnet   │  │ Private Subnet   │        │
│ │ 10.0.11.0/24     │  │ 10.0.12.0/24     │        │
│ │ - ECS Task 1     │  │ - ECS Task 2     │        │
│ │ - RDS Primary    │  │ - RDS Standby    │        │
│ └──────────────────┘  └──────────────────┘        │
└────────────────────────────────────────────────────┘
```

### Subnet 할당

| Subnet | CIDR | 가용 IP | 용도 |
|--------|------|--------:|------|
| Public-2a | 10.0.1.0/24 | 251 | ALB, NAT Gateway |
| Public-2c | 10.0.2.0/24 | 251 | ALB (standby) |
| Private-2a | 10.0.11.0/24 | 251 | ECS Task, RDS Primary |
| Private-2c | 10.0.12.0/24 | 251 | ECS Task, RDS Standby |

**총 사용 IP 예상**: ~20개 (여유 충분)

### NAT Gateway

**선택**: **Single NAT Gateway** (ap-northeast-2a)

| 항목 | Single NAT | Multi-AZ NAT |
|------|-----------|--------------|
| **비용** | ₩40,000/월 | ₩80,000/월 |
| **고가용성** | ❌ (Single point of failure) | ✅ |
| **Outbound 트래픽** | $0.045/GB | $0.045/GB |

**선택 근거**:
- 초기 비용 절감 (₩40,000/월 절약)
- Outbound 트래픽 적음 (Anthropic API 호출만, 월 <1GB)
- NAT 장애 시 영향: S3/RDS 접근 가능, 외부 API만 불가
- 향후 Multi-AZ로 업그레이드 가능

### Security Groups

#### SG-ALB (Application Load Balancer)
```hcl
ingress {
  from_port   = 443
  to_port     = 443
  protocol    = "tcp"
  cidr_blocks = ["0.0.0.0/0"]  # 전 세계 접근
}

egress {
  from_port       = 8000
  to_port         = 8000
  protocol        = "tcp"
  security_groups = [aws_security_group.ecs.id]
}
```

#### SG-ECS (ECS Tasks)
```hcl
ingress {
  from_port       = 8000
  to_port         = 8000
  protocol        = "tcp"
  security_groups = [aws_security_group.alb.id]  # ALB만
}

egress {
  # RDS 접근
  from_port       = 5432
  to_port         = 5432
  protocol        = "tcp"
  security_groups = [aws_security_group.rds.id]
}

egress {
  # S3, ECR, CloudWatch 접근 (HTTPS)
  from_port   = 443
  to_port     = 443
  protocol    = "tcp"
  cidr_blocks = ["0.0.0.0/0"]
}
```

#### SG-RDS (Database)
```hcl
ingress {
  from_port       = 5432
  to_port         = 5432
  protocol        = "tcp"
  security_groups = [aws_security_group.ecs.id]  # ECS만
}

egress = []  # 아웃바운드 불필요
```

### 비용 계산

```
NAT Gateway:
- 고정 비용: $0.045/시간 × 730시간 = $32.85/월 ≈ ₩42,705/월
- 데이터 처리: 1GB × $0.045 = $0.045/월 ≈ ₩59/월
- 합계: ₩42,764/월

VPC 자체: ₩0 (무료)
Security Groups: ₩0 (무료)

총 비용: ₩42,764/월 (NAT만)
```

---

## 5️⃣ 로드 밸런싱 (ALB) 결정

### 결정: **Application Load Balancer (HTTPS only)**

### ALB 구성

| 항목 | 값 | 근거 |
|------|---|------|
| **Type** | Application | HTTP/HTTPS 라우팅 필요 |
| **Scheme** | Internet-facing | 공개 서비스 |
| **IP Address Type** | IPv4 | IPv6 불필요 |
| **Subnets** | Public-2a, Public-2c | 2 AZ 고가용성 |

### Listeners

#### Listener 1: HTTP → HTTPS Redirect
```hcl
protocol = "HTTP"
port     = 80

default_action {
  type = "redirect"
  redirect {
    protocol    = "HTTPS"
    port        = "443"
    status_code = "HTTP_301"  # Permanent redirect
  }
}
```

#### Listener 2: HTTPS → ECS Target Group
```hcl
protocol        = "HTTPS"
port            = 443
ssl_policy      = "ELBSecurityPolicy-TLS13-1-2-2021-06"
certificate_arn = aws_acm_certificate.triflow.arn

default_action {
  type             = "forward"
  target_group_arn = aws_lb_target_group.ecs.arn
}
```

### Target Group

| 항목 | 값 | 근거 |
|------|---|------|
| **Target Type** | IP | ECS Fargate는 IP 타입 |
| **Protocol** | HTTP | Backend는 HTTP:8000 |
| **VPC** | triflow-prod-vpc | - |
| **Deregistration Delay** | 30초 | 종료 전 연결 대기 |

### Health Check

```hcl
health_check {
  enabled             = true
  path                = "/health"
  protocol            = "HTTP"
  port                = 8000
  interval            = 15  # 15초마다 체크
  timeout             = 5   # 5초 내 응답
  healthy_threshold   = 2   # 2회 성공 → Healthy
  unhealthy_threshold = 3   # 3회 실패 → Unhealthy
  matcher             = "200"  # HTTP 200만 성공
}
```

### Sticky Session (Session Affinity)

**설정**: **Enabled** (Cookie-based)

```hcl
stickiness {
  enabled         = true
  type            = "lb_cookie"
  duration        = 3600  # 1시간
  cookie_name     = "TRIFLOW_LB_COOKIE"
}
```

**이유**:
- Canary Deployment 지원 (같은 사용자 → 같은 버전)
- WebSocket 연결 유지 (향후 고려)
- 세션 기반 캐싱 효율 증가

### SSL/TLS 인증서

**선택**: **AWS Certificate Manager (ACM)**

| 항목 | 값 |
|------|---|
| **CA** | Let's Encrypt (AWS 관리형) |
| **비용** | ₩0 (무료) |
| **갱신** | 자동 (60일 전 자동 갱신) |
| **와일드카드** | Supported (*.triflow-ai.com) |
| **도메인 검증** | DNS (Route 53) |

**SSL 정책**: `ELBSecurityPolicy-TLS13-1-2-2021-06`
- TLS 1.3 ⭐
- TLS 1.2 ⭐
- TLS 1.0/1.1 ❌ (보안 취약)

### Access Logs

**선택**: **비활성화** (초기)

**이유**:
- 초기에는 CloudWatch Logs로 충분
- Access Log는 S3 저장 비용 추가 (₩5,000/월)
- 필요 시 나중에 활성화 (규제 요구 시)

### 비용 계산

```
ALB 고정 비용:
- $0.0225/시간 × 730시간 = $16.43/월 ≈ ₩21,359/월

LCU (Load Balancer Capacity Units):
- 신규 연결: ~10/초 = 0.025 LCU
- 활성 연결: ~50 = 0.1 LCU
- 대역폭: ~10 Mbps = 0.04 LCU
- Rule 평가: ~100/초 = 0.1 LCU
- 합계: 0.265 LCU

LCU 비용:
- 0.265 LCU × $0.008/LCU/시간 × 730시간 = $1.55/월 ≈ ₩2,015/월

총 비용: ₩21,359 + ₩2,015 ≈ ₩23,374/월
```

---

## 6️⃣ 모니터링 및 로깅 결정

### 결정: **CloudWatch Logs + Prometheus Hybrid**

### 로그 수집

**전략**: **CloudWatch Logs** (ECS) + **S3 Archive** (장기 보관)

| Log Source | Destination | Retention | 비용/월 |
|-----------|-------------|-----------|--------:|
| ECS Task Logs | CloudWatch Logs | 15일 | ₩10,000 |
| RDS PostgreSQL | CloudWatch Logs | 7일 | ₩3,000 |
| ALB Access Logs | Disabled | - | ₩0 |
| 15일 이후 로그 | S3 (Glacier) | 1년 | ₩500 |

**CloudWatch Log Groups**:
```
/aws/ecs/triflow-backend     # ECS Task 로그
/aws/rds/instance/triflow    # PostgreSQL 로그
```

### 메트릭 수집

**기본 메트릭** (무료):
```
ECS:
- CPUUtilization (%)
- MemoryUtilization (%)
- RunningTaskCount

RDS:
- CPUUtilization (%)
- DatabaseConnections (count)
- FreeStorageSpace (GB)
- ReadLatency (ms)
- WriteLatency (ms)

ALB:
- RequestCount
- TargetResponseTime (P50, P95, P99)
- HTTPCode_Target_5XX_Count
- HealthyHostCount
```

**커스텀 메트릭** (선택):
```
비용: ₩5,000/월 (100개 메트릭)

예시:
- triflow.api.latency (endpoint별)
- triflow.workflow.execution_time
- triflow.judgment.llm_tokens
- triflow.trust.level_distribution
```

**결정**: **초기에는 기본 메트릭만**, 4-5월에 커스텀 추가

### CloudWatch Alarms

#### Critical Alarms (즉시 대응)

| Alarm | 조건 | 기간 | 채널 |
|-------|------|------|------|
| **RDS CPU High** | CPU > 80% | 5분 연속 | Slack + SMS |
| **RDS Storage Low** | Storage < 10GB | 1분 | Slack + SMS |
| **ECS Memory High** | Memory > 90% | 3분 연속 | Slack |
| **ALB 5xx Errors** | 5xx > 5% of requests | 1분 | Slack + SMS |
| **RDS Connection Spike** | Connections > 80 | 5분 | Slack |

#### Warning Alarms (모니터링)

| Alarm | 조건 | 기간 | 채널 |
|-------|------|------|------|
| **RDS CPU Medium** | CPU > 60% | 10분 연속 | Slack |
| **ECS Task Restart** | Task 재시작 발생 | 즉시 | Slack |
| **ALB Latency High** | P95 > 2초 | 5분 평균 | Slack |

### SNS Topic 구성

```hcl
# SNS Topic
resource "aws_sns_topic" "alarms" {
  name = "triflow-alarms-prod"
}

# Slack Subscription
resource "aws_sns_topic_subscription" "slack" {
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "https"
  endpoint  = "https://hooks.slack.com/services/T.../B.../..."
}

# Email Subscription (Tech Lead)
resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = "tech-lead@company.com"
}
```

### Prometheus 통합 (기존 유지)

**전략**: **Hybrid Monitoring**

```
ECS Task → Prometheus (사이드카)
          ↓
     Grafana Dashboard (기존)
          ↓
     CloudWatch (장기 보관)
```

**이유**:
- 기존 Grafana 대시보드 재사용
- CloudWatch는 알람 + 장기 보관용
- 비용 절감 (Prometheus는 ECS Task 내부)

### 비용 계산

```
CloudWatch Logs:
- Ingestion: 10GB × $0.50 = $5/월 ≈ ₩6,500/월
- Storage (15일): 10GB × $0.03 = $0.3/월 ≈ ₩390/월
- 합계: ₩6,890/월

CloudWatch Alarms:
- 10개 알람 × $0.10 = $1/월 ≈ ₩1,300/월

SNS:
- 1,000 notifications × $0.0005 = $0.5/월 ≈ ₩650/월

총 비용: ₩6,890 + ₩1,300 + ₩650 ≈ ₩8,840/월
```

---

## 💰 총 비용 요약

### 월간 운영 비용 (Reserved Instances 적용)

| 서비스 | 사양 | On-Demand | Reserved (RI) | 절감액 |
|--------|------|----------:|---------------:|-------:|
| **ECS Fargate** | 1 vCPU, 2GB × 2 tasks | ₩93,678 | ₩93,678 | - |
| **RDS PostgreSQL** | db.t4g.medium Multi-AZ | ₩320,000 | ₩192,000 | ₩128,000 |
| **S3** | 50GB (Standard + Glacier) | ₩600 | ₩600 | - |
| **ALB** | 기본 + LCU | ₩23,374 | ₩23,374 | - |
| **NAT Gateway** | Single (2a) | ₩42,764 | ₩42,764 | - |
| **CloudWatch** | Logs + Alarms | ₩8,840 | ₩8,840 | - |
| **데이터 전송** | 10GB/월 | ₩15,000 | ₩15,000 | - |

**월 합계**:
- On-Demand: ₩504,256/월
- **Reserved: ₩376,256/월** ✅
- **절감: ₩128,000/월 (25%)**

### Reserved Instances 선불금

| RI | 타입 | 선불금 (1년) | 월 절감 | ROI |
|----|------|-------------:|--------:|----:|
| RDS | 1년 All Upfront | ₩300,000 | ₩128,000 | 2.3개월 |

**총 선불금**: ₩300,000 (RDS만, ECS는 RI 없음)

### 연간 비용

```
1년 비용 (RI 적용):
- 선불금: ₩300,000 (1회)
- 월 운영: ₩376,256 × 12 = ₩4,515,072
- 합계: ₩4,815,072/년

1년 비용 (On-Demand):
- ₩504,256 × 12 = ₩6,051,072/년

절감: ₩1,236,000/년 (20%)
```

---

## 📐 최종 아키텍처 다이어그램

### High-Level Architecture

```mermaid
graph TB
    User[사용자<br/>Browser/API Client] -->|HTTPS| Route53[Route 53<br/>DNS: triflow-ai.com]
    Route53 -->|HTTPS:443| ALB[Application Load Balancer<br/>Public Subnet]

    subgraph VPC[VPC: 10.0.0.0/16]
        subgraph Public[Public Subnets]
            ALB
            NAT[NAT Gateway<br/>10.0.1.0/24]
        end

        subgraph Private[Private Subnets]
            ECS1[ECS Fargate Task 1<br/>1 vCPU, 2GB<br/>10.0.11.x]
            ECS2[ECS Fargate Task 2<br/>1 vCPU, 2GB<br/>10.0.12.x]

            RDS_Primary[RDS PostgreSQL Primary<br/>db.t4g.medium<br/>10.0.11.x]
            RDS_Standby[RDS PostgreSQL Standby<br/>db.t4g.medium<br/>10.0.12.x]
        end
    end

    ALB -->|HTTP:8000| ECS1
    ALB -->|HTTP:8000| ECS2

    ECS1 -->|SQL:5432| RDS_Primary
    ECS2 -->|SQL:5432| RDS_Primary

    RDS_Primary -.Sync Replication.-> RDS_Standby

    ECS1 -->|HTTPS:443| S3[S3 Bucket<br/>triflow-ai-prod]
    ECS2 -->|HTTPS:443| S3

    ECS1 -.External API.-> NAT
    ECS2 -.External API.-> NAT
    NAT -->|HTTPS| Anthropic[Anthropic API<br/>Claude 3.5]

    ECS1 --> CloudWatch[CloudWatch<br/>Logs + Metrics + Alarms]
    ECS2 --> CloudWatch
    RDS_Primary --> CloudWatch
    ALB --> CloudWatch

    CloudWatch -->|Alerts| SNS[SNS Topic]
    SNS -->|Webhook| Slack[Slack Channel<br/>#triflow-alerts]
    SNS -->|Email| Email[tech-lead@company.com]
```

### Network Topology

```
Region: ap-northeast-2 (Seoul)

┌─────────────────────────────────────────────────────────────┐
│ VPC: triflow-prod-vpc (10.0.0.0/16)                         │
│                                                              │
│  ┌────────────────────────┐  ┌────────────────────────┐     │
│  │ ap-northeast-2a        │  │ ap-northeast-2c        │     │
│  │                        │  │                        │     │
│  │ ┌──────────────────┐   │  │ ┌──────────────────┐   │     │
│  │ │ Public Subnet    │   │  │ │ Public Subnet    │   │     │
│  │ │ 10.0.1.0/24      │   │  │ │ 10.0.2.0/24      │   │     │
│  │ │ ┌──────────────┐ │   │  │ │                  │   │     │
│  │ │ │ ALB          │ │   │  │ │                  │   │     │
│  │ │ │ (Primary)    │ │◄──┼──┼─┤ ALB (Standby)    │   │     │
│  │ │ └──────────────┘ │   │  │ │                  │   │     │
│  │ │ ┌──────────────┐ │   │  │ │                  │   │     │
│  │ │ │ NAT Gateway  │ │   │  │ │                  │   │     │
│  │ │ └──────┬───────┘ │   │  │ │                  │   │     │
│  │ └────────┼─────────┘   │  │ └──────────────────┘   │     │
│  │          │              │  │                        │     │
│  │ ┌────────┴─────────┐   │  │ ┌──────────────────┐   │     │
│  │ │ Private Subnet   │   │  │ │ Private Subnet   │   │     │
│  │ │ 10.0.11.0/24     │   │  │ │ 10.0.12.0/24     │   │     │
│  │ │ ┌──────────────┐ │   │  │ │ ┌──────────────┐ │   │     │
│  │ │ │ ECS Task 1   │ │   │  │ │ │ ECS Task 2   │ │   │     │
│  │ │ │ (Backend)    │ │   │  │ │ │ (Backend)    │ │   │     │
│  │ │ └──────────────┘ │   │  │ │ └──────────────┘ │   │     │
│  │ │ ┌──────────────┐ │   │  │ │ ┌──────────────┐ │   │     │
│  │ │ │ RDS Primary  │ │   │  │ │ │ RDS Standby  │ │   │     │
│  │ │ └──────────────┘ │   │  │ │ └──────────────┘ │   │     │
│  │ └──────────────────┘   │  │ └──────────────────┘   │     │
│  └────────────────────────┘  └────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### 데이터 흐름

```
사용자 요청 흐름:
1. User → Route 53 (DNS 조회)
2. Route 53 → ALB (Public Subnet, 2a or 2c)
3. ALB → ECS Task (Private Subnet, Health Check 통과한 Task)
4. ECS → RDS Primary (SQL 쿼리)
5. ECS → S3 (파일 업로드/다운로드)
6. ECS → Anthropic API (NAT Gateway 경유)
7. ECS → CloudWatch (로그 전송)

장애 복구 흐름:
1. RDS Primary 다운 → Automatic Failover → RDS Standby (2분)
2. ECS Task 다운 → ALB Health Check 실패 → 트래픽 중단 → Auto Scaling 새 Task 시작
3. ALB 다운 → 불가능 (AWS 관리형, 99.99% SLA)
```

---

## 🔧 개발 환경 vs 프로덕션

### 환경 분리 전략

| 항목 | Development | Staging | Production |
|------|------------|---------|-----------|
| **VPC** | 공유 (별도 Subnet) | 별도 VPC | 별도 VPC |
| **RDS** | db.t4g.micro (Single-AZ) | db.t4g.small (Single-AZ) | db.t4g.medium (Multi-AZ) |
| **ECS** | 0.5 vCPU, 1GB × 1 | 1 vCPU, 2GB × 1 | 1 vCPU, 2GB × 2+ |
| **S3** | 공유 버킷 (dev/ 폴더) | 공유 버킷 (staging/ 폴더) | 전용 버킷 |
| **도메인** | dev.triflow-ai.com | staging.triflow-ai.com | triflow-ai.com |

### 비용

```
Development: ₩70,000/월
Staging: ₩120,000/월
Production: ₩376,256/월

총: ₩566,256/월
```

**최적화**:
- Development/Staging은 야간 자동 중단 (Fargate Scale to 0)
- 절감: ₩70,000 + ₩120,000 = ₩190,000/월 → ₩50,000/월
- **최종**: ₩376,256 + ₩50,000 = **₩426,256/월**

---

## 📊 사양 선택 Summary Table

| 결정 항목 | 최종 선택 | 대안 | 선택 이유 |
|----------|-----------|------|-----------|
| **컴퓨팅** | ECS Fargate | EC2, Lambda | 서버리스, Auto Scaling 자동, 관리 부담 최소 |
| **컴퓨팅 사양** | 1 vCPU, 2GB | 0.5/1, 2/4 | 성능/비용 균형, 여유 확보 |
| **Auto Scaling** | Min:2, Max:5 | Min:1, Max:10 | 고가용성 + 비용 제어 |
| **RDS 인스턴스** | db.t4g.medium | small, large | pgvector 성능, 확장 가능 |
| **RDS Multi-AZ** | Enabled | Disabled | SLA 99.95%, 자동 Failover |
| **RDS 스토리지** | gp3 100GB | gp2, 50GB | 20% 저렴, 자동 확장 200GB |
| **S3 버킷 구조** | 단일 버킷 | 테넌트별 | 관리 단순, 비용 효율 |
| **S3 Lifecycle** | 90일 Glacier | 180일, 비활성화 | 비용 80% 절감 |
| **VPC 구성** | Public+Private | Public only | 보안 강화 (RDS Private) |
| **NAT Gateway** | Single | Multi-AZ | 비용 50% 절감 |
| **ALB SSL** | ACM 무료 | 외부 인증서 | 무료, 자동 갱신 |
| **Sticky Session** | Enabled | Disabled | Canary 지원, 세션 유지 |
| **로그 보관** | 15일 | 7일, 30일 | 비용/디버깅 균형 |

---

## 🚀 다음 단계

### Phase 0 남은 작업
1. ✅ 아키텍처 설계 완료 (이 문서)
2. ⏭️ Terraform 코드 작성 (이 문서 기반)
3. ⏭️ AWS SDK 래퍼 구현
4. ⏭️ LocalStack 테스트
5. ⏭️ 배포 스크립트 작성

### 검토 요청 사항

**결정이 필요한 추가 항목**:
- [ ] **ElastiCache Redis**: 즉시 도입? or 4-5월 추가?
  - 비용: ₩50,000/월 (cache.t4g.small)
  - 효과: 세션 저장 고가용성, API 응답 캐싱
  - 권장: **4-5월 추가** (초기 비용 절감)

- [ ] **Route 53**: 도메인 사용? or ALB DNS?
  - 비용: ₩700/월 (Hosted Zone)
  - 필요: 커스텀 도메인 (triflow-ai.com)
  - 권장: **Yes, 필수** (고객사 요구사항)

- [ ] **WAF (Web Application Firewall)**: 도입?
  - 비용: ₩6,000/월 + 요청당 과금
  - 효과: DDoS 방어, SQL Injection 차단
  - 권장: **4-5월 추가** (초기에는 Security Group으로 충분)

---

## 🔖 참고 문서

- [AWS ECS Fargate Pricing](https://aws.amazon.com/fargate/pricing/)
- [AWS RDS PostgreSQL Pricing](https://aws.amazon.com/rds/postgresql/pricing/)
- [AWS VPC Best Practices](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-security-best-practices.html)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)

---

**문서 상태**: ✅ 초안 완성, 팀 리뷰 대기
**다음 작업**: Terraform 코드 작성 (이 문서 기반)
