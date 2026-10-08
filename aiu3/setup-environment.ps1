# Prepare the project-local Python serial environment with dependencies cached on E drive.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
$uvPath = if ($uvCommand) { $uvCommand.Source } else { Join-Path $env:USERPROFILE '.local\bin\uv.exe' }
if (-not (Test-Path -LiteralPath $uvPath)) { throw 'uv was not found. Install uv first.' }
$env:UV_CACHE_DIR = Join-Path $projectRoot '.uv-cache'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $projectRoot '.python'
Push-Location $projectRoot
try {
    & $uvPath sync --python 3.12
    if ($LASTEXITCODE -ne 0) { throw 'Python environment setup failed.' }
    Write-Host 'Ready: .\.venv\Scripts\python.exe -m host'
}
finally { Pop-Location }

