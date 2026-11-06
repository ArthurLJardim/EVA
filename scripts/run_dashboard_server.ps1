$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$LogDir = Join-Path $ProjectRoot "logs"
$LogFile = Join-Path $LogDir "dashboard.log"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python da .venv nao encontrado em: $Python"
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location -LiteralPath $ProjectRoot

while ($true) {
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Iniciando dashboard em http://127.0.0.1:8765/dashboard.html" | Tee-Object -FilePath $LogFile -Append
    & $Python -m bot_faculdade serve-dashboard --port 8765 2>&1 | Tee-Object -FilePath $LogFile -Append
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Dashboard parou inesperadamente, reiniciando em 10s..." | Tee-Object -FilePath $LogFile -Append
    Start-Sleep -Seconds 10
}
