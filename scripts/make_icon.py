"""Render vector masters and a PNG-backed multi-resolution Windows ICO."""
import os
from pathlib import Path
import struct
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication
from mini_whiteboard.branding import APP_SIZES, TRAY_SIZES


def generate(project=None):
    app = QApplication.instance() or QApplication([])
    project = Path(project or Path(__file__).resolve().parents[1])
    assets = project/'assets';output = assets/'branding';output.mkdir(exist_ok=True)
    master = (assets/'mini_whiteboard.svg').read_bytes()
    tray = (assets/'tray_symbol.svg').read_bytes()
    def render(source, side, target):
        renderer = QSvgRenderer(QByteArray(source))
        if not renderer.isValid():raise ValueError('Invalid vector master')
        image = QImage(side,side,QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter,QRectF(0,0,side,side));painter.end()
        if not image.save(str(target),'PNG'):raise OSError('Cannot save icon raster')
    for side in APP_SIZES:render(master,side,output/f'app-{side}.png')
    for color,ink in (('dark',b'#172b4d'),('light',b'#f4f8ff')):
        for side in TRAY_SIZES:
            render(tray.replace(b'#172b4d',ink),side,output/f'tray-{color}-{side}.png')
    sides=[side for side in APP_SIZES if side<=256]
    chunks=[(output/f'app-{side}.png').read_bytes() for side in sides]
    offset=6+16*len(sides);entries=[]
    for side,data in zip(sides,chunks):
        entries.append(struct.pack('<BBBBHHII',side%256,side%256,0,0,1,32,len(data),offset))
        offset+=len(data)
    (assets/'mini_whiteboard.ico').write_bytes(struct.pack('<HHH',0,1,len(sides))+b''.join(entries)+b''.join(chunks))
    # Installer-only artwork stays outside the runtime branding directory.
    installer=assets/'installer';installer.mkdir(exist_ok=True)
    renderer=QSvgRenderer(QByteArray(master))
    for filename,width,height,rectangle in (
            ('wizard.png',492,942,QRectF(36,280,420,420)),
            ('wizard-small.png',232,232,QRectF(10,10,212,212))):
        image=QImage(width,height,QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.white)
        painter=QPainter(image);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if height>width:
            gradient=QLinearGradient(0,0,width,height)
            gradient.setColorAt(0,QColor('#edf8fc'));gradient.setColorAt(1,QColor('#dbeaf7'))
            painter.fillRect(image.rect(),gradient)
        renderer.render(painter,rectangle);painter.end()
        if not image.save(str(installer/filename),'PNG'):raise OSError('Cannot save installer artwork')
    return output


if __name__=='__main__':print(generate())
