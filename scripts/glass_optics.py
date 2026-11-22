"""Photograph a real BoardWindow over two positions of a separately painted line.

Run only on a test desktop. The camera belongs to this review script. The app
does not inspect, store or request permission to capture a backdrop for a theme.
"""
import argparse
import json
from multiprocessing import get_context
import os
from pathlib import Path
import platform
import subprocess
import sys

from PIL import Image
from PySide6 import __version__ as qt_binding
from PySide6.QtCore import QPoint, QPointF, Qt, QTimer
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
    grazing = False

    def __init__(self, parent, flags):
        # The board is always on top. Keep the test scene in that same band,
        # underneath it, when the hosted runner opens normal console windows.
        if sys.platform == 'win32':
            flags |= Qt.WindowType.WindowStaysOnTopHint
        super().__init__(parent, flags)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        base, line = ('#e7ecec', '#2e4755')
        if self.palette_name == 'dark':
            base, line = '#263543', '#dce9db'
        if self.palette_name == 'neutral':
            base, line = '#dfdfdf', '#202020'
        if self.palette_name == 'reel':
            base, line = '#121212', '#f5f5f5'
        painter.fillRect(self.rect(), QColor(base))
        if self.palette_name == 'busy':
            for x in range(-150, self.width() + 50, 34):
                painter.setPen(QPen(QColor('#a4babc'), 12))
                painter.drawLine(x, 0, x + 150, self.height())
            for y in range(0, self.height(), 45):
                painter.setPen(QPen(QColor('#ced9cf'), 7))
                painter.drawLine(0, y, self.width(), y - 30)
        if self.phase is not None:
            painter.setPen(QPen(QColor(line), 5))
            if self.grazing:
                # A near-vertical line meets the lower-right curve at a shallow
                # angle. It reveals displacement along the normal to that rim.
                def x_at(y):
                    return RIGHT - 7 + (y-BOTTOM+28)*.19 + self.phase
                painter.drawLine(QPointF(x_at(0),0), QPointF(x_at(self.height()), self.height()))
            else:
                offsets = (-92, 0, 92) if self.palette_name == 'reel' else (0,)
                for offset in offsets:
                    painter.drawLine(QPointF(0, line_y(0, self.phase + offset)),
                                     QPointF(self.width(), line_y(self.width(), self.phase + offset)))


def photograph(background, path, area=None, *, settle_ms=450):
    QTest.qWait(settle_ms)
    origin = background.mapToGlobal(QPoint()) if area is None else area.topLeft()
    width, height = (WIDTH, HEIGHT) if area is None else (area.width(), area.height())
    if sys.platform == 'darwin':
        subprocess.run(['/usr/sbin/screencapture', '-x',
                        f'-R{origin.x()},{origin.y()},{width},{height}', str(path)],
                       check=True, timeout=15)
    else:
        from mini_whiteboard.platform.windows import native
        ratio = background.devicePixelRatioF()
        left, top, right, bottom = (round(v * ratio) for v in
                                   (origin.x(), origin.y(), origin.x()+width, origin.y()+height))
        if not native.capture_rect(Rect(left,top,right-left,bottom-top)).save(str(path)):
            raise OSError(f'Could not save {path.name}')
    with Image.open(path) as image:
        if image.width < width or max(image.convert('L').getextrema()) == 0:
            raise RuntimeError('OS capture returned an empty or undersized image')


def backdrop_process(connection):
    """A separate test application owns all moving pixels behind the real board."""
    app = QApplication([])
    bg = Background(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
    work = app.primaryScreen().availableGeometry()
    bg.setGeometry(work.x()+(work.width()-WIDTH)//2, work.y()+(work.height()-HEIGHT)//2,
                   WIDTH, HEIGHT)
    bg.show()
    bg.raise_()
    bg.activateWindow()
    QTest.qWait(350)
    pos = bg.mapToGlobal(QPoint())
    connection.send((pos.x(),pos.y(),bg.devicePixelRatioF(),os.getpid()))
    def receive():
        if connection.poll():
            message = connection.recv()
            if message is None:
                app.quit()
            else:
                bg.palette_name,bg.phase,bg.grazing = message
                bg.repaint()
                connection.send(True)
    timer = QTimer()
    timer.timeout.connect(receive)
    timer.start(20)
    app.exec()
    connection.close()


class RemoteBackground:
    palette_name, phase, grazing = 'light', None, False

    def __init__(self):
        context = get_context('spawn')
        self.channel, other = context.Pipe()
        self.process = context.Process(target=backdrop_process,args=(other,),daemon=True)
        self.process.start()
        other.close()
        if not self.channel.poll(20):
            raise RuntimeError('Backdrop test process did not start')
        x,y,self.ratio,self.pid = self.channel.recv()
        self.origin = QPoint(x,y)

    def mapToGlobal(self, point):
        return self.origin + point

    def devicePixelRatioF(self):
        return self.ratio

    def update(self):
        self.channel.send((self.palette_name,self.phase,self.grazing))
        if not self.channel.poll(8) or not self.channel.recv():
            raise RuntimeError('Moving backdrop did not acknowledge the requested phase')

    def close(self):
        try:
            self.channel.send(None)
            self.process.join(5)
        finally:
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(3)
            self.channel.close()


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


def channel_separation(folder, name, phase, palette='neutral'):
    """Compare channel centroids of the moving neutral line after subtracting the static rim."""
    import numpy as np
    def rgb(suffix):
        with Image.open(folder/f'{palette}-{name}-{suffix}.png') as im:
            return np.array(im.convert('RGB').resize((WIDTH,HEIGHT),Image.Resampling.BOX), dtype=float)
    change = np.abs(rgb(phase)-rgb('bare'))
    def separation(xs):
        offsets = []
        for x in xs:
            y = round(line_y(x, phase))
            ys = np.arange(y-25,y+26)
            signal = change[ys,x,:]
            if min(signal.max(axis=0)) < 5:
                continue
            weights = np.maximum(0,signal-.04*signal.max(axis=0))
            means = np.average(ys, weights=weights[:,0])-np.average(ys, weights=weights[:,2])
            offsets.append(abs(float(means)))
        return round(max(offsets),3) if offsets else None
    return dict(centre_max=separation(range(RIGHT-100, RIGHT-50)),
                rim_max=separation(range(RIGHT-16, RIGHT)), exterior_max=separation(range(RIGHT+10, RIGHT+32)))


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
    work = screen.availableGeometry()
    bg = RemoteBackground()
    origin = bg.mapToGlobal(QPoint())
    factor = screen.devicePixelRatio() if sys.platform == 'win32' else 1
    bounds = Rect(*[round(v*factor) for v in (origin.x()+LEFT, origin.y()+TOP, BOARD_W, BOARD_H)])
    board = BoardWindow('Mini Whiteboard', preferences, services)
    report = dict(system=platform.platform(), release=platform.mac_ver() if sys.platform == 'darwin'
                  else platform.win32_ver(), qt=qt_binding, backend=app.platformName(),
                  ratio=screen.devicePixelRatio(), display=[work.width(), work.height()],
                  runner=os.getenv('ImageVersion'), board_pid=os.getpid(), backdrop_pid=bg.pid, samples={})
    try:
        modes = ['Uncovered', 'White', 'Frosted Glass', 'Liquid Glass']
        for theme in modes:
            name = theme.lower().split()[0]
            if theme != 'Uncovered':
                preferences.set_theme(theme)
                if not board.isVisible():
                    board.place(bounds)
                QTest.qWait(500)
            native = board.native_glass
            print(f'{theme}, adapter returned {native!r}', flush=True)
            record = report['samples'][theme] = dict(native=native, policy=vars(board.display_policy),
                                                     channel_rim=getattr(board, '_glass_rim', None) is not None)
            for palette in ('light', 'dark', 'busy', 'neutral'):
                bg.palette_name = palette
                for phase in (None, 0, 12):
                    bg.phase = phase
                    bg.update()
                    suffix = 'bare' if phase is None else str(phase)
                    photograph(bg, folder / f'{palette}-{name}-{suffix}.png')
                record[palette] = [measure(folder, name, palette, p) for p in (0, 12)]
            bg.grazing, bg.palette_name = True, 'neutral'
            for phase in (None, -4, 0, 4):
                bg.phase = phase
                bg.update()
                suffix = 'bare' if phase is None else str(phase)
                photograph(bg, folder/f'rim-{name}-{suffix}.png')
            bg.grazing = False
            record['neutral_red_blue_displacement'] = [channel_separation(folder,name,k) for k in (0,12)]
            print(json.dumps(record['light'][0]), flush=True)
        raw = report['samples']['Uncovered']['light']
        assert all(row['centre']['columns'] == 110 and row['exterior']['signal'] > 50 for row in raw)
        assert all(row['centre']['columns'] == 0 for row in report['samples']['White']['light'])
        for theme in ('Frosted Glass', 'Liquid Glass'):
            record = report['samples'][theme]
            for phase in record['light']:
                assert phase['exterior']['columns'] == 30
                if not record['native']:
                    assert phase['centre']['columns'] == 0
                elif record['native'] == 'Liquid Glass':
                    assert phase['centre']['signal'] > 15
                    assert max(abs(d-raw[0]['centre']['offset']) for _,d in phase['rim_samples']) > 1.5
                else:
                    assert phase['centre'].get('width_sd',0) > raw[0]['centre']['width_sd']*1.5
    finally:
        (folder/'optics.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        board.close()
        bg.close()
        app.processEvents()


if __name__ == '__main__':
    main()
