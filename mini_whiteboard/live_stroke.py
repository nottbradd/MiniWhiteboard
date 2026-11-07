"""Gesture-local geometry: no immutable intermediate strokes in global caches."""
from dataclasses import replace
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainterPath
from . import rendering


class LiveStroke:
    def __init__(self, stroke):
        self.stroke = stroke
        self.points = list(stroke.points)
        self.prefix = QPainterPath(QPointF(*self.points[0]))
        x, y = self.points[0]
        self.extents = [x, y, x, y]
        self._data = None

    def append(self, point):
        if len(self.points) >= 2:
            previous = self.points[-1]
            self.prefix.quadTo(QPointF(*previous), QPointF(
                (previous[0]+point[0])/2, (previous[1]+point[1])/2))
        self.points.append(point)
        x, y = point
        e = self.extents
        e[:] = min(e[0],x), min(e[1],y), max(e[2],x), max(e[3],y)
        self._data = None

    @property
    def bounds(self):
        x, y, right, bottom = self.extents
        r = self.stroke.width/2
        return QRectF(x-r,y-r,right-x+2*r,bottom-y+2*r)

    def path(self):
        path = QPainterPath(self.prefix)
        if len(self.points) == 1:
            path.addEllipse(QPointF(*self.points[0]), self.stroke.width/2, self.stroke.width/2)
        else:
            path.lineTo(QPointF(*self.points[-1]))
        return path

    def paint_data(self):
        if self._data is None:
            path = self.path()
            ink = path if len(self.points) == 1 else rendering.stroked(path, self.stroke.width)
            remaining = ink
            clip = None
            if self.stroke.clip is not None:
                boundary = rendering.clip_path(self.stroke.clip)
                if not boundary.contains(self.bounds):
                    remaining = ink.intersected(boundary)
                    clip = boundary
            self._data = rendering.PaintData(path, ink, remaining, clip, None)
        return self._data

    def freeze(self):
        return replace(self.stroke, points=tuple(self.points))
