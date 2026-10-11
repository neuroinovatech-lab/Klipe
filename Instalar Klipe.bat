@echo off
setlocal
title Instalar Klipe
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\install-windows.ps1" %*
set "RESULT=%ERRORLEVEL%"
echo.
if not "%RESULT%"=="0" echo A instalacao nao terminou. Veja o erro acima e execute novamente.
pause
exit /b %RESULT%
