# ===================================================
# TriFlow AI - Production Deployment Script (PowerShell)
# ===================================================
# Usage:
#   .\scripts\deploy.ps1 -Environment staging
#   .\scripts\deploy.ps1 -Environment production -Build -Migrate
# ===================================================

param(
    [Parameter(Position = 0)]
    [ValidateSet("staging", "production")]
    [string]$Environment = "staging",

    [switch]$Build,
    [switch]$Migrate,
    [switch]$Restart,
    [switch]$Logs
)

$ErrorActionPreference = "Stop"

# Configuration
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$ComposeFile = "docker-compose.prod.yml"

# Functions
function Write-Info { param($Message) Write-Host "[INFO] $Message" -ForegroundColor Blue }
function Write-Success { param($Message) Write-Host "[SUCCESS] $Message" -ForegroundColor Green }
function Write-Warning { param($Message) Write-Host "[WARNING] $Message" -ForegroundColor Yellow }
function Write-Error { param($Message) Write-Host "[ERROR] $Message" -ForegroundColor Red }

function Test-Requirements {
    Write-Info "Checking requirements..."

    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $docker) {
        Write-Error "Docker is not installed"
        exit 1
    }

    $compose = Get-Command docker-compose -ErrorAction SilentlyContinue
    if (-not $compose) {
        Write-Error "Docker Compose is not installed"
        exit 1
    }

    Write-Success "All requirements satisfied"
}

function Import-EnvFile {
    $envFile = Join-Path $ProjectDir ".env.$Environment"

    if (-not (Test-Path $envFile)) {
        Write-Error "Environment file not found: .env.$Environment"
        Write-Info "Create one from .env.$Environment.example"
        exit 1
    }

    Write-Info "Loading environment: $Environment"

    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

function Test-EnvVariables {
    Write-Info "Validating environment variables..."

    $requiredVars = @(
        "POSTGRES_PASSWORD",
        "REDIS_PASSWORD",
        "MINIO_SECRET_KEY",
        "ANTHROPIC_API_KEY",
        "SECRET_KEY"
    )

    $missing = @()
    foreach ($var in $requiredVars) {
        $value = [Environment]::GetEnvironmentVariable($var)
        if ([string]::IsNullOrEmpty($value)) {
            $missing += $var
        }
    }

    if ($missing.Count -gt 0) {
        Write-Error "Missing required environment variables:"
        $missing | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
        exit 1
    }

    Write-Success "Environment variables validated"
}

function Build-Images {
    Write-Info "Building Docker images..."

    Set-Location $ProjectDir
    docker-compose -f $ComposeFile --env-file ".env.$Environment" build

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to build images"
        exit 1
    }

    Write-Success "Images built successfully"
}

function Deploy-Services {
    Write-Info "Deploying services..."

    Set-Location $ProjectDir

    if ($Restart) {
        docker-compose -f $ComposeFile --env-file ".env.$Environment" restart
    }
    else {
        docker-compose -f $ComposeFile --env-file ".env.$Environment" up -d
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to deploy services"
        exit 1
    }

    Write-Success "Services deployed"
}

function Invoke-Migrations {
    Write-Info "Running database migrations..."

    Set-Location $ProjectDir
    docker-compose -f $ComposeFile --env-file ".env.$Environment" `
        exec -T backend alembic upgrade head

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to run migrations"
        exit 1
    }

    Write-Success "Migrations completed"
}

function Wait-ForHealth {
    Write-Info "Waiting for services to be healthy..."

    $maxAttempts = 30
    $attempt = 1

    while ($attempt -le $maxAttempts) {
        $status = docker-compose -f $ComposeFile ps 2>&1

        if ($status -match "unhealthy|starting") {
            Write-Info "Attempt $attempt/$maxAttempts - Services starting..."
            Start-Sleep -Seconds 5
            $attempt++
        }
        else {
            Write-Success "All services are healthy!"
            return
        }
    }

    Write-Error "Services did not become healthy in time"
    docker-compose -f $ComposeFile ps
    exit 1
}

function Show-Status {
    Write-Info "Current service status:"
    Set-Location $ProjectDir
    docker-compose -f $ComposeFile ps
}

function Show-Logs {
    Write-Info "Showing logs (Ctrl+C to exit)..."
    Set-Location $ProjectDir
    docker-compose -f $ComposeFile logs -f --tail=100
}

# Main
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  TriFlow AI Deployment" -ForegroundColor Cyan
Write-Host "  Environment: $Environment" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

Test-Requirements
Import-EnvFile
Test-EnvVariables

if ($Build) {
    Build-Images
}

Deploy-Services

if ($Migrate) {
    Invoke-Migrations
}

Wait-ForHealth
Show-Status

if ($Logs) {
    Show-Logs
}

Write-Success "Deployment completed!"
Write-Host ""
Write-Host "Access points:"
$backendPort = [Environment]::GetEnvironmentVariable("BACKEND_PORT")
if (-not $backendPort) { $backendPort = "8000" }
$prometheusPort = [Environment]::GetEnvironmentVariable("PROMETHEUS_PORT")
if (-not $prometheusPort) { $prometheusPort = "9090" }
$grafanaPort = [Environment]::GetEnvironmentVariable("GRAFANA_PORT")
if (-not $grafanaPort) { $grafanaPort = "3000" }

Write-Host "  - Backend API: http://localhost:$backendPort"
Write-Host "  - Prometheus:  http://localhost:$prometheusPort"
Write-Host "  - Grafana:     http://localhost:$grafanaPort"
