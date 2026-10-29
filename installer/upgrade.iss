{ Replacement is staged and verified before the normal Inno copy phase.
  Inno owns install/uninstall metadata; our backup restores overwritten bytes
  after its rollback. Obsolete files require trusted path AND original hash. }
const
  PayloadName = 'MiniWhiteboard.payload';
  PayloadHeader = 'MiniWhiteboard payload v1 {94CAAC15-1695-4601-9CA3-67F10E2A8A32}';
var
  NewPayload, OldPayload, BackedUp, NewPaths: TStringList;
  InstallStarted, ReplacementVerified, InstallCommitted, BackupReady: Boolean;
  UpgradeRoot, BackupRoot: String;

function FileAttributes(Name: String): Cardinal;
  external 'GetFileAttributesW@kernel32.dll stdcall';
function OpenExisting(Name: String; Access, Share: Cardinal; Security: Integer;
                      Disposition, Flags: Cardinal; Template: Integer): THandle;
  external 'CreateFileW@kernel32.dll stdcall';
function CloseNative(Handle: THandle): Boolean;
  external 'CloseHandle@kernel32.dll stdcall';

function SafePath(Root, Relative: String): String;
var
  I: Integer;
  Part, Current: String;
begin
  if (Relative = '') or (Pos(':', Relative) > 0) or (Pos('\', Relative) > 0) or
     (Relative[1] = '/') then RaiseException('Unsafe payload path.');
  Current := RemoveBackslash(ExpandFileName(Root));
  { Reject reparse points throughout the destination path, not just the leaf. }
  Part := Current;
  while Length(Part) > 3 do begin
    if (FileAttributes(Part) <> $FFFFFFFF) and ((FileAttributes(Part) and $400) <> 0) then
      RaiseException('Install paths must not contain junctions or symbolic links.');
    Part := ExtractFileDir(Part);
  end;
  Part := '';
  for I := 1 to Length(Relative) + 1 do begin
    if (I > Length(Relative)) or (Relative[I] = '/') then begin
      if (Part = '') or (Part = '.') or (Part = '..') or
         (Part[Length(Part)] = '.') or (Part[Length(Part)] = ' ') then
        RaiseException('Unsafe payload path component.');
      Current := AddBackslash(Current) + Part;
      if (FileAttributes(Current) <> $FFFFFFFF) and ((FileAttributes(Current) and $400) <> 0) then
        RaiseException('Payload paths must not contain junctions or symbolic links.');
      Part := '';
    end else begin
      if Pos(Relative[I], ':*?<>|"') > 0 then RaiseException('Unsafe payload filename.');
      Part := Part + Relative[I];
    end;
  end;
  Result := Current;
end;

function EntryPath(Line: String): String;
begin
  Result := Copy(Line, 67, MaxInt);
end;

procedure LoadPayload(Name: String; List: TStringList; Root: String);
var
  I, J: Integer;
  Digest, Relative: String;
  Seen: TStringList;
begin
  List.LoadFromFile(Name);
  if (List.Count < 3) or (List[0] <> PayloadHeader) or
     (Pos('version=', List[1]) <> 1) then RaiseException('Invalid payload inventory.');
  Seen := TStringList.Create;
  try
    for I := 2 to List.Count - 1 do begin
      Digest := Copy(List[I], 1, 64);
      Relative := EntryPath(List[I]);
      if (Length(Digest) <> 64) or (Copy(List[I], 65, 2) <> '  ') then
        RaiseException('Invalid payload hash.');
      for J := 1 to 64 do
        if Pos(Digest[J], '0123456789abcdef') = 0 then RaiseException('Invalid payload hash.');
      SafePath(Root, Relative);
      if Seen.IndexOf(Lowercase(Relative)) >= 0 then RaiseException('Duplicate payload path.');
      Seen.Add(Lowercase(Relative));
    end;
    if Seen.IndexOf('mini whiteboard.exe') < 0 then RaiseException('Missing application inventory.');
  finally
    Seen.Free;
  end;
end;

procedure VerifyPayload(List: TStringList; Root: String);
var
  I: Integer;
  Name: String;
begin
  for I := 2 to List.Count - 1 do begin
    Name := SafePath(Root, EntryPath(List[I]));
    if not FileExists(Name) or (CompareText(GetSHA256OfFile(Name), Copy(List[I], 1, 64)) <> 0) then
      RaiseException('Replacement verification failed: ' + EntryPath(List[I]));
  end;
end;

procedure BackupFile(Relative: String);
var
  Name, Destination: String;
  Handle: THandle;
begin
  if BackedUp.IndexOf(Relative) >= 0 then Exit;
  Name := SafePath(UpgradeRoot, Relative);
  if not FileExists(Name) then Exit;
  { Test write/delete access without changing bytes. No reboot replacement. }
  Handle := OpenExisting(Name, $C0010000, 7, 0, 3, 0, 0);
  if Handle = THandle(-1) then
    RaiseException('Cannot replace ' + Relative + '. Close the application using it and retry.');
  CloseNative(Handle);
  Destination := SafePath(BackupRoot, Relative);
  if not ForceDirectories(ExtractFileDir(Destination)) or not FileCopy(Name, Destination, True) then
    RaiseException('Could not back up the previous application. Installation was not started.');
  if GetSHA256OfFile(Name) <> GetSHA256OfFile(Destination) then RaiseException('Backup verification failed.');
  BackedUp.Add(Relative);
end;

procedure PrepareReplacement;
var
  I: Integer;
  Stage, OldManifest, RegisteredHash, Relative: String;
  LegacyMatches: Boolean;
begin
  UpgradeRoot := RemoveBackslash(ExpandFileName(ExpandConstant('{app}')));
  if (Length(UpgradeRoot) < 4) or (UpgradeRoot[2] <> ':') or (UpgradeRoot[3] <> '\') or
     (UpgradeRoot = ExtractFileDrive(UpgradeRoot) + '\') then
    RaiseException('Choose a folder on a local drive, not a drive root or network share.');
  if (PreviousInstall <> '') and (CompareText(UpgradeRoot, RemoveBackslash(ExpandFileName(PreviousInstall))) <> 0) then
    RaiseException('Upgrade the existing Mini Whiteboard folder: ' + PreviousInstall);
  if (PreviousInstall = '') and FileExists(UpgradeRoot + '\Mini Whiteboard.exe') then
    RaiseException('This folder contains an unregistered copy. Choose a new installation folder; keep portable copies separate.');
  ExtractTemporaryFiles('{app}\*');
  Stage := ExpandConstant('{tmp}') + '\{app}';
  NewPayload := TStringList.Create;
  OldPayload := TStringList.Create;
  BackedUp := TStringList.Create;
  NewPaths := TStringList.Create;
  BackupRoot := ExpandConstant('{tmp}\previous-payload');
  LoadPayload(Stage + '\' + PayloadName, NewPayload, Stage);
  VerifyPayload(NewPayload, Stage);
  OldManifest := UpgradeRoot + '\' + PayloadName;
  if (PreviousInstall <> '') then begin
    if FileExists(OldManifest) and
       RegQueryStringValue(HKCU, UninstallKey, 'PayloadManifestSHA256', RegisteredHash) and
       (CompareText(GetSHA256OfFile(OldManifest), RegisteredHash) = 0) then
      LoadPayload(OldManifest, OldPayload, UpgradeRoot)
    else begin
      { V1.3.3 predates inventories. Only its exact published EXE establishes
        ownership for the embedded V1.3.3 file/hash list. }
      ExtractTemporaryFile('legacy-v1.3.3.payload');
      LoadPayload(ExpandConstant('{tmp}\legacy-v1.3.3.payload'), OldPayload, UpgradeRoot);
      LegacyMatches := False;
      for I := 2 to OldPayload.Count - 1 do
        if EntryPath(OldPayload[I]) = 'Mini Whiteboard.exe' then
          LegacyMatches := FileExists(UpgradeRoot + '\Mini Whiteboard.exe') and
             (CompareText(GetSHA256OfFile(UpgradeRoot + '\Mini Whiteboard.exe'), Copy(OldPayload[I], 1, 64)) = 0);
      if not LegacyMatches then OldPayload.Clear;
    end;
  end;
  for I := 2 to NewPayload.Count - 1 do begin
    Relative := EntryPath(NewPayload[I]);
    SafePath(UpgradeRoot, Relative);
    NewPaths.Add(Relative);
    BackupFile(Relative);
  end;
  NewPaths.Add(PayloadName);
  BackupFile(PayloadName);
  for I := 2 to OldPayload.Count - 1 do
    BackupFile(EntryPath(OldPayload[I]));
  BackupReady := True;
end;

procedure VerifyReplacement;
begin
  { This is the final [Files] entry, before Inno commits uninstall metadata. }
  VerifyPayload(NewPayload, UpgradeRoot);
  ReplacementVerified := True;
end;

procedure CommitReplacement;
var
  I: Integer;
  Relative, Name, Parent: String;
begin
  if not ReplacementVerified then RaiseException('Replacement was not verified.');
  for I := 2 to OldPayload.Count - 1 do begin
    Relative := EntryPath(OldPayload[I]);
    if NewPaths.IndexOf(Relative) < 0 then begin
      Name := SafePath(UpgradeRoot, Relative);
      if FileExists(Name) and (CompareText(GetSHA256OfFile(Name), Copy(OldPayload[I], 1, 64)) = 0) then begin
        if not DeleteFile(Name) then
          Log('Preserved obsolete file that could not be removed: ' + Name)
        else begin
          Log('Removed obsolete owned payload: ' + Relative);
          Parent := ExtractFileDir(Name);
          while (CompareText(Parent, UpgradeRoot) <> 0) and RemoveDir(Parent) do
            Parent := ExtractFileDir(Parent);
        end;
      end;
    end;
  end;
  RegWriteStringValue(HKCU, UninstallKey, 'PayloadManifestSHA256', GetSHA256OfFile(UpgradeRoot + '\' + PayloadName));
  InstallCommitted := True;
end;

procedure RestoreReplacement;
var
  I: Integer;
  Name, Saved: String;
  Failed: Boolean;
begin
  if not BackupReady or not InstallStarted or InstallCommitted then Exit;
  Failed := False;
  for I := 0 to NewPaths.Count - 1 do
    if BackedUp.IndexOf(NewPaths[I]) < 0 then
      DeleteFile(SafePath(UpgradeRoot, NewPaths[I]));
  for I := 0 to BackedUp.Count - 1 do begin
    Name := SafePath(UpgradeRoot, BackedUp[I]);
    Saved := SafePath(BackupRoot, BackedUp[I]);
    ForceDirectories(ExtractFileDir(Name));
    if not FileExists(Name) or (GetSHA256OfFile(Name) <> GetSHA256OfFile(Saved)) then
      if not FileCopy(Saved, Name, False) then Failed := True;
  end;
  if Failed then
    MsgBox('Some previous files could not be restored. Close applications using this folder and run the previous installer again.', mbError, MB_OK)
  else Log('Previous payload restored after cancelled or failed installation.');
end;
