@echo off
REM ILLIP launcher — type `illip` in any terminal.
REM   illip                      -> start the server + open the UI (no args)
REM   illip build "make X" -d .  -> run the agent crew on a folder from the terminal
REM   illip do "add tests"       -> build in the current folder
REM   illip status / version     -> CLI subcommands
REM (Add this folder to PATH, or copy illip.bat into a folder already on PATH.)
cd /d "E:\Projects\ILLIP_AI"

REM No arguments -> the original "start server + open browser" behavior.
if "%~1"=="" goto :serve

REM Any arguments -> forward straight to the Python CLI (build/do/status/...).
".venv\Scripts\python.exe" -m app.cli %*
goto :eof

:serve
netstat -ano | findstr ":8000 " | findstr LISTENING >nul 2>&1
if errorlevel 1 (
    echo Starting ILLIP...
    start "ILLIP" /min ".venv\Scripts\python.exe" -m uvicorn app.main:app --port 8000
    timeout /t 5 /nobreak >nul
) else (
    echo ILLIP already running.
)
start "" "http://localhost:8000"
