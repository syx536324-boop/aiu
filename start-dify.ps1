# Start the local Docker engine and Dify Compose stack, then open the local web UI.

param([switch]$SkipOpenBrowser)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$composeDirectory = Join-Path $projectRoot '.setup\dify-src\docker'
$dockerBin = 'C:\Program Files\Docker\Docker\resources\bin'
$dockerCli = Join-Path $dockerBin 'docker.exe'
$dockerDesktop = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
$ollamaCli = 'C:\Users\shao\AppData\Local\Programs\Ollama\ollama.exe'
$ollamaApi = 'http://127.0.0.1:11434/api/tags'
$bridgePython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$bridgeHealthUrl = 'http://127.0.0.1:8765/health'
$agentUrl = 'http://127.0.0.1/chat/XDl3dp5fj0mhW7mH'

function Test-DockerEngine {
    $ErrorActionPreference = 'Continue'
    & $dockerCli info --format '{{.ServerVersion}}' 2>$null | Out-Null
    return $LASTEXITCODE -eq 0
}

if (-not (Test-Path -LiteralPath $composeDirectory)) {
    throw "Dify Compose directory not found: $composeDirectory"
}
if (-not (Test-Path -LiteralPath $dockerCli)) {
    throw "Docker CLI not found: $dockerCli"
}
if (-not (Test-Path -LiteralPath $ollamaCli)) {
    throw "Ollama CLI not found: $ollamaCli"
}
if (-not (Test-Path -LiteralPath $bridgePython)) {
    throw "Project Python not found: $bridgePython"
}

$env:PATH = "$dockerBin;$env:PATH"

$ollamaTags = $null
try {
    $ollamaTags = Invoke-RestMethod -Uri $ollamaApi -TimeoutSec 3 -ErrorAction Stop
}
catch {
    Start-Process -FilePath $ollamaCli -ArgumentList 'serve' -WindowStyle Hidden | Out-Null
}

$ollamaReady = $false
for ($attempt = 0; $attempt -lt 40; $attempt++) {
    try {
        $ollamaTags = Invoke-RestMethod -Uri $ollamaApi -TimeoutSec 3 -ErrorAction Stop
        $ollamaReady = $true
        break
    }
    catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $ollamaReady) {
    throw 'Ollama did not become ready within 80 seconds.'
}
if (-not ($ollamaTags.models | Where-Object { $_.name -eq 'qwen3.5:4b' })) {
    throw 'The required Ollama model qwen3.5:4b is not installed.'
}

if (-not (Test-DockerEngine)) {
    if (-not (Test-Path -LiteralPath $dockerDesktop)) {
        throw "Docker Desktop not found: $dockerDesktop"
    }
    Start-Process -FilePath $dockerDesktop -WindowStyle Hidden | Out-Null
}

$engineReady = $false
for ($attempt = 0; $attempt -lt 80; $attempt++) {
    if (Test-DockerEngine) {
        $engineReady = $true
        break
    }
    Start-Sleep -Seconds 3
}
if (-not $engineReady) {
    throw 'Docker Engine did not become ready within four minutes.'
}

$bridgeReady = $false
try {
    $bridgeStatus = Invoke-RestMethod -Uri $bridgeHealthUrl -TimeoutSec 3 -ErrorAction Stop
    $bridgeReady = $bridgeStatus.status -eq 'ok' -and $bridgeStatus.service -eq 'aiu-file-bridge'
}
catch {
}
if (-not $bridgeReady) {
    Start-Process -FilePath $bridgePython -ArgumentList '-m file_bridge' -WorkingDirectory $projectRoot -WindowStyle Hidden | Out-Null
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $bridgeStatus = Invoke-RestMethod -Uri $bridgeHealthUrl -TimeoutSec 3 -ErrorAction Stop
            if ($bridgeStatus.status -eq 'ok' -and $bridgeStatus.service -eq 'aiu-file-bridge') {
                $bridgeReady = $true
                break
            }
        }
        catch {
            Start-Sleep -Seconds 2
        }
    }
}
if (-not $bridgeReady) {
    throw 'AIU file bridge did not become ready. Run .venv\Scripts\python.exe -m file_bridge for details.'
}

Push-Location $composeDirectory
try {
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $dockerCli compose up -d
        $composeExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($composeExitCode -ne 0) {
        throw "Dify Compose failed with exit code $composeExitCode."
    }
}
finally {
    Pop-Location
}

$webReady = $false
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    try {
        $response = Invoke-WebRequest -Uri $agentUrl -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        if ([int]$response.StatusCode -lt 500) {
            $webReady = $true
            break
        }
    }
    catch {
        $response = $_.Exception.Response
        if ($null -ne $response -and [int]$response.StatusCode -lt 500) {
            $webReady = $true
            break
        }
    }
    Start-Sleep -Seconds 3
}

if (-not $SkipOpenBrowser) {
    Start-Process -FilePath $agentUrl
}
if ($webReady) {
    Write-Host "Dify agent is ready at $agentUrl"
}
else {
    Write-Host "Dify is starting. If the page shows an error, wait a minute and refresh $agentUrl"
}
