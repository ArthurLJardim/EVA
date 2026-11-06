$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $ProjectRoot "logs"
$LogFile = Join-Path $LogDir "dashboard.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$processes = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'powershell.exe'" |
    Where-Object { $_.CommandLine -like "*serve-dashboard*" -or $_.CommandLine -like "*run_dashboard_server.ps1*" }

foreach ($process in $processes) {
    Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
}

"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Dashboard parado ($($processes.Count) processo(s))." | Tee-Object -FilePath $LogFile -Append
