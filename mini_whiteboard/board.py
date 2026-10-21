"""Frameless paper, shadow, window gestures, and board lifecycle."""
import math
from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QToolButton, QWidget

from .platform import get_platform
from .shortcuts import ui_font_family
from .appearance import corner_radius, paint_surface
from .geometry import Rect, large_enough
from .settings import (BORDER, EDGE_GRIP, MIN_HEIGHT, MIN_WIDTH, PAPER,
                       RADIUS, SHADOW, TOP_STRIP, CANVAS_INSET, BORDER_WIDTH,
                       CONTROL_WIDTH, CONTROL_HEIGHT, CONTROL_TOP, CONTROL_GAP,
                       CONTROL_RIGHT, CONTROL_FONT_SIZE)


class BoardWindow(QWidget):
    deleted = Signal(object)
    minimized = Signal(object)
    restored = Signal(object)

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
        from .appearance import Emphasis
        self.display_policy = self.desktop.display_policy()
        self.native_glass = False
        self.emphasis = Emphasis(self)
        self._presented_theme = self.appearance_theme
        self.canvas.preferences.appearance_changed.connect(self.refresh_appearance)

    def refresh_appearance(self):
        if self.canvas is None or not hasattr(self, 'emphasis') or self._closing:
            return
        self.emphasis.stop()
        theme_changed = self._presented_theme != self.appearance_theme
        self._presented_theme = self.appearance_theme
        self.display_policy = self.desktop.display_policy()
        self.desktop.release_appearance(self)
        self.native_glass = self.desktop.apply_appearance(self) if self.isVisible() else False
        self.layout_children()
        self._region_key = None
        self.sync_shadow()
        glass = self.appearance_theme == 'Glass' and not self.display_policy.high_contrast
        for button, delete in ((self.minus, False), (self.remove, True)):
            background = '#ef5b64' if delete else 'rgba(90,94,115,32)'
            foreground = '#ffffff' if delete else '#292c38'
            button.setStyleSheet(
                f"QToolButton {{ border:0; border-radius:10px; color:{foreground if glass else '#d75555' if delete else '#71777d'}; "
                f"background:{background if glass else 'transparent'}; font:{CONTROL_FONT_SIZE}px '{ui_font_family()}'; }}"
                "QToolButton:hover { background:rgba(120,130,155,65); }"
                "QToolButton:pressed { background:rgba(100,110,140,90); }")
        self.canvas.stop_transient_ui()
        if theme_changed:
            self.emphasis.start()
        self.update()

    @property
    def appearance_theme(self):
        return self.canvas.preferences.theme

    def corner_radius(self):
        return corner_radius(self.paper_rect(), self.appearance_theme)

    def event(self, event):
        result = super().event(event)
        if event.type() == QEvent.Type.WinIdChange and hasattr(self, 'emphasis') and not self._closing:
            self.refresh_appearance()
        return result

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
        from .appearance import GLASS_CONTROL_TOP, GLASS_CONTROL_RIGHT
        glass = self.appearance_theme == 'Glass' if self.canvas is not None else False
        top, inset = (GLASS_CONTROL_TOP,GLASS_CONTROL_RIGHT) if glass else (CONTROL_TOP,CONTROL_RIGHT)
        right = paper.right()-inset-CONTROL_WIDTH
        self.remove.setGeometry(round(right), round(paper.top()+top), CONTROL_WIDTH, CONTROL_HEIGHT)
        self.minus.setGeometry(round(right-CONTROL_WIDTH-CONTROL_GAP), round(paper.top()+top), CONTROL_WIDTH, CONTROL_HEIGHT)
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
        self.refresh_appearance()
        self.sync_shadow()
        if self.appearance_theme == 'Glass':
            self.emphasis.start()

    def hideEvent(self, event):
        if hasattr(self, 'emphasis'):
            self.emphasis.stop()
        self.desktop.release_appearance(self)
        if self._shadow is not None:
            self._shadow.hide()
        if self.canvas is not None and self.canvas.tool_overlay is not None:
            self.canvas.tool_overlay.hide()
        super().hideEvent(event)

    def sync_shadow(self):
        self.desktop.sync_decoration(self)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        paper = self.paper_rect()
        painter.setPen(Qt.PenStyle.NoPen)
        if self.desktop.paints_shadow:
            # Offscreen rendering has no native input region or shadow window.
            for spread in range(SHADOW, 0, -1):
                painter.setBrush(QColor(30, 38, 45, 2 + (SHADOW-spread)//2))
                painter.drawRoundedRect(paper.adjusted(-spread, -spread+1, spread, spread+1),
                                        RADIUS+spread, RADIUS+spread)
        paint_surface(painter, paper, self.appearance_theme, self.native_glass, self.display_policy,
                      emphasis=self.emphasis.value)

    def place(self, rect):
        self.desktop.place_board(self, rect)
        self.layout_children()
        self.sync_shadow()
        self.desktop.focus_window(self)
        (self.canvas or self).setFocus()
        self.activation_timer.start(0)

    def minimize_to_tray(self):
        self.prepare_hide()
        self.hide()
        self.minimized.emit(self)

    def prepare_hide(self):
        self.activation_timer.stop()
        self.cancel_window_gesture()
        if self.canvas is not None:
            self.canvas.suspended = True
            self.canvas.finish_editing(refocus=False)
            self.canvas.cancel_interaction()
            self.canvas.stop_transient_ui()

    def restore(self, *, activate=True):
        self.activation_timer.stop()
        if self.canvas is not None:
            self.canvas.suspended = False
        if activate:
            self.desktop.focus_window(self)
            (self.canvas or self).setFocus()
            self.activation_timer.start(0)
        else:
            self.desktop.show_without_activating(self)
        self.restored.emit(self)

    def activate_explicitly(self):
        if self.isVisible():
            self.desktop.focus_window(self)
            if self.canvas is not None and self.canvas.editor_overlay is not None:
                # Placement may still have its one queued activation when a
                # user starts typing. Preserve the editor's exclusive focus.
                self.canvas.editor_overlay.activate_editor()
            else:
                (self.canvas or self).setFocus()

    def closeEvent(self, event):
        self.activation_timer.stop()
        self.desktop.release_appearance(self)
        if hasattr(self, 'emphasis'):
            self.emphasis.stop()
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
        radius = self.corner_radius()
        if radius > RADIUS:
            # A large rounded corner has no painted pixels in the old 7×7
            # corner square. Follow its visible arc with the same grip depth.
            for horizontal, dx in ((Qt.Edge.LeftEdge,point.x()-r.left()),
                                   (Qt.Edge.RightEdge,r.right()-point.x())):
                for vertical, dy in ((Qt.Edge.TopEdge,point.y()-r.top()),
                                     (Qt.Edge.BottomEdge,r.bottom()-point.y())):
                    if (0 <= dx < radius and 0 <= dy < radius
                            and radius-EDGE_GRIP <= math.hypot(radius-dx,radius-dy) <= radius):
                        return horizontal | vertical
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
