#!/bin/bash
# ===================================================
# TriFlow AI - Database Backup Script
# ===================================================
# Creates backups of PostgreSQL and Redis data
# Usage: ./scripts/backup.sh [destination]
# ===================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${1:-$PROJECT_DIR/backups}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo "=========================================="
echo "  TriFlow AI Backup"
echo "  Timestamp: $TIMESTAMP"
echo "=========================================="

# PostgreSQL Backup
log_info "Backing up PostgreSQL..."
POSTGRES_BACKUP="$BACKUP_DIR/postgres_${TIMESTAMP}.sql.gz"

docker exec triflow-postgres pg_dump -U triflow triflow_ai | gzip > "$POSTGRES_BACKUP"

if [ -f "$POSTGRES_BACKUP" ]; then
    log_success "PostgreSQL backup: $POSTGRES_BACKUP"
    log_info "Size: $(du -h "$POSTGRES_BACKUP" | cut -f1)"
else
    log_error "PostgreSQL backup failed"
fi

# Redis Backup (RDB snapshot)
log_info "Backing up Redis..."
REDIS_BACKUP="$BACKUP_DIR/redis_${TIMESTAMP}.rdb"

docker exec triflow-redis redis-cli -a "$REDIS_PASSWORD" BGSAVE
sleep 2
docker cp triflow-redis:/data/dump.rdb "$REDIS_BACKUP"

if [ -f "$REDIS_BACKUP" ]; then
    log_success "Redis backup: $REDIS_BACKUP"
    log_info "Size: $(du -h "$REDIS_BACKUP" | cut -f1)"
else
    log_error "Redis backup failed"
fi

# MinIO Backup (optional - can be large)
log_info "MinIO backup skipped (use MinIO's own backup tools for large files)"

# Cleanup old backups (keep last 7 days)
log_info "Cleaning up backups older than 7 days..."
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +7 -delete 2>/dev/null || true
find "$BACKUP_DIR" -name "*.rdb" -mtime +7 -delete 2>/dev/null || true

echo ""
log_success "Backup completed!"
echo ""
echo "Backup location: $BACKUP_DIR"
ls -lh "$BACKUP_DIR" | tail -5
