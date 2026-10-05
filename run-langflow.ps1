$Port = 7861
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$langflowExe = Join-Path $repoRoot ".venv\Scripts\langflow.exe"

if (-not (Test-Path $langflowExe)) {
    throw "Langflow is not installed in .venv. Run: uv sync"
}

$env:LANGFLOW_CONFIG_DIR = Join-Path $repoRoot ".langflow"
$env:LANGFLOW_SAVE_DB_IN_CONFIG_DIR = "true"
& $langflowExe run --host 127.0.0.1 --port $Port
