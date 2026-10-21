"""Temporary feedback and an on-demand reference; no permanent tool controls."""
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QLabel, QVBoxLayout

from .appearance import ANIMATION_MS, interface_font
from .surfaces import Surface


class FeedbackLabel(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFont(interface_font('support'))
        self.opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity)
        self.fade = QPropertyAnimation(self.opacity, b"opacity", self)
        self.fade.setDuration(ANIMATION_MS)
        self.fade.setStartValue(1.0)
        self.fade.setEndValue(0.0)
        self.fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.fade.finished.connect(self.hide)
        self.delay = QTimer(self)
        self.delay.setSingleShot(True)
        self.delay.setInterval(1000)
        self.delay.timeout.connect(self.finish_delay)
        self.hide()

    def finish_delay(self):
        policy = getattr(self.window(), 'display_policy', None)
        if policy is not None and not policy.motion:
            self.hide()
        else:
            self.fade.start()

    def show_message(self, text):
        self.fade.stop()
        self.delay.stop()
        board = self.window()
        glass = board.appearance_theme == 'Glass' and board.display_policy.transparency
        self.setStyleSheet('color:#303644; border:1px solid rgba(255,255,255,170); '
                           'border-radius:10px; padding:6px 11px; '
                           f"background:{'rgba(247,248,252,220)' if glass else '#f0f2f4'};")
        self.setText(text)
        self.adjustSize()
        self.reposition()
        self.opacity.setOpacity(1)
        self.show()
        self.raise_()
        self.delay.start()

    def reposition(self):
        self.move(8, max(4, self.parentWidget().height()-self.height()-8))

    def stop(self):
        self.delay.stop()
        self.fade.stop()
        self.hide()


class ShortcutReference(Surface, QFrame):
    def __init__(self, board, preferences):
        super().__init__(board, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.init_surface(board.platform, preferences)
        self.setWindowTitle("Mini Whiteboard shortcuts")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        label = QLabel(board.platform.shortcuts.help_html(), self)
        label.setFont(interface_font('support'))
        label.setStyleSheet('color:#181b24; background:transparent;')
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(label)
        self.setFixedWidth(560)
        self.adjustSize()

    def paintEvent(self, event):
        self.paint_surface()
        super().paintEvent(event)

    def showEvent(self, event):
        board = self.parentWidget()
        self.findChild(QLabel).setText(board.platform.shortcuts.help_html())
        self.adjustSize()
        available = board.screen().availableGeometry()
        origin = board.frameGeometry().topRight()
        x = min(origin.x()+8, available.right()-self.width())
        y = min(origin.y(), available.bottom()-self.height())
        self.move(max(available.left(), x), max(available.top(), y))
        super().showEvent(event)
