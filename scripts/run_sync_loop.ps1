$ErrorActionPreference = "Continue"

param(
    [int]$SyncEveryMinutes = 30
)

$Script = Join-Path $PSScriptRoot "run_sync.ps1"

while ($true) {
    try {
        powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$Script"
    } catch {
        Write-Host "Falha ao executar sync: $($_.Exception.Message)"
    }

    Start-Sleep -Seconds ($SyncEveryMinutes * 60)
}
