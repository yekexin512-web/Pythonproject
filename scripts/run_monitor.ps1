$ErrorActionPreference = "Stop"

$project = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $project "logs"
$logFile = Join-Path $logDir "run_monitor.log"
$python = "D:\anaconda3\python.exe"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
Set-Location $project

"==== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') start ====" | Out-File -FilePath $logFile -Append -Encoding utf8
& $python -m un_intern_monitor.main *>> $logFile
$exitCode = $LASTEXITCODE
if ($exitCode -eq 0) {
    & $python -m un_intern_monitor.static_site *>> $logFile
    $exitCode = $LASTEXITCODE
}
"==== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') exit $exitCode ====" | Out-File -FilePath $logFile -Append -Encoding utf8

exit $exitCode
