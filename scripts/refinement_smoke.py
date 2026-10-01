"""Native cache, border and actual mouse-resize checks on an owned board."""
import ctypes as C
from ctypes import wintypes as W
from dataclasses import replace
import os

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from mini_whiteboard import rendering, windows
from mini_whiteboard.settings import BORDER, EDGE_GRIP
from .polish_smoke import capture_board


def run_refinement_checks(board,check,artifacts):
    canvas = board.canvas
    source = canvas.document.objects[0]
    cache = canvas.background_cache
    check('Native screenshot cache exists at exactly the viewport physical resolution', cache is not None
          and cache.image.width() == round(canvas.width()*board.devicePixelRatioF())
          and cache.image.height() == round(canvas.height()*board.devicePixelRatioF()),
          {'source':source.pixel_size,'cache':[cache.image.width(),cache.image.height()],
           'viewport':[canvas.width(),canvas.height()],'dpr':board.devicePixelRatioF()})
    raster,builds = cache.image,cache.builds
    QTest.mousePress(canvas,Qt.MouseButton.LeftButton,pos=QPoint(30,60))
    for x in range(40,190,10):
        QTest.mouseMove(canvas,QPoint(x,65+(x%30)//2))
    QTest.mouseRelease(canvas,Qt.MouseButton.LeftButton,pos=QPoint(190,75))
    QTest.qWait(50)
    check('Native drawing reuses screenshot raster and original image identity', cache.image is raster
          and cache.builds == builds and canvas.document.objects[0] is source)
    canvas.set_tool('Eraser')
    QTest.mousePress(canvas,Qt.MouseButton.LeftButton,pos=QPoint(100,50))
    QTest.mouseMove(canvas,QPoint(100,100))
    QTest.mouseRelease(canvas,Qt.MouseButton.LeftButton,pos=QPoint(100,100))
    QTest.qWait(50)
    check('Native circular erasing reuses screenshot cache and preserves locked pixels', cache.builds == builds
          and canvas.document.objects[0] is source and canvas.document.objects[1].erasures)
    canvas.set_number(5)
    QTest.mouseClick(canvas,Qt.MouseButton.LeftButton,pos=QPoint(45,71))
    QTest.qWait(50)
    check('Native whole-stroke eraser removes annotation while retaining cached screenshot',
          canvas.document.objects == (source,) and cache.image is raster)
    canvas.set_locked({source.id},False)
    canvas.nudge(10,5)
    check('Native screenshot unlock permits transforms without changing original PNG data',
          not canvas.document.objects[0].locked and canvas.document.objects[0].png is source.png
          and canvas.document.objects[0].transform != source.transform)
    canvas.document.undo()
    canvas.document.undo()
    canvas.sync_selection()
    canvas.update()
    QTest.qWait(60)
    check('Native undo restores the original locked screenshot and cache', canvas.document.objects[0] is source
          and cache.matches(source) and cache.image is raster and cache.builds == builds)
    canvas.set_selection(set())
    canvas.set_tool('Draw')
    canvas.feedback.stop()
    image = board.grab().toImage()
    r = board.paper_rect()
    dpr = board.devicePixelRatioF()
    pixel = lambda x,y:image.pixelColor(round(x*dpr),round(y*dpr)).name()
    check('Native top border remains subtle grey', pixel(r.center().x(),r.top()) == BORDER)
    check('Native left right bottom edges contain no grey outline',
          all(pixel(x,y)=='#3179b5' for x,y in ((r.left(),r.center().y()),(r.right()-1,r.center().y()),
                                               (r.center().x(),r.bottom()-1))))
    check('Native shadow and both top controls remain present', board._shadow.isVisible()
          and board.minus.isVisible() and board.remove.isVisible())
    capture_board(board).save(str(artifacts/'refinement-screenshot-border.png'))

    original = windows.window_rect(board)
    before_objects = canvas.document.objects
    set_cursor = windows.bind(windows.user32,'SetCursorPos',W.BOOL,C.c_int,C.c_int)
    mouse = windows.bind(windows.user32,'mouse_event',None,W.DWORD,W.DWORD,W.DWORD,W.DWORD,C.c_size_t)
    get_at = windows.bind(windows.user32,'WindowFromPoint',W.HWND,W.POINT)
    get_pid = windows.bind(windows.user32,'GetWindowThreadProcessId',W.DWORD,W.HWND,C.POINTER(W.DWORD))
    pressed = False
    try:
        # The outermost top-right target avoids the close button's larger hitbox.
        points = [('left',(r.left()+6,r.center().y()),(-20,0)),
                  ('right',(r.right()-6,r.center().y()),(20,0)),
                  ('top',(r.center().x(),r.top()+6),(0,-20)),
                  ('bottom',(r.center().x(),r.bottom()-6),(0,20)),
                  ('top-left',(r.left()+6,r.top()+6),(-20,-20)),
                  ('top-right',(r.right()-3,r.top()+6),(20,-20)),
                  ('bottom-left',(r.left()+6,r.bottom()-6),(-20,20)),
                  ('bottom-right',(r.right()-6,r.bottom()-6),(20,20))]
        for name,(x,y),(dx,dy) in points:
            windows.set_window_rect(board,original)
            QTest.qWait(50)
            native = windows.window_rect(board)
            start = (round(native.x+x*dpr),round(native.y+y*dpr))
            owner = W.DWORD()
            get_pid(get_at(W.POINT(*start)),C.byref(owner))
            if owner.value != os.getpid() or board.childAt(round(x),round(y)) in (board.minus,board.remove):
                raise RuntimeError('Resize test target is not the owned resize zone: '+name)
            set_cursor(*start)
            QTest.qWait(50)
            mouse(0x0002,0,0,0,0)
            pressed = True
            QTest.qWait(40)
            set_cursor(round(start[0]+dx*dpr),round(start[1]+dy*dpr))
            QTest.qWait(80)
            mouse(0x0004,0,0,0,0)
            pressed = False
            QTest.qWait(50)
            changed = windows.window_rect(board)
            check('Native invisible resize works: '+name, changed != original
                  and (not dx or changed.width > original.width)
                  and (not dy or changed.height > original.height),vars(changed))
        windows.set_window_rect(board,original)
        QTest.qWait(70)
        check('Native invisible resizing keeps document objects exact', canvas.document.objects == before_objects
              and EDGE_GRIP == 7 and board._gesture is None)
    finally:
        if pressed:
            mouse(0x0004,0,0,0,0)
        windows.set_window_rect(board,original)
