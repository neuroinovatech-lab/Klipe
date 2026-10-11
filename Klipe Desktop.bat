@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0app\dist\Klipe.exe" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\install-windows.ps1"
    if errorlevel 1 (
        pause
        exit /b 1
    )
)
if not exist "%~dp0app\dist\Klipe.exe" exit /b 1
start "" "%~dp0app\dist\Klipe.exe"
