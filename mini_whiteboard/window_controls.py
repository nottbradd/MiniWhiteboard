"""Theme-aware window actions with symmetric vector icons, independent of fonts."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QToolButton
from .chrome import ChromeSample, paint_chrome
from .settings import CONTROL_HIT_PADDING


class WindowControl(QToolButton):
    def __init__(self, board, *, delete=False):
        super().__init__(board)
        self.board, self.delete = board, delete
        self.chrome_sample = ChromeSample()
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setAccessibleName('Delete whiteboard' if delete else 'Minimise whiteboard')
        self.setToolTip('Delete this whiteboard and its contents' if delete else
                        f'Minimise this whiteboard to the {board.platform.shortcuts.status_location}')

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        hover, pressed = self.underMouse(), self.isDown()
        pad = CONTROL_HIT_PADDING
        rect = QRectF(self.rect()).adjusted(pad, pad, -pad, -pad)
        ink = paint_chrome(painter, self, rect, self.chrome_sample, hover=hover, pressed=pressed,
                           destructive=self.delete)
        pen = QPen(ink, 1.35)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        centre = QPointF(self.width()/2, self.height()/2)
        if self.delete:
            for sign in (-1, 1):
                painter.drawLine(centre + QPointF(-3.2, sign*3.2),
                                 centre + QPointF(3.2, -sign*3.2))
        else:
            painter.drawLine(centre + QPointF(-3.8, .25), centre + QPointF(3.8, .25))
