@echo off
setlocal enabledelayedexpansion

echo ========================================
echo   TriFlow AI Backend Server Starter
echo ========================================
echo.

REM Method 1: Kill all Python processes (most reliable)
echo [Step 1] Killing all Python processes...
taskkill /F /IM python.exe 2>nul
if errorlevel 1 (
    echo   No Python processes found.
) else (
    echo   Python processes killed.
)

REM Method 2: Kill by port (backup)
echo [Step 2] Checking port 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING 2^>nul') do (
    echo   Killing PID %%a on port 8000...
    taskkill /F /PID %%a 2>nul
)

REM Wait for port to be released
echo [Step 3] Waiting for port release...
timeout /t 3 /nobreak >nul

REM Verify port is free
netstat -ano | findstr :8000 | findstr LISTENING >nul 2>&1
if errorlevel 1 (
    echo   Port 8000 is now free.
) else (
    echo   WARNING: Port 8000 may still be in use.
    echo   Please check Task Manager if server fails to start.
)

echo.
echo [Step 4] Starting TriFlow AI Backend...
echo ========================================
cd /d %~dp0
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
