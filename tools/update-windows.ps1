param([switch]$Yes)
. "$PSScriptRoot\windows-runtime.ps1"
Set-Location -LiteralPath $KlipeRoot
try {
    Write-Host 'Klipe - atualizar codigo oficial e dependencias'
    Write-Host 'Salve seus projetos e feche todas as janelas do Klipe, inclusive o servidor no terminal.'
    if (-not $Yes -and (Read-Host 'Tudo salvo e fechado? Continuar? [S/N]') -notmatch '^(s|sim)$') { exit 0 }
    $running = Get-CimInstance Win32_Process | Where-Object {
        ($_.Name -match '^(node|Klipe)\.exe$') -and
        ($_.Name -eq 'Klipe.exe' -or $_.CommandLine -match 'editor-server\.js')
    }
    if ($running) { throw 'Ainda ha um Klipe/servidor aberto. Feche-o antes de atualizar. Nenhum processo foi encerrado.' }
    $node = Find-Runtime 'node'
    if (-not $node) { throw 'Node nao encontrado. Execute Instalar Klipe.bat.' }
    Invoke-Checked $node @('update-api.js','--closed-update')
    Invoke-Checked 'powershell.exe' @('-NoProfile','-ExecutionPolicy','Bypass','-File',"$PSScriptRoot\install-windows.ps1",'-Yes')
    Write-Host 'Atualizacao concluida. Abra Klipe Desktop ou Iniciar Klipe.'
} catch {
    Write-Host "ERRO: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'Nao apague seus projetos. Consulte docs/ATUALIZACOES.md.'
    exit 1
}
