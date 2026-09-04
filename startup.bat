@echo off
setlocal
cd /d "%~dp0"

if "%PORT%"=="" set "PORT=8765"
echo [CONFIG] API port: %PORT%

where uv >nul 2>nul
if errorlevel 1 (
    echo [ERROR] uv was not found. Install uv and reopen the terminal.
    exit /b 1
)

echo [1/2] Syncing project dependencies...
uv sync
if errorlevel 1 (
    echo [ERROR] Dependency sync failed.
    exit /b 1
)

echo [2/2] Starting API and Momo in this console session...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\startup.ps1" -ProjectRoot "%~dp0." -Port "%PORT%"
exit /b %errorlevel%

endlocal
