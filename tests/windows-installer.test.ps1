$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
foreach ($file in Get-ChildItem (Join-Path $root 'tools') -Filter '*windows*.ps1') {
    $tokens = $null; $errors = $null
    [void][Management.Automation.Language.Parser]::ParseFile($file.FullName,[ref]$tokens,[ref]$errors)
    if ($errors.Count) { throw ($errors | Out-String) }
}
. (Join-Path $root 'tools/windows-runtime.ps1')
function Assert-True($Value, $Message) { if (-not $Value) { throw $Message } }
$node = Find-Runtime 'node'
Assert-True ($null -ne $node) 'Node 22+ deve ser detectado, inclusive em caminho com espacos.'
Assert-True (Test-Executable $node @('-e','process.exit(0)')) 'Execucao valida recusada.'
Assert-True (-not (Test-Executable $node @('-e','process.exit(7)'))) 'Erro nativo tratado como sucesso.'
$failed = $false
try { Invoke-Checked $node @('-e','process.exit(7)') } catch { $failed = $true }
Assert-True $failed 'Invoke-Checked precisa interromper a instalacao ao falhar.'
$listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,0)
try {
    $listener.Start()
    $occupied = $listener.LocalEndpoint.Port
    $port = Get-FreePort $occupied @($occupied+1)
    Assert-True ($port -gt ($occupied+1)) 'Porta ocupada ou reservada foi reutilizada.'
} finally { $listener.Stop() }
$before = Test-Path -LiteralPath $RuntimeFile
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'tools/install-windows.ps1') -CheckOnly
Assert-True ($LASTEXITCODE -eq 0) 'Diagnostico falhou.'
Assert-True ((Test-Path -LiteralPath $RuntimeFile) -eq $before) 'Diagnostico gravou configuracao.'
Write-Host 'OK: sintaxe, deteccao, erros nativos, portas e diagnostico sem instalacao.'
