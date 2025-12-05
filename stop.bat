@echo off
chcp 65001 >nul
echo ========================================
echo   TriFlow AI - Stopping All Services
echo ========================================
echo.

:: Backend 프로세스 종료 (포트 8000)
echo [1/3] Stopping Backend...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo      Backend stopped!

:: Frontend 프로세스 종료 (포트 1420)
echo [2/3] Stopping Frontend...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :1420 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo      Frontend stopped!

:: Docker 컨테이너 종료
echo [3/3] Stopping Docker containers...
docker-compose -f c:\dev\triflow-ai\docker-compose.yml down
echo      Docker containers stopped!

echo.
echo ========================================
echo   All services stopped!
echo ========================================
pause
