@echo off
setlocal
title Klipe
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\start-windows.ps1"
exit /b %ERRORLEVEL%
