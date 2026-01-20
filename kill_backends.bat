@echo off
echo Killing all processes on port 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do (
    echo Killing PID %%a
    taskkill /F /PID %%a 2>nul
)
echo Done!
