# Start the local YOLO web app in the background and open its browser page.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$appUrl = 'http://127.0.0.1:8765/'

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Python environment not found: $pythonPath"
}

$listener = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    try {
        Invoke-RestMethod -Uri "${appUrl}api/config" -TimeoutSec 2 | Out-Null
    }
    catch {
        throw 'Port 8765 is already used by another program. Close that program or change the web port before starting AIU YOLO.'
    }
}
if (-not $listener) {
    Start-Process -FilePath $pythonPath -ArgumentList '-m yolo_demo web --host 127.0.0.1 --port 8765' -WorkingDirectory $projectRoot -WindowStyle Hidden
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        Start-Sleep -Milliseconds 500
        $listener = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
        if ($listener) { break }
    }
}

if (-not $listener) {
    throw 'The YOLO web service did not start. Run .\.venv\Scripts\python.exe -m yolo_demo web in PowerShell to view the error.'
}

Start-Process $appUrl

