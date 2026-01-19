# Terraform 검증 가이드
**목적**: AWS 계정 생성 전 Terraform 코드를 로컬에서 검증
**소요 시간**: 30분
**필요**: Terraform CLI만 (AWS 계정 불필요)

---

## 🎯 검증 목표

✅ Terraform 문법 오류 없음
✅ 45개 리소스 정의 정확함
✅ 변수 타입 및 기본값 검증
✅ 리소스 간 의존성 정확함
✅ 비용 예측 정확함

---

## 📋 검증 절차

### 1. Terraform 설치 확인

```bash
# Terraform 버전 확인 (1.6+ 필요)
terraform version

# 예상 출력:
# Terraform v1.7.0
# on windows_amd64

# 설치 안 됨 시:
# Windows: choco install terraform
# macOS: brew install terraform
# Linux:
wget https://releases.hashicorp.com/terraform/1.7.0/terraform_1.7.0_linux_amd64.zip
unzip terraform_1.7.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/
```

### 2. Terraform 초기화

```bash
cd infrastructure/terraform

# Provider 플러그인 다운로드
terraform init

# 예상 출력:
# Initializing the backend...
# Initializing provider plugins...
# - Finding hashicorp/aws versions matching "~> 5.0"...
# - Installing hashicorp/aws v5.xx.x...
# ✅ Terraform has been successfully initialized!
```

**성공 조건**: 에러 메시지 없이 완료

### 3. 변수 파일 생성

```bash
# Example 파일 복사
cp terraform.tfvars.example terraform.tfvars

# 임시 값 설정 (검증용)
cat > terraform.tfvars << 'EOF'
aws_region  = "ap-northeast-2"
environment = "production"
project_name = "triflow-ai"

# VPC
vpc_cidr = "10.0.0.0/16"
availability_zones = ["ap-northeast-2a", "ap-northeast-2c"]

# RDS (임시 비밀번호)
db_instance_class = "db.t4g.medium"
db_allocated_storage = 100
db_max_allocated_storage = 200
db_name = "triflow"
db_username = "triflow_admin"
db_password = "TempPassword123!@#"  # 검증용 임시

# ECS
ecs_task_cpu = 1024
ecs_task_memory = 2048
ecs_desired_count = 2
ecs_min_count = 2
ecs_max_count = 5

# S3
s3_bucket_name = "triflow-ai-prod"
s3_lifecycle_glacier_days = 90

# CloudWatch
cloudwatch_log_retention_days = 15
EOF
```

### 4. Terraform Format 검증

```bash
# 코드 포맷팅 확인
terraform fmt -check -recursive

# 자동 포맷팅
terraform fmt -recursive

# 예상 출력:
# main.tf
# variables.tf
# (포맷팅된 파일 목록)
```

### 5. Terraform Validate

```bash
# 문법 검증 (AWS 계정 불필요!)
terraform validate

# 예상 출력:
# ✅ Success! The configuration is valid.
```

**에러 발생 시 수정 예시**:
```hcl
# 에러: Missing required argument
# 해결: 필수 인자 추가

# 에러: Invalid reference
# 해결: 리소스 참조 수정

# 에러: Unsupported argument
# 해결: 오타 수정 또는 Provider 버전 확인
```

### 6. Terraform Plan (핵심!)

```bash
# 실행 계획 생성 (AWS 계정 없어도 가능!)
terraform plan -out=tfplan.out

# 예상 소요 시간: 10~30초

# 예상 출력:
# Terraform will perform the following actions:
#
#   # aws_vpc.main will be created
#   + resource "aws_vpc" "main" {
#       + cidr_block = "10.0.0.0/16"
#       ...
#     }
#
#   # aws_db_instance.main will be created
#   + resource "aws_db_instance" "main" {
#       + instance_class = "db.t4g.medium"
#       + multi_az = true
#       ...
#     }
#
#   ... (총 45개 리소스)
#
# Plan: 45 to add, 0 to change, 0 to destroy.
```

**성공 조건**:
- ✅ `Plan: 45 to add, 0 to change, 0 to destroy`
- ✅ 에러 메시지 없음
- ✅ 경고 메시지 검토 (무시 가능한지 확인)

### 7. 생성될 리소스 상세 검토

```bash
# Plan 파일을 JSON으로 변환
terraform show -json tfplan.out > tfplan.json

# jq로 리소스 타입별 개수 확인
cat tfplan.json | jq -r '.planned_values.root_module.resources[].type' | sort | uniq -c

# 예상 출력:
#   2 aws_acm_certificate
#   1 aws_acm_certificate_validation
#   1 aws_cloudwatch_dashboard
#   1 aws_cloudwatch_log_group
#   8 aws_cloudwatch_metric_alarm
#   1 aws_db_instance
#   1 aws_db_parameter_group
#   1 aws_db_subnet_group
#   1 aws_ecr_lifecycle_policy
#   1 aws_ecr_repository
#   1 aws_ecs_cluster
#   1 aws_ecs_service
#   1 aws_ecs_task_definition
#   1 aws_eip
#   3 aws_iam_policy
#   6 aws_iam_role_policy_attachment
#   3 aws_iam_role
#   1 aws_internet_gateway
#   1 aws_lb
#   2 aws_lb_listener
#   1 aws_lb_target_group
#   1 aws_nat_gateway
#   4 aws_route_table_association
#   2 aws_route_table
#   1 aws_s3_bucket
#   1 aws_s3_bucket_lifecycle_configuration
#   1 aws_s3_bucket_policy
#   1 aws_s3_bucket_public_access_block
#   1 aws_s3_bucket_server_side_encryption_configuration
#   1 aws_s3_bucket_versioning
#   3 aws_security_group
#   1 aws_sns_topic
#   1 aws_sns_topic_subscription
#   4 aws_subnet
#   1 aws_vpc
#   1 aws_vpc_endpoint
```

**검토 포인트**:
- VPC: 1개 ✅
- Subnet: 4개 (Public 2 + Private 2) ✅
- RDS: 1개 (Multi-AZ) ✅
- ECS: Cluster 1 + Service 1 + Task Definition 1 ✅
- ALB: 1개 + Listener 2개 + Target Group 1개 ✅
- S3: 1개 + Lifecycle + Encryption ✅
- Security Group: 3개 (ALB, ECS, RDS) ✅
- CloudWatch Alarm: 8개 ✅

---

## 🔍 상세 검증 항목

### VPC 검증

```bash
# VPC CIDR 확인
terraform plan | grep "cidr_block"

# 예상:
# + cidr_block = "10.0.0.0/16"

# Subnet 확인
terraform plan | grep "availability_zone"

# 예상:
# + availability_zone = "ap-northeast-2a"
# + availability_zone = "ap-northeast-2c"
```

### RDS 검증

```bash
# RDS 사양 확인
terraform plan | grep -A 10 "aws_db_instance.main"

# 검증 포인트:
# ✅ instance_class = "db.t4g.medium"
# ✅ multi_az = true
# ✅ storage_type = "gp3"
# ✅ allocated_storage = 100
# ✅ engine = "postgres"
# ✅ engine_version = "14.10"
# ✅ backup_retention_period = 7
# ✅ deletion_protection = true
```

### ECS 검증

```bash
# ECS Task 사양 확인
terraform plan | grep -A 5 "aws_ecs_task_definition.backend"

# 검증 포인트:
# ✅ cpu = "1024" (1 vCPU)
# ✅ memory = "2048" (2 GB)
# ✅ network_mode = "awsvpc"
# ✅ requires_compatibilities = ["FARGATE"]
```

### S3 검증

```bash
# S3 Lifecycle 규칙 확인
terraform plan | grep -A 20 "aws_s3_bucket_lifecycle_configuration"

# 검증 포인트:
# ✅ Rule 1: workflows → 90일 후 Glacier
# ✅ Rule 2: exports → 90일 후 Glacier
# ✅ Rule 3: logs → 365일 후 삭제
# ✅ Rule 4: Multipart upload 7일 후 정리
```

---

## 💰 비용 예측 검증

### Terraform Cost Estimation (infracost 사용)

```bash
# infracost 설치 (선택사항)
# macOS: brew install infracost
# Windows: choco install infracost

# 비용 예측
infracost breakdown --path infrastructure/terraform

# 예상 출력:
# Name                                    Monthly Qty  Unit         Monthly Cost
#
# aws_db_instance.main
#  ├─ Database instance (on-demand)                730  hours            $147.20
#  ├─ Storage (gp3)                                100  GB                $11.50
#  └─ Multi-AZ                                       1  months           $147.20
#
# aws_ecs_service.backend
#  ├─ Per vCPU                                     730  hours             $29.55
#  └─ Per GB                                     1,460  GB-hours           $6.49
#
# ... (더 많은 리소스)
#
# OVERALL TOTAL                                                          $398.12
```

**예상 비용**: $398/월 ≈ ₩517,400/월 (On-Demand)
**Reserved 적용**: ₩388,504/월 ✅

---

## ⚠️ 발견 가능한 문제들

### 1. Provider Version 호환성
```bash
# 문제: AWS Provider 버전이 오래된 경우
# 증상: terraform init 시 경고

# 해결: versions.tf 확인
cat versions.tf | grep "version"

# 올바른 설정:
# aws = {
#   source  = "hashicorp/aws"
#   version = "~> 5.0"  # 5.x 최신 버전
# }
```

### 2. 리소스 이름 충돌
```bash
# 문제: S3 버킷 이름이 전역적으로 유일해야 함
# 증상: terraform plan 성공, terraform apply 실패

# 해결: s3_bucket_name 변경
# triflow-ai-prod → triflow-ai-prod-{account-id}
```

### 3. 할당량(Quota) 초과
```bash
# AWS 기본 할당량 확인
# - VPC: 5개 (충분)
# - EIP: 5개 (NAT 1개만 사용, 충분)
# - RDS 인스턴스: 40개 (충분)
# - ECS 클러스터: 10,000개 (충분)

# 문제 없음! ✅
```

---

## 📊 검증 체크리스트

### Phase 1: 파일 존재 확인
- [x] versions.tf (Provider 설정)
- [x] variables.tf (30개 변수)
- [x] outputs.tf (환경 변수 출력)
- [x] main.tf (공통 설정)
- [x] vpc.tf (VPC, Subnet, NAT, SG)
- [x] rds.tf (PostgreSQL Multi-AZ)
- [x] s3.tf (S3 + Lifecycle)
- [x] ecr.tf (ECR Repository)
- [x] iam.tf (IAM Roles)
- [x] ecs.tf (ECS Fargate)
- [x] alb.tf (ALB + Listener)
- [x] cloudwatch.tf (Logs + Alarms)
- [x] terraform.tfvars.example
- [x] .gitignore
- [x] README.md

### Phase 2: 문법 검증
- [ ] `terraform init` 성공
- [ ] `terraform fmt -check` 성공
- [ ] `terraform validate` 성공
- [ ] `terraform plan` 성공 (Plan: 45 to add)

### Phase 3: 리소스 검증
- [ ] VPC: 1개, Subnet: 4개
- [ ] RDS: db.t4g.medium Multi-AZ
- [ ] ECS: Fargate 1 vCPU, 2GB
- [ ] S3: Lifecycle 4 rules
- [ ] Security Groups: 3개 (ALB, ECS, RDS)
- [ ] CloudWatch Alarms: 8개

### Phase 4: 의존성 검증
- [ ] ECS → RDS (Security Group 참조)
- [ ] ALB → ECS (Target Group 연결)
- [ ] NAT → Private Subnet (Route Table)
- [ ] IAM Role → ECS Task (Execution Role)

### Phase 5: 비용 검증
- [ ] RDS: ~₩218,700/월
- [ ] ECS: ~₩93,704/월
- [ ] NAT: ~₩43,000/월
- [ ] ALB: ~₩22,000/월
- [ ] 합계: ~₩388,504/월 (RI)

---

## 🐛 일반적인 문제 및 해결

### 문제 1: `terraform init` 실패

**증상**:
```
Error: Failed to install provider
```

**원인**: 네트워크 또는 프록시 문제

**해결**:
```bash
# 프록시 설정 (필요 시)
export HTTP_PROXY=http://proxy:port
export HTTPS_PROXY=http://proxy:port

# Provider 수동 다운로드
terraform providers mirror ./terraform-providers
terraform init -plugin-dir=./terraform-providers
```

### 문제 2: `terraform validate` 경고

**증상**:
```
Warning: Deprecated argument
```

**원인**: Provider API 변경

**해결**:
```bash
# Provider 문서 확인
# https://registry.terraform.io/providers/hashicorp/aws/latest/docs

# 최신 문법으로 수정 (예시)
# Old: domain = "vpc"
# New: domain = "vpc"  # (변경 없음, 경고만 무시)
```

### 문제 3: `terraform plan` 실패 - 순환 참조

**증상**:
```
Error: Cycle: aws_security_group.alb → aws_security_group.ecs
```

**원인**: Security Group 간 상호 참조

**해결**: 현재 코드는 이미 해결됨 (ALB → ECS 단방향) ✅

### 문제 4: 비밀번호 정책 위반

**증상**:
```
Error: password does not meet RDS requirements
```

**원인**: db_password가 너무 단순

**해결**:
```bash
# 강력한 비밀번호 생성
openssl rand -base64 32

# terraform.tfvars 업데이트
db_password = "생성된_비밀번호"
```

---

## 🎨 추가 개선 사항

### 1. ElastiCache Redis 추가 (4-5월 대비)

**새 파일 생성**: `infrastructure/terraform/elasticache.tf`

```hcl
# ElastiCache Subnet Group
resource "aws_elasticache_subnet_group" "main" {
  name       = "${local.name_prefix}-redis-subnet-group"
  subnet_ids = aws_subnet.private[*].id

  tags = local.common_tags
}

# ElastiCache Redis Replication Group
resource "aws_elasticache_replication_group" "main" {
  replication_group_id       = "${local.name_prefix}-redis"
  replication_group_description = "TriFlow AI Redis cluster"
  engine                     = "redis"
  engine_version             = "7.0"
  node_type                  = "cache.t4g.small"
  num_cache_clusters         = 2  # Primary + Replica
  parameter_group_name       = "default.redis7"
  port                       = 6379
  subnet_group_name          = aws_elasticache_subnet_group.main.name
  security_group_ids         = [aws_security_group.redis.id]
  automatic_failover_enabled = true
  multi_az_enabled          = true

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                = var.redis_password  # 비밀번호 설정

  tags = local.common_tags
}

# Security Group for Redis
resource "aws_security_group" "redis" {
  name        = "${local.name_prefix}-redis-sg"
  description = "Security group for ElastiCache Redis"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Redis from ECS"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-redis-sg"
    }
  )
}
```

**추가 비용**: ₩50,000/월 (cache.t4g.small × 2)

### 2. Terraform Modules 구조화

**목적**: 재사용성 향상, 환경별 분리

```
infrastructure/terraform/
├─ modules/
│  ├─ vpc/
│  │  ├─ main.tf
│  │  ├─ variables.tf
│  │  └─ outputs.tf
│  ├─ rds/
│  │  ├─ main.tf
│  │  ├─ variables.tf
│  │  └─ outputs.tf
│  └─ ecs/
│     ├─ main.tf
│     ├─ variables.tf
│     └─ outputs.tf
├─ environments/
│  ├─ production/
│  │  ├─ main.tf
│  │  └─ terraform.tfvars
│  └─ staging/
│     ├─ main.tf
│     └─ terraform.tfvars
```

### 3. Terraform State S3 Backend

**목적**: State 파일 공유 및 잠금

```hcl
# versions.tf에 추가
terraform {
  backend "s3" {
    bucket         = "triflow-terraform-state"
    key            = "production/terraform.tfstate"
    region         = "ap-northeast-2"
    encrypt        = true
    dynamodb_table = "triflow-terraform-locks"
  }
}
```

**사전 작업** (AWS 계정 필요):
```bash
# S3 버킷 생성
aws s3 mb s3://triflow-terraform-state --region ap-northeast-2

# Versioning 활성화
aws s3api put-bucket-versioning \
    --bucket triflow-terraform-state \
    --versioning-configuration Status=Enabled

# DynamoDB 테이블 생성 (State Lock용)
aws dynamodb create-table \
    --table-name triflow-terraform-locks \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region ap-northeast-2
```

---

## 📈 검증 결과 리포트

### 체크리스트

| 항목 | 상태 | 비고 |
|------|:----:|------|
| Terraform 설치 | ✅ | v1.7.0 |
| terraform init | ⏳ | 실행 대기 |
| terraform fmt | ⏳ | 실행 대기 |
| terraform validate | ⏳ | 실행 대기 |
| terraform plan | ⏳ | 실행 대기 |
| 리소스 개수 (45개) | ⏳ | 검증 대기 |
| 비용 예측 (₩388,504) | ✅ | 수동 계산 완료 |
| 보안 설정 | ⏳ | Plan 검토 필요 |

### 다음 단계

**로컬 검증 완료 후**:
1. ✅ Terraform 코드 승인
2. ✅ Git commit (infrastructure/ 디렉토리만)
3. ⏳ AWS 계정 생성 대기
4. ⏳ terraform apply 실행 (AWS 계정 생성 후)

---

**검증 예상 시간**: 30분
**수정 필요 시**: +1시간
**총 소요**: 1.5시간 이내
