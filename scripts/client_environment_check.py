"""Bounded, recorded readiness repair on a disposable Windows client VM."""
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time


def setup_wsl(output):
    """One normal install/update command; never disable features or protection."""
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
        raise RuntimeError('Disposable hosted client only')
    from scripts.observed_process import run
    from scripts.client_wizard_check import native_windows
    from PIL import ImageGrab
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    report=dict(scope='Authorised normal WSL setup on an owned disposable VM',
                started_utc=datetime.now(timezone.utc).isoformat(),operations=[],result='INCOMPLETE',
                security_settings_changed=False,distribution_installed=False)
    def save():
        (output/'setup.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    def observe(label):
        (output/(label+'.json')).write_text(json.dumps(native_windows(),indent=2),encoding='utf-8')
        ImageGrab.grab(all_screens=True).save(output/(label+'.png'))
    def operation(label,command,timeout):
        report['phase']=label;save()
        result=run(command,output/label,label,timeout)
        report['operations'].append(result);save()
        return result
    executable=str(Path(os.environ['WINDIR'])/'System32/wsl.exe')
    try:
        save();observe('before')
        before=operation('version-before',[executable,'--version'],10)
        raw=(output/'version-before/stderr.txt').read_bytes()
        message=raw.decode('utf-16-le' if b'\x00' in raw else 'utf-8',errors='replace')
        if before['status']!='PASS' and 'Windows Subsystem for Linux is not installed' in message:
            report['setup_choice']='Missing WSL: normal install without a distribution'
            command=[executable,'--install','--no-distribution','--web-download']
        else:
            report['setup_choice']='Existing WSL: normal update'
            command=[executable,'--update','--web-download']
        updated=operation('normal-setup',command,180)
        if updated['status']=='FAILED':
            raw=(output/'normal-setup/stderr.txt').read_bytes()
            message=raw.decode('utf-16-le' if b'\x00' in raw else 'utf-8',errors='replace')
            if 'Windows Subsystem for Linux is not installed' in message and updated['elapsed_seconds']<1:
                # The image's stub rejects even its advertised --install path.
                # Microsoft's official MSI is a normal documented setup route.
                updated=operation('official-msi',['pwsh','-NoProfile','-NonInteractive','-File',
                    str(Path(__file__).with_name('setup_client_wsl.ps1')),'-Output',str(output.resolve())],210)
        if updated['status']!='PASS':
            raise RuntimeError('Normal WSL setup failed or timed out; no further setup or reboot attempted')
        after=operation('version-after',[executable,'--version'],15)
        if after['status']!='PASS':
            raise RuntimeError('WSL version still unavailable after the bounded update')
        report['result']='PASS for WSL command readiness; desktop preflight remains separate'
    except Exception as error:
        report.update(result='BLOCKED',error=str(error));raise
    finally:
        observe('after');report['ended_utc']=datetime.now(timezone.utc).isoformat();save()


def dismiss_wsl_prompt():
    """Close only the observed unrelated WSL terminal, at most once per VM job."""
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
        raise RuntimeError('Disposable hosted client only')
    from scripts.client_wizard_check import native_windows
    rows=native_windows()
    expected=str(Path(os.environ['WINDIR'])/'system32/wsl.exe').lower()
    targets=[r for r in rows if r['title'].lower()==expected]
    if not targets:
        return
    output=Path(os.environ['GITHUB_WORKSPACE'])/'verification/client-desktop'
    output.mkdir(parents=True,exist_ok=True)
    receipt=output/'wsl-prompt-dismissal.json'
    from PIL import ImageGrab
    ImageGrab.grab(all_screens=True).save(output/'wsl-before-close.png')
    if receipt.exists() or len(targets)!=1:
        raise RuntimeError('WSL prompt recurred or is ambiguous after the one allowed environment repair')
    row=targets[0]
    kernel=C.windll.kernel32
    kernel.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];kernel.OpenProcess.restype=W.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes=[W.HANDLE,W.DWORD,W.LPWSTR,C.POINTER(W.DWORD)]
    kernel.CloseHandle.argtypes=[W.HANDLE]
    handle=kernel.OpenProcess(0x1000,False,row['pid'])
    name=C.create_unicode_buffer(32768);size=W.DWORD(len(name))
    try:
        if not handle or not kernel.QueryFullProcessImageNameW(handle,0,name,C.byref(size)):
            raise RuntimeError('Cannot identify the WSL prompt process')
    finally:
        if handle: kernel.CloseHandle(handle)
    if Path(name.value).name.lower() not in ('windowsterminal.exe','conhost.exe','wsl.exe'):
        raise RuntimeError('Unexpected WSL prompt window owner; no close sent')
    data=dict(utc=datetime.now(timezone.utc).isoformat(),window=row,process_image=name.value,
              action='WM_CLOSE of the observed unrelated WSL update terminal',
              os_settings_changed=False,installation_input_sent=False,security_warning_dismissed=False)
    receipt.write_text(json.dumps(data,indent=2),encoding='utf-8')
    u=C.windll.user32
    u.PostMessageW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM]
    u.IsWindowVisible.argtypes=[W.HWND]
    if not u.PostMessageW(row['handle'],0x10,0,0):
        raise RuntimeError('Could not request closing the WSL prompt')
    deadline=time.monotonic()+3
    while u.IsWindowVisible(row['handle']) and time.monotonic()<deadline:
        time.sleep(.05)
    data['closed']=not bool(u.IsWindowVisible(row['handle']))
    receipt.write_text(json.dumps(data,indent=2),encoding='utf-8')
    ImageGrab.grab(all_screens=True).save(output/'wsl-after-close.png')
    if not data['closed']:
        raise RuntimeError('WSL prompt did not close; client remains unusable')


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--setup',type=Path)
    action.add_argument('--observe',type=Path)
    args=parser.parse_args()
    if args.setup:
        setup_wsl(args.setup)
    else:
        if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
            raise RuntimeError('Disposable hosted client only')
        from scripts.client_wizard_check import native_windows
        from PIL import ImageGrab
        args.observe.mkdir(parents=True,exist_ok=True)
        (args.observe/'before.json').write_text(json.dumps(dict(
            utc=datetime.now(timezone.utc).isoformat(),windows=native_windows(),
            scope='Initial VM state before normal WSL setup; no application bytes executed'),indent=2),encoding='utf-8')
        ImageGrab.grab(all_screens=True).save(args.observe/'before.png')
