@echo on
echo Step 1: Setting codepage
chcp 65001
echo.

echo Step 2: Changing directory
cd /d c:\dev\triflow-ai
echo Current dir: %CD%
echo.

echo Step 3: Checking Docker
docker info >nul 2>&1
echo Docker errorlevel: %errorlevel%
echo.

echo Step 4: Starting containers
docker-compose -f c:\dev\triflow-ai\docker-compose.yml up -d postgres redis
echo Docker-compose errorlevel: %errorlevel%
echo.

echo Step 5: Done
pause
