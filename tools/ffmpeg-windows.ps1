Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$FFmpegRelease = Get-Content (Join-Path $PSScriptRoot 'ffmpeg-release.json') -Raw | ConvertFrom-Json

function Test-FFmpegRelease {
    param([string]$Directory)
    foreach ($name in @('ffmpeg','ffprobe')) {
        $exe = Join-Path $Directory "bin\$name.exe"
        if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { return $false }
        $output = & $exe -version 2>&1
        if ($LASTEXITCODE -ne 0 -or ($output -join "`n") -notmatch
            ('(?m)^' + $name + ' version ' + [regex]::Escape($FFmpegRelease.version) + '(?:-|\s)')) { return $false }
    }
    return $true
}

function Test-FFmpegArchive {
    param([string]$Archive)
    if ((Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash -ne $FFmpegRelease.sha256) {
        throw 'FFmpeg: SHA256 nao confere. Nenhum executavel desse pacote foi instalado.'
    }
}

function Install-FFmpegRelease {
    param([string]$Archive = '')
    $base = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'Klipe\ffmpeg'))
    $dest = [IO.Path]::GetFullPath((Join-Path $base $FFmpegRelease.version))
    if (-not $dest.StartsWith($base + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Destino FFmpeg invalido.' }
    if (Test-Path -LiteralPath $dest) {
        if (-not (Test-FFmpegRelease $dest)) { throw "Instalacao incompleta em $dest. Preserve seus projetos e repare essa pasta antes de tentar novamente." }
    } else {
        New-Item -ItemType Directory -Path $base -Force | Out-Null
        $stage = Join-Path $base ('.install-' + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $stage | Out-Null
        try {
            if (-not $Archive) {
                $Archive = Join-Path $stage 'package.zip'
                Write-Host "Baixando FFmpeg $($FFmpegRelease.version) com verificacao SHA256..."
                $ProgressPreference = 'SilentlyContinue'
                Invoke-WebRequest -UseBasicParsing -Uri $FFmpegRelease.url -OutFile $Archive
            }
            Test-FFmpegArchive $Archive
            Expand-Archive -LiteralPath $Archive -DestinationPath (Join-Path $stage 'unpacked')
            $source = [IO.Path]::GetFullPath((Join-Path $stage ('unpacked\' + $FFmpegRelease.directory)))
            if (-not $source.StartsWith($stage + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Origem FFmpeg invalida.' }
            if (-not (Test-FFmpegRelease $source)) { throw 'O pacote nao contem o par FFmpeg/FFprobe esperado.' }
            Move-Item -LiteralPath $source -Destination $dest
        } finally {
            $resolved = [IO.Path]::GetFullPath($stage)
            if ($resolved.StartsWith($base + '\.install-', [StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $resolved)) {
                Remove-Item -LiteralPath $resolved -Recurse -Force
            }
        }
    }
    return @{ffmpeg=(Join-Path $dest 'bin\ffmpeg.exe'); ffprobe=(Join-Path $dest 'bin\ffprobe.exe')}
}
