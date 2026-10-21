"""Small temporary palette; number keys belong to this popup while it is open."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QFrame, QGridLayout, QLabel, QToolButton, QVBoxLayout
from .settings import PALETTE_COLORS
from .appearance import interface_font
from .surfaces import Surface


class ColorPalette(Surface, QFrame):
    def __init__(self, canvas, identifiers):
        super().__init__(canvas.window(), Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.canvas, self.identifiers = canvas, set(identifiers)
        self.init_surface(canvas.window().platform, canvas.preferences)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        panel = QFrame()
        grid = QGridLayout(panel)
        grid.setContentsMargins(24, 20, 24, 18)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(18)
        heading = QLabel('Colour')
        heading.setFont(interface_font('heading'))
        heading.setStyleSheet('color:#181b24; background:transparent;')
        grid.addWidget(heading, 0, 0, 1, 7)
        for index, (name, color) in enumerate(PALETTE_COLORS):
            button = self.swatch(color, f"{index+1} · {name}")
            grid.addWidget(button, 1, index)
        for index, color in enumerate(canvas.recent_colors[:7]):
            grid.addWidget(self.swatch(color, "Recent colour"), 2, index)
        custom = QToolButton()
        custom.setText("Custom colour…")
        custom.setFont(interface_font('action'))
        custom.setStyleSheet('QToolButton { border:none; border-top:1px solid rgba(90,105,130,30); '
                            'border-radius:9px; color:#181b24; padding:12px 4px 6px; background:transparent; }'
                            'QToolButton:hover, QToolButton:focus { background:rgba(228,238,255,205); color:#123eae; }')
        custom.setAccessibleName('Custom colour')
        custom.clicked.connect(self.custom_color)
        grid.addWidget(custom, 3, 0, 1, 7)
        layout.addWidget(panel)
        self.adjustSize()

    def paintEvent(self, event):
        self.paint_surface()
        super().paintEvent(event)

    def swatch(self, color, label):
        button = QToolButton()
        button.setFixedSize(32, 32)
        button.setToolTip(label)
        button.setAccessibleName(label)
        button.setCheckable(True)
        button.setChecked(QColor(color) == QColor(self.canvas.active_color))
        foreground = '#202124' if QColor(color).lightness() > 130 else '#ffffff'
        button.setStyleSheet(f"QToolButton {{ background:{color}; color:{foreground}; border:1px solid rgba(60,65,85,40); border-radius:16px; }}"
                             'QToolButton:checked { border:3px solid #2467f5; }'
                             'QToolButton:hover { border:3px solid #ffffff; }'
                             'QToolButton:focus { border:3px dashed #2467f5; }')
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
        if not self.contains_input(event.position()):
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
