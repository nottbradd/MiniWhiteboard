"""Immutable drawing objects and per-board transactional history.

Snapshots share immutable objects, including stroke point tuples. Resizing a
window never mutates this model. No Qt types are needed to test document state.
"""
from dataclasses import dataclass, field, replace
from uuid import uuid4
import math

from .geometry import Point
from .transforms import Affine, Erasure, PaintClip, IDENTITY, translation
from .settings import INK, TEXT_MIN_WIDTH, TEXT_DEFAULT_WIDTH, TEXT_MAX_WIDTH


def new_id():
    return uuid4().hex


@dataclass(frozen=True)
class Stroke:
    points: tuple[Point, ...]
    width: float = 2
    id: str = field(default_factory=new_id)
    transform: Affine = IDENTITY
    erasures: tuple[Erasure, ...] = ()
    clip: PaintClip | None = None
    color: str = INK
    locked: bool = False


@dataclass(frozen=True)
class Shape:
    kind: str
    a: Point
    b: Point
    width: float = 2
    id: str = field(default_factory=new_id)
    transform: Affine = IDENTITY
    erasures: tuple[Erasure, ...] = ()
    clip: PaintClip | None = None
    color: str = INK
    locked: bool = False


@dataclass(frozen=True)
class Text:
    position: Point
    text: str = ""
    size: float = 14
    id: str = field(default_factory=new_id)
    transform: Affine = IDENTITY
    erasures: tuple[Erasure, ...] = ()
    clip: PaintClip | None = None
    color: str = INK
    locked: bool = False
    layout_width: float = TEXT_DEFAULT_WIDTH

    def __post_init__(self):
        width = self.layout_width
        if (isinstance(width, bool) or not isinstance(width, (int, float))
                or not math.isfinite(width) or not TEXT_MIN_WIDTH <= width <= TEXT_MAX_WIDTH):
            raise ValueError("Invalid text layout width")
        # QTextEdit's fixed pixel wrap width is integral in local logical units.
        object.__setattr__(self, "layout_width", round(width))


@dataclass(frozen=True)
class ImageObject:
    position: Point
    png: bytes
    pixel_size: tuple[int, int]
    id: str = field(default_factory=new_id)
    transform: Affine = IDENTITY
    erasures: tuple[Erasure, ...] = ()
    clip: PaintClip | None = None
    locked: bool = False


Object = Stroke | Shape | Text | ImageObject


def moved(obj: Object, dx: float, dy: float) -> Object:
    return transformed(obj, translation(dx, dy))


def transformed(obj: Object, matrix: Affine) -> Object:
    return replace(obj, transform=matrix @ obj.transform)


@dataclass(frozen=True)
class Edit:
    before: tuple[Object, ...]
    after: tuple[Object, ...]
    label: str


class Document:
    def __init__(self):
        self.objects: tuple[Object, ...] = ()
        self.history: list[Edit] = []
        self.index = 0

    def get(self, identifier):
        return next((obj for obj in self.objects if obj.id == identifier), None)

    def commit(self, objects, label, *, merge=False):
        after = tuple(objects)
        if after == self.objects:
            return False
        del self.history[self.index:]
        if merge and self.index and self.history[-1].label == label:
            self.history[-1] = Edit(self.history[-1].before, after, label)
            self.objects = after
            return True
        self.history.append(Edit(self.objects, after, label))
        self.index += 1
        self.objects = after
        return True

    def add(self, obj, label="Create object"):
        return self.commit((*self.objects, obj), label)

    def replace(self, obj, label="Change object"):
        if self.get(obj.id) is None:
            raise KeyError(obj.id)
        return self.commit((obj if old.id == obj.id else old for old in self.objects), label)

    def delete(self, identifiers, label="Delete object"):
        ids = set(identifiers)
        return self.commit((obj for obj in self.objects if obj.id not in ids), label)

    def undo(self):
        if self.index == 0:
            return False
        self.index -= 1
        self.objects = self.history[self.index].before
        return True

    def redo(self):
        if self.index == len(self.history):
            return False
        self.objects = self.history[self.index].after
        self.index += 1
        return True
