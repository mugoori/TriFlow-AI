# AWS 배포 가이드
**프로젝트**: TriFlow AI
**대상**: DevOps, Backend 팀
**작성일**: 2026년 1월 20일

---

## 📋 배포 프로세스 개요

```
Phase 0 (현재)          Phase 1 (AWS 계정 생성 후)
│                       │
├─ 아키텍처 설계 ✅      ├─ AWS 계정 생성
├─ Terraform 코드 ✅    ├─ Terraform apply
├─ AWS SDK 래퍼 ✅      ├─ pgvector extension 설치
├─ 환경 설정 ✅         ├─ ECR에 이미지 push
├─ LocalStack 테스트 ✅ ├─ ECS Service 시작
└─ 배포 스크립트 ✅     └─ 통합 테스트
```

---

## 🚀 Phase 0: 로컬 검증 (AWS 계정 없이)

### 1. Terraform 문법 검증

```bash
cd infrastructure/terraform

# 초기화
terraform init

# 변수 파일 생성
cp terraform.tfvars.example terraform.tfvars

# 임시 비밀번호 설정 (나중에 변경)
vim terraform.tfvars
# db_password = "temporary-password-12345"

# 계획 확인 (AWS 계정 없어도 가능!)
terraform plan

# 예상 출력:
# Plan: 45 to add, 0 to change, 0 to destroy
```

**성공 조건**: `terraform plan` 에러 없이 완료 ✅

### 2. LocalStack 테스트

```bash
# LocalStack 시작
docker-compose -f docker-compose.localstack.yml up -d

# 초기화 대기
sleep 10

# 초기화 스크립트 실행
bash scripts/init-localstack.sh

# 테스트: S3 버킷 확인
aws --endpoint-url=http://localhost:4566 s3 ls

# 예상 출력:
# 2026-01-20 10:00:00 triflow-ai-local
```

### 3. AWS SDK 래퍼 테스트

```bash
cd backend

# pytest 환경 설정
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export S3_BUCKET_NAME=triflow-ai-local

# 테스트 실행
pytest tests/test_aws_services.py -v

# 예상 출력:
# tests/test_aws_services.py::test_s3_upload PASSED
# tests/test_aws_services.py::test_s3_download PASSED
# tests/test_aws_services.py::test_secrets_manager PASSED
```

---

## 🌐 Phase 1: AWS 인프라 구축

### 1. AWS 계정 생성 및 설정

#### AWS 계정 생성
```bash
# https://aws.amazon.com/ko/
# 1. "AWS 계정 만들기" 클릭
# 2. 이메일, 비밀번호 설정
# 3. 결제 정보 등록 (신용카드/체크카드)
# 4. 본인 확인 (전화번호 인증)
# 5. Support Plan: Basic (무료) 선택
```

#### IAM User 생성 (Terraform 실행용)
```bash
# AWS Console → IAM → Users → Create User
# 1. User name: terraform-deploy
# 2. Access type: Programmatic access
# 3. Permissions: AdministratorAccess (초기에만)
# 4. Download credentials.csv

# AWS CLI 설정
aws configure
# AWS Access Key ID: (credentials.csv 참조)
# AWS Secret Access Key: (credentials.csv 참조)
# Default region: ap-northeast-2
# Default output format: json

# 계정 확인
aws sts get-caller-identity
# {
#   "UserId": "AIDA...",
#   "Account": "123456789012",
#   "Arn": "arn:aws:iam::123456789012:user/terraform-deploy"
# }
```

### 2. Terraform으로 인프라 구축

```bash
cd infrastructure/terraform

# terraform.tfvars 실제 값 설정
vim terraform.tfvars

# 필수 변경 사항:
# - db_password: 강력한 비밀번호 (16자 이상, 특수문자 포함)
# - domain_name: 실제 도메인 (사용 시)
# - slack_webhook_url: Slack Webhook URL (사용 시)

# Terraform 계획 확인
terraform plan -out=tfplan

# 리소스 생성 (15~20분 소요)
terraform apply tfplan

# 진행 상황:
# - VPC, Subnet, NAT: 1~2분
# - Security Groups: 즉시
# - S3 Bucket: 즉시
# - ECR Repository: 즉시
# - RDS (Multi-AZ): 10~15분 ⏳ (가장 오래 걸림!)
# - ECS Cluster: 1분
# - ALB: 2~3분
# - CloudWatch: 즉시
```

**성공 확인**:
```bash
# 출력 값 확인
terraform output

# 주요 출력:
# - rds_endpoint = "triflow-ai-production-db.xxxxx.rds.amazonaws.com:5432"
# - alb_dns_name = "triflow-ai-production-alb-xxxxx.elb.amazonaws.com"
# - ecr_repository_url = "123456789012.dkr.ecr.ap-northeast-2.amazonaws.com/triflow-ai-backend"
```

### 3. PostgreSQL Extensions 설치

```bash
# Terraform output에서 RDS 주소 가져오기
RDS_ENDPOINT=$(terraform output -raw rds_address)

# psql 설치 (없을 경우)
# macOS: brew install postgresql
# Ubuntu: sudo apt install postgresql-client

# RDS 연결
psql -h $RDS_ENDPOINT -U triflow_admin -d triflow

# 비밀번호 입력 (terraform.tfvars의 db_password)

# Extensions 설치
CREATE EXTENSION IF NOT EXISTS vector;           -- pgvector
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";      -- UUID 생성
CREATE EXTENSION IF NOT EXISTS pg_trgm;          -- 텍스트 검색
CREATE EXTENSION IF NOT EXISTS pg_stat_statements; -- 쿼리 모니터링

# 설치 확인
\dx

# 예상 출력:
#                                      List of installed extensions
#   Name    | Version |   Schema   |                         Description
# ----------+---------+------------+--------------------------------------------------------------
#  pg_trgm  | 1.6     | public     | text similarity measurement and index searching
#  plpgsql  | 1.0     | pg_catalog | PL/pgSQL procedural language
#  uuid-ossp| 1.1     | public     | generate universally unique identifiers (UUIDs)
#  vector   | 0.5.0   | public     | vector data type and ivfflat access method

\q
```

### 4. ECR에 Docker 이미지 Push

```bash
# ECR 로그인
ECR_REGISTRY=$(terraform output -raw ecr_repository_url | cut -d'/' -f1)
aws ecr get-login-password --region ap-northeast-2 | \
    docker login --username AWS --password-stdin $ECR_REGISTRY

# 이미지 빌드
docker build --platform linux/amd64 -t triflow-backend:latest -f backend/Dockerfile ./backend

# 이미지 태그
ECR_REPO_URL=$(terraform output -raw ecr_repository_url)
docker tag triflow-backend:latest ${ECR_REPO_URL}:latest

# 이미지 Push
docker push ${ECR_REPO_URL}:latest

# 성공 확인
aws ecr describe-images --repository-name triflow-ai-backend
```

### 5. Alembic Database 마이그레이션

```bash
cd backend

# 환경 변수 설정 (.env.production 파일 생성)
cp ../.env.production.example .env.production

# Terraform outputs으로 자동 생성 (권장)
cd ../infrastructure/terraform
terraform output -raw env_variables > ../../.env.production

# .env.production 편집 (RDS_PASSWORD 추가)
vim ../../.env.production

cd ../../backend

# Alembic 마이그레이션 실행
source .env.production  # 환경 변수 로드
alembic upgrade head

# 성공 확인
psql -h $RDS_ADDRESS -U $RDS_USERNAME -d $RDS_DATABASE -c "\dt core.*"

# 예상 출력:
#          List of relations
#  Schema |     Name      | Type  |     Owner
# --------+---------------+-------+----------------
#  core   | tenants       | table | triflow_admin
#  core   | users         | table | triflow_admin
#  core   | workflows     | table | triflow_admin
#  ...
```

### 6. ECS Service 시작

```bash
# 배포 스크립트 실행
cd ../
./scripts/deploy-aws.sh production latest

# 진행 상황:
# ✅ ECR login
# ✅ Docker build
# ✅ Push to ECR
# ✅ Update task definition
# ✅ Update ECS service
# ⏳ Waiting for stability... (2~5분)

# 성공 출력:
# ========================================
# ✅ Deployment Complete!
# ========================================
#
# 📊 Deployment Summary:
#    Cluster: triflow-ai-production-cluster
#    Service: triflow-ai-production-backend-service
#    Image: 123456789012.dkr.ecr.ap-northeast-2.amazonaws.com/triflow-ai-backend:latest
#    Running Tasks: 2/2
#
# 🌐 Access Points:
#    ALB: https://triflow-ai-production-alb-xxxxx.elb.amazonaws.com
#    Health: https://triflow-ai-production-alb-xxxxx.elb.amazonaws.com/health
```

### 7. 배포 검증

```bash
# Health check
ALB_DNS=$(cd infrastructure/terraform && terraform output -raw alb_dns_name)
curl https://${ALB_DNS}/health

# 예상 응답:
# {"status":"healthy","timestamp":"2026-01-20T10:00:00Z"}

# API 테스트
curl https://${ALB_DNS}/api/v1/health

# ECS 태스크 상태 확인
aws ecs describe-services \
    --cluster triflow-ai-production-cluster \
    --services triflow-ai-production-backend-service \
    --query 'services[0].{Desired:desiredCount,Running:runningCount,Pending:pendingCount}'

# CloudWatch 로그 확인
aws logs tail /aws/ecs/triflow-ai-production-backend --follow
```

---

## 🔄 일상 배포 프로세스

### 방법 1: 로컬에서 배포 스크립트 사용

```bash
# 코드 변경 후
git add .
git commit -m "feat: Add new feature"
git push origin develop

# 배포
./scripts/deploy-aws.sh production $(git rev-parse --short HEAD)

# 롤백 (이전 이미지로)
./scripts/deploy-aws.sh production v1.2.3
```

### 방법 2: GitHub Actions 자동 배포

```bash
# main 브랜치에 push하면 자동 배포
git checkout main
git merge develop
git push origin main

# GitHub Actions가 자동으로:
# 1. Docker 이미지 빌드
# 2. ECR에 push
# 3. ECS Service 업데이트
# 4. Slack 알림 전송
```

### 방법 3: 수동 배포 (GitHub Actions UI)

```
1. GitHub → Actions → "Deploy to AWS ECS"
2. "Run workflow" 클릭
3. Environment 선택: production / staging
4. Image tag 입력: latest / v1.2.3 / SHA
5. "Run workflow" 클릭
```

---

## 🐛 트러블슈팅

### Terraform apply 실패: RDS

**에러**: `Error creating DB Instance: InvalidParameterCombination`
```bash
# 원인: db.t4g 인스턴스는 ap-northeast-2에서 지원됨
# 해결: aws_region이 ap-northeast-2인지 확인

# db.t4g 지원 확인
aws rds describe-orderable-db-instance-options \
    --engine postgres \
    --engine-version 14.10 \
    --query 'OrderableDBInstanceOptions[?DBInstanceClass==`db.t4g.medium`]'
```

**에러**: `Error: timeout while waiting for state to become 'available'`
```bash
# 원인: RDS Multi-AZ는 15분 이상 소요
# 해결: 인내심을 가지고 기다리거나, AWS Console에서 진행 상황 확인
#       https://console.aws.amazon.com/rds/
```

### ECR Push 실패

**에러**: `no basic auth credentials`
```bash
# 원인: ECR 로그인 만료 (12시간 유효)
# 해결: ECR 재로그인
aws ecr get-login-password --region ap-northeast-2 | \
    docker login --username AWS --password-stdin ${ECR_REGISTRY}
```

**에러**: `denied: Your authorization token has expired`
```bash
# 원인: Docker 로그인 만료
# 해결: 위와 동일
```

### ECS Service 시작 실패

**에러**: `service triflow-ai-production-backend-service was unable to place a task`
```bash
# 원인 1: Subnet에 가용 IP 부족
# 해결: Private Subnet CIDR 확인 (10.0.11.0/24 = 251 IPs)

# 원인 2: Security Group 잘못 설정
# 해결: terraform apply 재실행

# 원인 3: ECR 이미지 없음
# 해결: ECR에 이미지 push 먼저 수행
```

**에러**: `CannotPullContainerError: pull image manifest has been retried`
```bash
# 원인: ECR 이미지 Pull 권한 없음
# 해결: IAM Role 확인 (ecs_task_execution_role)

# ECS Task Execution Role 권한 확인
aws iam get-role --role-name triflow-ai-production-ecs-task-execution-role
```

### Health Check 실패

**에러**: `service is unhealthy in target group`
```bash
# 원인: /health 엔드포인트 응답 없음
# 해결 1: Backend 로그 확인
aws logs tail /aws/ecs/triflow-ai-production-backend --follow

# 해결 2: Security Group 확인 (ALB → ECS 8000 port)
aws ec2 describe-security-groups --group-ids sg-xxxxx

# 해결 3: ECS Task 내부 접근 테스트
# ECS Task IP 조회
TASK_ARN=$(aws ecs list-tasks --cluster triflow-ai-production-cluster --service-name triflow-ai-production-backend-service --query 'taskArns[0]' --output text)
TASK_IP=$(aws ecs describe-tasks --cluster triflow-ai-production-cluster --tasks $TASK_ARN --query 'tasks[0].containers[0].networkInterfaces[0].privateIpv4Address' --output text)

# EC2 Instance에서 테스트 (Bastion Host 필요)
curl http://${TASK_IP}:8000/health
```

---

## 📊 모니터링 및 로그

### CloudWatch Logs 확인

```bash
# 실시간 로그 스트리밍
aws logs tail /aws/ecs/triflow-ai-production-backend --follow

# 특정 시간대 로그
aws logs tail /aws/ecs/triflow-ai-production-backend \
    --since 1h \
    --format short

# 에러 로그만 필터링
aws logs tail /aws/ecs/triflow-ai-production-backend \
    --follow \
    --filter-pattern "ERROR"
```

### CloudWatch Metrics 확인

```bash
# ECS CPU 사용률
aws cloudwatch get-metric-statistics \
    --namespace AWS/ECS \
    --metric-name CPUUtilization \
    --dimensions Name=ClusterName,Value=triflow-ai-production-cluster Name=ServiceName,Value=triflow-ai-production-backend-service \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 300 \
    --statistics Average

# RDS CPU 사용률
aws cloudwatch get-metric-statistics \
    --namespace AWS/RDS \
    --metric-name CPUUtilization \
    --dimensions Name=DBInstanceIdentifier,Value=triflow-ai-production-db \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 300 \
    --statistics Average
```

### Grafana 대시보드

```
# CloudWatch 데이터소스 추가
1. Grafana → Configuration → Data Sources
2. Add data source → CloudWatch
3. Auth Provider: Access & Secret Key
4. Access Key ID: (IAM User credentials)
5. Secret Access Key: (IAM User credentials)
6. Default Region: ap-northeast-2
7. Save & Test

# 대시보드 Import
1. Grafana → Dashboards → Import
2. Import via grafana.com: 11265 (AWS ECS Fargate)
3. Select CloudWatch data source
4. Import
```

---

## 🔄 롤백 절차

### 이전 Task Definition으로 롤백

```bash
# 현재 Task Definition 조회
aws ecs describe-services \
    --cluster triflow-ai-production-cluster \
    --services triflow-ai-production-backend-service \
    --query 'services[0].taskDefinition'

# 출력: arn:aws:ecs:ap-northeast-2:123456789012:task-definition/triflow-ai-production-backend:5

# 이전 버전으로 롤백 (Revision 4로)
aws ecs update-service \
    --cluster triflow-ai-production-cluster \
    --service triflow-ai-production-backend-service \
    --task-definition triflow-ai-production-backend:4 \
    --force-new-deployment

# 안정화 대기
aws ecs wait services-stable \
    --cluster triflow-ai-production-cluster \
    --services triflow-ai-production-backend-service
```

### 특정 이미지로 롤백

```bash
# ECR 이미지 목록 조회
aws ecr describe-images \
    --repository-name triflow-ai-backend \
    --query 'sort_by(imageDetails,& imagePushedAt)[-10:].[imageTags[0], imagePushedAt]' \
    --output table

# 특정 태그로 배포
./scripts/deploy-aws.sh production v1.2.3
```

---

## 💰 비용 모니터링

### CloudWatch Billing Alarm 설정

```bash
# Billing 알람 (월 $500 초과 시)
aws cloudwatch put-metric-alarm \
    --alarm-name triflow-monthly-billing-alarm \
    --alarm-description "Monthly AWS bill exceeds $500" \
    --metric-name EstimatedCharges \
    --namespace AWS/Billing \
    --statistic Maximum \
    --period 21600 \
    --evaluation-periods 1 \
    --threshold 500 \
    --comparison-operator GreaterThanThreshold \
    --dimensions Name=Currency,Value=USD \
    --alarm-actions $(cd ../infrastructure/terraform && terraform output -raw sns_topic_arn)
```

### Cost Explorer 확인

```bash
# 이번 달 비용 조회 (AWS CLI v2 필요)
aws ce get-cost-and-usage \
    --time-period Start=$(date -u -d 'month ago' +%Y-%m-01),End=$(date -u +%Y-%m-%d) \
    --granularity MONTHLY \
    --metrics UnblendedCost \
    --group-by Type=SERVICE

# 또는 AWS Console 사용
# https://console.aws.amazon.com/cost-management/home#/cost-explorer
```

---

## 🔐 보안 체크리스트

### 배포 후 즉시 확인

- [ ] RDS publicly_accessible = false 확인
- [ ] S3 Public Access Block 활성화 확인
- [ ] Security Group 최소 포트만 오픈 확인
- [ ] IAM Role 최소 권한 확인
- [ ] CloudWatch Logs 암호화 확인
- [ ] ALB HTTPS만 허용 확인 (HTTP는 Redirect)
- [ ] SSL/TLS 정책 최신 버전 확인

```bash
# RDS Public 접근 확인
aws rds describe-db-instances \
    --db-instance-identifier triflow-ai-production-db \
    --query 'DBInstances[0].PubliclyAccessible'
# 출력: false ✅

# S3 Public Access 확인
aws s3api get-public-access-block --bucket triflow-ai-prod
# 모든 설정이 true ✅

# Security Group 확인
aws ec2 describe-security-groups \
    --filters "Name=tag:Environment,Values=production" \
    --query 'SecurityGroups[*].{Name:GroupName,Ingress:IpPermissions}'
```

---

## 📚 참고 문서

- [Architecture Decisions](./architecture-decisions.md) - 아키텍처 설계 근거
- [Cost Calculator](./cost-calculator.md) - 비용 상세 분석
- [Architecture Diagram](./architecture-diagram.md) - 인프라 다이어그램
- [Terraform README](../../infrastructure/terraform/README.md) - Terraform 사용법

---

## 📞 문의 및 지원

**문제 발생 시**:
1. CloudWatch Logs 확인
2. #triflow-alerts Slack 채널 확인
3. DevOps 팀에 문의 (devops@company.com)

**긴급 장애**:
- Tech Lead: +82-10-XXXX-XXXX
- DevOps On-Call: +82-10-YYYY-YYYY

---

**작성**: DevOps Team
**최종 업데이트**: 2026-01-20
**버전**: 1.0
