"""Opt-in real Windows hold/release keyboard test using an owned external focus target.

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
    messages = []
    controller.placement.message.connect(messages.append)
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

        def begin(trigger, point):
            set_cursor(*point)
            for vk in (0x11, 0x12, ord(trigger)):
                key(vk)
            QTest.qWait(100)

        def release_all():
            for vk in tuple(pressed):
                key(vk, True)
            QTest.qWait(80)

        def idle(label):
            check(label, not controller.placement.overlays and not controller.capture.overlays
                  and not controller.placement.timer.isActive() and not controller.capture.tracking.isActive()
                  and not controller.hotkeys.hold.timer.isActive() and not controller.hotkeys.hold.blocked
                  and controller.placement.session.owner is None)

        begin('W', a)
        check('Hold starts placement without a board', controller.placement.state.anchor == a and not controller.boards, {"anchor":controller.placement.state.anchor,"messages":messages,"registered":list(controller.hotkeys.registered)})
        check('Passive preview preserves external focus', foreground() == helper_id)
        set_cursor(*b)
        QTest.qWait(100)
        expected = normalized(a, controller.placement.last_point)
        check('Held preview follows pointer with fixed anchor', all(o.outline == expected for o in controller.placement.overlays))
        overlay = controller.placement.overlays[0]
        image = overlay.grab().toImage()
        check('Preview interior remains transparent', image.pixelColor(a[0]-round(base.x)+20, a[1]-round(base.y)+20).alpha() == 0)
        for _ in range(30):
            key(ord('W'))
            QTest.qWait(40)
        check('Thirty repeated key-downs cannot confirm or restart', controller.placement.state.active and not controller.boards)
        key(ord('S'))
        QTest.qWait(100)
        check('Competing capture is ignored during W hold', not controller.capture.active and controller.placement.state.active)
        key(ord('W'), True)
        QTest.qWait(100)
        check('Trigger-first release creates exactly one board', len(controller.boards) == 1 and not controller.placement.state.active)
        board = controller.boards[-1]
        check('Release paper matches sampled bounds', board.physical_paper_rect() == confirmed_rectangles[-1])
        check('Completed board gets canvas focus', board.canvas.hasFocus())
        key(0x11, True)
        key(0x12, True)
        for _ in range(5):
            key(ord('S'))
            QTest.qWait(25)
        check('Competing held S cannot switch focused board to Shape', board.canvas.tool == 'Draw')
        release_all()
        idle('Completion drains keys and removes every preview/timer')
        board.minimize_to_tray()

        for modifier, name in ((0x11, 'Control'), (0x12, 'Alt')):
            focus_target()
            count = len(controller.boards)
            begin('W', b)
            set_cursor(*a)
            QTest.qWait(40)
            key(modifier, True)
            QTest.qWait(100)
            check(name+'-first release finishes reverse placement once', len(controller.boards) == count+1
                  and controller.boards[-1].physical_paper_rect() == confirmed_rectangles[-1])
            for _ in range(5):
                key(ord('W'))
                QTest.qWait(25)
            check(name+'-first held repeats leave no new outline', not controller.placement.state.active and len(controller.boards) == count+1)
            release_all()
            idle(name+'-first release cleanup is idle')
            controller.boards[-1].minimize_to_tray()

        focus_target()
        count = len(controller.boards)
        begin('W', a)
        key(0x1B)
        QTest.qWait(60)
        key(0x1B, True)
        check('Escape cancels while Control Alt W remain held externally', not controller.placement.state.active and foreground() == helper_id, {'placement':controller.placement.state.active,'foreground':foreground(),'helper':helper_id,'hold':controller.hotkeys.hold.active,'blocked':list(controller.hotkeys.hold.blocked),'errors':errors})
        for _ in range(10):
            key(ord('W'))
            QTest.qWait(30)
        check('Cancelled held repeats never restart', not controller.placement.state.active and len(controller.boards) == count)
        release_all()
        idle('Cancelled hold cleanup is idle')
        begin('W', a)
        key(ord('W'), True)
        QTest.qWait(60)
        check('Immediate zero-area release cancels without waiting', not controller.placement.state.active and len(controller.boards) == count)
        release_all()
        idle('Too-small release cleanup is idle')

        focus_target()
        start, end = (250,330), (500,470)
        expected_pixel = windows.capture_rect(Rect(250,330,250,140)).pixelColor(100,50).name()
        begin('S', start)
        check('S hold anchors at shortcut activation without capture', controller.capture.anchor == start and len(controller.boards) == count)
        check('Screenshot preview preserves external focus', foreground() == helper_id)
        get_at = windows.bind(user32, 'WindowFromPoint', W.HWND, W.POINT)
        check('Screenshot preview is mouse transparent', get_at(W.POINT(*start)) not in {int(o.winId()) for o in controller.capture.overlays})
        set_cursor(*end)
        QTest.qWait(80)
        check('Screenshot preview tracks while held', all(o.outline == Rect(250,330,250,140) for o in controller.capture.overlays))
        key(0x11, True)
        QTest.qWait(250)
        check('S modifier-first release captures without any mouse input', len(controller.boards) == count+1 and not controller.capture.active)
        captured = controller.boards[-1].canvas.document.objects[0]
        check('Captured image starts locked at physical size', isinstance(captured, ImageObject) and captured.locked and captured.pixel_size == (250,140))
        check('Captured pixels exclude preview', images.decoded(captured.png).pixelColor(100,50).name() == expected_pixel)
        key(0x12, True)
        for _ in range(8):
            key(ord('S'))
            QTest.qWait(25)
        check('Remaining capture S cannot activate the Shape tool', controller.boards[-1].canvas.tool == 'Draw')
        release_all()
        idle('Screenshot completion cleanup is idle')
        controller.boards[-1].minimize_to_tray()
        focus_target()
        begin('S', a)
        key(0x1B)
        QTest.qWait(60)
        key(0x1B, True)
        check('Escape cancels an S hold before capture', not controller.capture.active)
        release_all()
        idle('Screenshot cancellation cleanup is idle')
        begin('W', a)
        set_cursor(*b)
        QTest.qWait(30)
        release_all()
        check('Fresh W works immediately after cancelled capture', len(controller.boards) == count+2)
        idle('Final gesture leaves no tracking resources')
        check('No callback exceptions', not errors, errors)
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
