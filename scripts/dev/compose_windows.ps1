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
    Write-Error "已创建 env.production。请先填写本机需要的 TikHub/LLM/端口配置，然后重新运行本脚本。"
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
