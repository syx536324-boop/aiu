# Responsibility: locate an existing Node runtime for this project.
function Resolve-Aiu4Node {
    $aiu4Command = Get-Command node.exe -ErrorAction SilentlyContinue
    $aiu4Candidates = @()
    if ($aiu4Command) { $aiu4Candidates += $aiu4Command.Source }
    $aiu4BundleRoot = Join-Path $env:LOCALAPPDATA 'stm32cube\bundles\node'
    if (Test-Path -LiteralPath $aiu4BundleRoot) {
        $aiu4Candidates += Get-ChildItem -LiteralPath $aiu4BundleRoot -Directory | Sort-Object Name -Descending | ForEach-Object { Join-Path $_.FullName 'node\bin\node.exe' }
    }
    foreach ($aiu4Candidate in $aiu4Candidates) {
        if (Test-Path -LiteralPath $aiu4Candidate) {
            $aiu4Version = & $aiu4Candidate --version
            if ($LASTEXITCODE -eq 0 -and [version]($aiu4Version.TrimStart('v')) -ge [version]'22.19.0') { return $aiu4Candidate }
        }
    }
    throw 'Node.js 22.19+ is required: https://nodejs.org/en/download'
}
