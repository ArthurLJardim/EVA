$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$LogDir = Join-Path $ProjectRoot "logs"
$LogFile = Join-Path $LogDir "sync.log"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python da .venv nao encontrado em: $Python"
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location -LiteralPath $ProjectRoot

"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Iniciando sync" | Tee-Object -FilePath $LogFile -Append
$ErrorActionPreference = "Continue"
$env:PYTHONUNBUFFERED = "1"
& $Python -u -m bot_faculdade sync --notify 2>&1 | Tee-Object -FilePath $LogFile -Append
$ExitCode = $LASTEXITCODE
"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Sync finalizado com codigo $ExitCode" | Tee-Object -FilePath $LogFile -Append

exit $ExitCode
