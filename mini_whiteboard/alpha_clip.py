"""Antialiased view clipping, without binary widget/window regions.

Interior canvas painting stays on its direct path. Only boundary artwork, the
one screenshot display cache, and the temporary editor need alpha coverage.
Document geometry, source pixels and clipboard rendering remain authoritative.
"""
import math
from dataclasses import replace
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QGraphicsEffect


def mask_image(size, dpr, path, origin=QPointF()):
    mask = QImage(size, QImage.Format.Format_Alpha8)
    mask.setDevicePixelRatio(dpr)
    mask.fill(0)
    painter = QPainter(mask)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.translate(-origin.x(), -origin.y())
    painter.fillPath(path, Qt.GlobalColor.white)
    painter.end()
    return mask


def apply_mask(image, mask):
    painter = QPainter(image)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    painter.drawImage(QPointF(), mask)
    painter.end()


def paint_boundary(painter, obj, data, path, dirty, dpr):
    from . import rendering
    from .document import Shape, Stroke
    if isinstance(obj, (Shape, Stroke)):
        # Filling the intersected vector outline gives real alpha coverage;
        # QPainter's raster clip alone would quantise its curved boundary.
        ink = rendering.qt_transform(obj.transform).map(data.remaining)
        painter.fillPath(ink.intersected(path), QColor(obj.color))
        return
    if data.clip is not None:
        path = path.intersected(rendering.qt_transform(obj.transform).map(data.clip))
    rect = QRectF(dirty.toAlignedRect())
    if rect.isEmpty():
        return
    image = QImage(max(1, math.ceil(rect.width()*dpr)), max(1, math.ceil(rect.height()*dpr)),
                   QImage.Format.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(dpr)
    image.fill(Qt.GlobalColor.transparent)
    target = QPainter(image)
    target.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
    target.translate(-rect.left(), -rect.top())
    rendering.paint_object(target, obj, replace(data, clip=None))
    target.end()
    apply_mask(image, mask_image(image.size(), dpr, path, rect.topLeft()))
    painter.drawImage(rect.topLeft(), image)


class EditorClip(QGraphicsEffect):
    """Clip a real proxy editor's pixels; focus, input and popups stay with Qt."""
    def __init__(self, canvas, parent):
        super().__init__(parent)
        self.canvas = canvas
        self.key = self.mask = None

    def draw(self, painter):
        from . import rendering
        if self.canvas.clip_spec is None:
            self.drawSource(painter)
            return
        offset = QPoint()
        source = self.sourcePixmap(Qt.CoordinateSystem.LogicalCoordinates, offset,
                                   QGraphicsEffect.PixmapPadMode.NoPad)
        image = source.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        if image.isNull():
            return
        key = (image.width(), image.height(), image.devicePixelRatio(),
               offset.x(), offset.y(), self.canvas.clip_spec)
        if key != self.key:
            self.mask = mask_image(image.size(), image.devicePixelRatio(),
                                   rendering.clip_path(self.canvas.clip_spec), QPointF(offset))
            self.key = key
        apply_mask(image, self.mask)
        painter.drawImage(QPointF(offset), image)
