Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Mirrors = @(
    'https://docker.1panel.live',
    'https://hub.1panel.dev',
    'https://docker.m.daocloud.io'
)
$MaxDownloadAttempts = 5

function Get-DockerEngineConfigPath {
    if ([string]::IsNullOrWhiteSpace($HOME)) {
        throw 'HOME is unavailable; cannot locate Docker Desktop daemon.json.'
    }
    return Join-Path $HOME '.docker\daemon.json'
}

function Read-DockerEngineConfig {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return [pscustomobject]@{}
    }
    $raw = Get-Content -LiteralPath $Path -Raw
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return [pscustomobject]@{}
    }
    try {
        return $raw | ConvertFrom-Json
    }
    catch {
        throw "Docker Engine configuration is not valid JSON: $Path"
    }
}

function Set-DaemonOption {
    param(
        [Parameter(Mandatory = $true)][object]$Daemon,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][object]$Value
    )

    $Daemon | Add-Member -NotePropertyName $Name -NotePropertyValue $Value -Force
}

function Test-ExpectedMirrorsApplied {
    try {
        $raw = & docker info --format '{{json .RegistryConfig.Mirrors}}' 2>$null
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($raw)) {
            return $false
        }
        $actual = @($raw | ConvertFrom-Json)
        if ($actual.Count -ne $Mirrors.Count) {
            return $false
        }
        for ($index = 0; $index -lt $Mirrors.Count; $index++) {
            if ($actual[$index].TrimEnd('/') -ne $Mirrors[$index].TrimEnd('/')) {
                return $false
            }
        }
        return $true
    }
    catch {
        return $false
    }
}

function Wait-DockerEngineReady {
    for ($attempt = 1; $attempt -le 60; $attempt++) {
        & docker info *> $null
        if ($LASTEXITCODE -eq 0) {
            return
        }
        Start-Sleep -Seconds 2
    }
    throw 'Docker Desktop did not become ready after applying registry mirrors.'
}

function Configure-DockerDesktopMirrors {
    $dockerPath = Get-Command docker.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $dockerPath) {
        Write-Warning 'Docker Desktop is not installed or docker.exe is not on PATH; Docker Hub mirror setup was skipped. Rerun setup_dev_environment.cmd after Docker Desktop is installed.'
        return
    }

    & docker desktop version *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Warning 'Docker Desktop CLI is unavailable; Docker Hub mirror setup was skipped. Rerun setup_dev_environment.cmd with a current Docker Desktop installation.'
        return
    }

    if (Test-ExpectedMirrorsApplied) {
        Write-Host 'Docker Desktop registry mirrors already match AIMA defaults.'
        return
    }

    $configPath = Get-DockerEngineConfigPath
    $configDirectory = Split-Path -Parent $configPath
    New-Item -ItemType Directory -Path $configDirectory -Force | Out-Null
    $daemon = Read-DockerEngineConfig -Path $configPath
    Set-DaemonOption -Daemon $daemon -Name 'registry-mirrors' -Value $Mirrors
    Set-DaemonOption -Daemon $daemon -Name 'max-download-attempts' -Value $MaxDownloadAttempts

    $backupPath = $null
    if (Test-Path -LiteralPath $configPath) {
        $backupPath = "$configPath.aima-backup-$(Get-Date -Format 'yyyyMMddHHmmss')"
        Copy-Item -LiteralPath $configPath -Destination $backupPath -Force
    }

    $utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
    $daemonJson = $daemon | ConvertTo-Json -Depth 20
    [IO.File]::WriteAllText($configPath, $daemonJson + [Environment]::NewLine, $utf8WithoutBom)

    Write-Host 'Restarting Docker Desktop to apply AIMA Docker Hub mirrors ...'
    & docker desktop restart
    if ($LASTEXITCODE -ne 0) {
        throw "docker desktop restart failed with exit code $LASTEXITCODE"
    }
    Wait-DockerEngineReady

    if (-not (Test-ExpectedMirrorsApplied)) {
        $restoreHint = if ($null -ne $backupPath) {
            " Restore backup if needed: $backupPath"
        }
        else {
            " Remove the newly created file if needed: $configPath"
        }
        throw "Docker Desktop restarted, but docker info does not report the expected registry mirrors.$restoreHint"
    }

    Write-Host 'Docker Desktop registry mirrors configured:'
    foreach ($mirror in $Mirrors) {
        Write-Host "  $mirror"
    }
    Write-Host "Docker Engine config: $configPath"
    if ($null -ne $backupPath) {
        Write-Host "Previous Docker Engine config backup: $backupPath"
    }
}

Configure-DockerDesktopMirrors
