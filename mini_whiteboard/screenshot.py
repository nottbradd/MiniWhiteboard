"""Click-drag screenshot selection, separate from the two-hotkey placement flow."""
from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from .platform.base import CapturePermissionError
from .geometry import normalized
from .placement import PreviewOverlay


class CaptureOverlay(PreviewOverlay):
    def __init__(self, monitor, controller):
        super().__init__(monitor, interactive=True, platform=controller.platform)
        self.controller = controller
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def paintEvent(self, event):
        # A one-alpha veil makes the layered HWND receive mouse events on
        # Windows while keeping the live desktop visible beneath it.
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0,0,0,1))
        painter.end()
        super().paintEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.controller.anchor = self.controller.desktop.cursor_position()
            self.grabMouse()
            self.controller.track(self.controller.anchor)

    def mouseMoveEvent(self, event):
        if self.controller.anchor is not None:
            self.controller.track(self.controller.desktop.cursor_position())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.controller.anchor is not None:
            self.releaseMouse()
            self.controller.finish(self.controller.desktop.cursor_position())


class ScreenshotController(QObject):
    captured = Signal(object, object)
    message = Signal(str)
    permission_required = Signal(str)

    def __init__(self, hotkeys, placement, parent=None):
        super().__init__(parent)
        self.hotkeys, self.placement = hotkeys, placement
        self.platform = placement.platform
        self.desktop = self.platform.desktop
        self.service = self.platform.capture
        self.generation = 0
        self.overlays = []
        self.anchor = None
        self.pending = False
        hotkeys.events.capture.connect(self.start)
        hotkeys.events.cancel.connect(self.cancel)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.capture_pending)
        self.pending_rect = None
        self.pending_excluded = ()

    @property
    def active(self):
        return bool(self.overlays) or self.pending

    def start(self):
        self.cancel()
        self.placement.cancel()
        try:
            self.service.prepare()
            self.hotkeys.enable_escape()
            for monitor in self.desktop.displays():
                overlay = CaptureOverlay(monitor, self)
                self.overlays.append(overlay)
                overlay.show()
                self.desktop.configure_overlay(overlay, interactive=True)
                self.desktop.set_window_rect(overlay,overlay.monitor.rect)
        except CapturePermissionError as error:
            self.cancel()
            self.permission_required.emit(str(error))
        except (OSError, ValueError) as error:
            self.cancel()
            self.message.emit(f"Screenshot selection could not start: {error}")

    def track(self, point):
        if self.anchor is not None:
            rect = normalized(self.anchor, point)
            for overlay in self.overlays:
                overlay.set_outline(rect)

    def finish(self, point):
        if self.anchor is None:
            return
        rect = normalized(self.anchor, point)
        excluded = tuple(identifier for overlay in self.overlays
                         if (identifier := self.desktop.capture_window_identifier(overlay)) is not None)
        if rect.width < 4 or rect.height < 4:
            self.cancel()
            self.message.emit("Choose a screenshot region at least 4 × 4 pixels.")
            return
        self.anchor = None
        self.close_overlays()
        self.pending_rect, self.pending = rect, True
        self.pending_excluded = excluded
        # Run after Qt has hidden every overlay; DwmFlush in the native capture
        # boundary waits for desktop composition before reading the pixels.
        self.timer.start(0)

    def capture_pending(self):
        if not self.pending:
            return
        rect = self.pending_rect
        generation = self.generation
        def success(image):
            if generation != self.generation or not self.pending:
                return
            self.pending = False
            self.pending_rect = None
            self.hotkeys.disable_escape()
            if image.isNull():
                self.message.emit("Screenshot capture returned no image.")
                return
            self.captured.emit(rect,image)
        def failure(error):
            if generation != self.generation or not self.pending:
                return
            self.pending = False
            self.pending_rect = None
            self.hotkeys.disable_escape()
            if isinstance(error, CapturePermissionError):
                self.permission_required.emit(str(error))
            else:
                self.message.emit(f"Screenshot capture failed: {error}")
        try:
            self.service.capture_region(rect, success, failure, self.pending_excluded)
        except (OSError,ValueError) as error:
            failure(error)

    def cancel(self):
        self.generation += 1
        self.service.cancel()
        self.timer.stop()
        self.pending = False
        self.pending_rect = None
        self.pending_excluded = ()
        self.anchor = None
        self.close_overlays()
        # Placement and capture never run together; don't unregister the other
        # workflow's Escape when this already-idle controller is cancelled.
        if not self.placement.state.active:
            self.hotkeys.disable_escape()

    def close_overlays(self):
        for overlay in self.overlays:
            overlay.releaseMouse()
            overlay.hide()
            overlay.close()
            overlay.deleteLater()
        self.overlays.clear()
