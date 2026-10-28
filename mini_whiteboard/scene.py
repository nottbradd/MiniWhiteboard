"""Cheap broad-phase records and sparse previews; no document mutation here."""
from dataclasses import dataclass
from PySide6.QtCore import QRectF
from . import rendering
from .document import Shape, Text, Stroke


@dataclass
class Record:
    obj: object
    bounds: QRectF
    hit_bounds: QRectF
    paint: rendering.PaintData

    @classmethod
    def make(cls, obj, paint=None):
        paint = rendering.paint_data(obj) if paint is None else paint
        matrix = rendering.qt_transform(obj.transform)
        bounds = matrix.map(paint.remaining).boundingRect()
        hit = bounds
        if not bounds.isEmpty():
            if isinstance(obj, Text):
                for rect in rendering.text_hit_rects(obj.text, obj.size, obj.layout_width):
                    hit = hit.united(matrix.mapRect(rect.translated(*obj.position)))
            elif isinstance(obj, Shape) and obj.kind not in ("Line", "Arrow"):
                hit = hit.united(matrix.mapRect(paint.path.boundingRect()))
            hit = hit.adjusted(-5, -5, 5, 5)
        return cls(obj, bounds, hit, paint)


class Scene:
    def __init__(self):
        self.source = None
        self.records = {}
        self.order = ()
        self.editable_order = ()
        self.previews = {}

    def sync(self, objects):
        if self.source is objects:
            return
        current = {**self.records, **self.previews}
        self.records = {obj.id: current[obj.id] if current.get(obj.id) is not None and current[obj.id].obj is obj
                        else Record.make(obj) for obj in objects}
        self.order = tuple(obj.id for obj in objects)
        self.editable_order = tuple(obj.id for obj in objects if not obj.locked)
        self.source = objects
        self.previews.clear()

    def record(self, identifier):
        return self.previews.get(identifier, self.records.get(identifier))

    def query(self, rect, *, hits=False, reverse=False, editable=False, strokes_only=False):
        order = self.editable_order if editable else self.order
        for identifier in reversed(order) if reverse else order:
            record = self.record(identifier)
            if record is None or (editable and record.obj.locked) or (strokes_only and not isinstance(record.obj, Stroke)):
                continue
            if record is not None and (record.hit_bounds if hits else record.bounds).intersects(rect):
                yield record

    def preview(self, identifier, obj, *, transform_only=False):
        old = self.record(identifier)
        paint = self.records[identifier].paint if transform_only else None
        new = Record.make(obj, paint) if obj is not None else None
        self.previews[identifier] = new
        return (old.bounds if old else QRectF()).united(new.bounds if new else QRectF())

    def after(self):
        return tuple(record.obj for identifier in self.order if (record := self.record(identifier)) is not None)

    def clear_preview(self):
        dirty = QRectF()
        for identifier, record in self.previews.items():
            if record is not None:
                dirty = dirty.united(record.bounds)
            dirty = dirty.united(self.records[identifier].bounds)
        self.previews.clear()
        return dirty
