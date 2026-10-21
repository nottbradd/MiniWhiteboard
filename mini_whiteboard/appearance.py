"""Shared visual values; native compositor and accessibility policy stay in adapters."""
from dataclasses import dataclass
from PySide6.QtCore import QEasingCurve, QElapsedTimer, QPointF, QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainterPath, QPen, QRegion

ANIMATION_MS = 140
ACCENT = '#2467f5'
GLASS_BORDER = '#f5f7ff'
GLASS_TINT = '#f5f5f7'
GLASS_FALLBACK = '#edf0f5'
WHITE = '#ffffff'
HOVER = '#e5ecfb'
GLASS_RADIUS = 32
POPOVER_RADIUS = 22
UI_INK = '#181b24'
UI_SECONDARY = '#4c5261'


def interface_font(role='action'):
    """Interface weights never enter the shared document/editor font path."""
    from .shortcuts import ui_font_family
    size, weight = {'heading': (13.5, QFont.Weight.Bold),
                    'action': (11.5, QFont.Weight.Medium),
                    'support': (10.5, QFont.Weight.Normal)}[role]
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


def surface(theme, native_glass, policy, *, preview=False):
    if theme != 'Glass' or policy.high_contrast:
        return QColor(WHITE)
    color = QColor(GLASS_TINT if native_glass else GLASS_FALLBACK)
    if policy.transparency and (native_glass or preview):
        color.setAlpha(32 if preview else 120)
    return color


def paint_surface(painter, rect, theme, native_glass, policy, *, popup=False, emphasis=0, preview=False):
    """A neutral backing, broad reflected light and one continuous optical edge.

    The compositor supplies frost. These static gradients suggest a polished
    curved edge without a texture, desktop readback or a continuously running timer.
    """
    from .settings import BORDER, BORDER_WIDTH
    radius = corner_radius(rect, theme, popup=popup)
    glass = theme == 'Glass' and not policy.high_contrast
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(surface(theme, native_glass, policy, preview=preview))
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
        if emphasis:
            # A brief light catch confined to the edge, beneath the fixed rim.
            # The document is always painted at its normal opacity/position.
            painter.setPen(QPen(QColor(255,255,255,round(85*emphasis)), 4.4))
            painter.drawRoundedRect(rect.adjusted(2.2,2.2,-2.2,-2.2), radius-2.2, radius-2.2)
        painter.setPen(QPen(edge, 1.35))
        painter.drawRoundedRect(rect.adjusted(.7,.7,-.7,-.7), radius-.7, radius-.7)
    elif popup:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRoundedRect(rect.adjusted(.5,.5,-.5,-.5), radius, radius)
    else:
        border = QColor(BORDER)
        if emphasis:
            accent = QColor(ACCENT)
            border = QColor(*(round(base*(1-emphasis)+light*emphasis) for base,light in
                              zip(border.getRgb()[:3],accent.getRgb()[:3])))
        painter.setPen(QPen(border, BORDER_WIDTH, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(rect.left()+radius, rect.top()+BORDER_WIDTH/2),
                         QPointF(rect.right()-radius, rect.top()+BORDER_WIDTH/2))


def paint_preview(painter, rect, native_glass, policy):
    if rect.isEmpty():
        return
    if not policy.transparency or policy.high_contrast:
        # No translucent fill when transparency is disabled. A static two-tone
        # perimeter remains precise and readable on both light and dark content.
        radius = corner_radius(rect, 'Glass')
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for color, width in (('#202124', 3), ('#ffffff', 1)):
            painter.setPen(QPen(QColor(color), width))
            painter.drawRoundedRect(rect.adjusted(1.5,1.5,-1.5,-1.5),
                                    max(0,radius-1.5), max(0,radius-1.5))
        return
    paint_surface(painter, rect, 'Glass', native_glass, policy, preview=True)


class Emphasis:
    """One bounded edge light catch; repeated triggers cannot extend its deadline."""
    def __init__(self, board):
        self.board = board
        self.value = 0
        self.clock = QElapsedTimer()
        self.animation = QVariantAnimation(board)
        self.animation.setDuration(ANIMATION_MS)
        self.animation.setStartValue(1.0)
        self.animation.setEndValue(0.0)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self.changed)
        self.deadline = QTimer(board)
        self.deadline.setSingleShot(True)
        self.deadline.setTimerType(Qt.TimerType.PreciseTimer)
        self.deadline.timeout.connect(self.stop)
        self.animation.finished.connect(self.stop)

    def changed(self, value):
        if value and self.clock.isValid() and self.clock.elapsed() >= ANIMATION_MS:
            self.stop()
            return
        self.value = value
        paper = self.board.paper_rect().toAlignedRect()
        self.board.update(QRegion(paper).subtracted(QRegion(paper.adjusted(5,5,-5,-5))))

    def start(self):
        if self.clock.isValid():
            return
        if self.board.isVisible() and self.board.display_policy.motion and not self.board.display_policy.high_contrast:
            self.clock.start()
            # QVariantAnimation may still cache its previous first value. Make
            # the first native paint explicit even when Qt emits no change.
            self.changed(1.0)
            self.animation.start()
            # Qt's shared animation clock can defer its first frame under load.
            # A separate deadline bounds presentation lifetime from the trigger.
            self.deadline.start(ANIMATION_MS)

    def stop(self):
        self.animation.stop()
        self.deadline.stop()
        self.clock.invalidate()
        if self.value:
            self.changed(0)
