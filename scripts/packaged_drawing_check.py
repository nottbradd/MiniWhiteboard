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
import sys
import threading
import time
from datetime import datetime, timezone


def main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
        raise SystemExit('Requires an isolated GitHub-hosted Windows desktop.')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--toolbar',action='store_true')
    parser.add_argument('--expected-sha',required=True)
    parser.add_argument('--visual-only',action='store_true')
    parser.add_argument('--comparison',action='store_true',help='Capture identical empty artwork and native host state, without toolbar editing.')
    parser.add_argument('--theme',choices=('White','Glass'),default='White')
    parser.add_argument('--background',choices=('light','busy'),default='light')
    args = parser.parse_args()
    if args.comparison and not args.visual_only:
        parser.error('--comparison requires --visual-only')
    if args.visual_only:
        # Qt's GUI thread uses STA. Initialize the UIA client in that apartment
        # before Qt, instead of importing pywinauto during a live popup.
        sys.coinit_flags=2
        from pywinauto import Desktop
        from scripts.client_environment_check import dismiss_wsl_prompt
        dismiss_wsl_prompt()
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
    report = dict(exe_sha256=digest,toolbar=args.toolbar,started_utc=datetime.now(timezone.utc).isoformat(),scope='Unchanged frozen app; injected native mouse and GUI-thread WM_NULL probes, not physical pen/display latency',
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
    background_process = None
    held = set()
    samples = []
    def capture_state(label):
        from scripts.client_glass_diagnostics import window_state
        shot=n.capture_rect(n.monitors()[0].rect)
        shot.save(str(args.output/(label+'.png')))
        points=((280,300),(420,300),(650,450))
        report.setdefault('observations',[]).append(dict(label=label,**window_state(process.pid),
            points=points,pixels=[shot.pixelColor(x,y).getRgb() for x,y in points]))
        save()
    def press(vk):
        key(vk,0,0,0);held.add(vk)
    def release(vk):
        key(vk,0,2,0);held.discard(vk)
    def windows(include_hidden=False):
        result = {}
        @enum_type
        def visit(hwnd,_):
            pid=W.DWORD();pid_for(hwnd,C.byref(pid))
            if pid.value==process.pid and (include_hidden or visible(hwnd)):
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
    def uia_control(handle,name,action):
        destination=args.output/('uia-'+str(len(report.setdefault('uia',[])))+'.json')
        result=subprocess.run([sys.executable,'-m','scripts.client_uia_check','--handle',str(handle),
            '--pid',str(process.pid),'--name',name,'--action',action,'--output',str(destination)],
            capture_output=True,text=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
        report['uia'].append(dict(file=destination.name,exit_code=result.returncode,stderr=result.stderr))
        save()
        if result.returncode:raise RuntimeError('Separate UIA query failed; see '+destination.name)
        return json.loads(destination.read_text())
    preferences = QSettings('MiniWhiteboard','MiniWhiteboard')
    had=preferences.contains('tools/floating');old=preferences.value('tools/floating')
    try:
        with compatibility_preferences(defaults(hide='shift')):
            if args.visual_only:
                background_process=subprocess.Popen([sys.executable,'-m','scripts.floating_tools_check','--native',
                    '--background-child','--background-kind',args.background,'--output',str(args.output/'background')],
                    creationflags=subprocess.CREATE_NO_WINDOW)
                from scripts.client_glass_diagnostics import wait_visible_window
                report['background_readiness']=wait_visible_window(background_process.pid,app.processEvents,background_kind=args.background)
                preferences.setValue('appearance/theme',args.theme)
                report.update(scope='Exact frozen executable visual/toolbar checks on an owned background',theme=args.theme,background=args.background)
                n.capture_rect(n.monitors()[0].rect).save(str(args.output/'background-before-app.png'))
            preferences.setValue('tools/floating',args.toolbar);preferences.sync()
            process=subprocess.Popen([str(executable)],creationflags=subprocess.CREATE_NO_WINDOW)
            startup=time.monotonic()
            # A fixed 1.8 s sleep raced the first emulated cold launch. Wait
            # for its real tray message window and a serviced GUI message;
            # this changes test readiness, never the shortcut assertion.
            def ready():
                tray=windows(include_hidden=True).get('QTrayIconMessageWindow')
                value=C.c_size_t()
                return bool(tray and ping(tray[0],0,0,0,2,100,C.byref(value)))
            wait_for('Frozen tray GUI is ready before input',ready,seconds=8)
            report['startup_ready_ms']=(time.monotonic()-startup)*1000
            capture_state('startup-ready')
            check('Frozen process stays alive at startup',process.poll() is None)
            move(180,210)
            for vk in (0xA2,0x5B,0xA0,0x57):press(vk)
            m=n.monitors()[0].rect
            end=(min(1050,int(m.x+m.width-55)),min(760,int(m.y+m.height-100))) if args.visual_only else (1050,760)
            time.sleep(.15);move(*end);time.sleep(.1)
            for vk in (0x57,0xA0,0x5B,0xA2):release(vk)
            wait_for('Native default shortcut creates a board',lambda:'Whiteboard 1' in windows())
            hwnd,rect=windows()['Whiteboard 1']
            if args.comparison:
                report['placement']=rect
                capture_state('board-initial')
                time.sleep(.8)
                capture_state('board-settled')
                check('Comparison text targets the owned board',foreground()==hwnd)
                press(0x54);release(0x54);time.sleep(.08)
                tap(rect[0]+120,rect[1]+110);time.sleep(.2)
                for character in 'GLASS TEST':
                    press(ord(character));release(ord(character));time.sleep(.04)
                press(0x11);press(0x0D);release(0x0D);release(0x11)
                time.sleep(.2);press(0x1B);release(0x1B);time.sleep(.2)
                capture_state('board-text-readability')
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
                if args.comparison:
                    capture_state('board-toolbar-popover')
                    time.sleep(.8)
                    capture_state('board-toolbar-popover-settled')
                    return
                if args.visual_only:
                    options_hwnd=windows()['Mini Whiteboard Draw options'][0]
                    uia_control(options_hwnd,'White','click')
                    time.sleep(.35)
                    check('White choice keeps its options visible','Mini Whiteboard Draw options' in windows())
                    n.capture_rect(n.monitors()[0].rect).save(str(args.output/'frozen-white-selected.png'))
                    tap(rect[0]+100,rect[1]+100)
                    before=windows()['Mini Whiteboard floating tools'][1]
                    gx,gy=before[0]+16*scale,before[1]+23*scale
                    move(round(gx),round(gy));mouse(2,0,0,0,0)
                    for i in range(1,7):
                        move(round(gx-40*i/6),round(gy+50*i/6));time.sleep(.03)
                    mouse(4,0,0,0,0);time.sleep(.2)
                    after=windows()['Mini Whiteboard floating tools'][1]
                    check('Frozen toolbar grip changes tool position without moving the board',
                          after[:2]!=before[:2] and windows()['Whiteboard 1'][1]==rect)
                    n.capture_rect(n.monitors()[0].rect).save(str(args.output/'frozen-dragged.png'))
                    # Read the real frozen widget's accessibility state. A tool
                    # click and a second board must use the same canvas state.
                    def checked_tool(name):
                        return uia_control(windows()['Mini Whiteboard floating tools'][0],name,'state')['checked']
                    tap(after[0]+91*scale,after[1]+23*scale)
                    wait_for('First board retains Eraser as the selected tool',lambda:checked_tool('Eraser'))
                    move(380,310)
                    for vk in (0xA2,0x5B,0xA0,0x57):press(vk)
                    time.sleep(.15);move(min(880,int(m.x+m.width-90)),min(610,int(m.y+m.height-120)));time.sleep(.1)
                    for vk in (0x57,0xA0,0x5B,0xA2):release(vk)
                    wait_for('Second board is created independently',lambda:'Whiteboard 2' in windows())
                    wait_for('Second board toolbar starts with Draw',lambda:checked_tool('Draw'))
                    tap(rect[0]+65,rect[1]+16)
                    wait_for('Switching back restores the first board tool',lambda:foreground()==hwnd and checked_tool('Eraser'))
                    check('Switching boards preserves the first board toolbar position',windows()['Mini Whiteboard floating tools'][1]==after)
                    n.capture_rect(n.monitors()[0].rect).save(str(args.output/'frozen-board-switch.png'))
                    return
                tap(rect[0]+100,rect[1]+100)
                # Closing a tool window must never produce a second drawing event.
            else:
                check('Default-off has no toolbar','Mini Whiteboard floating tools' not in windows())
                if args.comparison:
                    return
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
    except Exception as error:
        from scripts.client_wizard_check import native_windows
        report['failure']=dict(error=repr(error),foreground=foreground(),windows=native_windows())
        save()
        n.capture_rect(n.monitors()[0].rect).save(str(args.output/'failure.png'))
        raise
    finally:
        stop.set()
        mouse(4,0,0,0,0)
        for vk in tuple(held):release(vk)
        if process is not None and process.poll() is None:
            process.terminate();process.wait(10)
        if args.comparison and process is not None:
            from scripts.client_glass_diagnostics import window_state
            report['after_owned_process_exit']=window_state(process.pid)
        if background_process is not None and background_process.poll() is None:
            background_process.terminate();background_process.wait(5)
        preferences.setValue('tools/floating',old) if had else preferences.remove('tools/floating')
        report['ended_utc']=datetime.now(timezone.utc).isoformat()
        preferences.sync();save()


if __name__=='__main__':
    main()
