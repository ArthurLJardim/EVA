param(
    [int]$SyncEveryMinutes = 30
)

$ErrorActionPreference = "Stop"

$StartupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$LoopScript = Join-Path $PSScriptRoot "run_sync_loop.ps1"
$ShortcutPath = Join-Path $StartupDir "Bot Faculdade Sync.lnk"
$PowerShell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

if (-not (Test-Path -LiteralPath $LoopScript)) {
    throw "Script de loop nao encontrado em: $LoopScript"
}

New-Item -ItemType Directory -Force -Path $StartupDir | Out-Null

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $PowerShell
$Shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$LoopScript`" -SyncEveryMinutes $SyncEveryMinutes"
$Shortcut.WorkingDirectory = Split-Path -Parent $PSScriptRoot
$Shortcut.WindowStyle = 7
$Shortcut.Description = "Inicia o Bot Faculdade automaticamente ao entrar no Windows."
$Shortcut.Save()

Write-Host "Atalho criado em: $ShortcutPath"
Write-Host "O bot sera iniciado no proximo login e sincronizara a cada $SyncEveryMinutes minutos."
