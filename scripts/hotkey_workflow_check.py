"""Opt-in real Windows keyboard test using an owned external focus target.

Temporarily moves the cursor and sends Ctrl+Alt+W/Escape. Never types into an
unowned window; aborts if the foreground window is unexpected. Restores cursor
and foreground on exit, and closes only the disposable windows it created.
"""
import ctypes as C
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import sys

os.environ["QT_QPA_PLATFORM"] = "windows"
from PySide6.QtCore import QProcess, QCoreApplication, QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from mini_whiteboard import windows, images
from mini_whiteboard.document import ImageObject
from mini_whiteboard.snapping import SnapPreferences
from mini_whiteboard.app import WhiteboardApplication
from mini_whiteboard.geometry import Rect, normalized


def main():
    windows.enable_dpi_awareness()
    app = QApplication([])
    guard = windows.SingleInstance()
    if not guard.acquired:
        raise SystemExit("Exit Mini Whiteboard before running this desktop test.")
    user32 = windows.user32
    foreground = windows.bind(user32, "GetForegroundWindow", W.HWND)
    cursor = windows.cursor_position()
    previous = foreground()
    set_cursor = windows.bind(user32, "SetCursorPos", W.BOOL, C.c_int, C.c_int)
    key_event = windows.bind(user32, "keybd_event", None, W.BYTE, W.BYTE, W.DWORD, C.c_size_t)
    controller = WhiteboardApplication(app, SnapPreferences())
    confirmed_rectangles = []
    controller.placement.confirmed.connect(confirmed_rectangles.append)
    helper = QProcess()
    results, errors = [], []
    sys.excepthook = lambda typ, value, tb: errors.append(repr(value))
    pressed = set()
    helper_id = None
    helper_pid = None
    mouse_down = False

    def check(label, condition, detail=None):
        results.append({"check": label, "status": "PASS" if condition else "FAIL", "detail": detail})
        print(json.dumps(results[-1]), flush=True)
        if not condition:
            raise AssertionError(label)

    def key(vk, up=False):
        key_event(vk, 0, 2 if up else 0, 0)
        if up:
            pressed.discard(vk)
        else:
            pressed.add(vk)

    def press_creation(release=True):
        key(0x11)
        key(0x12)
        key(ord("W"))
        QTest.qWait(180)
        if release:
            for vk in (ord("W"), 0x12, 0x11):
                key(vk, True)
            QTest.qWait(50)

    def press_capture():
        for vk in (0x11, 0x12, ord('S')):
            key(vk)
        QTest.qWait(100)
        for vk in (ord('S'), 0x12, 0x11):
            key(vk, True)
        QTest.qWait(60)

    def focus_target():
        user32.SetForegroundWindow(helper_id)
        QTest.qWait(80)
        if foreground() != helper_id:
            # Windows may deny a background process foreground activation.
            # Bring only our helper to the top, verify ownership at the target
            # point, then give that window a normal user-style click.
            point = W.POINT(100, 130)
            get_at = windows.bind(user32, "WindowFromPoint", W.HWND, W.POINT)
            get_pid = windows.bind(user32, "GetWindowThreadProcessId", W.DWORD, W.HWND, C.POINTER(W.DWORD))
            pid = W.DWORD()
            # Wait for the separate process's first show/desktop composition.
            # Never click until the actual window under the point is our helper.
            for attempt in range(5):
                user32.SetWindowPos(helper_id, W.HWND(-1), 0, 0, 0, 0, 0x0053)
                QTest.qWait(200)
                get_pid(get_at(point), C.byref(pid))
                if pid.value == helper_pid:
                    break
            helper_rect = W.RECT()
            user32.GetWindowRect(helper_id, C.byref(helper_rect))
            check("Activation click belongs to disposable helper", pid.value == helper_pid,
                  {"found_pid": pid.value, "helper_pid": helper_pid, "launcher_pid": helper.processId(), "helper_hwnd": helper_id,
                   "foreground": foreground(), "rect": [helper_rect.left, helper_rect.top, helper_rect.right, helper_rect.bottom],
                   "process_state": str(helper.state()), "stderr": bytes(helper.readAllStandardError()).decode(errors="replace")})
            old_cursor = windows.cursor_position()
            set_cursor(point.x, point.y)
            QTest.qWait(80)
            actual = W.POINT(*windows.cursor_position())
            get_pid(get_at(actual), C.byref(pid))
            check("Settled activation pointer is over the disposable helper", pid.value == helper_pid)
            mouse = windows.bind(user32, "mouse_event", None, W.DWORD, W.DWORD, W.DWORD, W.DWORD, C.c_size_t)
            mouse(0x0002, 0, 0, 0, 0)
            mouse(0x0004, 0, 0, 0, 0)
            # Let Windows deliver the input before restoring the cursor. Moving
            # it back immediately can send activation to the former location.
            QTest.qWait(120)
            set_cursor(*old_cursor)
            user32.SetWindowPos(helper_id, W.HWND(-2), 0, 0, 0, 0, 0x0013)
            QTest.qWait(120)
        check("External test application has focus", foreground() == helper_id)

    try:
        helper.start(sys.executable, ["-m", "scripts.focus_target"])
        if not helper.waitForStarted(5000) or not helper.waitForReadyRead(5000):
            raise RuntimeError(bytes(helper.readAllStandardError()).decode(errors="replace"))
        # A Windows venv python.exe can launch a child Python process. The HWND
        # belongs to that child, not necessarily QProcess.processId(). Obtain its
        # identity over the owned helper's stdout and verify it before any input.
        identity = json.loads(bytes(helper.readLine()))
        helper_id, helper_pid = identity["hwnd"], identity["pid"]
        get_owner = windows.bind(user32, "GetWindowThreadProcessId", W.DWORD, W.HWND, C.POINTER(W.DWORD))
        owner = W.DWORD()
        get_owner(helper_id, C.byref(owner))
        check("Disposable helper reports its actual window owner", owner.value == helper_pid)
        focus_target()
        base = windows.monitors()[0].rect
        a, b = (round(base.x+130), round(base.y+150)), (round(base.x+630), round(base.y+490))
        set_cursor(*a)
        press_creation(release=False)
        check("First real key press starts placement only", controller.placement.state.anchor == a and not controller.boards,
              {"anchor": controller.placement.state.anchor, "expected": a,
               "cursor": windows.cursor_position(), "boards": len(controller.boards),
               "registered": list(controller.hotkeys.registered), "errors": errors})
        check("Preview does not steal external focus", foreground() == helper_id)
        key(ord("W"))  # repeated key-down without a key-up
        QTest.qWait(100)
        check("MOD_NOREPEAT prevents held shortcut confirmation", controller.placement.state.active and not controller.boards)
        for vk in (ord("W"), 0x12, 0x11):
            key(vk, True)
        QTest.qWait(100)
        check("Releasing shortcut does not confirm", controller.placement.state.active and not controller.boards)
        set_cursor(*b)
        QTest.qWait(100)
        expected = normalized(a, controller.placement.last_point)
        check("First anchor stays fixed as cursor moves", controller.placement.state.anchor == a)
        check("Preview follows cursor", all(o.outline == expected for o in controller.placement.overlays),
              {"expected": vars(expected), "cursor": windows.cursor_position(),
               "last_point": controller.placement.last_point,
               "outlines": [vars(o.outline) if o.outline else None for o in controller.placement.overlays], "errors": errors})
        overlay = controller.placement.overlays[0]
        image = overlay.grab().toImage()
        check("Preview interior remains transparent", image.pixelColor(a[0]-round(base.x)+20, a[1]-round(base.y)+20).alpha() == 0)
        focus_target()
        press_creation()
        check("Second distinct key press creates exactly one board", len(controller.boards) == 1 and not controller.placement.state.active)
        board = controller.boards[0]
        QTest.qWait(150)
        check("Finished paper matches confirmation bounds", board.physical_paper_rect() == confirmed_rectangles[-1])
        check("Confirmed board receives keyboard focus", board.canvas.hasFocus())
        check("Confirmation removes preview and tracking timer", not controller.placement.overlays and not controller.placement.timer.isActive())
        board.minimize_to_tray()
        focus_target()
        set_cursor(*b)
        press_creation()
        # An undersized confirmation preserves the first corner.
        set_cursor(b[0]-20, b[1]-20)
        press_creation()
        check("Undersized confirmation retains placement and first corner", controller.placement.state.anchor == b and len(controller.boards) == 1)
        set_cursor(*a)
        press_creation()
        check("Reverse direction creates a second independent board", len(controller.boards) == 2 and controller.boards[1].physical_paper_rect() == confirmed_rectangles[-1])
        controller.boards[1].minimize_to_tray()
        focus_target()
        press_creation()
        key(0x1B)
        key(0x1B, True)
        QTest.qWait(100)
        check("Real Escape cancels with external application focused", not controller.placement.state.active and len(controller.boards) == 2)
        check("Escape leaves external focus intact", foreground() == helper_id)
        press_capture()
        check('Real Ctrl+Alt+S enters screenshot selection without a board', controller.capture.active and len(controller.boards) == 2)
        check('Screenshot selection keeps the external application focused', foreground() == helper_id)
        key(0x1B)
        key(0x1B, True)
        QTest.qWait(80)
        check('Real Escape cancels screenshot selection', not controller.capture.active and len(controller.boards) == 2)
        expected_pixel = windows.capture_rect(Rect(250,330,250,140)).pixelColor(100,50).name()
        press_capture()
        start, end = (250,330), (500,470)
        get_at = windows.bind(user32, 'WindowFromPoint', W.HWND, W.POINT)
        check('Screenshot click target belongs to our capture overlay',
              get_at(W.POINT(*start)) in {int(o.winId()) for o in controller.capture.overlays})
        mouse = windows.bind(user32, 'mouse_event', None, W.DWORD, W.DWORD, W.DWORD, W.DWORD, C.c_size_t)
        set_cursor(*start)
        mouse(0x0002,0,0,0,0)
        mouse_down = True
        QTest.qWait(80)
        check('Real screenshot mouse press records physical first corner', controller.capture.anchor == start,
              controller.capture.anchor)
        set_cursor(*end)
        QTest.qWait(80)
        mouse(0x0004,0,0,0,0)
        mouse_down = False
        QTest.qWait(180)
        check('Real screenshot mouse release creates exactly one image board', len(controller.boards) == 3 and not controller.capture.active)
        captured = controller.boards[-1].canvas.document.objects[0]
        check('Real screenshot preserves physical size and starts locked', isinstance(captured,ImageObject)
              and captured.locked and captured.pixel_size == (250,140))
        captured_pixel = images.decoded(captured.png).pixelColor(100,50).name()
        check('Real screenshot reads the disposable helper blank paper', captured_pixel == expected_pixel,
              {'expected': expected_pixel, 'captured': captured_pixel})
        controller.boards[-1].minimize_to_tray()
        focus_target()
        press_creation()
        check('Ctrl+Alt+W still starts first-corner placement after screenshot', controller.placement.state.active
              and len(controller.boards) == 3 and not controller.capture.active)
        key(0x1B)
        key(0x1B, True)
        QTest.qWait(80)
        check("No callback exceptions", not errors, errors)
    finally:
        if mouse_down:
            windows.bind(user32, 'mouse_event', None, W.DWORD, W.DWORD, W.DWORD, W.DWORD, C.c_size_t)(0x0004,0,0,0,0)
        for vk in tuple(pressed):
            key(vk, True)
        controller.cleanup()
        if helper_id:
            post = windows.bind(user32, "PostMessageW", W.BOOL, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
            post(helper_id, 0x0010, 0, 0)
        if helper.state() != QProcess.ProcessState.NotRunning and not helper.waitForFinished(2000):
            helper.terminate()
            helper.waitForFinished(2000)
        guard.close()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        set_cursor(*cursor)
        if previous:
            user32.SetForegroundWindow(previous)
        Path(".test-artifacts").mkdir(exist_ok=True)
        Path(".test-artifacts/hotkey-workflow.json").write_text(json.dumps({"results": results, "exceptions": errors}, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
