"""Shared visual values; native compositor and accessibility policy stay in adapters."""
from dataclasses import dataclass
from PySide6.QtCore import QEasingCurve, QVariantAnimation
from PySide6.QtGui import QColor

ANIMATION_MS = 140
ACCENT = '#48bfd7'
GLASS_BORDER = '#93b9c3'
GLASS_TINT = '#e4f2f6'
GLASS_FALLBACK = '#e9f3f6'
WHITE = '#ffffff'
HOVER = '#e2f2f6'


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
        color.setAlpha(132)
    return color


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

    def start(self):
        self.stop()
        if self.board.display_policy.motion and not self.board.display_policy.high_contrast:
            self.animation.start()

    def stop(self):
        self.animation.stop()
        self.value = 0
