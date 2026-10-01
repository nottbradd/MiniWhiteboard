"""Generate a native .icns from the shared vector icon on macOS."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    if sys.platform != "darwin":
        raise SystemExit("iconutil requires macOS.")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from mini_whiteboard.app import app_icon
    app = QApplication.instance() or QApplication([])
    destination = Path(__file__).resolve().parents[1]/"assets"/"mini_whiteboard.icns"
    with tempfile.TemporaryDirectory() as directory:
        iconset = Path(directory)/"MiniWhiteboard.iconset"
        iconset.mkdir()
        for points in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                size = points*scale
                suffix = "@2x" if scale == 2 else ""
                path = iconset/f"icon_{points}x{points}{suffix}.png"
                if not app_icon(size).pixmap(size, size).save(str(path), "PNG"):
                    raise RuntimeError("Could not write icon raster.")
        subprocess.run(["/usr/bin/iconutil", "-c", "icns", str(iconset), "-o", str(destination)], check=True)
    print(destination)


if __name__ == "__main__":
    main()
