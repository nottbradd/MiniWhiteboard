"""Coordinate operations with no Qt or operating-system dependencies.

Rectangles use exclusive right/bottom edges, avoiding QRect's inclusive integer
corner convention. Desktop positions use native platform units (Windows pixels,
macOS points); document positions are always logical.
"""

from dataclasses import dataclass
import math

Point = tuple[float, float]


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self):
        return self.x + self.width

    @property
    def bottom(self):
        return self.y + self.height

    def expanded(self, amount):
        return Rect(self.x - amount, self.y - amount,
                    self.width + 2 * amount, self.height + 2 * amount)

    def intersection_area(self, other):
        return (max(0, min(self.right, other.right) - max(self.x, other.x)) *
                max(0, min(self.bottom, other.bottom) - max(self.y, other.y)))

    def contains(self, p):
        return self.x <= p[0] <= self.right and self.y <= p[1] <= self.bottom


def normalized(a: Point, b: Point) -> Rect:
    return Rect(min(a[0], b[0]), min(a[1], b[1]),
                abs(b[0] - a[0]), abs(b[1] - a[1]))


def local_point(physical: Point, origin: Point, scale: float) -> Point:
    return ((physical[0] - origin[0]) / scale,
            (physical[1] - origin[1]) / scale)


def large_enough(rect: Rect, scale: float) -> bool:
    from .settings import MIN_WIDTH, MIN_HEIGHT
    return rect.width >= MIN_WIDTH * scale and rect.height >= MIN_HEIGHT * scale


def constrained_end(a: Point, b: Point, kind: str, shift: bool,
                    ratio: float = 1.0) -> Point:
    if not shift:
        return b
    dx, dy = b[0] - a[0], b[1] - a[1]
    if kind in ("Line", "Arrow"):
        length = math.hypot(dx, dy)
        angle = round(math.atan2(dy, dx) / (math.pi / 4)) * (math.pi / 4)
        return a[0] + length * math.cos(angle), a[1] + length * math.sin(angle)
    if kind in ("Rectangle", "Ellipse"):
        ratio = 1.0
    width = max(abs(dx), abs(dy) * ratio)
    return (a[0] + math.copysign(width, dx or 1),
            a[1] + math.copysign(width / ratio, dy or 1))


class PlacementState:
    """One hold owns an anchor; release always ends it, including invalid sizes."""

    def __init__(self):
        self.anchor: Point | None = None

    @property
    def active(self):
        return self.anchor is not None

    def begin(self, point: Point):
        if self.anchor is not None:
            return False
        self.anchor = point
        return True

    def release(self, point: Point, scale: float = 1.0):
        if self.anchor is None:
            return "idle", None
        rect = normalized(self.anchor, point)
        self.anchor = None
        if (not all(math.isfinite(v) for v in (rect.x, rect.y, rect.width, rect.height, scale))
                or scale <= 0 or not large_enough(rect, scale)):
            return "too_small", rect
        return "confirmed", rect

    def cancel(self):
        self.anchor = None
