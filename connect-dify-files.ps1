# Register the local file bridge as a Dify API tool and attach it to the existing agent.

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$credentialPath = Join-Path $projectRoot '.setup\dify-admin-credentials.txt'
$tokenPath = Join-Path $projectRoot '.setup\file-bridge-token.txt'
$bridgeSchemaUrl = 'http://127.0.0.1:8765/openapi.json'
$consoleApi = 'http://127.0.0.1/console/api'
$appId = 'cb4e3546-c9d4-4126-937a-cb2fd9669fc8'
$providerName = 'aiu_local_files'
$instructionPath = Join-Path $projectRoot 'file_bridge\dify_instructions.txt'

function Get-CredentialField([string[]]$lines, [string]$name) {
    $line = $lines | Where-Object { $_ -like "${name}:*" } | Select-Object -First 1
    if (-not $line) {
        throw "Missing $name in $credentialPath"
    }
    return ($line -replace "^${name}:\s*", '').Trim()
}

function Invoke-ConsoleApi([string]$path, [string]$method, $body = $null) {
    $requestOptions = @{
        Uri = "$consoleApi$path"
        Method = $method
        WebSession = $session
        Headers = @{ 'X-CSRF-Token' = $csrf }
        TimeoutSec = 30
        ErrorAction = 'Stop'
    }
    if ($null -ne $body) {
        $json = $body | ConvertTo-Json -Depth 100 -Compress
        $requestOptions.ContentType = 'application/json; charset=utf-8'
        $requestOptions.Body = [Text.Encoding]::UTF8.GetBytes($json)
    }
    return Invoke-RestMethod @requestOptions
}

if (-not (Test-Path -LiteralPath $credentialPath)) {
    throw "Dify credentials not found: $credentialPath"
}
if (-not (Test-Path -LiteralPath $tokenPath)) {
    throw "File bridge token not found: $tokenPath. Start the file bridge first."
}

$token = (Get-Content -LiteralPath $tokenPath -Raw).Trim()
if ($token.Length -lt 32 -or $token -notmatch '^[A-Za-z0-9_-]+$') {
    throw 'File bridge token is missing or invalid.'
}

$schemaObject = Invoke-RestMethod -Uri $bridgeSchemaUrl -TimeoutSec 10
if (-not $schemaObject.openapi -or -not $schemaObject.paths) {
    throw 'File bridge did not return a valid OpenAPI schema.'
}
$schema = $schemaObject | ConvertTo-Json -Depth 100 -Compress

$lines = Get-Content -LiteralPath $credentialPath
$email = Get-CredentialField $lines 'Email'
$password = Get-CredentialField $lines 'Password'
$passwordBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($password))
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$loginBody = @{ email = $email; password = $passwordBase64; remember_me = $false } | ConvertTo-Json -Compress
$login = Invoke-RestMethod -Uri "$consoleApi/login" -Method Post -ContentType 'application/json' -Body $loginBody -WebSession $session -TimeoutSec 20
if ($login.result -ne 'success') {
    throw 'Dify administrator login failed.'
}
$csrfCookie = $session.Cookies.GetCookies('http://127.0.0.1/')['csrf_token']
if ($null -eq $csrfCookie) {
    throw 'Dify login did not return a CSRF token.'
}
$csrf = $csrfCookie.Value

$providerPayload = @{
    provider = $providerName
    schema_type = 'openapi'
    schema = $schema
    icon = @{ background = '#E8F5E9'; content = 'F' }
    credentials = @{
        auth_type = 'api_key_header'
        api_key_header = 'Authorization'
        api_key_header_prefix = 'bearer'
        api_key_value = $token
    }
    privacy_policy = ''
    labels = @()
    custom_disclaimer = ''
}

$providers = @(Invoke-ConsoleApi '/workspaces/current/tool-providers?type=api' 'Get')
$provider = $providers | Where-Object { $_.name -eq $providerName } | Select-Object -First 1
if ($provider) {
    $providerPayload.original_provider = $providerName
    $null = Invoke-ConsoleApi '/workspaces/current/tool-provider/api/update' 'Post' $providerPayload
    Write-Host 'Updated the existing Dify file tool provider.'
}
else {
    $null = Invoke-ConsoleApi '/workspaces/current/tool-provider/api/add' 'Post' $providerPayload
    Write-Host 'Registered the Dify file tool provider.'
}

$providers = @(Invoke-ConsoleApi '/workspaces/current/tool-providers?type=api' 'Get')
$provider = $providers | Where-Object { $_.name -eq $providerName } | Select-Object -First 1
if (-not $provider -or -not $provider.id) {
    throw 'Registered Dify tool provider was not found.'
}
$toolRows = @(Invoke-ConsoleApi "/workspaces/current/tool-provider/api/tools?provider=$providerName" 'Get')
$toolNames = @($toolRows | ForEach-Object { $_.name } | Where-Object { $_ })
if ($toolNames.Count -lt 4) {
    throw 'Dify did not discover the file tools from the OpenAPI schema.'
}

$app = Invoke-ConsoleApi "/apps/$appId" 'Get'
if ($app.mode -ne 'agent-chat' -or -not $app.model_config) {
    throw 'Expected Dify agent-chat app configuration was not found.'
}
$config = $app.model_config
$backupPath = Join-Path $projectRoot '.setup\dify-before-file-tools.json'
if (-not (Test-Path -LiteralPath $backupPath)) {
    $backupJson = $config | ConvertTo-Json -Depth 100
    [IO.File]::WriteAllText($backupPath, $backupJson, (New-Object Text.UTF8Encoding($false)))
}
foreach ($field in @('created_by', 'created_at', 'updated_by', 'updated_at')) {
    $config.PSObject.Properties.Remove($field)
}
$retainedTools = @($config.agent_mode.tools | Where-Object {
    $_.provider_id -ne $provider.id -and $_.provider_name -ne $providerName
})
$fileTools = @($toolNames | ForEach-Object {
    @{
        enabled = $true
        provider_type = 'api'
        provider_id = $provider.id
        provider_name = $providerName
        tool_name = $_
        tool_parameters = @{}
    }
})
$config.agent_mode.tools = @($retainedTools) + @($fileTools)

$fileInstructions = (Get-Content -LiteralPath $instructionPath -Raw -Encoding UTF8).Trim()
$prompt = [string]$config.pre_prompt
$prompt = [regex]::Replace($prompt, '(?m)^- [^\r\n]*Dify[^\r\n]*Windows[^\r\n]*(?:\r?\n)?', '')
$oldBlock = [regex]::Match($prompt, '(?s)\[AIU local file bridge\].*?\[/AIU local file bridge\]')
if ($oldBlock.Success) {
    $config.pre_prompt = $prompt.Replace($oldBlock.Value, $fileInstructions)
}
else {
    $config.pre_prompt = $prompt.TrimEnd() + "`n`n" + $fileInstructions
}

$null = Invoke-ConsoleApi "/apps/$appId/model-config" 'Post' $config
$saved = Invoke-ConsoleApi "/apps/$appId" 'Get'
$savedFileTools = @($saved.model_config.agent_mode.tools | Where-Object {
    $_.provider_type -eq 'api' -and $_.provider_id -eq $provider.id -and $_.enabled
})
if ($savedFileTools.Count -ne $toolNames.Count) {
    throw "Dify saved $($savedFileTools.Count) of $($toolNames.Count) file tools."
}
Write-Host "Dify agent now has $($savedFileTools.Count) AIU file tools."
