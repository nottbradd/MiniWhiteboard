"""Create the build icon from the application's own vector drawing."""
import os
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from mini_whiteboard.app import app_icon

app = QApplication([])
destination = Path(__file__).resolve().parents[1] / "assets" / "mini_whiteboard.ico"
if not app_icon().pixmap(64, 64).save(str(destination), "ICO"):
    raise SystemExit("Could not write the Windows icon")
print(destination)
