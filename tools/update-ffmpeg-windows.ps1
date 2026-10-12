param([string]$Archive = '')
. "$PSScriptRoot\windows-runtime.ps1"
. "$PSScriptRoot\ffmpeg-windows.ps1"
try {
    if (-not (Test-Path -LiteralPath $RuntimeFile)) { throw 'Execute Instalar Klipe.bat primeiro.' }
    $runtime = Get-Content -LiteralPath $RuntimeFile -Raw | ConvertFrom-Json
    $pair = Install-FFmpegRelease -Archive $Archive
    Copy-Item -LiteralPath $RuntimeFile -Destination ($RuntimeFile + '.before-ffmpeg-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.bak')
    $runtime | Add-Member -NotePropertyName ffmpeg -NotePropertyValue $pair.ffmpeg -Force
    $runtime | Add-Member -NotePropertyName ffprobe -NotePropertyValue $pair.ffprobe -Force
    $runtime | ConvertTo-Json | Set-Content -LiteralPath $RuntimeFile -Encoding UTF8
    Write-Host "FFmpeg $($FFmpegRelease.version) pronto. Reinicie o Klipe depois de salvar. Versoes antigas foram preservadas."
} catch { Write-Host $_.Exception.Message -ForegroundColor Red; exit 1 }
