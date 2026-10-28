"""Temporary feedback and an on-demand reference; no permanent tool controls."""
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QFontMetrics, QPainter
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QGridLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from .appearance import ANIMATION_MS, interface_font
from .surfaces import Surface
from .chrome import ChromeSample, paint_chrome


class FeedbackLabel(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        font = interface_font('support')
        font.setPointSizeF(9)
        self.setFont(font)
        self.chrome_sample = ChromeSample()
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
        self.reposition()
        self.opacity.setOpacity(1)
        self.show()
        self.raise_()
        self.delay.start()

    def reposition(self):
        parent = self.parentWidget()
        margin = 10
        width = max(20, min(320, parent.width()-2*margin))
        fm = QFontMetrics(self.font())
        width = min(width, fm.horizontalAdvance(self.text())+16)
        flags = Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft
        text_rect = fm.boundingRect(QRect(0, 0, max(4, width-16), 10000), flags, self.text())
        height = min(max(22, text_rect.height()+8), max(22, parent.height()-2*margin))
        self.resize(width, height)
        self.move(margin, max(margin, parent.height()-height-margin))

    def paintEvent(self, event):
        painter = QPainter(self)
        ink = paint_chrome(painter, self, QRectF(self.rect()), self.chrome_sample, radius=7)
        painter.setPen(ink)
        painter.setFont(self.font())
        painter.drawText(self.rect().adjusted(8, 4, -8, -4),
                         Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         self.text())

    def hideEvent(self, event):
        self.delay.stop()
        self.fade.stop()
        super().hideEvent(event)

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
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(18)
        from . import APP_VERSION
        title = QLabel(f'Shortcuts <span style="font-size:10.5pt;font-weight:400"> · Mini Whiteboard {APP_VERSION}</span>')
        title.setFont(interface_font('heading'))
        title.setStyleSheet('color:#181b24; background:transparent;')
        layout.addWidget(title)
        self.content = QWidget()
        self.content.setStyleSheet('background:transparent;')
        self.grid = QGridLayout(self.content)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(28)
        self.grid.setVerticalSpacing(20)
        self.sections = []
        for _ in board.platform.shortcuts.help_sections():
            label = QLabel()
            label.setFont(interface_font('support'))
            label.setStyleSheet('color:#181b24; background:transparent;')
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.RichText)
            self.sections.append(label)
        self.label = self.sections[0]
        self.scroll = QScrollArea(self)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet('QScrollArea { background:transparent; border:0; }')
        self.scroll.viewport().setAutoFillBackground(False)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.content)
        self.scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.scroll.verticalScrollBar().setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.scroll)
        # Shape the reference only when requested, keeping board creation free
        # of six rich-text layouts that are usually never shown.

    def fit_reference(self):
        board = self.parentWidget()
        available = board.screen().availableGeometry()
        self.columns = 2 if available.width() >= 1000 and available.height() >= 600 else 1
        width = min(900 if self.columns == 2 else 500, available.width()-24)
        self.setFixedWidth(width)
        column_width = (width-70-28*(self.columns-1))//self.columns
        rows = (len(self.sections)+self.columns-1)//self.columns
        for index, (label, (title, body)) in enumerate(zip(self.sections, board.platform.shortcuts.help_sections())):
            self.grid.removeWidget(label)
            label.setText(f'<span style="font-size:12pt;font-weight:700">{title}</span><br>{body}')
            label.setFixedWidth(column_width)
            label.setFixedHeight(label.heightForWidth(column_width))
            self.grid.addWidget(label, index % rows, index // rows, Qt.AlignmentFlag.AlignTop)
            label.show()
        self.grid.invalidate()
        self.content.setFixedSize(width-70, self.grid.sizeHint().height())
        self.setFixedHeight(min(self.content.height()+88, available.height()-24))

    def paintEvent(self, event):
        self.paint_surface()
        super().paintEvent(event)

    def showEvent(self, event):
        board = self.parentWidget()
        self.fit_reference()
        available = board.screen().availableGeometry()
        origin = board.frameGeometry().topRight()
        x = min(origin.x()+8, available.right()-self.width())
        y = min(origin.y(), available.bottom()-self.height())
        self.move(max(available.left(), x), max(available.top(), y))
        super().showEvent(event)
