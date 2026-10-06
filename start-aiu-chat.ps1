# Start the local chat dependencies and open the AIU VALORANT web app.
param()

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$difyScript = Join-Path $projectRoot 'start-dify.ps1'
$platformScript = Join-Path $projectRoot 'start-valorant-platform.ps1'

Write-Host 'Starting Ollama, Docker, Dify, and the local chat website. This may take a few minutes.'
& $difyScript -SkipOpenBrowser
& $platformScript
Write-Host 'AIU local chat is open at http://127.0.0.1:8780/#/'
