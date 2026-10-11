Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$KlipeRoot = Split-Path -Parent $PSScriptRoot
$RuntimeFile = Join-Path $KlipeRoot '.klipe-runtime.json'

function Invoke-Checked {
    param([string]$File, [string[]]$Arguments)
    & $File @Arguments | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "Falha ($LASTEXITCODE): $File $($Arguments -join ' ')" }
}

function Test-Executable {
    param([string]$File, [string[]]$Arguments)
    if (-not $File -or -not (Test-Path -LiteralPath $File -PathType Leaf)) { return $false }
    try { & $File @Arguments *> $null; return ($LASTEXITCODE -eq 0) } catch { return $false }
}

function Find-Runtime {
    param([ValidateSet('node','python','ffmpeg','ffprobe')][string]$Name)
    $candidates = @()
    if (Test-Path -LiteralPath $RuntimeFile) {
        try {
            $saved = Get-Content -LiteralPath $RuntimeFile -Raw | ConvertFrom-Json
            if ($saved.PSObject.Properties[$Name]) { $candidates += $saved.$Name }
        } catch { Write-Warning 'Configuracao local invalida; procurando dependencias novamente.' }
    }
    $command = Get-Command "$Name.exe" -CommandType Application -ErrorAction SilentlyContinue
    if ($command) { $candidates += $command.Source }
    switch ($Name) {
        node { $candidates += "$env:ProgramFiles\nodejs\node.exe" }
        python {
            $candidates += @("$env:LOCALAPPDATA\Programs\Python\Python311\python.exe", 'C:\Python311\python.exe')
            foreach ($base in @('anaconda3','miniconda3','.conda')) {
                $candidates += "$env:USERPROFILE\$base\envs\klipe\python.exe"
            }
            foreach ($key in @('HKCU:\Software\Python\PythonCore\3.11\InstallPath','HKLM:\Software\Python\PythonCore\3.11\InstallPath')) {
                if (Test-Path $key) { $candidates += Join-Path (Get-Item $key).GetValue('') 'python.exe' }
            }
        }
        default {
            $candidates += @("$env:LOCALAPPDATA\Klipe\ffmpeg\bin\$Name.exe", "C:\ffmpeg\bin\$Name.exe",
                "$env:LOCALAPPDATA\Microsoft\WinGet\Links\$Name.exe")
        }
    }
    $arguments = switch ($Name) {
        node { @('-e','process.exit(parseInt(process.versions.node) >= 22 ? 0 : 1)') }
        python { @('-c','import sys; sys.exit(0 if sys.version_info[:2] == (3,11) else 1)') }
        default { @('-version') }
    }
    foreach ($file in ($candidates | Select-Object -Unique)) {
        # Never launch the Microsoft Store python execution alias.
        if ($Name -eq 'python' -and $file -like '*\Microsoft\WindowsApps\*') { continue }
        if (Test-Executable $file $arguments) { return $file }
    }
    return $null
}

function Refresh-UserPath {
    $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' +
        [Environment]::GetEnvironmentVariable('Path','User') + ';' + $env:Path
}

function Install-WingetPackage {
    param([string]$Id, [string]$Scope = '')
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw 'Instale/atualize o Instalador de Aplicativo da Microsoft Store (https://aka.ms/getwinget), depois execute Instalar Klipe novamente.'
    }
    $argsList = @('install','--id',$Id,'--exact','--source','winget','--silent',
        '--accept-package-agreements','--accept-source-agreements','--disable-interactivity')
    if ($Scope) { $argsList += @('--scope',$Scope) }
    Invoke-Checked $winget.Source $argsList
    Refresh-UserPath
}

function Get-FreePort {
    param([int]$Start, [int[]]$Exclude = @())
    foreach ($port in $Start..($Start+40)) {
        if ($Exclude -contains $port) { continue }
        $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,$port)
        try { $listener.Start(); return $port } catch {} finally { $listener.Stop() }
    }
    throw 'Nenhuma porta local livre para iniciar o Klipe.'
}
