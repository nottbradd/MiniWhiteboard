"""A discrete native shortcut stays latched until its physical key is released."""
from PySide6.QtCore import QObject, QEvent, QTimer, Qt, Signal


class ToggleLatch(QObject):
    released = Signal()

    def __init__(self, app, signal, is_down):
        super().__init__()
        self.app, self.signal, self.is_down = app, signal, is_down
        self.held = self.closed = False
        self.trigger_key = Qt.Key.Key_H
        self.failures = 0
        self.timer = QTimer(self)
        self.timer.setInterval(12)
        self.timer.timeout.connect(self.poll)
        app.installEventFilter(self)

    def activate(self):
        if self.closed:
            return
        if self.held:
            if not self.timer.isActive():
                self.failures = 0
                self.timer.start()
            return
        self.held = True
        self.timer.start()
        self.signal.emit()

    def poll(self):
        try:
            down = self.is_down()
        except OSError:
            self.failures += 1
            self.timer.setInterval(250)
            if self.failures >= 5:
                self.timer.stop()
            return  # Keep the latch until native release can be established.
        self.failures = 0
        self.timer.setInterval(12)
        if self.held and not down:
            self.held = False
            self.timer.stop()
            self.released.emit()

    def eventFilter(self, watched, event):
        if (self.held and event.type() in (QEvent.Type.KeyPress, QEvent.Type.ShortcutOverride)
                and event.key() == self.trigger_key):
            event.accept()
            return True
        return False

    def close(self):
        self.closed = True
        self.held = False
        self.timer.stop()
        self.app.removeEventFilter(self)
