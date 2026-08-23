[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ComposeArgs
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$envFile = Join-Path $repoRoot "env.production"
$envExample = Join-Path $repoRoot "env.production.example"

if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
    Copy-Item -LiteralPath $envExample -Destination $envFile
    Write-Error "Created env.production. Configure local ports and optional TikHub/LLM settings, then run this script again."
    exit 2
}

if (-not $ComposeArgs -or $ComposeArgs.Count -eq 0) {
    $ComposeArgs = @("up", "-d", "--build", "--wait")
}

Push-Location $repoRoot
try {
    & docker compose `
        -f compose.yaml `
        -f compose.windows.yaml `
        --env-file env.production `
        @ComposeArgs
    $exitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

exit $exitCode
