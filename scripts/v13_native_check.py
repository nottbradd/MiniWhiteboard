"""Actual Windows compositor/OCR UI and bounded lifetime checks on owned surfaces."""
import ctypes as C
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import sys
import time

os.environ['QT_QPA_PLATFORM'] = 'windows'
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from mini_whiteboard import windows
from mini_whiteboard.app import WhiteboardApplication
from mini_whiteboard.document import Text, Stroke
from mini_whiteboard.geometry import Rect
from mini_whiteboard.snapping import SnapPreferences
from mini_whiteboard import clipboard, images
from mini_whiteboard.transforms import Affine
from dataclasses import replace


class Background(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.dark = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#172234' if self.dark else '#ebd8b6'))
        for x in range(0, self.width(), 48):
            for y in range(0, self.height(), 48):
                if (x//48+y//48) % 2:
                    painter.fillRect(x, y, 24, 24, QColor('#a256dc' if self.dark else '#3aaf88'))


def main():
    windows.enable_dpi_awareness()
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    guard = windows.SingleInstance()
    if not guard.acquired:
        raise RuntimeError('Exit Mini Whiteboard before this desktop test.')
    foreground = windows.bind(windows.user32, 'GetForegroundWindow', W.HWND)()
    cursor = windows.cursor_position()
    controller = WhiteboardApplication(app, SnapPreferences())
    background = Background()
    results, errors = [], []
    old_hook = sys.excepthook
    sys.excepthook = lambda typ, value, tb: errors.append(repr(value))
    media = Path('docs/media')

    def check(label, passed, detail=None):
        results.append(dict(check=label, status='PASS' if passed else 'FAIL', detail=detail))
        print(json.dumps(results[-1]), flush=True)
        if not passed:
            raise AssertionError(label)

    def resources():
        get = windows.bind(windows.user32, 'GetGuiResources', W.DWORD, W.HANDLE, W.DWORD)
        current = windows.bind(windows.kernel32, 'GetCurrentProcess', W.HANDLE)()
        return tuple(get(current, kind) for kind in (0, 1))

    try:
        origin = windows.monitors()[0].rect
        region = Rect(origin.x+90, origin.y+90, 840, 620)
        background.show()
        windows.set_window_rect(background, region)
        background.raise_()
        board = controller.create_board(Rect(origin.x+140, origin.y+130, 700, 480))
        canvas = board.canvas
        canvas.document.add(Text((35, 35), 'Mini Whiteboard V1.3\nDraw, type, annotate', size=24, layout_width=520))
        canvas.document.add(Stroke(((45, 155), (140, 175), (230, 140), (335, 170)), 6, color='#2878d0'))
        source = images.from_file('tests/fixtures/ocr/clean.png')
        source = replace(source, locked=True, transform=Affine(a=.5, d=.5, tx=35, ty=210))
        canvas.document.add(source)
        canvas.sync_selection()
        before = (canvas.document.objects, list(canvas.document.history), board.physical_paper_rect())
        copied = clipboard.rendered_image(canvas.document.objects)
        QTest.qWait(250)
        windows.capture_rect(region).save(str(media/'white-v13.png'))
        controller.preferences.set_theme('Glass')
        QTest.qWait(250)
        check('Document, source image and clipboard artwork survive theme switching',
              before == (canvas.document.objects, canvas.document.history, board.physical_paper_rect())
              and canvas.document.get(source.id) is source and clipboard.rendered_image(canvas.document.objects) == copied)
        check('Supported Windows DWM backdrop is present behind artwork', board.native_glass,
              {'policy': vars(board.display_policy), 'windows_build': sys.getwindowsversion().build})
        bright = windows.capture_rect(region)
        bright.save(str(media/'glass-v13.png'))
        background.dark = True
        background.update()
        QTest.qWait(250)
        dark = windows.capture_rect(region)
        dark.save('verification/v13-glass-dark.png')
        check('Native frost follows an owned changing desktop background',
              abs(bright.pixelColor(500, 450).red()-dark.pixelColor(500, 450).red()) > 15,
              {'bright': bright.pixelColor(500, 450).getRgb(), 'dark': dark.pixelColor(500, 450).getRgb()})
        blue = QColor('#2878d0')
        check('Strokes retain opaque exact ink through native Glass',
              sum(dark.pixelColor(x, y) == blue for x in range(70, 400) for y in range(165, 245)) > 30
              and board.windowOpacity() == 1)
        initial = resources()
        for _ in range(30):
            controller.preferences.set_theme('White')
            controller.preferences.set_theme('Glass')
            controller.toggle_visibility()
            check_hidden = not board.isVisible() and getattr(board, '_backdrop', None) is None
            controller.toggle_visibility()
            if not check_hidden:
                raise AssertionError('Hide left a native host')
        QTest.qWait(200)
        final = resources()
        check('Thirty theme/hide cycles preserve bounds and release native resources',
              all(b <= a+4 for a, b in zip(initial, final))
              and board.physical_paper_rect() == before[2] and not board.activation_timer.isActive(),
              {'before_gdi_user': initial, 'after_gdi_user': final})
        canvas.extract_text(source)
        panel = canvas.ocr_panel
        heartbeat = []
        QTimer.singleShot(0, lambda: heartbeat.append(True))
        deadline = time.monotonic()+15
        while not panel.ready and time.monotonic() < deadline:
            QTest.qWait(20)
        check('Native OCR review is responsive and exactly recognizes the original locked image',
              heartbeat and panel.ready and panel.review.toPlainText() ==
              'MINI WHITEBOARD\nMeeting 42: Ready!\nhttps://example.com/plan')
        windows.capture_rect(region).save(str(media/'ocr-v13.png'))
        controller.toggle_visibility()
        QTest.qWait(100)
        check('Hide All removes OCR review and the compositor host immediately',
              canvas.ocr_panel is None and not panel.valid and not board.isVisible()
              and getattr(board, '_backdrop', None) is None)
        controller.toggle_visibility()
        check('Restored board keeps original image bytes, history and geometry',
              before == (canvas.document.objects, canvas.document.history, board.physical_paper_rect()))
        check('No callback exceptions or mouse grab', not errors and board.mouseGrabber() is None, errors)
    finally:
        controller.cleanup()
        background.close()
        app.processEvents()
        windows.bind(windows.user32, 'SetCursorPos', W.BOOL, C.c_int, C.c_int)(*cursor)
        if foreground:
            windows.user32.SetForegroundWindow(foreground)
        guard.close()
        sys.excepthook = old_hook
        Path('verification/v13-native-features.json').write_text(json.dumps(results, indent=2)+'\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
