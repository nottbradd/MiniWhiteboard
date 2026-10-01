"""Editable JSON MIME plus a normal image on the Windows clipboard; no pickle."""
import base64
from dataclasses import asdict
import json
import math
from uuid import uuid4

from PySide6.QtCore import QMimeData, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter

from .document import Stroke, Shape, Text, ImageObject
from .geometry import Rect
from .transforms import Affine, Erasure, PaintClip
from .settings import CLIPBOARD_MIME, MAX_CLIPBOARD_BYTES, SHAPES
from . import rendering


def encode(objects, board_id):
    items = []
    for obj in objects:
        item = asdict(obj)
        item['type'] = type(obj).__name__
        if isinstance(obj, ImageObject):
            item['png'] = base64.b64encode(obj.png).decode('ascii')
        items.append(item)
    payload = json.dumps({'schema': 1, 'source': board_id, 'token': uuid4().hex, 'objects': items},
                         separators=(',', ':'), allow_nan=False).encode('utf-8')
    if len(payload) > MAX_CLIPBOARD_BYTES:
        raise ValueError("This selection is too large for the editable clipboard format.")
    return payload


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > 1e8:
        raise ValueError("Invalid clipboard geometry.")
    return value


def pair(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("Invalid clipboard point.")
    return tuple(number(v) for v in value)


def affine(value):
    if set(value) != {'a','b','c','d','tx','ty'}:
        raise ValueError("Invalid clipboard transform.")
    result = Affine(**{k:number(v) for k,v in value.items()})
    result.inverse()
    return result


def clip(value):
    if value is None:
        return None
    def rect(item):
        result = Rect(**{k:number(v) for k,v in item.items()})
        if result.width < 0 or result.height < 0:
            raise ValueError("Invalid clip size.")
        return result
    if len(value['exclusions']) > 100 or number(value['radius']) < 0:
        raise ValueError("Invalid clip.")
    return PaintClip(rect(value['viewport']), rect(value['paper']), value['radius'],
                     tuple(rect(r) for r in value['exclusions']))


def decode(payload):
    if len(payload) > MAX_CLIPBOARD_BYTES:
        raise ValueError("Clipboard data is too large.")
    try:
        data = json.loads(bytes(payload))
        if data['schema'] != 1 or not isinstance(data['source'], str) or not isinstance(data['token'], str):
            raise ValueError("Unsupported clipboard format.")
        if not isinstance(data['objects'], list) or not 0 < len(data['objects']) <= 10000:
            raise ValueError("Invalid clipboard object count.")
        objects = []
        for raw in data['objects']:
            item = dict(raw)
            kind = item.pop('type')
            if type(item['locked']) is not bool or not isinstance(item['id'], str):
                raise ValueError("Invalid object metadata.")
            item['transform'] = affine(item['transform'])
            item['clip'] = clip(item['clip'])
            if len(item['erasures']) > 100000:
                raise ValueError("Too many erasure records.")
            masks = []
            for mask in item['erasures']:
                radius = number(mask['radius'])
                if radius <= 0:
                    raise ValueError("Invalid brush radius.")
                masks.append(Erasure(pair(mask['start']), pair(mask['end']), radius,
                                     affine(mask['to_local']), clip(mask['clip'])))
            item['erasures'] = tuple(masks)
            if kind != 'ImageObject':
                if not isinstance(item['color'], str) or not QColor(item['color']).isValid():
                    raise ValueError("Invalid colour.")
                item['color'] = QColor(item['color']).name()
            if kind == 'Stroke':
                if not 0 < len(item['points']) <= 500000:
                    raise ValueError("Invalid stroke size.")
                item['points'] = tuple(pair(p) for p in item['points'])
                if not 0 < number(item['width']) <= 10000:
                    raise ValueError("Invalid stroke width.")
                obj = Stroke(**item)
            elif kind == 'Shape':
                item['a'], item['b'] = pair(item['a']), pair(item['b'])
                if item['kind'] not in SHAPES.values() or not 0 < number(item['width']) <= 10000:
                    raise ValueError("Invalid shape.")
                obj = Shape(**item)
            elif kind == 'Text':
                item['position'] = pair(item['position'])
                if not isinstance(item['text'], str) or not 0 < number(item['size']) <= 10000:
                    raise ValueError("Invalid text.")
                obj = Text(**item)
            elif kind == 'ImageObject':
                from .images import decoded
                item['position'] = pair(item['position'])
                item['pixel_size'] = pair(item['pixel_size'])
                item['png'] = base64.b64decode(item['png'], validate=True)
                image = decoded(item['png'])
                if item['pixel_size'] != (image.width(), image.height()):
                    raise ValueError("Image dimensions do not match.")
                obj = ImageObject(**item)
            else:
                raise ValueError("Unknown clipboard object type.")
            objects.append(obj)
        return tuple(objects), data['source'], data['token']
    except (KeyError, TypeError, OverflowError, RecursionError) as error:
        raise ValueError("Invalid Mini Whiteboard clipboard data.") from error


def rendered_image(objects):
    bounds = QRectF()
    for obj in objects:
        bounds = bounds.united(rendering.bounds(obj))
    if bounds.isEmpty():
        return QImage()
    bounds = bounds.adjusted(-2,-2,2,2)
    scale = min(1, 4096/max(bounds.width(), bounds.height()))
    image = QImage(max(1, math.ceil(bounds.width()*scale)), max(1, math.ceil(bounds.height()*scale)),
                   QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing |
                           QPainter.RenderHint.SmoothPixmapTransform)
    painter.scale(scale, scale)
    painter.translate(-bounds.left(), -bounds.top())
    for obj in objects:
        rendering.paint_object(painter, obj)
    painter.end()
    return image


def mime_data(objects, board_id):
    result = QMimeData()
    result.setData(CLIPBOARD_MIME, encode(objects, board_id))
    result.setImageData(rendered_image(objects))
    return result
