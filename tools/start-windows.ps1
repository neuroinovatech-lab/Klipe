param([switch]$SmokeTest)
. "$PSScriptRoot\windows-runtime.ps1"
Set-Location -LiteralPath $KlipeRoot
$process = $null
try {
    if (-not (Test-Path -LiteralPath $RuntimeFile)) {
        Write-Host 'Primeiro vamos preparar o Klipe.'
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot\install-windows.ps1"
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $RuntimeFile)) { throw 'Instalacao nao concluida.' }
    }
    $runtime = Get-Content -LiteralPath $RuntimeFile -Raw | ConvertFrom-Json
    foreach ($name in @('node','python','ffmpeg','ffprobe')) {
        if (-not (Test-Path -LiteralPath $runtime.$name -PathType Leaf)) { throw "$name indisponivel. Execute Instalar Klipe.bat novamente." }
    }
    $env:PYTHON_EXE = $runtime.python
    $env:KLIPE_FFMPEG = $runtime.ffmpeg
    $env:KLIPE_FFPROBE = $runtime.ffprobe
    $env:Path = (Split-Path $runtime.node) + ';' + (Split-Path $runtime.ffmpeg) + ';' + $env:Path
    $env:PORT = [string](Get-FreePort 3002)
    $env:MOTIONCORE_PORT = [string](Get-FreePort 3011 @([int]$env:PORT))
    $url = "http://127.0.0.1:$env:PORT"
    $logs = Join-Path $KlipeRoot 'logs'
    New-Item -ItemType Directory -Path $logs -Force | Out-Null
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    $errorLog = Join-Path $logs "servidor-$stamp.err.log"
    $process = Start-Process -FilePath $runtime.node -ArgumentList 'editor-server.js' -WorkingDirectory $KlipeRoot -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs "servidor-$stamp.log") -RedirectStandardError $errorLog
    $ready = $false
    for ($i=0; $i -lt 60; $i++) {
        if ($process.HasExited) { throw "Servidor encerrou. Veja $errorLog" }
        try {
            $response = Invoke-WebRequest -Uri "$url/" -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) { $ready = $true; break }
        } catch {}
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw "O servidor nao ficou pronto. Veja $errorLog" }
    if ($SmokeTest) { Write-Host "OK: servidor respondeu em $url"; exit 0 }
    Start-Process $url
    Write-Host "Klipe aberto em $url"
    Write-Host 'Mantenha esta janela aberta. Ctrl+C encerra o servidor.'
    while (-not $process.HasExited) { Start-Sleep -Seconds 1 }
    if ($process.ExitCode -ne 0) { throw "Klipe encerrou com erro. Veja $errorLog" }
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    if (-not $SmokeTest) { Read-Host 'Pressione Enter para fechar' }
    exit 1
} finally {
    if ($process -and -not $process.HasExited) {
        & taskkill.exe /PID $process.Id /T /F *> $null
    }
}
