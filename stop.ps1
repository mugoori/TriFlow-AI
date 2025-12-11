# TriFlow AI - Stop All Services
$ErrorActionPreference = "SilentlyContinue"
Set-Location "c:\dev\triflow-ai"

Write-Host "========================================"
Write-Host "  TriFlow AI - Stopping All Services"
Write-Host "========================================"
Write-Host ""

# 1. Frontend (Node.js) 프로세스 종료
Write-Host "[1/4] Stopping Frontend processes..."
Get-Process -Name "node*" -ErrorAction SilentlyContinue | ForEach-Object {
    $proc = $_
    if ($proc.MainWindowTitle -match "triflow" -or $proc.Path -match "triflow") {
        Stop-Process -Id $proc.Id -Force
        Write-Host "     Killed Node.js PID: $($proc.Id)"
    }
}

# Tauri 앱 종료
Get-Process -Name "triflow-ai*" -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.Id -Force
    Write-Host "     Killed Tauri app PID: $($_.Id)"
}
Write-Host "     Frontend stopped."
Write-Host ""

# 2. Backend (Python) 프로세스 종료
Write-Host "[2/4] Stopping Backend processes..."
Get-Process -Name "python*" -ErrorAction SilentlyContinue | ForEach-Object {
    $proc = $_
    try {
        $connections = Get-NetTCPConnection -OwningProcess $proc.Id -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -eq 8000 }
        if ($connections) {
            Stop-Process -Id $proc.Id -Force
            Write-Host "     Killed Python PID: $($proc.Id)"
        }
    } catch {}
}

# netstat로 추가 확인
$pids = netstat -ano | Select-String ":8000.*LISTENING" | ForEach-Object { ($_ -split '\s+')[-1] } | Select-Object -Unique
foreach ($pid in $pids) {
    if ($pid -match '^\d+$' -and $pid -ne "0") {
        try {
            Stop-Process -Id $pid -Force
            Write-Host "     Killed PID: $pid"
        } catch {}
    }
}
Write-Host "     Backend stopped."
Write-Host ""

# 3. Docker 컨테이너 중지 (선택적)
Write-Host "[3/4] Stopping Docker containers..."
$response = Read-Host "     Stop PostgreSQL and Redis containers? (y/N)"
if ($response -eq "y" -or $response -eq "Y") {
    docker-compose -f c:\dev\triflow-ai\docker-compose.yml down
    Write-Host "     Docker containers stopped."
} else {
    Write-Host "     Docker containers kept running."
}
Write-Host ""

# 4. 포트 상태 확인
Write-Host "[4/4] Verifying port status..."
Start-Sleep -Seconds 2
$stillListening = netstat -ano | Select-String ":8000.*LISTENING"
if ($stillListening) {
    Write-Host "     WARNING: Port 8000 still has connections (TIME_WAIT)"
    Write-Host "     These will clear automatically in ~30 seconds"
} else {
    Write-Host "     Port 8000 is free!"
}

Write-Host ""
Write-Host "========================================"
Write-Host "  All services stopped!"
Write-Host "========================================"
Write-Host ""
Read-Host "Press Enter to exit"
