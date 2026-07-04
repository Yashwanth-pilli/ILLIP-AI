@echo off
REM ILLIP launcher — type `illip` in any terminal to start ILLIP and open it.
REM (Add this folder to PATH, or copy illip.bat into a folder already on PATH.)
cd /d "E:\Projects\ILLIP_AI"

REM Start the backend (serves the UI too) minimized if not already running.
netstat -ano | findstr ":8000 " | findstr LISTENING >nul 2>&1
if errorlevel 1 (
    echo Starting ILLIP...
    start "ILLIP" /min ".venv\Scripts\python.exe" -m uvicorn app.main:app --port 8000
    REM give the server a moment to boot before opening the browser
    timeout /t 5 /nobreak >nul
) else (
    echo ILLIP already running.
)

start "" "http://localhost:8000"
