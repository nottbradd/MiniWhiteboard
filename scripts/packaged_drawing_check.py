"""Native injected-mouse observations of an unchanged frozen app on a hosted VM.

WM_NULL responses measure GUI-thread liveness, not display/pen latency. Samples
and images are retained. The app is exited and settings restored after each run.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import threading
import time


def main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
        raise SystemExit('Requires an isolated GitHub-hosted Windows desktop.')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--toolbar',action='store_true')
    parser.add_argument('--expected-sha',required=True)
    args = parser.parse_args()
    executable = args.executable.resolve(strict=True)
    digest = hashlib.sha256(executable.read_bytes()).hexdigest()
    if digest!=args.expected_sha:
        raise ValueError('Executable identity mismatch')
    os.environ['QT_QPA_PLATFORM']='windows'
    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QGuiApplication
    from mini_whiteboard import windows as n
    from mini_whiteboard.hotkey_config import defaults
    from scripts.native_preferences import compatibility_preferences
    from scripts.drawing_performance import stats
    n.enable_dpi_awareness()
    app = QGuiApplication([])
    args.output.mkdir(parents=True,exist_ok=True)
    report = dict(exe_sha256=digest,toolbar=args.toolbar,scope='Unchanged frozen app; injected native mouse and GUI-thread WM_NULL probes, not physical pen/display latency',
                  nominal_input_hz=240,checks=[],workloads=[],real_pen='NOT RUN')
    def save():
        (args.output/'checks.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    def check(label,condition,detail=None):
        report['checks'].append(dict(check=label,status='PASS' if condition else 'FAIL',detail=detail))
        save()
        if not condition:
            raise AssertionError(label)
    u = n.user32
    pid_for = n.bind(u,'GetWindowThreadProcessId',W.DWORD,W.HWND,C.POINTER(W.DWORD))
    title = n.bind(u,'GetWindowTextW',C.c_int,W.HWND,W.LPWSTR,C.c_int)
    visible = n.bind(u,'IsWindowVisible',W.BOOL,W.HWND)
    get_rect = n.bind(u,'GetWindowRect',W.BOOL,W.HWND,C.POINTER(W.RECT))
    enum_type = C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
    enum = n.bind(u,'EnumWindows',W.BOOL,enum_type,W.LPARAM)
    move = n.bind(u,'SetCursorPos',W.BOOL,C.c_int,C.c_int)
    key = n.bind(u,'keybd_event',None,W.BYTE,W.BYTE,W.DWORD,C.c_size_t)
    mouse = n.bind(u,'mouse_event',None,W.DWORD,W.DWORD,W.DWORD,W.DWORD,C.c_size_t)
    foreground = n.bind(u,'GetForegroundWindow',W.HWND)
    ping = n.bind(u,'SendMessageTimeoutW',C.c_size_t,W.HWND,W.UINT,W.WPARAM,W.LPARAM,W.UINT,W.UINT,C.POINTER(C.c_size_t))
    stop = threading.Event()
    process = None
    held = set()
    samples = []
    def press(vk):
        key(vk,0,0,0);held.add(vk)
    def release(vk):
        key(vk,0,2,0);held.discard(vk)
    def windows():
        result = {}
        @enum_type
        def visit(hwnd,_):
            pid=W.DWORD();pid_for(hwnd,C.byref(pid))
            if pid.value==process.pid and visible(hwnd):
                text=C.create_unicode_buffer(256);title(hwnd,text,256)
                r=W.RECT()
                if get_rect(hwnd,C.byref(r)):
                    result[text.value]=(hwnd,(r.left,r.top,r.right-r.left,r.bottom-r.top))
            return True
        enum(visit,0)
        return result
    def wait_for(label,predicate,seconds=3):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            if predicate():
                check(label,True);return
            app.processEvents();time.sleep(.02)
        check(label,False,windows())
    def tap(x,y):
        move(round(x),round(y));mouse(2,0,0,0,0);time.sleep(.04);mouse(4,0,0,0,0)
    preferences = QSettings('MiniWhiteboard','MiniWhiteboard')
    had=preferences.contains('tools/floating');old=preferences.value('tools/floating')
    try:
        with compatibility_preferences(defaults(hide='shift')):
            preferences.setValue('tools/floating',args.toolbar);preferences.sync()
            process=subprocess.Popen([str(executable)],creationflags=subprocess.CREATE_NO_WINDOW)
            time.sleep(1.8)
            check('Frozen process stays alive at startup',process.poll() is None)
            move(180,210)
            for vk in (0xA2,0x5B,0xA0,0x57):press(vk)
            time.sleep(.15);move(1050,760);time.sleep(.1)
            for vk in (0x57,0xA0,0x5B,0xA2):release(vk)
            wait_for('Native default shortcut creates a board',lambda:'Whiteboard 1' in windows())
            hwnd,rect=windows()['Whiteboard 1']
            if args.toolbar:
                wait_for('Frozen optional toolbar is visible',lambda:'Mini Whiteboard floating tools' in windows())
                check('Toolbar show does not take foreground',foreground()==hwnd)
                _,tr=windows()['Mini Whiteboard floating tools'];scale=tr[2]/375
                def tool(index):
                    tap(tr[0]+(28+42*index+(7 if index>=5 else 0)+21)*scale,tr[1]+23*scale)
                tool(1);tool(0)
                check('Tool taps leave the board foreground',foreground()==hwnd)
                move(round(tr[0]+49*scale),round(tr[1]+23*scale));mouse(2,0,0,0,0);time.sleep(1)
                wait_for('Frozen long-press options are visible',lambda:'Mini Whiteboard Draw options' in windows())
                mouse(4,0,0,0,0);time.sleep(.1)
                check('Frozen long-press release preserves options','Mini Whiteboard Draw options' in windows())
                n.capture_rect(n.monitors()[0].rect).save(str(args.output/'frozen-options.png'))
                tap(rect[0]+100,rect[1]+100)
                # Closing a tool window must never produce a second drawing event.
            else:
                check('Default-off has no toolbar','Mini Whiteboard floating tools' not in windows())
            tap(rect[0]+120,rect[1]+120)
            press(0x44);release(0x44)
            def monitor():
                while not stop.wait(.016):
                    result=C.c_size_t();start=time.perf_counter()
                    ok=ping(hwnd,0,0,0,2,500,C.byref(result))
                    samples.append(((time.perf_counter()-start)*1000,bool(ok)))
            thread=threading.Thread(target=monitor,daemon=True);thread.start()
            for stroke_count,points in ((1,1920),(30,24)):
                start=time.perf_counter();sent=0
                for stroke in range(stroke_count):
                    move(rect[0]+70,rect[1]+250);mouse(2,0,0,0,0)
                    for i in range(points):
                        move(round(rect[0]+70+(i*.65)%650),round(rect[1]+250+90*math.sin(i*.03)))
                        sent+=1;time.sleep(1/240)
                    mouse(4,0,0,0,0)
                report['workloads'].append(dict(strokes=stroke_count,sent_points=sent,seconds=time.perf_counter()-start))
                save()
            stop.set();thread.join(1)
            report['liveness']=stats([ms for ms,_ in samples])
            report['probe_timeouts']=sum(not ok for _,ok in samples)
            report['stalls_over_100ms']=sum(ms>100 for ms,_ in samples)
            report['samples_ms']=samples
            check('Frozen app remains responsive after sustained injected drawing',process.poll() is None and ping(hwnd,0,0,0,2,2000,C.byref(C.c_size_t()))!=0)
            n.capture_rect(n.monitors()[0].rect).save(str(args.output/'frozen-drawing.png'))
    finally:
        stop.set()
        mouse(4,0,0,0,0)
        for vk in tuple(held):release(vk)
        if process is not None and process.poll() is None:
            process.terminate();process.wait(10)
        preferences.setValue('tools/floating',old) if had else preferences.remove('tools/floating')
        preferences.sync();save()


if __name__=='__main__':
    main()
