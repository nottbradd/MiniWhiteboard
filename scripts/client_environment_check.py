"""Bounded, recorded readiness repair on a disposable Windows client VM."""
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time


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
