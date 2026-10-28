"""Opt-in real Windows hold/release keyboard test using an owned external focus target.

Temporarily moves the cursor and sends Win+Alt+Shift+W/Escape. Never types into an
unowned window; aborts if the foreground window is unexpected. Restores cursor
and foreground on exit, and closes only the disposable windows it created.
"""
import ctypes as C
import argparse
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "windows"
from PySide6.QtCore import QProcess, QCoreApplication, QEvent, Qt, QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from mini_whiteboard import windows, images
from mini_whiteboard.document import ImageObject
from mini_whiteboard.snapping import SnapPreferences
from mini_whiteboard.app import WhiteboardApplication
from mini_whiteboard.geometry import Rect, normalized


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path('verification/v133-review02/hotkey-workflow.json'))
    parser.add_argument('--hide-shortcut', choices=('default','shift'), default='default',
                        help='Select and reload the shipped persisted Windows Hide All configuration.')
    args = parser.parse_args()
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
    settings_directory = tempfile.TemporaryDirectory(prefix='miniwhiteboard-shortcut-test-')
    settings_path = str(Path(settings_directory.name)/'settings.ini')
    controller = WhiteboardApplication(app, SnapPreferences(settings=QSettings(settings_path,QSettings.Format.IniFormat)))
    warnings = []
    controller.notify = warnings.append
    hide_modifiers = (0x11,0x12,0x10) if args.hide_shortcut == 'shift' else (0x11,0x12)
    controller.rebuild_menu()
    choices = next(a.menu() for a in controller.menu.actions() if a.text() == 'Hide All shortcut')
    label = 'Ctrl+Alt+Shift+H' if args.hide_shortcut == 'shift' else 'Ctrl+Alt+H'
    next(a for a in choices.actions() if a.text() == label).trigger()
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
        key_event(vk, user32.MapVirtualKeyW(vk, 0), (2 if up else 0) | (1 if vk in (0x5B, 0x5C, 0xA5) else 0), 0)
        if up:
            pressed.discard(vk)
        else:
            pressed.add(vk)

    def press_creation(release=True):
        key(0x5B)
        key(0xA4)
        key(0xA0)
        key(ord("W"))
        QTest.qWait(180)
        if release:
            for vk in (ord("W"), 0xA0, 0xA4, 0x5B):
                key(vk, True)
            QTest.qWait(50)

    def press_capture():
        for vk in (0x5B, 0xA4, 0xA0, ord('Q')):
            key(vk)
        QTest.qWait(100)
        for vk in (ord('Q'), 0xA0, 0xA4, 0x5B):
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
            check("Settled activation pointer is over the disposable helper", pid.value == helper_pid,
                  {'expected':[point.x,point.y],'actual':[actual.x,actual.y],
                   'target':get_at(actual),'target_pid':pid.value,'helper_pid':helper_pid})
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
        saved = SnapPreferences(settings=QSettings(settings_path,QSettings.Format.IniFormat))
        check('Shipped menu selection persists and reloads the Windows H choice',
              saved.windows_hide == args.hide_shortcut and controller.hotkeys.hide_shortcut == saved.windows_hide)
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
            for vk in (0x5B, 0xA4, 0xA0, ord(trigger)):
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
        preview_alpha=image.pixelColor(round((a[0]+b[0])/2-base.x),round((a[1]+b[1])/2-base.y)).alpha()
        preview_policy=overlay.display_policy
        check('Preview keeps a low tint or unfilled accessibility fallback',
              0<preview_alpha<130 if preview_policy.transparency and not preview_policy.high_contrast else preview_alpha==0,
              {'alpha':preview_alpha,'policy':vars(preview_policy)})
        for _ in range(30):
            key(ord('W'))
            QTest.qWait(40)
        check('Thirty repeated key-downs cannot confirm or restart', controller.placement.state.active and not controller.boards)
        key(ord('Q'))
        QTest.qWait(100)
        check('Competing capture is ignored during W hold', not controller.capture.active and controller.placement.state.active)
        key(ord('W'), True)
        QTest.qWait(100)
        check('Trigger-first release creates exactly one board', len(controller.boards) == 1 and not controller.placement.state.active)
        board = controller.boards[-1]
        check('Release paper matches sampled bounds', board.physical_paper_rect() == confirmed_rectangles[-1])
        check('Completed board gets canvas focus', board.canvas.hasFocus())
        key(0x5B, True)
        key(0xA4, True)
        for _ in range(5):
            key(ord('Q'))
            QTest.qWait(25)
        check('Competing held Q cannot switch focused board to Shape', board.canvas.tool == 'Draw')
        release_all()
        idle('Completion drains keys and removes every preview/timer')
        board.minimize_to_tray()

        for modifier, name in ((0x5B, 'Windows'), (0xA4, 'Alt'), (0xA0, 'Shift')):
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
        check('Escape cancels while Windows Alt Shift W remain held externally', not controller.placement.state.active and foreground() == helper_id, {'placement':controller.placement.state.active,'foreground':foreground(),'helper':helper_id,'hold':controller.hotkeys.hold.active,'blocked':list(controller.hotkeys.hold.blocked),'errors':errors})
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
        begin('Q', start)
        check('Q hold anchors at shortcut activation without capture', controller.capture.anchor == start and len(controller.boards) == count)
        check('Screenshot preview preserves external focus', foreground() == helper_id)
        get_at = windows.bind(user32, 'WindowFromPoint', W.HWND, W.POINT)
        check('Screenshot preview is mouse transparent', get_at(W.POINT(*start)) not in {int(o.winId()) for o in controller.capture.overlays})
        set_cursor(*end)
        QTest.qWait(80)
        check('Screenshot preview tracks while held', all(o.outline == Rect(250,330,250,140) for o in controller.capture.overlays))
        key(0x5B, True)
        QTest.qWait(250)
        check('Q modifier-first release captures without any mouse input', len(controller.boards) == count+1 and not controller.capture.active)
        captured = controller.boards[-1].canvas.document.objects[0]
        check('Captured image starts locked at physical size', isinstance(captured, ImageObject) and captured.locked and captured.pixel_size == (250,140))
        check('Captured pixels exclude preview', images.decoded(captured.png).pixelColor(100,50).name() == expected_pixel)
        key(0xA4, True)
        for _ in range(8):
            key(ord('Q'))
            QTest.qWait(25)
        check('Remaining capture Q cannot activate the Shape tool', controller.boards[-1].canvas.tool == 'Draw')
        release_all()
        idle('Screenshot completion cleanup is idle')
        controller.boards[-1].minimize_to_tray()
        focus_target()
        begin('Q', a)
        key(0x1B)
        QTest.qWait(60)
        key(0x1B, True)
        check('Escape cancels an Q hold before capture', not controller.capture.active)
        release_all()
        idle('Screenshot cancellation cleanup is idle')
        begin('W', a)
        set_cursor(*b)
        QTest.qWait(30)
        release_all()
        check('Fresh W works immediately after cancelled capture', len(controller.boards) == count+2)
        idle('Final gesture leaves no tracking resources')
        from mini_whiteboard.document import Text
        board = controller.boards[-1]
        board.canvas.begin_editing(Text((30, 40), 'creation while editing'))
        QTest.qWait(80)
        check('Creation audit begins with a focused editor', board.canvas.editor.hasFocus())
        count = len(controller.boards)
        begin('W', a)
        set_cursor(*b)
        release_all()
        QTest.qWait(100)
        check('Native W hold from an editor creates exactly one new board', len(controller.boards) == count+1)
        check('New-board activation commits the old editor once', board.canvas.editor is None
              and len(board.canvas.document.objects) == 1
              and board.canvas.document.objects[0].text == 'creation while editing')
        board = controller.boards[-1]
        board.canvas.open_palette()
        QTest.qWait(60)
        check('Creation audit opens a temporary palette', board.canvas.palette is not None
              and board.canvas.palette.isVisible())
        count = len(controller.boards)
        begin('Q', a)
        key(0x1B)
        QTest.qWait(60)
        key(0x1B, True)
        release_all()
        check('Native capture cancellation with a popup creates no extra board', len(controller.boards) == count
              and not controller.capture.active)
        board.canvas.stop_transient_ui()
        idle('Editor and popup creation audits leave no tracking resources')
        from mini_whiteboard.platform.base import HIDE_HOTKEY
        check('Native H registers alongside W and Q', HIDE_HOTKEY in controller.hotkeys.registered,
              {'shipped_chord': label,
               'default_registration_warnings': warnings})
        manually_hidden = controller.boards[0]
        manually_hidden.minimize_to_tray()
        visible = [b for b in controller.boards if b.isVisible()]
        snapshot = {b: (b.geometry(), b.canvas.document.objects, list(b.canvas.document.history),
                        set(b.canvas.selected_ids)) for b in visible}
        focus_target()
        for vk in (*hide_modifiers, ord('H')):
            key(vk)
        QTest.qWait(140)
        check('Native H hides exactly the visible batch', set(controller.hidden_batch) == set(visible)
              and all(not b.isVisible() for b in visible))
        for _ in range(6):
            key(ord('H'))
            QTest.qWait(20)
        key(0x11, True)
        key(ord('H'))
        QTest.qWait(60)
        check('Native H held repeats and modifier-first release cannot restore',
              all(not b.isVisible() for b in visible))
        key(ord('H'), True)
        key(0x12, True)
        if args.hide_shortcut == 'shift':
            key(0x10, True)
        QTest.qWait(80)
        check('Native H physical release stops its tracker without toggling',
              not controller.hotkeys.hide_latch.timer.isActive() and all(not b.isVisible() for b in visible))
        focus_target()
        for vk in (*hide_modifiers, ord('H')):
            key(vk)
        QTest.qWait(180)
        check('Native Restore All preserves the external foreground application', foreground() == helper_id)
        check('Native Restore All excludes manually minimized boards',
              all(b.isVisible() for b in visible) and not manually_hidden.isVisible())
        for vk in (ord('H'), *reversed(hide_modifiers)):
            key(vk, True)
        QTest.qWait(300)
        check('Native restore has no late activation or geometry/history/selection changes',
              foreground() == helper_id and all(not b.activation_timer.isActive() for b in visible)
              and all(snapshot[b] == (b.geometry(), b.canvas.document.objects,
                                      b.canvas.document.history, b.canvas.selected_ids) for b in visible))
        check('No callback exceptions', not errors, errors)
    finally:
        if mouse_down:
            windows.bind(user32, 'mouse_event', None, W.DWORD, W.DWORD, W.DWORD, W.DWORD, C.c_size_t)(0x0004,0,0,0,0)
        for vk in tuple(pressed):
            key(vk, True)
        controller.cleanup()
        settings_directory.cleanup()
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
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps({"results": results, "exceptions": errors}, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
