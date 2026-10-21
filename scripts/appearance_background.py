"""Owned, separately composed background for opt-in Windows material checks."""
import argparse
import ctypes as C
from ctypes import wintypes as W
import json
import os
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'windows'
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from .appearance_check import Background
from mini_whiteboard import windows
from mini_whiteboard.geometry import Rect


class ControlledBackground(Background):
    def nativeEvent(self, event_type, message):
        if bytes(event_type) == b'windows_generic_MSG':
            msg = W.MSG.from_address(int(message))
            if msg.message == 0x8001:
                self.mode = ('busy','light','dark')[msg.wParam]
                self.repaint()
                return True, 0
            if msg.message == 0x8002:
                QApplication.instance().quit()
                return True, 0
        return super().nativeEvent(event_type, message)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ready',type=Path,required=True)
    args = parser.parse_args()
    windows.enable_dpi_awareness()
    app = QApplication([])
    window = ControlledBackground()
    window.setWindowTitle('Mini Whiteboard owned material-test background')
    display = windows.monitors()[0].rect
    rect = Rect(display.x+60,display.y+80,1500,850)
    window.show()
    windows.set_window_rect(window,rect)
    def ready():
        args.ready.write_text(json.dumps({'handle':int(window.winId()),'pid':os.getpid(),
                                         'parent':os.getppid(),'rect':vars(rect)}),encoding='utf-8')
    QTimer.singleShot(0,ready)
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
