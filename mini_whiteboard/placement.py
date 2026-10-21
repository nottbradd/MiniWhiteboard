"""Non-activating, input-transparent placement preview and its controller."""

from PySide6.QtCore import QEvent, QObject, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QPainter, QRegion
from PySide6.QtWidgets import QWidget

from .platform import get_platform
from .gestures import CreationSession
from .geometry import PlacementState, normalized, local_point
from .settings import PREVIEW_INTERVAL_MS
from .appearance import corner_radius, paint_preview


class PreviewOverlay(QWidget):
    def __init__(self, monitor, interactive=False, platform=None):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool |
                         Qt.WindowType.WindowStaysOnTopHint |
                         (Qt.WindowType(0) if interactive else Qt.WindowType.WindowTransparentForInput) |
                         Qt.WindowType.WindowDoesNotAcceptFocus)
        self.monitor = monitor
        self.interactive = interactive
        self.platform = platform or get_platform()
        self.desktop = self.platform.desktop
        self.outline = None
        self._closing = False
        self.appearance_theme = 'Glass'
        self.native_glass = False
        self.display_policy = self.desktop.display_policy()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, not interactive)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.winId()
        self.desktop.configure_overlay(self, interactive=interactive)
        self.desktop.set_window_rect(self, monitor.rect)

    def local_bounds(self, r):
        return self.desktop.overlay_local_bounds(self, r)

    def showEvent(self, event):
        super().showEvent(event)
        self.desktop.configure_overlay(self, interactive=self.interactive)
        self.sync_material()

    def paper_rect(self):
        return self.local_bounds(self.outline) if self.outline is not None else QRectF()

    def physical_paper_rect(self):
        return self.outline

    def corner_radius(self):
        return corner_radius(self.paper_rect(), 'Glass')

    def sync_material(self):
        if (not self.isVisible() or self.outline is None or self.outline.width <= 0
                or self.outline.height <= 0 or not self.outline.intersection_area(self.monitor.rect)):
            self.desktop.release_appearance(self)
            self.native_glass = False
        else:
            self.native_glass = self.desktop.apply_appearance(self)
            if self.platform.name == 'macos':
                self.desktop.sync_material(self)

    def refresh_appearance(self):
        self.desktop.release_appearance(self)
        self.display_policy = self.desktop.display_policy()
        self.sync_material()
        self.update()

    def hideEvent(self, event):
        self.desktop.release_appearance(self)
        self.native_glass = False
        super().hideEvent(event)

    def closeEvent(self, event):
        self._closing = True
        self.desktop.release_appearance(self)
        super().closeEvent(event)

    def nativeEvent(self, event_type, message):
        if hasattr(self, 'desktop'):
            result = self.desktop.native_event(self, event_type, message)
            if result is not None:
                return result
        return super().nativeEvent(event_type, message)

    def event(self, event):
        result=super().event(event)
        if event.type()==QEvent.Type.DevicePixelRatioChange and hasattr(self,'display_policy'):
            self.refresh_appearance()
        return result

    def outline_region(self, outline):
        if outline is None:
            return QRegion()
        bounds = self.local_bounds(outline)
        # The selection is filled now. Invalidate its interior as well as both
        # perimeters, otherwise moving/shrinking leaves old tint on the desktop.
        return QRegion(bounds.adjusted(-2, -2, 2, 2).toAlignedRect()).intersected(QRegion(self.rect()))

    def set_outline(self, outline):
        if outline == self.outline:
            return
        dirty = self.outline_region(self.outline).united(self.outline_region(outline))
        self.outline = outline
        self.sync_material()
        self.update(dirty)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.outline is not None:
            paint_preview(painter, self.paper_rect(), self.native_glass, self.display_policy)


class PlacementController(QObject):
    confirmed = Signal(object)
    message = Signal(str)

    def __init__(self, hotkeys, parent=None, platform=None):
        super().__init__(parent)
        self.platform = platform or get_platform()
        self.desktop = self.platform.desktop
        self.hotkeys = hotkeys
        self.state = PlacementState()
        self.overlays = []
        self.last_point = None
        self.session = CreationSession()
        self.timer = QTimer(self)
        self.timer.setInterval(PREVIEW_INTERVAL_MS)
        self.timer.timeout.connect(self.track)
        hotkeys.events.create.connect(self.press)
        hotkeys.events.create_released.connect(self.release)
        hotkeys.events.cancel.connect(self.cancel)

    def press(self):
        if self.session.owner is not None:
            return
        try:
            self.start_at(self.desktop.cursor_position())
        except Exception as error:
            self.cancel()
            self.message.emit(f"Placement could not start: {error}")

    def release(self):
        if self.session.owner != "board" or not self.state.active:
            return
        try:
            point = self.desktop.cursor_position()
            rect = normalized(self.state.anchor, point)
            scale = self.desktop.placement_scale(rect)
            status, rect = self.state.release(point, scale)
            self.cancel()
            if status == "too_small":
                self.message.emit("Selection cancelled. Choose at least 160 × 100 logical pixels.")
                return
            self.confirmed.emit(rect)
        except Exception as error:
            self.cancel()
            self.message.emit(f"Placement could not start or finish: {error}")

    def start_at(self, point):
        if not self.session.claim("board"):
            return
        try:
            self.state.begin(point)
            self.hotkeys.enable_escape()
            for monitor in self.desktop.displays():
                self.overlays.append(PreviewOverlay(monitor, platform=self.platform))
            for overlay in self.overlays:
                overlay.show()
            self.last_point = None
            self.track()
            if self.state.active:
                self.timer.start()
        except Exception:
            self.cancel()
            raise

    def track(self):
        if not self.state.active:
            return
        try:
            point = self.desktop.cursor_position()
            if point != self.last_point:
                rect = normalized(self.state.anchor, point)
                for overlay in self.overlays:
                    overlay.set_outline(rect)
                self.last_point = point
        except Exception as error:
            self.cancel()
            self.message.emit(str(error))

    def cancel(self):
        self.timer.stop()
        self.state.cancel()
        if self.session.owner == "board":
            self.session.finish("board")
            try:
                self.hotkeys.disable_escape()
            except Exception as error:
                self.message.emit(f"Placement cleanup: {error}")
        for overlay in self.overlays:
            overlay.hide()
            overlay.close()
            overlay.deleteLater()
        self.overlays.clear()
        self.last_point = None
