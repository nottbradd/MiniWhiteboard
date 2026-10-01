"""Immutable affine geometry. All drag results are relative to their start state."""
from dataclasses import dataclass
import math

from .geometry import Point, Rect


@dataclass(frozen=True)
class Affine:
    a: float = 1
    b: float = 0
    c: float = 0
    d: float = 1
    tx: float = 0
    ty: float = 0

    def map(self, p: Point) -> Point:
        return self.a*p[0] + self.c*p[1] + self.tx, self.b*p[0] + self.d*p[1] + self.ty

    def __matmul__(self, other):
        """Composition: (a @ b).map(p) applies b, then a."""
        return Affine(self.a*other.a+self.c*other.b, self.b*other.a+self.d*other.b,
                      self.a*other.c+self.c*other.d, self.b*other.c+self.d*other.d,
                      *self.map((other.tx, other.ty)))

    def inverse(self):
        det = self.a*self.d - self.b*self.c
        if not math.isfinite(det) or abs(det) < 1e-15:
            raise ValueError("Singular object transform")
        return Affine(self.d/det, -self.b/det, -self.c/det, self.a/det,
                      (self.c*self.ty-self.d*self.tx)/det,
                      (self.b*self.tx-self.a*self.ty)/det)

    @property
    def scale(self):
        return math.hypot(self.a, self.b)


IDENTITY = Affine()


def translation(x, y):
    return Affine(tx=x, ty=y)


def rotation(degrees):
    angle = math.radians(degrees)
    c, s = math.cos(angle), math.sin(angle)
    return Affine(c, s, -s, c)


def around(anchor, matrix):
    return translation(*anchor) @ matrix @ translation(-anchor[0], -anchor[1])


@dataclass(frozen=True)
class PaintClip:
    """Frozen creation/brush footprint; independent of later viewport resizing."""
    viewport: Rect
    paper: Rect
    radius: float
    exclusions: tuple[Rect, ...] = ()


@dataclass(frozen=True)
class Erasure:
    """A round swept brush, mapped to the object's original coordinate system."""
    start: Point
    end: Point
    radius: float
    to_local: Affine = IDENTITY
    clip: PaintClip | None = None


@dataclass(frozen=True)
class SelectionFrame:
    center: Point
    width: float
    height: float
    angle: float = 0

    def handle(self, index):
        fractions = ((-1, -1), (0, -1), (1, -1), (1, 0),
                     (1, 1), (0, 1), (-1, 1), (-1, 0))
        x, y = fractions[index]
        offset = rotation(self.angle).map((x*self.width/2, y*self.height/2))
        return self.center[0]+offset[0], self.center[1]+offset[1]

    def rotation_handle(self, distance=24):
        offset = rotation(self.angle).map((0, -self.height/2-distance))
        return self.center[0]+offset[0], self.center[1]+offset[1]

    def contains(self, p):
        x, y = rotation(-self.angle).map((p[0]-self.center[0], p[1]-self.center[1]))
        return abs(x) <= self.width/2 and abs(y) <= self.height/2

    def transformed(self, matrix):
        basis = matrix @ rotation(self.angle)
        return SelectionFrame(matrix.map(self.center), self.width*math.hypot(basis.a, basis.b),
                              self.height*math.hypot(basis.c, basis.d),
                              math.degrees(math.atan2(basis.b, basis.a)))


def resize_transform(frame, handle, start, current, proportional=False):
    """Resize along the captured frame axes, preserving the opposite anchor."""
    anchor = frame.handle((handle+4) % 8)
    tip = frame.handle(handle)
    unrotate = rotation(-frame.angle)
    vx, vy = unrotate.map((tip[0]-anchor[0], tip[1]-anchor[1]))
    dx, dy = unrotate.map((current[0]-start[0], current[1]-start[1]))
    uniform = proportional or handle % 2 == 0
    if uniform:
        factor = 1+(vx*dx+vy*dy)/max(vx*vx+vy*vy, 1e-12)
        sx = sy = max(1/max(min(frame.width, frame.height), 1), factor)
    else:
        sx = max(1/max(frame.width, 1), 1+dx/vx) if abs(vx) > 1e-9 else 1
        sy = max(1/max(frame.height, 1), 1+dy/vy) if abs(vy) > 1e-9 else 1
    if not all(math.isfinite(n) for n in (sx, sy)):
        return IDENTITY
    return around(anchor, rotation(frame.angle) @ Affine(a=sx, d=sy) @ rotation(-frame.angle))


def rotate_transform(frame, start, current, snap=False):
    cx, cy = frame.center
    if math.dist(frame.center, current) < 1e-6:
        return IDENTITY
    angle = math.degrees(math.atan2(current[1]-cy, current[0]-cx)
                         - math.atan2(start[1]-cy, start[0]-cx))
    if snap:
        angle = round((frame.angle+angle)/15)*15-frame.angle
    return around(frame.center, rotation(angle))
