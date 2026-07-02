# PowerShell Script to Start ILLIP AI (backend serves the built frontend too)
# Run as: .\scripts\dev_start.ps1
#
# The backend mounts frontend/dist/ and serves the whole app from one port —
# no separate frontend server needed. Run "cd frontend; npm run build" first
# if frontend/dist/ is missing or stale. For hot-reload frontend dev, use
# .\scripts\run_frontend.ps1 (Vite dev server) in a separate terminal instead.

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ILLIP AI - Development Server (Full Stack)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check virtual environment
if (-not (Test-Path "venv")) {
    Write-Host "ERROR: Virtual environment not found." -ForegroundColor Red
    Write-Host "Run .\scripts\setup.ps1 first" -ForegroundColor Yellow
    exit 1
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

if (-not $?) {
    Write-Host "ERROR: Failed to activate virtual environment" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting Backend..." -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "API: http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Docs: http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host ""

# Start backend in a new window
$backendJob = Start-Process -FilePath "python" `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000" `
    -WindowStyle Normal `
    -PassThru

Write-Host "✓ Backend started (PID: $($backendJob.Id))" -ForegroundColor Green

if (-not (Test-Path "frontend\dist\index.html")) {
    Write-Host ""
    Write-Host "WARNING: frontend/dist/ not found — the app UI won't load." -ForegroundColor Yellow
    Write-Host "Run: cd frontend; npm install; npm run build; cd .." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ILLIP AI running!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Services:" -ForegroundColor Yellow
Write-Host "  App (UI + API): http://127.0.0.1:8000" -ForegroundColor White
Write-Host "  API Docs:       http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "To stop, close the backend window or press Ctrl+C" -ForegroundColor Gray
Write-Host ""

# Wait for any key to exit
Write-Host "Press any key to stop the server..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

Write-Host ""
Write-Host "Stopping server..." -ForegroundColor Yellow

try {
    Stop-Process -Id $backendJob.Id -Force -ErrorAction SilentlyContinue
    Write-Host "✓ Backend stopped" -ForegroundColor Green
} catch { }

Write-Host "Done!" -ForegroundColor Cyan
