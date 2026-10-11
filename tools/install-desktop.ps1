param([switch]$NoShortcut)
. "$PSScriptRoot\windows-runtime.ps1"
Set-Location -LiteralPath $KlipeRoot
try {
    $base = Find-Runtime 'python'
    if (-not $base) { throw 'Execute Instalar Klipe.bat primeiro.' }
    $webview = @(Get-ItemProperty 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\*',
        'HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\*', 'HKCU:\Software\Microsoft\EdgeUpdate\Clients\*' -ErrorAction SilentlyContinue |
        Where-Object { $_.PSObject.Properties['name'] -and $_.name -like '*WebView2*' -and $_.PSObject.Properties['pv'] -and $_.pv -ne '0.0.0.0' })
    if (-not $webview.Count) { Install-WingetPackage 'Microsoft.EdgeWebView2Runtime' }
    $python = Join-Path $KlipeRoot '.venv-desktop\Scripts\python.exe'
    if (-not (Test-Executable $python @('-c','import pip'))) {
        Invoke-Checked $base @('-m','venv',(Join-Path $KlipeRoot '.venv-desktop'))
    }
    Invoke-Checked $python @('-m','pip','install','-r','requirements-desktop.txt')
    Invoke-Checked $python @('app/build_exe.py')
    if (-not $NoShortcut) {
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Klipe Desktop.lnk'))
        $shortcut.TargetPath = Join-Path $KlipeRoot 'app\dist\Klipe.exe'
        $shortcut.WorkingDirectory = $KlipeRoot
        $shortcut.IconLocation = Join-Path $KlipeRoot 'app\klipe.ico'
        $shortcut.Description = 'Klipe em janela propria'
        $shortcut.Save()
    }
    Write-Host 'Klipe Desktop pronto: app\dist\Klipe.exe'
} catch { Write-Host $_.Exception.Message -ForegroundColor Red; exit 1 }
