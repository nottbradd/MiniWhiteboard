"""Painting and hit geometry derived from immutable document objects."""
from functools import lru_cache
from collections import OrderedDict
from dataclasses import dataclass, replace
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QAbstractTextDocumentLayout, QColor, QFont, QPainterPath,
                          QPainterPathStroker, QPalette, QPen, QTextDocument, QTextOption,
                          QTransform, QPolygonF)

from .document import Shape, Stroke, Text, ImageObject
from .geometry import normalized
from .settings import (INK, SELECTION, HANDLE_DIAMETER, HANDLE_HIT_RADIUS,
                       ROTATION_HANDLE_DISTANCE, CONTAINMENT_TOLERANCE, TEXT_DEFAULT_WIDTH)
from .transforms import SelectionFrame, IDENTITY


def point(p):
    return QPointF(*p)


def qt_transform(matrix):
    return QTransform(matrix.a, matrix.b, matrix.c, matrix.d, matrix.tx, matrix.ty)


@lru_cache(maxsize=256)
def clip_path(clip):
    path = QPainterPath()
    path.addRoundedRect(QRectF(clip.paper.x, clip.paper.y, clip.paper.width, clip.paper.height), clip.radius, clip.radius)
    viewport = QPainterPath()
    viewport.addRect(QRectF(clip.viewport.x, clip.viewport.y, clip.viewport.width, clip.viewport.height))
    path = path.intersected(viewport)
    for rect in clip.exclusions:
        hole = QPainterPath()
        hole.addRect(QRectF(rect.x, rect.y, rect.width, rect.height))
        path = path.subtracted(hole)
    return path


@lru_cache(maxsize=256)
def text_document(text, size, layout_width=TEXT_DEFAULT_WIDTH):
    document = QTextDocument()
    document.setDocumentMargin(2)
    from .shortcuts import ui_font_family
    font = QFont(ui_font_family())
    font.setPointSizeF(size)
    document.setDefaultFont(font)
    option = QTextOption()
    option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
    document.setDefaultTextOption(option)
    document.setPlainText(text)
    document.setTextWidth(layout_width)
    return document


def object_path(obj):
    return _object_path(replace(obj, transform=IDENTITY, erasures=()))


@lru_cache(maxsize=512)
def _object_path(obj):
    path = QPainterPath()
    if isinstance(obj, Stroke):
        if not obj.points:
            return path
        path.moveTo(point(obj.points[0]))
        if len(obj.points) == 1:
            path.addEllipse(point(obj.points[0]), obj.width/2, obj.width/2)
        elif len(obj.points) == 2:
            path.lineTo(point(obj.points[-1]))
        else:
            # Midpoint quadratic interpolation smooths samples without a lagging
            # filter, retaining the actual start and finish of each stroke.
            for i in range(1, len(obj.points)-1):
                p, q = obj.points[i], obj.points[i+1]
                path.quadTo(point(p), QPointF((p[0]+q[0])/2, (p[1]+q[1])/2))
            path.lineTo(point(obj.points[-1]))
    elif isinstance(obj, Shape):
        bounds = normalized(obj.a, obj.b)
        r = QRectF(bounds.x, bounds.y, bounds.width, bounds.height)
        if obj.kind == "Rectangle":
            path.addRect(r)
        elif obj.kind == "Rounded rectangle":
            radius = min(12, r.width()/4, r.height()/4)
            path.addRoundedRect(r, radius, radius)
        elif obj.kind == "Ellipse":
            path.addEllipse(r)
        elif obj.kind in ("Line", "Arrow"):
            path.moveTo(point(obj.a))
            path.lineTo(point(obj.b))
        elif obj.kind == "Triangle":
            path.moveTo(r.center().x(), r.top())
            path.lineTo(r.right(), r.bottom())
            path.lineTo(r.left(), r.bottom())
            path.closeSubpath()
        elif obj.kind == "Diamond":
            path.moveTo(r.center().x(), r.top())
            path.lineTo(r.right(), r.center().y())
            path.lineTo(r.center().x(), r.bottom())
            path.lineTo(r.left(), r.center().y())
            path.closeSubpath()
    elif isinstance(obj, ImageObject):
        path.addRect(QRectF(*obj.position, *obj.pixel_size))
    else:
        path.addRect(text_bounds(obj))
    return path


def arrowhead(obj):
    path = QPainterPath()
    ax, ay = obj.a
    bx, by = obj.b
    length = math.hypot(bx-ax, by-ay)
    if length < .01:
        return path
    ux, uy = (bx-ax)/length, (by-ay)/length
    size = min(length, max(10, obj.width*4))
    path.moveTo(bx, by)
    path.lineTo(bx-ux*size-uy*size*.45, by-uy*size+ux*size*.45)
    path.lineTo(bx-ux*size+uy*size*.45, by-uy*size-ux*size*.45)
    path.closeSubpath()
    return path


def text_bounds(obj):
    size = text_document(obj.text, obj.size, obj.layout_width).size()
    return QRectF(*obj.position, max(20, size.width()), max(20, size.height()))


def stroked(path, width):
    stroker = QPainterPathStroker()
    stroker.setWidth(width)
    stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
    stroker.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return stroker.createStroke(path)


@lru_cache(maxsize=256)
def text_ink(text, size, layout_width=TEXT_DEFAULT_WIDTH):
    document = text_document(text, size, layout_width)
    document.documentLayout().documentSize()
    result = QPainterPath()
    result.setFillRule(Qt.FillRule.WindingFill)
    block = document.begin()
    while block.isValid():
        layout = block.layout()
        origin = layout.position()
        # A QTextDocument-backed layout may expose an empty layout.text(); its
        # default glyphRuns range is then empty even though the block is laid out.
        for run in layout.glyphRuns(0, block.length()-1):
            font = run.rawFont()
            for glyph, pos in zip(run.glyphIndexes(), run.positions()):
                outline = font.pathForGlyph(glyph)
                result.addPath(QTransform.fromTranslate(origin.x()+pos.x(), origin.y()+pos.y()).map(outline))
        block = block.next()
    # CoreText outlines can contain coincident cubic segments. Combining a
    # long wrapped run with an erasure can stall Qt's curve boolean clipper.
    # Flatten only the hit/erasure geometry at 4x precision, retaining contour
    # winding and holes. QTextDocument still paints the original shaped text.
    # Qt's polygon conversion is bounded and avoids cubic/cubic intersections.
    polygons = QPainterPath()
    polygons.setFillRule(Qt.FillRule.WindingFill)
    scale = QTransform.fromScale(4, 4)
    unscale = QTransform.fromScale(.25, .25)
    for contour in result.toSubpathPolygons(scale):
        polygons.addPolygon(unscale.map(contour))
        polygons.closeSubpath()
    return polygons


def local_ink(obj):
    return _local_ink(replace(obj, transform=IDENTITY, erasures=()))


@lru_cache(maxsize=512)
def _local_ink(obj):
    if isinstance(obj, Text):
        ink = QTransform.fromTranslate(*obj.position).map(text_ink(obj.text, obj.size, obj.layout_width))
    elif isinstance(obj, ImageObject):
        ink = object_path(obj)
    else:
        path = object_path(obj)
        ink = path if isinstance(obj, Stroke) and len(obj.points) == 1 else stroked(path, obj.width)
        if isinstance(obj, Shape) and obj.kind == "Arrow":
            ink = ink.united(arrowhead(obj))
    if obj.clip is not None:
        ink = ink.intersected(clip_path(obj.clip))
    return ink


def swept_brush(a, b, diameter):
    path = QPainterPath(point(a))
    path.lineTo(point(b))
    swept = stroked(path, diameter) if a != b else QPainterPath()
    end = QPainterPath()
    end.addEllipse(point(b), diameter/2, diameter/2)
    return swept.united(end)


_MASK_CACHE = OrderedDict()


def mask_path(erasures):
    if erasures in _MASK_CACHE:
        _MASK_CACHE.move_to_end(erasures)
        return _MASK_CACHE[erasures]
    # Most calls extend one gesture by one sample. Reuse its previous union;
    # rebuilding every earlier capsule at every move makes long drags quadratic.
    previous = _MASK_CACHE.get(erasures[:-1]) if erasures else None
    result = QPainterPath(previous) if previous is not None else QPainterPath()
    pending = erasures[-1:] if previous is not None else erasures
    for mask in pending:
        swept = swept_brush(mask.start, mask.end, mask.radius*2)
        if mask.clip is not None:
            swept = swept.intersected(clip_path(mask.clip))
        result = result.united(qt_transform(mask.to_local).map(swept))
    _MASK_CACHE[erasures] = result
    if len(_MASK_CACHE) > 128:
        _MASK_CACHE.popitem(last=False)
    return result


def remaining_local(obj):
    # A gesture changes the affine transform on every sample, while the local
    # ink and mask stay identical. Exclude that transform from the cache key.
    return _remaining_local(replace(obj, transform=IDENTITY))


@lru_cache(maxsize=1024)
def _remaining_local(obj):
    ink = local_ink(obj)
    return ink.subtracted(mask_path(obj.erasures)) if obj.erasures else ink


@lru_cache(maxsize=512)
def visible_ink(obj):
    return qt_transform(obj.transform).map(remaining_local(obj))


@lru_cache(maxsize=2048)
def bounds(obj):
    """Full surviving painted bounds, including pen widths, never viewport-clipped."""
    return visible_ink(obj).boundingRect()


def interaction_bounds(obj):
    result = bounds(obj)
    if result.isEmpty():
        return result
    if isinstance(obj, Text) or isinstance(obj, Shape) and obj.kind not in ("Line", "Arrow"):
        result = result.united(qt_transform(obj.transform).mapRect(object_path(obj).boundingRect()))
    return result.adjusted(-5, -5, 5, 5)


def hit_path(obj, tolerance=5, interior=True):
    ink = visible_ink(obj)
    if ink.isEmpty():
        return ink
    result = ink.united(stroked(ink, tolerance*2)) if tolerance else QPainterPath(ink)
    transform = qt_transform(obj.transform)
    if interior:
        if isinstance(obj, Text):
            result = result.united(transform.map(object_path(obj)))
        elif isinstance(obj, Shape) and obj.kind not in ("Line", "Arrow"):
            result = result.united(transform.map(object_path(obj)))
    # Subtract AFTER inflating tolerance: erased holes must stay unselectable.
    if obj.clip is not None:
        result = result.intersected(transform.map(clip_path(obj.clip)))
    if obj.erasures:
        result = result.subtracted(transform.map(mask_path(obj.erasures)))
    return result


def hit_test(objects, position):
    p = point(position)
    return next((obj for obj in reversed(objects) if interaction_bounds(obj).contains(p)
                 and hit_path(obj).contains(p)), None)


def swept_hits(obj, a, b, diameter=16):
    return swept_brush(a, b, diameter).intersects(visible_ink(obj))


def fully_contained(obj, rectangle):
    r = bounds(obj)
    if r.isEmpty():
        return False
    epsilon = CONTAINMENT_TOLERANCE
    return rectangle.adjusted(-epsilon, -epsilon, epsilon, epsilon).contains(r)


@lru_cache(maxsize=1024)
def _paint_clip(obj):
    clip = QPainterPath()
    clip.addRect(local_ink(obj).boundingRect().adjusted(-2, -2, 2, 2))
    if obj.clip is not None:
        clip = clip.intersected(clip_path(obj.clip))
    return clip.subtracted(mask_path(obj.erasures)) if obj.erasures else clip


@dataclass(frozen=True)
class PaintData:
    path: QPainterPath
    ink: QPainterPath
    remaining: QPainterPath
    clip: QPainterPath | None
    document: object
    image: object = None


def paint_data(obj):
    return _paint_data(replace(obj, transform=IDENTITY))


@lru_cache(maxsize=1024)
def _paint_data(obj):
    from .images import decoded
    return PaintData(object_path(obj), local_ink(replace(obj, clip=None)), remaining_local(obj),
                     _paint_clip(obj) if obj.erasures or obj.clip is not None else None,
                     text_document(obj.text, obj.size, obj.layout_width) if isinstance(obj, Text) else None,
                     decoded(obj.png) if isinstance(obj, ImageObject) else None)


def paint_object(painter, obj, data=None):
    data = paint_data(obj) if data is None else data
    painter.save()
    painter.setTransform(qt_transform(obj.transform), True)
    if data.clip is not None:
        painter.setClipPath(data.clip, Qt.ClipOperation.IntersectClip)
    if isinstance(obj, ImageObject):
        painter.setRenderHint(painter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(QRectF(*obj.position, *obj.pixel_size), data.image)
        painter.restore()
        return
    if isinstance(obj, Text):
        painter.translate(*obj.position)
        # An OS dark theme may give QTextDocument a white default text color.
        # The paper is always white, so supply an explicit text palette.
        context = QAbstractTextDocumentLayout.PaintContext()
        context.palette.setColor(QPalette.ColorRole.Text, QColor(obj.color))
        data.document.documentLayout().draw(painter, context)
        painter.restore()
        return
    # The round-cap/join stroke outline (including arrowhead) is already cached
    # for geometry. Fill it directly rather than asking Qt to stroke every path
    # again on every affine preview frame.
    painter.fillPath(data.ink, QColor(obj.color))
    painter.restore()


def selection_frame(objects):
    rectangles = [rect for obj in objects if not (rect := bounds(obj)).isEmpty()]
    if not rectangles:
        return None
    r = rectangles[0]
    for other in rectangles[1:]:
        r = r.united(other)
    return SelectionFrame((r.center().x(), r.center().y()), max(1, r.width()), max(1, r.height()))


def handles(frame, dpr=1):
    return [point(frame.handle(i)) for i in range(8)] + [point(frame.rotation_handle(ROTATION_HANDLE_DISTANCE/dpr))]


def handle_at(frame, position, dpr=1):
    if frame is None:
        return None
    candidates = [(math.dist((p.x(), p.y()), position), i) for i, p in enumerate(handles(frame, dpr))]
    distance, index = min(candidates)
    return index if distance <= HANDLE_HIT_RADIUS else None


def endpoint_at(obj, position):
    if isinstance(obj, Shape) and obj.kind in ("Line", "Arrow"):
        for i, p in enumerate((obj.a, obj.b)):
            if math.dist(obj.transform.map(p), position) <= HANDLE_HIT_RADIUS:
                return i
    return None


def paint_selection(painter, frame, dpr=1, show_handles=True):
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(SELECTION), 1/dpr))
    painter.drawPolygon(QPolygonF([point(frame.handle(i)) for i in (0, 2, 4, 6)]))
    if show_handles:
        positions = handles(frame, dpr)
        painter.drawLine(positions[1], positions[8])
        painter.setBrush(QColor("white"))
        radius = HANDLE_DIAMETER/2/dpr
        for p in positions:
            painter.drawEllipse(p, radius, radius)
