"""Purely decorative window; it can never receive mouse or keyboard input."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget

from .settings import RADIUS, SHADOW


class PaperShadow(QWidget):
    def __init__(self, board):
        super().__init__(board, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowTransparentForInput |
                         Qt.WindowType.WindowDoesNotAcceptFocus)
        self.board = board
        self.desktop = board.desktop
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def sync(self):
        self.desktop.set_window_rect(self, self.desktop.window_rect(self.board))
        if self.board.isVisible():
            self.show()
            self.desktop.set_window_rect(self, self.desktop.window_rect(self.board))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        paper = self.board.paper_rect()
        radius = self.board.corner_radius()
        ring = QPainterPath()
        ring.addRect(self.rect())
        hole = QPainterPath()
        hole.addRoundedRect(paper, radius, radius)
        painter.setClipPath(ring.subtracted(hole))
        painter.setPen(Qt.PenStyle.NoPen)
        for spread in range(SHADOW, 0, -1):
            painter.setBrush(QColor(30, 38, 45, 2 + (SHADOW-spread)//2))
            painter.drawRoundedRect(paper.adjusted(-spread, -spread+1, spread, spread+1),
                                    radius+spread, radius+spread)
