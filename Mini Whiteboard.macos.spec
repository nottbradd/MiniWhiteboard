"""Build on macOS using build_macos.sh. Never cross-build this bundle on Windows."""
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

if sys.platform != "darwin":
    raise SystemExit("Mini Whiteboard.app must be built on macOS.")
project = Path(SPECPATH)
sys.path.insert(0, str(project))
from scripts.build_support import configure_qt_plugins, notice_data
configure_qt_plugins()
target = os.environ.get("MINIWHITEBOARD_ARCH", "universal2")
identity = os.environ.get("MINIWHITEBOARD_SIGNING_IDENTITY") or None
a = Analysis(
    [str(project / "main.py")], pathex=[str(project)], binaries=[], datas=notice_data(project),
    hiddenimports=["objc", "AppKit", "Foundation", "CoreMedia"] +
                  collect_submodules("Quartz") + collect_submodules("ScreenCaptureKit"),
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=["mini_whiteboard.platform.windows", "mini_whiteboard.windows",
              "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtWebEngineCore", "PySide6.QtTest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Mini Whiteboard",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, argv_emulation=False, target_arch=target,
          codesign_identity=identity, entitlements_file=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Mini Whiteboard")
app = BUNDLE(coll, name="Mini Whiteboard.app", icon=str(project/"assets"/"mini_whiteboard.icns"),
             bundle_identifier="com.brad.miniwhiteboard", version="1.3.1",
             info_plist={
                 "CFBundleName": "Mini Whiteboard", "CFBundleDisplayName": "Mini Whiteboard",
                 "CFBundleShortVersionString": "1.3.1", "CFBundleVersion": "1.3.1",
                 "LSMinimumSystemVersion": "14.0", "LSUIElement": True,
                 "NSHighResolutionCapable": True,
                 "NSScreenCaptureUsageDescription": "Capture a region you select as a whiteboard background.",
                 "NSHumanReadableCopyright": "Mini Whiteboard",
             })
