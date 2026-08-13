Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Get-AimaRepositoryRoot {
    param([Parameter(Mandatory = $true)][string]$ScriptRoot)

    return (Split-Path -Parent $ScriptRoot)
}

function Get-AimaTargetVersions {
    param([Parameter(Mandatory = $true)][string]$RepoRoot)

    $packageJsonPath = Join-Path $RepoRoot 'frontend\package.json'
    $packageJson = Get-Content -LiteralPath $packageJsonPath -Raw | ConvertFrom-Json
    $npmVersion = [string]$packageJson.packageManager
    if ($npmVersion -match '^npm@(\d+\.\d+\.\d+)$') {
        $npmTarget = $Matches[1]
    }
    else {
        throw "Unable to parse npm target from $packageJsonPath"
    }

    return [pscustomobject]@{
        Python = (Get-Content -LiteralPath (Join-Path $RepoRoot '.python-version') -Raw).Trim()
        Node   = (Get-Content -LiteralPath (Join-Path $RepoRoot '.node-version') -Raw).Trim()
        Npm    = $npmTarget
        Uv     = (Get-Content -LiteralPath (Join-Path $RepoRoot '.uv-version') -Raw).Trim()
    }
}

function ConvertTo-AimaVersion {
    param([AllowNull()][string]$Text)

    if ([string]::IsNullOrWhiteSpace($Text)) {
        return $null
    }

    if ($Text -match '(\d+\.\d+\.\d+)') {
        return $Matches[1]
    }

    return $null
}

function Get-AimaCommandPath {
    param([Parameter(Mandatory = $true)][string]$Name)

    $command = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $command) {
        return $null
    }

    $source = [string]$command.Source
    if ($source -match '\\WindowsApps\\python(?:3)?\.exe$') {
        return $null
    }

    return $source
}

function Get-AimaCommandVersion {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $commandPath = Get-AimaCommandPath -Name $Name
    if ([string]::IsNullOrWhiteSpace($commandPath)) {
        return $null
    }

    try {
        $output = & $commandPath @Arguments 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) {
            return $null
        }
        return (ConvertTo-AimaVersion -Text $output)
    }
    catch {
        return $null
    }
}

function Get-AimaCurrentVersions {
    return [pscustomobject]@{
        Python = Get-AimaCommandVersion -Name 'python.exe' -Arguments @('--version')
        Node   = Get-AimaCommandVersion -Name 'node.exe' -Arguments @('--version')
        Npm    = Get-AimaCommandVersion -Name 'npm.cmd' -Arguments @('--version')
        Uv     = Get-AimaCommandVersion -Name 'uv.exe' -Arguments @('--version')
    }
}

function Get-AimaPythonInstallerUri {
    param([Parameter(Mandatory = $true)][string]$Version)

    return "https://www.python.org/ftp/python/$Version/python-$Version-amd64.exe"
}

function Get-AimaNodeInstallerUri {
    param([Parameter(Mandatory = $true)][string]$Version)

    return "https://nodejs.org/dist/v$Version/node-v$Version-x64.msi"
}

function Get-AimaNodeChecksumUri {
    param([Parameter(Mandatory = $true)][string]$Version)

    return "https://nodejs.org/dist/v$Version/SHASUMS256.txt"
}

function Get-AimaUvInstallerUri {
    param([Parameter(Mandatory = $true)][string]$Version)

    return "https://astral.sh/uv/$Version/install.ps1"
}

function Enable-AimaTls12 {
    [Net.ServicePointManager]::SecurityProtocol =
        [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
}

function Refresh-AimaProcessPath {
    $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $segments = @()

    if (-not [string]::IsNullOrWhiteSpace($machinePath)) {
        $segments += $machinePath
    }
    if (-not [string]::IsNullOrWhiteSpace($userPath)) {
        $segments += $userPath
    }

    $env:Path = ($segments -join ';')
}

function Invoke-AimaDownload {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    Enable-AimaTls12
    Write-Host "Downloading: $Uri"
    Invoke-WebRequest -Uri $Uri -OutFile $Destination -UseBasicParsing
}

function Get-AimaRegisteredPrograms {
    $registryPaths = @(
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )
    $seen = @{}
    $programs = @()

    foreach ($registryPath in $registryPaths) {
        $items = Get-ItemProperty -Path $registryPath -ErrorAction SilentlyContinue
        foreach ($item in $items) {
            if ([string]::IsNullOrWhiteSpace([string]$item.DisplayName)) {
                continue
            }

            $key = "{0}|{1}|{2}" -f $item.DisplayName, $item.DisplayVersion, $item.PSChildName
            if ($seen.ContainsKey($key)) {
                continue
            }
            $seen[$key] = $true
            $programs += $item
        }
    }

    return $programs
}

function Get-AimaPythonRegistrations {
    param([Parameter(Mandatory = $true)][string]$TargetVersion)

    return @(Get-AimaRegisteredPrograms | Where-Object {
        $_.DisplayName -match '^Python \d+\.\d+\.\d+(?: \((?:32|64)-bit\))?$' -and
        [string]$_.DisplayVersion -ne $TargetVersion
    })
}

function Get-AimaNodeRegistrations {
    param([Parameter(Mandatory = $true)][string]$TargetVersion)

    return @(Get-AimaRegisteredPrograms | Where-Object {
        $_.DisplayName -eq 'Node.js' -and [string]$_.DisplayVersion -ne $TargetVersion
    })
}

function Confirm-AimaUninstall {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][object[]]$Programs
    )

    if ($Programs.Count -eq 0) {
        return $false
    }

    Write-Host ''
    Write-Host "Detected registered $Label installation(s) that do not match the repository target:"
    foreach ($program in $Programs) {
        Write-Host ("  - {0} {1}" -f $program.DisplayName, $program.DisplayVersion)
    }
    Write-Host 'Keeping older versions can be useful for other projects. Default: keep them.'
    $answer = Read-Host "Uninstall these old $Label installation(s) first? [y/N]"
    return ($answer -match '^(?i:y|yes)$')
}

function Invoke-AimaRegisteredUninstall {
    param([Parameter(Mandatory = $true)][object]$Program)

    Write-Host ("Opening uninstaller: {0} {1}" -f $Program.DisplayName, $Program.DisplayVersion)
    $process = $null
    $productCode = [string]$Program.PSChildName
    $uninstallString = [string]$Program.UninstallString

    if ($productCode -match '^\{[0-9A-Fa-f-]+\}$' -and $uninstallString -match '(?i)msiexec') {
        $process = Start-Process -FilePath 'msiexec.exe' -ArgumentList @('/x', $productCode) -Wait -PassThru
    }
    elseif (-not [string]::IsNullOrWhiteSpace($uninstallString)) {
        $process = Start-Process -FilePath 'cmd.exe' -ArgumentList @('/d', '/s', '/c', $uninstallString) -Wait -PassThru
    }
    else {
        Write-Warning ("No safe registered uninstaller was found for {0}; leaving it installed." -f $Program.DisplayName)
        return
    }

    if ($process.ExitCode -notin @(0, 1641, 3010)) {
        if ($process.ExitCode -eq 1602) {
            throw "Uninstall was cancelled by the user: $($Program.DisplayName)"
        }
        throw "Uninstall failed with exit code $($process.ExitCode): $($Program.DisplayName)"
    }
}

function Install-AimaPython {
    param(
        [Parameter(Mandatory = $true)][string]$TargetVersion,
        [Parameter(Mandatory = $true)][string]$TempDir
    )

    $registrations = Get-AimaPythonRegistrations -TargetVersion $TargetVersion
    if (Confirm-AimaUninstall -Label 'Python' -Programs $registrations) {
        foreach ($program in $registrations) {
            Invoke-AimaRegisteredUninstall -Program $program
        }
        Refresh-AimaProcessPath
    }

    $installerName = "python-$TargetVersion-amd64.exe"
    $installerPath = Join-Path $TempDir $installerName
    Invoke-AimaDownload -Uri (Get-AimaPythonInstallerUri -Version $TargetVersion) -Destination $installerPath

    $signature = Get-AuthenticodeSignature -FilePath $installerPath
    if ($signature.Status -ne 'Valid') {
        throw "Python installer Authenticode verification failed: $($signature.Status)"
    }

    Write-Host ''
    Write-Host "Opening the official Python $TargetVersion installer."
    Write-Host 'The installer UI remains visible. Complete the installation to continue.'
    $arguments = @(
        'InstallAllUsers=0',
        'PrependPath=1',
        'Include_test=0',
        'InstallLauncherAllUsers=0'
    )
    $process = Start-Process -FilePath $installerPath -ArgumentList $arguments -Wait -PassThru
    if ($process.ExitCode -notin @(0, 1641, 3010)) {
        throw "Python installer exited with code $($process.ExitCode)"
    }

    Refresh-AimaProcessPath
}

function Install-AimaNode {
    param(
        [Parameter(Mandatory = $true)][string]$TargetVersion,
        [Parameter(Mandatory = $true)][string]$TempDir
    )

    $registrations = Get-AimaNodeRegistrations -TargetVersion $TargetVersion
    if ($registrations.Count -gt 0) {
        Write-Host ''
        Write-Host 'Node.js usually uses one standard installation location on Windows.'
        Write-Host 'Choosing to keep the old version means this script will not uninstall it first; the official MSI may still perform an in-place product upgrade.'
    }
    if (Confirm-AimaUninstall -Label 'Node.js' -Programs $registrations) {
        foreach ($program in $registrations) {
            Invoke-AimaRegisteredUninstall -Program $program
        }
        Refresh-AimaProcessPath
    }

    $installerName = "node-v$TargetVersion-x64.msi"
    $installerPath = Join-Path $TempDir $installerName
    $checksumUri = Get-AimaNodeChecksumUri -Version $TargetVersion
    Enable-AimaTls12
    $checksums = (Invoke-WebRequest -Uri $checksumUri -UseBasicParsing).Content
    $pattern = '(?m)^([0-9A-Fa-f]{64})\s+' + [regex]::Escape($installerName) + '\s*$'
    if ($checksums -notmatch $pattern) {
        throw "Unable to find $installerName in official Node.js SHASUMS256.txt"
    }
    $expectedHash = $Matches[1].ToLowerInvariant()

    Invoke-AimaDownload -Uri (Get-AimaNodeInstallerUri -Version $TargetVersion) -Destination $installerPath
    $actualHash = (Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $expectedHash) {
        throw "Node.js MSI SHA-256 mismatch. Expected $expectedHash, got $actualHash"
    }

    Write-Host ''
    Write-Host "Opening the official Node.js $TargetVersion MSI installer."
    $process = Start-Process -FilePath 'msiexec.exe' -ArgumentList @('/i', ('"{0}"' -f $installerPath)) -Wait -PassThru
    if ($process.ExitCode -notin @(0, 1641, 3010)) {
        if ($process.ExitCode -eq 1602) {
            throw 'Node.js installation was cancelled by the user.'
        }
        throw "Node.js installer exited with code $($process.ExitCode)"
    }

    Refresh-AimaProcessPath
}

function Update-AimaNpm {
    param([Parameter(Mandatory = $true)][string]$TargetVersion)

    $npmPath = Get-AimaCommandPath -Name 'npm.cmd'
    if ([string]::IsNullOrWhiteSpace($npmPath)) {
        throw 'npm.cmd is not available after Node.js installation.'
    }

    Write-Host "Updating npm to $TargetVersion ..."
    & $npmPath install --global "npm@$TargetVersion"
    if ($LASTEXITCODE -ne 0) {
        throw "npm upgrade failed with exit code $LASTEXITCODE. If Windows reports permission denied, rerun the setup entry as Administrator."
    }
    Refresh-AimaProcessPath
}

function Remove-AimaStandaloneUvIfRequested {
    $uvPath = Get-AimaCommandPath -Name 'uv.exe'
    if ([string]::IsNullOrWhiteSpace($uvPath)) {
        return
    }

    $answer = Read-Host 'Remove the currently resolved uv executable before installing the repository version? [y/N]'
    if ($answer -notmatch '^(?i:y|yes)$') {
        return
    }

    $standardDir = [IO.Path]::GetFullPath((Join-Path $HOME '.local\bin')).TrimEnd('\')
    $resolvedDir = [IO.Path]::GetFullPath((Split-Path -Parent $uvPath)).TrimEnd('\')
    if (-not $resolvedDir.Equals($standardDir, [StringComparison]::OrdinalIgnoreCase)) {
        Write-Warning "uv is resolved from $resolvedDir, which may be owned by another package manager. It will not be deleted automatically."
        return
    }

    foreach ($name in @('uv.exe', 'uvx.exe', 'uvw.exe')) {
        $path = Join-Path $resolvedDir $name
        if (Test-Path -LiteralPath $path) {
            Remove-Item -LiteralPath $path -Force
        }
    }
}

function Install-AimaUv {
    param(
        [Parameter(Mandatory = $true)][string]$TargetVersion,
        [Parameter(Mandatory = $true)][string]$TempDir,
        [AllowNull()][string]$CurrentVersion
    )

    if (-not [string]::IsNullOrWhiteSpace($CurrentVersion)) {
        Write-Host "Current uv version: $CurrentVersion; target: $TargetVersion"
        Remove-AimaStandaloneUvIfRequested
    }

    $installerPath = Join-Path $TempDir "uv-$TargetVersion-install.ps1"
    Invoke-AimaDownload -Uri (Get-AimaUvInstallerUri -Version $TargetVersion) -Destination $installerPath

    Write-Host "Running the official Astral uv $TargetVersion installer ..."
    $process = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
        '-NoLogo',
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-File',
        ('"{0}"' -f $installerPath)
    ) -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "uv installer exited with code $($process.ExitCode)"
    }

    Refresh-AimaProcessPath
}

function Assert-AimaToolVersion {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [AllowNull()][string]$Actual,
        [Parameter(Mandatory = $true)][string]$Expected
    )

    if ($Actual -ne $Expected) {
        throw "$Label version mismatch after setup. Expected $Expected, got $Actual. Open a new terminal and rerun the setup; if an older runtime still wins PATH resolution, keep it only after fixing PATH precedence."
    }
}

function Install-AimaProjectDependencies {
    param([Parameter(Mandatory = $true)][string]$RepoRoot)

    $uvPath = Get-AimaCommandPath -Name 'uv.exe'
    $npmPath = Get-AimaCommandPath -Name 'npm.cmd'
    if ([string]::IsNullOrWhiteSpace($uvPath) -or [string]::IsNullOrWhiteSpace($npmPath)) {
        throw 'uv or npm is unavailable; project dependencies cannot be installed.'
    }

    Push-Location $RepoRoot
    try {
        Write-Host 'Checking Python lock ...'
        & $uvPath lock --check
        if ($LASTEXITCODE -ne 0) {
            throw "uv lock --check failed with exit code $LASTEXITCODE"
        }

        Write-Host 'Installing locked Python dependencies ...'
        & $uvPath sync --locked
        if ($LASTEXITCODE -ne 0) {
            throw "uv sync --locked failed with exit code $LASTEXITCODE"
        }

        Write-Host 'Installing locked frontend dependencies ...'
        & $npmPath ci --prefix frontend
        if ($LASTEXITCODE -ne 0) {
            throw "npm ci --prefix frontend failed with exit code $LASTEXITCODE"
        }

        & $uvPath run python -c 'import aima_ugc; print(aima_ugc.__version__)'
        if ($LASTEXITCODE -ne 0) {
            throw "Python package import verification failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}

function Write-AimaVersionSummary {
    param(
        [Parameter(Mandatory = $true)]$Current,
        [Parameter(Mandatory = $true)]$Target
    )

    Write-Host ''
    Write-Host 'Toolchain status:'
    Write-Host ("  Python  current={0} target={1}" -f $(if ($Current.Python) { $Current.Python } else { '<missing>' }), $Target.Python)
    Write-Host ("  Node    current={0} target={1}" -f $(if ($Current.Node) { $Current.Node } else { '<missing>' }), $Target.Node)
    Write-Host ("  npm     current={0} target={1}" -f $(if ($Current.Npm) { $Current.Npm } else { '<missing>' }), $Target.Npm)
    Write-Host ("  uv      current={0} target={1}" -f $(if ($Current.Uv) { $Current.Uv } else { '<missing>' }), $Target.Uv)
}

function Invoke-AimaDevEnvironmentSetup {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw 'This one-click bootstrap currently supports Windows only. Use docs/Environment instructions for Linux/macOS.'
    }
    if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -ne 'AMD64') {
        throw 'This one-click bootstrap currently supports Windows x64 only.'
    }

    $repoRoot = Get-AimaRepositoryRoot -ScriptRoot $PSScriptRoot
    $target = Get-AimaTargetVersions -RepoRoot $repoRoot
    $tempDir = Join-Path ([IO.Path]::GetTempPath()) ("AIMA_UGC-dev-setup-" + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

    try {
        Refresh-AimaProcessPath
        $current = Get-AimaCurrentVersions
        Write-AimaVersionSummary -Current $current -Target $target

        if ($current.Python -ne $target.Python) {
            Install-AimaPython -TargetVersion $target.Python -TempDir $tempDir
            $current = Get-AimaCurrentVersions
            Assert-AimaToolVersion -Label 'Python' -Actual $current.Python -Expected $target.Python
        }

        if ($current.Node -ne $target.Node) {
            Install-AimaNode -TargetVersion $target.Node -TempDir $tempDir
            $current = Get-AimaCurrentVersions
            Assert-AimaToolVersion -Label 'Node.js' -Actual $current.Node -Expected $target.Node
        }

        if ($current.Npm -ne $target.Npm) {
            Update-AimaNpm -TargetVersion $target.Npm
            $current = Get-AimaCurrentVersions
            Assert-AimaToolVersion -Label 'npm' -Actual $current.Npm -Expected $target.Npm
        }

        if ($current.Uv -ne $target.Uv) {
            Install-AimaUv -TargetVersion $target.Uv -TempDir $tempDir -CurrentVersion $current.Uv
            $current = Get-AimaCurrentVersions
            Assert-AimaToolVersion -Label 'uv' -Actual $current.Uv -Expected $target.Uv
        }

        Write-AimaVersionSummary -Current $current -Target $target
        Install-AimaProjectDependencies -RepoRoot $repoRoot

        Write-Host ''
        Write-Host 'AIMA_UGC development environment is ready.'
        Write-Host 'Start backend:'
        Write-Host '  uv run uvicorn aima_ugc.entrypoints.api_main:app --host 127.0.0.1 --port 8090 --reload --reload-dir backend/src'
        Write-Host 'Start frontend in another terminal:'
        Write-Host '  npm --prefix frontend run dev'
    }
    finally {
        if (Test-Path -LiteralPath $tempDir) {
            Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    try {
        Invoke-AimaDevEnvironmentSetup
        exit 0
    }
    catch {
        Write-Host ''
        Write-Error $_
        exit 1
    }
}
