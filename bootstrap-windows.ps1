# Windows PowerShell 5.1+. Installs an official, signed Python runtime when needed.
[CmdletBinding()]
param(
    [switch]$InstallOnly,
    [switch]$ForceManagedInstall,
    [string]$RuntimeDirectory = (Join-Path $env:LOCALAPPDATA 'Hehu\Python313')
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$projectRoot = $PSScriptRoot
$env:PYTHONUTF8 = '1'

function Test-Python {
    param([string]$Executable, [string[]]$PrefixArgs = @())
    if (-not $Executable) { return $null }
    # Do not invoke Microsoft Store execution aliases.
    if ($Executable -like '*\Microsoft\WindowsApps\*') { return $null }
    try {
        $result = & $Executable @PrefixArgs -c 'import sys,sqlite3; assert sys.version_info >= (3,9); print("HEHU_PYTHON="+sys.executable)' 2>$null
        if ($LASTEXITCODE -ne 0) { return $null }
        foreach ($line in @($result)) {
            if ("$line".StartsWith('HEHU_PYTHON=')) { return "$line".Substring(12) }
        }
    } catch { return $null }
    return $null
}

function Find-Python {
    if ($env:PYTHON_EXE) {
        $found = Test-Python $env:PYTHON_EXE
        if ($found) { return $found }
        throw 'PYTHON_EXE is set but does not point to Python 3.9+ with sqlite3. Correct or clear it and retry.'
    }
    $found = Test-Python (Join-Path $RuntimeDirectory 'python.exe')
    if ($found) { return $found }
    foreach ($name in @('py.exe', 'python.exe', 'python3.exe')) {
        $cmd = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($cmd) {
            $prefix = @()
            if ($name -eq 'py.exe') { $prefix = @('-3') }
            $found = Test-Python -Executable $cmd.Source -PrefixArgs $prefix
            if ($found) { return $found }
        }
    }
    foreach ($key in @('HKCU:\Software\Python\PythonCore\*\InstallPath', 'HKLM:\Software\Python\PythonCore\*\InstallPath', 'HKLM:\Software\WOW6432Node\Python\PythonCore\*\InstallPath')) {
        foreach ($item in @(Get-ItemProperty -Path $key -ErrorAction SilentlyContinue)) {
            $candidate = $item.ExecutablePath
            if (-not $candidate -and $item.'(default)') { $candidate = Join-Path $item.'(default)' 'python.exe' }
            $found = Test-Python $candidate
            if ($found) { return $found }
        }
    }
    return $null
}

function Install-ManagedPython {
    $existing = Test-Python (Join-Path $RuntimeDirectory 'python.exe')
    if ($existing) { return $existing }
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    Write-Host 'Python is missing. Downloading the latest stable Python 3.13 installer from python.org...'
    $listing = Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/' -TimeoutSec 60
    $versions = [regex]::Matches($listing.Content, 'href="(3\.13\.\d+)/"') | ForEach-Object { [version]$_.Groups[1].Value } | Sort-Object -Descending -Unique
    if (-not $versions) { throw 'Could not discover a stable Python 3.13 release on python.org.' }
    $version = $versions[0].ToString()
    $arch = $env:PROCESSOR_ARCHITEW6432
    if (-not $arch) { $arch = $env:PROCESSOR_ARCHITECTURE }
    switch ($arch.ToUpperInvariant()) {
        'ARM64' { $suffix = '-arm64.exe' }
        'AMD64' { $suffix = '-amd64.exe' }
        'X86' { $suffix = '.exe' }
        default { throw "Unsupported Windows architecture: $arch" }
    }
    $url = "https://www.python.org/ftp/python/$version/python-$version$suffix"
    $installer = Join-Path ([IO.Path]::GetTempPath()) ('hehu-python-' + [guid]::NewGuid().ToString('N') + '.exe')
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $installer -TimeoutSec 300
        $signature = Get-AuthenticodeSignature -FilePath $installer
        if ($signature.Status -ne 'Valid' -or -not $signature.SignerCertificate -or $signature.SignerCertificate.Subject -notmatch 'Python Software Foundation') {
            throw 'Python installer signature validation failed. The installer will not be executed.'
        }
        if ($RuntimeDirectory.Contains('"')) { throw 'Invalid runtime directory.' }
        $target = [IO.Path]::GetFullPath($RuntimeDirectory)
        Write-Host "Installing Python $version for the current user: $target"
        $arguments = '/quiet InstallAllUsers=0 Include_launcher=0 Include_test=0 Include_doc=0 Include_pip=0 PrependPath=0 AssociateFiles=0 Shortcuts=0 TargetDir="' + $target + '"'
        $process = Start-Process -FilePath $installer -ArgumentList $arguments -Wait -PassThru
        if ($process.ExitCode -notin @(0, 3010)) { throw "Python installer failed with exit code $($process.ExitCode)." }
        $python = Test-Python (Join-Path $target 'python.exe')
        if (-not $python) { throw 'Python installation completed but the runtime check failed. Restart Windows if the installer requested it, then retry.' }
        return $python
    } finally {
        Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue
    }
}

try {
    if ($ForceManagedInstall) { $python = Install-ManagedPython }
    else {
        $python = Find-Python
        if (-not $python) { $python = Install-ManagedPython }
    }
    Write-Host "Python ready: $python"
    if ($InstallOnly) { exit 0 }
    Set-Location -LiteralPath $projectRoot
    if (-not $env:HOST) { $env:HOST = '127.0.0.1' }
    if (-not $env:PORT) { $env:PORT = '8765' }
    Write-Host "Starting Hehu on $($env:HOST):$($env:PORT). Keep this window open."
    & $python (Join-Path $projectRoot 'server.py')
    exit $LASTEXITCODE
} catch {
    Write-Host ('Startup failed: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'Check Internet access to python.org and your user-directory permissions, then run start-windows.cmd again.'
    exit 1
}
