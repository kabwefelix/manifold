$ErrorActionPreference = "Stop"

$connections = Get-NetTCPConnection -LocalPort 18790 -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique

if (-not $connections) {
    Write-Host "Manifold is not currently running on port 18790."
    exit 0
}

foreach ($processId in $connections) {
    try {
        Stop-Process -Id $processId -Force -ErrorAction Stop
        Write-Host "Stopped Manifold process $processId."
    }
    catch {
        Write-Host "Could not stop process ${processId}: $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
}
