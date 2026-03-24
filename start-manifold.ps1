$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $repoRoot "venv\Scripts\python.exe"
$runDir = Join-Path $repoRoot "manifold"
$monitorUrl = "http://127.0.0.1:18790/"
$envFile = Join-Path $repoRoot ".env"
$defaultManifoldHome = $runDir

function Import-DotEnv {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }

        $parts = $line.Split("=", 2)
        $name = $parts[0].Trim()
        $value = $parts[1].Trim()

        if (
            ($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))
        ) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

if (-not (Test-Path $pythonExe)) {
    Write-Host "Python virtualenv not found at $pythonExe" -ForegroundColor Red
    Write-Host "Create it first, then rerun this launcher." -ForegroundColor Yellow
    exit 1
}

if (Test-Path $envFile) {
    Import-DotEnv -Path $envFile
}

$configuredManifoldHome = $env:MANIFOLD_HOME
$placeholderHome = "/absolute/path/to/manifold/data"

if (
    [string]::IsNullOrWhiteSpace($configuredManifoldHome) -or
    $configuredManifoldHome -eq $placeholderHome -or
    -not (Test-Path $configuredManifoldHome)
) {
    $env:MANIFOLD_HOME = $defaultManifoldHome
}

New-Item -ItemType Directory -Force -Path $env:MANIFOLD_HOME | Out-Null

Write-Host ""
Write-Host "Starting Manifold..." -ForegroundColor Cyan
Write-Host "Server:  http://127.0.0.1:18790"
Write-Host "Monitor: $monitorUrl"
Write-Host "Data:    $($env:MANIFOLD_HOME)"
Write-Host ""

$isPortOpen = $false
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $tcp.Connect("127.0.0.1", 18790)
    if ($tcp.Connected) {
        $isPortOpen = $true
        $tcp.Close()
    }
} catch {
    $isPortOpen = $false
}

if ($isPortOpen) {
    Write-Host "Manifold is already running. Opening the monitor..." -ForegroundColor Yellow
    Start-Process $monitorUrl | Out-Null
    Start-Sleep -Seconds 2
    exit 0
}

# Spawn a silent background job to poll the port so we load the web UI the exact millisecond the server finishes booting.
$jobScript = {
    param($url)
    $portOpen = $false
    while (-not $portOpen) {
        try {
            $tcp = New-Object System.Net.Sockets.TcpClient
            $tcp.Connect("127.0.0.1", 18790)
            if ($tcp.Connected) {
                $portOpen = $true
                $tcp.Close()
            }
        } catch {
            Start-Sleep -Milliseconds 400
        }
    }
    Start-Process $url | Out-Null
}
Start-Job -ScriptBlock $jobScript -ArgumentList $monitorUrl | Out-Null

Push-Location $runDir
try {
    & $pythonExe -m manifold.agent_server
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}
