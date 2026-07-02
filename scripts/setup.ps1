# PowerShell Setup Script for ILLIP AI
# Run as: .\scripts\setup.ps1

param(
    [switch]$SkipVenv = $false,
    [switch]$SkipDeps = $false
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ILLIP AI - Setup Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "Checking Python installation..." -ForegroundColor Yellow
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "ERROR: Python not found. Please install Python 3.9+" -ForegroundColor Red
    exit 1
}

$pythonVersion = python --version 2>&1
Write-Host "✓ Found: $pythonVersion" -ForegroundColor Green

# Create virtual environment
if (-not $SkipVenv) {
    Write-Host ""
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    if (Test-Path "venv") {
        Write-Host "✓ Virtual environment already exists" -ForegroundColor Green
    } else {
        python -m venv venv
        Write-Host "✓ Virtual environment created" -ForegroundColor Green
    }
}

# Activate virtual environment
Write-Host ""
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1
if ($?) {
    Write-Host "✓ Virtual environment activated" -ForegroundColor Green
} else {
    Write-Host "ERROR: Failed to activate virtual environment" -ForegroundColor Red
    exit 1
}

# Install dependencies
if (-not $SkipDeps) {
    Write-Host ""
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    pip install --upgrade pip
    pip install -r requirements.txt
    if ($?) {
        Write-Host "✓ Dependencies installed" -ForegroundColor Green
    } else {
        Write-Host "ERROR: Failed to install dependencies" -ForegroundColor Red
        exit 1
    }
}

# Setup environment file
Write-Host ""
Write-Host "Setting up environment configuration..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "✓ Created .env from .env.example" -ForegroundColor Green
    }
} else {
    Write-Host "✓ .env already exists" -ForegroundColor Green
}

# Create data directories
Write-Host ""
Write-Host "Creating data directories..." -ForegroundColor Yellow
$dirs = @("data", "data/logs", "data/memory", "data/tasks", "data/workspaces", "data/snapshots")
foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}
Write-Host "✓ Data directories created" -ForegroundColor Green

# Build frontend (frontend/dist/ is gitignored — must be built locally)
Write-Host ""
Write-Host "Building frontend..." -ForegroundColor Yellow
$npm = Get-Command npm -ErrorAction SilentlyContinue
if (-not $npm) {
    Write-Host "⚠ npm not found — skipping frontend build. Install Node.js, then run:" -ForegroundColor Yellow
    Write-Host "  cd frontend; npm install; npm run build; cd .." -ForegroundColor White
} else {
    Push-Location frontend
    if (-not (Test-Path "node_modules")) {
        npm install
    }
    npm run build
    Pop-Location
    if (Test-Path "frontend\dist\index.html") {
        Write-Host "✓ Frontend built" -ForegroundColor Green
    } else {
        Write-Host "⚠ Frontend build did not produce frontend/dist/index.html" -ForegroundColor Yellow
    }
}

# Run tests
Write-Host ""
Write-Host "Running health check tests..." -ForegroundColor Yellow
pytest tests/test_health.py -v
if ($?) {
    Write-Host "✓ Basic tests passed" -ForegroundColor Green
} else {
    Write-Host "⚠ Some tests failed (non-critical)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "✓ Setup Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Start the app:  .\scripts\run_backend.ps1  (serves UI + API at http://127.0.0.1:8000)" -ForegroundColor White
Write-Host "2. Editing the frontend? Hot-reload dev server: .\scripts\run_frontend.ps1" -ForegroundColor White
Write-Host ""
Write-Host "For detailed instructions, see START_HERE.md" -ForegroundColor Cyan
