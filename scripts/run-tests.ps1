# ===================================================
# TriFlow AI - Test Runner Script (PowerShell)
# ===================================================
# Usage:
#   .\scripts\run-tests.ps1              # Run all tests
#   .\scripts\run-tests.ps1 -Coverage    # With coverage
#   .\scripts\run-tests.ps1 -E2E         # E2E tests only
#   .\scripts\run-tests.ps1 -Quick       # Quick tests only
# ===================================================

param(
    [switch]$Coverage,
    [switch]$E2E,
    [switch]$Quick,
    [switch]$Integration
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$BackendDir = Join-Path $ProjectDir "backend"

# Functions
function Write-Info { param($Message) Write-Host "[INFO] $Message" -ForegroundColor Blue }
function Write-Success { param($Message) Write-Host "[SUCCESS] $Message" -ForegroundColor Green }
function Write-Warning { param($Message) Write-Host "[WARNING] $Message" -ForegroundColor Yellow }
function Write-Error { param($Message) Write-Host "[ERROR] $Message" -ForegroundColor Red }

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  TriFlow AI Test Runner" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

Set-Location $BackendDir

# Check for pytest
try {
    python -c "import pytest" 2>$null
}
catch {
    Write-Info "Installing test dependencies..."
    pip install -r requirements-test.txt
}

# Build pytest command
$PytestArgs = @("-v", "--tb=short")

if ($Coverage) {
    $PytestArgs += @("--cov=app", "--cov-report=term-missing", "--cov-report=html:htmlcov")
}

if ($E2E) {
    $PytestArgs += @("-m", "e2e")
}
elseif ($Quick) {
    $PytestArgs += @("-m", "not slow and not e2e")
}
elseif ($Integration) {
    $PytestArgs += @("-m", "integration")
}

Write-Info "Running: python -m pytest $($PytestArgs -join ' ')"
Write-Host ""

# Run tests
python -m pytest @PytestArgs
$ExitCode = $LASTEXITCODE

Write-Host ""
if ($ExitCode -eq 0) {
    Write-Success "All tests passed!"
    if ($Coverage) {
        Write-Info "Coverage report: $BackendDir\htmlcov\index.html"
    }
}
else {
    Write-Error "Some tests failed (exit code: $ExitCode)"
}

exit $ExitCode
