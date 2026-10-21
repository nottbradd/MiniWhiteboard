# Build with: .venv\Scripts\python.exe -m PyInstaller --noconfirm "Mini Whiteboard.spec"
from pathlib import Path

project = Path(SPECPATH)
import sys
sys.path.insert(0, str(project))
from scripts.build_support import configure_qt_plugins, notice_data
from PyInstaller.utils.hooks import collect_all
configure_qt_plugins()
ocr_data, ocr_binaries, ocr_imports = collect_all('tesserocr', include_py_files=False)
ocr_data = [(source, target) for source, target in ocr_data if not source.endswith('.pyi')]
ocr_imports = [name for name in ocr_imports if 'CSI-helper' not in name]
a = Analysis(
    [str(project / "main.py")],
    pathex=[str(project)],
    binaries=ocr_binaries,
    datas=notice_data(project) + ocr_data + [(str(project / 'assets' / 'ocr'), 'assets/ocr')],
    hiddenimports=ocr_imports + ['mini_whiteboard.ocr_worker', 'mini_whiteboard.platform.windows.ocr'],
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
