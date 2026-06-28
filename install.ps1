# ILLIP AI — one-line installer for Windows
# Run: irm https://raw.githubusercontent.com/YOUR_USER/ILLIP_AI/main/install.ps1 | iex

param(
    [string]$RepoUrl  = "https://github.com/YOUR_USER/ILLIP_AI",
    [string]$InstallDir = ".\illip_ai"
)

$ErrorActionPreference = "Stop"

Write-Host "=== ILLIP AI Installer ===" -ForegroundColor Cyan

# Check Python
try {
    $pyVer = python --version 2>&1
    Write-Host "$pyVer found."
} catch {
    Write-Host "ERROR: python not found. Install Python 3.11+ from python.org" -ForegroundColor Red
    exit 1
}

# Check git
try {
    git --version | Out-Null
} catch {
    Write-Host "ERROR: git not found. Install git from git-scm.com" -ForegroundColor Red
    exit 1
}

# Clone or pull
if (Test-Path $InstallDir) {
    Write-Host "Directory $InstallDir exists — pulling latest..."
    git -C $InstallDir pull origin main
} else {
    Write-Host "Cloning ILLIP AI..."
    git clone --depth=1 $RepoUrl $InstallDir
}

Set-Location $InstallDir

# Install deps
Write-Host "Installing dependencies..."
python -m pip install -r requirements.txt -q

# Setup .env
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ""
    Write-Host "=== SETUP REQUIRED ===" -ForegroundColor Yellow
    Write-Host "Edit .env to configure your model provider (Ollama/OpenRouter/Groq)."
    Write-Host "Telegram, Discord, Slack, Email — all optional, set env vars to enable."
    Write-Host "Open .env with: notepad .env"
    Write-Host "======================"
}

# Create data dirs
python -c "from app.config import settings; settings.ensure_directories()" 2>$null
if (-not $?) {
    New-Item -ItemType Directory -Force -Path "data\memory","data\logs","data\tasks","data\workspaces","data\snapshots","data\connectors" | Out-Null
}

Write-Host ""
Write-Host "ILLIP AI installed at: $(Get-Location)" -ForegroundColor Green
Write-Host ""
Write-Host "Start:  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
Write-Host ""
Write-Host "Add integrations from URL (zero download):"
Write-Host "  POST /api/skills/install  {`"url`": `"https://raw.github.com/.../skill.py`"}"
Write-Host ""
