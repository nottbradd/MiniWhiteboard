"""Photograph a real BoardWindow over two positions of a separately painted line.

Run only on a test desktop. The camera belongs to this review script. The app
does not inspect, store or request permission to capture a backdrop for a theme.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

from PIL import Image, ImageGrab
from PySide6 import __version__ as qt_binding
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from mini_whiteboard.board import BoardWindow
from mini_whiteboard.geometry import Rect
from mini_whiteboard.platform import get_platform
from mini_whiteboard.snapping import SnapPreferences


WIDTH, HEIGHT = 640, 406
LEFT, TOP, BOARD_W, BOARD_H = 76, 78, 464, 244
RIGHT, BOTTOM = LEFT + BOARD_W, TOP + BOARD_H


def line_y(x, offset=0):
    return BOTTOM - 27 + .54 * (x - RIGHT) + offset


class Background(QWidget):
    phase = None
    palette_name = 'light'

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        base, line = ('#e7ecec', '#2e4755')
        if self.palette_name == 'dark':
            base, line = '#263543', '#dce9db'
        painter.fillRect(self.rect(), QColor(base))
        if self.palette_name == 'busy':
            for x in range(-150, WIDTH + 50, 34):
                painter.setPen(QPen(QColor('#a4babc'), 12))
                painter.drawLine(x, 0, x + 150, HEIGHT)
            for y in range(0, HEIGHT, 45):
                painter.setPen(QPen(QColor('#ced9cf'), 7))
                painter.drawLine(0, y, WIDTH, y - 30)
        if self.phase is not None:
            painter.setPen(QPen(QColor(line), 5))
            painter.drawLine(QPointF(0, line_y(0, self.phase)),
                             QPointF(WIDTH, line_y(WIDTH, self.phase)))


def photograph(background, path):
    QTest.qWait(450)
    origin = background.mapToGlobal(QPoint())
    if sys.platform == 'darwin':
        subprocess.run(['/usr/sbin/screencapture', '-x',
                        f'-R{origin.x()},{origin.y()},{WIDTH},{HEIGHT}', str(path)],
                       check=True, timeout=15)
    else:
        ratio = background.devicePixelRatioF()
        box = tuple(round(v * ratio) for v in (origin.x(), origin.y(),
                                                origin.x() + WIDTH, origin.y() + HEIGHT))
        ImageGrab.grab(bbox=box, include_layered_windows=True, all_screens=True).save(path)
    with Image.open(path) as image:
        if image.width < WIDTH or max(image.convert('L').getextrema()) == 0:
            raise RuntimeError('OS capture returned an empty or undersized image')


def measure(folder, name, palette, phase):
    """Subtract the identical no-line frame to exclude fixed borders and shadows."""
    import numpy as np
    def gray(suffix):
        with Image.open(folder / f'{palette}-{name}-{suffix}.png') as image:
            return np.asarray(image.convert('L').resize((WIDTH, HEIGHT),
                                                        Image.Resampling.BOX), dtype=float)
    delta = np.abs(gray(str(phase)) - gray('bare'))
    columns = []
    for x in range(LEFT+50, RIGHT+50):
        y = round(line_y(x, phase))
        ys = np.arange(max(0, y - 38), min(HEIGHT, y + 39))
        signal = delta[ys, x]
        strength = float(signal.max())
        weights = np.maximum(signal - max(1.5, strength * .04), 0)
        if strength < 3 or weights.sum() < 9:
            continue
        centre = float(np.average(ys, weights=weights))
        columns.append((x, centre-line_y(x, phase), strength,
                        float(np.sqrt(np.average((ys-centre)**2, weights=weights)))))
    def region(lo, hi):
        data = [row for row in columns if lo <= row[0] < hi]
        if not data:
            return {'columns': 0}
        arr = np.array(data)
        return dict(columns=len(data), offset=round(float(np.median(arr[:, 1])), 2),
                    max_abs=round(float(max(abs(arr[:, 1]))), 2),
                    signal=round(float(np.median(arr[:, 2])), 2),
                    width_sd=round(float(np.median(arr[:, 3])), 2))
    return dict(centre=region(RIGHT-175, RIGHT-65), rim=region(RIGHT-18, RIGHT-2),
                exterior=region(RIGHT+16, RIGHT+46),
                rim_samples=[(x, round(d, 2)) for x,d,_,_ in columns if RIGHT-20 <= x < RIGHT])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    folder = args.output
    folder.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    screen = app.primaryScreen()
    services = get_platform()
    preferences = SnapPreferences()
    bg = Background(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
    work = screen.availableGeometry()
    bg.setGeometry(work.x()+(work.width()-WIDTH)//2, work.y()+(work.height()-HEIGHT)//2,
                   WIDTH, HEIGHT)
    bg.show()
    bg.raise_()
    bg.activateWindow()
    QTest.qWait(400)
    origin = bg.mapToGlobal(QPoint())
    factor = screen.devicePixelRatio() if sys.platform == 'win32' else 1
    bounds = Rect(*[round(v*factor) for v in (origin.x()+LEFT, origin.y()+TOP, BOARD_W, BOARD_H)])
    board = BoardWindow('Mini Whiteboard', preferences, services)
    report = dict(system=platform.platform(), release=platform.mac_ver() if sys.platform == 'darwin'
                  else platform.win32_ver(), qt=qt_binding, backend=app.platformName(),
                  ratio=screen.devicePixelRatio(), display=[work.width(), work.height()],
                  runner=os.getenv('ImageVersion'), samples={})
    try:
        modes = ['Uncovered', 'White', 'Frosted Glass', 'Liquid Glass']
        if sys.platform == 'win32':
            modes.append('Desktop acrylic')
        for theme in modes:
            name = theme.lower().split()[0]
            if theme != 'Uncovered':
                if theme == 'Desktop acrylic':
                    from .probe_acrylic import AcrylicHost
                    board.desktop.release_appearance(board)
                    board._backdrop = AcrylicHost(board)
                    board._backdrop.sync(board)
                else:
                    preferences.set_theme(theme)
                if not board.isVisible():
                    board.place(bounds)
                QTest.qWait(500)
            native = board.native_glass
            print(f'{theme}, adapter returned {native!r}', flush=True)
            record = report['samples'][theme] = dict(native=native, policy=vars(board.display_policy))
            for palette in ('light', 'dark', 'busy'):
                bg.palette_name = palette
                for phase in (None, 0, 12):
                    bg.phase = phase
                    bg.update()
                    suffix = 'bare' if phase is None else str(phase)
                    photograph(bg, folder / f'{palette}-{name}-{suffix}.png')
                record[palette] = [measure(folder, name, palette, p) for p in (0, 12)]
            print(json.dumps(record['light'][0]), flush=True)
    finally:
        (folder/'optics.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        board.close()
        bg.close()
        app.processEvents()


if __name__ == '__main__':
    main()
