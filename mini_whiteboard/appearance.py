"""Shared visual values; native compositor and accessibility policy stay in adapters."""
from dataclasses import dataclass
from PySide6.QtCore import QEasingCurve, QElapsedTimer, QPointF, QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QPen, QRegion

ANIMATION_MS = 140
ACCENT = '#2467f5'
GLASS_TINT = '#f5f5f7'
GLASS_FALLBACK = '#edf0f5'
WHITE = '#ffffff'
HOVER = '#e5ecfb'
GLASS_RADIUS = 32
POPOVER_RADIUS = 22
UI_INK = '#181b24'
UI_SECONDARY = '#4c5261'
LIQUID = 'Liquid Glass'
FROSTED = 'Frosted Glass'
THEMES = ('White', LIQUID, FROSTED)
OPAQUE = 'Opaque'


def is_glass(theme):
    return theme in (LIQUID, FROSTED, 'Glass')


def interface_font(role='action'):
    """Interface weights never enter the shared document/editor font path."""
    from .shortcuts import ui_font_family
    size, weight = {'heading': (13.5, QFont.Weight.Bold),
                    'compact_heading': (11.5, QFont.Weight.DemiBold),
                    'action': (11.5, QFont.Weight.Medium),
                    'support': (10.5, QFont.Weight.Normal)}[role]
    font = QFont(ui_font_family())
    font.setPointSizeF(size)
    font.setWeight(weight)
    return font


def corner_radius(rect, theme, *, popup=False):
    from .settings import RADIUS
    preferred = POPOVER_RADIUS if popup else GLASS_RADIUS if is_glass(theme) else RADIUS
    return min(preferred, rect.width()/2, rect.height()/2)


@dataclass(frozen=True)
class DisplayPolicy:
    transparency: bool = True
    motion: bool = True
    high_contrast: bool = False


def surface(theme, native_glass, policy, *, preview=False, popup=False):
    if not is_glass(theme) or policy.high_contrast:
        return QColor(WHITE)
    if not policy.transparency or (not native_glass and not preview):
        return QColor(GLASS_FALLBACK)
    tint = QColor(GLASS_TINT)
    # Controls get their own legibility backing. Changing tint never moves ink
    # or alters the radius/blur of the native optical material.
    alpha = 194 if popup else 22 if native_glass == LIQUID else 66
    tint.setAlpha(32 if preview else alpha)
    return tint


def paint_surface(painter, rect, theme, native_glass, policy, *, popup=False, emphasis=0, preview=False):
    """Paint the legibility backing and fine edge underneath Qt foreground content."""
    from .settings import BORDER, BORDER_WIDTH
    radius = corner_radius(rect, theme, popup=popup)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(surface(theme, native_glass, policy, preview=preview, popup=popup))
    painter.drawRoundedRect(rect, radius, radius)
    if is_glass(theme):
        # AppKit renders the displaced background, specular rim and dispersion.
        # Frost has a single quiet edge. The opaque material has no optical rim.
        liquid = native_glass == LIQUID and policy.transparency and not policy.high_contrast
        edge = (QColor(255, 255, 255, 102) if liquid else QColor(79, 93, 110, 69))
        if policy.high_contrast:
            edge = QColor(UI_INK)
        elif preview:
            edge = QColor(248, 252, 255, 225)
        elif emphasis:
            edge = QColor(63, 91, 129, round(69 + 58*emphasis))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(edge, 1))
        painter.drawRoundedRect(rect.adjusted(.5, .5, -.5, -.5), max(0, radius-.5), max(0, radius-.5))
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
