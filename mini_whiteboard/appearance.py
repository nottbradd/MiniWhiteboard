"""Shared visual values; native compositor and accessibility policy stay in adapters."""
from dataclasses import dataclass
from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainterPath, QPen

ANIMATION_MS = 140
ACCENT = '#2467f5'
GLASS_BORDER = '#f5f7ff'
GLASS_TINT = '#f5f5f7'
GLASS_FALLBACK = '#edf0f5'
WHITE = '#ffffff'
HOVER = '#e5ecfb'
GLASS_RADIUS = 32
POPOVER_RADIUS = 22
GLASS_CONTROL_TOP, GLASS_CONTROL_RIGHT = 7, 10
UI_INK = '#181b24'
UI_SECONDARY = '#4c5261'


def interface_font(role='action'):
    """Interface weights never enter the shared document/editor font path."""
    from .shortcuts import ui_font_family
    size, weight = {'heading': (12, QFont.Weight.Bold),
                    'action': (10.5, QFont.Weight.Medium),
                    'support': (10, QFont.Weight.Normal)}[role]
    font = QFont(ui_font_family())
    font.setPointSizeF(size)
    font.setWeight(weight)
    return font


def corner_radius(rect, theme, *, popup=False):
    from .settings import RADIUS
    preferred = POPOVER_RADIUS if popup else GLASS_RADIUS if theme == 'Glass' else RADIUS
    return min(preferred, rect.width()/2, rect.height()/2)


@dataclass(frozen=True)
class DisplayPolicy:
    transparency: bool = True
    motion: bool = True
    high_contrast: bool = False


def surface(theme, native_glass, policy):
    if theme != 'Glass' or policy.high_contrast:
        return QColor(WHITE)
    color = QColor(GLASS_TINT if native_glass else GLASS_FALLBACK)
    if native_glass and policy.transparency:
        color.setAlpha(38)
    return color


def paint_surface(painter, rect, theme, native_glass, policy, *, popup=False, emphasis=0):
    """A neutral backing, broad reflected light and a thin double optical rim.

    The compositor supplies frost. These static gradients suggest a polished
    curved edge without a texture, desktop readback or a continuously running timer.
    """
    from .settings import BORDER, BORDER_WIDTH
    radius = corner_radius(rect, theme, popup=popup)
    glass = theme == 'Glass' and not policy.high_contrast
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(surface(theme, native_glass, policy))
    painter.drawRoundedRect(rect, radius, radius)
    if glass:
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.save()
        painter.setClipPath(path)
        light = QLinearGradient(rect.topLeft(), rect.bottomRight())
        for stop, color in ((0, QColor(255,255,255,54)), (.24, QColor(255,255,255,9)),
                            (.62, QColor(255,255,255,0)), (1, QColor(210,220,246,30))):
            light.setColorAt(stop, color)
        painter.fillRect(rect, light)
        # A broad, very faint top reflection, independent of document content.
        top = QLinearGradient(0, rect.top(), 0, rect.top()+min(54, rect.height()/3))
        top.setColorAt(0, QColor(255,255,255,29))
        top.setColorAt(1, QColor(255,255,255,0))
        painter.fillRect(rect, top)
        painter.restore()
        edge = QLinearGradient(rect.topLeft(), rect.bottomRight())
        edge.setColorAt(0, QColor(255,255,255,244))
        edge.setColorAt(.36, QColor(255,255,255,136))
        edge.setColorAt(.7, QColor(220,231,255,120))
        edge.setColorAt(1, QColor(255,255,255,222))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(edge, 1.15 + .3*emphasis))
        painter.drawRoundedRect(rect.adjusted(.7,.7,-.7,-.7), radius-.7, radius-.7)
        # The darker inner hairline gives the light edge visible depth over white.
        painter.setPen(QPen(QColor(65,77,107,43), .8))
        painter.drawRoundedRect(rect.adjusted(2.4,2.4,-2.4,-2.4), radius-2.4, radius-2.4)
        painter.setPen(QPen(QColor(255,255,255,76), .8))
        painter.drawRoundedRect(rect.adjusted(3.5,3.5,-3.5,-3.5), radius-3.5, radius-3.5)
    elif popup:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRoundedRect(rect.adjusted(.5,.5,-.5,-.5), radius, radius)
    else:
        border = QColor(ACCENT if emphasis else BORDER)
        painter.setPen(QPen(border, BORDER_WIDTH, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(rect.left()+radius, rect.top()+BORDER_WIDTH/2),
                         QPointF(rect.right()-radius, rect.top()+BORDER_WIDTH/2))


class Emphasis:
    """One bounded top-edge emphasis; artwork and window geometry never animate."""
    def __init__(self, board):
        self.board = board
        self.value = 0
        self.animation = QVariantAnimation(board)
        self.animation.setDuration(ANIMATION_MS)
        self.animation.setStartValue(1.0)
        self.animation.setEndValue(0.0)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self.changed)

    def changed(self, value):
        self.value = value
        self.board.update(0, 0, self.board.width(), 18)
        self.board.update(0, self.board.height()-5, self.board.width(), 5)
        self.board.update(0, 18, 5, self.board.height()-23)
        self.board.update(self.board.width()-5, 18, 5, self.board.height()-23)

    def start(self):
        self.stop()
        if self.board.isVisible() and self.board.display_policy.motion and not self.board.display_policy.high_contrast:
            self.animation.start()

    def stop(self):
        self.animation.stop()
        self.value = 0
