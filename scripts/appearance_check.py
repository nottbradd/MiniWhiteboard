"""Opt-in native Windows material captures and lifetime checks on owned windows."""
import argparse
import ctypes as C
from ctypes import wintypes as W
from dataclasses import replace
import json
import os
from pathlib import Path
import sys

os.environ['QT_QPA_PLATFORM'] = 'windows'
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from mini_whiteboard import windows, clipboard, images
from mini_whiteboard import APP_VERSION
from mini_whiteboard.app import WhiteboardApplication
from mini_whiteboard.appearance import interface_font
from mini_whiteboard.document import Text, Stroke, Shape
from mini_whiteboard.geometry import Rect
from mini_whiteboard.snapping import SnapPreferences
from mini_whiteboard.transforms import Affine


class Background(QWidget):
    """An owned demonstration backdrop, never the user's wallpaper."""
    def __init__(self):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.mode = 'busy'

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor({'busy':'#91ace2','light':'#eef1f7','dark':'#202b46'}[self.mode]))
        if self.mode == 'busy':
            p.scale(self.width()/1500, self.height()/850)
            for y, colors in ((-150, ('#8974bf','#ffc1ae')), (250, ('#446fb0','#96b3ea')),
                              (530, ('#c06a97','#ffd0a5'))):
                path = QPainterPath(QPointF(-100,y))
                path.cubicTo(400,y+250,800,y-150,1600,y+320)
                path.lineTo(1600,y+680)
                path.cubicTo(900,y+230,500,y+560,-100,y+240)
                path.closeSubpath()
                gradient = QLinearGradient(200,y,900,y+400)
                gradient.setColorAt(0, QColor(colors[0]))
                gradient.setColorAt(1, QColor(colors[1]))
                p.fillPath(path, gradient)
                p.setPen(QPen(QColor(255,255,255,90),1.5))
                p.drawPath(path)
        font = interface_font('heading')
        font.setPointSize(12)  # Keep the controlled backdrop identical across revisions.
        p.setFont(font)
        p.setPen(QColor('#ffffff' if self.mode == 'dark' else '#242a3c'))
        p.drawText(38, 32, f'Mini Whiteboard {APP_VERSION} · unpublished candidate · owned demonstration background')


def sample_image():
    image = QImage(780, 440, QImage.Format.Format_RGB32)
    image.fill('#f8fafc')
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QColor('#152034'))
    font = interface_font('heading')
    font.setPointSize(22)
    p.setFont(font)
    p.drawText(35,55,'Sprint overview')
    font.setPointSize(14)
    font.setWeight(font.Weight.Normal)
    p.setFont(font)
    p.drawText(35,94,'Original screenshot pixels stay sharp and opaque.')
    for index, (label, value) in enumerate((('Design',.78),('Build',.6),('Review',.4))):
        y = 145 + index*86
        p.setPen(QColor('#23324c'))
        p.drawText(35,y,label)
        p.fillRect(QRectF(35,y+12,700,17),QColor('#e0e6f0'))
        p.fillRect(QRectF(35,y+12,700*value,17),QColor('#2467f5'))
    p.end()
    return image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('verification/v133-review02/appearance'))
    args = parser.parse_args()
    windows.enable_dpi_awareness()
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    guard = windows.SingleInstance()
    if not guard.acquired:
        raise RuntimeError('Exit Mini Whiteboard before this desktop test.')
    foreground = windows.bind(windows.user32,'GetForegroundWindow',W.HWND)()
    cursor = windows.cursor_position()
    controller = WhiteboardApplication(app, SnapPreferences())
    controller.notify = lambda text: None
    background = Background()
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    results, errors = [], []
    old_hook = sys.excepthook
    sys.excepthook = lambda typ,value,tb: errors.append(repr(value))
    def check(label, passed, detail=None):
        results.append(dict(check=label,status='PASS' if passed else 'FAIL',detail=detail))
        print(json.dumps(results[-1]),flush=True)
        if not passed:
            raise AssertionError(label)
    def capture(name):
        QTest.qWait(230)
        windows.capture_rect(region).save(str(output/(name+'.png')))
    def resources():
        get = windows.bind(windows.user32,'GetGuiResources',W.DWORD,W.HANDLE,W.DWORD)
        handle = windows.bind(windows.kernel32,'GetCurrentProcess',W.HANDLE)()
        return tuple(get(handle,kind) for kind in (0,1))
    try:
        origin = windows.monitors()[0].rect
        region = Rect(origin.x+60,origin.y+80,1500,850)
        background.show()
        windows.set_window_rect(background,region)
        background.raise_()
        board = controller.create_board(Rect(region.x+35,region.y+70,990,660))
        canvas = board.canvas
        canvas.document.add(Text((65,135),'A little space for ideas.\nDraw. Type. Annotate.',size=25,layout_width=750))
        points = ((125,320),(100,355),(135,385),(220,380),(360,330),(530,257),(660,243),(720,266),(735,300))
        canvas.document.add(Stroke(points,3.5,color='#2467f5'))
        canvas.document.add(Shape('Rounded rectangle',(605,355),(805,480),3,color='#2467f5'))
        canvas.document.add(Shape('Arrow',(525,340),(585,395),3,color='#2467f5'))
        canvas.sync_selection()
        QTest.qWait(200)
        before = canvas.document.objects,list(canvas.document.history),board.physical_paper_rect()
        copied = clipboard.rendered_image(canvas.document.objects)
        capture('white')
        controller.preferences.set_theme('Glass')
        capture('glass-busy')
        painted = windows.capture_rect(region)
        blue = QColor('#2467f5')
        check('Native Glass retains exact opaque blue artwork',sum(
              painted.pixelColor(x,y) == blue for y in range(300,650)
              for x in range(100,900)) > 100 and board.windowOpacity() == 1)
        check('Native DWM material is supported and present',board.native_glass,
              {'policy':vars(board.display_policy),'windows_build':sys.getwindowsversion().build})
        check('Theme preserves document/history/bounds and exact clipboard pixels',
              before == (canvas.document.objects,canvas.document.history,board.physical_paper_rect())
              and clipboard.rendered_image(canvas.document.objects) == copied and board.windowOpacity() == 1)
        background.mode = 'light'
        background.update()
        capture('glass-light')
        background.mode = 'dark'
        background.update()
        capture('glass-dark')
        background.mode = 'busy'
        background.update()
        # Separate the demonstration background's composition from popup entry.
        # The material-state check also exercises updates while a popup is open.
        QTest.qWait(100)
        controller.rebuild_menu()
        menu = next(a.menu() for a in controller.menu.actions() if a.text() == 'Appearance')
        menu.popup(QPoint(round(region.x+1070),round(region.y+85)))
        capture('appearance-menu')
        check('Appearance menu uses a passive material host',menu.native_glass and bool(getattr(menu,'_backdrop',None)),
              {'size':[menu.width(),menu.height()], 'native':vars(menu.physical_paper_rect()),
               'hint':[menu.sizeHint().width(),menu.sizeHint().height()],
               'actions':[(a.text(),menu.actionGeometry(a).getRect()) for a in menu.actions()]})
        menu.hide()
        check('Dismissed menu releases its native material host',getattr(menu,'_backdrop',None) is None)
        canvas.open_palette()
        canvas.palette.move(round(region.x+1070),round(region.y+210))
        capture('colour-palette')
        check('Palette uses the same native material',canvas.palette.native_glass)
        canvas.palette.close()
        canvas.context_menu = canvas.make_context_menu((690,410))
        canvas.context_menu.popup(QPoint(round(region.x+1070),round(region.y+85)))
        capture('context-menu')
        canvas.context_menu.close()
        canvas.help_panel.show()
        canvas.help_panel.move(round(region.right-canvas.help_panel.width()-12),round(region.y+50))
        capture('help')
        check('Help fits the available desktop',canvas.help_panel.frameGeometry().height() <= board.screen().availableGeometry().height(),
              [canvas.help_panel.width(),canvas.help_panel.height()])
        canvas.help_panel.hide()
        screenshot = controller.create_screenshot_board(Rect(region.x+70,region.y+160,780,440),sample_image())
        shot_board = controller.boards[-1]
        capture('screenshot')
        check('Screenshot uses original opaque pixels and its cached display path',
              shot_board.canvas.background_cache is not None
              and shot_board.canvas.document.objects[0].png == images.from_image(sample_image()).png)
        shot_board.close()
        # Closing the second tool window may activate the owned topmost
        # backdrop. Expose the board before testing its input region; an
        # occluded board is not an input-transparency failure.
        board.restore()
        QTest.qWait(100)
        # Zero-alpha layered pixels exclude actual desktop input. The visible
        # antialias fringe extends beyond the mathematical curve by a subpixel.
        get_at = windows.bind(windows.user32,'WindowFromPoint',W.HWND,W.POINT)
        bounds = board.physical_paper_rect()
        check('Transparent rounded corner passes through to owned background',
              get_at(W.POINT(round(bounds.x+1),round(bounds.y+1))) == int(background.winId()))
        ancestor = windows.bind(windows.user32,'GetAncestor',W.HWND,W.HWND,W.UINT)
        target = get_at(W.POINT(round(bounds.x+200),round(bounds.y+200)))
        check('Canvas remains the input target inside the glass',
              ancestor(target,2) == int(board.winId()), {'target':target,'root':ancestor(target,2),'board':int(board.winId())})
        path = QPainterPath()
        path.addRoundedRect(board.paper_rect(),board.corner_radius(),board.corner_radius())
        window = board.desktop.window_rect(board)
        probes, fringe, blocked = 0, 0, []
        alpha = board.grab().toImage()
        for dx in range(0,33,2):
            for dy in range(0,33,2):
                for x,y in ((bounds.x+dx,bounds.y+dy),(bounds.right-dx-1,bounds.y+dy),
                            (bounds.x+dx,bounds.bottom-dy-1),(bounds.right-dx-1,bounds.bottom-dy-1)):
                    local = QPointF((x+.5-window.x)/board.devicePixelRatioF(),(y+.5-window.y)/board.devicePixelRatioF())
                    if not path.contains(local):
                        if alpha.pixelColor(round(x-window.x),round(y-window.y)).alpha():
                            fringe += 1
                            continue
                        probes += 1
                        if ancestor(get_at(W.POINT(round(x),round(y))),2) != int(background.winId()):
                            blocked.append([x,y])
        check('All sampled zero-alpha corner points pass desktop input',not blocked and probes>=200,
              {'zero_alpha_probes':probes,'visible_fringe_samples':fringe,'blocked':blocked})
        mouse = windows.bind(windows.user32,'mouse_event',None,W.DWORD,W.DWORD,W.DWORD,W.DWORD,C.c_size_t)
        set_cursor = windows.bind(windows.user32,'SetCursorPos',W.BOOL,C.c_int,C.c_int)
        for right,bottom in ((False,False),(True,False),(False,True),(True,True)):
            old = board.desktop.window_rect(board)
            paper = board.physical_paper_rect()
            x = paper.right-8 if right else paper.x+8
            y = paper.bottom-20 if bottom else paper.y+20
            set_cursor(round(x),round(y));QTest.qWait(30)
            if ancestor(get_at(W.POINT(round(x),round(y))),2) != int(board.winId()):
                raise AssertionError('Rounded resize target is not owned by the board')
            mouse(2,0,0,0,0);QTest.qWait(25)
            set_cursor(round(x+12),round(y+10));QTest.qWait(70)
            mouse(4,0,0,0,0);QTest.qWait(50)
            resized = board.desktop.window_rect(board)
            if (resized.width != old.width+(12 if right else -12)
                    or resized.height != old.height+(10 if bottom else -10)):
                raise AssertionError('A visible Glass corner did not resize both axes: '+repr(
                    {'right':right,'bottom':bottom,'before':vars(old),'after':vars(resized),
                     'point':[x,y], 'foreground':windows.bind(windows.user32,'GetForegroundWindow',W.HWND)(),
                     'board':int(board.winId()), 'gesture':board._gesture}))
            board.desktop.set_window_rect(board,old)
            QTest.qWait(30)
        check('All four visible Glass corner arcs support native diagonal resizing',
              board.physical_paper_rect() == before[2])
        for _ in range(8):
            old = board.desktop.window_rect(board)
            target = Rect(old.x+13,old.y+9,old.width+17,old.height+11)
            board.desktop.set_window_rect(board,target)
            QTest.qWait(10)
            host = board._backdrop
            native_bounds = W.RECT()
            windows.user32.GetWindowRect(host.handle,C.byref(native_bounds))
            host_bounds = Rect(native_bounds.left,native_bounds.top,
                               native_bounds.right-native_bounds.left,native_bounds.bottom-native_bounds.top)
            check_inside = board.physical_paper_rect().contains((host_bounds.x,host_bounds.y)) and (
                board.physical_paper_rect().contains((host_bounds.right,host_bounds.bottom)))
            if not check_inside:
                raise AssertionError('Backdrop lost its board during a native move/resize')
            board.desktop.set_window_rect(board,old)
        QTest.qWait(30)
        check('Native material follows repeated moves and resizes',board.physical_paper_rect() == before[2])
        initial = resources()
        for _ in range(30):
            controller.preferences.set_theme('White')
            controller.preferences.set_theme('Glass')
            controller.toggle_visibility()
            if board.isVisible() or getattr(board,'_backdrop',None) is not None:
                raise AssertionError('Hide left a native host')
            controller.toggle_visibility()
        QTest.qWait(200)
        final = resources()
        check('Thirty theme/hide cycles release resources and stop activation',
              all(b <= a+4 for a,b in zip(initial,final)) and not board.activation_timer.isActive(),
              {'before_gdi_user':initial,'after_gdi_user':final})
        check('No callback exceptions, mouse grab or geometry/history changes',not errors
              and board.mouseGrabber() is None and before == (
                  canvas.document.objects,canvas.document.history,board.physical_paper_rect()),errors)
    finally:
        controller.cleanup()
        background.close()
        app.processEvents()
        windows.bind(windows.user32,'SetCursorPos',W.BOOL,C.c_int,C.c_int)(*cursor)
        if foreground:
            windows.user32.SetForegroundWindow(foreground)
        guard.close()
        sys.excepthook = old_hook
        (output/'checks.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
