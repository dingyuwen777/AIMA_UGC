Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Mirrors = @(
    'https://docker.1panel.live',
    'https://hub.1panel.dev',
    'https://docker.m.daocloud.io'
)
$MaxDownloadAttempts = 5

function Get-DockerDesktopSettingsPath {
    if ([string]::IsNullOrWhiteSpace($env:APPDATA)) {
        throw 'APPDATA is unavailable; cannot locate Docker Desktop settings-store.json.'
    }
    return Join-Path $env:APPDATA 'Docker\settings-store.json'
}

function ConvertFrom-DaemonOptions {
    param([AllowNull()][object]$Value)

    if ($null -eq $Value) {
        return [pscustomobject]@{}
    }
    if ($Value -is [string]) {
        if ([string]::IsNullOrWhiteSpace($Value)) {
            return [pscustomobject]@{}
        }
        return $Value | ConvertFrom-Json
    }
    return $Value
}

function Set-DaemonOption {
    param(
        [Parameter(Mandatory = $true)][object]$Daemon,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][object]$Value
    )

    $Daemon | Add-Member -NotePropertyName $Name -NotePropertyValue $Value -Force
}

function Get-DockerDesktopDaemonSlot {
    param([Parameter(Mandatory = $true)][object]$Settings)

    $topLevel = $Settings.PSObject.Properties['dockerDaemonOptions']
    if ($null -ne $topLevel) {
        return [pscustomobject]@{
            Kind = 'top-level'
            Value = $topLevel.Value
        }
    }

    $linuxVm = $Settings.PSObject.Properties['linuxVM']
    if ($null -ne $linuxVm -and $null -ne $linuxVm.Value) {
        $daemonOptions = $linuxVm.Value.PSObject.Properties['dockerDaemonOptions']
        if ($null -ne $daemonOptions -and $null -ne $daemonOptions.Value) {
            $valueProperty = $daemonOptions.Value.PSObject.Properties['value']
            if ($null -ne $valueProperty) {
                return [pscustomobject]@{
                    Kind = 'linux-vm'
                    Value = $valueProperty.Value
                }
            }
        }
    }

    return [pscustomobject]@{
        Kind = 'new-top-level'
        Value = $null
    }
}

function Set-DockerDesktopDaemonSlot {
    param(
        [Parameter(Mandatory = $true)][object]$Settings,
        [Parameter(Mandatory = $true)][string]$Kind,
        [Parameter(Mandatory = $true)][string]$Value
    )

    switch ($Kind) {
        'top-level' {
            $Settings.dockerDaemonOptions = $Value
        }
        'linux-vm' {
            $Settings.linuxVM.dockerDaemonOptions.value = $Value
        }
        'new-top-level' {
            $Settings | Add-Member -NotePropertyName 'dockerDaemonOptions' -NotePropertyValue $Value
        }
        default {
            throw "Unsupported Docker Desktop settings layout: $Kind"
        }
    }
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
        Write-Warning 'Docker Desktop is not installed or docker.exe is not on PATH; registry mirror setup was skipped. Rerun setup_dev_environment.cmd after Docker Desktop is installed.'
        return
    }

    & docker desktop version *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Warning 'Docker Desktop CLI is unavailable; registry mirror setup was skipped. Rerun setup_dev_environment.cmd with a current Docker Desktop installation.'
        return
    }

    if (Test-ExpectedMirrorsApplied) {
        Write-Host 'Docker Desktop registry mirrors already match AIMA defaults.'
        return
    }

    $settingsPath = Get-DockerDesktopSettingsPath
    if (-not (Test-Path -LiteralPath $settingsPath)) {
        throw "Docker Desktop settings file is missing: $settingsPath. Start Docker Desktop once, then rerun setup_dev_environment.cmd."
    }

    $settings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
    $slot = Get-DockerDesktopDaemonSlot -Settings $settings
    $daemon = ConvertFrom-DaemonOptions -Value $slot.Value
    Set-DaemonOption -Daemon $daemon -Name 'registry-mirrors' -Value $Mirrors
    Set-DaemonOption -Daemon $daemon -Name 'max-download-attempts' -Value $MaxDownloadAttempts
    $daemonJson = $daemon | ConvertTo-Json -Compress -Depth 20
    Set-DockerDesktopDaemonSlot -Settings $settings -Kind $slot.Kind -Value $daemonJson

    $backupPath = "$settingsPath.aima-backup-$(Get-Date -Format 'yyyyMMddHHmmss')"
    Copy-Item -LiteralPath $settingsPath -Destination $backupPath -Force

    Write-Host 'Stopping Docker Desktop before updating Docker Engine settings ...'
    & docker desktop stop
    if ($LASTEXITCODE -ne 0) {
        throw "docker desktop stop failed with exit code $LASTEXITCODE"
    }

    $utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
    $settingsJson = $settings | ConvertTo-Json -Depth 100
    [IO.File]::WriteAllText($settingsPath, $settingsJson + [Environment]::NewLine, $utf8WithoutBom)

    Write-Host 'Starting Docker Desktop with AIMA Docker Hub mirrors ...'
    & docker desktop start
    if ($LASTEXITCODE -ne 0) {
        throw "docker desktop start failed with exit code $LASTEXITCODE"
    }
    Wait-DockerEngineReady

    if (-not (Test-ExpectedMirrorsApplied)) {
        throw "Docker Desktop started, but docker info does not report the expected registry mirrors. Restore backup if needed: $backupPath"
    }

    Write-Host 'Docker Desktop registry mirrors configured:'
    foreach ($mirror in $Mirrors) {
        Write-Host "  $mirror"
    }
    Write-Host "Docker Desktop settings backup: $backupPath"
}

Configure-DockerDesktopMirrors
