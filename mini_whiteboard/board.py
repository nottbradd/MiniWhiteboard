"""Frameless paper, shadow, window gestures, and board lifecycle."""
import math
from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QToolButton, QWidget

from .platform import get_platform
from .shortcuts import ui_font_family
from .geometry import Rect, large_enough
from .settings import (BORDER, EDGE_GRIP, MIN_HEIGHT, MIN_WIDTH, PAPER,
                       RADIUS, SHADOW, TOP_STRIP, CANVAS_INSET, BORDER_WIDTH,
                       CONTROL_WIDTH, CONTROL_HEIGHT, CONTROL_TOP, CONTROL_GAP,
                       CONTROL_RIGHT, CONTROL_FONT_SIZE)


class BoardWindow(QWidget):
    deleted = Signal(object)
    minimized = Signal(object)

    def __init__(self, name, preferences=None, platform=None):
        platform = platform or get_platform()
        super().__init__(None, platform.desktop.board_flags())
        self.platform = platform
        self.desktop = platform.desktop
        self.name = name
        self.setWindowTitle(name)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(MIN_WIDTH + 2*self.desktop.shadow_margin, MIN_HEIGHT + 2*self.desktop.shadow_margin)
        self._gesture = None
        self._closing = False
        self._shadow = None
        self._region_key = None
        self.activation_timer = QTimer(self)
        self.activation_timer.setSingleShot(True)
        self.activation_timer.timeout.connect(self.activate_explicitly)
        self.canvas = None
        self.minus = self.make_button("−", f"Minimise this whiteboard to the {platform.shortcuts.status_location}", "#71777d")
        self.remove = self.make_button("×", "Delete this whiteboard and its contents", "#d75555")
        self.minus.clicked.connect(self.minimize_to_tray)
        self.remove.clicked.connect(self.close)
        from .canvas import Canvas
        self.install_canvas(Canvas(self, preferences))

    def make_button(self, text, tooltip, color):
        button = QToolButton(self)
        button.setText(text)
        button.setToolTip(tooltip)
        button.setCursor(Qt.CursorShape.ArrowCursor)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setStyleSheet(f"QToolButton {{ border: none; border-radius: 6px; color: {color}; "
                             f"background: transparent; font: {CONTROL_FONT_SIZE}px '{ui_font_family()}'; }}"
                             "QToolButton:hover { background: #f0f1f2; }"
                             "QToolButton:pressed { background: #e4e6e8; }")
        return button

    def paper_rect(self):
        return self.desktop.paper_rect(self)

    def physical_paper_rect(self):
        """Legacy Windows diagnostic name; Mac returns its native desktop points."""
        return self.desktop.paper_bounds(self)

    def install_canvas(self, canvas):
        self.canvas = canvas
        canvas.setParent(self)
        self.layout_children()
        canvas.show()
        self.setFocusProxy(canvas)

    def layout_children(self):
        paper = self.paper_rect()
        right = paper.right()-CONTROL_RIGHT-CONTROL_WIDTH
        self.remove.setGeometry(round(right), round(paper.top()+CONTROL_TOP), CONTROL_WIDTH, CONTROL_HEIGHT)
        self.minus.setGeometry(round(right-CONTROL_WIDTH-CONTROL_GAP), round(paper.top()+CONTROL_TOP), CONTROL_WIDTH, CONTROL_HEIGHT)
        if self.canvas is not None:
            self.canvas.setGeometry(math.ceil(paper.left()+CANVAS_INSET),
                                    math.ceil(paper.top()+TOP_STRIP),
                                    max(1, math.floor(paper.width()-2*CANVAS_INSET)),
                                    max(1, math.floor(paper.height()-TOP_STRIP-CANVAS_INSET)))
            self.canvas.refresh_document_clip()
        self.minus.raise_()
        self.remove.raise_()

    def resizeEvent(self, event):
        self.layout_children()
        super().resizeEvent(event)
        self.sync_shadow()

    def moveEvent(self, event):
        super().moveEvent(event)
        self.sync_shadow()
        if self.canvas is not None:
            self.canvas.sync_tool_overlay()

    def showEvent(self, event):
        super().showEvent(event)
        self.sync_shadow()

    def hideEvent(self, event):
        if self._shadow is not None:
            self._shadow.hide()
        if self.canvas is not None and self.canvas.tool_overlay is not None:
            self.canvas.tool_overlay.hide()
        super().hideEvent(event)

    def sync_shadow(self):
        self.desktop.sync_decoration(self)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        paper = self.paper_rect()
        painter.setPen(Qt.PenStyle.NoPen)
        if self.desktop.paints_shadow:
            # Offscreen rendering has no native input region or shadow window.
            for spread in range(SHADOW, 0, -1):
                painter.setBrush(QColor(30, 38, 45, 2 + (SHADOW-spread)//2))
                painter.drawRoundedRect(paper.adjusted(-spread, -spread+1, spread, spread+1),
                                        RADIUS+spread, RADIUS+spread)
        painter.setBrush(QColor(PAPER))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(paper, RADIUS, RADIUS)
        painter.setPen(QPen(QColor(BORDER), BORDER_WIDTH, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(paper.left()+RADIUS, paper.top()+BORDER_WIDTH/2),
                         QPointF(paper.right()-RADIUS, paper.top()+BORDER_WIDTH/2))

    def place(self, rect):
        self.desktop.place_board(self, rect)
        self.layout_children()
        self.sync_shadow()
        self.desktop.focus_window(self)
        (self.canvas or self).setFocus()
        self.activation_timer.start(0)

    def minimize_to_tray(self):
        self.activation_timer.stop()
        if self.canvas is not None:
            self.canvas.finish_editing()
            self.canvas.cancel_interaction()
            self.canvas.stop_transient_ui()
        self.hide()
        self.minimized.emit(self)

    def restore(self):
        self.desktop.focus_window(self)
        (self.canvas or self).setFocus()
        self.activation_timer.start(0)

    def activate_explicitly(self):
        if self.isVisible():
            self.desktop.focus_window(self)
            (self.canvas or self).setFocus()

    def closeEvent(self, event):
        self.activation_timer.stop()
        if self._shadow is not None:
            self._shadow.close()
        if self.canvas is not None and self.canvas.tool_overlay is not None:
            self.canvas.tool_overlay.close()
        if not self._closing:
            self._closing = True
            if self.canvas is not None:
                self.canvas.finish_editing()
                self.canvas.cancel_interaction()
                self.canvas.stop_transient_ui()
            self.deleted.emit(self)
        event.accept()

    def edges_at(self, point):
        r = self.paper_rect()
        if not r.contains(point):
            return Qt.Edge(0)
        edges = Qt.Edge(0)
        if point.x() <= r.left()+EDGE_GRIP:
            edges |= Qt.Edge.LeftEdge
        if point.x() >= r.right()-EDGE_GRIP:
            edges |= Qt.Edge.RightEdge
        if point.y() <= r.top()+EDGE_GRIP:
            edges |= Qt.Edge.TopEdge
        if point.y() >= r.bottom()-EDGE_GRIP:
            edges |= Qt.Edge.BottomEdge
        return edges

    def mouseMoveEvent(self, event):
        if self._gesture:
            kind, start, bounds, edges = self._gesture
            current = self.desktop.cursor_position()
            dx, dy = current[0]-start[0], current[1]-start[1]
            if kind == "move":
                target = Rect(bounds.x+dx, bounds.y+dy, bounds.width, bounds.height)
            else:
                l, t, r, b = bounds.x, bounds.y, bounds.right, bounds.bottom
                scale = self.desktop.window_scale(self)
                margin = self.desktop.shadow_margin
                mw, mh = (MIN_WIDTH+2*margin)*scale, (MIN_HEIGHT+2*margin)*scale
                if edges & Qt.Edge.LeftEdge:
                    l = min(l+dx, r-mw)
                if edges & Qt.Edge.RightEdge:
                    r = max(r+dx, l+mw)
                if edges & Qt.Edge.TopEdge:
                    t = min(t+dy, b-mh)
                if edges & Qt.Edge.BottomEdge:
                    b = max(b+dy, t+mh)
                target = Rect(l, t, r-l, b-t)
            self.desktop.set_window_rect(self, target)
            return
        edges = self.edges_at(event.position())
        self.setCursor(self.edge_cursor(edges) if edges else
                       Qt.CursorShape.SizeAllCursor if event.position().y() <= self.paper_rect().top()+TOP_STRIP
                       else Qt.CursorShape.ArrowCursor)

    @staticmethod
    def edge_cursor(edges):
        vertical = bool(edges & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge))
        horizontal = bool(edges & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge))
        if vertical and horizontal:
            same = bool(edges & Qt.Edge.LeftEdge) == bool(edges & Qt.Edge.TopEdge)
            cursor = Qt.CursorShape.SizeFDiagCursor if same else Qt.CursorShape.SizeBDiagCursor
        elif horizontal:
            cursor = Qt.CursorShape.SizeHorCursor
        elif vertical:
            cursor = Qt.CursorShape.SizeVerCursor
        else:
            cursor = Qt.CursorShape.ArrowCursor
        return cursor

    def route_canvas_edge(self, event):
        # The narrow canvas inset must not shrink the invisible resize target.
        # Route only an idle edge interaction; active tools keep their mouse grab
        # and shared transform handles have priority over resizing the window.
        if event.type() in (QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress):
            canvas = self.canvas
            if canvas.gesture or canvas.editor is not None:
                return False
            position = event.position()
            if canvas.frame and canvas.tool in ('Select','Shape','Text'):
                from . import rendering
                if rendering.handle_at(canvas.frame,(position.x(),position.y()),self.devicePixelRatioF()) is not None:
                    return False
                if canvas.tool == 'Shape' and rendering.endpoint_at(canvas.selected,(position.x(),position.y())) is not None:
                    return False
            point = position + QPointF(canvas.x(),canvas.y())
            edges = self.edges_at(point)
            if edges:
                if event.type() == QEvent.Type.MouseMove:
                    canvas.setCursor(self.edge_cursor(edges))
                    canvas.cursor_position = None
                    canvas.sync_tool_overlay()
                elif event.button() == Qt.MouseButton.LeftButton:
                    canvas.setFocus(Qt.FocusReason.MouseFocusReason)
                    self._gesture = ('resize',self.desktop.cursor_position(),self.desktop.window_rect(self),edges)
                    self.grabMouse()
                else:
                    return False
                return True
        return False

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self.canvas is not None:
            self.canvas.finish_editing()
        edges = self.edges_at(event.position())
        if edges:
            kind = "resize"
        elif self.paper_rect().contains(event.position()) and event.position().y() <= self.paper_rect().top()+TOP_STRIP:
            kind = "move"
        else:
            return
        self._gesture = (kind, self.desktop.cursor_position(), self.desktop.window_rect(self), edges)
        self.grabMouse()

    def mouseReleaseEvent(self, event):
        if self._gesture:
            self._gesture = None
            self.releaseMouse()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self._gesture:
            self.cancel_window_gesture()
            return
        super().keyPressEvent(event)

    def cancel_window_gesture(self):
        if self._gesture:
            self.desktop.set_window_rect(self, self._gesture[2])
            self._gesture = None
            self.releaseMouse()

    def nativeEvent(self, event_type, message):
        result = self.desktop.native_event(self, event_type, message)
        if result is not None:
            return result
        return super().nativeEvent(event_type, message)
