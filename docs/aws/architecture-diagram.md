# AWS 아키텍처 다이어그램
**프로젝트**: TriFlow AI
**버전**: 1.0
**작성일**: 2026년 1월 20일

---

## High-Level Architecture

```mermaid
graph TB
    User[👤 사용자<br/>웹 브라우저] -->|HTTPS| Route53[🌐 Route 53<br/>DNS: triflow-ai.com]
    Route53 -->|DNS Query| ALB[⚖️ Application Load Balancer<br/>Public Subnet<br/>HTTPS:443]

    subgraph VPC[☁️ VPC: 10.0.0.0/16 ap-northeast-2]
        subgraph PublicSubnet[📡 Public Subnets]
            direction LR
            ALB
            NAT[🚪 NAT Gateway<br/>10.0.1.x<br/>ap-northeast-2a]
        end

        subgraph PrivateSubnet[🔒 Private Subnets]
            direction TB
            ECS1[🐳 ECS Fargate Task 1<br/>1 vCPU, 2GB RAM<br/>10.0.11.x<br/>ap-northeast-2a]
            ECS2[🐳 ECS Fargate Task 2<br/>1 vCPU, 2GB RAM<br/>10.0.12.x<br/>ap-northeast-2c]

            RDS_Primary[(🗄️ RDS PostgreSQL Primary<br/>db.t4g.medium<br/>4GB RAM, 100GB gp3<br/>10.0.11.x<br/>ap-northeast-2a)]
            RDS_Standby[(🗄️ RDS PostgreSQL Standby<br/>db.t4g.medium<br/>4GB RAM, 100GB gp3<br/>10.0.12.x<br/>ap-northeast-2c)]
        end
    end

    ALB -->|HTTP:8000<br/>Health Check /health| ECS1
    ALB -->|HTTP:8000<br/>Health Check /health| ECS2

    ECS1 -->|SQL:5432<br/>pgvector queries| RDS_Primary
    ECS2 -->|SQL:5432<br/>pgvector queries| RDS_Primary

    RDS_Primary -.Synchronous Replication.-> RDS_Standby

    ECS1 -->|HTTPS:443<br/>boto3| S3[🪣 S3 Bucket<br/>triflow-ai-prod<br/>Versioning, Encryption]
    ECS2 -->|HTTPS:443<br/>boto3| S3

    ECS1 -.Anthropic API<br/>Claude 3.5.-> NAT
    ECS2 -.Anthropic API<br/>Claude 3.5.-> NAT
    NAT -->|HTTPS| Internet[🌍 Internet<br/>api.anthropic.com]

    ECS1 -->|Logs + Metrics| CloudWatch[📊 CloudWatch<br/>Logs, Metrics, Alarms]
    ECS2 -->|Logs + Metrics| CloudWatch
    RDS_Primary -->|PostgreSQL Logs| CloudWatch
    ALB -->|Access Logs| CloudWatch

    CloudWatch -->|Alarms| SNS[📢 SNS Topic<br/>triflow-alarms-prod]
    SNS -->|Webhook| Slack[💬 Slack<br/>#triflow-alerts]
    SNS -->|Email| Email[📧 tech-lead@company.com]

    style VPC fill:#e1f5ff
    style PublicSubnet fill:#fff4e6
    style PrivateSubnet fill:#f0f0f0
    style RDS_Primary fill:#4CAF50
    style RDS_Standby fill:#81C784
    style ECS1 fill:#2196F3
    style ECS2 fill:#64B5F6
    style CloudWatch fill:#FF9800
    style S3 fill:#FF5722
```

---

## Network Topology (Detailed)

```mermaid
graph TD
    subgraph Internet[🌍 인터넷]
        Users[사용자들]
        AnthropicAPI[Anthropic API]
    end

    subgraph AWS_Region[AWS Region: ap-northeast-2 Seoul]
        Route53[Route 53 DNS]

        subgraph AZ_2a[Availability Zone: ap-northeast-2a]
            subgraph Public_2a[Public Subnet<br/>10.0.1.0/24]
                ALB_Primary[ALB Primary]
                NAT_2a[NAT Gateway]
            end

            subgraph Private_2a[Private Subnet<br/>10.0.11.0/24]
                ECS_Task_2a[ECS Fargate Task<br/>Backend Container<br/>1 vCPU, 2GB]
                RDS_Primary_2a[(PostgreSQL Primary<br/>db.t4g.medium<br/>Multi-AZ Enabled)]
            end
        end

        subgraph AZ_2c[Availability Zone: ap-northeast-2c]
            subgraph Public_2c[Public Subnet<br/>10.0.2.0/24]
                ALB_Standby[ALB Standby]
            end

            subgraph Private_2c[Private Subnet<br/>10.0.12.0/24]
                ECS_Task_2c[ECS Fargate Task<br/>Backend Container<br/>1 vCPU, 2GB]
                RDS_Standby_2c[(PostgreSQL Standby<br/>db.t4g.medium<br/>Automatic Failover)]
            end
        end

        S3_Bucket[S3: triflow-ai-prod]
        CloudWatch_Service[CloudWatch]
        SNS_Service[SNS]
    end

    Users -->|HTTPS:443| Route53
    Route53 --> ALB_Primary
    Route53 --> ALB_Standby

    ALB_Primary -->|HTTP:8000| ECS_Task_2a
    ALB_Primary -->|HTTP:8000| ECS_Task_2c
    ALB_Standby -->|HTTP:8000| ECS_Task_2a
    ALB_Standby -->|HTTP:8000| ECS_Task_2c

    ECS_Task_2a -->|5432| RDS_Primary_2a
    ECS_Task_2c -->|5432| RDS_Primary_2a

    RDS_Primary_2a -.Sync Replication<br/>DRBD.-> RDS_Standby_2c

    ECS_Task_2a --> S3_Bucket
    ECS_Task_2c --> S3_Bucket

    ECS_Task_2a -.via NAT.-> NAT_2a
    ECS_Task_2c -.via NAT.-> NAT_2a
    NAT_2a --> AnthropicAPI

    ECS_Task_2a --> CloudWatch_Service
    ECS_Task_2c --> CloudWatch_Service
    RDS_Primary_2a --> CloudWatch_Service

    CloudWatch_Service --> SNS_Service
    SNS_Service --> Slack
    SNS_Service --> Email[Email Alerts]

    style AZ_2a fill:#e3f2fd
    style AZ_2c fill:#fff3e0
    style RDS_Primary_2a fill:#4CAF50
    style RDS_Standby_2c fill:#81C784
```

---

## Security Groups Flow

```mermaid
graph LR
    Internet[0.0.0.0/0] -->|HTTPS:443| SG_ALB[SG-ALB]
    SG_ALB -->|HTTP:8000| SG_ECS[SG-ECS]
    SG_ECS -->|PostgreSQL:5432| SG_RDS[SG-RDS]
    SG_ECS -->|HTTPS:443| Internet2[Internet<br/>S3, ECR, Anthropic]

    subgraph SecurityGroups[Security Groups]
        SG_ALB
        SG_ECS
        SG_RDS
    end

    style SG_ALB fill:#FFC107
    style SG_ECS fill:#2196F3
    style SG_RDS fill:#4CAF50
```

**Security Group Rules**:

| Security Group | Direction | Protocol | Port | Source/Destination | Purpose |
|----------------|-----------|----------|------|--------------------|---------|
| **SG-ALB** | Inbound | TCP | 443 | 0.0.0.0/0 | HTTPS from Internet |
| | Outbound | TCP | 8000 | SG-ECS | Forward to Backend |
| **SG-ECS** | Inbound | TCP | 8000 | SG-ALB | Receive from ALB |
| | Outbound | TCP | 5432 | SG-RDS | Database queries |
| | Outbound | TCP | 443 | 0.0.0.0/0 | S3, ECR, Anthropic |
| **SG-RDS** | Inbound | TCP | 5432 | SG-ECS | PostgreSQL connections |
| | Outbound | - | - | None | No outbound needed |

---

## Data Flow Diagrams

### Request Flow (Normal Operation)

```mermaid
sequenceDiagram
    participant User as 👤 사용자
    participant Route53 as Route 53
    participant ALB as ALB
    participant ECS as ECS Fargate
    participant RDS as RDS Primary
    participant S3 as S3 Bucket
    participant Anthropic as Claude API

    User->>Route53: 1. DNS Query (triflow-ai.com)
    Route53-->>User: 2. ALB IP Address
    User->>ALB: 3. HTTPS Request (443)
    ALB->>ECS: 4. HTTP Request (8000)

    alt 워크플로우 실행
        ECS->>RDS: 5a. SQL Query (workflow data)
        RDS-->>ECS: 5b. Query Result
        ECS->>Anthropic: 6a. LLM Request (via NAT)
        Anthropic-->>ECS: 6b. LLM Response
        ECS->>S3: 7a. Upload Result (CSV)
        S3-->>ECS: 7b. S3 URI
    end

    ECS-->>ALB: 8. HTTP Response (200)
    ALB-->>User: 9. HTTPS Response

    ECS->>CloudWatch: 10. Logs + Metrics
```

### Failover Flow (RDS Primary Failure)

```mermaid
sequenceDiagram
    participant ECS as ECS Task
    participant RDS_P as RDS Primary
    participant RDS_S as RDS Standby
    participant Route53 as Route 53 (CNAME)
    participant CloudWatch as CloudWatch

    ECS->>RDS_P: 1. SQL Query
    RDS_P-xECS: 2. Connection Failed ❌

    Note over RDS_P: Primary Failure Detected

    RDS_P->>CloudWatch: 3. Failure Alarm
    CloudWatch->>SNS: 4. Send Alert
    SNS->>Slack: 5. #triflow-alerts

    RDS_S->>RDS_S: 6. Automatic Promotion<br/>(60-120초)

    Note over RDS_S: Standby → Primary

    Route53->>Route53: 7. CNAME Update<br/>RDS Endpoint

    ECS->>RDS_S: 8. Retry Connection<br/>(New Primary)
    RDS_S-->>ECS: 9. Connection Success ✅

    Note over ECS,RDS_S: RTO: 2분 이내
```

---

## Deployment Flow

```mermaid
graph TB
    Developer[개발자<br/>로컬 환경] -->|git push| GitHub[GitHub Repository<br/>main/develop branch]
    GitHub -->|Trigger| GHA[GitHub Actions<br/>deploy-aws.yml]

    GHA -->|1. Build| Docker[Docker Build<br/>backend:$SHA]
    Docker -->|2. Push| ECR[ECR Repository<br/>triflow-backend]

    GHA -->|3. Update| TaskDef[ECS Task Definition<br/>New Revision]
    TaskDef -->|4. Register| ECS_Service[ECS Service<br/>Rolling Update]

    ECS_Service -->|5. Launch| NewTask[New ECS Task<br/>Health Check]
    NewTask -->|6. Health OK?| ALB_Check{ALB Health Check<br/>/health endpoint}

    ALB_Check -->|✅ Healthy| Drain[Old Task Drain<br/>30초 대기]
    ALB_Check -->|❌ Unhealthy| Rollback[Rollback<br/>이전 Task Definition]

    Drain -->|7. Terminate| OldTask[Old Task Terminated]
    OldTask -->|8. Complete| Success[✅ Deployment Success]

    Rollback -->|Notify| Slack_Fail[Slack Alert<br/>배포 실패]

    Success -->|Notify| Slack_Success[Slack Alert<br/>배포 성공]

    style Success fill:#4CAF50
    style Rollback fill:#F44336
    style NewTask fill:#2196F3
```

---

## Auto Scaling Flow

```mermaid
graph TD
    CloudWatch[CloudWatch Metrics] -->|CPU > 70%<br/>3분 연속| Alarm_High[CloudWatch Alarm<br/>Scale Out]
    Alarm_High -->|Trigger| ASG_Out[ECS Auto Scaling<br/>Desired Count +1]
    ASG_Out -->|Launch| NewTask[New ECS Task<br/>Provisioning]
    NewTask -->|Register| ALB_TG[ALB Target Group<br/>Health Check]
    ALB_TG -->|Healthy| Active[Active Task<br/>트래픽 수신]

    CloudWatch2[CloudWatch Metrics] -->|CPU < 30%<br/>10분 연속| Alarm_Low[CloudWatch Alarm<br/>Scale In]
    Alarm_Low -->|Trigger| ASG_In[ECS Auto Scaling<br/>Desired Count -1]
    ASG_In -->|Deregister| OldTask[Old ECS Task<br/>Draining]
    OldTask -->|30초 대기| Terminate[Task Terminated]

    style Active fill:#4CAF50
    style Terminate fill:#9E9E9E
    style NewTask fill:#2196F3
```

**Auto Scaling Policy**:
- **Scale Out**: CPU > 70% for 3분 → Add 1 task (Max: 5)
- **Scale In**: CPU < 30% for 10분 → Remove 1 task (Min: 2)
- **Cooldown**: 5분 (연속 스케일링 방지)

---

## Cost Breakdown (월간)

```mermaid
pie title 월간 AWS 비용 분포 (₩376,256)
    "RDS PostgreSQL (Multi-AZ)" : 192000
    "ECS Fargate (2 Tasks)" : 93678
    "NAT Gateway" : 42764
    "ALB" : 23374
    "CloudWatch" : 8840
    "S3 + Data Transfer" : 15600
```

| 서비스 | 비용/월 | 비율 |
|--------|--------:|-----:|
| RDS PostgreSQL | ₩192,000 | 51% |
| ECS Fargate | ₩93,678 | 25% |
| NAT Gateway | ₩42,764 | 11% |
| ALB | ₩23,374 | 6% |
| CloudWatch | ₩8,840 | 2% |
| S3 + Transfer | ₩15,600 | 4% |
| **총계** | **₩376,256** | 100% |

---

## Monitoring Dashboard Layout

```
┌─────────────────────────────────────────────────────────────┐
│ TriFlow AI - Production Monitoring (Grafana)               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│ │ ECS Tasks   │ │ RDS CPU     │ │ ALB Latency │           │
│ │ 2/5 Running │ │ 45%         │ │ P95: 350ms  │           │
│ │ ✅ Healthy  │ │ ✅ Normal   │ │ ✅ Good     │           │
│ └─────────────┘ └─────────────┘ └─────────────┘           │
│                                                             │
│ ┌───────────────────────────────────────────────────────┐   │
│ │ 📈 API Request Rate (req/sec)                        │   │
│ │ [Graph: Last 6 hours]                                │   │
│ │                    ╱╲                                │   │
│ │           ╱╲      ╱  ╲     ╱╲                        │   │
│ │      ╱╲  ╱  ╲    ╱    ╲   ╱  ╲                       │   │
│ │ ────╱  ╲╱    ╲──╱      ╲─╱    ╲──                    │   │
│ └───────────────────────────────────────────────────────┘   │
│                                                             │
│ ┌──────────────────────┐ ┌──────────────────────────────┐  │
│ │ 🗄️ Database          │ │ 📊 System Resources         │  │
│ │ Connections: 23/100  │ │ CPU: 45% (Target: <70%)     │  │
│ │ QPS: 450             │ │ Memory: 1.2GB/2GB (60%)     │  │
│ │ Latency: 12ms        │ │ Disk: 15GB/100GB (15%)      │  │
│ └──────────────────────┘ └──────────────────────────────┘  │
│                                                             │
│ ┌───────────────────────────────────────────────────────┐   │
│ │ 🚨 Recent Alarms (Last 24h)                          │   │
│ │ [No active alarms] ✅                                │   │
│ └───────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Backup & Recovery Strategy

```mermaid
graph TB
    subgraph Production[Production Database]
        RDS_Prod[(RDS Primary<br/>Live Data)]
    end

    subgraph AutoBackup[Automated Backups]
        Daily[Daily Automated Backup<br/>03:00-04:00 KST<br/>7-day retention]
        PITR[Point-in-Time Recovery<br/>5분 단위<br/>7일 이내]
    end

    subgraph ManualBackup[Manual Backups]
        Weekly[Weekly Snapshot<br/>Every Sunday 03:00<br/>30-day retention]
    end

    subgraph Recovery[Recovery Options]
        Restore_PITR[PITR Restore<br/>RPO: 5분<br/>RTO: 1시간]
        Restore_Snapshot[Snapshot Restore<br/>RPO: 1주<br/>RTO: 30분]
    end

    RDS_Prod -->|자동| Daily
    RDS_Prod -->|자동| PITR
    RDS_Prod -->|수동| Weekly

    Daily -.복구 가능.-> Restore_PITR
    PITR -.복구 가능.-> Restore_PITR
    Weekly -.복구 가능.-> Restore_Snapshot

    Restore_PITR -->|New Instance| RDS_New[(Restored RDS<br/>새 인스턴스)]
    Restore_Snapshot -->|New Instance| RDS_New

    style Daily fill:#4CAF50
    style PITR fill:#81C784
    style Weekly fill:#FFC107
    style Restore_PITR fill:#2196F3
    style Restore_Snapshot fill:#64B5F6
```

**Backup Schedule**:
- 자동 백업: 매일 03:00-04:00 KST (7일 보관)
- 수동 스냅샷: 매주 일요일 03:00 (30일 보관)
- PITR: 7일 이내 5분 단위 복구 가능

**Recovery Scenarios**:
1. 데이터 손상 (실수로 삭제): PITR로 5분 전 복구
2. 주간 백업 필요: Snapshot으로 복구
3. 재해 복구: Multi-AZ Failover (자동, 2분)

---

## S3 Bucket Structure

```
s3://triflow-ai-prod/
│
├─ tenants/
│  ├─ {tenant-uuid-A}/
│  │  ├─ workflows/
│  │  │  ├─ {workflow-id-1}/
│  │  │  │  ├─ execution_20260120_143022.json
│  │  │  │  ├─ output_20260120_143022.csv
│  │  │  │  └─ logs_20260120_143022.txt
│  │  │  └─ {workflow-id-2}/...
│  │  ├─ uploads/
│  │  │  ├─ {file-uuid}.xlsx
│  │  │  └─ {file-uuid}.pdf
│  │  └─ exports/
│  │     ├─ export_20260120.xlsx
│  │     └─ export_20260119.csv
│  │
│  └─ {tenant-uuid-B}/
│     └─ (동일 구조)
│
├─ shared/
│  ├─ templates/
│  │  ├─ workflow_template_defect_detection.json
│  │  └─ workflow_template_quality_check.json
│  ├─ industry-profiles/
│  │  ├─ pharma.json
│  │  ├─ food.json
│  │  └─ electronics.json
│  └─ system/
│     └─ config.json
│
└─ backups/ (선택사항)
   └─ db/
      ├─ manual_snapshot_20260120.sql.gz
      └─ manual_snapshot_20260113.sql.gz
```

**Lifecycle Rules**:
```
Rule 1: workflows/* → 90일 후 Glacier (80% 비용 절감)
Rule 2: uploads/* → 180일 후 Glacier
Rule 3: exports/* → 90일 후 Glacier
Rule 4: backups/* → 30일 후 삭제
```

---

## IAM Roles & Policies

```mermaid
graph TD
    subgraph ECS_Task_Role[ECS Task Execution Role]
        ECS_Pull[ECR Pull Images]
        ECS_Logs[CloudWatch Logs Write]
    end

    subgraph ECS_App_Role[ECS Task Role]
        S3_Access[S3 Read/Write<br/>tenants/{tenant_id}/*]
        RDS_Connect[RDS Connect<br/>IAM Auth]
        Secrets_Read[Secrets Manager Read<br/>triflow/prod/*]
        CW_Metrics[CloudWatch PutMetrics]
    end

    subgraph RDS_Monitoring[RDS Enhanced Monitoring]
        RDS_CW[CloudWatch Logs Write<br/>PostgreSQL Logs]
    end

    ECS_Task[ECS Fargate Task] --> ECS_Task_Role
    ECS_Task --> ECS_App_Role
    RDS[RDS Instance] --> RDS_Monitoring

    style ECS_Task_Role fill:#2196F3
    style ECS_App_Role fill:#4CAF50
    style RDS_Monitoring fill:#FF9800
```

**IAM Policy Example (S3 Access)**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::triflow-ai-prod/tenants/${aws:userid}/*",
        "arn:aws:s3:::triflow-ai-prod/shared/*"
      ]
    }
  ]
}
```

**최소 권한 원칙**:
- ECS Task는 자신의 테넌트 폴더만 접근
- Secrets Manager는 Read-Only
- CloudWatch는 Write-Only (Logs, Metrics)

---

## 확장 계획 (4-5월)

### ElastiCache Redis 추가 (선택사항)

```mermaid
graph TB
    ALB[ALB] --> ECS1[ECS Task 1]
    ALB --> ECS2[ECS Task 2]

    ECS1 --> Redis_Primary[ElastiCache Redis Primary<br/>cache.t4g.small<br/>2GB]
    ECS2 --> Redis_Primary

    Redis_Primary -.Async Replication.-> Redis_Replica[ElastiCache Redis Replica<br/>cache.t4g.small<br/>2GB<br/>Read-Only]

    ECS1 --> RDS[RDS Primary]
    ECS2 --> RDS

    style Redis_Primary fill:#E91E63
    style Redis_Replica fill:#F06292
```

**추가 비용**: ₩50,000/월 (cache.t4g.small × 2)

**효과**:
- 세션 저장 고가용성 (현재: 메모리, 재시작 시 손실)
- API 응답 캐싱 (RDS 부하 감소)
- 워크플로우 실행 결과 캐싱

---

## 참고: AWS 리전 선택 근거

**선택**: **ap-northeast-2 (Seoul)**

| 리전 | Latency (한국) | 비용 | 서비스 가용성 | 선택 |
|------|---------------:|------|--------------|:----:|
| ap-northeast-2 (Seoul) | 5-10ms | 100% | Full | ✅ |
| ap-northeast-1 (Tokyo) | 30-40ms | 95% | Full | ❌ |
| us-west-2 (Oregon) | 150-200ms | 80% | Full | ❌ |

**이유**:
- 사용자 대부분 한국 (Latency 최소화)
- 데이터 주권 (한국 법규 준수)
- AWS Direct Connect 서울 가능

---

**문서 버전**: 1.0 (2026-01-20)
**다음 업데이트**: Terraform 코드 완성 후
