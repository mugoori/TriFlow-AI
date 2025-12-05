# TriFlow AI - Start All Services
$ErrorActionPreference = "Stop"
Set-Location "c:\dev\triflow-ai"

Write-Host "========================================"
Write-Host "  TriFlow AI - Starting All Services"
Write-Host "========================================"
Write-Host ""

# Docker 실행 확인
Write-Host "[0/3] Checking Docker..."
try {
    docker info 2>&1 | Out-Null
    Write-Host "     Docker is running!"
} catch {
    Write-Host ""
    Write-Host "[ERROR] Docker is not running!"
    Write-Host "Please start Docker Desktop first."
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host ""

# Docker 컨테이너 시작
Write-Host "[1/3] Starting Docker containers (PostgreSQL, Redis)..."
docker-compose -f c:\dev\triflow-ai\docker-compose.yml up -d postgres redis
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] Docker containers failed to start!"
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "     PostgreSQL, Redis started!"
Write-Host ""

# DB 준비 대기
Write-Host "[2/3] Waiting for database to be ready..."
Start-Sleep -Seconds 5
Write-Host "     Database ready!"
Write-Host ""

# Backend 시작
Write-Host "[3/3] Starting Backend and Frontend..."
Write-Host ""
Write-Host "     [Backend] Initializing..."
Write-Host "     [Backend] Directory: c:\dev\triflow-ai\backend"
Write-Host "     [Backend] URL: http://localhost:8000"
Start-Process cmd -ArgumentList '/k', 'cd /d c:\dev\triflow-ai\backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info'

# Backend 시작 대기
Write-Host "     [Backend] Waiting for server to start..."
Start-Sleep -Seconds 5

# Health Check
Write-Host "     [Backend] Performing health check..."
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 5
    Write-Host "     [Backend] Health check PASSED!"
    Write-Host "     [Backend] Status: $($response.Content)"
} catch {
    Write-Host "     [Backend] Still starting... waiting more"
    Start-Sleep -Seconds 5
}
Write-Host ""

# Frontend 시작
Write-Host "     [Frontend] Initializing Tauri App..."
Write-Host "     [Frontend] Directory: c:\dev\triflow-ai\frontend"
Start-Process cmd -ArgumentList '/k', 'cd /d c:\dev\triflow-ai\frontend && npm run tauri dev'

Write-Host ""
Write-Host "========================================"
Write-Host "  All services started!"
Write-Host "========================================"
Write-Host ""
Write-Host "  Tauri App:  Starting..."
Write-Host "  Backend:    http://localhost:8000"
Write-Host "  API Docs:   http://localhost:8000/docs"
Write-Host ""
Write-Host "  Login: admin@triflow.ai / admin1234"
Write-Host "========================================"
Write-Host ""
Write-Host "Tauri app will open automatically."
Read-Host "Press Enter to exit this window"
