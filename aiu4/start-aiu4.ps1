# Responsibility: start the local paper assistant and open its browser page.
param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
try {
    $aiu4Root = $PSScriptRoot
    . (Join-Path $aiu4Root 'scripts\runtime.ps1')
    $aiu4Node = Resolve-Aiu4Node
    $aiu4Runtime = Join-Path $aiu4Root '.runtime'
    $aiu4Logs = Join-Path $aiu4Root 'logs'
    New-Item -ItemType Directory -Path $aiu4Runtime,$aiu4Logs -Force | Out-Null
    $aiu4Config = Get-Content -LiteralPath (Join-Path $aiu4Root 'config.example.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $aiu4Local = Join-Path $aiu4Runtime 'config.json'
    if (Test-Path -LiteralPath $aiu4Local) {
        $aiu4Overrides = Get-Content -LiteralPath $aiu4Local -Raw -Encoding UTF8 | ConvertFrom-Json
        foreach ($aiu4Property in $aiu4Overrides.PSObject.Properties) { $aiu4Config | Add-Member -MemberType NoteProperty -Name $aiu4Property.Name -Value $aiu4Property.Value -Force }
    }
    $aiu4Url = 'http://127.0.0.1:' + $aiu4Config.port
    $aiu4Ollama = if ($env:AIU4_OLLAMA_URL) { $env:AIU4_OLLAMA_URL } else { $aiu4Config.ollamaUrl }
    if (([Uri]$aiu4Ollama).Host -notin @('127.0.0.1','localhost','[::1]','::1')) { throw 'Only a local Ollama URL is allowed.' }
    $aiu4OllamaExe = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
    try { Invoke-RestMethod -Uri ($aiu4Ollama + '/api/tags') -TimeoutSec 2 | Out-Null }
    catch {
        if (Test-Path -LiteralPath $aiu4OllamaExe) {
            Start-Process -FilePath $aiu4OllamaExe -ArgumentList 'serve' -WindowStyle Hidden -RedirectStandardOutput (Join-Path $aiu4Logs 'ollama.out.log') -RedirectStandardError (Join-Path $aiu4Logs 'ollama.err.log') | Out-Null
        } else { Write-Warning 'Ollama is missing. Paper search and collection still work.' }
    }
    # Create only a local alias; this reuses the installed model blobs and does not pull a model.
    if ($aiu4Config.model -eq 'aiu4-research:latest' -and (Test-Path -LiteralPath $aiu4OllamaExe)) {
        $aiu4Tags = $null
        for ($aiu4Wait=0; $aiu4Wait -lt 10; $aiu4Wait++) {
            try { $aiu4Tags=Invoke-RestMethod -Uri ($aiu4Ollama + '/api/tags') -TimeoutSec 2; break } catch { Start-Sleep -Milliseconds 500 }
        }
        if ($aiu4Tags -and 'aiu4-research:latest' -notin @($aiu4Tags.models.name) -and 'qwen3.5:4b' -in @($aiu4Tags.models.name)) {
            & $aiu4OllamaExe create aiu4-research -f (Join-Path $aiu4Root 'Modelfile')
            if ($LASTEXITCODE -ne 0) { Write-Warning 'Local model alias creation failed. Paper search remains available.' }
        }
    }
    $aiu4Existing = $null
    try { $aiu4Existing = Invoke-RestMethod -Uri ($aiu4Url + '/api/status') -TimeoutSec 3 } catch { }
    if ($aiu4Existing -and $aiu4Existing.app -ne 'aiu4') { throw 'The configured port belongs to another service.' }
    if ($aiu4Existing -and [IO.Path]::GetFullPath($aiu4Existing.root) -ne [IO.Path]::GetFullPath($aiu4Root)) { throw 'This port belongs to a different AIU4 project directory.' }
    if (-not $aiu4Existing) {
        if (-not (Test-Path -LiteralPath (Join-Path $aiu4Root 'node_modules\@earendil-works\pi-agent-core'))) { throw 'Run setup-aiu4.ps1 first.' }
        $aiu4Entry = Join-Path $aiu4Root 'src\main.mjs'
        $aiu4Process = Start-Process -FilePath $aiu4Node -ArgumentList @(('"' + $aiu4Entry + '"'),'serve') -WorkingDirectory $aiu4Root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $aiu4Logs 'server.out.log') -RedirectStandardError (Join-Path $aiu4Logs 'server.err.log')
        [IO.File]::WriteAllText((Join-Path $aiu4Runtime 'server.pid'), [string]$aiu4Process.Id)
        $aiu4Ready = $false
        for ($aiu4Attempt=0; $aiu4Attempt -lt 20; $aiu4Attempt++) {
            Start-Sleep -Milliseconds 500
            if ($aiu4Process.HasExited) { throw ('Server stopped. See ' + (Join-Path $aiu4Logs 'server.err.log')) }
            try { $aiu4Status = Invoke-RestMethod -Uri ($aiu4Url + '/api/status') -TimeoutSec 3; if ($aiu4Status.app -eq 'aiu4') { $aiu4Ready=$true; break } } catch { }
        }
        if (-not $aiu4Ready) { throw 'Server startup timed out. See logs/server.err.log.' }
    }
    if (-not $NoBrowser) { Start-Process $aiu4Url }
    Write-Host ('AIU4 is running: ' + $aiu4Url)
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    if (-not $NoBrowser) { Read-Host 'Press Enter to close' | Out-Null }
    exit 1
}
