"""Owned native Mac windows; actual global keystrokes/Spaces remain manual checks."""
import argparse
import json
import os
from pathlib import Path
import sys
import time


def main():
    if sys.platform != "darwin":
        raise SystemExit("NOT RUN: native Mac checks require macOS 14+.")
    os.environ["QT_QPA_PLATFORM"] = "cocoa"
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", action="store_true", help="Also exercise ScreenCaptureKit; may request Screen Recording access")
    args = parser.parse_args()
    import AppKit
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon
    from mini_whiteboard.app import WhiteboardApplication
    from mini_whiteboard.document import Shape, Text
    from mini_whiteboard.geometry import Rect
    from mini_whiteboard.platform import get_platform
    from mini_whiteboard.platform.macos.desktop import native_window
    from mini_whiteboard.snapping import SnapPreferences
    platform = get_platform()
    platform.runtime.prepare()
    guard = platform.runtime.single_instance()
    if not guard.acquired:
        raise SystemExit("Quit Mini Whiteboard before this native check.")
    app = QApplication([])
    platform.runtime.configure_application(app)
    results, exceptions = [], []
    old_hook = sys.excepthook
    sys.excepthook = lambda typ, error, tb: exceptions.append(repr(error))
    controller = None
    def check(label, condition, detail=None):
        results.append(dict(check=label, status="PASSED" if condition else "FAILED", detail=detail))
        print(json.dumps(results[-1]), flush=True)
        if not condition:
            raise AssertionError(label)
    try:
        controller = WhiteboardApplication(app, SnapPreferences(), platform)
        check("Status item available; startup has no boards", QSystemTrayIcon.isSystemTrayAvailable() and not controller.boards)
        check("Accessory activation policy", AppKit.NSApplication.sharedApplication().activationPolicy() == AppKit.NSApplicationActivationPolicyAccessory)
        duplicate = platform.runtime.single_instance()
        check("Duplicate process lock rejected", not duplicate.acquired)
        duplicate.close()
        for display in platform.desktop.displays():
            rect = Rect(display.rect.x+60, display.rect.y+80, 440, 320)
            board = controller.create_board(rect)
            app.processEvents()
            check("Logical paper placement: "+display.name, board is not None and board.physical_paper_rect() == rect,
                  dict(scale=display.scale, bounds=rect.__dict__))
            native = native_window(board)
            check("Floating level and visible when inactive", native.level() == AppKit.NSFloatingWindowLevel and not native.hidesOnDeactivate())
            check("Normal Space membership", not (native.collectionBehavior() & AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces))
            board.canvas.document.add(Shape("Rectangle", (40,40), (140,110), 3))
            board.canvas.document.add(Text((45,130), "Mac text", 20))
            board.canvas.select_all()
            board.canvas.setFocus()
            QTest.keyClick(board.canvas, Qt.Key.Key_D, Qt.KeyboardModifier.ControlModifier)
            check("Native Qt Command-duplicate route", len(board.canvas.document.objects) == 4)
            QTest.keyClick(board.canvas, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
            check("Native Qt Command-undo route", len(board.canvas.document.objects) == 2)
            saved = board.canvas.document.objects
            board.minimize_to_tray()
            check("Minimise hides and retains document", not board.isVisible() and board.canvas.document.objects == saved)
            board.restore()
            app.processEvents()
            check("Restore focuses the same canvas", board.isVisible() and board.canvas.hasFocus())
            board.close()
            app.processEvents()
        check("Last board close leaves status app alive", not controller.boards and controller.tray.isVisible() and not app.quitOnLastWindowClosed())
        if args.capture:
            display = platform.desktop.displays()[0]
            rect = Rect(display.rect.x+100, display.rect.y+150, 300, 200)
            images, failures = [], []
            platform.capture.capture_region(rect, images.append, lambda e: failures.append(str(e)))
            deadline = time.monotonic()+17
            while not images and not failures and time.monotonic() < deadline:
                QTest.qWait(25)
            check("ScreenCaptureKit returns a nonempty native image", bool(images) and not images[0].isNull(), failures)
            board = controller.create_screenshot_board(rect, images[0])
            check("Capture creates locked source ready to draw", board.canvas.document.objects[0].locked and board.canvas.tool == "Draw")
            board.close()
        else:
            results.append(dict(check="ScreenCaptureKit", status="NOT RUN", detail="Use --capture after checking permission handling."))
        before = time.process_time()
        QTest.qWait(1000)
        cpu = time.process_time()-before
        check("Idle CPU below 10% of one core", cpu < .1, cpu)
        controller.cleanup()
        check("Global registrations released", not controller.hotkeys.registered)
        check("No Qt callback exceptions", not exceptions, exceptions)
    except Exception as error:
        results.append(dict(check="Native smoke completed", status="FAILED", detail=str(error)))
    finally:
        if controller is not None:
            controller.cleanup()
        guard.close()
        sys.excepthook = old_hook
        output = Path("verification/macos-native-smoke.json")
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return int(any(row["status"] == "FAILED" for row in results))


if __name__ == "__main__":
    raise SystemExit(main())
