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

# 2. Backend (Python) 프로세스 종료 - Graceful Shutdown
Write-Host "[2/4] Stopping Backend processes (graceful)..."

# 포트 목록 (8000, 8001 둘 다 정리)
$ports = @(8000, 8001)

# Step 1: Graceful shutdown 시도 (taskkill without /F)
foreach ($port in $ports) {
    Get-Process -Name "python*" -ErrorAction SilentlyContinue | ForEach-Object {
        $proc = $_
        try {
            $connections = Get-NetTCPConnection -OwningProcess $proc.Id -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -eq $port }
            if ($connections) {
                Write-Host "     Sending graceful shutdown to PID: $($proc.Id) (port $port)"
                # /F 없이 먼저 시도 (graceful)
                Start-Process -FilePath "taskkill" -ArgumentList "/PID", $proc.Id -NoNewWindow -Wait -ErrorAction SilentlyContinue
            }
        } catch {}
    }
}

# Step 2: 5초 대기 (graceful shutdown 시간)
Write-Host "     Waiting for graceful shutdown (5 sec)..."
Start-Sleep -Seconds 5

# Step 3: 아직 살아있으면 강제 종료
foreach ($port in $ports) {
    Get-Process -Name "python*" -ErrorAction SilentlyContinue | ForEach-Object {
        $proc = $_
        try {
            $connections = Get-NetTCPConnection -OwningProcess $proc.Id -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -eq $port }
            if ($connections) {
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
                Write-Host "     Force killed Python PID: $($proc.Id) (port $port)"
            }
        } catch {}
    }
}

# Step 4: netstat로 남은 프로세스 강제 종료
foreach ($port in $ports) {
    $procIds = netstat -ano | Select-String ":$port.*LISTENING" | ForEach-Object { ($_ -split '\s+')[-1] } | Select-Object -Unique
    foreach ($procId in $procIds) {
        if ($procId -match '^\d+$' -and $procId -ne "0") {
            try {
                $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
                if ($proc) {
                    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                    Write-Host "     Force killed PID: $procId (port $port)"
                }
            } catch {
                Write-Host "     Ghost socket detected for PID: $procId (port $port)"
            }
        }
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
