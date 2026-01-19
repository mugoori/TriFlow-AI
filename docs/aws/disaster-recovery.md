# 재해 복구 계획 (Disaster Recovery Plan)
**프로젝트**: TriFlow AI
**작성일**: 2026년 1월 20일
**버전**: 1.0
**승인**: Pending

---

## 📋 Executive Summary

본 문서는 TriFlow AI의 AWS 인프라에 대한 재해 복구 계획을 정의합니다.

**목표**:
- **RTO (Recovery Time Objective)**: 4시간 이내
- **RPO (Recovery Point Objective)**: 5분 이내
- **가용성 목표**: 99.95% (연간 다운타임 < 4.4시간)

---

## 🎯 재해 시나리오 및 대응

### 시나리오 1: RDS Primary 장애 ⚡ Critical

**증상**:
- Database 연결 실패
- API 5xx 에러 급증
- CloudWatch Alarm: `rds-cpu-high` or `rds-connections-high`

**자동 복구 (Multi-AZ Failover)**:
```
1. AWS가 Primary 장애 감지 (30초 이내)
2. Standby를 Primary로 자동 승격 (60~120초)
3. CNAME 레코드 자동 업데이트
4. 애플리케이션 자동 재연결 (연결 재시도 로직)

총 RTO: 2~3분 ✅
RPO: 0초 (동기화 복제) ✅
```

**수동 개입 불필요**: AWS가 자동 처리

**모니터링**:
```bash
# Failover 이벤트 확인
aws rds describe-events \
    --source-identifier triflow-ai-production-db \
    --duration 60 \
    --query 'Events[?contains(Message, `failover`)]'

# 현재 Primary 확인
aws rds describe-db-instances \
    --db-instance-identifier triflow-ai-production-db \
    --query 'DBInstances[0].{AZ:AvailabilityZone,MultiAZ:MultiAZ}'
```

**검증**:
- [ ] Failover 테스트 (Staging 환경에서 수행)
- [ ] 애플리케이션 재연결 로직 확인
- [ ] 데이터 무결성 확인

---

### 시나리오 2: ECS Task 전체 장애 ⚡ Critical

**증상**:
- 모든 ECS Task Down
- ALB Health Check 실패
- 503 Service Unavailable

**자동 복구 (ECS Auto Scaling)**:
```
1. ALB Health Check 실패 감지 (15초 간격)
2. ECS가 Task Unhealthy 판단 (45초, 3회 실패)
3. ECS가 새 Task 자동 시작 (30~60초)
4. Task가 Healthy 상태 도달 (60초)

총 RTO: 2~3분 ✅
RPO: N/A (Stateless 애플리케이션)
```

**수동 개입 (자동 복구 실패 시)**:
```bash
# ECS 서비스 강제 재배포
aws ecs update-service \
    --cluster triflow-ai-production-cluster \
    --service triflow-ai-production-backend-service \
    --force-new-deployment

# 또는 Desired Count 조정
aws ecs update-service \
    --cluster triflow-ai-production-cluster \
    --service triflow-ai-production-backend-service \
    --desired-count 3  # 2 → 3으로 증가

# Task 로그 확인
aws logs tail /aws/ecs/triflow-ai-production-backend --follow
```

**RTO**: 5분
**RPO**: N/A

---

### 시나리오 3: ALB 장애 🟡 Medium

**증상**:
- 사용자 접속 불가
- DNS 해석 실패 또는 502 Bad Gateway

**복구 (AWS 관리형)**:
```
ALB는 AWS 관리형 서비스 (SLA 99.99%)
→ 사용자가 복구할 수 없음
→ AWS Support 티켓 생성 필요
```

**대응 절차**:
```
1. CloudWatch Alarm 확인
2. AWS Personal Health Dashboard 확인
   https://phd.aws.amazon.com/

3. AWS Support 티켓 생성
   - Severity: Critical (Production system down)
   - Issue: ALB not responding

4. 임시 조치: 다른 Region으로 Failover (수동)
   → Cross-Region DR 필요 (미구현)
```

**RTO**: 1~4시간 (AWS 응답 시간)
**RPO**: N/A

**향후 개선**:
- [ ] Multi-Region 구성 (ap-northeast-2 + us-west-2)
- [ ] Route 53 Failover 정책

---

### 시나리오 4: NAT Gateway 장애 🟢 Low

**증상**:
- Anthropic API 호출 실패
- ECR 이미지 pull 실패 (배포 시)
- 외부 API 접근 불가

**영향**:
- ✅ RDS 접근: 정상 (Private Subnet 내부)
- ✅ S3 접근: 정상 (VPC Endpoint 사용)
- ❌ Anthropic API: 실패
- ❌ 배포: 불가 (ECR 접근 불가)

**복구**:
```bash
# 새 NAT Gateway 생성 (다른 AZ)
# 1. Elastic IP 생성
aws ec2 allocate-address --domain vpc

# 2. NAT Gateway 생성
aws ec2 create-nat-gateway \
    --subnet-id subnet-xxxxx \
    --allocation-id eipalloc-xxxxx

# 3. Route Table 업데이트
aws ec2 replace-route \
    --route-table-id rtb-xxxxx \
    --destination-cidr-block 0.0.0.0/0 \
    --nat-gateway-id nat-xxxxx
```

**RTO**: 10~15분
**RPO**: N/A

**향후 개선**:
- [ ] Multi-AZ NAT Gateway (추가 비용 ₩40,000/월)

---

### 시나리오 5: S3 데이터 손실 🟡 Medium

**증상**:
- 워크플로우 결과 파일 삭제됨
- 사용자 업로드 파일 손실

**복구 (S3 Versioning)**:
```bash
# 삭제된 객체 복구 (Versioning 활성화됨)
aws s3api list-object-versions \
    --bucket triflow-ai-prod \
    --prefix tenants/uuid-123/workflows/wf-456/

# 이전 버전으로 복구
aws s3api copy-object \
    --bucket triflow-ai-prod \
    --copy-source triflow-ai-prod/path/to/file?versionId=xxx \
    --key path/to/file
```

**RTO**: 30분 (수동 복구)
**RPO**: 0분 (모든 버전 보관)

**예방**:
- ✅ S3 Versioning 활성화됨
- ✅ S3 Object Lock 고려 (규제 요구 시)
- ✅ MFA Delete 고려

---

### 시나리오 6: 전체 Region 장애 🔴 Critical (극히 드묾)

**증상**:
- ap-northeast-2 (Seoul) 전체 장애
- AWS 서비스 접근 불가

**복구 (Cross-Region DR, 미구현)**:
```
현재: ap-northeast-2만 사용
→ Region 장애 시 복구 불가 ⚠️

향후 구현 (Phase 5):
1. Read Replica (ap-northeast-1, Tokyo)
2. S3 Cross-Region Replication
3. Route 53 Failover Policy
4. Lambda@Edge for CDN
```

**RTO**: 현재 불가 (향후 4시간 목표)
**RPO**: 현재 불가 (향후 15분 목표)

**확률**: 매우 낮음 (AWS 역사상 Region 전체 장애는 드묾)

---

## 🔄 백업 전략

### 1. RDS 자동 백업

**설정**:
```hcl
backup_retention_period = 7  # 7일 보관
backup_window          = "18:00-19:00"  # UTC (한국 03:00-04:00)
```

**기능**:
- 매일 자동 전체 백업
- Point-in-Time Recovery (PITR, 5분 단위)
- Multi-AZ Standby에도 백업 저장

**복구 방법**:
```bash
# 특정 시점으로 복구 (예: 1시간 전)
aws rds restore-db-instance-to-point-in-time \
    --source-db-instance-identifier triflow-ai-production-db \
    --target-db-instance-identifier triflow-ai-production-db-restored \
    --restore-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)

# 복구 완료 후 CNAME 변경 (10~15분)
# Application 재시작 또는 연결 문자열 업데이트
```

**RTO**: 1시간
**RPO**: 5분 ✅

### 2. RDS 수동 스냅샷

**스케줄**: 매주 일요일 03:00 KST

```bash
# 수동 스냅샷 생성
aws rds create-db-snapshot \
    --db-instance-identifier triflow-ai-production-db \
    --db-snapshot-identifier triflow-manual-$(date +%Y%m%d)

# 스냅샷 목록 확인
aws rds describe-db-snapshots \
    --db-instance-identifier triflow-ai-production-db \
    --query 'DBSnapshots[*].{ID:DBSnapshotIdentifier,Time:SnapshotCreateTime,Status:Status}'

# 스냅샷에서 복구
aws rds restore-db-instance-from-db-snapshot \
    --db-instance-identifier triflow-ai-production-db-restored \
    --db-snapshot-identifier triflow-manual-20260120
```

**보관 기간**: 30일
**RTO**: 30분
**RPO**: 최대 1주일

### 3. S3 백업

**자동 백업** (S3 Versioning):
- ✅ 모든 파일 버전 관리
- ✅ 삭제 마커도 보관
- ✅ 복구 즉시 가능

**Cross-Region Replication** (향후):
```hcl
# s3.tf에 추가 (Phase 5)
resource "aws_s3_bucket_replication_configuration" "main" {
  bucket = aws_s3_bucket.main.id

  rule {
    id     = "replicate-to-tokyo"
    status = "Enabled"

    destination {
      bucket        = aws_s3_bucket.dr.arn  # Tokyo 버킷
      storage_class = "STANDARD_IA"
    }
  }
}
```

### 4. ElastiCache 백업

**설정**:
```hcl
snapshot_retention_limit = 5  # 5일 보관
snapshot_window         = "17:00-18:00"  # UTC (한국 02:00-03:00)
```

**복구**:
```bash
# 스냅샷에서 복구
aws elasticache create-replication-group \
    --replication-group-id triflow-redis-restored \
    --snapshot-name triflow-redis-snapshot-20260120 \
    --cache-node-type cache.t4g.small \
    --num-cache-clusters 2
```

**RTO**: 15분
**RPO**: 최대 24시간 (일일 백업)

**주의**: Redis는 캐시이므로 데이터 손실 허용 가능

---

## 🔧 복구 절차 (Runbook)

### Runbook 1: RDS Failover (자동)

**감지**:
```
1. CloudWatch Alarm 발생
   - Slack #triflow-alerts: "🚨 RDS CPU High"

2. RDS 이벤트 확인
   aws rds describe-events --source-identifier triflow-ai-production-db

3. Failover 자동 진행 중 확인
   Event Message: "Multi-AZ failover started"
```

**조치**:
```
1. ⏳ 대기 (2~3분, 자동 복구)

2. 복구 확인
   - /health endpoint 정상 응답
   - CloudWatch Alarm 해제
   - Slack 알람: "✅ RDS recovered"

3. 사후 분석
   - RDS Performance Insights 확인
   - Slow Query Log 분석
   - 원인 파악 및 최적화
```

**담당자**: On-Call DevOps (자동 복구 모니터링만)

---

### Runbook 2: PITR 복구 (수동, 데이터 손상 시)

**시나리오**: 실수로 중요 데이터 삭제/변경

**절차**:
```bash
# 1. 영향 범위 확인
# - 언제 데이터가 손상되었는지 파악
# - 예: 2026-01-20 14:30에 실수로 DELETE 쿼리 실행

# 2. 복구 시점 결정
RESTORE_TIME="2026-01-20T14:25:00Z"  # UTC, 5분 전

# 3. PITR 복구 (새 인스턴스 생성)
aws rds restore-db-instance-to-point-in-time \
    --source-db-instance-identifier triflow-ai-production-db \
    --target-db-instance-identifier triflow-ai-production-db-pitr-$(date +%Y%m%d-%H%M) \
    --restore-time $RESTORE_TIME \
    --db-instance-class db.t4g.medium \
    --multi-az \
    --vpc-security-group-ids sg-xxxxx \
    --db-subnet-group-name triflow-ai-production-db-subnet-group

# 4. 복구 완료 대기 (10~15분)
aws rds wait db-instance-available \
    --db-instance-identifier triflow-ai-production-db-pitr-20260120-1430

# 5. 복구된 DB에서 데이터 확인
RESTORED_ENDPOINT=$(aws rds describe-db-instances \
    --db-instance-identifier triflow-ai-production-db-pitr-20260120-1430 \
    --query 'DBInstances[0].Endpoint.Address' \
    --output text)

psql -h $RESTORED_ENDPOINT -U triflow_admin -d triflow
> SELECT COUNT(*) FROM core.workflows;  # 데이터 확인

# 6a. 옵션 A: 복구된 DB를 Primary로 승격 (다운타임 발생)
# - ECS Service 중단
# - .env 파일 업데이트 (RDS_ENDPOINT 변경)
# - ECS Service 재시작

# 6b. 옵션 B: 필요한 데이터만 복사 (권장, 다운타임 최소)
pg_dump -h $RESTORED_ENDPOINT -U triflow_admin -t core.workflows | \
    psql -h $ORIGINAL_ENDPOINT -U triflow_admin -d triflow

# 7. 복구 검증
psql -h $ORIGINAL_ENDPOINT -U triflow_admin -d triflow
> SELECT COUNT(*) FROM core.workflows;  # 데이터 복구 확인

# 8. 임시 DB 삭제
aws rds delete-db-instance \
    --db-instance-identifier triflow-ai-production-db-pitr-20260120-1430 \
    --skip-final-snapshot
```

**RTO**: 1시간 (복구 DB 생성 15분 + 데이터 복사 30분 + 검증 15분)
**RPO**: 5분 ✅

**담당자**: Senior DevOps + DBA

---

### Runbook 3: 전체 인프라 재생성 (재해 복구)

**시나리오**: Terraform state 손실, 계정 해킹, Region 장애 등

**사전 준비**:
```bash
# 1. Terraform state 백업 (매일)
cd infrastructure/terraform
terraform state pull > ../../backups/terraform.tfstate.$(date +%Y%m%d)

# 2. RDS 스냅샷 백업 (매주)
aws rds create-db-snapshot \
    --db-instance-identifier triflow-ai-production-db \
    --db-snapshot-identifier triflow-weekly-$(date +%Y%m%d)

# 3. S3 데이터 백업 (선택사항)
aws s3 sync s3://triflow-ai-prod s3://triflow-ai-backup-$(date +%Y%m%d)
```

**복구 절차**:
```bash
# === 새 AWS 계정 또는 다른 Region ===

# 1. Terraform 코드 clone
git clone https://github.com/mugoori/TriFlow-AI.git
cd TriFlow-AI/infrastructure/terraform

# 2. terraform.tfvars 설정
cp terraform.tfvars.example terraform.tfvars
vim terraform.tfvars
# db_password, redis_auth_token 등 설정

# 3. Terraform 초기화 및 인프라 생성
terraform init
terraform apply  # 15~20분

# 4. RDS 스냅샷에서 복구 (백업이 있는 경우)
# 4a. 스냅샷을 새 Region으로 복사 (Cross-Region)
aws rds copy-db-snapshot \
    --source-db-snapshot-identifier arn:aws:rds:ap-northeast-2:123456789012:snapshot:triflow-weekly-20260120 \
    --target-db-snapshot-identifier triflow-weekly-20260120 \
    --source-region ap-northeast-2 \
    --region ap-northeast-1  # Tokyo

# 4b. 스냅샷에서 복구
aws rds restore-db-instance-from-db-snapshot \
    --db-instance-identifier triflow-ai-production-db \
    --db-snapshot-identifier triflow-weekly-20260120

# 5. S3 데이터 복구 (백업이 있는 경우)
aws s3 sync s3://triflow-ai-backup-20260120 s3://triflow-ai-prod

# 6. pgvector extension 설치
psql -h $(terraform output -raw rds_address) -U triflow_admin -d triflow
> CREATE EXTENSION vector;

# 7. Alembic 마이그레이션 (스냅샷 버전과 현재 코드 차이)
cd ../../backend
alembic upgrade head

# 8. ECR에 이미지 push
cd ..
./scripts/deploy-aws.sh production latest

# 9. 배포 검증
curl https://$(cd infrastructure/terraform && terraform output -raw alb_dns_name)/health

# 10. DNS 업데이트 (Route 53, 선택사항)
# 기존 도메인을 새 ALB로 포인팅
```

**RTO**: 4시간
- Terraform apply: 20분
- RDS 복구: 30분
- 데이터 복구: 1시간
- 검증: 30분
- DNS 전파: 1~2시간

**RPO**: 7일 (주간 백업 기준) 또는 5분 (PITR 사용 시)

**담당자**: DevOps Lead + CTO

---

## 📊 RTO/RPO 요약표

| 시나리오 | 확률 | 영향 | RTO | RPO | 복구 방식 |
|---------|:----:|:----:|----:|----:|----------|
| RDS Primary 장애 | 중간 | 높음 | **2~3분** | **0분** | 자동 (Multi-AZ Failover) |
| ECS Task 장애 | 높음 | 중간 | **2~3분** | N/A | 자동 (Auto Scaling) |
| ALB 장애 | 낮음 | 높음 | 1~4시간 | N/A | AWS Support |
| NAT 장애 | 낮음 | 낮음 | 10~15분 | N/A | 수동 (새 NAT 생성) |
| S3 데이터 손실 | 낮음 | 중간 | 30분 | **0분** | 수동 (Versioning) |
| Region 전체 장애 | 극히 낮음 | 최고 | 4시간 | 7일 | 수동 (Cross-Region) |

**평균 RTO**: **15분** (자동 복구 포함)
**평균 RPO**: **5분** (PITR 기준)

---

## 🧪 재해 복구 테스트 계획

### 월간 DR 테스트 (매월 첫째 주 일요일 03:00)

#### Test 1: RDS Failover (30분)
```bash
# Staging 환경에서 강제 Failover
aws rds reboot-db-instance \
    --db-instance-identifier triflow-ai-staging-db \
    --force-failover

# 검증:
# - Failover 시간 측정 (목표: <3분)
# - 애플리케이션 재연결 확인
# - 데이터 무결성 확인
```

#### Test 2: ECS Task 강제 종료 (15분)
```bash
# Task 강제 종료
TASK_ARN=$(aws ecs list-tasks --cluster triflow-ai-staging-cluster --query 'taskArns[0]' --output text)
aws ecs stop-task --cluster triflow-ai-staging-cluster --task $TASK_ARN

# 검증:
# - 새 Task 자동 시작 확인 (목표: <3분)
# - ALB Health Check 통과 확인
# - 사용자 영향 없음 확인
```

#### Test 3: PITR 복구 (1시간)
```bash
# 5분 전 시점으로 복구
aws rds restore-db-instance-to-point-in-time \
    --source-db-instance-identifier triflow-ai-staging-db \
    --target-db-instance-identifier triflow-ai-staging-db-pitr-test \
    --restore-time $(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%SZ)

# 검증:
# - 복구 시간 측정 (목표: <1시간)
# - 데이터 일치 확인
# - 임시 DB 삭제
```

### 분기별 DR 테스트 (분기별 1회, 토요일 심야)

#### Test 4: 전체 인프라 재생성 (4시간)
```bash
# 1. 현재 스냅샷 생성
# 2. Terraform destroy (Staging)
# 3. Terraform apply (재생성)
# 4. 스냅샷에서 복구
# 5. 통합 테스트

# 검증:
# - 전체 복구 시간 측정 (목표: <4시간)
# - Terraform 코드 정확성 확인
# - 복구 절차 문서 업데이트
```

---

## 📞 비상 연락망

### Escalation Path

| Level | 역할 | 담당자 | 연락처 | 대응 시간 |
|:-----:|------|--------|--------|-----------|
| **L1** | On-Call DevOps | DevOps 당직 | +82-10-XXXX-XXXX | 15분 이내 |
| **L2** | DevOps Lead | 홍길동 | +82-10-YYYY-YYYY | 30분 이내 |
| **L3** | CTO | 김철수 | +82-10-ZZZZ-ZZZZ | 1시간 이내 |
| **L4** | AWS Support | AWS Premium Support | Console | 15분 이내 (Critical) |

### 비상 대응 프로세스

```
장애 감지 (CloudWatch Alarm)
    ↓
L1: On-Call DevOps (15분 이내 대응)
    ├─ 자동 복구 확인
    ├─ 로그 분석
    └─ 초기 조치
    ↓
심각도 판단
    ├─ Critical → L2 Escalate (즉시)
    ├─ High → L2 Escalate (30분 내)
    └─ Medium → L1 처리
    ↓
L2: DevOps Lead
    ├─ 복구 절차 실행
    ├─ AWS Support 티켓
    └─ 고객 공지 (필요 시)
    ↓
복구 실패 시
    ↓
L3: CTO
    ├─ 비즈니스 결정
    ├─ 외부 전문가 투입
    └─ 고객사 직접 소통
```

---

## 📋 재해 복구 체크리스트

### 장애 발생 시 (실시간)

- [ ] CloudWatch Alarm 확인
- [ ] Slack #triflow-alerts 확인
- [ ] AWS Personal Health Dashboard 확인
- [ ] 영향 범위 파악 (사용자 수, 서비스 범위)
- [ ] 자동 복구 진행 중인지 확인 (Multi-AZ, Auto Scaling)
- [ ] 로그 수집 (CloudWatch Logs)
- [ ] 고객 공지 필요성 판단

### 복구 진행 중

- [ ] 복구 절차 Runbook 선택
- [ ] 복구 시작 시간 기록
- [ ] 진행 상황 Slack 업데이트 (30분마다)
- [ ] 백업 복구 시 데이터 무결성 검증
- [ ] Health Check 통과 확인

### 복구 완료 후

- [ ] 서비스 정상 동작 확인 (/health, API 테스트)
- [ ] 데이터 무결성 확인 (샘플 데이터 조회)
- [ ] CloudWatch Metrics 정상화 확인
- [ ] 복구 완료 시간 기록
- [ ] RTO/RPO 달성 여부 확인
- [ ] 고객 공지 (복구 완료)

### 사후 분석 (24시간 이내)

- [ ] 장애 원인 분석 (Root Cause Analysis)
- [ ] 타임라인 작성 (감지 → 복구 완료)
- [ ] 예방 조치 수립
- [ ] Runbook 업데이트
- [ ] 팀 회고 (Retrospective)
- [ ] 장애 보고서 작성

---

## 🔐 보안 사고 대응

### 시나리오: AWS 계정 해킹

**증상**:
- 알 수 없는 리소스 생성
- 비정상적인 비용 급증
- IAM 권한 변경

**즉시 조치**:
```bash
# 1. AWS 계정 루트 비밀번호 변경
# 2. MFA 활성화 (없을 경우)
# 3. IAM Access Key 전체 비활성화
aws iam list-access-keys --user-name terraform-deploy
aws iam update-access-key --access-key-id AKIA... --status Inactive

# 4. CloudTrail 로그 확인 (누가 무엇을?)
aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=RunInstances --max-results 50

# 5. 의심스러운 리소스 삭제
# 6. AWS Support에 보안 사고 신고
# 7. 새 Access Key 생성
```

**RTO**: 2시간
**RPO**: N/A

---

## 💾 백업 보관 정책

| 백업 유형 | 주기 | 보관 기간 | 저장 위치 | 비용/월 |
|----------|------|----------|----------|--------:|
| **RDS 자동 백업** | 매일 | 7일 | AWS 관리 | 포함 (₩0) |
| **RDS 수동 스냅샷** | 매주 | 30일 | S3 | ₩12,400 |
| **S3 Versioning** | 실시간 | 무제한 | S3 | ₩100 |
| **ElastiCache 스냅샷** | 매일 | 5일 | S3 | ₩500 |
| **Terraform State** | 매일 | 30일 | 로컬 + Git | ₩0 |

**총 백업 비용**: ₩13,000/월

---

## 📈 가용성 계산

### SLA (Service Level Agreement)

**목표**: 99.95% (연간 다운타임 < 4.4시간)

**컴포넌트별 가용성**:
```
ALB: 99.99% (AWS SLA)
ECS Fargate: 99.99% (AWS SLA)
RDS Multi-AZ: 99.95% (AWS SLA)
ElastiCache: 99.99% (Multi-AZ)

전체 가용성 = 99.99% × 99.99% × 99.95% × 99.99%
            ≈ 99.92%
```

**실제 목표**: 99.95% (RDS가 병목)

**허용 다운타임**:
- 월간: 22분
- 연간: 4.4시간

---

## 🎓 DR 교육 계획

### 신규 DevOps 교육 (Onboarding)

1. **DR 문서 숙지** (2시간)
   - 이 문서 읽기
   - Runbook 실습

2. **Staging 환경 DR 테스트** (4시간)
   - RDS Failover 실습
   - PITR 복구 실습
   - 전체 인프라 재생성 실습

3. **On-Call 당직 투입** (1주 후)

### 분기별 DR 훈련 (전체 팀)

- **시뮬레이션**: 특정 장애 시나리오 발생
- **역할극**: 각자 역할에 맞게 대응
- **타이머**: RTO 달성 여부 측정
- **회고**: 개선 사항 도출

---

## 🔗 참고 문서

- [AWS RDS Multi-AZ Failover](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZ.html)
- [AWS Well-Architected Framework - Reliability](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/welcome.html)
- [Terraform State 백업](https://www.terraform.io/docs/language/state/backup.html)
- [Architecture Decisions](./architecture-decisions.md)
- [Deployment Guide](./deployment-guide.md)

---

**문서 상태**: ✅ 초안 완성
**검토자**: DevOps Lead, CTO
**승인**: Pending
**다음 업데이트**: Phase 3 (DR 테스트 후)
