"""Opt-in native compositor/focus/popup/motion checks, never OS policy changes."""
import argparse
import ctypes as C
from ctypes import wintypes as W
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import time

os.environ['QT_QPA_PLATFORM'] = 'windows'
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from mini_whiteboard import windows
from mini_whiteboard.app import WhiteboardApplication
from mini_whiteboard.appearance import DisplayPolicy
from mini_whiteboard.document import Text, Stroke, Shape
from mini_whiteboard.geometry import Rect
from mini_whiteboard.snapping import SnapPreferences


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path('verification/v133-review01/material'))
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True,exist_ok=True)
    windows.enable_dpi_awareness()
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    guard = windows.SingleInstance()
    if not guard.acquired:
        raise RuntimeError('Exit Mini Whiteboard before this native check.')
    u = windows.user32
    foreground = windows.bind(u,'GetForegroundWindow',W.HWND)
    previous, cursor = foreground(), windows.cursor_position()
    at = windows.bind(u,'WindowFromPoint',W.HWND,W.POINT)
    ancestor = windows.bind(u,'GetAncestor',W.HWND,W.HWND,W.UINT)
    set_cursor = windows.bind(u,'SetCursorPos',W.BOOL,C.c_int,C.c_int)
    mouse = windows.bind(u,'mouse_event',None,W.DWORD,W.DWORD,W.DWORD,W.DWORD,C.c_size_t)
    key_event = windows.bind(u,'keybd_event',None,W.BYTE,W.BYTE,W.DWORD,C.c_size_t)
    pid_for = windows.bind(u,'GetWindowThreadProcessId',W.DWORD,W.HWND,C.POINTER(W.DWORD))
    send = windows.bind(u,'SendMessageW',C.c_ssize_t,W.HWND,W.UINT,W.WPARAM,W.LPARAM)
    flush = windows.bind(C.WinDLL('dwmapi'),'DwmFlush',C.c_long)
    is_window = windows.bind(u,'IsWindow',W.BOOL,W.HWND)
    resources_api = windows.bind(u,'GetGuiResources',W.DWORD,W.HANDLE,W.DWORD)
    process_handle = windows.bind(windows.kernel32,'GetCurrentProcess',W.HANDLE)()
    def resources():
        return tuple(resources_api(process_handle,kind) for kind in (0,1))
    controller = WhiteboardApplication(app,SnapPreferences())
    controller.notify = lambda text:None
    original_policy = controller.platform.desktop.display_policy
    system_policy = original_policy()
    reports, observations, errors = [], [], []
    old_hook = sys.excepthook
    sys.excepthook = lambda kind,value,tb:errors.append(repr(value))
    child = None
    background_handle = None
    def check(label, condition, detail=None):
        item = dict(check=label,status='PASS' if condition else 'FAIL',detail=detail)
        reports.append(item)
        print(json.dumps(item),flush=True)
        if not condition:
            raise AssertionError(label)
    def click(handle,x,y):
        set_cursor(round(x),round(y))
        QTest.qWait(30)
        if ancestor(at(W.POINT(round(x),round(y))),2) != handle:
            raise RuntimeError('Native input target is not the intended owned window.')
        mouse(2,0,0,0,0)
        QTest.qWait(30)
        mouse(4,0,0,0,0)
        QTest.qWait(100)
        if foreground()!=handle:
            u.SetForegroundWindow(handle)
            QTest.qWait(100)
        if foreground()!=handle:
            raise RuntimeError('Native focus was not established on the intended owned window.')
    def capture(name, wait=220):
        QTest.qWait(wait)
        paper=board.physical_paper_rect()
        target=at(W.POINT(round(paper.x+paper.width/2),round(paper.y+paper.height/2)))
        if ancestor(target,2)!=int(board.winId()):
            raise RuntimeError('The owned background occludes the board during '+name)
        flush()
        image = windows.capture_rect(region)
        image.save(str(output/(name+'.png')))
        return image
    sample_points = ((300,110),(850,110),(300,560),(850,650),(500,520))
    def samples(image):
        return [image.pixelColor(x,y).getRgb()[:3] for x,y in sample_points]
    def difference(a,b):
        return max(abs(x-y) for first,second in zip(a,b) for x,y in zip(first,second))
    def observe(name,image):
        host = getattr(board,'_backdrop',None)
        entry = dict(name=name,foreground=foreground(),board=int(board.winId()),
                     active=board.isActiveWindow(),host=host.handle if host else None,
                     samples=samples(image),system_policy=vars(system_policy))
        observations.append(entry)
        return entry['samples']
    def background(mode):
        send(background_handle,0x8001,('busy','light','dark').index(mode),0)
        QTest.qWait(90)
        flush()
    def key(code):
        owner=W.DWORD()
        pid_for(foreground(),C.byref(owner))
        if owner.value!=os.getpid():
            raise RuntimeError('Native key target is not the owned test application.')
        key_event(code,0,0,0)
        key_event(code,0,2,0)
        QTest.qWait(60)
    try:
        ready = output/'background-ready.json'
        if ready.exists():
            ready.unlink()
        child = subprocess.Popen([sys.executable,'-m','scripts.appearance_background','--ready',str(ready)],
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.monotonic()+6
        while not ready.exists() and child.poll() is None and time.monotonic()<deadline:
            QTest.qWait(20)
        if not ready.exists():
            raise RuntimeError('Owned background did not become ready.')
        info = json.loads(ready.read_text(encoding='utf-8'))
        background_handle = info['handle']
        region = Rect(**info['rect'])
        native_pid = W.DWORD()
        windows.bind(u,'GetWindowThreadProcessId',W.DWORD,W.HWND,C.POINTER(W.DWORD))(background_handle,C.byref(native_pid))
        check('Demonstration background belongs to a separate owned process',
              native_pid.value==info['pid'] and info['pid']!=os.getpid()
              and child.poll() is None and child.pid in (info['pid'],info['parent']))
        board = controller.create_board(Rect(region.x+35,region.y+70,990,660))
        canvas = board.canvas
        canvas.document.add(Text((65,135),'A little space for ideas.\nDraw. Type. Annotate.',size=25,layout_width=750))
        canvas.document.add(Stroke(((125,320),(100,355),(135,385),(220,380),(360,330),(530,257),(660,243),(720,266),(735,300)),3.5,color='#2467f5'))
        canvas.document.add(Shape('Rounded rectangle',(605,355),(805,480),3,color='#2467f5'))
        canvas.document.add(Shape('Arrow',(525,340),(585,395),3,color='#2467f5'))
        canvas.sync_selection()
        controller.preferences.set_theme('Glass')
        board.restore()
        QTest.qWait(100)
        click(int(board.winId()),region.x+440,region.y+73)
        check('Focused comparison has native foreground on the board',foreground()==int(board.winId()))
        busy = observe('focused',capture('focused-busy'))
        click(background_handle,region.x+1420,region.y+780)
        # Keep the independent application focused, with its surface behind the
        # board/shadow rather than occluding the comparison.
        u.SetWindowPos(background_handle,board._backdrop.handle,0,0,0,0,0x0013)
        check('Unfocused comparison leaves the board exposed above the owned background',
              ancestor(at(W.POINT(round(region.x+300),round(region.y+300))),2)==int(board.winId()))
        unfocused = observe('unfocused',capture('unfocused-busy'))
        check('External owned focus preserves the visible material',foreground()==background_handle and difference(busy,unfocused)<=2,
              {'max_rgb_delta':difference(busy,unfocused)})
        board.restore()
        QTest.qWait(100)
        click(int(board.winId()),region.x+440,region.y+73)
        check('Native board focus is reestablished before material comparisons',foreground()==int(board.winId()))
        reference={}
        for mode in ('busy','light','dark','busy'):
            fixed_focus = foreground()
            background(mode)
            image = capture('focused-'+mode)
            reference[mode] = observe('fixed-focus-'+mode,image)
            check('Background '+mode+' changes without a focus change',foreground()==fixed_focus)
        check('Backdrop visibly responds to independent background updates',
              difference(reference['light'],reference['dark'])>50 and difference(reference['busy'],reference['light'])>30)
        controller.rebuild_menu()
        appearance = next(a.menu() for a in controller.menu.actions() if a.text()=='Appearance')
        def open_surface(kind):
            if kind=='appearance':
                surface = appearance
                surface.popup(QPoint(round(region.x+1070),round(region.y+85)))
            elif kind=='palette':
                canvas.open_palette()
                surface = canvas.palette
                surface.move(round(region.x+1070),round(region.y+210))
            else:
                surface = canvas.make_context_menu((690,410))
                canvas.context_menu = surface
                surface.popup(QPoint(round(region.x+1070),round(region.y+85)))
            return surface
        for kind in ('appearance','palette','context'):
            surface = open_surface(kind)
            image = capture(kind+'-open')
            actual = observe(kind+'-open',image)
            check(kind+' opening keeps the settled board material',difference(actual,reference['busy'])<=2)
            for mode in ('dark','light','busy'):
                fixed_focus = foreground()
                background(mode)
                actual = observe(kind+'-background-'+mode,capture(kind+'-background-'+mode))
                check(kind+' stays coherent as the independent background becomes '+mode,
                      difference(actual,reference[mode])<=3 and foreground()==fixed_focus,
                      {'max_rgb_delta':difference(actual,reference[mode])})
            surface.close()
            actual = observe(kind+'-dismissed',capture(kind+'-dismissed'))
            check(kind+' dismissal releases its host and preserves material',
                  getattr(surface,'_backdrop',None) is None and difference(actual,reference['busy'])<=2)
        # The exact original failure path: a background change and popup entry
        # share one GUI turn. A long wait alone did not fix the previous host.
        background('dark')
        send(background_handle,0x8001,0,0)
        appearance.popup(QPoint(round(region.x+1070),round(region.y+85)))
        actual = observe('same-turn-change-and-popup',capture('same-turn-change-and-popup'))
        check('Same-turn background update and popup cannot retain the old grey material',difference(actual,reference['busy'])<=3)
        appearance.close()
        board.restore()
        QTest.qWait(120)
        click(int(board.winId()),region.x+440,region.y+73)
        appearance.popup(QPoint(round(region.x+1070),round(region.y+85)))
        appearance.setActiveAction(None)
        key(0x28)
        key(0x28)
        selected=appearance.activeAction()
        capture('appearance-keyboard-selected')
        check('Native menu keys focus the checked Glass action',
              selected is not None and selected.text()=='Glass' and selected.isChecked())
        key(0x1b)
        check('Native Escape dismisses the menu and releases its host',
              not appearance.isVisible() and getattr(appearance,'_backdrop',None) is None)
        canvas.setFocus()
        key(0x70)  # F1
        canvas.help_panel.move(round(region.right-canvas.help_panel.width()-12),round(region.y+50))
        capture('help-native-keyboard')
        check('Native F1 shows grouped help without changing foreground focus',
              canvas.help_panel.isVisible() and canvas.help_panel.columns==2 and foreground()==int(board.winId()))
        key(0x70)
        check('Native F1 dismisses help and stops its material',
              not canvas.help_panel.isVisible() and getattr(canvas.help_panel,'_backdrop',None) is None)
        canvas.set_selection(set())
        palette_before=canvas.document.objects,list(canvas.document.history)
        canvas.open_palette()
        key(ord('3'))
        check('Native palette number key chooses its colour without editing the document',
              canvas.palette is None and canvas.active_color=='#2878d0'
              and palette_before==(canvas.document.objects,canvas.document.history),
              {'palette_open':canvas.palette is not None,'active_colour':str(canvas.active_color),
               'history_length':len(canvas.document.history),'focus_type':type(app.focusWidget()).__name__})
        old_handle = int(board.winId())
        old_paper = board.physical_paper_rect()
        board.prepare_hide()
        board.hide()
        board.destroy()
        # This deliberately destructive QWidget probe needs explicit placement
        # again, just like a newly allocated board HWND.
        board.desktop.place_board(board,old_paper)
        board.restore()
        QTest.qWait(180)
        actual = observe('recreated',capture('recreated'))
        check('Native handle recreation recreates the rounded material on the new owner',
              int(board.winId())!=old_handle and not is_window(old_handle)
              and board._backdrop.owner==int(board.winId()) and difference(actual,reference['busy'])<=3,
              {'old_handle':old_handle,'new_handle':int(board.winId()),'old_still_valid':bool(is_window(old_handle)),
               'max_rgb_delta':difference(actual,reference['busy'])})
        for size in ((990,660),(160,100)):
            paper = Rect(region.x+35,region.y+70,*size)
            board.desktop.place_board(board,paper)
            QTest.qWait(120)
            host = board._backdrop
            bounds = W.RECT()
            u.GetWindowRect(host.handle,C.byref(bounds))
            check('Native material exactly aligns at '+str(size),
                  (bounds.left,bounds.top,bounds.right-bounds.left,bounds.bottom-bounds.top)==
                  (round(paper.x),round(paper.y),*size))
            visible = capture('geometry-'+str(size[0]))
            windows.bind(u,'ShowWindow',W.BOOL,W.HWND,C.c_int)(host.handle,0)
            without = capture('geometry-'+str(size[0])+'-without-host',80)
            from PySide6.QtCore import QPointF
            from PySide6.QtGui import QPainterPath
            path = QPainterPath()
            path.addRoundedRect(board.paper_rect(),board.corner_radius(),board.corner_radius())
            window = board.desktop.window_rect(board)
            leaks=[]
            probes=0
            for dx in range(0,33,2):
                for dy in range(0,33,2):
                    for x,y in ((paper.x+dx,paper.y+dy),(paper.right-dx-1,paper.y+dy),
                                (paper.x+dx,paper.bottom-dy-1),(paper.right-dx-1,paper.bottom-dy-1)):
                        local=QPointF(x+.5-window.x,y+.5-window.y)
                        if not path.contains(local):
                            probes+=1
                            px,py=round(x-region.x),round(y-region.y)
                            if visible.pixelColor(px,py)!=without.pixelColor(px,py):
                                leaks.append([px,py])
            check('Native backdrop contributes no pixels outside the rounded outline at '+str(size),not leaks,
                  {'outside_probes':probes,'leaks':leaks})
            host.sync(board)
        board.desktop.place_board(board,Rect(region.x+35,region.y+70,990,660))
        before = canvas.document.objects,list(canvas.document.history),board.physical_paper_rect()
        for policy,name in ((replace(system_policy,transparency=False),'transparency-off'),
                            (replace(system_policy,high_contrast=True),'high-contrast')):
            controller.platform.desktop.display_policy=lambda p=policy:p
            board.refresh_appearance()
            capture(name)
            check(name+' releases compositor and keeps content',not board.native_glass and getattr(board,'_backdrop',None) is None
                  and before==(canvas.document.objects,canvas.document.history,board.physical_paper_rect()))
        # The only policy injection is in this test process. Production still
        # reads Windows settings. Native frames and values identify the policy.
        for motion in (True,False):
            policy=replace(system_policy,motion=motion)
            controller.platform.desktop.display_policy=lambda p=policy:p
            paper=board.physical_paper_rect()
            board.hide()
            board.place(paper)
            for trigger in ('creation','restore','palette'):
                if trigger=='restore':
                    board.prepare_hide();board.hide();board.restore(activate=False)
                subject=board
                if trigger=='palette':
                    canvas.open_palette();subject=canvas.palette
                    subject.move(round(region.x+1070),round(region.y+210))
                prefix=('motion-injected' if motion else 'reduced-motion')+'-'+trigger
                started=time.monotonic()
                frames=[]
                images=[]
                for target in (0,35,70,110,180):
                    remaining=target-round((time.monotonic()-started)*1000)
                    if remaining>0:QTest.qWait(remaining)
                    app.processEvents()
                    # Acquire actual composed pixels now; defer PNG encoding
                    # until later so the evidence writer cannot consume the
                    # entire 140 ms presentation budget on the GUI thread.
                    observed=round((time.monotonic()-started)*1000,1)
                    value=subject.emphasis.value
                    images.append(windows.capture_rect(region))
                    frames.append(dict(target_ms=target,observed_ms=observed,
                                       capture_finished_ms=round((time.monotonic()-started)*1000,1),
                                       emphasis=value,deadline=subject.emphasis.deadline.isActive()))
                for target,image in zip((0,35,70,110,180),images):
                    image.save(str(output/(prefix+'-'+str(target)+'.png')))
                observations.append(dict(name=prefix,injected_policy=vars(policy),system_policy=vars(system_policy),frames=frames))
                check(prefix+' is bounded and respects policy',not subject.emphasis.deadline.isActive()
                      and subject.emphasis.value==0 and (any(f['emphasis']>0 for f in frames) if motion else all(f['emphasis']==0 for f in frames)),frames)
                if trigger=='palette':subject.close()
        controller.platform.desktop.display_policy=original_policy
        board.refresh_appearance()
        initial=None
        for index in range(36):
            for kind in ('appearance','palette','context'):
                popup=open_surface(kind)
                popup.close()
            controller.preferences.set_theme('White')
            controller.preferences.set_theme('Glass')
            controller.toggle_visibility()
            if getattr(board,'_backdrop',None) is not None:
                raise AssertionError('Hidden board retains a native host')
            controller.toggle_visibility()
            QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
            app.processEvents()
            if index==5:initial=resources()
        QTest.qWait(200)
        final=resources()
        check('Repeated menu/theme/hide cycles have stable GDI/User resources',
              all(b<=a+4 for a,b in zip(initial,final)),{'after_warmup':initial,'final':final})
        check('All transient animation and activation timers stop at idle',
              not board.activation_timer.isActive() and not board.emphasis.deadline.isActive()
              and all(not widget.emphasis.deadline.isActive() for widget in app.topLevelWidgets() if hasattr(widget,'emphasis')))
        check('Native material work preserves document, history and geometry',
              before==(canvas.document.objects,canvas.document.history,board.physical_paper_rect()) and not errors,errors)
        shadow_handle=int(board._shadow.winId())
        controller.cleanup()
        app.processEvents()
        title=windows.bind(u,'GetWindowTextW',C.c_int,W.HWND,W.LPWSTR,C.c_int)
        pid=windows.bind(u,'GetWindowThreadProcessId',W.DWORD,W.HWND,C.POINTER(W.DWORD))
        enum_type=C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
        orphan=[]
        @enum_type
        def visit(handle,data):
            owner=W.DWORD();pid(handle,C.byref(owner))
            text=C.create_unicode_buffer(160);title(handle,text,160)
            if owner.value==os.getpid() and text.value=='Mini Whiteboard glass backdrop':
                orphan.append(text.value)
            return True
        windows.bind(u,'EnumWindows',W.BOOL,enum_type,W.LPARAM)(visit,0)
        visible=windows.bind(u,'IsWindowVisible',W.BOOL,W.HWND)
        check('Cleanup destroys backdrop hosts and leaves owned shadows hidden',
              not orphan and not visible(shadow_handle),{'orphan_hosts':orphan,'shadow_visible':bool(visible(shadow_handle))})
        QTimer.singleShot(0,app.quit)
        app.exec()
        check('Normal Qt exit shuts down the compositor dispatcher without callback errors',not errors,errors)
    finally:
        controller.platform.desktop.display_policy=original_policy
        controller.cleanup()
        if background_handle and is_window(background_handle):
            send(background_handle,0x8002,0,0)
        if child is not None:
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:child.terminate();child.wait(timeout=5)
        mouse(4,0,0,0,0)
        set_cursor(*cursor)
        if previous:u.SetForegroundWindow(previous)
        guard.close()
        sys.excepthook=old_hook
        (output/'checks.json').write_text(json.dumps({'checks':reports,'observations':observations,'errors':errors},indent=2)+'\n',encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
