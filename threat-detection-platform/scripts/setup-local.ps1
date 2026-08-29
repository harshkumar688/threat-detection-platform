# =============================================================================
# Threat Detection Platform - Local Development Setup (without Docker)
# =============================================================================
# Use this when you want to run backend/frontend natively.
# PostgreSQL and Redis still need to be running (via Docker or installed locally).
#
# Run from project root: .\scripts\setup-local.ps1
# =============================================================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " Local Development Setup (No Docker for app)" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# --- Step 1: Check Python ---
Write-Host "[1/6] Checking Python..." -ForegroundColor Yellow
try {
    $pyVersion = python --version 2>&1
    Write-Host "  OK: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Python not found. Install Python 3.10+" -ForegroundColor Red
    exit 1
}

# --- Step 2: Check Node ---
Write-Host "[2/6] Checking Node.js..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version 2>&1
    Write-Host "  OK: Node $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Node.js not found. Install Node 18+" -ForegroundColor Red
    exit 1
}

# --- Step 3: Create .env ---
Write-Host "[3/6] Setting up .env..." -ForegroundColor Yellow
if (Test-Path ".env") {
    Write-Host "  SKIP: .env already exists" -ForegroundColor Gray
} else {
    Copy-Item ".env.example" ".env"
    # Update DATABASE_URL for local (localhost instead of docker service name)
    (Get-Content ".env") -replace "postgres:5432", "localhost:5432" `
                         -replace "redis:6379", "localhost:6379" `
                         -replace "POSTGRES_HOST=postgres", "POSTGRES_HOST=localhost" `
                         -replace "REDIS_HOST=redis", "REDIS_HOST=localhost" | Set-Content ".env"
    Write-Host "  OK: Created .env (configured for localhost)" -ForegroundColor Green
}

# --- Step 4: Backend Virtual Environment ---
Write-Host "[4/6] Setting up backend Python virtual environment..." -ForegroundColor Yellow
Push-Location backend

if (-not (Test-Path "venv")) {
    python -m venv venv
    Write-Host "  Created venv at backend/venv/" -ForegroundColor Green
} else {
    Write-Host "  SKIP: venv already exists" -ForegroundColor Gray
}

# Activate and install
& "venv\Scripts\Activate.ps1"
pip install --upgrade pip -q
pip install -r requirements.txt -r requirements-dev.txt -q
Write-Host "  OK: Backend dependencies installed" -ForegroundColor Green

Pop-Location

# --- Step 5: Frontend Dependencies ---
Write-Host "[5/6] Setting up frontend Node dependencies..." -ForegroundColor Yellow
Push-Location frontend

if (-not (Test-Path "node_modules")) {
    npm ci
} else {
    Write-Host "  SKIP: node_modules already exists" -ForegroundColor Gray
}
Write-Host "  OK: Frontend dependencies installed" -ForegroundColor Green

Pop-Location

# --- Step 6: Start infrastructure (PostgreSQL + Redis via Docker) ---
Write-Host "[6/6] Starting infrastructure (PostgreSQL + Redis)..." -ForegroundColor Yellow
docker-compose up -d postgres redis
if ($LASTEXITCODE -ne 0) {
    Write-Host "  WARNING: Could not start Docker services." -ForegroundColor Yellow
    Write-Host "  Ensure PostgreSQL and Redis are running locally." -ForegroundColor Gray
} else {
    Write-Host "  OK: PostgreSQL and Redis running via Docker" -ForegroundColor Green
}

# --- Summary ---
Write-Host ""
Write-Host "=============================================" -ForegroundColor Green
Write-Host " Local Setup Complete!" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
Write-Host ""
Write-Host "To start development:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Backend (Terminal 1):" -ForegroundColor White
Write-Host "    cd backend" -ForegroundColor Gray
Write-Host "    .\venv\Scripts\Activate.ps1" -ForegroundColor Gray
Write-Host "    uvicorn app.main:app --reload --port 8000" -ForegroundColor Gray
Write-Host ""
Write-Host "  Frontend (Terminal 2):" -ForegroundColor White
Write-Host "    cd frontend" -ForegroundColor Gray
Write-Host "    npm run dev" -ForegroundColor Gray
Write-Host ""
Write-Host "  Access:" -ForegroundColor White
Write-Host "    Backend API:  http://localhost:8000" -ForegroundColor Gray
Write-Host "    API Docs:     http://localhost:8000/docs" -ForegroundColor Gray
Write-Host "    Frontend:     http://localhost:3000 (or :5173)" -ForegroundColor Gray
Write-Host ""
