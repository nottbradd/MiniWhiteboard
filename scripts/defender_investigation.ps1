# Investigation of fixed, already-public bytes. This is not release acceptance.
# Never run on a developer's desktop or a self-hosted runner.
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted') {
    throw 'This script requires a disposable GitHub-hosted Windows runner.'
}
$evidenceRoot = Join-Path $env:GITHUB_WORKSPACE 'verification/defender-investigation'
New-Item -ItemType Directory -Path $evidenceRoot -ErrorAction Stop | Out-Null
$started = Get-Date
$report = [ordered]@{
    started_utc = $started.ToUniversalTime().ToString('o')
    source_revision = $env:GITHUB_SHA
    runner_image = $env:ImageVersion
    purpose = 'Original published-file investigation; no release acceptance claim'
    download_method = 'Invoke-WebRequest, not a browser; no origin marker added or removed'
    extraction_method = 'Expand-Archive, not Explorer'
    runtime = 'NOT RUN by this scan-only investigation'
    snapshots = @()
    files = @()
    scans = @()
    result = 'BLOCKED'
}

function Save-Json($Value, [string]$Name) {
    $Value | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $evidenceRoot $Name) -Encoding utf8
}

function Snapshot([string]$Stage) {
    $status = Get-MpComputerStatus
    $preferences = Get-MpPreference
    $snapshot = [ordered]@{
        stage = $Stage
        utc = (Get-Date).ToUniversalTime().ToString('o')
        os = Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,OSArchitecture
        status = $status | Select-Object AMRunningMode,AMServiceEnabled,AntivirusEnabled,AntispywareEnabled,
            RealTimeProtectionEnabled,BehaviorMonitorEnabled,IoavProtectionEnabled,OnAccessProtectionEnabled,
            IsTamperProtected,AMProductVersion,AMEngineVersion,AntivirusSignatureVersion,AntivirusSignatureLastUpdated,
            NISEnabled,NISEngineVersion,NISSignatureVersion,SmartAppControlState
        preferences = $preferences | Select-Object DisableRealtimeMonitoring,DisableBehaviorMonitoring,
            DisableIOAVProtection,DisableArchiveScanning,DisableScriptScanning,DisableBlockAtFirstSeen,
            DisableAutoExclusions,MAPSReporting,SubmitSamplesConsent,CloudBlockLevel,CloudExtendedTimeout,
            PUAProtection,EnableNetworkProtection,EnableControlledFolderAccess,ExclusionPath,ExclusionProcess,
            ExclusionExtension,ExclusionIpAddress,AttackSurfaceReductionOnlyExclusions,
            AttackSurfaceReductionRules_Ids,AttackSurfaceReductionRules_Actions
    }
    $report.snapshots += $snapshot
    Save-Json $report 'report.json'
    return $snapshot
}

function Require-Protection($Snapshot) {
    $s = $Snapshot.status
    $p = $Snapshot.preferences
    foreach ($name in @('AMServiceEnabled','AntivirusEnabled','RealTimeProtectionEnabled',
            'BehaviorMonitorEnabled','IoavProtectionEnabled','OnAccessProtectionEnabled')) {
        if ($s.$name -ne $true) { throw "Defender protection unavailable: $name" }
    }
    if ($s.AMRunningMode -ne 'Normal') { throw "Defender is not active: $($s.AMRunningMode)" }
    foreach ($name in @('DisableRealtimeMonitoring','DisableBehaviorMonitoring','DisableIOAVProtection',
            'DisableArchiveScanning','DisableScriptScanning','DisableBlockAtFirstSeen')) {
        if ($p.$name -ne $false) { throw "Defender protection disabled: $name" }
    }
    foreach ($name in @('ExclusionPath','ExclusionProcess','ExclusionExtension','AttackSurfaceReductionOnlyExclusions')) {
        if (@($p.$name | Where-Object { $_ }).Count) { throw "Unresolved Defender exclusions: $name" }
    }
    if (-not $p.DisableAutoExclusions -or $p.MAPSReporting -eq 0 -or $p.SubmitSamplesConsent -eq 2) {
        throw 'Automatic exclusions or cloud protection would invalidate this investigation.'
    }
    if (((Get-Date) - $s.AntivirusSignatureLastUpdated).TotalHours -gt 48) {
        throw 'Security intelligence is older than 48 hours.'
    }
}

function Record-File([string]$Path, [string]$Stage) {
    $exists = Test-Path -LiteralPath $Path -PathType Leaf
    $file = [ordered]@{ stage=$Stage; name=(Split-Path -Leaf $Path); exists=$exists }
    if ($exists) {
        $file.bytes = (Get-Item -LiteralPath $Path).Length
        $file.sha256 = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
        $file.zone_identifier = @(Get-Content -LiteralPath $Path -Stream Zone.Identifier -ErrorAction SilentlyContinue)
    }
    $report.files += $file
    return $file
}

function Scan([string]$Path, [string]$Label) {
    Require-Protection (Snapshot "before-$Label")
    $scanStart = Get-Date
    & $script:scanner -Scan -ScanType 3 -File $Path 2>&1 |
        Out-File -LiteralPath (Join-Path $evidenceRoot "$Label-scan.txt") -Encoding utf8
    $report.scans += @{ label=$Label; exit_code=$LASTEXITCODE;
        started_utc=$scanStart.ToUniversalTime().ToString('o');
        ended_utc=(Get-Date).ToUniversalTime().ToString('o') }
    Require-Protection (Snapshot "after-$Label")
}

try {
    $null = Snapshot 'runner-defaults'
    # Runner images disable Defender and exclude entire drives. Strengthen only
    # this disposable VM before downloading samples; never bypass a detection.
    $preferences = Get-MpPreference
    foreach ($name in @('ExclusionPath','ExclusionProcess','ExclusionExtension','AttackSurfaceReductionOnlyExclusions')) {
        $values = @($preferences.$name | Where-Object { $_ })
        if ($values.Count) {
            $arguments = @{}; $arguments[$name] = $values
            Remove-MpPreference @arguments
        }
    }
    $passivePolicy = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows Advanced Threat Protection'
    if (Test-Path -LiteralPath $passivePolicy) {
        $passive = Get-ItemPropertyValue -LiteralPath $passivePolicy -Name ForceDefenderPassiveMode -ErrorAction SilentlyContinue
        if ($passive -eq 1) {
            Set-ItemProperty -LiteralPath $passivePolicy -Name ForceDefenderPassiveMode -Value 0
        }
    }
    Set-MpPreference -DisableRealtimeMonitoring $false -DisableBehaviorMonitoring $false `
        -DisableIOAVProtection $false -DisableArchiveScanning $false -DisableScriptScanning $false `
        -DisableBlockAtFirstSeen $false -DisableAutoExclusions $true -MAPSReporting Advanced `
        -SubmitSamplesConsent SendSafeSamples -PUAProtection Enabled
    Update-MpSignature -UpdateSource MicrosoftUpdateServer
    Require-Protection (Snapshot 'enabled-updated')
    $script:scanner = (Get-ChildItem -Path "$env:ProgramData\Microsoft\Windows Defender\Platform\*\MpCmdRun.exe" |
        Sort-Object FullName -Descending | Select-Object -First 1).FullName
    if (-not $script:scanner) { $script:scanner = "$env:ProgramFiles\Windows Defender\MpCmdRun.exe" }
    & $script:scanner -ValidateMapsConnection 2>&1 | Out-File (Join-Path $evidenceRoot 'cloud-connection.txt')
    $report.cloud_connection_exit_code = $LASTEXITCODE
    if ($LASTEXITCODE -ne 0) { throw 'Defender cloud connectivity check failed.' }

    $downloadRoot = Join-Path $env:USERPROFILE 'Downloads\MiniWhiteboard-investigation'
    New-Item -ItemType Directory -Path $downloadRoot -ErrorAction Stop | Out-Null
    $assets = @(
        @{name='MiniWhiteboard-1.3.4-HotkeyPatch-Setup.exe';bytes=27476405;
            sha256='29770151f8df811e1f8890a93aaa201f2e666e05bb1310dcf086bbd7b73a460b'},
        @{name='WinMiniWhiteboardV1.3.4-HotkeyPatch.zip';bytes=38075984;
            sha256='5fa64240a14d49c5ec2cb1d2fd5ad2f370365474a3c5a165c9806516ac37dc89'}
    )
    foreach ($asset in $assets) {
        $asset.url = 'https://github.com/nottbradd/MiniWhiteboard/releases/download/v1.3.4/' + $asset.name
        $path = Join-Path $downloadRoot $asset.name
        Invoke-WebRequest -Uri $asset.url -OutFile $path
        $file = Record-File $path 'downloaded'
        if ($file.sha256 -ne $asset.sha256 -or $file.bytes -ne $asset.bytes) { throw 'Published download identity mismatch.' }
        Scan $path $asset.name
        $file = Record-File $path 'after-scan'
        if ($file.sha256 -ne $asset.sha256) { throw 'Download is missing or changed after scan.' }
    }
    $report.assets = $assets
    $extracted = Join-Path $downloadRoot 'portable'
    Expand-Archive -LiteralPath (Join-Path $downloadRoot $assets[1].name) -DestinationPath $extracted
    $exe = Join-Path $extracted 'Mini Whiteboard\Mini Whiteboard.exe'
    $file = Record-File $exe 'after-extraction'
    if ($file.sha256 -ne 'a539339e2ee83c54be86e3e67115c5d1f0bcbca12605bb875ba241f5b79e2716') {
        throw 'Extracted executable missing or different.'
    }
    Scan $extracted 'portable-extracted'
    $file = Record-File $exe 'after-extracted-scan'
    if ($file.sha256 -ne 'a539339e2ee83c54be86e3e67115c5d1f0bcbca12605bb875ba241f5b79e2716') {
        throw 'Extracted executable missing or changed after scan.'
    }
    $inventory = @(Get-ChildItem -LiteralPath $extracted -Recurse -File | ForEach-Object {
        @{path=$_.FullName.Substring($extracted.Length+1);bytes=$_.Length;
          sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
    })
    Save-Json $inventory 'extracted-files.json'
    $report.result = 'SCANS COMPLETED; runtime and browser-download acceptance NOT RUN'
} catch {
    $report.error = $_.Exception.Message
    Write-Warning $report.error
} finally {
    try { $null = Snapshot 'end' } catch { $report.final_snapshot_error = $_.Exception.Message }
    try {
        Save-Json @(Get-MpThreat) 'threats.json'
        Save-Json @(Get-MpThreatDetection) 'detections.json'
    } catch { $report.threat_history_error = $_.Exception.Message }
    try {
        $events = @(Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Windows Defender/Operational';StartTime=$started} -ErrorAction SilentlyContinue)
        Save-Json @($events | ForEach-Object {
            @{utc=$_.TimeCreated.ToUniversalTime().ToString('o');id=$_.Id;level=$_.LevelDisplayName;
                message=$_.Message;xml=$_.ToXml()}
        }) 'defender-events.json'
        $report.detection_event_count = @($events | Where-Object Id -In 1006,1007,1008,1015,1116,1117,1118,1119,1121).Count
        if ($report.detection_event_count) { $report.result = 'DETECTION OR BLOCK OBSERVED; inspect events' }
    } catch { $report.event_log_error = $_.Exception.Message }
    $report.ended_utc = (Get-Date).ToUniversalTime().ToString('o')
    Save-Json $report 'report.json'
    Write-Output $report.result
}
if ($report.result -notlike 'SCANS COMPLETED*') { exit 1 }
