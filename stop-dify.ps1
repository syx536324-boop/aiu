# Stop Dify services while preserving databases, uploaded files, and other Docker volumes.

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$composeDirectory = Join-Path $projectRoot '.setup\dify-src\docker'
$dockerBin = 'C:\Program Files\Docker\Docker\resources\bin'
$dockerCli = Join-Path $dockerBin 'docker.exe'
$bridgePython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$bridgeHealthUrl = 'http://127.0.0.1:8765/health'

if (-not (Test-Path -LiteralPath $composeDirectory)) {
    throw "Dify Compose directory not found: $composeDirectory"
}
if (-not (Test-Path -LiteralPath $dockerCli)) {
    throw "Docker CLI not found: $dockerCli"
}

$env:PATH = "$dockerBin;$env:PATH"
$bridgeReady = $false
try {
    $bridgeStatus = Invoke-RestMethod -Uri $bridgeHealthUrl -TimeoutSec 3 -ErrorAction Stop
    $bridgeReady = $bridgeStatus.status -eq 'ok' -and $bridgeStatus.service -eq 'aiu-file-bridge'
}
catch {
}
if ($bridgeReady -and (Test-Path -LiteralPath $bridgePython)) {
    Push-Location $projectRoot
    try {
        & $bridgePython -m file_bridge --stop
        if ($LASTEXITCODE -ne 0) {
            throw "AIU file bridge stop failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }
}

Push-Location $composeDirectory
try {
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $dockerCli compose stop
        $composeExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($composeExitCode -ne 0) {
        throw "Dify Compose stop failed with exit code $composeExitCode."
    }
}
finally {
    Pop-Location
}
