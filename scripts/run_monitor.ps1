$ErrorActionPreference = "Stop"

$project = Split-Path -Parent $PSScriptRoot
$python = "D:\anaconda3\python.exe"

Set-Location $project
& $python -m un_intern_monitor.scheduled
exit $LASTEXITCODE
