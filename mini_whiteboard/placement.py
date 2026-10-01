"""Non-activating, input-transparent placement preview and its controller."""

from PySide6.QtCore import QObject, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QRegion
from PySide6.QtWidgets import QWidget

from .platform import get_platform
from .geometry import PlacementState, normalized, local_point
from .settings import (PREVIEW_INTERVAL_MS, PREVIEW_DOT_DIAMETER, PREVIEW_DOT_GAP,
                       PREVIEW_DOT_OPACITY, PREVIEW_SHADOW_OPACITY, PREVIEW_SHADOW_SPREAD,
                       PREVIEW_SHADOW_OFFSET)


def dot_path(bounds):
    """Real circles with an even pitch on each edge, sharing the corner dots."""
    path = QPainterPath()
    radius = PREVIEW_DOT_DIAMETER/2
    pitch = PREVIEW_DOT_DIAMETER + PREVIEW_DOT_GAP
    corners = (bounds.topLeft(), bounds.topRight(), bounds.bottomRight(), bounds.bottomLeft())
    for a, b in zip(corners, (*corners[1:], corners[0])):
        distance = abs(b.x()-a.x()) + abs(b.y()-a.y())
        count = max(1, round(distance/pitch))
        for i in range(count):
            p = a + (b-a)*(i/count)
            path.addEllipse(p, radius, radius)
    path.setFillRule(Qt.FillRule.WindingFill)
    return path


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

    def outline_region(self, outline):
        if outline is None:
            return QRegion()
        bounds = self.local_bounds(outline)
        padding = PREVIEW_DOT_DIAMETER/2 + PREVIEW_SHADOW_SPREAD + PREVIEW_SHADOW_OFFSET + 1
        outer = QRegion(bounds.adjusted(-padding, -padding, padding, padding).toAlignedRect())
        inner = bounds.adjusted(padding, padding, -padding, -padding)
        return outer.subtracted(QRegion(inner.toRect())) if inner.width() > 0 and inner.height() > 0 else outer

    def set_outline(self, outline):
        if outline == self.outline:
            return
        dirty = self.outline_region(self.outline).united(self.outline_region(outline))
        self.outline = outline
        self.update(dirty)

    def paintEvent(self, event):
        if self.outline is None:
            return
        dots = dot_path(self.local_bounds(self.outline))
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Two faint expanding layers soften the small offset shadow. No fill,
        # continuous border, dash pattern, or per-dot widgets are involved.
        shadow = QColor(25, 29, 35)
        painter.save()
        painter.translate(PREVIEW_SHADOW_OFFSET, PREVIEW_SHADOW_OFFSET)
        for spread, opacity in ((PREVIEW_SHADOW_SPREAD, .35), (PREVIEW_SHADOW_SPREAD*.45, .65)):
            shadow.setAlphaF(PREVIEW_SHADOW_OPACITY*opacity)
            painter.setPen(QPen(shadow, spread*2))
            painter.setBrush(shadow)
            painter.drawPath(dots)
        painter.restore()
        white = QColor("white")
        white.setAlphaF(PREVIEW_DOT_OPACITY)
        painter.fillPath(dots, white)


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
        self.confirmation_anchor = None
        self.before_start = None
        self.timer = QTimer(self)
        self.timer.setInterval(PREVIEW_INTERVAL_MS)
        self.timer.timeout.connect(self.track)
        hotkeys.events.create.connect(self.press)
        hotkeys.events.cancel.connect(self.cancel)

    def press(self):
        try:
            point = self.desktop.cursor_position()
            if not self.state.active:
                self.start_at(point)
                return
            rect = normalized(self.state.anchor, point)
            scale = self.desktop.placement_scale(rect)
            anchor = self.state.anchor
            status, rect = self.state.press(point, scale)
            if status == "too_small":
                self.message.emit(f"Choose at least 160 × 100 logical pixels. Move the cursor and press {self.platform.shortcuts.global_label('W')} again.")
                return
            self.cancel()
            self.confirmation_anchor = anchor
            self.confirmed.emit(rect)
        except Exception as error:
            self.cancel()
            self.message.emit(f"Placement could not start or finish: {error}")

    def start_at(self, point):
        if self.before_start is not None:
            self.before_start()
        self.hotkeys.enable_escape()
        self.state.anchor = point
        # Append incrementally so a failure on a later display can clean up all
        # windows already created by this interaction.
        for monitor in self.desktop.displays():
            self.overlays.append(PreviewOverlay(monitor, platform=self.platform))
        for overlay in self.overlays:
            overlay.show()
        self.last_point = None
        self.track()
        self.timer.start()

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
        except OSError as error:
            self.cancel()
            self.message.emit(str(error))

    def cancel(self):
        self.timer.stop()
        self.state.cancel()
        self.hotkeys.disable_escape()
        for overlay in self.overlays:
            overlay.hide()
            overlay.close()
            overlay.deleteLater()
        self.overlays.clear()
        self.last_point = None
