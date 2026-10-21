"""Cached raster assets from the vector masters; no SVG rendering at startup."""
from functools import lru_cache
from pathlib import Path
import sys
from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon

APP_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256, 512, 1024)
TRAY_SIZES = (16, 20, 24, 32, 40, 48, 64)


def asset_root():
    return Path(sys._MEIPASS)/'branding' if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]/'assets/branding'


@lru_cache(maxsize=1)
def app_icon(size=64):
    icon = QIcon()
    for side in APP_SIZES:
        icon.addFile(str(asset_root()/f'app-{side}.png'), QSize(side, side))
    return icon


@lru_cache(maxsize=3)
def tray_icon(*, light_background=True, template=False):
    icon = QIcon()
    color = 'dark' if light_background or template else 'light'
    for side in TRAY_SIZES:
        icon.addFile(str(asset_root()/f'tray-{color}-{side}.png'), QSize(side, side))
    icon.setIsMask(template)
    return icon
