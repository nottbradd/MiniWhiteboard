"""Temporary feedback and an on-demand reference; no permanent tool controls."""
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QLabel, QVBoxLayout

from .shortcuts import ui_font_family
from .appearance import ANIMATION_MS


class FeedbackLabel(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet("background: #f0f2f4; color: #48535e; border-radius: 6px; "
                           f"padding: 5px 9px; font: 10pt '{ui_font_family()}';")
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


class ShortcutReference(QFrame):
    def __init__(self, board):
        super().__init__(board, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("Mini Whiteboard shortcuts")
        self.setStyleSheet("QFrame { background: #fafbfc; color: #303841; "
                           "border: 1px solid #d5dbe0; border-radius: 9px; }"
                           f"QLabel {{ border: none; font: 10pt '{ui_font_family()}'; }}")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        label = QLabel(board.platform.shortcuts.help_html(), self)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(label)
        self.setFixedWidth(510)
        self.adjustSize()

    def showEvent(self, event):
        board = self.parentWidget()
        available = board.screen().availableGeometry()
        origin = board.frameGeometry().topRight()
        x = min(origin.x()+8, available.right()-self.width())
        y = min(origin.y(), available.bottom()-self.height())
        self.move(max(available.left(), x), max(available.top(), y))
        super().showEvent(event)
