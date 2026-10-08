# Prepare pinned ONNX dependencies and Microsoft's native SDK inside the D-drive project.
$ErrorActionPreference = 'Stop'
$featureRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $featureRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$cachePath = Join-Path $projectRoot '.native-cache'
$env:UV_CACHE_DIR = Join-Path $projectRoot '.uv-cache'
Get-Command g++ -ErrorAction Stop | Out-Null
uv pip install --python $pythonPath --requirement (Join-Path $featureRoot 'requirements.txt') --index-url https://pypi.org/simple
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
New-Item -ItemType Directory -Path $cachePath -Force | Out-Null
$sdkPath = Join-Path $cachePath 'onnxruntime-win-x64-1.23.2'
if (-not (Test-Path -LiteralPath (Join-Path $sdkPath 'lib\onnxruntime.dll'))) {
    $archivePath = Join-Path $cachePath 'onnxruntime-win-x64-1.23.2.zip'
    Invoke-WebRequest -Uri 'https://github.com/microsoft/onnxruntime/releases/download/v1.23.2/onnxruntime-win-x64-1.23.2.zip' -OutFile $archivePath -TimeoutSec 120
    Expand-Archive -LiteralPath $archivePath -DestinationPath $cachePath -Force
}
Write-Output 'Ready. Run: .\.venv\Scripts\python.exe -m native_experiment --iterations 80 --warmups 12 --threads 4'
