"""Immutable PNG sources, decoded once and transformed only at display time."""
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QImage, QImageReader

from .document import ImageObject
from .settings import MAX_IMAGE_PIXELS


def check_size(width, height):
    if width <= 0 or height <= 0 or width*height > MAX_IMAGE_PIXELS:
        raise ValueError("Choose an image containing at most 64 million pixels.")


def from_image(image, position=(0, 0), **kwargs):
    if image.isNull():
        raise ValueError("The clipboard does not contain a readable image.")
    check_size(image.width(), image.height())
    image = QImage(image)
    image.setDevicePixelRatio(1)
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise ValueError("The image could not be converted to PNG.")
    return ImageObject(position, bytes(data), (image.width(), image.height()), **kwargs)


def from_file(filename):
    if Path(filename).suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
        raise ValueError("Drop PNG, JPG, JPEG or WEBP image files.")
    reader = QImageReader(str(filename))
    reader.setAutoTransform(True)
    check_size(reader.size().width(), reader.size().height())
    image = reader.read()
    if image.isNull():
        raise ValueError(reader.errorString())
    return from_image(image)


def read_bytes(encoded, format_name=b""):
    data = QByteArray(encoded)
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buffer, format_name)
    reader.setAutoTransform(True)
    check_size(reader.size().width(), reader.size().height())
    image = reader.read()
    if image.isNull():
        raise ValueError("Invalid image data.")
    image.setDevicePixelRatio(1)
    return image


@lru_cache(maxsize=16)
def decoded(png):
    return read_bytes(png, b"png")
