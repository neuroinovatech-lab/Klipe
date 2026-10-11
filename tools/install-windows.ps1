param([switch]$Yes, [switch]$SkipVision, [switch]$CheckOnly, [switch]$NoShortcut)
. "$PSScriptRoot\windows-runtime.ps1"
Set-Location -LiteralPath $KlipeRoot
$logging = $false
try {
    if (-not [Environment]::Is64BitOperatingSystem) { throw 'O instalador requer Windows 10/11 de 64 bits.' }
    $runtime = [ordered]@{}
    foreach ($name in @('node','python','ffmpeg','ffprobe')) { $runtime[$name] = Find-Runtime $name }
    Write-Host "`nKlipe - instalacao automatica para Windows`n"
    foreach ($name in $runtime.Keys) { Write-Host ('{0}: {1}' -f $name, $(if($runtime[$name]){$runtime[$name]}else{'sera instalado'})) }
    if ($CheckOnly) { Write-Host 'Diagnostico concluido. Nenhuma instalacao foi executada.'; exit 0 }
    Write-Host "`nSerao instaladas dependencias Node/Python/FFmpeg e criado um ambiente nesta pasta:"
    Write-Host $KlipeRoot
    Write-Host 'Requer internet e espaco em disco. O Windows pode solicitar permissao para instalar o Node.'
    Write-Host 'Nenhum projeto sera apagado. Dependencias existentes compativeis serao reutilizadas.'
    if (-not $SkipVision) { Write-Host 'Inclui Remover fundo: ambiente de visao e modelo local.' }
    if (-not $Yes -and (Read-Host 'Continuar? [S/N]') -notmatch '^(s|sim)$') { exit 0 }
    $logs = Join-Path $KlipeRoot 'logs'
    New-Item -ItemType Directory -Path $logs -Force | Out-Null
    Start-Transcript -Path (Join-Path $logs ('instalacao-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'.log')) | Out-Null
    $logging = $true
    if (-not $runtime.node) { Install-WingetPackage 'OpenJS.NodeJS.22'; $runtime.node = Find-Runtime 'node' }
    if (-not $runtime.python) { Install-WingetPackage 'Python.Python.3.11' 'user'; $runtime.python = Find-Runtime 'python' }
    if (-not $runtime.ffmpeg -or -not $runtime.ffprobe) {
        Install-WingetPackage 'Gyan.FFmpeg' 'user'
        $runtime.ffmpeg = Find-Runtime 'ffmpeg'; $runtime.ffprobe = Find-Runtime 'ffprobe'
    }
    foreach ($name in $runtime.Keys) { if (-not $runtime[$name]) { throw "$name nao foi encontrado depois da instalacao. Feche e execute este instalador novamente." } }
    $env:Path = (Split-Path $runtime.node) + ';' + (Split-Path $runtime.ffmpeg) + ';' + $env:Path
    $npm = Join-Path (Split-Path $runtime.node) 'npm.cmd'
    if (-not (Test-Path -LiteralPath $npm)) { throw 'npm nao encontrado junto do Node. Repare a instalacao do Node.js.' }
    Write-Host "`n[1/4] Dependencias do editor"
    Invoke-Checked $npm @('ci','--no-audit','--no-fund')
    $python = Join-Path $KlipeRoot '.venv\Scripts\python.exe'
    Write-Host "`n[2/4] Ambiente Python isolado"
    if (-not (Test-Executable $python @('-c','import pip'))) {
        Invoke-Checked $runtime.python @('-m','venv',(Join-Path $KlipeRoot '.venv'))
    }
    Invoke-Checked $python @('-c','import sys; assert sys.version_info[:2] == (3,11)')
    Invoke-Checked $python @('-m','pip','install','--upgrade','pip')
    Invoke-Checked $python @('-m','pip','install','-r','requirements.txt')
    Invoke-Checked $python @('-c','import skia, numpy, faster_whisper, requests, yt_dlp, PIL, glfw; from google import genai')
    Invoke-Checked $runtime.node @('-e',"const D=require('better-sqlite3'); const d=new D(':memory:'); d.close()")
    Write-Host "`n[3/4] Remocao de fundo"
    if (-not $SkipVision) {
        Invoke-Checked $python @('tools/setup_assistant_vision.py')
        Invoke-Checked (Join-Path $KlipeRoot '.venv-vision\Scripts\python.exe') @('-c','import mediapipe, cv2')
    }
    Write-Host "`n[4/4] Atalho e configuracao local"
    $runtime.python = $python
    $runtime | ConvertTo-Json | Set-Content -LiteralPath $RuntimeFile -Encoding UTF8
    if (-not $NoShortcut) {
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Klipe.lnk'))
        $shortcut.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
        $shortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $KlipeRoot 'tools\start-windows.ps1') + '"'
        $shortcut.WorkingDirectory = $KlipeRoot
        $shortcut.Description = 'Abrir o editor Klipe'
        $shortcut.Save()
    }
    Write-Host "`nPronto! Abra Iniciar Klipe.bat ou o atalho criado na area de trabalho."
} catch {
    Write-Host "`nERRO: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'Corrija o problema e execute Instalar Klipe novamente. Logs na pasta logs/.'
    exit 1
} finally { if ($logging) { Stop-Transcript | Out-Null } }
