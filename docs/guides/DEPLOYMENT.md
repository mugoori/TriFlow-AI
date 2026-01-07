# TriFlow AI - Deployment Guide

## Overview

This guide covers deploying TriFlow AI to production environments.

## Prerequisites

- Docker & Docker Compose
- Git
- Valid API keys (Anthropic, Google OAuth, etc.)

## Quick Start

### 1. Clone Repository
```bash
git clone https://github.com/your-org/triflow-ai.git
cd triflow-ai
```

### 2. Configure Environment

Copy the example environment file:
```bash
cp .env.production.example .env.production
```

Edit `.env.production` and fill in required values:
- `POSTGRES_PASSWORD`: Strong database password
- `REDIS_PASSWORD`: Redis password
- `MINIO_SECRET_KEY`: MinIO secret
- `ANTHROPIC_API_KEY`: Your Anthropic API key
- `SECRET_KEY`: Generate with `openssl rand -hex 32`
- `GRAFANA_PASSWORD`: Grafana admin password

### 3. Deploy

**Linux/macOS:**
```bash
./scripts/deploy.sh production --build --migrate
```

**Windows (PowerShell):**
```powershell
.\scripts\deploy.ps1 -Environment production -Build -Migrate
```

### 4. Verify Deployment

Check health:
```bash
./scripts/health-check.sh
```

Or manually:
```bash
curl http://localhost:8000/health
```

## Environment Configuration

### Environment Files

| File | Purpose |
|------|---------|
| `.env.example` | Template for development |
| `.env.staging.example` | Template for staging |
| `.env.production.example` | Template for production |

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `POSTGRES_PASSWORD` | Database password | Strong random string |
| `REDIS_PASSWORD` | Redis password | Strong random string |
| `SECRET_KEY` | JWT signing key | 64-char hex string |
| `ANTHROPIC_API_KEY` | AI API key | `sk-ant-...` |

## Architecture

### Production Docker Compose

```
┌─────────────────────────────────────────────────────────────┐
│                    triflow-external                          │
│  ┌─────────┐  ┌──────────┐  ┌────────────┐  ┌───────────┐  │
│  │ Backend │  │Prometheus│  │  Grafana   │  │   Nginx   │  │
│  │  :8000  │  │  :9090   │  │   :3000    │  │  :80/443  │  │
│  └────┬────┘  └────┬─────┘  └─────┬──────┘  └─────┬─────┘  │
└───────┼────────────┼──────────────┼───────────────┼────────┘
        │            │              │               │
┌───────┼────────────┼──────────────┼───────────────┘
│       │  triflow-internal (isolated)
│  ┌────┴────┐  ┌─────────┐  ┌─────────┐
│  │Postgres │  │  Redis  │  │  MinIO  │
│  │  :5432  │  │  :6379  │  │  :9000  │
│  └─────────┘  └─────────┘  └─────────┘
└─────────────────────────────────────────
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| Backend | 8000 | FastAPI application |
| PostgreSQL | 5432 | Primary database |
| Redis | 6379 | Cache & sessions |
| MinIO | 9000/9001 | Object storage |
| Prometheus | 9090 | Metrics collection |
| Grafana | 3000 | Dashboards |
| Nginx | 80/443 | Reverse proxy (optional) |

## Monitoring

### Prometheus

Access at `http://localhost:9090`

Key metrics:
- `http_requests_total`: Request count
- `http_request_duration_seconds`: Response times
- `up`: Service health

### Grafana

Access at `http://localhost:3000`
- Default user: `admin`
- Password: Set in `.env.production`

Pre-configured dashboards:
- TriFlow AI Overview

## Maintenance

### Database Backup

```bash
./scripts/backup.sh /path/to/backups
```

Backups are automatically cleaned up after 7 days.

### Restore from Backup

```bash
# PostgreSQL
gunzip -c backups/postgres_20231201_120000.sql.gz | \
  docker exec -i triflow-postgres psql -U triflow triflow_ai

# Redis
docker cp backups/redis_20231201_120000.rdb triflow-redis:/data/dump.rdb
docker restart triflow-redis
```

### Log Access

```bash
# All logs
docker-compose -f docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker-compose.prod.yml logs -f backend
```

### Updating

```bash
git pull
./scripts/deploy.sh production --build --migrate
```

## Scaling

### Horizontal Scaling (Backend)

In `docker-compose.prod.yml`:
```yaml
backend:
  deploy:
    replicas: 3
```

Then use a load balancer (Nginx or external).

### Resource Limits

Adjust in `docker-compose.prod.yml`:
```yaml
deploy:
  resources:
    limits:
      memory: 4G
    reservations:
      memory: 1G
```

## Troubleshooting

### Service Not Starting

Check logs:
```bash
docker-compose -f docker-compose.prod.yml logs backend
```

### Database Connection Issues

Verify PostgreSQL is healthy:
```bash
docker exec triflow-postgres pg_isready -U triflow
```

### Memory Issues

Check resource usage:
```bash
docker stats
```

Adjust limits in `docker-compose.prod.yml`.

## SSL/TLS Setup (Let's Encrypt)

### Initial Setup

```bash
chmod +x scripts/init-letsencrypt.sh scripts/renew-certs.sh

# Get SSL certificate
./scripts/init-letsencrypt.sh your-domain.com your@email.com

# Start with Nginx (includes SSL)
docker-compose -f docker-compose.prod.yml --profile with-nginx up -d
```

### Auto-Renewal

Add to crontab (`crontab -e`):
```bash
0 0 1 * * cd /opt/triflow-ai && ./scripts/renew-certs.sh >> /var/log/cert-renewal.log 2>&1
```

---

## GitHub Actions CI/CD

### Required Secrets

Configure in GitHub Repository > Settings > Secrets:

| Secret | Description |
|--------|-------------|
| `STAGING_HOST` | Staging server IP |
| `STAGING_USER` | SSH username |
| `STAGING_SSH_KEY` | SSH private key |
| `PRODUCTION_HOST` | Production server IP |
| `PRODUCTION_USER` | SSH username |
| `PRODUCTION_SSH_KEY` | SSH private key |
| `SLACK_WEBHOOK_URL` | Notifications |

### Deployment Workflows

| Workflow | Trigger | Description |
|----------|---------|-------------|
| `backend-ci.yml` | Push to `main`/`develop` | Lint, test, coverage |
| `docker-build.yml` | Push to `main` | Build Docker images |
| `deploy.yml` | Tag `v*.*.*` or manual | Deploy to staging/production |

### Manual Deploy

1. Go to Actions > Deploy
2. Click "Run workflow"
3. Select environment (staging/production)
4. Click "Run workflow"

### Automatic Deploy

Push a version tag:
```bash
git tag v1.0.0
git push origin v1.0.0
```

---

## Security Checklist

- [ ] Change all default passwords
- [ ] Generate unique `SECRET_KEY`
- [ ] Configure HTTPS (via Nginx)
- [ ] Restrict CORS origins
- [ ] Enable firewall rules
- [ ] Set up regular backups
- [ ] Configure log rotation
- [ ] GitHub secrets configured
- [ ] SSH key authentication only
- [ ] `.env.production` not in git
