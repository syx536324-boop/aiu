# Start the local VALORANT web app without opening a visible console window.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$appUrl = 'http://127.0.0.1:8780'

if (-not (Test-Path -LiteralPath $python)) {
    throw "项目 Python 环境不存在：$python"
}

$ready = $false
try {
    $null = Invoke-WebRequest -Uri "$appUrl/api/health" -UseBasicParsing -TimeoutSec 2
    $ready = $true
} catch {
    $ready = $false
}

if (-not $ready) {
    Start-Process -FilePath $python -ArgumentList @('-m', 'valorant_platform') -WorkingDirectory $projectRoot -WindowStyle Hidden
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 500
        try {
            $null = Invoke-WebRequest -Uri "$appUrl/api/health" -UseBasicParsing -TimeoutSec 2
            $ready = $true
            break
        } catch {
            $ready = $false
        }
    }
}

if (-not $ready) {
    throw '本地 Web 服务没有在预期时间内启动。'
}

Start-Process $appUrl
