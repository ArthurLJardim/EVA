param(
    [int]$SyncEveryMinutes = 30,
    [switch]$InstallDashboard,
    [switch]$InstallWeeklyReport,
    [string]$ActiveStartTime = "08:00",
    [string]$ActiveEndTime = "20:00",
    [string[]]$ActiveDays = @("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SyncScript = Join-Path $PSScriptRoot "run_sync.ps1"
$DashboardScript = Join-Path $PSScriptRoot "run_dashboard_server.ps1"
$StopDashboardScript = Join-Path $PSScriptRoot "stop_dashboard.ps1"
$WeeklyReportScript = Join-Path $PSScriptRoot "run_weekly_report.ps1"
$HiddenLauncher = Join-Path $PSScriptRoot "run_hidden.vbs"

if (-not (Test-Path -LiteralPath $SyncScript)) {
    throw "Script de sync nao encontrado em: $SyncScript"
}

$WScript = "$env:SystemRoot\System32\wscript.exe"

$StartTime = [datetime]::ParseExact($ActiveStartTime, "HH:mm", $null)
$EndTime = [datetime]::ParseExact($ActiveEndTime, "HH:mm", $null)
$ActiveDuration = New-TimeSpan -Start $StartTime -End $EndTime

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew

# --- Sync: roda a cada $SyncEveryMinutes minutos, so entre $ActiveStartTime e $ActiveEndTime, nos dias em $ActiveDays ---
$SyncAction = New-ScheduledTaskAction `
    -Execute $WScript `
    -Argument "`"$HiddenLauncher`" `"$SyncScript`"" `
    -WorkingDirectory $ProjectRoot

$SyncTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $ActiveDays -At $ActiveStartTime
$SyncTrigger.Repetition = (New-ScheduledTaskTrigger `
    -Once -At $ActiveStartTime `
    -RepetitionInterval (New-TimeSpan -Minutes $SyncEveryMinutes) `
    -RepetitionDuration $ActiveDuration).Repetition

Register-ScheduledTask `
    -TaskName "Bot Faculdade Sync" `
    -Action $SyncAction `
    -Trigger $SyncTrigger `
    -Settings $Settings `
    -Description "Sincroniza SIGAA/e-mail/Classroom com a agenda e envia avisos." `
    -Force | Out-Null

Write-Host "Tarefa instalada: Bot Faculdade Sync"
Write-Host "Intervalo: a cada $SyncEveryMinutes minutos, das $ActiveStartTime as $ActiveEndTime, dias: $($ActiveDays -join ', ')."

if ($InstallDashboard) {
    if (-not (Test-Path -LiteralPath $DashboardScript)) {
        throw "Script do dashboard nao encontrado em: $DashboardScript"
    }
    if (-not (Test-Path -LiteralPath $StopDashboardScript)) {
        throw "Script de parada do dashboard nao encontrado em: $StopDashboardScript"
    }

    $DashboardAction = New-ScheduledTaskAction `
        -Execute $WScript `
        -Argument "`"$HiddenLauncher`" `"$DashboardScript`"" `
        -WorkingDirectory $ProjectRoot

    $DashboardStartTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $ActiveDays -At $ActiveStartTime

    Register-ScheduledTask `
        -TaskName "Bot Faculdade Dashboard" `
        -Action $DashboardAction `
        -Trigger $DashboardStartTrigger `
        -Settings $Settings `
        -Description "Mantem o dashboard local do Bot Faculdade no ar (dentro do horario ativo)." `
        -Force | Out-Null

    Write-Host "Tarefa instalada: Bot Faculdade Dashboard"
    Write-Host "Dashboard: http://127.0.0.1:8765/dashboard.html (sobe as $ActiveStartTime)"

    $StopDashboardAction = New-ScheduledTaskAction `
        -Execute $WScript `
        -Argument "`"$HiddenLauncher`" `"$StopDashboardScript`"" `
        -WorkingDirectory $ProjectRoot

    $DashboardStopTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $ActiveDays -At $ActiveEndTime

    Register-ScheduledTask `
        -TaskName "Bot Faculdade Dashboard Stop" `
        -Action $StopDashboardAction `
        -Trigger $DashboardStopTrigger `
        -Settings $Settings `
        -Description "Para o dashboard local fora do horario ativo." `
        -Force | Out-Null

    Write-Host "Tarefa instalada: Bot Faculdade Dashboard Stop"
    Write-Host "Para o dashboard as $ActiveEndTime."
}

if ($InstallWeeklyReport) {
    if (-not (Test-Path -LiteralPath $WeeklyReportScript)) {
        throw "Script de resumo semanal nao encontrado em: $WeeklyReportScript"
    }

    $WeeklyReportAction = New-ScheduledTaskAction `
        -Execute $WScript `
        -Argument "`"$HiddenLauncher`" `"$WeeklyReportScript`"" `
        -WorkingDirectory $ProjectRoot

    $WeeklyTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At "08:00"

    Register-ScheduledTask `
        -TaskName "Bot Faculdade Weekly Report" `
        -Action $WeeklyReportAction `
        -Trigger $WeeklyTrigger `
        -Settings $Settings `
        -Description "Envia o resumo semanal de faltas e medias toda sexta-feira." `
        -Force | Out-Null

    Write-Host "Tarefa instalada: Bot Faculdade Weekly Report"
    Write-Host "Envio: toda sexta-feira as 08:00."
}
