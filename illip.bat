@echo off
REM ILLIP launcher — type `illip` in any terminal.
REM   illip                   -> start the web app + open it in the browser (normal chat)
REM   illip code              -> terminal coding agent in a fresh window (serious work)
REM   illip code --continue   -> resume your last terminal conversation
REM   illip build "make X"    -> run the agent crew on a folder
REM   illip repair            -> fix a stuck/broken ILLIP (kill, heal, rollback, restart)
REM   illip stop              -> close ILLIP + Ollama, notify what was closed
REM   illip status / version  -> other subcommands
set "ILLIPDIR=E:\Projects\ILLIP_AI"
set "PY=%ILLIPDIR%\.venv\Scripts\python.exe"

REM No arguments -> start the server + open the browser.
if "%~1"=="" goto :serve

REM `illip code` -> open a CLEAN new terminal window running the agent. The new
REM window inherits YOUR current folder as its working dir (we don't cd here),
REM so it builds where you are. PYTHONPATH lets Python find the app package.
if /i "%~1"=="code" (
    set "PYTHONPATH=%ILLIPDIR%"
    start "ILLIP Code" cmd /k "%PY% -m app.cli %*"
    goto :eof
)

REM `illip repair` -> standalone recovery script (works even when app code
REM is broken — imports nothing from the app).
if /i "%~1"=="repair" (
    cd /d "%ILLIPDIR%"
    "%PY%" scripts\repair.py
    goto :eof
)

REM `illip stop` -> close the ILLIP server + Ollama, notify what was closed.
if /i "%~1"=="stop" (
    cd /d "%ILLIPDIR%"
    "%PY%" scripts\stop.py
    goto :eof
)

REM other subcommands run inline
cd /d "%ILLIPDIR%"
"%PY%" -m app.cli %*
goto :eof

:serve
cd /d "%ILLIPDIR%"

REM Start Ollama first so the server picks it up instead of falling back to Mock.
netstat -ano | findstr ":11434 " | findstr LISTENING >nul 2>&1
if errorlevel 1 (
    where ollama >nul 2>&1
    if errorlevel 1 (
        echo Ollama not found on PATH — skipping, ILLIP will fall back to cloud/mock.
    ) else (
        echo Starting Ollama...
        start "Ollama" /min ollama serve
        timeout /t 5 /nobreak >nul
    )
) else (
    echo Ollama already running.
)

REM Start OmniRoute (free cloud-model proxy) so /cloud mode works. Only if it's
REM installed; skipped silently otherwise. Runs in its own minimized window.
netstat -ano | findstr ":20128 " | findstr LISTENING >nul 2>&1
if errorlevel 1 (
    if exist "%APPDATA%\npm\omniroute.cmd" (
        echo Starting OmniRoute...
        start "OmniRoute" /min "%APPDATA%\npm\omniroute.cmd"
    )
) else (
    echo OmniRoute already running.
)

netstat -ano | findstr ":8000 " | findstr LISTENING >nul 2>&1
if errorlevel 1 (
    echo Starting ILLIP...
    start "ILLIP" /min "%PY%" -m uvicorn app.main:app --port 8000
    timeout /t 5 /nobreak >nul
) else (
    echo ILLIP already running.
)
start "" "http://localhost:8000"
