#!/bin/bash

# LocalStack 초기화 스크립트
# AWS 서비스 로컬 에뮬레이션 설정

set -e

echo "🚀 Initializing LocalStack for TriFlow AI..."

# AWS CLI를 LocalStack endpoint로 설정
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=ap-northeast-2
ENDPOINT_URL="http://localhost:4566"

# awslocal alias (선택사항)
alias awslocal="aws --endpoint-url=$ENDPOINT_URL"

# 1. S3 버킷 생성
echo "📦 Creating S3 bucket..."
aws --endpoint-url=$ENDPOINT_URL s3 mb s3://triflow-ai-local || true

# S3 버킷 정책 설정
aws --endpoint-url=$ENDPOINT_URL s3api put-bucket-versioning \
  --bucket triflow-ai-local \
  --versioning-configuration Status=Enabled || true

# 2. Secrets Manager 시크릿 생성
echo "🔐 Creating Secrets Manager secrets..."

# Database secret
aws --endpoint-url=$ENDPOINT_URL secretsmanager create-secret \
  --name triflow/local/database \
  --secret-string '{"username":"triflow","password":"triflow123","host":"postgres-test","port":"5432","database":"triflow_test"}' \
  || true

# JWT secret
aws --endpoint-url=$ENDPOINT_URL secretsmanager create-secret \
  --name triflow/local/jwt \
  --secret-string '{"secret_key":"local-dev-secret-key-for-testing-only"}' \
  || true

# Anthropic API key (테스트용)
aws --endpoint-url=$ENDPOINT_URL secretsmanager create-secret \
  --name triflow/local/anthropic \
  --secret-string '{"api_key":"sk-ant-test-key"}' \
  || true

# 3. CloudWatch Log Groups 생성
echo "📊 Creating CloudWatch Log Groups..."
aws --endpoint-url=$ENDPOINT_URL logs create-log-group \
  --log-group-name /local/triflow/backend || true

aws --endpoint-url=$ENDPOINT_URL logs create-log-group \
  --log-group-name /local/triflow/rds || true

# 4. ECR Repository 생성
echo "🐳 Creating ECR repository..."
aws --endpoint-url=$ENDPOINT_URL ecr create-repository \
  --repository-name triflow-ai-backend \
  --image-scanning-configuration scanOnPush=true || true

# 5. ECS Cluster 생성 (테스트용)
echo "⚙️ Creating ECS cluster..."
aws --endpoint-url=$ENDPOINT_URL ecs create-cluster \
  --cluster-name triflow-local || true

# 6. IAM Role 생성 (테스트용)
echo "🔑 Creating IAM roles..."
aws --endpoint-url=$ENDPOINT_URL iam create-role \
  --role-name triflow-ecs-task-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ecs-tasks.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }' || true

# 7. S3 테스트 파일 업로드
echo "📄 Uploading test files to S3..."
echo "Test workflow result" > /tmp/test-workflow.json
aws --endpoint-url=$ENDPOINT_URL s3 cp /tmp/test-workflow.json s3://triflow-ai-local/tenants/test-tenant/workflows/test-workflow.json || true

echo ""
echo "✅ LocalStack initialization complete!"
echo ""
echo "📌 LocalStack Endpoints:"
echo "   - S3: http://localhost:4566"
echo "   - Secrets Manager: http://localhost:4566"
echo "   - CloudWatch: http://localhost:4566"
echo "   - ECR: http://localhost:4566"
echo ""
echo "🔧 Test commands:"
echo "   aws --endpoint-url=http://localhost:4566 s3 ls s3://triflow-ai-local"
echo "   aws --endpoint-url=http://localhost:4566 secretsmanager list-secrets"
echo ""
echo "🧪 Run tests with:"
echo "   cd backend && pytest tests/test_aws_services.py"
