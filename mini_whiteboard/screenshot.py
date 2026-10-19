"""Hold, move, release screenshot selection with cancellable queued capture."""
import math
from PySide6.QtCore import QObject, QTimer, Qt, Signal
from .platform.base import CapturePermissionError
from .geometry import normalized
from .placement import PreviewOverlay
from .settings import PREVIEW_INTERVAL_MS


class ScreenshotController(QObject):
    captured = Signal(object, object)
    message = Signal(str)
    permission_required = Signal(str)
    delivery = Signal(object)

    def __init__(self, hotkeys, placement, parent=None):
        super().__init__(parent)
        self.hotkeys, self.placement = hotkeys, placement
        self.session = placement.session
        self.platform = placement.platform
        self.desktop, self.service = self.platform.desktop, self.platform.capture
        self.generation = 0
        self.overlays = []
        self.anchor = self.last_point = None
        self.pending = False
        self.pending_rect = None
        self.pending_excluded = ()
        hotkeys.events.capture.connect(self.start)
        hotkeys.events.capture_released.connect(self.release)
        hotkeys.events.cancel.connect(self.cancel)
        self.delivery.connect(self.deliver, Qt.ConnectionType.QueuedConnection)
        self.tracking = QTimer(self)
        self.tracking.setInterval(PREVIEW_INTERVAL_MS)
        self.tracking.timeout.connect(self.track)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.capture_pending)
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.setInterval(20000)
        self.timeout.timeout.connect(lambda: self.complete(self.generation, None,
                                         OSError("Screenshot capture timed out.")))

    @property
    def active(self):
        return self.anchor is not None or self.pending

    def start(self):
        if not self.session.claim("capture"):
            return
        try:
            self.anchor = self.desktop.cursor_position()
            self.hotkeys.enable_escape()
            for monitor in self.desktop.displays():
                overlay = PreviewOverlay(monitor, platform=self.platform)
                self.overlays.append(overlay)
                overlay.show()
            self.track()
            if self.anchor is not None:
                self.tracking.start()
        except Exception as error:
            self.cancel()
            self.message.emit(f"Screenshot selection could not start: {error}")

    def track(self, point=None):
        if self.anchor is None:
            return
        try:
            point = self.desktop.cursor_position() if point is None else point
            if point == self.last_point:
                return
            rect = normalized(self.anchor, point)
            for overlay in self.overlays:
                overlay.set_outline(rect)
            self.last_point = point
        except Exception as error:
            self.cancel()
            self.message.emit(f"Screenshot selection cancelled: {error}")

    def release(self):
        if self.anchor is None:
            return
        try:
            self.finish(self.desktop.cursor_position())
        except Exception as error:
            self.cancel()
            self.message.emit(f"Screenshot selection cancelled: {error}")

    def finish(self, point):
        if self.anchor is None or self.session.owner != "capture":
            return
        rect = normalized(self.anchor, point)
        if (not all(math.isfinite(v) for v in (rect.x, rect.y, rect.width, rect.height))
                or rect.width < 4 or rect.height < 4):
            self.cancel()
            self.message.emit("Selection cancelled. Choose a screenshot region at least 4 × 4 pixels.")
            return
        excluded = tuple(identifier for overlay in self.overlays
                         if (identifier := self.desktop.capture_window_identifier(overlay)) is not None)
        self.anchor = None
        self.tracking.stop()
        self.close_overlays()
        self.pending_rect, self.pending = rect, True
        self.pending_excluded = excluded
        # Start permission UI/capture only after release and overlay removal.
        self.timer.start(0)

    def capture_pending(self):
        if not self.pending:
            return
        generation, rect = self.generation, self.pending_rect
        self.timeout.start()
        try:
            self.service.prepare()
            if generation != self.generation or not self.pending:
                return
            self.service.capture_region(rect,
                lambda image: self.delivery.emit((generation, image, None)),
                lambda error: self.delivery.emit((generation, None, error)), self.pending_excluded)
        except Exception as error:
            self.complete(generation, None, error)

    def deliver(self, result):
        self.complete(*result)

    def complete(self, generation, image, error):
        if generation != self.generation or not self.pending:
            return
        rect = self.pending_rect
        self.cancel()
        if isinstance(error, CapturePermissionError):
            self.permission_required.emit(str(error))
        elif error is not None:
            self.message.emit(f"Screenshot capture failed: {error}")
        elif image is None or image.isNull():
            self.message.emit("Screenshot capture returned no image.")
        else:
            self.captured.emit(rect, image)

    def cancel(self):
        self.generation += 1
        self.timer.stop()
        self.tracking.stop()
        self.timeout.stop()
        self.pending = False
        self.pending_rect = None
        self.pending_excluded = ()
        self.anchor = self.last_point = None
        self.close_overlays()
        if self.session.owner == "capture":
            self.session.finish("capture")
            try:
                self.hotkeys.disable_escape()
            except Exception as error:
                self.message.emit(f"Shortcut cleanup: {error}")
        try:
            self.service.cancel()
        except Exception as error:
            self.message.emit(f"Screenshot cleanup: {error}")

    def close_overlays(self):
        for overlay in self.overlays:
            overlay.hide()
            overlay.close()
            overlay.deleteLater()
        self.overlays.clear()
