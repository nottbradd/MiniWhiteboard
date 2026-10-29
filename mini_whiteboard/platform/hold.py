"""Native hold latch. The adapter samples only the two registered shortcuts.

The timer exists only during a gesture or while its trigger keys are draining.
It never records general keyboard input. Controllers separately own the preview
until asynchronous work finishes, so a competing shortcut cannot replace it.
"""
from PySide6.QtCore import QObject, QEvent, QTimer, Qt
from .base import CREATE_HOTKEY, CAPTURE_HOTKEY


class HoldTracker(QObject):
    def __init__(self, app, events, sample, trigger_keys=None):
        super().__init__()
        self.app, self.events, self.sample = app, events, sample
        self.trigger_keys = ({Qt.Key.Key_W: CREATE_HOTKEY, Qt.Key.Key_S: CAPTURE_HOTKEY}
                             if trigger_keys is None else dict(trigger_keys))
        self.active = None
        self.blocked = set()
        self.closed = False
        self.failed = False
        self.escape_down = False
        self.timer = QTimer(self)
        self.timer.setInterval(8)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self.poll)
        app.installEventFilter(self)

    def activate(self, identifier):
        if self.closed:
            return
        if self.active is not None or self.blocked:
            self.blocked.add(identifier)
            return
        self.escape_down = False  # Escape can release while the idle timer is stopped.
        self.active = identifier
        self.blocked.add(identifier)
        self.timer.start()
        signal = self.events.create if identifier == CREATE_HOTKEY else self.events.capture
        signal.emit()

    def release(self, identifier):
        if identifier != self.active:
            return
        self.active = None  # Clear before synchronous slots can create/focus UI.
        signal = self.events.create_released if identifier == CREATE_HOTKEY else self.events.capture_released
        signal.emit()

    def poll(self):
        try:
            state = self.sample()
            down, complete = state[:2]
            escape = len(state) > 2 and state[2]
            if escape and not self.escape_down:
                self.events.cancel.emit()
            self.escape_down = bool(escape)
            self.failed = False
            self.timer.setInterval(8)
            # Include competing trigger keys even if their native activation
            # arrived after the modifiers were released.
            self.blocked.update(down)
            if self.active is not None and self.active not in complete:
                self.release(self.active)
            self.blocked.intersection_update(down)
            if self.active is None and not self.blocked:
                self.timer.stop()
        except Exception as error:
            # Keep only release cleanup alive at a reduced rate after a native
            # failure. Clearing the latch here would let held repeats restart.
            self.timer.setInterval(100)
            if not self.failed:
                self.failed = True
                self.events.cancel.emit()
                self.events.warning.emit(f"Shortcut tracking stopped: {error}. Release the keys and try again.")

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.KeyPress, QEvent.Type.ShortcutOverride):
            identifiers = self.trigger_keys.get(event.key(), set())
            if isinstance(identifiers, int):
                identifiers = {identifiers}
            if self.blocked.intersection(identifiers):
                event.accept()
                return True
        return False

    def close(self):
        self.closed = True
        self.timer.stop()
        self.active = None
        self.blocked.clear()
        self.app.removeEventFilter(self)
