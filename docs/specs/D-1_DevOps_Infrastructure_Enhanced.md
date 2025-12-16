# D-1. DevOps & Infrastructure - Enhanced

## 문서 정보
- **문서 ID**: D-1
- **버전**: 3.0 (V7 Intent + Orchestrator)
- **최종 수정일**: 2025-12-16
- **상태**: Active Development
- **관련 문서**:
  - B-1 System Architecture
  - B-3-3 V7 Intent Router 설계
  - B-3-4 Orchestrator 설계
  - C-1 Development Plan
  - C-5 Security & Compliance
  - D-3 Operation Runbook

## 목차
1. [인프라 개요](#1-인프라-개요)
2. [CI/CD 파이프라인](#2-cicd-파이프라인)
3. [Kubernetes 설정](#3-kubernetes-설정)
4. [V7 Intent Router & Orchestrator 배포](#4-v7-intent-router--orchestrator-배포)
5. [설정 및 비밀 관리](#5-설정-및-비밀-관리)
6. [백업 및 DR](#6-백업-및-dr)
7. [운영 자동화](#7-운영-자동화)

---

## 1. 인프라 개요

### 1.1 인프라 토폴로지 (AWS 클라우드)

```
┌──────────────────────────────────────────────────────────────┐
│                      Internet (Public)                       │
└──────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                AWS Application Load Balancer                 │
│  - HTTPS (443) Listener                                      │
│  - TLS Termination                                           │
│  - Health Check: /health                                     │
└──────────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Public      │  │  Private     │  │  Private     │
│  Subnet      │  │  Subnet      │  │  Subnet      │
│  (AZ-1)      │  │  (App, AZ-1) │  │  (DB, AZ-1)  │
│              │  │              │  │              │
│  NAT Gateway │  │  Services    │  │  PostgreSQL  │
│  Bastion     │  │  Pods        │  │  Redis       │
└──────────────┘  └──────────────┘  └──────────────┘

        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Public      │  │  Private     │  │  Private     │
│  Subnet      │  │  Subnet      │  │  Subnet      │
│  (AZ-2)      │  │  (App, AZ-2) │  │  (DB, AZ-2)  │
│              │  │              │  │              │
│  NAT Gateway │  │  Services    │  │  PostgreSQL  │
│              │  │  Pods        │  │  Replica     │
└──────────────┘  └──────────────┘  └──────────────┘
```

**VPC 설정**:
- **CIDR**: 10.0.0.0/16
- **Public Subnet**: 10.0.1.0/24, 10.0.2.0/24 (AZ-1, AZ-2)
- **Private Subnet (App)**: 10.0.10.0/24, 10.0.11.0/24
- **Private Subnet (DB)**: 10.0.20.0/24, 10.0.21.0/24

---

## 2. CI/CD 파이프라인

### 2.1 CI 파이프라인 (GitHub Actions)

**.github/workflows/ci.yml**:
```yaml
name: CI Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements-dev.txt
      - name: Run pylint
        run: pylint src/
      - name: Run mypy
        run: mypy src/

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_DB: test_db
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_password
        ports:
          - 5432:5432
      redis:
        image: redis:7
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: |
          pytest tests/ --cov=src --cov-report=xml --cov-fail-under=80
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml

  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Bandit (SAST)
        run: |
          pip install bandit
          bandit -r src/ -f json -o bandit-report.json
      - name: Run Trivy (Container Scan)
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          format: 'sarif'
          output: 'trivy-results.sarif'

  build:
    runs-on: ubuntu-latest
    needs: [lint, test, security-scan]
    steps:
      - uses: actions/checkout@v3
      - name: Build Docker image
        run: |
          docker build -t factory-ai/judgment-service:${{ github.sha }} .
      - name: Push to registry
        run: |
          docker push factory-ai/judgment-service:${{ github.sha }}
```

### 2.2 CD 파이프라인 (ArgoCD GitOps)

**.github/workflows/cd.yml**:
```yaml
name: CD Pipeline

on:
  workflow_run:
    workflows: ["CI Pipeline"]
    types:
      - completed
    branches: [main]

jobs:
  deploy-staging:
    runs-on: ubuntu-latest
    if: ${{ github.event.workflow_run.conclusion == 'success' }}
    steps:
      - uses: actions/checkout@v3

      - name: Update Helm values (Staging)
        run: |
          sed -i 's/tag: .*/tag: ${{ github.sha }}/' helm/staging-values.yaml

      - name: Commit and push
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          git add helm/staging-values.yaml
          git commit -m "Update staging image: ${{ github.sha }}"
          git push

      # ArgoCD가 자동으로 Git 변경 감지 및 배포

  deploy-production:
    runs-on: ubuntu-latest
    needs: deploy-staging
    environment:
      name: production
      url: https://api.factory-ai.com
    steps:
      - uses: actions/checkout@v3

      - name: Update Helm values (Production)
        run: |
          sed -i 's/tag: .*/tag: ${{ github.sha }}/' helm/production-values.yaml

      - name: Commit and push
        run: |
          git add helm/production-values.yaml
          git commit -m "Update production image: ${{ github.sha }}"
          git push
```

**ArgoCD Application 설정**:
```yaml
# argocd/judgment-service-prod.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: judgment-service-prod
  namespace: argocd
spec:
  project: factory-ai
  source:
    repoURL: https://github.com/factory-ai/platform
    targetRevision: main
    path: helm/judgment-service
    helm:
      valueFiles:
        - production-values.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: production
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

---

## 3. Kubernetes 설정

### 3.1 Namespace 구조

```yaml
# namespaces.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    environment: production
---
apiVersion: v1
kind: Namespace
metadata:
  name: staging
  labels:
    environment: staging
---
apiVersion: v1
kind: Namespace
metadata:
  name: monitoring
  labels:
    environment: shared
```

### 3.2 ResourceQuota 및 LimitRange

**Production Namespace Quota**:
```yaml
# resource-quota-production.yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: production-quota
  namespace: production
spec:
  hard:
    requests.cpu: "50"
    requests.memory: "100Gi"
    limits.cpu: "100"
    limits.memory: "200Gi"
    persistentvolumeclaims: "20"
    services.loadbalancers: "2"
```

**LimitRange** (기본 리소스 제한):
```yaml
# limit-range-production.yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: production-limit-range
  namespace: production
spec:
  limits:
  - max:
      cpu: "4"
      memory: "8Gi"
    min:
      cpu: "100m"
      memory: "128Mi"
    default:
      cpu: "500m"
      memory: "512Mi"
    defaultRequest:
      cpu: "250m"
      memory: "256Mi"
    type: Container
```

---

## 4. V7 Intent Router & Orchestrator 배포

### 4.1 Intent Router 서비스 배포

**deployment-intent-router.yaml**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: intent-router
  namespace: production
  labels:
    app: intent-router
    version: v7
spec:
  replicas: 3
  selector:
    matchLabels:
      app: intent-router
  template:
    metadata:
      labels:
        app: intent-router
        version: v7
    spec:
      containers:
        - name: intent-router
          image: factory-ai/intent-router:v7.0.0
          ports:
            - containerPort: 8010
          env:
            - name: ANTHROPIC_API_KEY
              valueFrom:
                secretKeyRef:
                  name: anthropic-secrets
                  key: api-key
            - name: DEFAULT_MODEL
              value: "claude-3-haiku-20240307"
            - name: INTENT_CLASSIFICATION_TIMEOUT
              value: "300"  # ms
          resources:
            requests:
              cpu: "250m"
              memory: "512Mi"
            limits:
              cpu: "1000m"
              memory: "1Gi"
          livenessProbe:
            httpGet:
              path: /health
              port: 8010
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /ready
              port: 8010
            initialDelaySeconds: 5
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: intent-router
  namespace: production
spec:
  selector:
    app: intent-router
  ports:
    - port: 8010
      targetPort: 8010
  type: ClusterIP
```

### 4.2 Orchestrator 서비스 배포

**deployment-orchestrator.yaml**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orchestrator
  namespace: production
  labels:
    app: orchestrator
    version: v1
spec:
  replicas: 2
  selector:
    matchLabels:
      app: orchestrator
  template:
    metadata:
      labels:
        app: orchestrator
    spec:
      containers:
        - name: orchestrator
          image: factory-ai/orchestrator:v1.0.0
          ports:
            - containerPort: 8020
          env:
            - name: ANTHROPIC_API_KEY
              valueFrom:
                secretKeyRef:
                  name: anthropic-secrets
                  key: api-key
            - name: PLAN_GENERATION_MODEL
              value: "claude-3-5-sonnet-20241022"
            - name: PLAN_GENERATION_TIMEOUT
              value: "500"  # ms
            - name: INTENT_ROUTER_URL
              value: "http://intent-router:8010"
            - name: DATA_LAYER_URL
              value: "http://data-layer:8030"
            - name: JUDGMENT_ENGINE_URL
              value: "http://judgment-engine:8040"
            - name: RULE_ENGINE_URL
              value: "http://rule-engine:8050"
          resources:
            requests:
              cpu: "500m"
              memory: "1Gi"
            limits:
              cpu: "2000m"
              memory: "2Gi"
          livenessProbe:
            httpGet:
              path: /health
              port: 8020
            initialDelaySeconds: 15
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /ready
              port: 8020
            initialDelaySeconds: 10
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: orchestrator
  namespace: production
spec:
  selector:
    app: orchestrator
  ports:
    - port: 8020
      targetPort: 8020
  type: ClusterIP
```

### 4.3 HPA 설정 (Intent Router & Orchestrator)

**hpa-intent-router.yaml**:
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: intent-router-hpa
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: intent-router
  minReplicas: 3
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Pods
      pods:
        metric:
          name: intent_classification_latency_p95
        target:
          type: AverageValue
          averageValue: "300m"  # 300ms
```

**hpa-orchestrator.yaml**:
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: orchestrator-hpa
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: orchestrator
  minReplicas: 2
  maxReplicas: 8
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Pods
      pods:
        metric:
          name: orchestrator_plan_latency_p95
        target:
          type: AverageValue
          averageValue: "500m"  # 500ms
```

### 4.4 서비스 간 의존성 (15 노드 타입)

**서비스 토폴로지**:
```
┌─────────────────────────────────────────────────────────────┐
│                    V7 Intent Router                          │
│        (14개 V7 Intent 분류, Claude Haiku)                   │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                     Orchestrator                             │
│    (Route Target → Plan 생성, Claude Sonnet)                │
└─────────────────────────────────────────────────────────────┘
          │               │               │
          ▼               ▼               ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│  Data Layer   │ │   Judgment    │ │  Rule Engine  │
│  (DATA 노드)  │ │(JUDGMENT 노드)│ │ (SWITCH 노드) │
└───────────────┘ └───────────────┘ └───────────────┘
          │               │               │
          └───────────────┼───────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│               Workflow Engine (15 노드)                      │
│  P0: DATA, JUDGMENT, CODE, SWITCH, ACTION                   │
│  P1: BI, MCP, TRIGGER, WAIT, APPROVAL                       │
│  P2: PARALLEL, COMPENSATION, DEPLOY, ROLLBACK, SIMULATE     │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. 설정 및 비밀 관리

### 5.1 ConfigMap (비민감 설정)

```yaml
# configmap-judgment-service.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: judgment-service-config
  namespace: production
data:
  REDIS_URL: "redis://redis-master:6379"
  POSTGRES_HOST: "postgresql-primary"
  POSTGRES_PORT: "5432"
  POSTGRES_DB: "factory_ai"
  LOG_LEVEL: "INFO"
  CACHE_TTL: "300"
  RULE_TIMEOUT_MS: "500"
  LLM_TIMEOUT_MS: "15000"
```

### 5.2 Secret (민감 정보)

**Kubernetes Secret**:
```yaml
# secret-judgment-service.yaml
apiVersion: v1
kind: Secret
metadata:
  name: judgment-service-secret
  namespace: production
type: Opaque
stringData:
  POSTGRES_USER: "postgres"
  POSTGRES_PASSWORD: "{{encrypted}}"
  OPENAI_API_KEY: "sk-{{encrypted}}"
  ANTHROPIC_API_KEY: "sk-ant-{{encrypted}}"
  JWT_SECRET_KEY: "{{encrypted}}"
```

**Sealed Secrets** (Git 저장 안전):
```bash
# SealedSecret 생성 (kubeseal)
kubeseal --format=yaml < secret-judgment-service.yaml > sealed-secret-judgment-service.yaml

# Git에 저장 (암호화됨)
git add sealed-secret-judgment-service.yaml
git commit -m "Add sealed secret for judgment service"
```

### 5.3 External Secrets (AWS Secrets Manager)

```yaml
# external-secret-judgment.yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: judgment-service-secret
  namespace: production
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: judgment-service-secret
    creationPolicy: Owner
  data:
  - secretKey: OPENAI_API_KEY
    remoteRef:
      key: factory-ai/openai-api-key
  - secretKey: POSTGRES_PASSWORD
    remoteRef:
      key: factory-ai/postgres-password
```

---

## 6. 백업 및 DR

### 6.1 PostgreSQL 백업 전략

#### 6.1.1 Full Backup (pg_dump)

**CronJob** (Kubernetes):
```yaml
# cronjob-postgres-backup.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
  namespace: production
spec:
  schedule: "0 3 * * *"  # 매일 03:00 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: postgres-backup
            image: postgres:14-alpine
            command:
            - /bin/sh
            - -c
            - |
              DATE=$(date +%Y%m%d)
              pg_dump -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -F c -f /backup/factory_ai_$DATE.dump
              gzip /backup/factory_ai_$DATE.dump
              aws s3 cp /backup/factory_ai_$DATE.dump.gz s3://factory-ai-backups/postgres/daily/
              rm /backup/factory_ai_$DATE.dump.gz
            env:
            - name: POSTGRES_HOST
              value: "postgresql-primary"
            - name: POSTGRES_USER
              valueFrom:
                secretKeyRef:
                  name: postgres-secret
                  key: username
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: postgres-secret
                  key: password
            - name: POSTGRES_DB
              value: "factory_ai"
            volumeMounts:
            - name: backup-storage
              mountPath: /backup
          volumes:
          - name: backup-storage
            emptyDir: {}
          restartPolicy: OnFailure
```

#### 6.1.2 WAL Archiving (Continuous Backup)

**postgresql.conf**:
```conf
wal_level = replica
archive_mode = on
archive_command = 'test ! -f /archive/%f && cp %p /archive/%f'
archive_timeout = 300  # 5분마다 WAL 파일 생성
```

**WAL 아카이브 → S3 업로드**:
```bash
#!/bin/bash
# wal_archive.sh

WAL_FILE=$1
S3_BUCKET="s3://factory-ai-backups/postgres/wal/"

# S3 업로드
aws s3 cp "$WAL_FILE" "$S3_BUCKET"

# 로컬 삭제 (옵션)
# rm "$WAL_FILE"
```

### 6.2 DR (Disaster Recovery)

**RTO (Recovery Time Objective)**: 4시간
**RPO (Recovery Point Objective)**: 30분

#### 6.2.1 DR 사이트 구성 (Cross-Region)

```
Primary Site (us-east-1)      DR Site (us-west-2)
┌───────────────────┐         ┌───────────────────┐
│  EKS Cluster      │         │  EKS Cluster      │
│  (Active)         │         │  (Standby)        │
├───────────────────┤         ├───────────────────┤
│  PostgreSQL       │ ──WAL──>│  PostgreSQL       │
│  (Primary)        │Streaming│  (Standby)        │
├───────────────────┤         ├───────────────────┤
│  S3 Backup        │ ──────> │  S3 Backup        │
│  (Replication)    │Cross-Rgn│  (Replica)        │
└───────────────────┘         └───────────────────┘
```

**DR Failover 절차**:
1. Primary Site 장애 확인 (Monitoring, Health Check)
2. DR Site PostgreSQL Standby → Primary 승격
   ```sql
   SELECT pg_promote();
   ```
3. DR Site 서비스 활성화 (Replicas 증가)
   ```bash
   kubectl scale deployment/judgment-service --replicas=3 -n production
   ```
4. DNS 변경 (Route53)
   ```
   api.factory-ai.com → DR ALB
   ```
5. 정합성 검증 (D-3 체크리스트)
6. 고객사 공지

---

## 7. 운영 자동화

### 7.1 자동 스케일링 (HPA)

**Judgment Service HPA**:
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: judgment-service-hpa
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: judgment-service
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Pods
    pods:
      metric:
        name: request_queue_length
      target:
        type: AverageValue
        averageValue: "50"
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Pods
        value: 1
        periodSeconds: 60
```

### 7.2 자동 복구 (Self-Healing)

**Liveness Probe** (서비스 생존 확인):
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8010
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3  # 3회 연속 실패 시 재시작
```

**Readiness Probe** (트래픽 수신 준비):
```yaml
readinessProbe:
  httpGet:
    path: /ready
    port: 8010
  initialDelaySeconds: 10
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 2  # 2회 연속 실패 시 트래픽 제외
```

---

## 결론

본 문서(D-1)는 **AI Factory Decision Engine** 의 DevOps 및 인프라 설정을 상세히 수립하였다.

### 주요 성과
1. **인프라 토폴로지**: VPC 3계층 분리 (Public, Application, Database)
2. **CI/CD 파이프라인**: GitHub Actions (CI), ArgoCD (CD GitOps)
3. **Kubernetes 설정**: Namespace, ResourceQuota, HPA
4. **V7 Intent Router 배포**: 3 Replicas, Claude Haiku, 300ms 타임아웃
5. **Orchestrator 배포**: 2 Replicas, Claude Sonnet, 500ms 타임아웃
6. **15 노드 서비스 토폴로지**: Intent Router → Orchestrator → Data/Judgment/Rule → Workflow
7. **설정/비밀 관리**: ConfigMap, Sealed Secrets, External Secrets, Anthropic API Key
8. **백업 전략**: 일 1회 Full Backup, WAL Archiving (실시간)
9. **DR 계획**: Cross-Region (RTO 4h, RPO 30m)
10. **운영 자동화**: HPA (Intent Router, Orchestrator 포함), Self-Healing

### 다음 단계
1. Kubernetes 클러스터 구축 (EKS)
2. CI/CD 파이프라인 구성
3. 백업 자동화 테스트
4. DR 훈련 (연 1회)

---

## 문서 이력
| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2025-11-01 | DevOps Team | 초안 작성 |
| 2.0 | 2025-11-26 | DevOps Team | Enhanced 버전 (CI/CD, Kubernetes, 백업/DR 상세 추가) |
| 3.0 | 2025-12-16 | DevOps Team | V7 Intent + Orchestrator 배포 추가: Intent Router Deployment (3 Replicas, Haiku), Orchestrator Deployment (2 Replicas, Sonnet), HPA 설정 (Latency 기반), 15노드 서비스 토폴로지 |
