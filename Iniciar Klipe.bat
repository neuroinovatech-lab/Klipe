@echo off
setlocal enabledelayedexpansion
title Klipe
cd /d "%~dp0"

echo.
echo   Klipe - editor de video
echo   =========================================================
echo.

:: =====================================================================
::  1. Conda e o ambiente "klipe"
::
::  Vem ANTES do Node de proposito: se o Node faltar, e do conda que ele
::  sai. Procurar o Node primeiro seria dar o diagnostico antes de ter a
::  ferramenta de conserto na mao.
::
::  O servidor procura o python sozinho, mas so dentro da pasta do
::  usuario. Aqui olhamos tambem em C:\ProgramData (instalacao para todos
::  os usuarios, comum em maquina de empresa) e passamos o caminho exato
::  em PYTHON_EXE, que o servidor ja sabia ler.
:: =====================================================================
set "PY="
set "CONDA_ROOT="
set "ENVDIR="
for %%D in ("%USERPROFILE%\anaconda3" "%USERPROFILE%\miniconda3" "%USERPROFILE%\.conda" "%LOCALAPPDATA%\anaconda3" "%LOCALAPPDATA%\miniconda3" "C:\ProgramData\anaconda3") do (
    if not defined CONDA_ROOT if exist "%%~D\Scripts\conda.exe" set "CONDA_ROOT=%%~D"
    if not defined PY if exist "%%~D\envs\klipe\python.exe" (
        set "PY=%%~D\envs\klipe\python.exe"
        set "ENVDIR=%%~D\envs\klipe"
    )
)

if not defined PY (
    if not defined CONDA_ROOT (
        echo   [!] Nem o ambiente "klipe" nem o conda foram encontrados.
        echo.
        echo       Sem Python o render, os titulos e as legendas nao rodam.
        echo       Instale o Miniconda:
        echo       https://docs.conda.io/en/latest/miniconda.html
        echo       e abra este arquivo de novo - o resto se resolve sozinho.
        echo.
        pause
        goto :node
    )

    echo   [!] Ambiente "klipe" ainda nao existe.
    echo       Vou criar agora ^(python 3.11 + 6 pacotes, cerca de 500 MB^).
    echo       Leva alguns minutos, e so acontece nesta primeira vez.
    echo.
    choice /c SN /n /m "   Criar agora? [S/N] "
    if errorlevel 2 (
        echo   Pulando.
        goto :node
    )
    echo.
    echo   Criando o ambiente...
    call "!CONDA_ROOT!\Scripts\conda.exe" create -n klipe python=3.11 -y
    if not exist "!CONDA_ROOT!\envs\klipe\python.exe" (
        echo   [X] O conda nao conseguiu criar o ambiente. Veja o erro acima.
        pause
        exit /b 1
    )
    set "PY=!CONDA_ROOT!\envs\klipe\python.exe"
    set "ENVDIR=!CONDA_ROOT!\envs\klipe"
    echo.
    echo   Instalando as dependencias...
    "!PY!" -m pip install -q -r requirements.txt
)

:: ---------------------------------------------------------------------
::  As dependencias estao mesmo la? Testamos IMPORTANDO, e nao olhando o
::  pip list: um ambiente pela metade (criado e nao instalado, instalacao
::  interrompida) passa no segundo teste e quebra no primeiro render.
:: ---------------------------------------------------------------------
if defined PY (
    "!PY!" -c "import skia, numpy" >nul 2>&1
    if errorlevel 1 (
        echo   [!] Faltam dependencias no ambiente. Instalando...
        "!PY!" -m pip install -q -r requirements.txt
        "!PY!" -c "import skia, numpy" >nul 2>&1
        if errorlevel 1 (
            echo   [X] Nao consegui instalar. Rode a mao para ver o erro:
            echo       "!PY!" -m pip install -r requirements.txt
            echo.
            pause
        )
    )
    echo   [ok] Python  !PY!
    set "PYTHON_EXE=!PY!"
)

:node
:: =====================================================================
::  2. Node
::
::  Aqui o Klipe difere do VTrans Pro: la o Node e opcional (resolve o
::  n-challenge do YouTube) e o servidor Python sobe sem ele, entao dava
::  para instalar por um botao na interface. No Klipe o servidor E o Node
::  - nao existe interface para hospedar botao nenhum enquanto ele falta.
::  Por isso a instalacao mora aqui, antes de qualquer coisa subir.
::
::  Procuramos em tres lugares, e o segundo e o que costuma ser esquecido:
::  o nodejs do conda-forge cai na RAIZ da env (envs\klipe\node.exe), nao
::  em Scripts\, e por isso NAO entra no PATH sem ativar o ambiente.
::  Verificado nesta maquina, na env do VTrans. Guardamos o caminho
::  absoluto em NODE e chamamos por ele - nada depende de PATH.
:: =====================================================================
set "NODE="
for /f "delims=" %%n in ('where node 2^>nul') do if not defined NODE set "NODE=%%n"
if not defined NODE if defined ENVDIR if exist "!ENVDIR!\node.exe" set "NODE=!ENVDIR!\node.exe"
if not defined NODE if exist "%ProgramFiles%\nodejs\node.exe" set "NODE=%ProgramFiles%\nodejs\node.exe"

if not defined NODE (
    echo   [!] Node.js nao encontrado - e ele que roda o Klipe.
    echo.
    choice /c SN /n /m "   Instalar agora ^(cerca de 100 MB^)? [S/N] "
    if errorlevel 2 (
        echo.
        echo       Sem Node nao ha o que iniciar. Instale a versao LTS em
        echo       https://nodejs.org e abra este arquivo de novo.
        echo.
        pause
        exit /b 1
    )
    echo.

    rem Primeiro pelo conda, dentro da propria env do Klipe: nao pede
    rem administrador e fica contido no projeto.
    if defined CONDA_ROOT (
        echo   Instalando pelo conda-forge...
        call "!CONDA_ROOT!\Scripts\conda.exe" install -n klipe -c conda-forge nodejs -y --quiet
        if exist "!CONDA_ROOT!\envs\klipe\node.exe" set "NODE=!CONDA_ROOT!\envs\klipe\node.exe"
    )

    rem Se nao deu, o winget. Instala em Program Files, e o PATH desta
    rem janela ja foi lido - por isso apontamos o caminho na mao em vez de
    rem chamar "node" e receber "nao encontrado" logo apos instalar.
    if not defined NODE (
        where winget >nul 2>&1
        if not errorlevel 1 (
            echo   Instalando pelo winget...
            winget install OpenJS.NodeJS.LTS --silent --accept-package-agreements --accept-source-agreements
            if exist "%ProgramFiles%\nodejs\node.exe" set "NODE=%ProgramFiles%\nodejs\node.exe"
        )
    )

    if not defined NODE (
        echo.
        echo   [X] Nao consegui instalar o Node automaticamente.
        echo       Baixe a versao LTS em https://nodejs.org e abra este
        echo       arquivo de novo.
        echo.
        pause
        exit /b 1
    )
    echo   Node instalado.
)

rem Versao velha quebra o servidor com erro de sintaxe, que nao parece
rem problema de versao para quem le. Melhor dizer na cara.
set "NODEVER="
for /f "delims=" %%v in ('"!NODE!" --version 2^>nul') do set "NODEVER=%%v"
set "NODEMAJ=!NODEVER:v=!"
for /f "tokens=1 delims=." %%m in ("!NODEMAJ!") do set "NODEMAJ=%%m"
if defined NODEMAJ if !NODEMAJ! LSS 18 (
    echo   [!] Node !NODEVER! e antigo demais. O Klipe precisa da 18 ou mais nova.
    echo       Atualize em https://nodejs.org
    echo.
    pause
)
echo   [ok] Node !NODEVER!

rem Instala a dependencia local do servidor na primeira execucao. Uma copia
rem limpa nao leva node_modules, entao abrir direto sem isto encerraria o
rem Klipe com "Cannot find module better-sqlite3".
if not exist "node_modules\better-sqlite3\package.json" (
    set "NPM="
    for %%D in ("!NODE!") do if exist "%%~dpDnpm.cmd" set "NPM=%%~dpDnpm.cmd"
    if not defined NPM for /f "delims=" %%n in ('where npm 2^>nul') do if not defined NPM set "NPM=%%n"
    if not defined NPM (
        echo   [X] npm nao encontrado junto do Node.
        echo       Reinstale o Node.js LTS em https://nodejs.org
        pause
        exit /b 1
    )
    echo   Instalando a dependencia local do servidor...
    call "!NPM!" install --no-audit --no-fund
    if errorlevel 1 (
        echo   [X] Nao consegui instalar as dependencias do Klipe.
        pause
        exit /b 1
    )
)

:: =====================================================================
::  3. FFmpeg - aviso, nao barreira: da para abrir o editor e instalar
::  pela interface, em Configuracoes / Render / Instalar.
:: =====================================================================
set "FFOK="
if exist "%LOCALAPPDATA%\Klipe\ffmpeg\bin\ffmpeg.exe" set "FFOK=1"
if exist "C:\ffmpeg\bin\ffmpeg.exe" set "FFOK=1"
where ffmpeg >nul 2>&1
if not errorlevel 1 set "FFOK=1"
if defined FFOK (
    echo   [ok] FFmpeg
) else (
    echo   [!] FFmpeg nao encontrado - o render precisa dele.
    echo       Abra Configuracoes / Render e clique em Instalar.
)

echo.
echo   Abrindo o Klipe
echo   Feche esta janela ^(ou Ctrl+C^) para desligar o Klipe.
echo.

start "" /b cmd /c "timeout /t 3 >nul & start http://localhost:3002"
"!NODE!" editor-server.js

echo.
echo   Klipe encerrado.
pause
