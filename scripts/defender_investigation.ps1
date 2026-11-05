# Investigate fixed public bytes only in disposable hosted Windows VMs.
param([switch]$Exercise, [ValidateSet('all','installer','portable')][string]$Package = 'all')
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted') {
    throw 'This script requires a disposable GitHub-hosted Windows runner.'
}
$evidenceRoot = Join-Path $env:GITHUB_WORKSPACE 'verification/defender-investigation'
New-Item -ItemType Directory -Path $evidenceRoot -ErrorAction Stop | Out-Null
$operationsRoot = Join-Path $evidenceRoot 'operations'
New-Item -ItemType Directory -Path $operationsRoot | Out-Null
$started = Get-Date
$workDeadline = $started.AddMinutes(18)
$collecting = $false
$operationNumber = 0
$report = [ordered]@{
    started_utc=$started.ToUniversalTime().ToString('o'); source_revision=$env:GITHUB_SHA
    runner_image=$env:ImageVersion; purpose='Original published-file investigation; no release acceptance claim'
    download_method='Invoke-WebRequest, not a browser; no origin marker added or removed'
    extraction_method='Expand-Archive, not Explorer'; runtime='NOT RUN'; package=$Package
    operation_budget_minutes=18; snapshots=@(); files=@(); scans=@(); result='BLOCKED'
}

function Save-Json($Value, [string]$Name) {
    ConvertTo-Json -InputObject $Value -Depth 12 | Set-Content -LiteralPath (Join-Path $evidenceRoot $Name) -Encoding utf8
}

function Invoke-Program([string]$Label, [string[]]$Command, [int]$Timeout = 30, [switch]$AllowFailure) {
    if (-not $script:collecting) {
        $remaining = [int]($script:workDeadline - (Get-Date)).TotalSeconds
        if ($remaining -le 0) { throw 'Investigation work budget exhausted; preserving evidence.' }
        $Timeout = [Math]::Min($Timeout, $remaining)
    }
    $script:operationNumber++
    $operationPath = Join-Path $operationsRoot ('{0:d3}-{1}' -f $script:operationNumber, ($Label -replace '[^a-zA-Z0-9_.-]','_'))
    & python -m scripts.observed_process --directory $operationPath --label $Label --timeout $Timeout -- @Command |
        ForEach-Object { Write-Host $_ }
    $operation = Get-Content -LiteralPath (Join-Path $operationPath 'result.json') -Raw | ConvertFrom-Json
    $operation | Add-Member -NotePropertyName stdout_path -NotePropertyValue (Join-Path $operationPath 'stdout.txt')
    $operation | Add-Member -NotePropertyName stderr_path -NotePropertyValue (Join-Path $operationPath 'stderr.txt')
    if (-not $AllowFailure -and $operation.status -ne 'PASS') {
        throw "$Label : $($operation.status), exit $($operation.exit_code). See $operationPath"
    }
    return $operation
}

function Probe([string]$Label, [scriptblock]$Code, [hashtable]$Data = @{}, [int]$Timeout = 30) {
    $stem = Join-Path $operationsRoot ('probe-{0:d3}' -f ($script:operationNumber + 1))
    $dataPath = "$stem.json"; $codePath = "$stem.ps1"
    ConvertTo-Json -InputObject $Data -Depth 8 | Set-Content -LiteralPath $dataPath -Encoding utf8
    $prefix = @'
param([string]$DataFile)
$ErrorActionPreference = 'Stop'
$task = Get-Content -LiteralPath $DataFile -Raw | ConvertFrom-Json
$result = & {
'@
    ($prefix + [Environment]::NewLine + $Code.ToString() + [Environment]::NewLine +
        '}; ConvertTo-Json -InputObject $result -Depth 12') | Set-Content -LiteralPath $codePath -Encoding utf8
    $operation = Invoke-Program $Label @((Join-Path $PSHOME 'pwsh.exe'), '-NoProfile', '-NonInteractive',
        '-File', $codePath, $dataPath) $Timeout
    return (Get-Content -LiteralPath $operation.stdout_path -Raw | ConvertFrom-Json)
}

function Snapshot([string]$Stage) {
    $snapshot = Probe "snapshot-$Stage" {
        @{
            stage=$task.stage; utc=(Get-Date).ToUniversalTime().ToString('o')
            os=Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,OSArchitecture
            status=Get-MpComputerStatus | Select-Object AMRunningMode,AMServiceEnabled,AntivirusEnabled,
                AntispywareEnabled,RealTimeProtectionEnabled,BehaviorMonitorEnabled,IoavProtectionEnabled,
                OnAccessProtectionEnabled,IsTamperProtected,AMProductVersion,AMEngineVersion,
                AntivirusSignatureVersion,AntivirusSignatureLastUpdated,NISEnabled,NISEngineVersion,
                NISSignatureVersion,SmartAppControlState
            preferences=Get-MpPreference | Select-Object DisableRealtimeMonitoring,DisableBehaviorMonitoring,
                DisableIOAVProtection,DisableArchiveScanning,DisableScriptScanning,DisableBlockAtFirstSeen,
                DisableAutoExclusions,MAPSReporting,SubmitSamplesConsent,CloudBlockLevel,CloudExtendedTimeout,
                PUAProtection,EnableNetworkProtection,EnableControlledFolderAccess,ExclusionPath,ExclusionProcess,
                ExclusionExtension,ExclusionIpAddress,AttackSurfaceReductionOnlyExclusions,
                AttackSurfaceReductionRules_Ids,AttackSurfaceReductionRules_Actions
        }
    } @{stage=$Stage}
    $report.snapshots += $snapshot
    Save-Json $report 'report.json'
    return $snapshot
}

function Require-Protection($Snapshot) {
    $s=$Snapshot.status; $p=$Snapshot.preferences
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
    if (((Get-Date) - [datetime]$s.AntivirusSignatureLastUpdated).TotalHours -gt 48) {
        throw 'Security intelligence is older than 48 hours.'
    }
}

function Record-File([string]$Path, [string]$Stage) {
    $file = Probe "file-$Stage-$(Split-Path -Leaf $Path)" {
        $exists=Test-Path -LiteralPath $task.path -PathType Leaf
        $file=[ordered]@{stage=$task.stage;name=(Split-Path -Leaf $task.path);exists=$exists}
        if ($exists) {
            $file.bytes=(Get-Item -LiteralPath $task.path).Length
            $file.sha256=(Get-FileHash -LiteralPath $task.path -Algorithm SHA256).Hash.ToLowerInvariant()
            $file.zone_identifier=@(Get-Content -LiteralPath $task.path -Stream Zone.Identifier -ErrorAction SilentlyContinue)
        }
        $file
    } @{path=$Path;stage=$Stage}
    $report.files += $file
    Save-Json $report 'report.json'
    return $file
}

function Scan([string]$Path, [string]$Label) {
    Require-Protection (Snapshot "before-$Label")
    $operation=Invoke-Program "scan-$Label" @($script:scanner,'-Scan','-ScanType','3','-File',$Path) 180 -AllowFailure
    $report.scans += $operation
    Copy-Item -LiteralPath $operation.stdout_path -Destination (Join-Path $evidenceRoot "$Label-scan.txt")
    Save-Json $report 'report.json'
    if ($operation.status -ne 'PASS') { throw "Defender scan incomplete: $Label ($($operation.status))" }
    Require-Protection (Snapshot "after-$Label")
}

function Download([string]$Url, [string]$Path) {
    $null=Probe "download-$(Split-Path -Leaf $Path)" {
        Invoke-WebRequest -Uri $task.url -OutFile $task.path -TimeoutSec 90
        @{completed=$true}
    } @{url=$Url;path=$Path} 100
}

function Processes([string]$Stage) {
    $data=Probe "processes-$Stage" { @{rows=@(Get-CimInstance Win32_Process | Select-Object Name,ProcessId,ParentProcessId,CreationDate,ExecutablePath)} }
    Save-Json @($data.rows) "processes-$Stage.json"
}

try {
    $null=Snapshot 'runner-defaults'
    # Strengthen only this disposable VM; never allow or exclude a detection.
    $null=Probe 'enable-protection' {
        $preferences=Get-MpPreference
        foreach ($name in @('ExclusionPath','ExclusionProcess','ExclusionExtension','AttackSurfaceReductionOnlyExclusions')) {
            $values=@($preferences.$name | Where-Object { $_ })
            if ($values.Count) { $arguments=@{}; $arguments[$name]=$values; Remove-MpPreference @arguments }
        }
        $policy='HKLM:\SOFTWARE\Policies\Microsoft\Windows Advanced Threat Protection'
        if (Test-Path -LiteralPath $policy) {
            if ((Get-ItemPropertyValue -LiteralPath $policy -Name ForceDefenderPassiveMode -ErrorAction SilentlyContinue) -eq 1) {
                Set-ItemProperty -LiteralPath $policy -Name ForceDefenderPassiveMode -Value 0
            }
        }
        Set-MpPreference -DisableRealtimeMonitoring $false -DisableBehaviorMonitoring $false -DisableIOAVProtection $false -DisableArchiveScanning $false -DisableScriptScanning $false -DisableBlockAtFirstSeen $false -DisableAutoExclusions $true -MAPSReporting Advanced -SubmitSamplesConsent SendSafeSamples -PUAProtection Enabled
        @{completed=$true}
    } @{} 60
    $null=Probe 'update-intelligence' { Update-MpSignature -UpdateSource MicrosoftUpdateServer; @{completed=$true} } @{} 120
    $readyDeadline=(Get-Date).AddSeconds(90)
    do {
        $ready=Snapshot 'waiting-for-protection'
        try { Require-Protection $ready; break }
        catch { if ((Get-Date) -ge $readyDeadline) { throw }; Start-Sleep -Seconds 5 }
    } while ($true)
    Require-Protection (Snapshot 'enabled-updated')
    $report.protection_ready_utc=(Get-Date).ToUniversalTime().ToString('o')
    Processes 'before-download'
    $script:scanner=(Get-ChildItem -Path "$env:ProgramData\Microsoft\Windows Defender\Platform\*\MpCmdRun.exe" |
        Sort-Object FullName -Descending | Select-Object -First 1).FullName
    if (-not $script:scanner) { $script:scanner="$env:ProgramFiles\Windows Defender\MpCmdRun.exe" }
    $cloud=Invoke-Program 'cloud-connection' @($script:scanner,'-ValidateMapsConnection') 60
    $report.cloud_connection_exit_code=$cloud.exit_code
    $downloadRoot=Join-Path $env:USERPROFILE 'Downloads\MiniWhiteboard-investigation'
    New-Item -ItemType Directory -Path $downloadRoot -ErrorAction Stop | Out-Null
    $assets=@(
        @{name='MiniWhiteboard-1.3.4-HotkeyPatch-Setup.exe';bytes=27476405;sha256='29770151f8df811e1f8890a93aaa201f2e666e05bb1310dcf086bbd7b73a460b'},
        @{name='WinMiniWhiteboardV1.3.4-HotkeyPatch.zip';bytes=38075984;sha256='5fa64240a14d49c5ec2cb1d2fd5ad2f370365474a3c5a165c9806516ac37dc89'}
    )
    foreach ($asset in $assets) {
        $asset.url='https://github.com/nottbradd/MiniWhiteboard/releases/download/v1.3.4/'+$asset.name
        $path=Join-Path $downloadRoot $asset.name
        Download $asset.url $path
        $file=Record-File $path 'downloaded'
        if ($file.sha256 -ne $asset.sha256 -or $file.bytes -ne $asset.bytes) { throw 'Published download identity mismatch.' }
        Scan $path $asset.name
        $file=Record-File $path 'after-scan'
        if ($file.sha256 -ne $asset.sha256) { throw 'Download is missing or changed after scan.' }
    }
    $report.assets=$assets
    $extracted=Join-Path $downloadRoot 'portable'
    $null=Probe 'extract-portable' {
        Expand-Archive -LiteralPath $task.archive -DestinationPath $task.destination
        @{completed=$true}
    } @{archive=(Join-Path $downloadRoot $assets[1].name);destination=$extracted} 60
    $exe=Join-Path $extracted 'Mini Whiteboard\Mini Whiteboard.exe'
    $file=Record-File $exe 'after-extraction'
    if ($file.sha256 -ne 'a539339e2ee83c54be86e3e67115c5d1f0bcbca12605bb875ba241f5b79e2716') { throw 'Extracted executable missing or different.' }
    Scan $extracted 'portable-extracted'
    $file=Record-File $exe 'after-extracted-scan'
    if ($file.sha256 -ne 'a539339e2ee83c54be86e3e67115c5d1f0bcbca12605bb875ba241f5b79e2716') { throw 'Extracted executable missing or changed after scan.' }
    $inventory=Probe 'inventory-extracted' {
        @{files=@(Get-ChildItem -LiteralPath $task.root -Recurse -File | ForEach-Object {
            @{path=$_.FullName.Substring($task.root.Length+1);bytes=$_.Length;sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
        })}
    } @{root=$extracted} 60
    Save-Json @($inventory.files) 'extracted-files.json'
    if ($Exercise) {
        if ($Package -ne 'portable') {
            $previousPath=Join-Path $downloadRoot 'MiniWhiteboard-1.3.4-Setup.exe'
            Download 'https://github.com/nottbradd/MiniWhiteboard/releases/download/v1.3.4/MiniWhiteboard-1.3.4-Setup.exe' $previousPath
            $previous=Record-File $previousPath 'predecessor-download'
            if ($previous.sha256 -ne '0139ba25a5b9cd119c52d42e30ca3052ebb49877d2eee14d45432eacc4506222') { throw 'Predecessor identity mismatch.' }
            Scan $previousPath 'predecessor'
        }
        # A scan can return zero after remediation. Check history before execution.
        $priorThreats=Probe 'threats-before-runtime' { @{detections=@(Get-MpThreatDetection | Select-Object ThreatID,Resources,ActionSuccess)} }
        Save-Json @($priorThreats.detections) 'detections-before-runtime.json'
        if (@($priorThreats.detections).Count) { throw 'Detection before runtime; inspect attribution before executing samples.' }
        Require-Protection (Snapshot 'before-runtime')
        $report.runtime="Attempting scripted $Package checks; see runtime.json"
        Save-Json $report 'report.json'
        $runtime=Invoke-Program "runtime-$Package" @((Get-Command python).Source,'-m','scripts.defender_runtime_check',
            '--downloads',$downloadRoot,'--output',$evidenceRoot,'--package',$Package) 600 -AllowFailure
        $report.runtime_exit_code=$runtime.exit_code; $report.runtime_status=$runtime.status
        Require-Protection (Snapshot 'after-runtime')
        if ($runtime.status -ne 'PASS') { throw "Exact-package runtime investigation $($runtime.status); see operation output." }
        $report.runtime="Completed scripted $Package checks of the original published executable; see runtime.json"
        Scan $downloadRoot 'after-runtime'
    }
    $report.result='SCANS COMPLETED; runtime and browser-download acceptance NOT RUN'
    if ($Exercise) { $report.result='ORIGINAL PACKAGE INVESTIGATION COMPLETED; browser-download and final release acceptance NOT RUN' }
} catch {
    $report.error=$_.Exception.Message
    Write-Warning $report.error
} finally {
    # Independent collection deadlines leave time for the artifact upload.
    $script:collecting=$true
    Save-Json $report 'report.json'
    try { Require-Protection (Snapshot 'end') } catch { $report.final_snapshot_error=$_.Exception.Message }
    try {
        $history=Probe 'collect-threat-history' {
            @{
                threats=@(Get-MpThreat | Select-Object ThreatID,ThreatName,CategoryID,SeverityID,DidThreatExecute,IsActive,Resources)
                detections=@(Get-MpThreatDetection | Select-Object ThreatID,DetectionID,InitialDetectionTime,LastThreatStatusChangeTime,
                    RemediationTime,ProcessName,Resources,ActionSuccess,CleaningActionID,ThreatStatusID,ThreatStatusErrorCode,
                    CurrentThreatExecutionStatusID,DetectionSourceTypeID,AMProductVersion)
            }
        }
        Save-Json @($history.threats) 'threats.json'
        Save-Json @($history.detections) 'detections.json'
        if (@($history.detections).Count) { $report.result='DETECTION OBSERVED; inspect attribution' }
    } catch { $report.threat_history_error=$_.Exception.Message; $report.result='THREAT HISTORY INCOMPLETE' }
    try { Processes 'after-runtime' } catch { $report.process_history_error=$_.Exception.Message }
    try {
        $eventData=Probe 'collect-defender-events' {
            @{events=@(Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Windows Defender/Operational';StartTime=[datetime]$task.start} -ErrorAction Stop |
                ForEach-Object { @{utc=$_.TimeCreated.ToUniversalTime().ToString('o');id=$_.Id;level=$_.LevelDisplayName;message=$_.Message;xml=$_.ToXml()} })}
        } @{start=$started.ToUniversalTime().ToString('o')}
        $events=@($eventData.events)
        Save-Json @($events) 'defender-events.json'
        $report.detection_event_count=@($events | Where-Object id -In 1006,1007,1008,1015,1116,1117,1118,1119,1121).Count
        if ($report.detection_event_count) { $report.result='DETECTION OR BLOCK OBSERVED; inspect events' }
        $report.protection_disabled_event_count=@($events | Where-Object id -In 5001,5010,5012).Count
        if ($report.protection_disabled_event_count) { $report.result='PROTECTION CHANGE OBSERVED; acceptance invalid' }
    } catch { $report.event_log_error=$_.Exception.Message; $report.result='DEFENDER EVENTS INCOMPLETE' }
    if ($report.process_history_error) { $report.result='PROCESS HISTORY INCOMPLETE' }
    if ($report.final_snapshot_error) { $report.result='FINAL PROTECTION SNAPSHOT INCOMPLETE' }
    $report.ended_utc=(Get-Date).ToUniversalTime().ToString('o')
    Save-Json $report 'report.json'
    Write-Output $report.result
}
if ($report.result -notlike 'SCANS COMPLETED*' -and $report.result -notlike 'ORIGINAL PACKAGE INVESTIGATION COMPLETED*') { exit 1 }
