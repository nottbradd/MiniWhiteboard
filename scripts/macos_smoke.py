"""Headless macOS dependency/import checks; never register keys or request capture."""
import argparse
import ctypes
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import sysconfig


def build_environment():
    versions = {}
    for name in ("PySide6", "PyInstaller", "pyobjc-core", "pyobjc-framework-Cocoa",
                 "pyobjc-framework-Quartz", "pyobjc-framework-ScreenCaptureKit",
                 "pyobjc-framework-CoreMedia", "pyobjc-framework-Vision", "pyobjc-framework-CoreML"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "not installed yet"
    try:
        from PySide6.QtCore import qVersion
        versions["Qt"] = qVersion()
    except ImportError:
        versions["Qt"] = "not installed yet"
    result = dict(macOS=platform.mac_ver()[0], cpu=platform.machine(),
                  python=sys.version, python_platform=sysconfig.get_platform(),
                  packages=versions, source_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  runner_os=os.environ.get('RUNNER_OS'), runner_arch=os.environ.get('RUNNER_ARCH'))
    if sys.platform == "darwin":
        result["python_binary"] = subprocess.check_output(
            ["/usr/bin/file", "-b", str(Path(sys.executable).resolve())], text=True).strip()
    return result


def run_smoke():
    if sys.platform != "darwin":
        raise RuntimeError("Mac import smoke checks must run on macOS.")
    modules = ("objc", "Foundation", "AppKit", "Quartz", "CoreMedia", "ScreenCaptureKit", "Vision", "CoreML")
    for name in modules:
        importlib.import_module(name)
    for name in ("runtime", "desktop", "hotkeys", "capture"):
        importlib.import_module("mini_whiteboard.platform.macos." + name)
    from PySide6.QtCore import QCoreApplication
    from mini_whiteboard.platform import get_platform
    if QCoreApplication.instance() is not None:
        raise RuntimeError("Run this check in a fresh process, before QApplication.")
    selected = get_platform()
    if selected.name != "macos":
        raise RuntimeError("Production platform selection did not select macOS.")
    selected.runtime.prepare()
    importlib.import_module("mini_whiteboard.app")
    unwanted = [name for name in sys.modules if name == "mini_whiteboard.windows"
                or name.startswith("mini_whiteboard.platform.windows")]
    if unwanted:
        raise RuntimeError("Windows startup modules were imported: " + ", ".join(unwanted))
    if QCoreApplication.instance() is not None or selected.capture._capture is not None:
        raise RuntimeError("Platform selection eagerly created capture Qt objects.")
    import ScreenCaptureKit
    if not hasattr(ScreenCaptureKit, "SCScreenshotManager"):
        raise RuntimeError("ScreenCaptureKit still-image API is unavailable.")
    carbon = ctypes.CDLL("/System/Library/Frameworks/Carbon.framework/Carbon")
    for name in ("RegisterEventHotKey", "UnregisterEventHotKey", "InstallEventHandler",
                 "RemoveEventHandler", "GetEventDispatcherTarget", "GetEventParameter",
                 "GetKeys", "GetCurrentKeyModifiers", "GetEventTime", "GetCurrentEventTime"):
        getattr(carbon, name)
    # Validate availability/callability without registering keys or printing
    # keyboard state. This does not prove interactive delivery or TCC behaviour.
    carbon.GetKeys.argtypes = [ctypes.POINTER(ctypes.c_uint32)]
    carbon.GetKeys.restype = None
    carbon.GetKeys((ctypes.c_uint32*4)())
    carbon.GetCurrentKeyModifiers.restype = ctypes.c_uint32
    carbon.GetCurrentKeyModifiers()
    return dict(imports=list(modules), platform=selected.name, windows_modules=unwanted,
                startup_before_application="PASSED", carbon_symbols="PASSED",
                screen_capture_api="PASSED", permission_requests="none")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment-only", action="store_true")
    args = parser.parse_args()
    output = Path("verification/macos-environment.json" if args.environment_only
                  else "verification/macos-import-smoke.json")
    result = {"environment": build_environment()}
    try:
        if not args.environment_only:
            result.update(run_smoke())
        result["status"] = "PASSED"
    except Exception as error:
        result.update(status="FAILED", error=str(error))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
