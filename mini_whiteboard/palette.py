"""Small temporary palette; number keys belong to this popup while it is open."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QColorDialog, QFrame, QGraphicsDropShadowEffect,
                              QGridLayout, QToolButton, QVBoxLayout)
from .settings import PALETTE_COLORS


class ColorPalette(QFrame):
    def __init__(self, canvas, identifiers):
        super().__init__(canvas.window(), Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.canvas, self.identifiers = canvas, set(identifiers)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 9, 9, 9)
        panel = QFrame()
        panel.setStyleSheet("QFrame { background:#fafbfc; border:1px solid #d5dbe0; border-radius:9px; }")
        shadow = QGraphicsDropShadowEffect(panel)
        shadow.setBlurRadius(15)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0,0,0,45))
        panel.setGraphicsEffect(shadow)
        grid = QGridLayout(panel)
        grid.setContentsMargins(9, 9, 9, 9)
        grid.setSpacing(5)
        for index, (name, color) in enumerate(PALETTE_COLORS):
            button = self.swatch(color, f"{index+1} · {name}")
            button.setText(str(index+1))
            grid.addWidget(button, 0, index)
        for index, color in enumerate(canvas.recent_colors[:7]):
            grid.addWidget(self.swatch(color, "Recent colour"), 1, index)
        custom = QToolButton()
        custom.setText("Custom colour…")
        custom.setStyleSheet("border:none; color:#303841; padding:4px;")
        custom.clicked.connect(self.custom_color)
        grid.addWidget(custom, 2, 0, 1, 7)
        layout.addWidget(panel)
        self.adjustSize()

    def swatch(self, color, label):
        button = QToolButton()
        button.setFixedSize(30, 30)
        button.setToolTip(label)
        foreground = '#202124' if QColor(color).lightness() > 130 else '#ffffff'
        button.setStyleSheet(f"QToolButton {{ background:{color}; color:{foreground}; border:1px solid #aab1b9; border-radius:7px; }}"
                             "QToolButton:hover { border:2px solid #738fae; }")
        button.clicked.connect(lambda checked=False, c=color: self.choose(c))
        return button

    def choose(self, color):
        self.canvas.apply_color(color, self.identifiers)
        self.close()

    def custom_color(self):
        self.hide()
        color = QColorDialog.getColor(QColor(self.canvas.active_color), self.canvas.window(), "Colour")
        if color.isValid():
            self.canvas.apply_color(color.name(), self.identifiers)
        self.close()

    def keyPressEvent(self, event):
        if Qt.Key.Key_1 <= event.key() <= Qt.Key.Key_7:
            self.choose(PALETTE_COLORS[event.key()-Qt.Key.Key_1][1])
        elif event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if not self.rect().contains(event.position().toPoint()):
            # Qt clears this flag for each new mouse event, so set it on the
            # dismissing press rather than when constructing the popup.
            self.setAttribute(Qt.WidgetAttribute.WA_NoMouseReplay)
            self.close()
            event.accept()
            return
        super().mousePressEvent(event)

    def closeEvent(self, event):
        self.canvas.palette = None
        if not self.canvas.suspended and self.canvas.window().isActiveWindow():
            self.canvas.setFocus(Qt.FocusReason.PopupFocusReason)
        self.canvas.sync_tool_overlay()
        super().closeEvent(event)

    def hideEvent(self, event):
        # Qt also dismisses a Popup on an outside click without calling close.
        QTimer.singleShot(0, self.canvas.sync_tool_overlay)
        super().hideEvent(event)
