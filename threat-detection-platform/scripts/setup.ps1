# =============================================================================
# Threat Detection Platform - Windows Development Setup Script
# =============================================================================
# Run from project root: .\scripts\setup.ps1
# =============================================================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " Threat Detection Platform - Dev Setup" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# Check Docker
Write-Host "[1/5] Checking Docker..." -ForegroundColor Yellow
try {
    $dockerVersion = docker --version
    Write-Host "  OK: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Docker not found. Install Docker Desktop first." -ForegroundColor Red
    Write-Host "  Download: https://www.docker.com/products/docker-desktop/" -ForegroundColor Gray
    exit 1
}

# Check Docker Compose
Write-Host "[2/5] Checking Docker Compose..." -ForegroundColor Yellow
try {
    $composeVersion = docker-compose --version
    Write-Host "  OK: $composeVersion" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Docker Compose not found." -ForegroundColor Red
    exit 1
}

# Create .env file
Write-Host "[3/5] Setting up environment variables..." -ForegroundColor Yellow
if (Test-Path ".env") {
    Write-Host "  SKIP: .env already exists" -ForegroundColor Gray
} else {
    Copy-Item ".env.example" ".env"
    Write-Host "  OK: Created .env from .env.example" -ForegroundColor Green
    Write-Host "  NOTE: Review .env and update passwords for production" -ForegroundColor Yellow
}

# Build Docker images
Write-Host "[4/5] Building Docker images..." -ForegroundColor Yellow
docker-compose build
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Docker build failed" -ForegroundColor Red
    exit 1
}
Write-Host "  OK: Images built successfully" -ForegroundColor Green

# Start services
Write-Host "[5/5] Starting services..." -ForegroundColor Yellow
docker-compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Failed to start services" -ForegroundColor Red
    exit 1
}

# Wait for health
Write-Host ""
Write-Host "Waiting for services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Check health
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/health" -Method Get -TimeoutSec 10
    Write-Host ""
    Write-Host "=============================================" -ForegroundColor Green
    Write-Host " Setup Complete!" -ForegroundColor Green
    Write-Host "=============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Backend API:    http://localhost:8000" -ForegroundColor White
    Write-Host "  API Docs:       http://localhost:8000/docs" -ForegroundColor White
    Write-Host "  Frontend:       http://localhost:3000" -ForegroundColor White
    Write-Host "  PostgreSQL:     localhost:5432" -ForegroundColor White
    Write-Host "  Redis:          localhost:6379" -ForegroundColor White
    Write-Host ""
    Write-Host "  Backend status: $($health.status)" -ForegroundColor Green
    Write-Host ""
    Write-Host "Commands:" -ForegroundColor Yellow
    Write-Host "  docker-compose logs -f       (view logs)" -ForegroundColor Gray
    Write-Host "  docker-compose down          (stop services)" -ForegroundColor Gray
    Write-Host "  docker-compose up -d         (start services)" -ForegroundColor Gray
    Write-Host ""
} catch {
    Write-Host ""
    Write-Host "  WARNING: Backend not responding yet. Give it a few more seconds." -ForegroundColor Yellow
    Write-Host "  Check logs with: docker-compose logs -f backend" -ForegroundColor Gray
    Write-Host ""
}
