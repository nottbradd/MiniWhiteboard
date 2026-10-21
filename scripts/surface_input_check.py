"""Native Windows alpha edges/previews and clicks into a separate owned process."""
import argparse
import ctypes as C
from ctypes import wintypes as W
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

os.environ['QT_QPA_PLATFORM']='windows'
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QImage, QPainterPath
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from mini_whiteboard import windows as n
from mini_whiteboard.app import WhiteboardApplication
from mini_whiteboard.geometry import Rect, normalized
from mini_whiteboard.snapping import SnapPreferences


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    output=args.output
    output.mkdir(parents=True,exist_ok=True)
    n.enable_dpi_awareness()
    app=QApplication([])
    app.setQuitOnLastWindowClosed(False)
    guard=n.SingleInstance()
    if not guard.acquired:raise RuntimeError('Exit Mini Whiteboard before the native check.')
    u=n.user32
    foreground=n.bind(u,'GetForegroundWindow',W.HWND)
    previous,cursor=foreground(),n.cursor_position()
    send=n.bind(u,'SendMessageW',C.c_ssize_t,W.HWND,W.UINT,W.WPARAM,W.LPARAM)
    set_cursor=n.bind(u,'SetCursorPos',W.BOOL,C.c_int,C.c_int)
    mouse=n.bind(u,'mouse_event',None,W.DWORD,W.DWORD,W.DWORD,W.DWORD,C.c_size_t)
    class MouseInput(C.Structure):
        _fields_=[('dx',W.LONG),('dy',W.LONG),('data',W.DWORD),('flags',W.DWORD),('time',W.DWORD),('extra',C.c_size_t)]
    class Payload(C.Union):
        _fields_=[('mouse',MouseInput)]
    class Input(C.Structure):
        _fields_=[('kind',W.DWORD),('payload',Payload)]
    send_input=n.bind(u,'SendInput',W.UINT,W.UINT,C.POINTER(Input),C.c_int)
    def external_click(x,y):
        metrics=n.bind(u,'GetSystemMetrics',C.c_int,C.c_int)
        sx,sy,sw,sh=[metrics(i) for i in (76,77,78,79)]
        dx,dy=round((x-sx)*65535/(sw-1)),round((y-sy)*65535/(sh-1))
        batch=(Input*3)(Input(0,Payload(MouseInput(dx,dy,0,0xC001,0,0))),
                        Input(0,Payload(MouseInput(0,0,0,2,0,0))),
                        Input(0,Payload(MouseInput(0,0,0,4,0,0))))
        if send_input(3,batch,C.sizeof(Input))!=3:raise C.WinError(C.get_last_error())
    at=n.bind(u,'WindowFromPoint',W.HWND,W.POINT)
    ancestor=n.bind(u,'GetAncestor',W.HWND,W.HWND,W.UINT)
    pid_for=n.bind(u,'GetWindowThreadProcessId',W.DWORD,W.HWND,C.POINTER(W.DWORD))
    flush=n.bind(C.WinDLL('dwmapi'),'DwmFlush',C.c_long)
    reports,measurements,errors=[],[],[]
    old_hook=sys.excepthook
    sys.excepthook=lambda kind,value,tb:errors.append(repr(value))
    child=controller=None
    background=None
    def check(label,condition,detail=None):
        row={'check':label,'status':'PASS' if condition else 'FAIL','detail':detail}
        reports.append(row)
        print(json.dumps(row),flush=True)
        if not condition:raise AssertionError(label)
    def lower_background():
        host=getattr(board,'_backdrop',None)
        below=host.handle if host is not None else int(board.winId())
        u.SetWindowPos(background,below,0,0,0,0,0x0013)
    def exposed():
        rect=board.physical_paper_rect()
        return ancestor(at(W.POINT(round(rect.x+rect.width/2),round(rect.y+rect.height/2))),2)==int(board.winId())
    def wait_for(predicate, milliseconds=500):
        deadline=time.monotonic()+milliseconds/1000
        while not predicate() and time.monotonic()<deadline:QTest.qWait(5)
        return bool(predicate())
    def focus_board():
        board.restore()
        wait_for(lambda:foreground()==int(board.winId()),150)
        if foreground()!=int(board.winId()):
            rect=board.physical_paper_rect()
            x,y=round(rect.x+rect.width/2),round(rect.y+4*scale)
            set_cursor(x,y);QTest.qWait(50)
            if ancestor(at(W.POINT(x,y)),2)!=int(board.winId()):raise RuntimeError('Unsafe activation target')
            mouse(2,0,0,0,0);QTest.qWait(30);mouse(4,0,0,0,0)
        check('Native foreground is the owned board before control input',wait_for(lambda:foreground()==int(board.winId())))
    def capture(name):
        QTest.qWait(100)
        lower_background()
        check(name+' has an exposed board',exposed())
        flush()
        bounds=board.desktop.window_rect(board)
        image=n.capture_rect(bounds)
        image.save(str(output/(name+'.png')))
        paper=board.physical_paper_rect()
        size=math.ceil(40*scale)
        inset=round(8*scale)
        for corner,x,y in [('tl',inset-3,inset-3),('tr',image.width()-inset-size+3,inset-3),
                           ('bl',inset-3,image.height()-inset-size+3),
                           ('br',image.width()-inset-size+3,image.height()-inset-size+3)]:
            crop=image.copy(x,y,size,size)
            crop.save(str(output/(name+'-'+corner+'.png')))
            crop.scaled(crop.width()*6,crop.height()*6,Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.FastTransformation).save(str(output/(name+'-'+corner+'-6x.png')))
        for button,label in ((board.minus,'minimise'),(board.remove,'close')):
            r=button.geometry()
            crop=image.copy(round(r.x()*scale)-3,round(r.y()*scale)-3,
                            round(r.width()*scale)+6,round(r.height()*scale)+6)
            crop.save(str(output/(name+'-'+label+'.png')))
        return image
    try:
        ready=output/'background-ready.json'
        if ready.exists():ready.unlink()
        child=subprocess.Popen([sys.executable,'-m','scripts.appearance_background','--ready',str(ready)],
                               creationflags=subprocess.CREATE_NO_WINDOW)
        start=time.monotonic()
        while not ready.exists() and child.poll() is None and time.monotonic()-start<6:QTest.qWait(20)
        info=json.loads(ready.read_text(encoding='utf-8'))
        background=info['handle']
        owner=W.DWORD();pid_for(background,C.byref(owner))
        check('Input recipient is a separately owned process',owner.value==info['pid']!=os.getpid()
              and child.pid in (info['pid'],info['parent']) and child.poll() is None)
        region=Rect(**info['rect'])
        controller=WhiteboardApplication(app,SnapPreferences())
        controller.notify=lambda text:None
        scale=app.primaryScreen().devicePixelRatio()
        board=controller.create_board(Rect(region.x+45,region.y+65,round(620*scale),round(350*scale)))
        scale=board.devicePixelRatioF()
        measurements.append({'qt_scale':scale,'native_dpi':u.GetDpiForWindow(int(board.winId())),
                             'screen':vars(n.monitors()[0].rect),'system_policy':vars(board.display_policy)})
        for theme in ('White','Glass'):
            controller.preferences.set_theme(theme)
            for size,width,height in [('normal',620,350),('minimum',160,100)]:
                board.desktop.set_window_rect(board,Rect(region.x+45,region.y+65,
                    round((width+16)*scale),round((height+16)*scale)))
                focus_board();QTest.qWait(80);lower_background()
                paper=board.physical_paper_rect()
                check(theme+' '+size+' keeps both full control rectangles inside the paper',all(
                    board.edges_at(QPointF(button.x()+button.width()/2,button.y()+button.height()/2))==Qt.Edge(0)
                    for button in (board.minus,board.remove)))
                for mode,index in [('light',1),('dark',2),('busy',0)]:
                    send(background,0x8001,index,0)
                    native_image=capture(theme.lower()+'-'+size+'-'+mode)
                    if mode=='dark':
                        qt=board.grab().toImage()
                        fringe=[]
                        pad=round(8*scale)
                        radius=round(board.corner_radius()*scale)
                        for x0,y0 in [(pad,pad),(qt.width()-pad-radius,pad),
                                      (pad,qt.height()-pad-radius),(qt.width()-pad-radius,qt.height()-pad-radius)]:
                            fringe.append(sum(0<qt.pixelColor(x,y).alpha()<240
                                for y in range(y0,y0+radius) for x in range(x0,x0+radius)))
                        check(theme+' '+size+' retains fractional edge coverage in all four corners',all(c>8 for c in fringe),fringe)
                        if theme=='White':
                            differences=[]
                            bg=(32,43,70)
                            for x in range(pad,pad+radius):
                                for y in range(pad,pad+radius):
                                    c=qt.pixelColor(x,y);alpha=c.alpha()/255
                                    if 20<c.alpha()<235:
                                        expected=[round(v*alpha+b*(1-alpha)) for v,b in zip(c.getRgb()[:3],bg)]
                                        actual=native_image.pixelColor(x,y).getRgb()[:3]
                                        differences.append(max(abs(a-b) for a,b in zip(expected,actual)))
                            check(size+' visible native alpha fringe matches the Qt edge',bool(differences) and max(differences)<=9,
                                  {'samples':len(differences),'max_channel_error':max(differences,default=0)})
                # Real mouse input, checked after each delivery. Lower the
                # background again so focusing it cannot conceal later probes.
                external=[]
                probes=[]
                near=max(0,math.floor(board.corner_radius()*scale*(1-1/math.sqrt(2)))-1)
                points=[(paper.x+1,paper.y+1),(paper.right-2,paper.y+1),
                            (paper.x+1,paper.bottom-2),(paper.right-2,paper.bottom-2),
                            (paper.x-4,paper.y+paper.height/2),(paper.right+4,paper.y+paper.height/2),
                            (paper.x+near,paper.y+near),(paper.right-near-1,paper.y+near),
                            (paper.x+near,paper.bottom-near-1),(paper.right-near-1,paper.bottom-near-1)]
                qt=board.grab().toImage();window=board.desktop.window_rect(board)
                check('Near-arc input probes have zero painted alpha',all(
                    qt.pixelColor(round(x-window.x),round(y-window.y)).alpha()==0 for x,y in points[-4:]))
                for x,y in points:
                    lower_background()
                    check('Board stays exposed before an external corner/margin click',exposed())
                    before=send(background,0x8003,0,0)
                    set_cursor(round(x),round(y));QTest.qWait(20)
                    target=at(W.POINT(round(x),round(y)))
                    styles=n.bind(u,'GetWindowLongPtrW',C.c_ssize_t,W.HWND,C.c_int)
                    probes.append({'point':[x,y],'target':target,'root':ancestor(target,2),
                        'board':int(board.winId()),'background':background,'foreground':foreground(),
                        'shadow':int(board._shadow.winId()),'board_ex':styles(int(board.winId()),-20),
                        'shadow_ex':styles(int(board._shadow.winId()),-20)})
                    external_click(round(x),round(y));QTest.qWait(45)
                    wait_for(lambda:send(background,0x8003,0,0)>before)
                    external.append(send(background,0x8003,0,0)-before)
                    lower_background()
                check(theme+' '+size+' forwards every outside click to the separate process',external==[1]*len(points),
                      {'delivered':external,'probes':probes})
                check(theme+' '+size+' outside clicks leave document history empty',not board.canvas.document.history)
                focus_board();QTest.qWait(50)
                for button,label in ((board.minus,'minimise'),(board.remove,'close')):
                    bounds=board.desktop.window_rect(board)
                    x=round(bounds.x+(button.x()+button.width()/2)*scale)
                    y=round(bounds.y+(button.y()+button.height()/2)*scale)
                    set_cursor(x,y);QTest.qWait(60)
                    check(theme+' '+size+' '+label+' native hit target belongs to the board',
                          ancestor(at(W.POINT(x,y)),2)==int(board.winId()))
                    capture(theme.lower()+'-'+size+'-'+label+'-hover')
                    mouse(2,0,0,0,0);QTest.qWait(40)
                    check(label+' has native pressed feedback',wait_for(button.isDown),
                          {'under_mouse':button.underMouse(),'foreground':foreground(),'board':int(board.winId()),
                           'cursor':n.cursor_position(),'button_geometry':button.geometry().getRect()})
                    capture(theme.lower()+'-'+size+'-'+label+'-pressed')
                    set_cursor(round(paper.x+paper.width/2),round(paper.y+paper.height/2))
                    mouse(4,0,0,0,0);QTest.qWait(40)
                    check(label+' drag-out cancels the action',board.isVisible() and not board._closing)
        board.minimize_to_tray()
        controller.preferences.set_theme('White')
        captured=[]
        controller.capture.captured.connect(lambda rect,image:captured.append((rect,image)))
        for kind in ('board','screenshot'):
            for index,(dx,dy) in enumerate(((340,200),(-340,200),(340,-200),(-340,-200))):
                anchor=(round(region.x+760),round(region.y+420))
                end=(anchor[0]+dx,anchor[1]+dy)
                rect=normalized(anchor,end)
                send(background,0x8001,0,0);QTest.qWait(80);flush()
                clean=n.capture_rect(rect)
                set_cursor(*anchor)
                before_boards=set(controller.boards)
                if kind=='board':controller.placement.start_at(anchor)
                else:controller.capture.start()
                set_cursor(*end)
                owner=controller.placement if kind=='board' else controller.capture
                owner.track();QTest.qWait(60)
                active=owner.overlays
                check(kind+' preview has material and does not activate',bool(active)
                      and not any(o.isActiveWindow() for o in active))
                n.capture_rect(region).save(str(output/(kind+'-preview-'+str(index)+'.png')))
                preview=n.capture_rect(rect)
                check(kind+' preview visibly changes the selection',preview!=clean)
                if kind=='board':controller.placement.release()
                else:controller.capture.release()
                start=time.monotonic()
                while set(controller.boards)==before_boards and time.monotonic()-start<5:QTest.qWait(10)
                created=set(controller.boards)-before_boards
                check(kind+' direction '+str(index)+' makes exactly one result',len(created)==1)
                result=created.pop()
                actual=captured[-1][0] if kind=='screenshot' else result.physical_paper_rect()
                check(kind+' retains exact selected coordinates',actual==rect,
                      {'wanted':vars(rect),'actual':vars(actual)})
                check(kind+' glass preview preserves the default White board',result.appearance_theme=='White')
                if kind=='screenshot':
                    from mini_whiteboard.images import decoded
                    obj=result.canvas.document.objects[0]
                    original=decoded(obj.png)
                    check('Screenshot contains only original screen pixels',original.convertToFormat(QImage.Format.Format_ARGB32)==clean.convertToFormat(QImage.Format.Format_ARGB32),
                          {'width':original.width(),'height':original.height()})
                    original.save(str(output/('screenshot-original-'+str(index)+'.png')))
                    clean.save(str(output/('screenshot-reference-'+str(index)+'.png')))
                check(kind+' removes all selection overlays',not owner.overlays)
                result.close();QTest.qWait(60)
        set_cursor(round(region.x+400),round(region.y+300))
        controller.placement.start_at(n.cursor_position())
        samples=[]
        for index in range(24):
            set_cursor(round(region.x+650+index*4),round(region.y+500+index*2))
            start=time.perf_counter()
            controller.placement.track();QTest.qWait(0);flush()
            samples.append((time.perf_counter()-start)*1000)
        controller.placement.cancel()
        measurements.append({'preview_track_and_compositor_flush_ms':samples,'median_ms':statistics.median(samples),
                             'p95_ms':sorted(samples)[math.ceil(len(samples)*.95)-1]})
        check('Preview cancellation releases material and timers',not controller.placement.overlays
              and not controller.placement.timer.isActive())
        check('No Qt callback exceptions',not errors,errors)
    finally:
        mouse(4,0,0,0,0)
        if controller:controller.cleanup()
        if child is not None and child.poll() is None:
            if background:send(background,0x8002,0,0)
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:child.terminate();child.wait(timeout=5)
        guard.close();app.processEvents()
        set_cursor(*cursor)
        if previous:u.SetForegroundWindow(previous)
        sys.excepthook=old_hook
        (output/'checks.json').write_text(json.dumps({'checks':reports,'measurements':measurements,'exceptions':errors},indent=2),encoding='utf-8')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
