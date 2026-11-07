"""Normal Shell/installer UI in a disposable client; never dismiss security blocks."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import threading


def native_windows():
    """Capture top-level state without waiting on an accessibility provider."""
    import ctypes as C
    from ctypes import wintypes as W
    u=C.windll.user32
    callback_type=C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
    u.IsWindowVisible.argtypes=[W.HWND]
    u.GetWindowTextW.argtypes=[W.HWND,W.LPWSTR,C.c_int]
    u.GetWindowThreadProcessId.argtypes=[W.HWND,C.POINTER(W.DWORD)]
    u.GetWindowRect.argtypes=[W.HWND,C.POINTER(W.RECT)]
    u.EnumWindows.argtypes=[callback_type,W.LPARAM]
    rows=[]
    @callback_type
    def visit(hwnd,_):
        if u.IsWindowVisible(hwnd):
            title=C.create_unicode_buffer(256);u.GetWindowTextW(hwnd,title,256)
            pid=W.DWORD();u.GetWindowThreadProcessId(hwnd,C.byref(pid))
            rect=W.RECT();u.GetWindowRect(hwnd,C.byref(rect))
            rows.append(dict(title=title.value,pid=pid.value,handle=int(hwnd),rectangle=[rect.left,rect.top,rect.right,rect.bottom]))
        return True
    u.EnumWindows(visit,0)
    return rows


def shell_open(launch,output):
    """Observe a Shell call that may itself block on an OS confirmation."""
    from PIL import ImageGrab
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    result={};done=threading.Event()
    def worker():
        import pythoncom
        pythoncom.CoInitialize()
        try:
            result['value']=launch()
        except Exception as error:
            result['error']=repr(error)
        finally:
            done.set();pythoncom.CoUninitialize()
    threading.Thread(target=worker,daemon=True).start()
    deadline=time.monotonic()+20
    previous=None;index=0
    while True:
        rows=native_windows();current=json.dumps(rows)
        if current!=previous:
            previous=current;index+=1
            (output/f'{index:02}-windows.json').write_text(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(),windows=rows,shell_returned=done.is_set()),indent=2),encoding='utf-8')
            ImageGrab.grab(all_screens=True).save(output/f'{index:02}-shell.png')
        security=[r['title'] for r in rows if any(t in r['title'].lower() for t in
                  ('smartscreen','windows protected','open file - security warning','user account control'))]
        if security:
            raise RuntimeError('Shell confirmation/block retained without dismissal: '+repr(security))
        if done.is_set():
            if 'error' in result: raise RuntimeError('Shell open failed: '+result['error'])
            return result.get('value')
        if time.monotonic()>=deadline:
            raise TimeoutError('Shell call did not return within 20 seconds; native windows and pixels retained')
        time.sleep(.25)


def main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
        raise SystemExit('Disposable hosted client only')
    parser=argparse.ArgumentParser()
    parser.add_argument('--executable',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--uninstall',action='store_true')
    args=parser.parse_args()
    from pywinauto import Desktop
    from PIL import ImageGrab
    desktop=Desktop(backend='uia')
    args.output.mkdir(parents=True,exist_ok=True)
    report=dict(started_utc=datetime.now(timezone.utc).isoformat(),method='Windows Shell open; normal visible wizard',
                security_warning_dismissed=False,steps=[],result='INCOMPLETE')
    target=Path(os.environ['LOCALAPPDATA'])/'Programs/Mini Whiteboard/Mini Whiteboard.exe'
    def save(label,windows):
        report['steps'].append(dict(utc=datetime.now(timezone.utc).isoformat(),phase=label,windows=windows))
        (args.output/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        ImageGrab.grab(all_screens=True).save(args.output/f'{len(report["steps"]):02}-{label}.png')
    def clean(text): return text.replace('&','').strip()
    try:
        save('before-shell-open',[])
        shell_open(lambda:os.startfile(str(args.executable.resolve())),args.output/'shell')
        deadline=time.monotonic()+65
        fingerprint=None
        finish_clicked=False
        while time.monotonic()<deadline:
            native=native_windows()
            (args.output/'latest-native-windows.json').write_text(json.dumps(native,indent=2),encoding='utf-8')
            ImageGrab.grab(all_screens=True).save(args.output/'latest-native.png')
            visible=[w for w in desktop.windows() if w.is_visible()]
            owned=[w for w in visible if 'Mini Whiteboard' in w.window_text() and
                   ('Setup' in w.window_text() or 'Uninstall' in w.window_text())]
            rows=[dict(title=w.window_text(),controls=[c.window_text() for c in w.descendants()]) for w in owned]
            security=[w.window_text() for w in visible if any(s in w.window_text().lower() for s in
                      ('smartscreen','windows protected','open file - security warning','user account control'))]
            if security:
                save('security-block',rows+[dict(security_titles=security)])
                raise RuntimeError('Shell security prompt requires manual review; no warning dismissed')
            current=json.dumps(rows)
            if current!=fingerprint:
                fingerprint=current;save('wizard',rows)
                for window,row in zip(owned,rows):
                    text=' '.join(row['controls'])
                    if 'Mini Whiteboard is running' in text or 'must be closed' in text.lower():
                        report['result']='RUNNING APPLICATION REFUSAL'
                        save('running-refusal',rows)
                        for b in window.descendants(control_type='Button'):
                            if clean(b.window_text())=='OK': b.click_input();break
                        return 10
                    radios=[b for b in window.descendants(control_type='RadioButton')
                            if clean(b.window_text()).startswith('I accept') and b.is_visible()]
                    if radios:
                        radios[0].click_input()
                    buttons=[b for b in window.descendants(control_type='Button') if b.is_visible() and b.is_enabled()]
                    names={clean(b.window_text()):b for b in buttons}
                    if args.uninstall and 'Yes' in names and 'remove' in text.lower():
                        names['Yes'].click_input();break
                    if args.uninstall and 'OK' in names and 'successfully removed' in text.lower():
                        names['OK'].click_input();finish_clicked=True;break
                    if not args.uninstall:
                        action=next((n for n in ('Finish','Install','Next >') if n in names),None)
                        if action:
                            if action=='Finish': finish_clicked=True
                            names[action].click_input();break
            if finish_clicked and not owned and (not target.exists() if args.uninstall else target.exists()):
                report['result']='PASS';save('completed',[]);return 0
            time.sleep(.3)
        raise TimeoutError('Normal wizard did not complete within 65 seconds; last visible state retained')
    except Exception as error:
        report.update(result='BLOCKED OR FAILED',error=str(error));save('failure',[])
        return 2
    finally:
        report['ended_utc']=datetime.now(timezone.utc).isoformat()
        (args.output/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__':
    raise SystemExit(main())
