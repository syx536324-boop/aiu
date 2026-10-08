# Responsibility: stop only the Node service recorded by this project launcher.
$ErrorActionPreference = 'Stop'
$aiu4PidFile = Join-Path $PSScriptRoot '.runtime\server.pid'
if (-not (Test-Path -LiteralPath $aiu4PidFile)) { Write-Host 'No AIU4 process record.'; exit }
$aiu4ProcessId = [int]([IO.File]::ReadAllText($aiu4PidFile).Trim())
$aiu4Process = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $aiu4ProcessId)
$aiu4Entry = Join-Path $PSScriptRoot 'src\main.mjs'
if ($aiu4Process -and $aiu4Process.Name -eq 'node.exe' -and $aiu4Process.CommandLine.Contains($aiu4Entry)) {
    Stop-Process -Id $aiu4ProcessId
    Write-Host 'AIU4 stopped. Ollama is left running for other projects.'
} else { Write-Host 'No matching AIU4 process. Other applications were not stopped.' }
