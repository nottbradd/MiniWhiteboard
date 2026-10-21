# Build with: .venv\Scripts\python.exe -m PyInstaller --noconfirm "Mini Whiteboard.spec"
from pathlib import Path

project = Path(SPECPATH)
import sys
sys.path.insert(0, str(project))
from scripts.build_support import configure_qt_plugins, notice_data
configure_qt_plugins()
a = Analysis(
    [str(project / "main.py")],
    pathex=[str(project)],
    binaries=[],
    datas=notice_data(project),
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtWebEngineCore", "PySide6.QtTest",
              "mini_whiteboard.platform.macos", "objc", "AppKit", "Foundation", "Quartz", "ScreenCaptureKit", "CoreMedia"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Mini Whiteboard",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(project / "assets" / "mini_whiteboard.ico"),
    manifest=str(project / "assets" / "app.manifest"),
    version=str(project / "assets" / "version_info.txt"),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Mini Whiteboard")
