# ILLIP AI - single entry point. Double-click run.bat.
# First run: installs everything (setup.ps1). Every run: starts the server.

$ErrorActionPreference = "Continue"
$Root = $PSScriptRoot
Set-Location $Root

$venvPython = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    & (Join-Path $Root "setup.ps1")
    if (-not (Test-Path $venvPython)) {
        Write-Host "[!] Setup did not finish - see the messages above." -ForegroundColor Red
        Exit 1
    }
}

$envPath = Join-Path $Root ".env"
if (-not (Test-Path $envPath)) {
    Copy-Item (Join-Path $Root ".env.example") $envPath
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "       Launching ILLIP AI Server...       " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$localIP = (Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "*" | Where-Object { $_.IPAddress -notmatch "^(127|169)" } | Select-Object -First 1).IPAddress
Write-Host "[+] Local URL:   http://127.0.0.1:8000" -ForegroundColor Green
if ($localIP) { Write-Host "[+] Network URL: http://${localIP}:8000  (other devices on same WiFi)" -ForegroundColor Green }
Write-Host "[+] API Docs:    http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host "[*] Press Ctrl+C to stop ILLIP." -ForegroundColor Yellow
Write-Host ""

Start-Process "http://127.0.0.1:8000"

# 0.0.0.0 makes it reachable from other devices on the same WiFi too.
& $venvPython -m uvicorn app.main:app --host 0.0.0.0 --port 8000
