# PostgreSQL's official Windows binaries require the Microsoft VC++ runtime.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try {
    $system = [Environment]::GetFolderPath('System')
    if ((Test-Path (Join-Path $system 'msvcp140.dll')) -and (Test-Path (Join-Path $system 'vcruntime140.dll'))) { exit 0 }
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    $installer = Join-Path ([IO.Path]::GetTempPath()) ('hehu-vcredist-' + [guid]::NewGuid().ToString('N') + '.exe')
    try {
        Write-Host 'Installing Microsoft Visual C++ runtime. Windows may request administrator approval.'
        Invoke-WebRequest -UseBasicParsing -Uri 'https://aka.ms/vs/17/release/vc_redist.x64.exe' -OutFile $installer -TimeoutSec 300
        $signature = Get-AuthenticodeSignature -FilePath $installer
        if ($signature.Status -ne 'Valid' -or -not $signature.SignerCertificate -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') {
            throw 'Microsoft runtime signature check failed.'
        }
        $process = Start-Process -FilePath $installer -ArgumentList '/install /quiet /norestart' -Verb RunAs -Wait -PassThru
        if ($process.ExitCode -notin @(0, 1638, 3010)) { throw "Microsoft runtime installer exited with $($process.ExitCode)." }
        if ($process.ExitCode -eq 3010) { Write-Host 'The runtime installer requested a Windows restart if startup fails.' }
    } finally {
        Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue
    }
    exit 0
} catch {
    Write-Host ('Microsoft runtime setup failed: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
