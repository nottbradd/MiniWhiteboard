"""Dismiss the hosted Windows client's first-run Start menu before photographing it."""
import os
from pathlib import Path
import sys
import time


def main():
    if sys.platform != 'win32' or os.getenv('GITHUB_ACTIONS') != 'true' or os.getenv('RUNNER_ENVIRONMENT') != 'github-hosted':
        raise SystemExit('This check operates only on a disposable GitHub-hosted Windows client.')
    import win32api
    import win32con
    import win32gui
    import win32process
    from pywinauto.keyboard import send_keys
    def owner(hwnd):
        if not hwnd:
            return ''
        _,pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            handle=win32api.OpenProcess(0x1000,False,pid)
            try:
                import ctypes as C
                from ctypes import wintypes as W
                query=C.windll.kernel32.QueryFullProcessImageNameW
                query.argtypes=[W.HANDLE,W.DWORD,W.LPWSTR,C.POINTER(W.DWORD)]
                buf=C.create_unicode_buffer(1024)
                size=W.DWORD(len(buf))
                if query(int(handle),0,buf,C.byref(size)):
                    return Path(buf.value).stem.lower()
            finally:
                handle.Close()
        except OSError:
            pass
        return ''
    point=(win32api.GetSystemMetrics(0)//2,win32api.GetSystemMetrics(1)//2)
    deadline=time.monotonic()+18
    clear_since=None
    shell_hosts={'startmenuexperiencehost','searchhost'}
    while time.monotonic()<deadline:
        at=win32gui.GetAncestor(win32gui.WindowFromPoint(point),win32con.GA_ROOT)
        fg=win32gui.GetForegroundWindow()
        target,front=owner(at),owner(fg)
        print('Desktop centre / foreground:',target,front,flush=True)
        if target in shell_hosts or front in shell_hosts:
            clear_since=None
            if front in shell_hosts:
                send_keys('{ESC}')
            if target in shell_hosts:
                win32gui.ShowWindow(at,win32con.SW_HIDE)
        elif clear_since is None:
            clear_since=time.monotonic()
        elif time.monotonic()-clear_since>=2:
            return
        time.sleep(.35)
    raise RuntimeError('The Windows Start panel still covers the native test area.')


if __name__=='__main__':
    main()
