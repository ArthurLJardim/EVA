param(
    [int]$SyncEveryMinutes = 30,
    [switch]$InstallDashboard
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SyncScript = Join-Path $PSScriptRoot "run_sync.ps1"
$DashboardScript = Join-Path $PSScriptRoot "run_dashboard_server.ps1"

if (-not (Test-Path -LiteralPath $SyncScript)) {
    throw "Script de sync nao encontrado em: $SyncScript"
}

$PowerShell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

$SyncAction = New-ScheduledTaskAction `
    -Execute $PowerShell `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$SyncScript`"" `
    -WorkingDirectory $ProjectRoot

$LogonTrigger = New-ScheduledTaskTrigger -AtLogOn
$RepeatTrigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).Date.AddMinutes(5) `
    -RepetitionInterval (New-TimeSpan -Minutes $SyncEveryMinutes) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName "Bot Faculdade Sync" `
    -Action $SyncAction `
    -Trigger @($LogonTrigger, $RepeatTrigger) `
    -Settings $Settings `
    -Description "Sincroniza SIGAA/e-mail/Classroom com a agenda e envia avisos." `
    -Force | Out-Null

Write-Host "Tarefa instalada: Bot Faculdade Sync"
Write-Host "Intervalo: a cada $SyncEveryMinutes minutos e tambem ao fazer login."

if ($InstallDashboard) {
    if (-not (Test-Path -LiteralPath $DashboardScript)) {
        throw "Script do dashboard nao encontrado em: $DashboardScript"
    }

    $DashboardAction = New-ScheduledTaskAction `
        -Execute $PowerShell `
        -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$DashboardScript`"" `
        -WorkingDirectory $ProjectRoot

    Register-ScheduledTask `
        -TaskName "Bot Faculdade Dashboard" `
        -Action $DashboardAction `
        -Trigger $LogonTrigger `
        -Settings $Settings `
        -Description "Mantem o dashboard local do Bot Faculdade no ar." `
        -Force | Out-Null

    Write-Host "Tarefa instalada: Bot Faculdade Dashboard"
    Write-Host "Dashboard: http://127.0.0.1:8765/dashboard.html"
}
