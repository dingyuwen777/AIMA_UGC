Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$MaxDownloadAttempts = 5
$DockerDesktopRestartTimeoutSeconds = 60
$MirrorVerificationTimeoutSeconds = 20
$MirrorProbeTimeoutSeconds = 3
$MirrorProbeCleanupTimeoutMilliseconds = 1000
$MirrorVerificationIntervalSeconds = 1
$MirrorConfigPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'config\docker_hub_mirrors.txt'

function ConvertTo-MirrorIdentity {
    param([Parameter(Mandatory = $true)][string]$Mirror)

    return $Mirror.Trim().TrimEnd('/').ToLowerInvariant()
}

function Read-DockerHubMirrors {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Docker Hub mirror configuration was not found: $Path"
    }

    $mirrors = @(
        Get-Content -LiteralPath $Path |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ -and -not $_.StartsWith('#') }
    )
    if ($mirrors.Count -eq 0) {
        throw "Docker Hub mirror configuration is empty: $Path"
    }

    $seen = @{}
    foreach ($mirror in $mirrors) {
        $uri = $null
        if (-not [Uri]::TryCreate($mirror, [UriKind]::Absolute, [ref]$uri) -or $uri.Scheme -ne 'https') {
            throw "Docker Hub mirror must be an absolute HTTPS URL: $mirror"
        }
        $identity = ConvertTo-MirrorIdentity -Mirror $mirror
        if ($seen.ContainsKey($identity)) {
            throw "Duplicate Docker Hub mirror in configuration: $mirror"
        }
        $seen[$identity] = $true
    }

    return $mirrors
}

$Mirrors = @(Read-DockerHubMirrors -Path $MirrorConfigPath)

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

function Test-AimaDaemonConfigMatches {
    param([Parameter(Mandatory = $true)][object]$Daemon)

    if ($null -eq $Daemon.PSObject.Properties['registry-mirrors']) {
        return $false
    }
    if ($null -eq $Daemon.PSObject.Properties['max-download-attempts']) {
        return $false
    }

    $configuredMirrors = @($Daemon.'registry-mirrors')
    if ($configuredMirrors.Count -ne $Mirrors.Count) {
        return $false
    }
    for ($index = 0; $index -lt $Mirrors.Count; $index++) {
        if (
            (ConvertTo-MirrorIdentity -Mirror ([string]$configuredMirrors[$index])) -ne
            (ConvertTo-MirrorIdentity -Mirror $Mirrors[$index])
        ) {
            return $false
        }
    }

    try {
        return ([int]$Daemon.'max-download-attempts') -eq $MaxDownloadAttempts
    }
    catch {
        return $false
    }
}

function Test-ExpectedMirrorsPresent {
    param([Parameter(Mandatory = $true)][string[]]$ActualMirrors)

    # Docker Desktop may add mirrors from settings outside AIMA. AIMA only requires
    # its managed mirrors to be present in their configured relative order.
    $actual = @($ActualMirrors)
    $searchFrom = 0
    foreach ($expectedMirror in $Mirrors) {
        $expectedIdentity = ConvertTo-MirrorIdentity -Mirror $expectedMirror
        $foundAt = -1
        for ($index = $searchFrom; $index -lt $actual.Count; $index++) {
            if ((ConvertTo-MirrorIdentity -Mirror ([string]$actual[$index])) -eq $expectedIdentity) {
                $foundAt = $index
                break
            }
        }
        if ($foundAt -lt 0) {
            return $false
        }
        $searchFrom = $foundAt + 1
    }
    return $true
}

function Get-AdditionalRegistryMirrors {
    param([Parameter(Mandatory = $true)][string[]]$ActualMirrors)

    $managed = @{}
    foreach ($mirror in $Mirrors) {
        $managed[(ConvertTo-MirrorIdentity -Mirror $mirror)] = $true
    }

    return @(
        $ActualMirrors | Where-Object {
            -not $managed.ContainsKey((ConvertTo-MirrorIdentity -Mirror ([string]$_)))
        }
    )
}

function Get-DockerRegistryMirrorProbe {
    param([int]$TimeoutSeconds = $MirrorProbeTimeoutSeconds)

    $dockerCommand = Get-Command docker.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $dockerCommand) {
        return [pscustomobject]@{
            Succeeded = $false
            TimedOut = $false
            Mirrors = @()
            Error = 'docker.exe is not available on PATH.'
        }
    }

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $dockerCommand.Source
    $startInfo.Arguments = 'info --format "{{json .RegistryConfig.Mirrors}}"'.Replace('\"', '"')
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    try {
        [void]$process.Start()
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            try {
                $process.Kill()
                [void]$process.WaitForExit($MirrorProbeCleanupTimeoutMilliseconds)
            }
            catch {
                # Best effort cleanup; the probe result remains a timeout.
            }
            return [pscustomobject]@{
                Succeeded = $false
                TimedOut = $true
                Mirrors = @()
                Error = "docker info exceeded the ${TimeoutSeconds}s probe timeout."
            }
        }

        $stdout = $process.StandardOutput.ReadToEnd().Trim()
        $stderr = $process.StandardError.ReadToEnd().Trim()
        if ($process.ExitCode -ne 0) {
            return [pscustomobject]@{
                Succeeded = $false
                TimedOut = $false
                Mirrors = @()
                Error = if ($stderr) { $stderr } else { "docker info exited with code $($process.ExitCode)." }
            }
        }
        if ([string]::IsNullOrWhiteSpace($stdout)) {
            return [pscustomobject]@{
                Succeeded = $false
                TimedOut = $false
                Mirrors = @()
                Error = 'docker info returned an empty registry mirror payload.'
            }
        }

        try {
            $actual = @($stdout | ConvertFrom-Json)
        }
        catch {
            return [pscustomobject]@{
                Succeeded = $false
                TimedOut = $false
                Mirrors = @()
                Error = "docker info returned invalid registry mirror JSON: $stdout"
            }
        }

        return [pscustomobject]@{
            Succeeded = $true
            TimedOut = $false
            Mirrors = [string[]]$actual
            Error = ''
        }
    }
    catch {
        return [pscustomobject]@{
            Succeeded = $false
            TimedOut = $false
            Mirrors = @()
            Error = $_.Exception.Message
        }
    }
    finally {
        $process.Dispose()
    }
}

function Write-EffectiveMirrorState {
    param([Parameter(Mandatory = $true)][string[]]$ActualMirrors)

    Write-Host 'AIMA Docker Hub registry mirrors are active:'
    foreach ($mirror in $Mirrors) {
        Write-Host "  $mirror"
    }

    $additional = @(Get-AdditionalRegistryMirrors -ActualMirrors $ActualMirrors)
    if ($additional.Count -gt 0) {
        Write-Warning 'Docker Desktop also reports additional registry mirrors not managed by AIMA:'
        foreach ($mirror in $additional) {
            Write-Host "  $mirror"
        }
    }
}

function Wait-ExpectedMirrorsApplied {
    param([Parameter(Mandatory = $true)][string]$RecoveryHint)

    $stopwatch = [Diagnostics.Stopwatch]::StartNew()
    $lastProbe = $null
    while ($stopwatch.Elapsed.TotalSeconds -lt $MirrorVerificationTimeoutSeconds) {
        $remainingSeconds = [Math]::Max(
            1,
            [Math]::Ceiling($MirrorVerificationTimeoutSeconds - $stopwatch.Elapsed.TotalSeconds)
        )
        $probeTimeout = [Math]::Min($MirrorProbeTimeoutSeconds, [int]$remainingSeconds)
        $lastProbe = Get-DockerRegistryMirrorProbe -TimeoutSeconds $probeTimeout
        if ($lastProbe.Succeeded -and (Test-ExpectedMirrorsPresent -ActualMirrors $lastProbe.Mirrors)) {
            Write-EffectiveMirrorState -ActualMirrors $lastProbe.Mirrors
            return
        }

        $elapsedSeconds = [Math]::Min(
            $MirrorVerificationTimeoutSeconds,
            [Math]::Floor($stopwatch.Elapsed.TotalSeconds)
        )
        $state = if ($lastProbe.Succeeded) {
            "effective mirrors: $($lastProbe.Mirrors -join ', ')"
        }
        else {
            $lastProbe.Error
        }
        Write-Host "[WAIT] Docker registry mirrors not ready yet (${elapsedSeconds}s/${MirrorVerificationTimeoutSeconds}s): $state"

        $remainingAfterProbe = $MirrorVerificationTimeoutSeconds - $stopwatch.Elapsed.TotalSeconds
        if ($remainingAfterProbe -gt 0) {
            Start-Sleep -Seconds ([Math]::Min($MirrorVerificationIntervalSeconds, $remainingAfterProbe))
        }
    }

    $observed = if ($null -ne $lastProbe -and $lastProbe.Succeeded) {
        $lastProbe.Mirrors -join ', '
    }
    elseif ($null -ne $lastProbe) {
        "unavailable: $($lastProbe.Error)"
    }
    else {
        'unavailable: no probe completed'
    }
    throw "Docker Desktop did not report all AIMA registry mirrors within ${MirrorVerificationTimeoutSeconds}s. Last observed state: $observed.$RecoveryHint"
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

    $configPath = Get-DockerEngineConfigPath
    $configDirectory = Split-Path -Parent $configPath
    New-Item -ItemType Directory -Path $configDirectory -Force | Out-Null

    $configExisted = Test-Path -LiteralPath $configPath
    $daemon = Read-DockerEngineConfig -Path $configPath
    $daemonMatches = Test-AimaDaemonConfigMatches -Daemon $daemon
    $currentProbe = Get-DockerRegistryMirrorProbe
    $effectiveMatches = $currentProbe.Succeeded -and (
        Test-ExpectedMirrorsPresent -ActualMirrors $currentProbe.Mirrors
    )

    if ($daemonMatches -and $effectiveMatches) {
        Write-Host 'Docker Engine config and effective AIMA registry mirrors already match; restart skipped.'
        Write-EffectiveMirrorState -ActualMirrors $currentProbe.Mirrors
        Write-Host "Docker Hub mirror source: $MirrorConfigPath"
        Write-Host "Docker Engine config: $configPath"
        return
    }

    $backupPath = $null
    if (-not $daemonMatches) {
        Set-DaemonOption -Daemon $daemon -Name 'registry-mirrors' -Value $Mirrors
        Set-DaemonOption -Daemon $daemon -Name 'max-download-attempts' -Value $MaxDownloadAttempts

        if ($configExisted) {
            $backupPath = "$configPath.aima-backup-$(Get-Date -Format 'yyyyMMddHHmmss')"
            Copy-Item -LiteralPath $configPath -Destination $backupPath -Force
        }

        $utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
        $daemonJson = $daemon | ConvertTo-Json -Depth 20
        [IO.File]::WriteAllText($configPath, $daemonJson + [Environment]::NewLine, $utf8WithoutBom)
        Write-Host "Docker Engine config updated from AIMA mirror source: $MirrorConfigPath"
    }
    else {
        Write-Host 'Docker Engine config already matches AIMA, but the effective Docker Engine state does not; restart is required.'
    }

    $recoveryHint = if ($null -ne $backupPath) {
        " Restore backup if needed: $backupPath"
    }
    elseif (-not $configExisted) {
        " Remove the newly created file if needed: $configPath"
    }
    else {
        " Docker Engine config: $configPath"
    }

    Write-Host "Restarting Docker Desktop to apply AIMA Docker Hub mirrors (timeout: ${DockerDesktopRestartTimeoutSeconds}s) ..."
    & docker desktop restart --timeout $DockerDesktopRestartTimeoutSeconds
    if ($LASTEXITCODE -ne 0) {
        throw "docker desktop restart failed or exceeded ${DockerDesktopRestartTimeoutSeconds}s (exit code $LASTEXITCODE).$recoveryHint"
    }

    Write-Host "Verifying effective Docker registry mirrors (deadline: ${MirrorVerificationTimeoutSeconds}s) ..."
    Wait-ExpectedMirrorsApplied -RecoveryHint $recoveryHint

    Write-Host "Docker Hub mirror source: $MirrorConfigPath"
    Write-Host "Docker Engine config: $configPath"
    if ($null -ne $backupPath) {
        Write-Host "Previous Docker Engine config backup: $backupPath"
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    Configure-DockerDesktopMirrors
}
