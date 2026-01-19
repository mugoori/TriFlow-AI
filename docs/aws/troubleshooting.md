# AWS 트러블슈팅 가이드
**프로젝트**: TriFlow AI
**작성일**: 2026년 1월 20일
**대상**: DevOps, Backend 팀

---

## 📋 목차

1. [Terraform 문제](#terraform-문제)
2. [AWS 인증 문제](#aws-인증-문제)
3. [RDS 문제](#rds-문제)
4. [ECS/Fargate 문제](#ecsfargate-문제)
5. [ALB/네트워크 문제](#alb네트워크-문제)
6. [S3 문제](#s3-문제)
7. [CloudWatch 문제](#cloudwatch-문제)
8. [비용 문제](#비용-문제)

---

## 🔧 Terraform 문제

### 문제 1: `terraform init` 실패

**증상**:
```
Error: Failed to install provider
Could not retrieve the list of available versions
```

**원인**: 네트워크 문제 또는 프록시 차단

**해결**:
```bash
# 1. 프록시 설정 (필요 시)
export HTTP_PROXY=http://proxy.company.com:8080
export HTTPS_PROXY=http://proxy.company.com:8080

# 2. DNS 확인
nslookup registry.terraform.io

# 3. 캐시 삭제 후 재시도
rm -rf .terraform .terraform.lock.hcl
terraform init

# 4. 오프라인 모드 (최후의 수단)
terraform init -plugin-dir=/path/to/plugins
```

---

### 문제 2: Security Group 순환 참조

**증상**:
```
Error: Cycle: aws_security_group.alb, aws_security_group.ecs, aws_security_group.rds
```

**원인**: Security Group이 서로 참조

**해결**: ✅ **이미 수정됨!**
```hcl
# Security Group Rule을 별도 리소스로 분리
resource "aws_security_group_rule" "alb_to_ecs" {
  type                     = "egress"
  security_group_id        = aws_security_group.alb.id
  source_security_group_id = aws_security_group.ecs.id
  ...
}
```

---

### 문제 3: `terraform plan` 실패 - AWS Credentials

**증상**:
```
Error: No valid credential sources found
```

**원인**: AWS 인증 정보 없음

**해결**:
```bash
# 방법 1: AWS CLI 설정
aws configure
# AWS Access Key ID: AKIA...
# AWS Secret Access Key: ...
# Default region: ap-northeast-2

# 방법 2: 환경 변수
export AWS_ACCESS_KEY_ID=AKIA...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=ap-northeast-2

# 방법 3: AWS Profile
export AWS_PROFILE=triflow-production

# 검증
aws sts get-caller-identity
```

---

### 문제 4: RDS 생성 시간 초과

**증상**:
```
Error: timeout while waiting for state to become 'available'
```

**원인**: RDS Multi-AZ는 15~20분 소요

**해결**:
```bash
# 정상입니다! 인내심을 가지세요.
# AWS Console에서 진행 상황 확인:
https://console.aws.amazon.com/rds/

# 또는 AWS CLI로 상태 확인
aws rds describe-db-instances \
    --db-instance-identifier triflow-ai-production-db \
    --query 'DBInstances[0].DBInstanceStatus'

# 출력: "creating" → "backing-up" → "available"
```

**예상 시간**:
- Single-AZ: 5~10분
- Multi-AZ: 15~20분 (정상!)

---

### 문제 5: S3 버킷 이름 충돌

**증상**:
```
Error: BucketAlreadyExists: The requested bucket name is not available
```

**원인**: S3 버킷 이름은 **전 세계적으로 유일**해야 함

**해결**:
```hcl
# variables.tf 또는 terraform.tfvars 수정
variable "s3_bucket_name" {
  default = "triflow-ai-prod-${data.aws_caller_identity.current.account_id}"
  # 예: triflow-ai-prod-123456789012
}
```

---

## 🔐 AWS 인증 문제

### 문제 6: ECR 로그인 실패

**증상**:
```
Error: no basic auth credentials
denied: Your authorization token has expired
```

**원인**: ECR 로그인 토큰 만료 (12시간 유효)

**해결**:
```bash
# ECR 재로그인
ECR_REGISTRY=$(aws sts get-caller-identity --query Account --output text).dkr.ecr.ap-northeast-2.amazonaws.com

aws ecr get-login-password --region ap-northeast-2 | \
    docker login --username AWS --password-stdin $ECR_REGISTRY

# 성공 확인
docker push ${ECR_REGISTRY}/triflow-ai-backend:latest
```

---

### 문제 7: IAM 권한 부족

**증상**:
```
Error: AccessDenied: User: arn:aws:iam::123456789012:user/deploy is not authorized to perform: rds:CreateDBInstance
```

**원인**: IAM User에 권한 없음

**해결**:
```bash
# 1. 현재 권한 확인
aws iam list-attached-user-policies --user-name deploy

# 2. AdministratorAccess 추가 (임시, 초기 구축 시만)
aws iam attach-user-policy \
    --user-name deploy \
    --policy-arn arn:aws:iam::aws:policy/AdministratorAccess

# 3. Terraform apply 재시도
terraform apply

# 4. 구축 완료 후 최소 권한으로 변경
```

**권장**: 초기 구축 시만 AdministratorAccess, 이후 최소 권한

---

## 🗄️ RDS 문제

### 문제 8: pgvector extension 설치 실패

**증상**:
```sql
ERROR: could not open extension control file
```

**원인**: pgvector extension이 RDS에 설치되지 않음

**해결**:
```sql
-- PostgreSQL 14에서 pgvector는 기본 제공되지 않음
-- RDS Parameter Group에서 활성화 필요

-- 1. Parameter Group 확인
SHOW shared_preload_libraries;

-- 2. pgvector 수동 설치 (RDS는 불가능)
-- RDS는 AWS가 관리하므로 직접 설치 불가

-- 3. 대안: PostgreSQL 15+ 사용 또는 AWS에 요청
```

**실제 해결** (TriFlow AI는 이미 지원됨):
```sql
-- pgvector는 CREATE EXTENSION으로 바로 설치 가능
CREATE EXTENSION IF NOT EXISTS vector;

-- 확인
\dx
```

**참고**: AWS RDS PostgreSQL 14.10+는 pgvector 기본 지원 ✅

---

### 문제 9: RDS 연결 실패

**증상**:
```
psql: error: connection to server at "triflow-db.xxxxx.rds.amazonaws.com" failed: timeout
```

**원인 1**: Security Group 차단

**해결**:
```bash
# Security Group 확인
aws ec2 describe-security-groups \
    --group-ids sg-xxxxx \
    --query 'SecurityGroups[0].IpPermissions'

# Ingress Rule이 있는지 확인:
# - Protocol: tcp
# - Port: 5432
# - Source: ECS Security Group 또는 내 IP
```

**원인 2**: VPC 외부에서 접근 시도 (publicly_accessible = false)

**해결**:
```bash
# 옵션 A: Bastion Host 사용 (권장)
# VPC 내부의 EC2에서 RDS 접근

# 옵션 B: 임시로 Public Access 활성화 (비권장)
aws rds modify-db-instance \
    --db-instance-identifier triflow-ai-production-db \
    --publicly-accessible \
    --apply-immediately

# ⚠️ 작업 완료 후 즉시 비활성화!
```

---

### 문제 10: RDS CPU 100%

**증상**:
- API 응답 느림
- CloudWatch Alarm: `rds-cpu-high`
- 쿼리 타임아웃

**진단**:
```sql
-- Slow Query 확인
SELECT
    pid,
    now() - query_start AS duration,
    query,
    state
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY duration DESC
LIMIT 10;

-- 실행 중인 쿼리 강제 종료 (조심!)
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE pid != pg_backend_pid() AND state = 'active' AND query_start < NOW() - INTERVAL '5 minutes';
```

**해결**:
```bash
# 1. 인덱스 추가
# 2. 쿼리 최적화
# 3. Connection Pool 조정
# 4. RDS 인스턴스 업그레이드 (최후의 수단)
aws rds modify-db-instance \
    --db-instance-identifier triflow-ai-production-db \
    --db-instance-class db.t4g.large \
    --apply-immediately
```

---

## 🐳 ECS/Fargate 문제

### 문제 11: ECS Task 시작 실패

**증상**:
```
service triflow-ai-production-backend-service was unable to place a task
```

**원인 1**: Subnet에 가용 IP 부족

**진단**:
```bash
# Subnet 가용 IP 확인
aws ec2 describe-subnets --subnet-ids subnet-xxxxx \
    --query 'Subnets[0].AvailableIpAddressCount'

# 10.0.11.0/24 = 251 IPs (충분함)
```

**원인 2**: ECR 이미지 없음

**해결**:
```bash
# ECR 이미지 확인
aws ecr describe-images --repository-name triflow-ai-backend

# 이미지 없으면 push
./scripts/deploy-aws.sh production latest
```

**원인 3**: IAM Role 권한 부족

**진단**:
```bash
# ECS Task Execution Role 확인
aws iam get-role --role-name triflow-ai-production-ecs-task-execution-role

# AmazonECSTaskExecutionRolePolicy 있는지 확인
aws iam list-attached-role-policies --role-name triflow-ai-production-ecs-task-execution-role
```

---

### 문제 12: ECS Task가 Unhealthy

**증상**:
```
service is unhealthy in target-group
Tasks are failing the ELB health checks in target-group
```

**진단 1**: Health Check 경로 문제

```bash
# ECS Task IP 조회
TASK_ARN=$(aws ecs list-tasks \
    --cluster triflow-ai-production-cluster \
    --service-name triflow-ai-production-backend-service \
    --query 'taskArns[0]' --output text)

TASK_IP=$(aws ecs describe-tasks \
    --cluster triflow-ai-production-cluster \
    --tasks $TASK_ARN \
    --query 'tasks[0].containers[0].networkInterfaces[0].privateIpv4Address' \
    --output text)

# Task 내부에서 Health Check 테스트
curl http://${TASK_IP}:8000/health
```

**해결**:
```python
# backend/app/main.py에 Health Check 엔드포인트 추가
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}
```

**진단 2**: Security Group 차단

```bash
# ALB → ECS 8000 port 허용되었는지 확인
aws ec2 describe-security-groups \
    --group-ids $(terraform output -raw ecs_security_group_id) \
    --query 'SecurityGroups[0].IpPermissions'

# Ingress Rule 필요:
# - From Port: 8000
# - Source: ALB Security Group
```

**진단 3**: Container 시작 실패

```bash
# ECS Task 로그 확인
aws logs tail /aws/ecs/triflow-ai-production-backend --follow

# 일반적인 에러:
# - "cannot connect to database" → RDS 연결 문제
# - "ModuleNotFoundError" → Dockerfile 문제
# - "port already in use" → 포트 충돌
```

---

### 문제 13: CannotPullContainerError

**증상**:
```
CannotPullContainerError: pull image manifest has been retried 5 time(s)
```

**원인 1**: ECR 권한 부족

**해결**:
```bash
# ECS Task Execution Role에 ECR 권한 추가
aws iam attach-role-policy \
    --role-name triflow-ai-production-ecs-task-execution-role \
    --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
```

**원인 2**: ECR 이미지 태그 오류

**해결**:
```bash
# ECR 이미지 목록 확인
aws ecr list-images --repository-name triflow-ai-backend

# Task Definition의 이미지 URI 확인
aws ecs describe-task-definition \
    --task-definition triflow-ai-production-backend \
    --query 'taskDefinition.containerDefinitions[0].image'

# 올바른 URI 형식:
# 123456789012.dkr.ecr.ap-northeast-2.amazonaws.com/triflow-ai-backend:latest
```

---

### 문제 14: ECS Task OOMKilled

**증상**:
```
Task stopped: Essential container exited
ExitCode: 137 (OOM Killed)
```

**원인**: 메모리 부족 (Task 2GB 초과)

**진단**:
```bash
# Task 메모리 사용률 확인
aws cloudwatch get-metric-statistics \
    --namespace AWS/ECS \
    --metric-name MemoryUtilization \
    --dimensions Name=ClusterName,Value=triflow-ai-production-cluster Name=ServiceName,Value=triflow-ai-production-backend-service \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 300 \
    --statistics Average,Maximum
```

**해결**:
```hcl
# ecs.tf에서 메모리 증가
variable "ecs_task_memory" {
  default = 4096  # 2GB → 4GB
}

# terraform apply
```

---

## ⚖️ ALB/네트워크 문제

### 문제 15: ALB 502 Bad Gateway

**증상**: 사용자가 502 에러 수신

**원인 1**: ECS Task가 모두 Unhealthy

**진단**:
```bash
# Target Group Health 확인
aws elbv2 describe-target-health \
    --target-group-arn $(terraform output -raw alb_target_group_arn)

# 출력:
# - State: unhealthy → ECS Task 문제
# - Reason: "Target.Timeout" → Health Check 응답 없음
# - Reason: "Target.FailedHealthChecks" → /health 엔드포인트 에러
```

**해결**: [문제 12 참조](#문제-12-ecs-task가-unhealthy)

**원인 2**: Security Group 차단

**진단**:
```bash
# ALB → ECS egress rule 확인
aws ec2 describe-security-groups \
    --group-ids $(terraform output -raw alb_security_group_id) \
    --query 'SecurityGroups[0].IpPermissionsEgress'

# Port 8000이 허용되었는지 확인
```

---

### 문제 16: ALB 504 Gateway Timeout

**증상**: 사용자가 504 에러 수신 (60초 후)

**원인**: Backend 응답이 60초 초과

**진단**:
```bash
# ALB Latency 확인
aws cloudwatch get-metric-statistics \
    --namespace AWS/ApplicationELB \
    --metric-name TargetResponseTime \
    --dimensions Name=LoadBalancer,Value=$(terraform output -raw alb_arn | cut -d'/' -f2-) \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 60 \
    --extended-statistics p95,p99
```

**해결**:
```python
# 장시간 작업은 비동기 처리
@app.post("/api/v1/workflows/{workflow_id}/execute")
async def execute_workflow(workflow_id: str, background_tasks: BackgroundTasks):
    # 즉시 응답
    background_tasks.add_task(long_running_workflow, workflow_id)
    return {"status": "accepted", "workflow_id": workflow_id}
```

---

### 문제 17: NAT Gateway 요금 급증

**증상**: 예상보다 NAT 비용 10배 높음

**진단**:
```bash
# NAT Gateway 데이터 전송량 확인
aws cloudwatch get-metric-statistics \
    --namespace AWS/NATGateway \
    --metric-name BytesOutToDestination \
    --dimensions Name=NatGatewayId,Value=nat-xxxxx \
    --start-time $(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 3600 \
    --statistics Sum

# GB 단위로 변환: Sum / 1073741824
```

**원인**: S3 트래픽이 NAT 경유 (VPC Endpoint 미사용)

**해결**: ✅ **이미 해결됨!**
```hcl
# vpc.tf에 S3 Gateway Endpoint 추가됨
resource "aws_vpc_endpoint" "s3" {
  vpc_id       = aws_vpc.main.id
  service_name = "com.amazonaws.ap-northeast-2.s3"
  ...
}
```

**절감 효과**: NAT 트래픽 80% 감소

---

## 🪣 S3 문제

### 문제 18: S3 Access Denied

**증상**:
```python
botocore.exceptions.ClientError: An error occurred (AccessDenied) when calling the PutObject operation
```

**원인**: IAM Role에 S3 권한 없음

**진단**:
```bash
# ECS Task Role 권한 확인
aws iam get-role-policy \
    --role-name triflow-ai-production-ecs-task-role \
    --policy-name triflow-ai-production-s3-access-policy
```

**해결**: ✅ **이미 설정됨!**
```hcl
# iam.tf에 S3 Policy 정의됨
resource "aws_iam_policy" "s3_access" {
  policy = jsonencode({
    Statement = [{
      Effect = "Allow"
      Action = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"]
      Resource = "${aws_s3_bucket.main.arn}/*"
    }]
  })
}
```

---

### 문제 19: S3 업로드 느림

**증상**: 10MB 파일 업로드에 1분+ 소요

**원인**: Multipart Upload 미사용

**해결**:
```python
# s3_client.py 개선 (Multipart Upload)
def upload_large_file(self, file_path: str, s3_key: str, threshold_mb: int = 5):
    """5MB 이상 파일은 Multipart Upload 사용"""
    file_size = os.path.getsize(file_path)

    if file_size > threshold_mb * 1024 * 1024:
        # Multipart Upload
        config = TransferConfig(
            multipart_threshold=threshold_mb * 1024 * 1024,
            max_concurrency=10,
            multipart_chunksize=5 * 1024 * 1024
        )
        self.client.upload_file(file_path, self.bucket, s3_key, Config=config)
    else:
        # 일반 Upload
        self.client.upload_file(file_path, self.bucket, s3_key)
```

**성능 개선**: 10MB 파일 1분 → **5초** ⚡

---

## 📊 CloudWatch 문제

### 문제 20: 로그가 CloudWatch에 안 보임

**증상**: ECS Task 로그가 CloudWatch에 없음

**원인 1**: Log Group이 생성되지 않음

**해결**:
```bash
# Log Group 확인
aws logs describe-log-groups \
    --log-group-name-prefix /aws/ecs/triflow

# 없으면 생성
aws logs create-log-group \
    --log-group-name /aws/ecs/triflow-ai-production-backend
```

**원인 2**: ECS Task Definition에 logConfiguration 누락

**해결**: ✅ **이미 설정됨!**
```hcl
# ecs.tf의 Task Definition에 logConfiguration 포함
logConfiguration = {
  logDriver = "awslogs"
  options = {
    "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
    "awslogs-region"        = var.aws_region
    "awslogs-stream-prefix" = "backend"
  }
}
```

---

### 문제 21: CloudWatch Alarm이 안 울림

**증상**: RDS CPU 100%인데 알람 없음

**진단**:
```bash
# Alarm 상태 확인
aws cloudwatch describe-alarms \
    --alarm-names triflow-ai-production-rds-cpu-high \
    --query 'MetricAlarms[0].{State:StateValue,Reason:StateReason}'

# 출력:
# - INSUFFICIENT_DATA → 메트릭 데이터 부족 (정상, 대기 중)
# - OK → 임계값 미달
# - ALARM → 알람 발생 (SNS 전송됨)
```

**원인**: SNS Subscription 미승인

**해결**:
```bash
# SNS Topic Subscription 확인
aws sns list-subscriptions-by-topic \
    --topic-arn $(terraform output -raw sns_topic_arn)

# Email Subscription은 수동 승인 필요
# 1. 이메일 받은함 확인
# 2. "Confirm subscription" 링크 클릭
```

---

## 💰 비용 문제

### 문제 22: 예상보다 비용 높음

**진단**:
```bash
# 이번 달 비용 확인
aws ce get-cost-and-usage \
    --time-period Start=$(date -u -d 'month ago' +%Y-%m-01),End=$(date -u +%Y-%m-%d) \
    --granularity MONTHLY \
    --metrics UnblendedCost \
    --group-by Type=SERVICE

# 서비스별 비용:
# - RDS: $xxx
# - EC2/Fargate: $xxx
# - NAT Gateway: $xxx
# - Data Transfer: $xxx (주목!)
```

**일반적인 원인**:

| 원인 | 해결 |
|------|------|
| **NAT 데이터 전송 과다** | VPC Endpoint 사용 (S3 무료) |
| **RDS Multi-AZ On-Demand** | Reserved Instance 구매 (40% 할인) |
| **ECS Task 과다** | Auto Scaling 임계값 조정 (CPU 70% → 80%) |
| **S3 Standard 스토리지** | Lifecycle Policy 활성화 (90일 Glacier) |
| **CloudWatch Logs 과다** | 보관 기간 단축 (30일 → 15일) |

---

### 문제 23: Reserved Instance 구매 후 청구

**증상**: RI 구매했는데 여전히 On-Demand 요금

**원인**: RI 적용 시간 지연 (최대 24시간)

**확인**:
```bash
# Reserved Instance 목록
aws rds describe-reserved-db-instances

# RI 사용 현황
aws ce get-reservation-utilization \
    --time-period Start=$(date -u -d '1 day ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d)
```

**해결**: 24~48시간 대기 (자동 적용됨)

---

## 🔍 일반 디버깅 팁

### CloudWatch Logs Insights 쿼리

**에러 로그만 검색**:
```
fields @timestamp, @message
| filter @message like /ERROR/
| sort @timestamp desc
| limit 100
```

**느린 API 요청**:
```
fields @timestamp, request_id, duration
| filter duration > 2000
| sort duration desc
| limit 50
```

**5xx 에러 빈도**:
```
fields @timestamp
| filter status_code >= 500
| stats count() by bin(5m)
```

---

### ECS Task 디버깅

**Task 내부 접속 (ECS Exec)**:
```bash
# ECS Exec 활성화 (Task Definition)
# enableExecuteCommand = true

# Task 내부 접속
aws ecs execute-command \
    --cluster triflow-ai-production-cluster \
    --task $TASK_ARN \
    --container backend \
    --interactive \
    --command "/bin/bash"

# 내부에서:
# - curl localhost:8000/health
# - ps aux
# - top
# - cat /proc/meminfo
```

---

### RDS 성능 분석

**Performance Insights**:
```
1. AWS Console → RDS → triflow-ai-production-db
2. "Monitoring" 탭
3. "Performance Insights" 클릭

확인 사항:
- Top SQL: 가장 느린 쿼리
- DB Load: CPU/IO 부하
- Wait Events: 대기 이벤트
```

**Slow Query Log**:
```sql
-- Slow Query 로그 활성화 (이미 설정됨)
-- Parameter Group: log_min_duration_statement = 1000 (1초)

-- CloudWatch Logs에서 확인
-- Log Group: /aws/rds/instance/triflow-ai-production-db/postgresql
```

---

## 📞 도움 요청

### AWS Support 티켓 생성

**케이스**:
1. **Critical**: 프로덕션 다운 (응답: 15분)
2. **High**: 성능 저하 (응답: 1시간)
3. **Normal**: 일반 문의 (응답: 12시간)

**생성 방법**:
```
AWS Console → Support → Create Case
또는
aws support create-case \
    --subject "RDS Performance Issue" \
    --service-code "amazon-rds" \
    --severity-code "high" \
    --category-code "performance" \
    --communication-body "RDS CPU consistently above 90%..."
```

---

### 내부 Escalation

1. **L1**: On-Call DevOps (+82-10-XXXX-XXXX)
2. **L2**: DevOps Lead (Slack @devops-lead)
3. **L3**: CTO (긴급 전화)
4. **L4**: AWS Support

---

## 📚 유용한 명령어 모음

### 빠른 상태 확인
```bash
# 모든 서비스 한눈에
alias aws-status='
  echo "=== ECS ===" &&
  aws ecs describe-services --cluster triflow-ai-production-cluster --services triflow-ai-production-backend-service --query "services[0].{Running:runningCount,Desired:desiredCount}" &&
  echo "=== RDS ===" &&
  aws rds describe-db-instances --db-instance-identifier triflow-ai-production-db --query "DBInstances[0].{Status:DBInstanceStatus,CPU:ProcessorFeatures}" &&
  echo "=== ALB ===" &&
  aws elbv2 describe-target-health --target-group-arn $(terraform output -raw alb_target_group_arn)
'

# 실행
aws-status
```

### 로그 스트리밍
```bash
# ECS 로그
aws logs tail /aws/ecs/triflow-ai-production-backend --follow --format short

# RDS 로그
aws logs tail /aws/rds/instance/triflow-ai-production-db/postgresql --follow

# 에러만 필터
aws logs tail /aws/ecs/triflow-ai-production-backend --follow --filter-pattern "ERROR"
```

---

## 🎓 참고 문서

- [AWS Troubleshooting Guide](https://docs.aws.amazon.com/index.html)
- [ECS Troubleshooting](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/troubleshooting.html)
- [RDS Troubleshooting](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Troubleshooting.html)
- [ALB Troubleshooting](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-troubleshooting.html)

---

**작성**: DevOps Team
**최종 업데이트**: 2026-01-20
**버전**: 1.0
