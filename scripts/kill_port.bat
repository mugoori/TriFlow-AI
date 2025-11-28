@echo off
REM Usage: kill_port.bat [port_number]
REM Default port is 8000 if not specified
REM Run this script as Administrator for best results

set PORT=%1
if "%PORT%"=="" set PORT=8000

echo ========================================
echo   Kill Port %PORT% Utility
echo ========================================
echo.

REM Method 1: Kill all Python processes (if port is default 8000)
if "%PORT%"=="8000" (
    echo [Method 1] Killing all Python processes...
    taskkill /F /IM python.exe 2>nul
    if errorlevel 1 (
        echo   No Python processes found.
    ) else (
        echo   Python processes killed.
    )
)

REM Method 2: Kill by port
echo [Method 2] Checking port %PORT%...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%PORT% ^| findstr LISTENING 2^>nul') do (
    echo   Found PID %%a on port %PORT%
    echo   Attempting to kill...
    taskkill /F /PID %%a 2>nul
)

REM Wait and verify
timeout /t 2 /nobreak >nul
echo.
echo [Verification] Current status of port %PORT%:
netstat -ano | findstr :%PORT% | findstr LISTENING 2>nul
if errorlevel 1 (
    echo   Port %PORT% is now free!
) else (
    echo   WARNING: Port %PORT% may still be in use.
    echo   Try running this script as Administrator.
    echo   Or use Task Manager to manually kill processes.
)
echo.
echo Done.
