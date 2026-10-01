"""Additional Version 1.1 image, snapping and clipboard timing fixtures."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
import math
from pathlib import Path
import statistics
from time import perf_counter
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter
from PySide6.QtWidgets import QApplication
from mini_whiteboard import clipboard, images
from mini_whiteboard.board import BoardWindow
from mini_whiteboard.document import Document
from .performance_check import MeasuredCanvas, fixture


def main():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    image = QImage(3840,2160,QImage.Format.Format_RGB32)
    painter = QPainter(image)
    gradient = QLinearGradient(0,0,3840,2160)
    gradient.setColorAt(0,QColor('#275a86'))
    gradient.setColorAt(1,QColor('#eef4fb'))
    painter.fillRect(image.rect(),gradient)
    painter.setPen(QColor('#30434f'))
    for y in range(40,2160,45):
        painter.drawText(40,y,'Mini Whiteboard image benchmark · Windows screenshot / annotation ' * 7)
    painter.end()
    before = perf_counter()
    source = images.from_image(image)
    encoding_ms = (perf_counter()-before)*1000
    rows = []
    with patch('mini_whiteboard.windows.IS_WINDOWS',False):
        board = BoardWindow('Image benchmark')
        board.canvas.hide()
        board.canvas.deleteLater()
        canvas = MeasuredCanvas(board)
        board.install_canvas(canvas)
        board.resize(1280,820)
        board.show()
        board.activateWindow()
        canvas.setFocus()
        app.processEvents()
        fitted = canvas.image_at(source,(620,380))
        objects = (fitted,*fixture(100))
        for operation in ('move','resize','rotate'):
            canvas.document = Document()
            canvas.document.commit(objects,'Fixture')
            canvas.tool = 'Select'
            canvas.set_selection({fitted.id})
            canvas.update()
            app.processEvents()
            frame = canvas.frame
            start = frame.handle(4) if operation == 'resize' else frame.rotation_handle() if operation == 'rotate' else frame.center
            canvas.start = canvas.last_sample = start
            canvas.start_gesture(operation)
            canvas.resize_handle = 4 if operation == 'resize' else 8
            samples = []
            canvas.paint_samples.clear()
            with patch.object(images,'decoded',side_effect=AssertionError('Unexpected image decode during transform')):
                for i in range(1,25):
                    t = i/24
                    if operation == 'rotate':
                        dx,dy = start[0]-frame.center[0],start[1]-frame.center[1]
                        angle = t*.3
                        point = (frame.center[0]+dx*math.cos(angle)-dy*math.sin(angle),
                                 frame.center[1]+dx*math.sin(angle)+dy*math.cos(angle))
                    else:
                        point = (start[0]+45*t,start[1]+25*t)
                    before = perf_counter()
                    canvas.update_gesture(point)
                    app.processEvents()
                    samples.append((perf_counter()-before)*1000)
            rows.append({'operation':operation,'frames':24,'median_event_ms':round(statistics.median(samples),3),
                         'p95_event_ms':round(sorted(samples)[22],3),'decodes_during_transform':0,
                         'mean_canvas_paint_fraction':round(statistics.mean(s[1] for s in canvas.paint_samples),4)})
            canvas.cancel_interaction()
        copy_rows = []
        for label, content in [('4K image plus 100 annotations',objects),('500 mixed vector objects',fixture(500))]:
            samples = []
            for _ in range(3):
                before = perf_counter()
                mime = clipboard.mime_data(content,'benchmark')
                samples.append((perf_counter()-before)*1000)
                mime.deleteLater()
            copy_rows.append({'fixture':label,'median_copy_ms':round(statistics.median(samples),3),
                              'first_copy_ms':round(samples[0],3)})
        board.close()
    result = {'platform':'offscreen','smart_guides':True,'source_pixels':[3840,2160],
              'source_png_bytes':len(source.png),'initial_png_encode_ms':round(encoding_ms,3),
              'image_with_100_annotations':rows,'clipboard':copy_rows}
    Path('verification/performance-images-v11.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
