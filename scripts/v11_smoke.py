"""Native release checks on owned Qt windows and an owned clipboard helper."""
import ctypes as C
from ctypes import wintypes as W
from dataclasses import replace
import json
import sys
import time

from PySide6.QtCore import QMimeData, QPoint, QProcess, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from mini_whiteboard import images, rendering, windows
from mini_whiteboard.document import Document, ImageObject, Shape, Stroke, Text
from mini_whiteboard.geometry import Rect
from mini_whiteboard.settings import CLIPBOARD_MIME
from mini_whiteboard.transforms import translation


def run_v11_checks(controller, check, artifacts):
    app = QApplication.instance()
    clipboard = app.clipboard()
    original = QMimeData()
    current = clipboard.mimeData()
    if current is not None:
        for name in current.formats():
            original.setData(name, current.data(name))
        if current.hasImage():
            original.setImageData(clipboard.image())
    board = controller.create_board(Rect(150, 170, 740, 520))
    canvas = board.canvas
    helper = QProcess()
    fixture = None
    screenshot_board = None

    def key(code, modifiers=Qt.KeyboardModifier.NoModifier):
        QTest.keyClick(canvas, code, modifiers)
        app.processEvents()

    def probe(publish=False):
        helper.start(sys.executable, ['-m', 'scripts.clipboard_probe', *(['--publish'] if publish else [])])
        if not helper.waitForStarted(5000):
            raise RuntimeError(helper.errorString())
        deadline = time.monotonic()+6
        # OLE may ask the owning GUI thread to render clipboard data lazily.
        # Keep its event loop alive while the separate process reads it.
        while not helper.canReadLine() and time.monotonic() < deadline:
            QTest.qWait(20)
        if not helper.canReadLine():
            raise RuntimeError(bytes(helper.readAllStandardError()).decode(errors='replace'))
        result = json.loads(bytes(helper.readLine()))
        if not publish:
            helper.waitForFinished(2000)
        return result

    try:
        QTest.qWait(120)
        canvas.setFocus()
        a = Stroke(((35, 90), (215, 90)), 5, color='#e04444')
        b = Text((50, 130), 'Native clipboard', 20, color='#2878d0')
        canvas.document.commit((a, b), 'Fixture')
        key(Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        check('Native Ctrl+A selects both objects', canvas.selected_ids == {a.id, b.id})
        key(Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        check('Windows clipboard contains editable MIME and image', clipboard.mimeData().hasFormat(CLIPBOARD_MIME)
              and clipboard.mimeData().hasImage() and not clipboard.image().isNull())
        check('Another Windows process receives editable data and ordinary image',
              (result := probe())['image'] and result['editable'] and result['payload_bytes'] > 0, result)
        key(Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        copies = canvas.document.objects[2:]
        check('Native same-board paste has independent IDs and 16 px offset', len(copies) == 2
              and all(x.id != y.id and y.transform == translation(16,16) @ x.transform for x,y in zip((a,b),copies)))
        key(Qt.Key.Key_Right)
        key(Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
        nudged = canvas.document.objects
        key(Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        check('Native consecutive nudges undo as one action', canvas.document.objects == (a,b,*copies))
        key(Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
        check('Native nudge redo is exact', canvas.document.objects == nudged)
        key(Qt.Key.Key_C)
        popup = canvas.palette
        QTest.qWait(80)
        check('Native palette is a temporary popup without tool-overlay obstruction', popup.isVisible()
              and popup.windowType() == Qt.WindowType.Popup
              and (canvas.tool_overlay is None or not canvas.tool_overlay.isVisible()))
        popup.grab().save(str(artifacts/'v11-colour-palette.png'))
        QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_4)
        QTest.qWait(60)
        check('Palette number changes selected colours and returns focus', canvas.active_color == '#26945c'
              and all(o.color == '#26945c' for o in canvas.selected_objects) and canvas.hasFocus())
        key(Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        check('Native colour undo restores exact objects', canvas.document.objects == nudged)
        key(Qt.Key.Key_D, Qt.KeyboardModifier.ControlModifier)
        check('Native duplicate adds independent objects', len(canvas.document.objects) == 6)
        key(Qt.Key.Key_X, Qt.KeyboardModifier.ControlModifier)
        check('Native cut removes only selected objects', len(canvas.document.objects) == 4)
        key(Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        check('Native cut undo restores selection contents', len(canvas.document.objects) == 6)
        canvas.set_selection({a.id})
        canvas.reorder(True)
        check('Native front ordering places selection last', canvas.document.objects[-1].id == a.id)
        canvas.set_locked({a.id}, True)
        check('Native lock prevents ordinary selection', canvas.document.get(a.id).locked and not canvas.selected_ids)
        menu = canvas.make_context_menu((50,90))
        unlock = next(action for action in menu.actions() if action.text() == 'Unlock this object')
        unlock.trigger()
        check('Native locked object can be unlocked through context menu', not canvas.document.get(a.id).locked)
        menu.deleteLater()

        check('External process publishes Windows image', probe(publish=True)['published'])
        key(Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        obj = canvas.document.objects[-1]
        check('Native external image paste creates editable image with original pixels', isinstance(obj, ImageObject)
              and obj.pixel_size == (240,120) and images.decoded(obj.png).pixelColor(10,10).name() == '#3179b5')
        helper.terminate()
        helper.waitForFinished(2000)
        canvas.duplicate_selection()
        copy = canvas.document.objects[-1]
        check('Image duplicate shares immutable PNG data with new identity', copy.png is obj.png and copy.id != obj.id)
        canvas.begin_editing(b)
        QTest.qWait(60)
        editor = QApplication.focusWidget()
        QTest.keyClick(editor, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClicks(editor, 'C A V E 1234554321')
        QTest.keyClick(editor, Qt.Key.Key_Left)
        check('Native text editor owns new C/numbers/Ctrl+A/arrows', canvas.editor.toPlainText() == 'C A V E 1234554321'
              and canvas.palette is None and canvas.editor.textCursor().position() == len('C A V E 1234554321')-1)
        QTest.keyClick(editor, Qt.Key.Key_Escape)
        QTest.qWait(50)

        # A native GDI capture reads only this disposable solid-colour fixture.
        board.minimize_to_tray()
        fixture = QWidget(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        fixture.setStyleSheet('background:#3179b5;')
        fixture.show()
        windows.set_window_rect(fixture, Rect(300, 250, 500, 350))
        QTest.qWait(150)
        sample = Rect(340, 290, 240, 140)
        image = windows.capture_rect(sample)
        check('Native GDI screenshot pixels and physical dimensions match owned fixture',
              image.size().width() == 240 and image.height() == 140
              and image.pixelColor(10,10).name() == '#3179b5', image.pixelColor(10,10).name())
        check('Native screenshot hotkey is registered', windows.CAPTURE_HOTKEY in controller.hotkeys.registered)
        controller.capture.start()
        QTest.qWait(100)
        overlay = next(o for o in controller.capture.overlays if o.monitor.rect.intersection_area(sample) > 0)
        check('Native screenshot overlay covers physical display', windows.window_rect(overlay) == overlay.monitor.rect)
        set_cursor = windows.bind(windows.user32, 'SetCursorPos', W.BOOL, C.c_int, C.c_int)
        set_cursor(340, 290)
        QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=overlay.mapFromGlobal(QPoint(340,290)))
        set_cursor(580, 430)
        QTest.mouseMove(overlay, overlay.mapFromGlobal(QPoint(580,430)))
        QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=overlay.mapFromGlobal(QPoint(580,430)))
        QTest.qWait(200)
        screenshot_board = controller.boards[-1]
        screenshot = screenshot_board.canvas.document.objects[0]
        check('Native click-drag screenshot creates locked source image ready to draw', screenshot.locked
              and screenshot.pixel_size == (240,140) and screenshot_board.canvas.tool == 'Draw')
        check('Native screenshot hides overlay before capturing unmodified pixels',
              not controller.capture.active and images.decoded(screenshot.png).pixelColor(10,10).name() == '#3179b5')
        check('Screenshot board content begins at selected screen position',
              screenshot_board.canvas.mapToGlobal(QPoint(0,0)) == QPoint(340,290))
        screenshot_board.grab().save(str(artifacts/'v11-screenshot-board.png'))
        from .refinement_smoke import run_refinement_checks
        run_refinement_checks(screenshot_board,check,artifacts)
        controller.capture.start()
        controller.hotkeys.events.cancel.emit()
        check('Screenshot Escape cleanup leaves no active overlay or timer', not controller.capture.active
              and not controller.capture.timer.isActive() and windows.ESCAPE_HOTKEY not in controller.hotkeys.registered)
    finally:
        if helper.state() != QProcess.ProcessState.NotRunning:
            helper.terminate()
            helper.waitForFinished(2000)
        controller.capture.cancel()
        clipboard.setMimeData(original)
        if screenshot_board is not None:
            screenshot_board.close()
        if fixture is not None:
            fixture.close()
            fixture.deleteLater()
        board.close()
        QTest.qWait(50)
