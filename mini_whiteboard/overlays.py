"""One lightweight, non-activating surface for unclipped tool visuals per board."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from . import rendering
from .geometry import Rect
from .settings import ERASER_CURSOR_PADDING, HANDLE_DIAMETER, ROTATION_HANDLE_DISTANCE, SELECTION, GUIDE_COLOR


def frame_bounds(frame, dpr):
    if frame is None:
        return QRectF()
    points = rendering.handles(frame, dpr)
    left, right = min(p.x() for p in points), max(p.x() for p in points)
    top, bottom = min(p.y() for p in points), max(p.y() for p in points)
    pad = HANDLE_DIAMETER/2/dpr+2
    return QRectF(left-pad, top-pad, right-left+2*pad, bottom-top+2*pad)


def paint_eraser_cursor(painter, position, diameter, whole_stroke=False):
    painter.setBrush(Qt.BrushStyle.NoBrush)
    p = rendering.point(position)
    radius = diameter/2
    painter.setPen(QPen(QColor("white"), 3))
    painter.drawEllipse(p, radius, radius)
    pen = QPen(QColor("#404951"), 1)
    if whole_stroke:
        pen.setStyle(Qt.PenStyle.CustomDashLine)
        pen.setDashPattern([3, 3])
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.drawEllipse(p, radius, radius)


class ToolOverlay(QWidget):
    def __init__(self, canvas):
        board = canvas.window()
        super().__init__(board, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowTransparentForInput |
                         Qt.WindowType.WindowDoesNotAcceptFocus)
        self.canvas = canvas
        self.desktop = board.desktop
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.frame = None
        self.cursor = None
        self.diameter = 16
        self.whole_stroke = False
        self.endpoints = ()
        self.marquee = QRectF()
        self.guides = ()
        self.visual_rect = QRectF()
        self._state = None
        self.desktop.configure_overlay(self, owner=board)

    def sync(self, frame, cursor, diameter, whole_stroke, endpoints=(), marquee=QRectF(), guides=()):
        board = self.canvas.window()
        dpr = board.devicePixelRatioF()
        rect = frame_bounds(frame, dpr)
        if not marquee.isEmpty():
            rect = rect.united(marquee.adjusted(-2, -2, 2, 2))
        for x1,y1,x2,y2 in guides:
            rect = rect.united(QRectF(rendering.point((x1,y1)), rendering.point((x2,y2))).normalized().adjusted(-2,-2,2,2))
        if cursor is not None:
            radius = diameter/2+ERASER_CURSOR_PADDING
            rect = rect.united(QRectF(cursor[0]-radius, cursor[1]-radius, 2*radius, 2*radius))
        # Offscreen artwork still has full document bounds, but must not allocate
        # an arbitrarily large native surface or draw chrome over distant apps.
        pad = max(diameter/2, (ROTATION_HANDLE_DISTANCE+HANDLE_DIAMETER)/dpr)+ERASER_CURSOR_PADDING
        rect = rect.intersected(QRectF(self.canvas.rect()).adjusted(-pad, -pad, pad, pad))
        if rect.isEmpty() or not board.isVisible() or self.canvas.editor is not None:
            self.hide()
            self._state = None
            return
        rect = QRectF(rect.toAlignedRect())
        physical = self.desktop.canvas_region(self.canvas, rect)
        state = (frame, cursor, diameter, whole_stroke, endpoints, marquee, guides, rect, physical, dpr)
        if state == self._state and self.isVisible():
            return
        self._state = state
        self.frame, self.cursor = frame, cursor
        self.diameter, self.whole_stroke = diameter, whole_stroke
        self.endpoints, self.visual_rect = endpoints, rect
        self.marquee = marquee
        self.guides = guides
        # Set Qt's cached size before showing, then apply authoritative native
        # coordinates; this mirrors the board/shadow placement boundary.
        self.resize(round(rect.width()), round(rect.height()))
        self.desktop.set_window_rect(self, physical)
        if not self.isVisible():
            self.show()
            self.desktop.configure_overlay(self, owner=board)
            self.desktop.set_window_rect(self, physical)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(-self.visual_rect.x(), -self.visual_rect.y())
        # Controls visually occlude tool chrome even though the passive native
        # overlay sits outside the board's rounded input/document region.
        clip = QPainterPath()
        clip.addRect(self.visual_rect)
        for rect in self.canvas.control_rects():
            hole = QPainterPath()
            hole.addRect(rect)
            clip = clip.subtracted(hole)
        painter.setClipPath(clip)
        dpr = self.canvas.devicePixelRatioF()
        if self.frame is not None:
            rendering.paint_selection(painter, self.frame, dpr)
            for endpoint in self.endpoints:
                painter.drawEllipse(rendering.point(endpoint), HANDLE_DIAMETER/2/dpr, HANDLE_DIAMETER/2/dpr)
        if self.cursor is not None:
            paint_eraser_cursor(painter, self.cursor, self.diameter, self.whole_stroke)
        if self.guides:
            painter.save()
            if self.canvas.clip_spec is not None:
                painter.setClipPath(rendering.clip_path(self.canvas.clip_spec), Qt.ClipOperation.IntersectClip)
            color = QColor(GUIDE_COLOR)
            color.setAlpha(135)
            painter.setPen(QPen(color, 1))
            for x1,y1,x2,y2 in self.guides:
                painter.drawLine(rendering.point((x1,y1)), rendering.point((x2,y2)))
            painter.restore()
        if not self.marquee.isEmpty():
            painter.save()
            if self.canvas.clip_spec is not None:
                painter.setClipPath(rendering.clip_path(self.canvas.clip_spec), Qt.ClipOperation.IntersectClip)
            color = QColor(SELECTION)
            color.setAlpha(22)
            painter.setBrush(color)
            painter.setPen(QPen(QColor(SELECTION), 1, Qt.PenStyle.DashLine))
            painter.drawRect(self.marquee)
            painter.restore()
