"""Paired raster-only timings separate image work from window/event-loop noise."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from dataclasses import replace
import json
from pathlib import Path
import statistics
from time import perf_counter
from unittest.mock import patch

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication
from mini_whiteboard import rendering
from mini_whiteboard.background import ScreenshotBackground
from mini_whiteboard.board import BoardWindow
from mini_whiteboard.scene import Record
from mini_whiteboard.transforms import Affine
from .screenshot_performance import screenshot


def main():
    app = QApplication.instance() or QApplication([])
    rows = []
    with patch('mini_whiteboard.windows.IS_WINDOWS',False):
        board = BoardWindow('Raster cache fixture')
        board.resize(1280,820)
        board.layout_children()
        canvas = board.canvas
        source = screenshot(3840,2160)
        source = replace(source,transform=Affine(a=canvas.width()/3840,d=canvas.width()/3840))
        record = Record.make(source)
        cache = ScreenshotBackground(source)
        cache.prepare(canvas.rect(),1,canvas.clip_spec,record)
        target = QImage(cache.image.size(),cache.image.format())
        target.fill(Qt.GlobalColor.white)
        clip = rendering.clip_path(canvas.clip_spec)
        for width,height in ((32,32),(160,80),(600,300)):
            samples = {'source':[],'cached':[]}
            for i in range(240):
                # Reverse order each iteration to keep load/warmup comparable.
                for mode in (('source','cached') if i%2 else ('cached','source')):
                    before = perf_counter()
                    painter = QPainter(target)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    painter.setClipRect(QRectF(20,40,width,height))
                    if mode=='source':
                        painter.setClipPath(clip,Qt.ClipOperation.IntersectClip)
                        rendering.paint_object(painter,source,record.paint)
                    else:
                        cache.paint(painter,None)
                    painter.end()
                    if i>=20:
                        samples[mode].append((perf_counter()-before)*1000)
            rows.append({'dirty_pixels':[width,height],'samples_per_path':220,
                         'source_median_ms':round(statistics.median(samples['source']),4),
                         'cached_median_ms':round(statistics.median(samples['cached']),4)})
        board.close()
    result = {'source_pixels':[3840,2160],'display_cache_pixels':[cache.image.width(),cache.image.height()],
              'dpr':1,'scope':'paired raster only, excludes event delivery/geometry/window composition','timings':rows}
    Path('verification/screenshot-raster-comparison.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
