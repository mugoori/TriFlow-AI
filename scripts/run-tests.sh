#!/bin/bash
# ===================================================
# TriFlow AI - Test Runner Script
# ===================================================
# Usage:
#   ./scripts/run-tests.sh              # Run all tests
#   ./scripts/run-tests.sh --cov        # With coverage
#   ./scripts/run-tests.sh --e2e        # E2E tests only
#   ./scripts/run-tests.sh --quick      # Quick tests only
# ===================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/backend"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Parse arguments
COVERAGE=false
E2E_ONLY=false
QUICK=false
MARKERS=""

for arg in "$@"; do
    case $arg in
        --cov|--coverage)
            COVERAGE=true
            ;;
        --e2e)
            E2E_ONLY=true
            MARKERS="-m e2e"
            ;;
        --quick)
            QUICK=true
            MARKERS="-m 'not slow and not e2e'"
            ;;
        --integration)
            MARKERS="-m integration"
            ;;
    esac
done

echo "=========================================="
echo "  TriFlow AI Test Runner"
echo "=========================================="

cd "$BACKEND_DIR"

# Check if virtual environment exists
if [ ! -d "venv" ] && [ -z "$VIRTUAL_ENV" ]; then
    log_warning "No virtual environment detected"
    log_info "Consider running: python -m venv venv && source venv/bin/activate"
fi

# Install test dependencies if needed
if ! python -c "import pytest" 2>/dev/null; then
    log_info "Installing test dependencies..."
    pip install -r requirements-test.txt
fi

# Build pytest command
PYTEST_CMD="python -m pytest"

if [ "$COVERAGE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --cov=app --cov-report=term-missing --cov-report=html:htmlcov"
fi

if [ -n "$MARKERS" ]; then
    PYTEST_CMD="$PYTEST_CMD $MARKERS"
fi

# Add common options
PYTEST_CMD="$PYTEST_CMD -v --tb=short"

log_info "Running: $PYTEST_CMD"
echo ""

# Run tests
eval $PYTEST_CMD

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    log_success "All tests passed!"
    if [ "$COVERAGE" = true ]; then
        log_info "Coverage report: $BACKEND_DIR/htmlcov/index.html"
    fi
else
    log_error "Some tests failed (exit code: $EXIT_CODE)"
fi

exit $EXIT_CODE
