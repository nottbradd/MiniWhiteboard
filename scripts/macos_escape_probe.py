"""Run on a Mac, focus another app, then press bare Escape within 45 seconds."""
import argparse
import json
import os
from pathlib import Path
import sys


def main():
    if sys.platform != "darwin":
        raise SystemExit("NOT RUN: this probe requires a real macOS desktop.")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=45)
    args = parser.parse_args()
    import AppKit
    import Quartz
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from mini_whiteboard.platform.macos.hotkeys import MacHotkeys
    from mini_whiteboard.platform.macos.runtime import MacRuntime
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    runtime = MacRuntime()
    runtime.configure_application(app)
    keys = MacHotkeys(app)
    result = {"status": "FAILED", "external_escape_observed": False,
              "accessibility_already_granted": bool(Quartz.AXIsProcessTrusted()),
              "method": "temporary Carbon RegisterEventHotKey, keycode 53, no modifiers",
              "detail": "No external Escape event observed before timeout."}
    def observed():
        foreground = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
        result["frontmost_pid"] = int(foreground.processIdentifier()) if foreground else None
        result["external_escape_observed"] = result["frontmost_pid"] not in (None, os.getpid())
        result["status"] = "PASSED" if result["external_escape_observed"] and not result["accessibility_already_granted"] else "INCONCLUSIVE"
        result["detail"] = "Event received. A permission-free pass requires another app focused and Accessibility not already granted."
        app.quit()
    keys.events.cancel.connect(observed)
    print("Focus another application and press bare Escape. No input will be synthesized; no Accessibility prompt is requested.", flush=True)
    try:
        if keys.enable_escape():
            QTimer.singleShot(args.seconds*1000, app.quit)
            app.exec()
        else:
            result["detail"] = "Bare Escape registration was rejected; use menu-bar cancellation and record OS version."
    finally:
        keys.close()
    output = Path("verification/macos-escape-probe.json")
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
