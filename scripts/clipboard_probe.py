"""Disposable second process for the opt-in native clipboard checks."""
import json
import sys
from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication
from mini_whiteboard.settings import CLIPBOARD_MIME

app = QApplication([])
clipboard = app.clipboard()
if '--publish' in sys.argv:
    image = QImage(240, 120, QImage.Format.Format_RGB32)
    image.fill(QColor('#3179b5'))
    clipboard.setImage(image)
    print(json.dumps({'published': True}), flush=True)
    QTimer.singleShot(15000, app.quit)
    app.exec()
else:
    image = clipboard.image()
    mime = clipboard.mimeData()
    print(json.dumps({'image': not image.isNull(), 'size': [image.width(), image.height()],
                      'editable': mime.hasFormat(CLIPBOARD_MIME),
                      'payload_bytes': mime.data(CLIPBOARD_MIME).size()}), flush=True)
