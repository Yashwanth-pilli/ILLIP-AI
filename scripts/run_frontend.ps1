# PowerShell Script to Run Frontend Dev Server (hot reload)
# Run as: .\scripts\run_frontend.ps1
#
# For production, you don't need this — the backend serves the built
# frontend from frontend/dist/ directly at http://127.0.0.1:8000/.
# Use this only when actively editing frontend/src/ and want hot reload.

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ILLIP AI - Frontend Dev Server (Vite)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$npm = Get-Command npm -ErrorAction SilentlyContinue
if (-not $npm) {
    Write-Host "ERROR: npm not found. Install Node.js first." -ForegroundColor Red
    exit 1
}

Push-Location frontend

if (-not (Test-Path "node_modules")) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
    npm install
}

Write-Host "Starting Vite dev server..." -ForegroundColor Yellow
Write-Host "Frontend (hot reload) will be available at: http://localhost:3000" -ForegroundColor Cyan
Write-Host "It proxies /api and /data to http://localhost:8000 — start the backend too." -ForegroundColor Gray
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Gray
Write-Host ""

npm run dev

Pop-Location
