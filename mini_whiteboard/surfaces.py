"""Rounded temporary surfaces, retaining QMenu's native input and navigation."""
from PySide6.QtCore import QEvent, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QRegion
from PySide6.QtWidgets import QLabel, QMenu, QWidgetAction

from .appearance import Emphasis, corner_radius, interface_font, paint_surface


class Surface:
    """Small lifecycle shared by app-owned popups; no background polling."""
    def init_surface(self, platform, preferences):
        self.platform, self.desktop, self.preferences = platform, platform.desktop, preferences
        self._closing = False
        self.native_glass = False
        self.display_policy = self.desktop.display_policy()
        self.emphasis = Emphasis(self)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.preferences.appearance_changed.connect(self.dismiss_for_theme)

    @property
    def appearance_theme(self):
        return self.preferences.theme

    def paper_rect(self):
        return QRectF(self.rect())

    def contains_input(self, position):
        path = QPainterPath()
        path.addRoundedRect(self.paper_rect(), self.corner_radius(), self.corner_radius())
        return path.contains(position)

    def physical_paper_rect(self):
        return self.desktop.window_rect(self)

    def corner_radius(self):
        return corner_radius(self.paper_rect(), self.appearance_theme, popup=True)

    def dismiss_for_theme(self):
        self.hide()
        self.desktop.release_appearance(self)

    def refresh_appearance(self):
        self.emphasis.stop()
        if isinstance(self, QMenu) and self.platform.shortcuts.mac:
            return
        self.desktop.release_appearance(self)
        self.display_policy = self.desktop.display_policy()
        self.native_glass = self.desktop.apply_appearance(self) if self.isVisible() else False
        self.sync_surface()
        self.update()

    def sync_surface(self):
        if isinstance(self, QMenu) and self.platform.shortcuts.mac:
            return
        if not self.isVisible():
            return
        # Binary widget masks cut the alpha fringe, especially at fractional
        # DPR. The painted alpha owns the edge; explicit paths own Qt input.
        self.clearMask()
        if self.platform.name == 'macos':
            self.desktop.sync_surface(self)
        host = getattr(self, '_backdrop', None)
        if host is not None:
            try:
                host.sync(self)
            except OSError:
                self.desktop.release_appearance(self)
                self.native_glass = False
                self.update()

    def showEvent(self, event):
        super().showEvent(event)
        if isinstance(self, QMenu) and self.platform.shortcuts.mac:
            return
        if self.platform.name == 'macos':
            self.desktop.configure_overlay(self, interactive=not bool(
                self.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus))
        self.refresh_appearance()
        if self.appearance_theme == 'Glass':
            self.emphasis.start()

    def hideEvent(self, event):
        self.emphasis.stop()
        self.desktop.release_appearance(self)
        self.native_glass = False
        super().hideEvent(event)

    def closeEvent(self, event):
        self.emphasis.stop()
        self.desktop.release_appearance(self)
        super().closeEvent(event)

    def moveEvent(self, event):
        super().moveEvent(event)
        self.sync_surface()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.sync_surface()

    def event(self, event):
        result = super().event(event)
        if event.type() in (QEvent.Type.WinIdChange,QEvent.Type.DevicePixelRatioChange) and hasattr(self, 'preferences') and self.isVisible():
            self.refresh_appearance()
        return result

    def nativeEvent(self, event_type, message):
        if hasattr(self, 'desktop') and not (isinstance(self, QMenu) and self.platform.shortcuts.mac):
            result = self.desktop.native_event(self, event_type, message)
            if result is not None:
                return result
        return super().nativeEvent(event_type, message)

    def paint_surface(self):
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        paint_surface(painter, self.paper_rect(), self.appearance_theme, self.native_glass,
                      self.display_policy, popup=True, emphasis=self.emphasis.value)
        painter.end()


class SurfaceMenu(Surface, QMenu):
    def __init__(self, platform, preferences, parent=None, title=''):
        super().__init__(title, parent)
        self.init_surface(platform, preferences)
        self.setFont(interface_font('action'))
        # Cocoa's NSMenu is OS-owned. Preserve its native material, navigation,
        # accessibility and popup behaviour rather than painting a replacement.
        if not platform.shortcuts.mac:
            self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
            self.setStyleSheet(
                'QMenu { background:transparent; border:0; padding:14px; color:#181b24; }'
                'QMenu::item { background:transparent; min-height:20px; padding:10px 28px 10px 18px; border-radius:10px; }'
                'QMenu::item:checked { background:rgba(255,255,255,100); }'
                'QMenu::item:selected { background:rgba(228,238,255,205); color:#123eae; }'
                'QMenu::item:disabled { color:#616775; }'
                'QMenu::separator { height:1px; background:rgba(90,105,130,35); margin:9px 6px; }'
                'QMenu::indicator { width:0; height:0; }')

    def addMenu(self, title):
        if not isinstance(title, str):
            return super().addMenu(title)
        child = SurfaceMenu(self.platform, self.preferences, self, title)
        super().addMenu(child)
        if title in ('Appearance', 'Hide All shortcut'):
            child.add_heading(title)
        return child

    def clear(self):
        for action in self.actions():
            child = action.menu()
            if child is not None:
                child.close()
                child.deleteLater()
        super().clear()

    def add_heading(self, title):
        if not self.platform.shortcuts.mac:
            action = QWidgetAction(self)
            action.setText(title)
            label = QLabel(title)
            label.setFont(interface_font('heading'))
            label.setMinimumWidth(206)
            label.setStyleSheet('color:#181b24; background:transparent; padding:8px 18px 12px;')
            action.setDefaultWidget(label)
            self.addAction(action)
        else:
            action = self.addAction(title)
        action.setFont(interface_font('heading'))
        action.setEnabled(False)
        return action

    def paintEvent(self, event):
        if not self.platform.shortcuts.mac:
            self.paint_surface()
        super().paintEvent(event)
        if not self.platform.shortcuts.mac:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            for action in self.actions():
                if action.isVisible() and action.isChecked():
                    row = self.actionGeometry(action)
                    x, y = row.right()-18, row.center().y()
                    pen = QPen(QColor('#2467f5' if action.isEnabled() else '#737b89'), 2.2)
                    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    painter.setPen(pen)
                    painter.drawPolyline([QPointF(x-5,y),QPointF(x-1,y+4),QPointF(x+6,y-4)])
            painter.end()

    def mousePressEvent(self, event):
        if not self.platform.shortcuts.mac and not self.contains_input(event.position()):
            self.setAttribute(Qt.WidgetAttribute.WA_NoMouseReplay)
            self.close()
            event.accept()
            return
        super().mousePressEvent(event)
