"""Compare identical annotation work on blank and locked-screenshot canvases."""
import os
import sys
os.environ['QT_QPA_PLATFORM'] = ('cocoa' if sys.platform == 'darwin' else 'windows') if '--native' in sys.argv else 'offscreen'
from contextlib import ExitStack
import argparse
import cProfile
from dataclasses import replace
import json
import math
from pathlib import Path
import pstats
import statistics
from time import perf_counter
from unittest.mock import patch

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from mini_whiteboard import images, rendering, windows
from mini_whiteboard.platform import get_platform
from mini_whiteboard.platform.windows import create_platform as test_platform
from mini_whiteboard.geometry import Rect
from mini_whiteboard.board import BoardWindow
from mini_whiteboard.document import Document, ImageObject, Shape, Stroke, Text
from mini_whiteboard.transforms import Affine
from .performance_check import MeasuredCanvas


def annotations():
    strokes = tuple(Stroke(tuple((40+(i%5)*215+j*2,55+(i//5)*95+12*math.sin(j/3))
                                 for j in range(70)),4) for i in range(20))
    shapes = tuple(Shape('Rounded rectangle',(45+(i%5)*215,440+(i//5)*65),
                        (150+(i%5)*215,475+(i//5)*65),3) for i in range(20))
    texts = tuple(Text((75+(i%5)*215,705+(i//5)*30),'Annotation',12) for i in range(10))
    return (*strokes,*shapes,*texts)


def screenshot(width,height):
    image = QImage(width,height,QImage.Format.Format_RGB32)
    painter = QPainter(image)
    gradient = QLinearGradient(0,0,width,height)
    gradient.setColorAt(0,QColor('#d5e1e9'))
    gradient.setColorAt(1,QColor('#fafcff'))
    painter.fillRect(image.rect(),gradient)
    painter.setPen(QColor('#446477'))
    for y in range(30,height,45):
        painter.drawText(20,y,'Screenshot comparison: stable background, editable annotations. '*12)
    painter.end()
    return images.from_image(image,locked=True)


def run(frames=40, repeats=3, native=False):
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    rows = []
    with ExitStack() as stack:
        if not native:
            stack.enter_context(patch('mini_whiteboard.windows.IS_WINDOWS',False))
            stack.enter_context(patch('mini_whiteboard.platform._platform', test_platform()))
        board = BoardWindow('Screenshot performance')
        board.canvas.hide()
        board.canvas.deleteLater()
        canvas = MeasuredCanvas(board)
        board.install_canvas(canvas)
        board.resize(1280,820)
        board.show()
        if native:
            desktop = board.desktop
            monitor = desktop.displays()[0]
            scale = desktop.placement_scale(monitor.rect)
            board.place(Rect(monitor.rect.x+30,monitor.rect.y+40,1264*scale,804*scale))
        board.activateWindow()
        canvas.setFocus()
        app.processEvents()
        objects = annotations()
        for size in (None,(1920,1080),(2560,1440),(3840,2160)):
            background = None
            if size:
                source = screenshot(*size)
                factor = min(canvas.width()/size[0],canvas.height()/size[1])
                background = replace(source,transform=Affine(a=factor,d=factor))
            for operation in ('draw','circular_erase','whole_stroke_erase','marquee','move_10','resize_10','rotate_10'):
                times,paints,commits = [],[],[]
                counters = {'image_paint_calls':0,'image_decode_calls':0,'image_geometry_builds':0}
                original_paint = rendering.paint_object
                original_decode = images.decoded
                original_data = rendering.paint_data
                def paint(painter,obj,*args,**kwargs):
                    if isinstance(obj,ImageObject): counters['image_paint_calls'] += 1
                    return original_paint(painter,obj,*args,**kwargs)
                def decode(*args,**kwargs):
                    counters['image_decode_calls'] += 1
                    return original_decode(*args,**kwargs)
                def data(obj,*args,**kwargs):
                    if isinstance(obj,ImageObject): counters['image_geometry_builds'] += 1
                    return original_data(obj,*args,**kwargs)
                for repeat in range(repeats):
                    canvas.cancel_interaction()
                    canvas.document = Document()
                    canvas.document.commit((background,*objects) if background else objects,'Fixture')
                    canvas.set_selection(set())
                    if hasattr(canvas,'set_screenshot_background'):
                        canvas.set_screenshot_background(background)
                    canvas.tool = 'Draw' if operation=='draw' else 'Eraser' if 'erase' in operation else 'Select'
                    canvas.eraser_mode = 'stroke' if operation=='whole_stroke_erase' else 'circular'
                    frame = None
                    if operation.endswith('_10'):
                        canvas.set_selection(o.id for o in objects[:10])
                        frame = canvas.frame
                        kind = operation.split('_')[0]
                        start = frame.handle(4) if kind=='resize' else frame.rotation_handle() if kind=='rotate' else frame.center
                    else:
                        kind = 'erase' if 'erase' in operation else operation
                        start = (25,55) if 'erase' in operation else (30,370) if kind=='draw' else (16,16)
                    canvas.update()
                    app.processEvents()
                    canvas.start = canvas.last_sample = start
                    canvas.start_gesture(kind)
                    canvas.resize_handle = 4 if kind=='resize' else 8
                    canvas.marquee_add = False
                    if kind=='draw':
                        canvas.points = [start]
                        canvas.preview = Stroke((start,),4,clip=canvas.clip_spec)
                    canvas.paint_samples.clear()
                    with patch.object(rendering,'paint_object',paint),patch.object(images,'decoded',decode),patch.object(rendering,'paint_data',data):
                        for i in range(1,frames+1):
                            t = i/frames
                            if kind=='rotate':
                                dx,dy = start[0]-frame.center[0],start[1]-frame.center[1]
                                pos = (frame.center[0]+dx*math.cos(t*.25)-dy*math.sin(t*.25),
                                       frame.center[1]+dx*math.sin(t*.25)+dy*math.cos(t*.25))
                            elif kind=='draw':
                                pos = (30+1070*t,370+25*math.sin(t*math.pi*5))
                            elif kind=='marquee': pos = (30+1100*t,30+700*t)
                            elif kind=='erase': pos = (25+1130*t,55)
                            else: pos = (start[0]+45*t,start[1]+25*t)
                            before = perf_counter()
                            canvas.update_gesture(pos)
                            app.processEvents()
                            times.append((perf_counter()-before)*1000)
                        before = perf_counter()
                        QTest.mouseRelease(canvas,Qt.MouseButton.LeftButton,pos=QPoint(round(pos[0]),round(pos[1])))
                        app.processEvents()
                        commits.append((perf_counter()-before)*1000)
                    paints.extend(canvas.paint_samples)
                    if background:
                        assert all(edit.before[0] is background and edit.after[0] is background
                                   for edit in canvas.document.history[1:])
                cache = getattr(canvas,'background_cache',None)
                rows.append({'source_pixels':size,'operation':operation,'samples':len(times),
                             'median_event_ms':round(statistics.median(times),3),
                             'p95_event_ms':round(sorted(times)[math.ceil(len(times)*.95)-1],3),
                             'median_commit_ms':round(statistics.median(commits),3),
                             'mean_canvas_paint_fraction':round(statistics.mean(p[1] for p in paints),5) if paints else 0,
                             'mean_paint_ms':round(statistics.mean(p[0] for p in paints),3) if paints else 0,
                             **counters,
                             'cache_builds':getattr(cache,'builds',None),
                             'cache_pixels':[cache.image.width(),cache.image.height()] if cache and cache.image is not None else None})
        board.close()
        board.deleteLater()
        app.processEvents()
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    parser.add_argument('--profile')
    parser.add_argument('--frames',type=int,default=40)
    parser.add_argument('--repeats',type=int,default=3)
    parser.add_argument('--native',action='store_true')
    args = parser.parse_args()
    if args.native:
        get_platform().runtime.prepare()
    rows = run(args.frames,args.repeats,args.native)
    Path(args.output).write_text(json.dumps({'annotations':{'strokes':20,'shapes':20,'text':10},
                                           'canvas_outer_size':[1280,820],'platform':os.environ['QT_QPA_PLATFORM'],'timings':rows},indent=2),encoding='utf-8')
    if args.profile:
        profiler = cProfile.Profile()
        profiler.runcall(run,24,1,args.native)
        with Path(args.profile).open('w',encoding='utf-8') as stream:
            pstats.Stats(profiler,stream=stream).sort_stats('cumulative').print_stats(55)
    print(json.dumps({'results':args.output,'blank':rows[:7],'4K':rows[-7:]},indent=2))


if __name__=='__main__':
    main()
