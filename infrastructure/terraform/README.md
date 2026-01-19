# TriFlow AI - Terraform Infrastructure

이 디렉토리는 TriFlow AI의 AWS 인프라를 Terraform으로 관리합니다.

## 📋 사전 요구사항

### 1. Terraform 설치
```bash
# macOS
brew install terraform

# Windows (Chocolatey)
choco install terraform

# Linux
wget https://releases.hashicorp.com/terraform/1.7.0/terraform_1.7.0_linux_amd64.zip
unzip terraform_1.7.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/
```

### 2. AWS CLI 설치 및 설정
```bash
# AWS CLI 설치
pip install awscli

# AWS Credentials 설정
aws configure
# AWS Access Key ID: AKIA...
# AWS Secret Access Key: ...
# Default region: ap-northeast-2
# Default output format: json
```

### 3. AWS 계정 권한

필요한 IAM 권한:
- VPC 생성 및 관리
- RDS 생성 및 관리
- ECS/Fargate 생성 및 관리
- ALB 생성 및 관리
- S3 버킷 생성 및 관리
- CloudWatch Logs/Alarms 생성
- IAM Role/Policy 생성
- ACM 인증서 생성 (도메인 사용 시)

**권장**: `AdministratorAccess` (초기 구축 시만)

---

## 🚀 사용법

### 1. 초기 설정

```bash
# terraform 디렉토리로 이동
cd infrastructure/terraform

# terraform.tfvars 파일 생성
cp terraform.tfvars.example terraform.tfvars

# 변수 값 설정 (중요!)
vim terraform.tfvars
# - db_password: 강력한 비밀번호 설정
# - domain_name: 도메인 사용 시 설정
# - slack_webhook_url: Slack 연동 시 설정
```

### 2. Terraform 초기화

```bash
# Provider 플러그인 다운로드
terraform init

# 출력 예시:
# Initializing provider plugins...
# - hashicorp/aws v5.x.x
# Terraform has been successfully initialized!
```

### 3. 인프라 계획 확인 (AWS 계정 없이도 가능)

```bash
# 생성될 리소스 확인
terraform plan

# 출력 예시:
# Plan: 45 to add, 0 to change, 0 to destroy
#
# 주요 리소스:
# + aws_vpc.main
# + aws_db_instance.main (db.t4g.medium, Multi-AZ)
# + aws_ecs_cluster.main
# + aws_lb.main
# + aws_s3_bucket.main
# ...
```

### 4. 인프라 생성 (AWS 계정 필요)

```bash
# 실제 인프라 생성
terraform apply

# 확인 메시지
# Do you want to perform these actions?
# Enter a value: yes

# 예상 시간: 15~20분
# - VPC/Subnet: 1분
# - RDS (Multi-AZ): 10~15분 (가장 오래 걸림)
# - ECS Cluster: 1분
# - ALB: 2~3분
# - S3: 즉시
```

### 5. 환경 변수 출력

```bash
# Terraform outputs을 .env 파일로 저장
terraform output -raw env_variables > ../../.env.production.generated

# .env.production 파일 편집
vim ../../.env.production.generated
# RDS_PASSWORD 추가 (Terraform output에는 보안상 제외됨)
```

---

## 📁 파일 구조

```
infrastructure/terraform/
├─ versions.tf          # Terraform 및 Provider 버전
├─ variables.tf         # 입력 변수 정의
├─ outputs.tf           # 출력 값 정의
├─ main.tf              # 공통 설정 및 데이터 소스
├─ vpc.tf               # VPC, Subnet, NAT, Security Groups
├─ rds.tf               # RDS PostgreSQL (Multi-AZ)
├─ s3.tf                # S3 Bucket (Lifecycle, Versioning)
├─ ecr.tf               # ECR Repository
├─ iam.tf               # IAM Roles & Policies
├─ ecs.tf               # ECS Cluster, Task Definition, Service
├─ alb.tf               # Application Load Balancer
├─ cloudwatch.tf        # CloudWatch Logs, Alarms, Dashboard
├─ terraform.tfvars.example  # 변수 값 예시
└─ README.md            # 이 파일
```

---

## 🔧 주요 명령어

### 인프라 관리

```bash
# 현재 상태 확인
terraform show

# 특정 리소스만 적용
terraform apply -target=aws_s3_bucket.main

# 인프라 삭제 (주의!)
terraform destroy

# 상태 파일 백업
terraform state pull > terraform.tfstate.backup
```

### 변수 오버라이드

```bash
# 명령줄에서 변수 전달
terraform apply -var="environment=staging" -var="ecs_desired_count=1"

# 변수 파일 지정
terraform apply -var-file="staging.tfvars"
```

### 출력 값 확인

```bash
# 모든 출력 값
terraform output

# 특정 출력 값
terraform output rds_endpoint
terraform output alb_dns_name

# JSON 형식
terraform output -json
```

---

## 📊 생성되는 리소스

| 리소스 | 개수 | 주요 사양 |
|--------|-----:|----------|
| VPC | 1 | 10.0.0.0/16 |
| Public Subnet | 2 | ap-northeast-2a, 2c |
| Private Subnet | 2 | ap-northeast-2a, 2c |
| Internet Gateway | 1 | - |
| NAT Gateway | 1 | ap-northeast-2a (Single) |
| Security Groups | 3 | ALB, ECS, RDS |
| **RDS PostgreSQL** | 1 | db.t4g.medium Multi-AZ |
| **ECS Cluster** | 1 | Fargate |
| **ECS Service** | 1 | 2~5 tasks (Auto Scaling) |
| **ALB** | 1 | Internet-facing |
| **S3 Bucket** | 1 | Versioning, Encryption |
| ECR Repository | 1 | Backend images |
| CloudWatch Log Group | 1 | 15일 보관 |
| CloudWatch Alarms | 8 | CPU, Memory, 5xx, Latency 등 |
| SNS Topic | 1 | 알람 전송 |
| IAM Roles | 3 | ECS Execution, Task, RDS Monitoring |

**총 리소스**: ~45개

---

## 💰 예상 비용

```
월간 비용 (Reserved Instances 적용):
- ECS Fargate (2 tasks): ₩93,704
- RDS db.t4g.medium (Multi-AZ, RI): ₩218,700
- S3: ₩600
- ALB: ₩22,000
- NAT Gateway: ₩43,000
- CloudWatch: ₩8,200
- Route 53 (선택): ₩1,300
- Data Transfer: ₩1,000
───────────────────────────────
합계: ₩388,504/월

RI 선불금 (1회): ₩300,000
```

---

## 🔒 보안 고려사항

### 1. 비밀번호 관리
- ❌ `terraform.tfvars`에 평문 저장 금지
- ✅ 환경 변수 사용: `export TF_VAR_db_password="..."`
- ✅ AWS Secrets Manager 사용 (권장)

### 2. State 파일 보안
- ❌ `terraform.tfstate`에 민감 정보 포함 (RDS 비밀번호 등)
- ✅ S3 Backend 사용 (암호화 + 버전 관리)
- ✅ `.gitignore`에 추가:
  ```
  *.tfstate
  *.tfstate.backup
  *.tfvars (terraform.tfvars.example 제외)
  ```

### 3. IAM 최소 권한
- ECS Task Role은 필요한 S3 폴더만 접근
- RDS는 Private Subnet에만 배치
- Security Group은 최소 포트만 오픈

---

## ⚠️ 주의사항

### RDS Deletion Protection
- `deletion_protection = true` 설정됨
- 삭제 시 먼저 비활성화 필요:
  ```bash
  # 1. deletion_protection 제거
  terraform apply -target=aws_db_instance.main

  # 2. 삭제
  terraform destroy
  ```

### Multi-AZ RDS 생성 시간
- 10~15분 소요 (Standby 복제 포함)
- 인내심을 가지고 기다리세요!

### NAT Gateway 비용
- Single NAT: ₩43,000/월
- **삭제 시 주의**: Elastic IP도 함께 삭제해야 비용 발생 안 함

---

## 🐛 트러블슈팅

### Terraform init 실패
```bash
# Provider 다운로드 실패 시
terraform init -upgrade

# 캐시 삭제
rm -rf .terraform
terraform init
```

### Terraform apply 실패: RDS
```bash
# 에러: "DB subnet group doesn't meet availability zone coverage"
# 해결: subnet이 최소 2개 AZ에 있어야 함 (이미 설정됨)

# 에러: "Password does not meet requirements"
# 해결: db_password는 최소 8자, 특수문자 포함 필요
```

### Terraform apply 실패: ECS
```bash
# 에러: "No Container Instances were found in your cluster"
# 해결: Fargate 사용 시 정상 (Container Instance 불필요)

# 에러: "Unable to pull image"
# 해결: ECR에 이미지 push 필요
#   docker build -t backend:latest ./backend
#   aws ecr get-login-password | docker login ...
#   docker push ${ECR_URL}:latest
```

---

## 📚 다음 단계

### 1. pgvector Extension 설치
Terraform 완료 후 수동 설치 필요:
```bash
# RDS 연결
psql -h $(terraform output -raw rds_address) -U triflow_admin -d triflow

# Extension 설치
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
```

### 2. ECR에 이미지 푸시
```bash
# ECR 로그인
aws ecr get-login-password --region ap-northeast-2 | \
  docker login --username AWS --password-stdin $(terraform output -raw ecr_repository_url | cut -d'/' -f1)

# 이미지 빌드 및 푸시
docker build -t triflow-backend:latest ./backend
docker tag triflow-backend:latest $(terraform output -raw ecr_repository_url):latest
docker push $(terraform output -raw ecr_repository_url):latest
```

### 3. ECS Service 시작
```bash
# Task Definition 업데이트 (이미지 포함)
# 배포 스크립트 사용: ../scripts/deploy-aws.sh production latest
```

---

## 🔗 참고 링크

- [Terraform AWS Provider 문서](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS ECS Fargate 가이드](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html)
- [AWS RDS PostgreSQL](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_PostgreSQL.html)
- [Architecture Decisions 문서](../../docs/aws/architecture-decisions.md)

---

**작성**: DevOps Team
**검토**: Tech Lead
**버전**: 1.0 (2026-01-20)
