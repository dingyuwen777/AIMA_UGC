[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Version,

    [ValidateSet("china", "official")]
    [string]$SourceProfile = "china",

    [switch]$Verify,

    [switch]$Formal,

    [string]$OutputRoot = "dist/releases"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-PythonCommand {
    <# 选择本机可用的 Python 入口；核心构建脚本只依赖标准库。 #>
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $python) {
        return @($python.Source)
    }

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $py) {
        return @($py.Source, "-3")
    }

    throw "未找到 Python。请先安装 Python 3，或运行仓库开发环境初始化脚本。"
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if ([System.IO.Path]::IsPathRooted($OutputRoot)) {
    $releaseRoot = Join-Path $OutputRoot $Version
}
else {
    $releaseRoot = Join-Path (Join-Path $repoRoot $OutputRoot) $Version
}

$bundleDir = Join-Path $releaseRoot "release-bundle"
$archivePath = Join-Path $releaseRoot "AIMA_UGC-$Version-deploy.tar.gz"
$coreScript = Join-Path $repoRoot "scripts\release\release_bundle.py"
$pythonCommand = @(Resolve-PythonCommand)

$arguments = @(
    $coreScript,
    "build",
    "--root", $repoRoot,
    "--version", $Version,
    "--source-profile", $SourceProfile,
    "--builder-context", "local",
    "--bundle-dir", $bundleDir,
    "--archive-path", $archivePath
)

if ($Verify) {
    $arguments += "--verify"
}
if ($Formal) {
    $arguments += "--formal"
}

Write-Host "AIMA_UGC local Release build"
Write-Host "  Version        : $Version"
Write-Host "  Source profile : $SourceProfile"
Write-Host "  Verify         : $($Verify.IsPresent)"
Write-Host "  Formal         : $($Formal.IsPresent)"
Write-Host "  Output         : $releaseRoot"

$executable = $pythonCommand[0]
$prefixArguments = @()
if ($pythonCommand.Count -gt 1) {
    $prefixArguments = $pythonCommand[1..($pythonCommand.Count - 1)]
}

& $executable @prefixArguments @arguments
if ($LASTEXITCODE -ne 0) {
    throw "本地 Release Bundle 构建失败，exit=$LASTEXITCODE"
}

Write-Host ""
Write-Host "构建完成："
Write-Host "  Bundle  : $bundleDir"
Write-Host "  Archive : $archivePath"
