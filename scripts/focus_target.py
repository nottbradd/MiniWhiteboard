"""A separate, disposable desktop application for the native hotkey test."""
import sys
import os
import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTextEdit

app = QApplication([])
window = QTextEdit()
window.setWindowTitle("Mini Whiteboard — disposable focus test target")
window.setPlainText("This test window represents another normal desktop application.\n"
                    "The integration check sends hotkeys only while this window has focus.")
window.setGeometry(70, 90, 650, 500)
window.show()
window.activateWindow()
window.setFocus()
print(json.dumps({"hwnd": int(window.winId()), "pid": os.getpid()}), flush=True)
raise SystemExit(app.exec())
