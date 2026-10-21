"""Theme-aware window actions with symmetric vector icons, independent of fonts."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QToolButton


class WindowControl(QToolButton):
    def __init__(self, board, *, delete=False):
        super().__init__(board)
        self.board, self.delete = board, delete
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
        policy = getattr(self.board, 'display_policy', None)
        contrast = policy is not None and policy.high_contrast
        glass = self.board.appearance_theme == 'Glass' and not contrast
        hover, pressed = self.underMouse(), self.isDown()
        destructive = self.delete and (hover or pressed)
        if contrast:
            fill, border, ink = QColor('white'), QColor('black'), QColor('black')
            if hover or pressed:
                fill, ink = QColor('black'), QColor('white')
        elif destructive:
            fill = QColor(218, 58, 73, 70 if pressed else 38)
            border, ink = QColor(183, 45, 59, 85), QColor('#9f2837')
        elif glass:
            fill = QColor(255, 255, 255, 118 if pressed else 94 if hover else 55)
            border, ink = QColor(255, 255, 255, 155), QColor('#303746')
        else:
            fill = QColor('#dfe5ee' if pressed else '#eaf0f7' if hover else '#f4f6f9')
            border, ink = QColor('#dce1e8'), QColor('#515967')
        # Inset the stroke by half a physical pixel, retaining alpha coverage
        # at every scale. Geometry/centre never depend on a font's bearings.
        pixel = 1 / self.devicePixelRatioF()
        rect = QRectF(self.rect()).adjusted(pixel/2, pixel/2, -pixel/2, -pixel/2)
        painter.setBrush(fill)
        painter.setPen(QPen(border, pixel))
        painter.drawRoundedRect(rect, 9, 9)
        if glass and not contrast:
            highlight = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            highlight.setColorAt(0, QColor(255, 255, 255, 40))
            highlight.setColorAt(1, QColor(255, 255, 255, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(highlight)
            painter.drawRoundedRect(rect.adjusted(pixel, pixel, -pixel, -pixel), 8, 8)
        pen = QPen(ink, 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        centre = QPointF(self.width()/2, self.height()/2)
        if self.delete:
            for sign in (-1, 1):
                painter.drawLine(centre + QPointF(-3.8, sign*3.8),
                                 centre + QPointF(3.8, -sign*3.8))
        else:
            painter.drawLine(centre + QPointF(-4.6, 0), centre + QPointF(4.6, 0))
