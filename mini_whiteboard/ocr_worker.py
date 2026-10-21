"""Bounded, offline OCR in a disposable process; no application windows or logs."""
import json
from pathlib import Path
import sys

MAX_PIXELS = 16_000_000
MAX_PNG = 32 * 1024 * 1024
MAX_REQUEST = 48 * 1024 * 1024
MAX_TEXT = 100_000
TIMEOUT = 20


def validate_image(obj):
    from .document import ImageObject
    if not isinstance(obj, ImageObject):
        raise ValueError('Choose one image to extract text.')
    width, height = obj.pixel_size
    if width <= 0 or height <= 0 or width * height > MAX_PIXELS or len(obj.png) > MAX_PNG:
        raise ValueError('OCR accepts images up to 16 million pixels and 32 MiB of PNG data.')
    if len(obj.erasures) > 4096:
        raise ValueError('This image has too many eraser samples for OCR.')


def prepare_image(obj):
    """Rectify display transforms, preserve original resolution and local masks."""
    from dataclasses import replace
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QImageReader, QPainter
    from .rendering import paint_object, remaining_local
    from .transforms import IDENTITY
    validate_image(obj)
    # Probe dimensions before decoding, including corrupt/mislabelled payloads.
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    buffer = QBuffer()
    buffer.setData(QByteArray(obj.png))
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buffer, b'png')
    size = reader.size()
    if (size.width(), size.height()) != obj.pixel_size:
        raise ValueError('The source image dimensions are invalid.')
    image = QImage(*obj.pixel_size, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    painter.translate(-obj.position[0], -obj.position[1])
    paint_object(painter, replace(obj, transform=IDENTITY))
    painter.end()
    gray = image.convertToFormat(QImage.Format.Format_Grayscale8)
    # Dark screenshot backgrounds need light text inverted for the engine.
    # Sample a bounded grid; source pixels and history are never changed.
    samples = [gray.pixelColor(x, y).red()
               for y in range(0, gray.height(), max(1, gray.height() // 32))
               for x in range(0, gray.width(), max(1, gray.width() // 32))]
    if sorted(samples)[len(samples)//2] < 100:
        gray.invertPixels()
    # Unpainted areas (transparency, masks and creation clip) always remain
    # white after inversion rather than becoming spurious dark text regions.
    from PySide6.QtGui import QPainterPath
    from PySide6.QtCore import QRectF
    outside = QPainterPath()
    outside.addRect(QRectF(*obj.position, *obj.pixel_size))
    outside = outside.subtracted(remaining_local(obj))
    painter = QPainter(gray)
    painter.translate(-obj.position[0], -obj.position[1])
    painter.fillPath(outside, Qt.GlobalColor.white)
    painter.end()
    return gray


def recognize(obj, language='en'):
    if language != 'en':
        raise ValueError('Only English OCR is supported in this release.')
    image = prepare_image(obj)
    if sys.platform == 'darwin':
        from .platform.macos.ocr import recognize_image
    elif sys.platform == 'win32':
        from .platform.windows.ocr import recognize_image
    else:
        raise RuntimeError('OCR is available on Windows and macOS.')
    text = recognize_image(image)
    if len(text) > MAX_TEXT:
        raise ValueError('OCR output exceeds 100,000 characters; use a smaller image.')
    return text.strip()


def worker_main(arguments):
    """Files avoid windowed-executable standard-stream assumptions; caller cleans up."""
    if len(arguments) != 2:
        return 2
    request, response = map(Path, arguments)
    import os
    if os.environ.get('MINIWHITEBOARD_OCR_DENY_NETWORK') == '1':
        def offline(event, args):
            if event in ('socket.connect', 'socket.connect_ex', 'socket.getaddrinfo', 'socket.bind'):
                raise PermissionError('Network access is disabled for this OCR diagnostic.')
        sys.addaudithook(offline)
    try:
        if request.stat().st_size > MAX_REQUEST:
            raise ValueError('The OCR request is too large.')
        data = json.loads(request.read_text(encoding='utf-8'))
        from .clipboard import decode
        objects, _, _ = decode(data['image'].encode('utf-8'))
        if len(objects) != 1:
            raise ValueError('Choose one image to extract text.')
        text = recognize(objects[0], data.get('language', 'en'))
        result = {'text': text, 'error': ''}
    except (ValueError, KeyError) as error:
        result = {'text': '', 'error': str(error)[:250]}
    except (ImportError, OSError, RuntimeError) as error:
        import os
        if os.environ.get("MINI_WHITEBOARD_OCR_DIAGNOSTIC"):
            response.write_text(json.dumps({"text": "", "error": type(error).__name__ + ": " + str(error)}), encoding="utf-8")
            return 1
        result = {'text': '', 'error': 'The offline OCR engine could not read this image. Check the app resources.'}
    # No source, recognized text, or engine output is written to routine logs.
    from . import APP_VERSION
    result['version'] = APP_VERSION
    response.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    return 0
