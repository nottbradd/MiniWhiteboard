"""Small cached screenshot samples for controls and click-through feedback.

Only the already-rendered screenshot cache is sampled, never the desktop.
The sample is bounded to the local surface and rebuilt only when it changes.
"""
import math
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen


class ChromeSample:
    def __init__(self):
        self.key = self.image = None
        self.dark = False
        self.builds = 0

    def prepare(self, widget, rect, radius):
        board = widget.window()
        canvas = getattr(board, 'canvas', None)
        cache = getattr(canvas, 'background_cache', None)
        if not getattr(board, 'screenshot_surface', False) or cache is None or cache.image is None:
            self.key = self.image = None
            self.dark = False
            return
        current = canvas.document.get(cache.source.id)
        if current is None or not cache.matches(current):
            self.key = self.image = None
            self.dark = True
            return
        # QWidget.mapTo requires an ancestor; controls and canvas are siblings.
        # Use their common board, avoiding global origins and mixed-DPI rounding.
        origin = widget.mapTo(board, QPoint(0, 0))-canvas.pos()
        local = rect.translated(origin)
        dpr = widget.devicePixelRatioF()
        key = (cache.image.cacheKey(), local.x(), local.y(), local.width(), local.height(), dpr, radius)
        if key == self.key:
            return
        # Downsample just this small area to create local frost; each surface
        # retains its finished raster across idle, hover and pressed repaints.
        source = cache.image.copy(math.floor(local.x()*dpr), math.floor(local.y()*dpr),
                                  max(1, math.ceil(local.width()*dpr)),
                                  max(1, math.ceil(local.height()*dpr)))
        source.setDevicePixelRatio(1)
        tiny = source.scaled(max(1, round(rect.width()/6)), max(1, round(rect.height()/6)),
                             Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        average = tiny.scaled(1, 1, Qt.AspectRatioMode.IgnoreAspectRatio,
                              Qt.TransformationMode.SmoothTransformation).pixelColor(0, 0)
        self.dark = (.2126*average.redF()+.7152*average.greenF()+.0722*average.blueF()) < .52
        image = tiny.scaled(source.size(), Qt.AspectRatioMode.IgnoreAspectRatio,
                            Qt.TransformationMode.SmoothTransformation).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        image.setDevicePixelRatio(dpr)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, rect.width(), rect.height()), radius, radius)
        from .alpha_clip import apply_mask, mask_image
        apply_mask(image, mask_image(image.size(), dpr, path))
        self.key, self.image = key, image
        self.builds += 1


def paint_chrome(painter, widget, rect, sample, *, radius=6, hover=False, pressed=False, destructive=False):
    board = widget.window()
    policy = getattr(board, 'display_policy', None)
    opaque = policy is None or policy.high_contrast or not policy.transparency
    screenshot = getattr(board, 'screenshot_surface', False)
    if not opaque:
        sample.prepare(widget, rect, radius)
    dark = screenshot and (sample.dark or sample.image is None)
    if opaque:
        fill, border, ink = QColor('white'), QColor('#252932'), QColor('#151821')
        if hover or pressed:
            fill, border, ink = QColor('#252932'), QColor('white'), QColor('white')
    elif dark:
        fill = QColor(28, 32, 40, 205 if pressed else 182 if hover else 155)
        border, ink = QColor(255, 255, 255, 42), QColor('#f4f5f7')
    else:
        fill = QColor(244, 247, 251, 220 if pressed else 198 if hover else 176)
        border, ink = QColor(75, 89, 108, 45), QColor('#303746')
    if destructive and (hover or pressed):
        fill = QColor((164 if pressed else 148) if dark else (218 if pressed else 229),
                      (36 if pressed else 47) if dark else (44 if pressed else 70), 61 if dark else 85,
                      235 if opaque else 195 if pressed else 155)
        ink = QColor('white') if dark or opaque else QColor('#8c1929')
        border = QColor(240, 99, 114, 105)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    if not opaque and sample.image is not None:
        painter.drawImage(rect.topLeft(), sample.image)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(fill)
    painter.drawRoundedRect(rect, radius, radius)
    pixel = 1/widget.devicePixelRatioF()
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(border, pixel))
    painter.drawRoundedRect(rect.adjusted(pixel/2, pixel/2, -pixel/2, -pixel/2), radius, radius)
    return ink
