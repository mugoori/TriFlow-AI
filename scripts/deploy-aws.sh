#!/bin/bash

# ===================================================
# TriFlow AI - AWS ECS Fargate 배포 스크립트
# ===================================================
# 사용법:
#   ./scripts/deploy-aws.sh [환경] [이미지태그]
#   ./scripts/deploy-aws.sh production latest
#   ./scripts/deploy-aws.sh staging v1.2.3
# ===================================================

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 환경 변수
ENV=${1:-production}
IMAGE_TAG=${2:-latest}
REGION=${AWS_REGION:-ap-northeast-2}

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}🚀 TriFlow AI - AWS Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Environment: ${ENV}${NC}"
echo -e "${GREEN}Image Tag: ${IMAGE_TAG}${NC}"
echo -e "${GREEN}Region: ${REGION}${NC}"
echo ""

# AWS 계정 확인
echo -e "${YELLOW}📋 Checking AWS account...${NC}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")
if [ -z "$AWS_ACCOUNT_ID" ]; then
    echo -e "${RED}❌ AWS credentials not configured${NC}"
    echo -e "${YELLOW}Run: aws configure${NC}"
    exit 1
fi
echo -e "${GREEN}✅ AWS Account: ${AWS_ACCOUNT_ID}${NC}"

# 변수 설정
CLUSTER_NAME="triflow-ai-${ENV}-cluster"
SERVICE_NAME="triflow-ai-${ENV}-backend-service"
TASK_FAMILY="triflow-ai-${ENV}-backend"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
ECR_REPOSITORY="triflow-ai-backend"
IMAGE_URI="${ECR_REGISTRY}/${ECR_REPOSITORY}:${IMAGE_TAG}"

echo ""
echo -e "${YELLOW}📦 Step 1/6: Logging into ECR...${NC}"
aws ecr get-login-password --region ${REGION} | \
    docker login --username AWS --password-stdin ${ECR_REGISTRY}
echo -e "${GREEN}✅ ECR login successful${NC}"

echo ""
echo -e "${YELLOW}🏗️ Step 2/6: Building Docker image...${NC}"
echo -e "${BLUE}Building: triflow-backend:${IMAGE_TAG}${NC}"

# Docker 빌드 (멀티 플랫폼 지원)
docker build \
    --platform linux/amd64 \
    -t triflow-backend:${IMAGE_TAG} \
    -f backend/Dockerfile \
    ./backend

echo -e "${GREEN}✅ Docker build successful${NC}"

echo ""
echo -e "${YELLOW}⬆️ Step 3/6: Pushing image to ECR...${NC}"
docker tag triflow-backend:${IMAGE_TAG} ${IMAGE_URI}
docker push ${IMAGE_URI}
echo -e "${GREEN}✅ Image pushed: ${IMAGE_URI}${NC}"

echo ""
echo -e "${YELLOW}📝 Step 4/6: Updating ECS Task Definition...${NC}"

# 현재 Task Definition 조회
TASK_DEF_ARN=$(aws ecs describe-task-definition \
    --task-definition ${TASK_FAMILY} \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text 2>/dev/null || echo "")

if [ -z "$TASK_DEF_ARN" ]; then
    echo -e "${RED}❌ Task Definition not found: ${TASK_FAMILY}${NC}"
    echo -e "${YELLOW}Please run Terraform first to create ECS resources${NC}"
    exit 1
fi

# Task Definition JSON 추출 및 수정
TASK_DEFINITION=$(aws ecs describe-task-definition \
    --task-definition ${TASK_FAMILY} \
    --query 'taskDefinition' \
    --output json)

# 이미지 URI 업데이트
NEW_TASK_DEF=$(echo $TASK_DEFINITION | jq \
    --arg IMAGE "$IMAGE_URI" \
    'del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities, .registeredAt, .registeredBy) |
     .containerDefinitions[0].image = $IMAGE')

# 새 Task Definition 등록
NEW_TASK_ARN=$(echo "$NEW_TASK_DEF" | aws ecs register-task-definition \
    --cli-input-json file:///dev/stdin \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text)

echo -e "${GREEN}✅ New Task Definition registered: ${NEW_TASK_ARN}${NC}"

echo ""
echo -e "${YELLOW}♻️ Step 5/6: Updating ECS Service (Rolling Update)...${NC}"

# ECS Service 업데이트 (강제 새 배포)
aws ecs update-service \
    --cluster ${CLUSTER_NAME} \
    --service ${SERVICE_NAME} \
    --task-definition ${NEW_TASK_ARN} \
    --force-new-deployment \
    --query 'service.serviceName' \
    --output text

echo -e "${GREEN}✅ ECS service update initiated${NC}"

echo ""
echo -e "${YELLOW}🏥 Step 6/6: Waiting for deployment to stabilize...${NC}"
echo -e "${BLUE}This may take 2-5 minutes. Monitoring health checks...${NC}"

# 배포 완료 대기 (최대 10분)
aws ecs wait services-stable \
    --cluster ${CLUSTER_NAME} \
    --services ${SERVICE_NAME} \
    --region ${REGION}

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"

# 배포 정보 출력
echo ""
echo -e "${BLUE}📊 Deployment Summary:${NC}"
echo -e "   Cluster: ${CLUSTER_NAME}"
echo -e "   Service: ${SERVICE_NAME}"
echo -e "   Image: ${IMAGE_URI}"
echo -e "   Task Definition: ${NEW_TASK_ARN}"

# 실행 중인 Task 개수 확인
RUNNING_COUNT=$(aws ecs describe-services \
    --cluster ${CLUSTER_NAME} \
    --services ${SERVICE_NAME} \
    --query 'services[0].runningCount' \
    --output text)

DESIRED_COUNT=$(aws ecs describe-services \
    --cluster ${CLUSTER_NAME} \
    --services ${SERVICE_NAME} \
    --query 'services[0].desiredCount' \
    --output text)

echo -e "   Running Tasks: ${RUNNING_COUNT}/${DESIRED_COUNT}"

# ALB 정보
echo ""
echo -e "${BLUE}🌐 Access Points:${NC}"

# ALB DNS 이름 가져오기 (Tag 기반)
ALB_DNS=$(aws elbv2 describe-load-balancers \
    --query "LoadBalancers[?contains(Tags[?Key=='Name'].Value, '${ENV}')].DNSName | [0]" \
    --output text 2>/dev/null || echo "")

if [ -n "$ALB_DNS" ]; then
    echo -e "   ALB: https://${ALB_DNS}"
    echo -e "   Health: https://${ALB_DNS}/health"
else
    echo -e "${YELLOW}   (ALB DNS not found, check AWS Console)${NC}"
fi

echo ""
echo -e "${BLUE}📌 Next Steps:${NC}"
echo "   1. Verify health: curl https://${ALB_DNS}/health"
echo "   2. Check logs: aws logs tail ${CLOUDWATCH_LOG_GROUP:-/aws/ecs/${TASK_FAMILY}} --follow"
echo "   3. Monitor: aws ecs describe-services --cluster ${CLUSTER_NAME} --services ${SERVICE_NAME}"
echo ""

# Slack 알림 (선택사항)
if [ -n "${SLACK_WEBHOOK_URL}" ]; then
    echo -e "${YELLOW}📣 Sending Slack notification...${NC}"
    curl -X POST ${SLACK_WEBHOOK_URL} \
        -H 'Content-Type: application/json' \
        -d "{
            \"text\": \":rocket: TriFlow AI Deployment Success\",
            \"blocks\": [
                {
                    \"type\": \"section\",
                    \"text\": {
                        \"type\": \"mrkdwn\",
                        \"text\": \"*Deployment Complete* :white_check_mark:\\n*Environment:* \`${ENV}\`\\n*Image:* \`${IMAGE_TAG}\`\\n*Tasks:* ${RUNNING_COUNT}/${DESIRED_COUNT}\"
                    }
                }
            ]
        }" 2>/dev/null || true
    echo -e "${GREEN}✅ Slack notification sent${NC}"
fi

echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
