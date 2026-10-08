# Responsibility: install locked application dependencies into the E-drive project.
$ErrorActionPreference = 'Stop'
$aiu4Root = $PSScriptRoot
. (Join-Path $aiu4Root 'scripts\runtime.ps1')
$aiu4Node = Resolve-Aiu4Node
$aiu4Npm = Join-Path (Split-Path -Parent $aiu4Node) 'npm.cmd'
if (-not (Test-Path -LiteralPath $aiu4Npm)) { throw 'npm.cmd was not found next to Node.js.' }
$aiu4UvCommand = Get-Command uv.exe -ErrorAction SilentlyContinue
$aiu4Uv = if ($aiu4UvCommand) { $aiu4UvCommand.Source } else { Join-Path $env:USERPROFILE '.local\bin\uv.exe' }
if (-not (Test-Path -LiteralPath $aiu4Uv)) { throw 'Install uv first: https://docs.astral.sh/uv/getting-started/installation/' }
$env:UV_CACHE_DIR = Join-Path $aiu4Root '.uv-cache'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $aiu4Root '.python'
$env:Path = (Split-Path -Parent $aiu4Node) + ';' + $env:Path
Push-Location -LiteralPath $aiu4Root
try {
    & $aiu4Npm ci --ignore-scripts --cache (Join-Path $aiu4Root '.npm-cache')
    if ($LASTEXITCODE -ne 0) { throw 'npm dependency installation failed.' }
    & $aiu4Uv sync --frozen --python 3.12
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
    Write-Host 'Setup complete. Run .\start-aiu4.ps1'
} finally { Pop-Location }
