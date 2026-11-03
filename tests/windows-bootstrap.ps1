# Optional Windows verification: download into an isolated temporary runtime,
# verify reuse, then run the application's API tests with that runtime.
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$project = Split-Path $PSScriptRoot -Parent
$runtime = Join-Path $env:TEMP 'hehu-bootstrap-test-python'
$tokens = $null
$parseErrors = $null
[System.Management.Automation.Language.Parser]::ParseFile((Join-Path $project 'bootstrap-windows.ps1'), [ref]$tokens, [ref]$parseErrors) | Out-Null
if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
& (Join-Path $project 'bootstrap-windows.ps1') -InstallOnly -ForceManagedInstall -RuntimeDirectory $runtime
if ($LASTEXITCODE -ne 0) { throw 'Bootstrap failed' }
& (Join-Path $project 'bootstrap-windows.ps1') -InstallOnly -ForceManagedInstall -RuntimeDirectory $runtime
if ($LASTEXITCODE -ne 0) { throw 'Runtime reuse failed' }
Set-Location $project
& (Join-Path $runtime 'python.exe') -m ensurepip
& (Join-Path $runtime 'python.exe') -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& (Join-Path $runtime 'python.exe') -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Application tests failed' }
Write-Host "Windows checks passed. Test runtime retained at: $runtime"
