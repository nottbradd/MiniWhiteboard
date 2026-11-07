param([Parameter(Mandatory=$true)][string]$Output)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted') { throw 'Disposable hosted VM only.' }
if ([string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) { throw 'Missing disposable temporary directory.' }
$destination=Join-Path $env:RUNNER_TEMP 'wsl.3.0.3.0.arm64.msi'
$outputDirectory=(Resolve-Path -LiteralPath $Output).Path
$expected='2937c7ce840bb35ec6e97f052189bdfff27f8c3463bfdd231df9a958212787a3'
$url='https://github.com/microsoft/WSL/releases/download/3.0.3/wsl.3.0.3.0.arm64.msi'
$record=@{scope='Normal Microsoft WSL MSI setup on an owned disposable VM; no distribution or reboot';url=$url;expected_sha256=$expected;started_utc=(Get-Date).ToUniversalTime().ToString('o');result='DOWNLOADING'}
function Save-Record { $record | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $outputDirectory 'official-msi.json') -Encoding utf8 }
Save-Record
try {
    Invoke-WebRequest -Uri $url -OutFile $destination -TimeoutSec 75
    $record.sha256=(Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
    $signature=Get-AuthenticodeSignature -LiteralPath $destination
    $record.signature=@{status=[string]$signature.Status;subject=$signature.SignerCertificate.Subject;thumbprint=$signature.SignerCertificate.Thumbprint}
    if ($record.sha256 -ne $expected -or $signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') { throw 'Official WSL installer identity/signature failed.' }
    $record.result='INSTALLING';Save-Record
    $log=Join-Path $outputDirectory 'official-msi.log'
    $arguments=@('/i',('"'+$destination+'"'),'/qn','/norestart','/L*v',('"'+$log+'"'))
    $process=Start-Process -FilePath (Join-Path $env:WINDIR 'System32\msiexec.exe') -ArgumentList $arguments -PassThru -WindowStyle Hidden
    if (-not $process.WaitForExit(120000)) { throw 'Normal WSL MSI exceeded its 120-second budget.' }
    $record.exit_code=$process.ExitCode
    if ($process.ExitCode -ne 0) { throw "Normal WSL MSI returned $($process.ExitCode); no reboot or further repair attempted." }
    $record.result='PASS for official MSI installation only'
} catch {
    $record.result='BLOCKED';$record.error=$_.Exception.Message;throw
} finally {
    $record.ended_utc=(Get-Date).ToUniversalTime().ToString('o');Save-Record
}
