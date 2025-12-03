#!/bin/bash
# ===================================================
# TriFlow AI - Health Check Script
# ===================================================
# Performs health checks on all services
# Returns 0 if all healthy, 1 otherwise
# ===================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
GRAFANA_URL="${GRAFANA_URL:-http://localhost:3000}"

check_service() {
    local name=$1
    local url=$2
    local path=$3

    if curl -sf "${url}${path}" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $name is healthy"
        return 0
    else
        echo -e "${RED}✗${NC} $name is not responding"
        return 1
    fi
}

echo "=========================================="
echo "  TriFlow AI Health Check"
echo "=========================================="
echo ""

FAILED=0

# Backend API
check_service "Backend API" "$BACKEND_URL" "/health" || ((FAILED++))

# Prometheus
check_service "Prometheus" "$PROMETHEUS_URL" "/-/healthy" || ((FAILED++))

# Grafana
check_service "Grafana" "$GRAFANA_URL" "/api/health" || ((FAILED++))

# Docker containers
echo ""
echo "Docker Container Status:"
docker-compose -f docker-compose.prod.yml ps 2>/dev/null || echo "  (Docker Compose not available)"

echo ""
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All services are healthy!${NC}"
    exit 0
else
    echo -e "${RED}$FAILED service(s) are unhealthy${NC}"
    exit 1
fi
