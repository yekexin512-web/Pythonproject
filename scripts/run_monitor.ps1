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
if ($exitCode -eq 0) {
    & git add docs/index.html docs/dashboard.css *> $null
    & git diff --cached --quiet
    if ($LASTEXITCODE -eq 0) {
        "No GitHub Pages changes to commit." | Out-File -FilePath $logFile -Append -Encoding utf8
    } else {
        & cmd /c "git commit -m `"Update dashboard $(Get-Date -Format 'yyyy-MM-dd')`" >> `"$logFile`" 2>&1"
        $exitCode = $LASTEXITCODE
        if ($exitCode -eq 0) {
            & cmd /c "git push origin main >> `"$logFile`" 2>&1"
            $exitCode = $LASTEXITCODE
        }
    }
}
"==== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') exit $exitCode ====" | Out-File -FilePath $logFile -Append -Encoding utf8

exit $exitCode
