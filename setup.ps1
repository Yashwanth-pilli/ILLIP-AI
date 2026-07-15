# ILLIP AI - One-click setup.
# Double-click setup.bat. This script:
#   1. Finds or installs Python (asks permission first)
#   2. Creates the virtualenv and installs dependencies
#   3. Finds or installs Ollama (asks permission first)
#   4. Looks at your hardware (GPU VRAM / RAM) and picks the right model
#   5. Downloads the model (asks permission first - it is gigabytes)
#   5a. Optional: browser engine (Playwright) for the web agent
#   5c. Optional: free cloud brain (OmniRoute) - starts it, sets your password,
#       opens the dashboard, and takes your API key to wire up /cloud
#   6. Puts a small cat on your desktop - click the cat to start ILLIP
# Every optional download is explained and asked first, so you decide.
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
    $envText = Get-Content $envPath -Raw
    $envText = $envText -replace '(?m)^OLLAMA_MODEL=.*', "OLLAMA_MODEL=$model"
    $envText = $envText -replace '(?m)^MODEL_PROVIDER=.*', 'MODEL_PROVIDER=ollama'
    [System.IO.File]::WriteAllText($envPath, $envText, [System.Text.UTF8Encoding]::new($false))
    Ok ".env set to use $model."
}

# -- 5a. Optional browser engine (Playwright) ---------------------------------
# Each optional step below explains what it does and asks before downloading, so
# the user decides. All are non-fatal: ILLIP runs fully local without any of them.
Step "Optional: browser engine for ILLIP's web agent..."
Say "  What it does: powers the Browser tool + live page reading (research," Gray
Say "  'read this URL', screenshots). About 150 MB, one time." Gray
Say "  Skip it if you only want to chat - everything else still works." Gray
if (Ask "Download the browser engine (Playwright Chromium) now?") {
    & $venvPython -m playwright install chromium
    if ($LASTEXITCODE -eq 0) { Ok "Browser engine installed." }
    else { Warn "Browser engine had trouble - run later: .venv\Scripts\playwright install chromium" }
}

# -- 5c. Optional free cloud brain (OmniRoute) --------------------------------
Step "Optional: free cloud brain (OmniRoute) for /cloud mode..."
Say "  What it does: runs BIG models in the cloud for FREE (~1.6B tokens/month)" Gray
Say "  so heavy questions do not strain your laptop. Your local model stays the" Gray
Say "  private default - /cloud only sends a request out when you turn it on." Gray
$node = Has-Command "node"
if (-not $node) {
    if ((Has-Command "winget") -and (Ask "Install Node.js? It is required for the free /cloud brain. Say no to stay fully local.")) {
        winget install --id OpenJS.NodeJS.LTS -e --accept-source-agreements --accept-package-agreements
        Refresh-Path
        $node = Has-Command "node"
    }
}
if ($node) {
    $omniCmd   = Join-Path $env:APPDATA "npm\omniroute.cmd"
    $omniReset = Join-Path $env:APPDATA "npm\omniroute-reset-password.cmd"
    if (-not (Test-Path $omniCmd)) {
        if (Ask "Install OmniRoute now? Free cloud-model proxy, one time, a few minutes.") {
            Step "Installing OmniRoute..."
            & npm install -g omniroute --no-fund --no-audit
        }
    } else { Ok "OmniRoute already installed." }

    if ((Test-Path $omniCmd) -and (Ask "Set up /cloud now? I will start OmniRoute, set your password, and open its dashboard so you can make a free API key.")) {
        Step "Starting OmniRoute..."
        Start-Process -FilePath $omniCmd -WindowStyle Minimized
        $up = $false
        for ($i = 0; $i -lt 30; $i++) {
            Start-Sleep -Seconds 2
            try { Invoke-WebRequest "http://127.0.0.1:20128/v1/models" -TimeoutSec 3 -UseBasicParsing | Out-Null; $up = $true; break } catch {}
        }
        if ($up) {
            Ok "OmniRoute is running."
            $omniPass = Read-Host "Choose a password for the OmniRoute dashboard (min 8 characters)"
            if ($omniPass.Length -ge 8 -and (Test-Path $omniReset)) {
                & $omniReset $omniPass | Out-Null
                Ok "Password set. Log in with the password you just chose."
            } else {
                Warn "Skipped password set (need 8+ chars). The dashboard will let you set one."
            }
            Say ""
            Say "  Opening the OmniRoute dashboard in your browser..." White
            Start-Process "http://localhost:20128"
            Say "  In the dashboard:" White
            Say "    1. Log in with your password" Gray
            Say "    2. Connect a FREE provider (Kiro, Pollinations - no card needed)" Gray
            Say "    3. Endpoints -> create an API key -> copy it" Gray
            Say ""
            $key = Read-Host "Paste your OmniRoute API key here (or press Enter to skip)"
            if ($key.Trim().Length -gt 0) {
                $envText = Get-Content $envPath -Raw
                $envText = $envText -replace '(?m)^OPENAI_COMPAT_BASE_URL=.*', 'OPENAI_COMPAT_BASE_URL=http://localhost:20128/v1'
                $envText = $envText -replace '(?m)^OPENAI_COMPAT_API_KEY=.*',  "OPENAI_COMPAT_API_KEY=$($key.Trim())"
                $envText = $envText -replace '(?m)^OPENAI_COMPAT_MODEL=.*',    'OPENAI_COMPAT_MODEL=auto'
                [System.IO.File]::WriteAllText($envPath, $envText, [System.Text.UTF8Encoding]::new($false))
                Ok "Cloud brain connected. In chat: /cloud on for big cloud models, /cloud off for local."
            } else {
                Warn "No key pasted - /cloud stays off. Add it to .env later as OPENAI_COMPAT_API_KEY."
            }
        } else {
            Warn "OmniRoute did not come up in time. It auto-starts with 'illip' - paste your key into .env then."
        }
    }
} else {
    Warn "Node.js not installed - /cloud skipped. ILLIP runs fully local without it."
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
$iconPath = Join-Path $Root "assets\illip-icon.ico"
if (Test-Path $iconPath) { $lnk.IconLocation = $iconPath }
$lnk.Save()
Ok "Desktop shortcut 'ILLIP Cat' created."

# -- Add ILLIP to PATH so 'illip' works from any terminal ---------------------
Step "Adding 'illip' command to your PATH..."
$userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($userPath -split ';' -contains $Root) {
    Ok "'illip' already on PATH."
} else {
    if ([string]::IsNullOrEmpty($userPath)) { $newPath = $Root }
    else { $newPath = $userPath.TrimEnd(';') + ';' + $Root }
    [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
    Ok "Added 'illip' to PATH. Open a NEW terminal, then type: illip"
}

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
