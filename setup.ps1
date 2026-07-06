# ILLIP AI - One-click setup.
# Double-click setup.bat. This script:
#   1. Finds or installs Python (asks permission first)
#   2. Creates the virtualenv and installs dependencies
#   3. Finds or installs Ollama (asks permission first)
#   4. Looks at your hardware (GPU VRAM / RAM) and picks the right model
#   5. Downloads the model (asks permission first - it is gigabytes)
#   6. Puts a small cat on your desktop - click the cat to start ILLIP
# Anything it cannot do automatically, it explains step by step.

$ErrorActionPreference = "Continue"
$Root = $PSScriptRoot
Set-Location $Root

function Say($msg, $color = "White") { Write-Host $msg -ForegroundColor $color }
function Step($msg) { Write-Host ""; Write-Host "[*] $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "[+] $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "[~] $msg" -ForegroundColor Yellow }
function Fail($msg) { Write-Host "[!] $msg" -ForegroundColor Red }

function Ask($question) {
    # Owner permission gate. Returns $true only on explicit yes.
    $answer = Read-Host "$question [Y/N]"
    return ($answer -match '^[Yy]')
}

function Refresh-Path {
    # Pick up PATH changes made by installers without restarting the shell.
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

function Has-Command($name) {
    return $null -ne (Get-Command $name -ErrorAction SilentlyContinue)
}

Say "==========================================" Cyan
Say "           ILLIP AI  -  Setup             " Cyan
Say "==========================================" Cyan

# -- 1. Python ----------------------------------------------------------------
Step "Checking for Python 3.10+..."
$python = $null
foreach ($candidate in @("python", "python3")) {
    if (Has-Command $candidate) {
        $v = & $candidate --version 2>&1
        if ($v -match "Python 3\.(\d+)") {
            if ([int]$Matches[1] -ge 10) { $python = $candidate; break }
        }
    }
}
if (-not $python -and (Has-Command "py")) {
    $v = & py -3 --version 2>&1
    if ($v -match "Python 3\.(\d+)" -and [int]$Matches[1] -ge 10) { $python = "py -3" }
}

if ($python) {
    Ok "Found Python ($python)."
} else {
    Warn "Python 3.10+ not found on this computer."
    if ((Has-Command "winget") -and (Ask "May I install Python 3.12 for you now? (free, from python.org via winget)")) {
        Step "Installing Python 3.12 - this takes a minute..."
        winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
        Refresh-Path
        if (Has-Command "python") {
            $python = "python"
            Ok "Python installed."
        }
    }
    if (-not $python) {
        Fail "Python could not be installed automatically."
        Say ""
        Say "  Do this yourself (takes 2 minutes):" Yellow
        Say "  1. I am opening https://www.python.org/downloads/ in your browser now." Yellow
        Say "  2. Click the big yellow 'Download Python 3.x' button." Yellow
        Say "  3. Run the downloaded file." Yellow
        Say "  4. IMPORTANT: tick the checkbox 'Add python.exe to PATH' at the bottom." Yellow
        Say "  5. Click 'Install Now' and wait." Yellow
        Say "  6. When done, double-click setup.bat again." Yellow
        Start-Process "https://www.python.org/downloads/"
        Exit 1
    }
}

# -- 2. Virtualenv + dependencies ---------------------------------------------
$venvPath = Join-Path $Root ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Step "Creating Python virtual environment (.venv)..."
    if ($python -eq "py -3") { & py -3 -m venv .venv } else { & $python -m venv .venv }
    if (-not (Test-Path $venvPython)) { Fail "Could not create .venv. Re-run setup.bat; if it fails again, delete the .venv folder first."; Exit 1 }
    Ok "Virtual environment created."
} else {
    Ok "Virtual environment already exists."
}

Step "Installing dependencies (first run downloads a few hundred MB - be patient)..."
& $venvPython -m pip install --upgrade pip --quiet
& $venvPython -m pip install -r (Join-Path $Root "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    Fail "Some dependencies failed to install."
    Say "  Fix: check your internet connection, then double-click setup.bat again." Yellow
    Say "  Setup resumes where it left off - nothing is lost." Yellow
    Exit 1
}
Ok "All dependencies installed."

# -- 3. .env + data folders ---------------------------------------------------
Step "Configuring..."
$envPath = Join-Path $Root ".env"
$envIsNew = -not (Test-Path $envPath)
if ($envIsNew) {
    Copy-Item (Join-Path $Root ".env.example") $envPath
    Ok "Created .env from template."
} else {
    Ok ".env already exists - keeping your settings."
}
foreach ($folder in @("data", "data/workspaces", "data/tasks", "data/logs", "data/memory", "data/snapshots")) {
    $p = Join-Path $Root $folder
    if (-not (Test-Path $p)) { New-Item $p -ItemType Directory | Out-Null }
}

# -- 4. Ollama ----------------------------------------------------------------
Step "Checking for Ollama (runs the AI model on your computer, fully private)..."
Refresh-Path
if (-not (Has-Command "ollama")) {
    Warn "Ollama not found."
    if ((Has-Command "winget") -and (Ask "May I install Ollama for you now? (free, from ollama.com via winget)")) {
        winget install --id Ollama.Ollama -e --accept-source-agreements --accept-package-agreements
        Refresh-Path
    }
    if (-not (Has-Command "ollama")) {
        Fail "Ollama could not be installed automatically."
        Say ""
        Say "  Do this yourself (takes 2 minutes):" Yellow
        Say "  1. I am opening https://ollama.com/download in your browser now." Yellow
        Say "  2. Click 'Download for Windows' and run the file." Yellow
        Say "  3. Click through the installer (just keep clicking Next)." Yellow
        Say "  4. When done, double-click setup.bat again." Yellow
        Start-Process "https://ollama.com/download"
        Exit 1
    }
}
Ok "Ollama is installed."

# Make sure the Ollama server is running.
$ollamaUp = $false
try { Invoke-RestMethod "http://localhost:11434/api/version" -TimeoutSec 3 | Out-Null; $ollamaUp = $true } catch {}
if (-not $ollamaUp) {
    Step "Starting Ollama..."
    Start-Process "ollama" "serve" -WindowStyle Hidden
    Start-Sleep 4
    try { Invoke-RestMethod "http://localhost:11434/api/version" -TimeoutSec 5 | Out-Null; $ollamaUp = $true } catch {}
}
if ($ollamaUp) { Ok "Ollama is running." } else { Warn "Ollama did not respond - the model download below may start it itself." }

# -- 5. Hardware check -> model pick -------------------------------------------
Step "Looking at your hardware to pick the right AI model..."

$ramGB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
$vramGB = 0
if (Has-Command "nvidia-smi") {
    try {
        $mib = (& nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>$null | Select-Object -First 1)
        if ($mib) { $vramGB = [math]::Round([int]$mib / 1024) }
    } catch {}
}
Say "    RAM: ${ramGB} GB   |   NVIDIA GPU VRAM: ${vramGB} GB"

# Model ladder by hardware. Sizes are approximate download sizes.
if ($vramGB -ge 8)      { $model = "qwen2.5:7b";  $size = "4.7 GB" }
elseif ($vramGB -ge 4)  { $model = "qwen2.5:3b";  $size = "1.9 GB" }
elseif ($ramGB -ge 16)  { $model = "qwen2.5:3b";  $size = "1.9 GB" }
else                    { $model = "llama3.2:1b"; $size = "1.3 GB" }
Ok "Best model for this computer: $model (download ~$size)"

$haveModel = $false
try { $haveModel = ((& ollama list 2>$null | Out-String) -match [regex]::Escape($model)) } catch {}

if ($haveModel) {
    Ok "Model $model is already downloaded."
} elseif (Ask "May I download $model now? (~$size, one time only)") {
    & ollama pull $model
    if ($LASTEXITCODE -ne 0) {
        Fail "Model download failed."
        Say "  Fix: check your internet connection, then double-click setup.bat again." Yellow
        Say "  Or open a terminal and run:  ollama pull $model" Yellow
        Exit 1
    }
    Ok "Model downloaded."
} else {
    Warn "Skipped. ILLIP needs a model - later, open a terminal and run:  ollama pull $model"
}

# Point ILLIP at the picked model - only on a fresh .env (never touch owner settings).
if ($envIsNew) {
    (Get-Content $envPath) -replace '^OLLAMA_MODEL=.*', "OLLAMA_MODEL=$model" -replace '^MODEL_PROVIDER=.*', 'MODEL_PROVIDER=ollama' | Set-Content $envPath
    Ok ".env set to use $model."
}

# -- 6. Desktop cat -----------------------------------------------------------
Step "Putting the ILLIP cat on your desktop..."
$desktop = [Environment]::GetFolderPath("Desktop")
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut((Join-Path $desktop "ILLIP Cat.lnk"))
$lnk.TargetPath = Join-Path $venvPath "Scripts\pythonw.exe"
$lnk.Arguments = '"' + (Join-Path $Root "scripts\illip_cat.pyw") + '"'
$lnk.WorkingDirectory = $Root
$lnk.Description = "Click the cat to start ILLIP"
$lnk.Save()
Ok "Desktop shortcut 'ILLIP Cat' created."

# -- Done ---------------------------------------------------------------------
Say ""
Say "==========================================" Green
Say "        ILLIP setup is complete!          " Green
Say "==========================================" Green
Say ""
Say "  A little cat now lives on your screen." White
Say "  Click the cat -> ILLIP starts and opens in your browser." White
Say "  Drag the cat anywhere you like. Right-click it to quit." White
Say ""
Say "  Optional (for the browser agent): open a terminal and run:" Gray
Say "    .venv\Scripts\playwright install chromium" Gray
Say ""

if (Ask "Start ILLIP now?") {
    Start-Process (Join-Path $venvPath "Scripts\pythonw.exe") ('"' + (Join-Path $Root "scripts\illip_cat.pyw") + '"') -WorkingDirectory $Root
    Ok "The cat is on your screen - click it!"
}
