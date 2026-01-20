@echo off
echo Killing all Python processes on port 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do (
    taskkill /F /PID %%a 2>nul
)

echo Waiting for port to be released...
timeout /t 3 /nobreak >nul

echo Starting backend...
cd c:\dev\triflow-ai\backend
start "TriFlow Backend" cmd /k "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

echo.
echo Backend restart initiated!
echo Check the "TriFlow Backend" window for logs.
echo Look for: "Module management router registered"
pause
