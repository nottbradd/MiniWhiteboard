"""Opt-in Windows desktop integration check. Briefly opens owned test windows.

Run separately from offscreen tests: .venv\\Scripts\\python -m scripts.native_smoke
No synthetic input is sent to third-party applications. Cursor/focus are restored.
"""
import ctypes as C
import argparse
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "windows"

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from mini_whiteboard import windows
from mini_whiteboard.app import WhiteboardApplication
from mini_whiteboard.document import Shape, Stroke, Text
from mini_whiteboard.geometry import Rect, normalized
from mini_whiteboard.snapping import SnapPreferences


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path('verification/v133-review01/native-smoke'))
    parser.add_argument('--allow-shortcut-conflict', action='store_true',
                        help='Record unavailable W as NOT RUN and continue unrelated native checks.')
    args=parser.parse_args()
    windows.enable_dpi_awareness()
    app = QApplication([])
    results = []
    errors = []
    sys.excepthook = lambda kind, value, tb: errors.append(repr(value))
    foreground = windows.bind(windows.user32, "GetForegroundWindow", W.HWND)()
    old_cursor = windows.cursor_position()
    set_cursor = windows.bind(windows.user32, "SetCursorPos", W.BOOL, C.c_int, C.c_int)
    guard = windows.SingleInstance()
    if not guard.acquired:
        raise SystemExit("Exit an existing Mini Whiteboard instance before this test.")
    controller = WhiteboardApplication(app, SnapPreferences())
    confirmed_rectangles = []
    controller.placement.confirmed.connect(confirmed_rectangles.append)
    artifacts = args.output
    artifacts.mkdir(parents=True,exist_ok=True)

    def check(label, condition, detail=None):
        entry = {"check": label, "status": "PASS" if condition else "FAIL", "detail": detail}
        results.append(entry)
        print(json.dumps(entry), flush=True)
        if not condition:
            raise AssertionError(label)

    try:
        QTest.qWait(150)
        if args.allow_shortcut_conflict and windows.CREATE_HOTKEY not in controller.hotkeys.registered:
            results.append({'check': 'Native Win+Alt+W registration', 'status': 'NOT RUN',
                            'detail': 'Shortcut is already registered on this desktop; direct controller checks follow.'})
        else:
            check("Native creation hotkey registration", windows.CREATE_HOTKEY in controller.hotkeys.registered)
        check("Launch creates no board", not controller.boards)
        check("Placement timer idle", not controller.placement.timer.isActive())
        monitors = windows.monitors()
        print("MONITORS " + json.dumps([{"name": m.name, "rect": vars(m.rect), "scale": m.scale} for m in monitors]), flush=True)
        for i, monitor in enumerate(monitors):
            rect = Rect(monitor.rect.x+90, monitor.rect.y+110, round(420*monitor.scale), round(300*monitor.scale))
            controller.create_board(rect)
            board = controller.boards[-1]
            QTest.qWait(150)
            check(f"Physical paper bounds monitor {i+1}", board.physical_paper_rect() == rect,
                  {"expected": vars(rect), "actual": vars(board.physical_paper_rect()), "dpr": board.devicePixelRatioF()})
            check(f"New board focuses canvas monitor {i+1}", board.canvas.hasFocus())
            from .topmost_check import run_topmost_checks
            run_topmost_checks(board, check)
            board.canvas.document.add(Text((30, 30), "Mini Whiteboard", 28))
            board.canvas.document.add(Text((30, 90), "Hold → move → release", 14))
            board.canvas.document.add(Shape("Rounded rectangle", (30, 140), (165, 225)))
            board.canvas.document.add(Shape("Arrow", (195, 180), (340, 180)))
            board.canvas.document.add(Stroke(((45, 250), (85, 235), (120, 260), (160, 240)), 4))
            board.canvas.update()
            QTest.qWait(100)
            board.grab().save(str(artifacts/f"board-monitor-{i+1}.png"))
            before = board.canvas.document.objects
            controller.remember_minimized(board)
            board.minimize_to_tray()
            QTest.qWait(50)
            controller.restore_board(board)
            QTest.qWait(150)
            check(f"Restored board focuses canvas monitor {i+1}", board.canvas.hasFocus())
            check(f"Minimise retains model monitor {i+1}", board.canvas.document.objects == before)
            QTest.keyClick(board.canvas, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
            check(f"Restored keyboard undo monitor {i+1}", board.canvas.document.objects == before[:-1])
            QTest.keyClick(board.canvas, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
            check(f"Restored keyboard redo monitor {i+1}", board.canvas.document.objects == before)
            board.canvas.toggle_help()
            QTest.qWait(80)
            check(f"F1 help preserves canvas focus monitor {i+1}", board.canvas.hasFocus())
            board.canvas.help_panel.grab().save(str(artifacts/f"help-monitor-{i+1}.png"))
            board.canvas.toggle_help()
            from .editing_smoke import run_editing_checks
            run_editing_checks(board, check, artifacts)
            from .polish_smoke import run_polish_checks
            run_polish_checks(board, check, artifacts)
            board.close()
            QTest.qWait(50)
        # Controller/overlay checks use direct gesture events. The separate
        # hotkey_workflow_check exercises real external-focus native input.
        post = windows.bind(windows.user32, "PostThreadMessageW", W.BOOL,
                            W.DWORD, W.UINT, W.WPARAM, W.LPARAM)
        tid = windows.bind(windows.kernel32, "GetCurrentThreadId", W.DWORD)()
        controller.placement.press()
        QTest.qWait(100)
        check("Native windows show a controller-started preview", controller.placement.state.active)
        check("Native preview windows cover their physical monitors",
              all(windows.window_rect(o) == o.monitor.rect for o in controller.placement.overlays),
              [{"actual": vars(windows.window_rect(o)), "expected": vars(o.monitor.rect)} for o in controller.placement.overlays])
        check("Preview remains non-focusing", windows.user32.GetForegroundWindow() != int(controller.placement.overlays[0].winId()))
        post(tid, windows.WM_HOTKEY, windows.ESCAPE_HOTKEY, 0)
        QTest.qWait(100)
        check("Native Escape event cancels", not controller.placement.state.active)
        check("Cancellation releases Escape", windows.ESCAPE_HOTKEY not in controller.hotkeys.registered)
        check("Cancellation removes overlays and timer", not controller.placement.overlays and not controller.placement.timer.isActive())
        origin = monitors[0].rect
        first = (round(origin.x+130), round(origin.y+150))
        second = (round(origin.x+630), round(origin.y+490))
        requested_first = first
        if not set_cursor(*first):
            raise C.WinError(C.get_last_error())
        # Let pending desktop cursor motion settle, then verify the app captures
        # that actual pre-hotkey position. The separate real-key suite also
        # asserts its fixed requested coordinates without this settling step.
        QTest.qWait(80)
        first = windows.cursor_position()
        controller.placement.press()
        QTest.qWait(100)
        check("Native placement samples first cursor point", controller.placement.state.anchor == first,
              {"requested": requested_first, "before_hotkey": first,
               "anchor": controller.placement.state.anchor, "cursor": windows.cursor_position()})
        set_cursor(*second)
        QTest.qWait(100)
        # The desktop can move the cursor after SetCursorPos (observed one-pixel
        # motion in this session). Compare to the actual sampled endpoint, not
        # the requested synthetic target. The preview may be one timer frame old.
        sampled = controller.placement.last_point
        expected = normalized(first, sampled)
        check("Native preview tracks physical cursor movement",
              sampled != first and all(o.outline == expected for o in controller.placement.overlays),
              {"expected": vars(expected), "cursor": windows.cursor_position(),
               "last_point": controller.placement.last_point,
               "outlines": [vars(o.outline) if o.outline else None for o in controller.placement.overlays]})
        controller.placement.release()
        QTest.qWait(100)
        check("Release creates matching paper",
              len(controller.boards) == 1 and bool(confirmed_rectangles) and
              controller.boards[0].physical_paper_rect() == confirmed_rectangles[-1],
              {"confirmed": vars(confirmed_rectangles[-1]) if confirmed_rectangles else None,
               "paper": vars(controller.boards[0].physical_paper_rect()) if controller.boards else None})
        controller.boards[0].close()
        QTest.qWait(50)
        from .v11_smoke import run_v11_checks
        run_v11_checks(controller, check, artifacts)
        duplicate = windows.SingleInstance()
        check("Single-instance mutex rejects duplicate", not duplicate.acquired)
        duplicate.close()
        check("No Qt callback exceptions", not errors, errors)
        check("Native tracking timers are stopped before idle measurement",
              not controller.hotkeys.hold.timer.isActive() and not controller.placement.timer.isActive()
              and not controller.capture.tracking.isActive() and not controller.capture.timeout.isActive())
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QTest.qWait(250)  # Finish owned-window teardown before measuring idle.
        start_cpu, start_wall = time.process_time(), time.monotonic()
        QTest.qWait(3000)
        cpu, wall = time.process_time()-start_cpu, time.monotonic()-start_wall
        check("Idle smoke CPU below 10% of one core", cpu/wall < .1, {"cpu_seconds": cpu, "wall_seconds": wall})
    finally:
        controller.cleanup()
        guard.close()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        set_cursor(*old_cursor)
        if foreground:
            windows.user32.SetForegroundWindow(foreground)
        (artifacts/"native-smoke.json").write_text(json.dumps({"results": results, "exceptions": errors}, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
