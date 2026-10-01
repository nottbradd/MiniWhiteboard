"""One display-resolution raster for an unchanged, locked capture image.

This is a view cache, never document/clipboard/history data. The original image
object remains authoritative. Pixel coordinates are multiplied by DPR once.
"""
import math
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from . import rendering


class ScreenshotBackground:
    def __init__(self, source):
        self.source = source
        self.image = None
        self.key = None
        self.builds = 0

    def matches(self, obj):
        return obj.locked and (obj is self.source or obj == self.source)

    def prepare(self, viewport, dpr, clip_spec, record):
        key = (viewport.width(), viewport.height(), round(dpr,6), clip_spec)
        if key == self.key:
            return
        image = QImage(max(1,math.ceil(viewport.width()*dpr)),
                       max(1,math.ceil(viewport.height()*dpr)),
                       QImage.Format.Format_ARGB32_Premultiplied)
        image.setDevicePixelRatio(dpr)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        if clip_spec is not None:
            painter.setClipPath(rendering.clip_path(clip_spec))
        rendering.paint_object(painter,record.obj,record.paint)
        painter.end()
        self.image, self.key = image, key
        self.builds += 1

    def paint(self, painter, region):
        # Qt's event clip limits this one-to-one raster blit to the dirty pixels.
        # No source transform, smooth scaling, clipping path or conversion here.
        painter.drawImage(QPointF(0,0),self.image)
