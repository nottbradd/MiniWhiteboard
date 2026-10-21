; Per-user installation. Keep AppId and mutex names stable across upgrades.
#ifndef AppVersion
  #define AppVersion "1.3.2"
#endif
#ifndef BundleDir
  #define BundleDir "..\dist\windows-v132-review01\Mini Whiteboard"
#endif
#ifndef OutputDir
  #define OutputDir "..\build\candidates\v1.3.2\review-01"
#endif

[Setup]
AppId={{94CAAC15-1695-4601-9CA3-67F10E2A8A32}
AppName=Mini Whiteboard
AppVersion={#AppVersion}
AppPublisher=nottbradd
AppPublisherURL=https://github.com/nottbradd/MiniWhiteboard
AppSupportURL=https://github.com/nottbradd/MiniWhiteboard/issues
DefaultDirName={localappdata}\Programs\Mini Whiteboard
DefaultGroupName=Mini Whiteboard
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
AppMutex=Local\MiniWhiteboard-9fb88530
SetupMutex=Local\MiniWhiteboard-Setup
CloseApplications=no
RestartApplications=no
RestartIfNeededByRun=no
UninstallRestartComputer=no
UninstallDisplayIcon={app}\Mini Whiteboard.exe
UninstallDisplayName=Mini Whiteboard
SetupIconFile=..\assets\mini_whiteboard.ico
WizardImageFile=..\assets\installer\wizard.png
WizardSmallImageFile=..\assets\installer\wizard-small.png
LicenseFile=..\LICENSE
OutputDir={#OutputDir}
OutputBaseFilename=MiniWhiteboard-{#AppVersion}-Setup
VersionInfoVersion={#AppVersion}.0
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
UsePreviousAppDir=yes
UsePreviousTasks=yes
DisableWelcomePage=no

[Tasks]
Name: desktopicon; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Mini Whiteboard"; Filename: "{app}\Mini Whiteboard.exe"; WorkingDir: "{app}"; IconFilename: "{app}\Mini Whiteboard.exe"; AppUserModelID: "MiniWhiteboard.Desktop"
Name: "{autodesktop}\Mini Whiteboard"; Filename: "{app}\Mini Whiteboard.exe"; WorkingDir: "{app}"; IconFilename: "{app}\Mini Whiteboard.exe"; AppUserModelID: "MiniWhiteboard.Desktop"; Tasks: desktopicon

[Run]
Filename: "{app}\Mini Whiteboard.exe"; Description: "Launch Mini Whiteboard in the tray"; Flags: nowait postinstall skipifsilent unchecked

[Code]
const
  RunKey = 'Software\Microsoft\Windows\CurrentVersion\Run';
  ApprovalKey = 'Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run';
  UninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{94CAAC15-1695-4601-9CA3-67F10E2A8A32}_is1';

var
  PreviousInstall: String;

function InitializeSetup: Boolean;
begin
  RegQueryStringValue(HKCU, UninstallKey, 'InstallLocation', PreviousInstall);
  Result := True;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if CheckForMutexes('Local\MiniWhiteboard-9fb88530') then
    Result := 'Mini Whiteboard is running. Keep any work you need, then choose Exit from its tray menu before installing.';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Command, PreviousCommand, NewCommand: String;
begin
  if (CurStep = ssPostInstall) and (PreviousInstall <> '') then begin
    PreviousCommand := '"' + AddBackslash(PreviousInstall) + 'Mini Whiteboard.exe" --login';
    NewCommand := '"' + ExpandConstant('{app}\Mini Whiteboard.exe') + '" --login';
    if (CompareText(PreviousCommand, NewCommand) <> 0) and
       RegQueryStringValue(HKCU, RunKey, 'MiniWhiteboard', Command) and
       (CompareText(Command, PreviousCommand) = 0) then
      RegWriteStringValue(HKCU, RunKey, 'MiniWhiteboard', NewCommand);
    { Preserve the OS approval record, including an external disable. }
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Command: String;
  Expected: String;
begin
  if CurUninstallStep = usUninstall then begin
    Expected := '"' + ExpandConstant('{app}\Mini Whiteboard.exe') + '" --login';
    if RegQueryStringValue(HKCU, RunKey, 'MiniWhiteboard', Command) and
       (CompareText(Command, Expected) = 0) then begin
      RegDeleteValue(HKCU, RunKey, 'MiniWhiteboard');
      RegDeleteValue(HKCU, ApprovalKey, 'MiniWhiteboard');
    end;
  end;
end;
