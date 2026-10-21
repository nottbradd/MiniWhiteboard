"""Refresh the tray symbol after OS broadcasts, without a polling timer."""
from ctypes import wintypes as W
from PySide6.QtCore import QAbstractNativeEventFilter, QTimer


class TrayThemeObserver(QAbstractNativeEventFilter):
    def __init__(self, app, tray, icon):
        super().__init__()
        self.app, self.tray, self.icon = app, tray, icon
        self.closed = False
        self.refresh = QTimer(app)
        self.refresh.setSingleShot(True)
        self.refresh.timeout.connect(self.update)
        app.installNativeEventFilter(self)
        app.styleHints().colorSchemeChanged.connect(self.schedule)

    def schedule(self, *_args):
        if not self.closed and not self.refresh.isActive():
            self.refresh.start(0)

    def update(self):
        if not self.closed:
            self.tray.setIcon(self.icon())

    def nativeEventFilter(self, kind, message):
        if bytes(kind) in (b'windows_generic_MSG', b'windows_dispatcher_MSG'):
            if W.MSG.from_address(int(message)).message in (0x001A, 0x0015, 0x031A):
                self.schedule()
        return False, 0

    def close(self):
        self.closed = True
        self.refresh.stop()
        self.app.removeNativeEventFilter(self)
        self.app.styleHints().colorSchemeChanged.disconnect(self.schedule)
        self.refresh.deleteLater()
