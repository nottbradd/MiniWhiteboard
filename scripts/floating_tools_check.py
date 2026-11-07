"""Capture the implemented widgets and check their native/offscreen interaction.

--native is intended for an isolated Windows VM. No user's boards/preferences
or global shortcuts are touched. An owned background keeps captures private.
"""
import argparse
import json
import math
import os
from pathlib import Path
import sys
import time
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native',action='store_true')
    parser.add_argument('--background-child',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--background-kind',choices=('pastel','light','busy'),default='pastel')
    parser.add_argument('--output',type=Path,default=Path('verification/v136/tools'))
    args = parser.parse_args()
    os.environ['QT_QPA_PLATFORM'] = 'windows' if args.native else 'offscreen'
    from PySide6.QtCore import QPoint, QPointF, QRect, Qt
    from PySide6.QtGui import QColor, QImage, QPainter, QLinearGradient, QFontDatabase, QFont
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QWidget, QToolButton, QLabel
    from unittest.mock import patch
    from mini_whiteboard import APP_VERSION, windows, clipboard
    from mini_whiteboard.board import BoardWindow
    from mini_whiteboard.document import Text, Stroke, Shape
    from mini_whiteboard.floating_tools import FloatingTools
    from mini_whiteboard.geometry import Rect
    from mini_whiteboard.snapping import SnapPreferences
    if args.native:
        if os.environ.get('GITHUB_ACTIONS') != 'true':
            raise SystemExit('Run native captures on the isolated candidate builder.')
        windows.enable_dpi_awareness()
    app = QApplication([])
    if not args.native and sys.platform=='win32':
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/seguisb.ttf')
    app.setQuitOnLastWindowClosed(False)
    prefs = SnapPreferences()
    manager = FloatingTools(app,prefs)
    args.output.mkdir(parents=True,exist_ok=True)
    rows,exceptions = [],[]
    original_hook = sys.excepthook
    sys.excepthook = lambda kind,value,tb:exceptions.append(repr(value))
    def check(label,condition,detail=None):
        rows.append(dict(check=label,status='PASS' if condition else 'FAIL',detail=detail))
        save()
        if not condition:
            raise AssertionError(label)
    def save():
        (args.output/'checks.json').write_text(json.dumps(dict(version=APP_VERSION,
            scope='native Windows source widgets' if args.native else 'offscreen Qt widget rendering',
            qt_scale=os.environ.get('QT_SCALE_FACTOR','1'),dpr=app.primaryScreen().devicePixelRatio(),
            real_pen='NOT RUN',hardware_dpi='NOT RUN; Qt scale override is synthetic',
            checks=rows,callback_errors=exceptions),indent=2),encoding='utf-8')
    class Background(QWidget):
        def paintEvent(self,event):
            p = QPainter(self)
            if args.background_kind=='light':
                p.fillRect(self.rect(),QColor('#f5f7fb'))
                p.setPen(QColor('#607080'))
                p.drawText(30,45,'Owned light background · Mini Whiteboard visual check')
                return
            if args.background_kind=='busy':
                for y in range(0,self.height(),48):
                    for x in range(0,self.width(),48):
                        p.fillRect(x,y,48,48,QColor(('#e7effa','#627d99','#dcc4db','#f6db9b')[(x//48+y//48)%4]))
                p.setPen(QColor('#172b43'))
                for y in range(30,self.height(),72):
                    p.drawText(25,y,'Owned patterned background · Contrast and frost check')
                return
            gradient = QLinearGradient(0,0,self.width(),self.height())
            gradient.setColorAt(0,QColor('#ffdce4'))
            gradient.setColorAt(.5,QColor('#cdddf8'))
            gradient.setColorAt(1,QColor('#ebdcf7'))
            p.fillRect(self.rect(),gradient)
    native_patch = patch('mini_whiteboard.windows.IS_WINDOWS',False) if not args.native else None
    if native_patch:
        native_patch.start()
    background = Background(None,Qt.WindowType.FramelessWindowHint)
    work = app.primaryScreen().availableGeometry()
    background.setGeometry(work)
    child = None
    if args.background_child:
        background.show()
        sys.excepthook = original_hook
        raise SystemExit(app.exec())
    if args.native:
        child = subprocess.Popen([sys.executable,'-m','scripts.floating_tools_check','--native',
            '--background-child','--output',str(args.output/'background')],creationflags=subprocess.CREATE_NO_WINDOW)
        QTest.qWait(800)
    else:
        background.show()
    board = BoardWindow('Mini Whiteboard · V1.3.6 candidate',prefs)
    manager.add_board(board)
    def focus():
        board.show()
        board.activateWindow()
        board.canvas.setFocus()
        QTest.qWait(60)
        if not args.native:
            app.setActiveWindow(board)  # Offscreen's platform activation is incomplete.
            board.canvas.setFocus()
            app.processEvents()
    def capture(name, expected_widget=None):
        QTest.qWait(200)
        if args.native:
            screen = app.primaryScreen()
            frame = screen.grabWindow(0)
            if expected_widget is not None:
                # A widget grab can be current while the hosted desktop still
                # presents the preceding frame. Check actual screen pixels,
                # retaining a stale frame instead of calling it a visual pass.
                point = expected_widget.mapToGlobal(QPoint(9,9))-screen.geometry().topLeft()
                dpr = frame.devicePixelRatio()
                expected = expected_widget.grab().toImage().pixelColor(round(9*dpr),round(9*dpr))
                started = time.monotonic()
                def matches():
                    actual = frame.toImage().pixelColor(round(point.x()*dpr),round(point.y()*dpr))
                    return max(abs(a-b) for a,b in zip(actual.getRgb()[:3],expected.getRgb()[:3])) < 12
                if not matches():
                    frame.save(str(args.output/(name+'-initial-stale.png')))
                while not matches() and time.monotonic()-started < 2:
                    QTest.qWait(50)
                    frame = screen.grabWindow(0)
                frame.save(str(args.output/(name+'.png')))
                check(name+' screen shows the current swatch state',matches(),
                      {'additional_wait_ms':round((time.monotonic()-started)*1000),'sample':expected.name()})
            else:
                frame.save(str(args.output/(name+'.png')))
        else:
            # Actual QWidget grabs, composed at their actual logical positions.
            image = QImage(work.size()*app.primaryScreen().devicePixelRatio(),QImage.Format.Format_ARGB32_Premultiplied)
            image.setDevicePixelRatio(app.primaryScreen().devicePixelRatio())
            image.fill(Qt.GlobalColor.transparent)
            p = QPainter(image)
            for widget in (background,board,manager.palette,manager.options):
                if widget is not None and widget.isVisible():
                    p.drawPixmap(widget.pos()-work.topLeft(),widget.grab())
            p.end()
            image.save(str(args.output/(name+'.png')))
        save()
    try:
        # Fit owned windows to each logical desktop, including scale overrides.
        width,height = min(920,work.width()-40),min(460,work.height()-180)
        board.setGeometry(work.x()+(work.width()-width)//2,work.y()+95,width,height)
        focus()
        c = board.canvas
        c.document.commit((Text((45,60),'Make room for ideas',size=26,layout_width=650),
            Text((48,125),'Sketch · Plan · Iterate',size=16,layout_width=600),
            Stroke(tuple((50+i*4,220+22*math.sin(i*.15)) for i in range(70)),3),
            Shape('Ellipse',(width-170,200),(width-65,280),2,color='#2878d0')), 'Demonstration')
        c.sync_selection()
        prefs.set_floating_tools(True)
        focus()
        check('One toolbar appears above the active board',manager.palette is not None and manager.palette.isVisible() and manager.placement=='above')
        check('Showing tools retains the active canvas',c.hasFocus() and board.isActiveWindow())
        check('46 logical pixel toolbar and 42 pixel pen targets',manager.palette.height()==46 and
              all(b.width()==42 and b.height()==42 for b in manager.palette.buttons.values()),
              {'size':[manager.palette.width(),manager.palette.height()],'dpr':board.devicePixelRatioF()})
        capture('white-above')
        prefs.set_theme('Glass')
        QTest.qWait(150)
        capture('glass-above')
        check('Theme change keeps the active toolbar',manager.palette.isVisible())
        button = manager.palette.buttons['Draw']
        QTest.mousePress(button,Qt.MouseButton.LeftButton)
        QTest.qWait(app.styleHints().mousePressAndHoldInterval()+50)
        check('Timed long press opens Draw options',manager.options is not None and manager.options.tool=='Draw')
        QTest.mouseRelease(button,Qt.MouseButton.LeftButton)
        check('Long-press release leaves options open',manager.options is not None)
        capture('glass-options')
        prefs.set_theme('White')
        QTest.qWait(150)
        capture('white-options')
        title = next(w for w in manager.options.findChildren(QLabel) if w.text()=='Draw')
        check('Compact options title uses semibold weight',title.font().weight()==QFont.Weight.DemiBold and title.font().pointSizeF()==11.5)
        def white_button():
            return next(b for b in manager.options.findChildren(QToolButton) if b.accessibleName()=='White')
        white = white_button()
        check('Unselected White has named 42px target',not white.isChecked() and white.width()==42 and white.height()==42 and white.toolTip()=='White')
        unselected = white.grab().toImage()
        dpr = unselected.devicePixelRatio()
        centre = unselected.pixelColor(round(21*dpr),round(21*dpr))
        outline = unselected.pixelColor(round(27*dpr),round(21*dpr))
        check('White fill and visible outline survive rendering',centre.lightness()>245 and outline.lightness()<200,
              {'fill':centre.name(),'outline':outline.name()})
        QTest.mouseClick(white,Qt.MouseButton.LeftButton)
        focus()
        manager.open_options('Draw')
        QTest.qWait(80)
        white = white_button()
        check('White selection updates shared colour and checked state',QColor(c.active_color)==QColor('white') and white.isChecked())
        selected = white.grab().toImage()
        check('White selected background differs visibly',selected.pixelColor(round(9*dpr),round(9*dpr)) != unselected.pixelColor(round(9*dpr),round(9*dpr)))
        capture('white-options-selected',white)
        prefs.set_theme('Glass')
        QTest.qWait(100)
        capture('glass-options-selected')
        prefs.set_theme('White')
        c.apply_color('#000000')
        manager.close_options(refocus=True)
        board.move(board.x(),work.top()-round(board.paper_rect().top()))
        focus()
        check('Top-edge board places tools below',manager.placement=='below')
        capture('white-below')
        board.setGeometry(work)
        focus()
        check('Screen-filling board places tools inside',manager.placement=='inside')
        capture('white-inside')
        grip = manager.palette.grip
        origin = QPointF(grip.mapToGlobal(grip.rect().center()))
        before = board.geometry()
        manager.start_drag(origin)
        manager.drag(origin+QPointF(-50,-80))
        manager.finish_drag()
        QTest.mouseClick(manager.palette.buttons['Eraser'],Qt.MouseButton.LeftButton)
        check('Grip drag moves tools only and selection synchronizes',board.geometry()==before and c.tool=='Eraser' and
              manager.palette.buttons['Eraser'].isChecked() and manager.placement=='manual')
        capture('white-dragged-eraser')
        before = clipboard.rendered_image(c.document.objects)
        manager.set_capture_suspended(True)
        check('Capture suspension hides all floating chrome',not manager.palette.isVisible() and manager.options is None)
        manager.set_capture_suspended(False)
        focus()
        check('Tools never enter document clipboard/export',before==clipboard.rendered_image(c.document.objects))
        manager.offsets.clear()
        prefs.set_theme('White')
        board.setGeometry(work.x()+80,work.y()+100,240,180)
        focus()
        capture('white-small')
        check('Small board retains full sized controls',manager.palette.height()==46)
        board.minimize_to_tray()
        check('Minimizing hides tools immediately',not manager.palette.isVisible())
        board.restore()
        focus()
        check('Explicit restore restores tools',manager.palette.isVisible())
        check('No uncaught Qt callback errors',not exceptions,exceptions)
    finally:
        manager.close()
        board.close()
        background.close()
        if child is not None and child.poll() is None:
            child.terminate()
            child.wait(timeout=5)
        app.processEvents()
        save()
        if native_patch:
            native_patch.stop()
        sys.excepthook = original_hook


if __name__ == '__main__':
    main()
