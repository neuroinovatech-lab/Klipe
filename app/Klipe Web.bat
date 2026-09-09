@echo off
chcp 65001 > nul
title Klipe (modo web)
color 0E
setlocal enabledelayedexpansion

rem  Modo WEB do Klipe: mesmo servidor do app de desktop, so que aberto no
rem  navegador e visivel pros outros aparelhos da rede. Da pra abrir do celular
rem  ou de outro PC usando o endereco da rede que aparece abaixo.
rem
rem  O app de desktop (Klipe.exe) fala com ESTE mesmo servidor. Se voce abrir os
rem  dois, o app se pluga aqui em vez de subir outro.

cd /d "%~dp0.."

echo.
echo  ============================================
echo    KLIPE - modo web
echo  ============================================
echo.

rem  Descobre o IP da rede local. Via PowerShell, e nao pelo ipconfig, por dois
rem  motivos: o texto do ipconfig muda de idioma, e o primeiro IP da lista aqui
rem  e o de VPN (26.x) — mostrar ele mandaria voce pro endereco errado.
set "IPREDE="
for /f "usebackq delims=" %%a in (`powershell -NoProfile -Command ^
  "@(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like '192.168.*' -or $_.IPAddress -like '10.*' -or $_.IPAddress -like '172.1*' } | Select-Object -First 1 -ExpandProperty IPAddress)"`) do (
  set "IPREDE=%%a"
)

echo  [1/2] Subindo o servidor na porta 3002...
start "Klipe Server" cmd /k "node editor-server.js"

echo  [2/2] Esperando o servidor responder...
timeout /t 4 /nobreak > nul

start "" "http://localhost:3002/"

echo.
echo  ============================================
echo   Neste PC        http://localhost:3002
if defined IPREDE echo   Na rede (celular) http://%IPREDE%:3002
echo.
echo   Pra parar, feche a janela "Klipe Server".
echo  ============================================
echo.
timeout /t 8 /nobreak > nul
exit
