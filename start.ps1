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

# 기존 백엔드 프로세스 정리 (강화된 버전)
Write-Host "     [Backend] Cleaning up existing processes..."

# 1. 포트 8000을 사용하는 모든 Python 프로세스 종료
Get-Process -Name "python*" -ErrorAction SilentlyContinue | ForEach-Object {
    $proc = $_
    try {
        $connections = Get-NetTCPConnection -OwningProcess $proc.Id -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -eq 8000 }
        if ($connections) {
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            Write-Host "     [Backend] Killed Python process PID: $($proc.Id)"
        }
    } catch {
        # 무시
    }
}

# 2. netstat로 포트 8000 LISTENING 프로세스 종료
$existingPids = netstat -ano | Select-String ":8000.*LISTENING" | ForEach-Object { ($_ -split '\s+')[-1] } | Select-Object -Unique
foreach ($procId in $existingPids) {
    if ($procId -match '^\d+$' -and $procId -ne "0") {
        try {
            $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
            if ($proc) {
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                Write-Host "     [Backend] Killed PID: $procId ($($proc.ProcessName))"
            }
        } catch {
            # Ghost socket - 프로세스 없음
            Write-Host "     [Backend] Ghost socket detected for PID: $procId"
        }
    }
}

# 3. Ghost socket 감지 및 대기
Start-Sleep -Seconds 2
$stillListening = netstat -ano | Select-String ":8000.*LISTENING"
if ($stillListening) {
    Write-Host "     [Backend] WARNING: Port 8000 still in use (ghost sockets)"
    Write-Host "     [Backend] Waiting for TCP TIME_WAIT to clear..."

    # 최대 30초 대기
    $maxWait = 30
    $waited = 0
    while ($waited -lt $maxWait) {
        Start-Sleep -Seconds 2
        $waited += 2
        $stillListening = netstat -ano | Select-String ":8000.*LISTENING"
        if (-not $stillListening) {
            Write-Host "     [Backend] Port 8000 is now free!"
            break
        }
        Write-Host "     [Backend] Still waiting... ($waited/$maxWait sec)"
    }

    # 그래도 안되면 netsh로 강제 리셋
    if ($stillListening) {
        Write-Host "     [Backend] Attempting TCP reset..."
        netsh int ip reset | Out-Null
        Start-Sleep -Seconds 3
    }
}

Write-Host "     [Backend] Process cleanup complete."

Write-Host "     [Backend] Initializing..."
Write-Host "     [Backend] Directory: c:\dev\triflow-ai\backend"
Write-Host "     [Backend] URL: http://localhost:8000"
Start-Process cmd -ArgumentList '/k', 'cd /d c:\dev\triflow-ai\backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level info'

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
