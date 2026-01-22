#!/bin/bash
#
# 자동 파티셔닝 배치 스크립트
# 스펙 참조: B-3-4 Performance & Operations
#
# 기능:
# 1. 미래 3개월 파티션 사전 생성 (장애 방지)
# 2. 보존 기간 초과 파티션 삭제 (스토리지 관리)
# 3. 파티션 상태 모니터링
#
# 스케줄: 매월 1일 03:00 (cron)
# 0 3 1 * * /app/backend/scripts/auto_partition.sh >> /var/log/auto_partition.log 2>&1
#

set -e  # 에러 발생 시 즉시 종료

# ========== 설정 ==========

# DB 연결 정보 (환경변수 또는 기본값)
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-postgres}"
DB_NAME="${DB_NAME:-ai_factory}"

# 로그 설정
LOG_FILE="${LOG_FILE:-/var/log/auto_partition.log}"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# 색상 코드
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# ========== 로깅 함수 ==========

log_info() {
    echo -e "${GREEN}[INFO]${NC} [$TIMESTAMP] $1" | tee -a "$LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} [$TIMESTAMP] $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} [$TIMESTAMP] $1" | tee -a "$LOG_FILE"
}

# ========== DB 연결 확인 ==========

check_db_connection() {
    log_info "Checking database connection..."

    if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c '\q' 2>/dev/null; then
        log_info "Database connection successful"
        return 0
    else
        log_error "Failed to connect to database"
        return 1
    fi
}

# ========== 파티션 생성 ==========

# 월별 파티션 대상 테이블
MONTHLY_TABLES=(
    "judgment_executions:created_at"
    "workflow_instances:started_at"
    "llm_calls:created_at"
    "mcp_call_logs:created_at"
    "audit_logs:created_at"
    "raw_mes_production:event_time"
    "raw_erp_order:event_time"
    "raw_inventory:event_time"
    "raw_equipment_event:event_time"
    "fact_hourly_production:hour_timestamp"
)

# 분기별 파티션 대상 테이블
QUARTERLY_TABLES=(
    "fact_daily_production:date"
    "fact_daily_defect:date"
    "fact_inventory_snapshot:date"
    "fact_equipment_event:date"
)

create_future_partitions() {
    log_info "Creating future partitions..."

    local created_count=0
    local failed_count=0

    # 월별 파티션 생성 (미래 3개월)
    for table_info in "${MONTHLY_TABLES[@]}"; do
        table="${table_info%%:*}"
        column="${table_info##*:}"

        for month in 1 2 3; do
            log_info "Creating monthly partition for $table (month +$month)..."

            if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
                -c "SELECT create_monthly_partition('$table', '$column', NOW() + INTERVAL '$month month');" \
                >> "$LOG_FILE" 2>&1; then
                ((created_count++))
                log_info "  ✓ Success: $table (month +$month)"
            else
                ((failed_count++))
                log_warn "  ✗ Failed: $table (month +$month) - may already exist"
            fi
        done
    done

    # 분기별 파티션 생성 (미래 2분기)
    for table_info in "${QUARTERLY_TABLES[@]}"; do
        table="${table_info%%:*}"
        column="${table_info##*:}"

        for quarter in 1 2; do
            log_info "Creating quarterly partition for $table (quarter +$quarter)..."

            if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
                -c "SELECT create_quarterly_partition('$table', '$column', NOW() + INTERVAL '$((quarter * 3)) month');" \
                >> "$LOG_FILE" 2>&1; then
                ((created_count++))
                log_info "  ✓ Success: $table (quarter +$quarter)"
            else
                ((failed_count++))
                log_warn "  ✗ Failed: $table (quarter +$quarter) - may already exist"
            fi
        done
    done

    log_info "Partition creation completed: $created_count created, $failed_count failed/skipped"
}

# ========== 오래된 파티션 삭제 ==========

delete_expired_partitions() {
    log_info "Deleting expired partitions..."

    local deleted_count=0

    # 2년 전 날짜 계산
    CUTOFF_DATE=$(date -d "2 years ago" '+%Y%m' 2>/dev/null || date -v-2y '+%Y%m')
    log_info "Cutoff date: $CUTOFF_DATE (2 years ago)"

    # 월별 파티션 삭제
    for table_info in "${MONTHLY_TABLES[@]}"; do
        table="${table_info%%:*}"
        partition_name="${table}_y${CUTOFF_DATE:0:4}m${CUTOFF_DATE:4:2}"

        log_info "Checking partition: $partition_name"

        # 파티션 존재 여부 확인
        if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
            -tAc "SELECT 1 FROM pg_tables WHERE schemaname='core' AND tablename='$partition_name';" \
            | grep -q 1; then

            log_info "Deleting expired partition: $partition_name"

            if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
                -c "DROP TABLE IF EXISTS core.$partition_name;" >> "$LOG_FILE" 2>&1; then
                ((deleted_count++))
                log_info "  ✓ Deleted: $partition_name"
            else
                log_error "  ✗ Failed to delete: $partition_name"
            fi
        fi
    done

    log_info "Partition deletion completed: $deleted_count partitions deleted"
}

# ========== 파티션 상태 모니터링 ==========

check_partition_status() {
    log_info "Checking partition status..."

    # 현재 월 파티션 존재 여부 확인
    CURRENT_MONTH=$(date '+%Y%m')

    local missing_count=0

    for table_info in "${MONTHLY_TABLES[@]}"; do
        table="${table_info%%:*}"
        partition_name="${table}_y${CURRENT_MONTH:0:4}m${CURRENT_MONTH:4:2}"

        if ! PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
            -tAc "SELECT 1 FROM pg_tables WHERE schemaname='core' AND tablename='$partition_name';" \
            | grep -q 1; then

            log_error "CRITICAL: Current month partition missing: $partition_name"
            ((missing_count++))
        fi
    done

    if [ $missing_count -eq 0 ]; then
        log_info "All current month partitions exist ✓"
    else
        log_error "ALERT: $missing_count current month partitions missing!"
        # 알림 발송 (선택)
        # send_alert "Partition missing alert" "$missing_count partitions missing"
    fi
}

# ========== 통계 정보 출력 ==========

print_partition_stats() {
    log_info "Partition statistics:"

    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<EOF
SELECT
    parent.relname AS parent_table,
    COUNT(*) AS partition_count,
    pg_size_pretty(SUM(pg_total_relation_size(child.oid))) AS total_size
FROM pg_inherits
JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
JOIN pg_class child ON pg_inherits.inhrelid = child.oid
WHERE parent.relname IN ('judgment_executions', 'workflow_instances', 'llm_calls', 'fact_daily_production')
GROUP BY parent.relname
ORDER BY parent.relname;
EOF
}

# ========== 메인 실행 ==========

main() {
    log_info "=========================================="
    log_info "Auto Partitioning Batch Started"
    log_info "=========================================="

    # 1. DB 연결 확인
    if ! check_db_connection; then
        log_error "Batch aborted: Cannot connect to database"
        exit 1
    fi

    # 2. 미래 파티션 생성
    create_future_partitions

    # 3. 만료된 파티션 삭제
    delete_expired_partitions

    # 4. 파티션 상태 확인
    check_partition_status

    # 5. 통계 출력
    print_partition_stats

    log_info "=========================================="
    log_info "Auto Partitioning Batch Completed"
    log_info "=========================================="
}

# 스크립트 실행
main
