#!/bin/bash
# ===================================================
# TriFlow AI - Production Deployment Script
# ===================================================
# Usage:
#   ./scripts/deploy.sh [environment] [options]
#
# Environments:
#   staging     - Deploy to staging
#   production  - Deploy to production
#
# Options:
#   --build     - Force rebuild images
#   --migrate   - Run database migrations
#   --restart   - Restart services only
#   --logs      - Show logs after deployment
# ===================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENVIRONMENT="${1:-staging}"
COMPOSE_FILE="docker-compose.prod.yml"

# Parse options
BUILD=false
MIGRATE=false
RESTART=false
SHOW_LOGS=false

for arg in "$@"; do
    case $arg in
        --build) BUILD=true ;;
        --migrate) MIGRATE=true ;;
        --restart) RESTART=true ;;
        --logs) SHOW_LOGS=true ;;
    esac
done

# Functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_requirements() {
    log_info "Checking requirements..."

    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi

    log_success "All requirements satisfied"
}

load_env() {
    local env_file=".env.${ENVIRONMENT}"

    if [ ! -f "$PROJECT_DIR/$env_file" ]; then
        log_error "Environment file not found: $env_file"
        log_info "Create one from .env.${ENVIRONMENT}.example"
        exit 1
    fi

    log_info "Loading environment: $ENVIRONMENT"
    export $(grep -v '^#' "$PROJECT_DIR/$env_file" | xargs)
}

validate_env() {
    log_info "Validating environment variables..."

    local required_vars=(
        "POSTGRES_PASSWORD"
        "REDIS_PASSWORD"
        "MINIO_SECRET_KEY"
        "ANTHROPIC_API_KEY"
        "SECRET_KEY"
    )

    local missing=()
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            missing+=("$var")
        fi
    done

    if [ ${#missing[@]} -ne 0 ]; then
        log_error "Missing required environment variables:"
        printf '%s\n' "${missing[@]}"
        exit 1
    fi

    log_success "Environment variables validated"
}

build_images() {
    log_info "Building Docker images..."

    cd "$PROJECT_DIR"
    docker-compose -f "$COMPOSE_FILE" --env-file ".env.${ENVIRONMENT}" build

    log_success "Images built successfully"
}

deploy_services() {
    log_info "Deploying services..."

    cd "$PROJECT_DIR"

    if [ "$RESTART" = true ]; then
        docker-compose -f "$COMPOSE_FILE" --env-file ".env.${ENVIRONMENT}" restart
    else
        docker-compose -f "$COMPOSE_FILE" --env-file ".env.${ENVIRONMENT}" up -d
    fi

    log_success "Services deployed"
}

run_migrations() {
    log_info "Running database migrations..."

    cd "$PROJECT_DIR"
    docker-compose -f "$COMPOSE_FILE" --env-file ".env.${ENVIRONMENT}" \
        exec -T backend alembic upgrade head

    log_success "Migrations completed"
}

wait_for_health() {
    log_info "Waiting for services to be healthy..."

    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if docker-compose -f "$COMPOSE_FILE" ps | grep -q "unhealthy\|starting"; then
            log_info "Attempt $attempt/$max_attempts - Services starting..."
            sleep 5
            ((attempt++))
        else
            log_success "All services are healthy!"
            return 0
        fi
    done

    log_error "Services did not become healthy in time"
    docker-compose -f "$COMPOSE_FILE" ps
    exit 1
}

show_status() {
    log_info "Current service status:"
    cd "$PROJECT_DIR"
    docker-compose -f "$COMPOSE_FILE" ps
}

show_logs() {
    log_info "Showing logs (Ctrl+C to exit)..."
    cd "$PROJECT_DIR"
    docker-compose -f "$COMPOSE_FILE" logs -f --tail=100
}

# Main
echo "=========================================="
echo "  TriFlow AI Deployment"
echo "  Environment: $ENVIRONMENT"
echo "=========================================="

check_requirements
load_env
validate_env

if [ "$BUILD" = true ]; then
    build_images
fi

deploy_services

if [ "$MIGRATE" = true ]; then
    run_migrations
fi

wait_for_health
show_status

if [ "$SHOW_LOGS" = true ]; then
    show_logs
fi

log_success "Deployment completed!"
echo ""
echo "Access points:"
echo "  - Backend API: http://localhost:${BACKEND_PORT:-8000}"
echo "  - Prometheus:  http://localhost:${PROMETHEUS_PORT:-9090}"
echo "  - Grafana:     http://localhost:${GRAFANA_PORT:-3000}"
