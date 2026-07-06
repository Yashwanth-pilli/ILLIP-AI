@echo off
REM ILLIP launcher — type `illip` in any terminal.
REM   illip                   -> start the web app + open it in the browser (normal chat)
REM   illip code              -> terminal coding agent for serious project work
REM   illip code --continue   -> resume your last terminal conversation
REM   illip build "make X"    -> run the agent crew on a folder
REM   illip status / version  -> other subcommands
cd /d "E:\Projects\ILLIP_AI"

REM No arguments -> start the server + open the browser.
if "%~1"=="" goto :serve

REM Any arguments -> forward to the Python CLI (code / build / status / ...).
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
