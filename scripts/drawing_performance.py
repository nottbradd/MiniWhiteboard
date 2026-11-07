"""Controlled freehand workload. Synthetic Qt events, not hardware/display latency.

Run the same file with --source pointing at either checkout. Each invocation is
a fresh process; JSON is flushed after every workload, preserving partial runs.
"""
import argparse
import cProfile
import ctypes
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import time


def stats(values):
    values = sorted(values)
    return dict(n=len(values), mean_ms=statistics.mean(values) if values else 0,
                p50_ms=statistics.median(values) if values else 0,
                p95_ms=values[max(0, math.ceil(len(values)*.95)-1)] if values else 0,
                max_ms=max(values, default=0))


def memory():
    if sys.platform != 'win32':
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    class Counters(ctypes.Structure):
        _fields_ = [('cb', ctypes.c_ulong), ('faults', ctypes.c_ulong)] + [
            (key, ctypes.c_size_t) for key in ('peak', 'working', 'poolpeak', 'pool',
                                              'nonpeak', 'non', 'page', 'pagepeak')]
    value = Counters()
    value.cb = ctypes.sizeof(value)
    kernel = ctypes.WinDLL('kernel32')
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    psapi = ctypes.WinDLL('psapi')
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(value), value.cb)
    return value.working


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='.')
    parser.add_argument('--output', default='verification/drawing.json')
    parser.add_argument('--points', default='120,480,1920')
    parser.add_argument('--contexts', default='empty,populated,screenshot')
    parser.add_argument('--themes', default='White,Glass')
    parser.add_argument('--toolbar', action='store_true')
    parser.add_argument('--profile')
    parser.add_argument('--rapid',type=int,default=0,help='Additional short strokes and erase/undo/tool-switch cycles per row')
    args = parser.parse_args()
    sys.path.insert(0, str(Path(args.source).resolve()))
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from PySide6 import __version__ as qt_version
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QImage, QMouseEvent
    from PySide6.QtWidgets import QApplication
    from unittest.mock import patch
    from mini_whiteboard import APP_VERSION, rendering
    from mini_whiteboard.board import BoardWindow
    from mini_whiteboard.canvas import Canvas
    from mini_whiteboard.document import Document, Shape
    from mini_whiteboard.snapping import SnapPreferences
    from mini_whiteboard.images import from_image
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    report = dict(scope='offscreen synthetic Qt mouse, unpaced backlog; paint each 4 samples (240 Hz input / 60 Hz paint equivalent, not real-time injection)',
                  version=APP_VERSION, python=sys.version, qt=qt_version, os=platform.platform(),
                  cpu=platform.processor(), cores=os.cpu_count(), dpr=app.primaryScreen().devicePixelRatio(),
                  board_size=[960,640], toolbar=args.toolbar, rapid_strokes=args.rapid, real_pen='NOT RUN', rows=[])
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    def save():
        output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    class Measured(Canvas):
        def paintEvent(self, event):
            start = time.perf_counter()
            super().paintEvent(event)
            paints.append((time.perf_counter()-start)*1000)
    profiler = cProfile.Profile()
    if args.profile:
        profiler.enable()
    with patch('mini_whiteboard.windows.IS_WINDOWS', False):
        for theme in args.themes.split(','):
            for context in args.contexts.split(','):
                for count in map(int, args.points.split(',')):
                    paints = []
                    prefs = SnapPreferences()
                    prefs.set_theme(theme)
                    board = BoardWindow('Synthetic drawing fixture', prefs)
                    old = board.canvas
                    old.hide()
                    old.deleteLater()
                    canvas = Measured(board, prefs)
                    board.install_canvas(canvas)
                    board.resize(960,640)
                    board.show()
                    board.activateWindow()
                    canvas.setFocus()
                    if context == 'populated':
                        canvas.document.commit(tuple(Shape('Rectangle',(20+i%20*40,30+i//20*40),
                                                           (42+i%20*40,52+i//20*40)) for i in range(200)), 'Fixture')
                    if context == 'screenshot':
                        im = QImage(1920,1080,QImage.Format.Format_RGB32)
                        im.fill(Qt.GlobalColor.lightGray)
                        obj = from_image(im, locked=True)
                        canvas.document.commit((obj,), 'Fixture')
                        canvas.set_screenshot_background(obj)
                    manager = None
                    if args.toolbar:
                        from mini_whiteboard.floating_tools import FloatingTools
                        manager = FloatingTools(app, prefs)
                        manager.add_board(board)
                        prefs.set_floating_tools(True)
                        manager.activate(board)
                    app.processEvents()
                    # Offscreen ignores native nonactivation. Establish canvas
                    # focus after the palette's queued show, before timed input.
                    app.processEvents()
                    board.activateWindow()
                    canvas.setFocus()
                    app.processEvents()
                    paints.clear()
                    def event(kind, p):
                        ev = QMouseEvent(kind, QPointF(*p), QPointF(*p),
                                         Qt.MouseButton.NoButton if kind == QMouseEvent.Type.MouseMove else Qt.MouseButton.LeftButton,
                                         Qt.MouseButton.NoButton if kind == QMouseEvent.Type.MouseButtonRelease else Qt.MouseButton.LeftButton,
                                         Qt.KeyboardModifier.NoModifier)
                        QApplication.sendEvent(canvas, ev)
                    start_cpu, start_wall, start_memory = time.process_time(), time.perf_counter(), memory()
                    event(QMouseEvent.Type.MouseButtonPress,(40,250))
                    samples, stalls = [], []
                    for i in range(1,count+1):
                        p = (40+(i*.8)%820, 260+160*math.sin(i*.032))
                        start = time.perf_counter()
                        event(QMouseEvent.Type.MouseMove,p)
                        samples.append((time.perf_counter()-start)*1000)
                        if i%4 == 0:
                            app.processEvents()
                            stalls.append((time.perf_counter()-start)*1000)
                    start = time.perf_counter()
                    event(QMouseEvent.Type.MouseButtonRelease,p)
                    app.processEvents()
                    commit = (time.perf_counter()-start)*1000
                    rapid_samples = []
                    committed_points = len(canvas.document.objects[-1].points)
                    for j in range(args.rapid):
                        start = time.perf_counter()
                        canvas.set_tool('Draw')
                        event(QMouseEvent.Type.MouseButtonPress,(60,480))
                        for k in range(1,13):
                            event(QMouseEvent.Type.MouseMove,(60+k*6,480+10*math.sin(k)))
                        event(QMouseEvent.Type.MouseButtonRelease,(138,480))
                        canvas.set_tool('Eraser')
                        canvas.eraser_mode = 'stroke'
                        event(QMouseEvent.Type.MouseButtonPress,(100,480))
                        event(QMouseEvent.Type.MouseButtonRelease,(100,480))
                        canvas.undo_redo()
                        canvas.undo_redo(True)
                        if manager and j%5 == 0:
                            manager.open_options('Draw')
                            manager.close_options(refocus=True)
                        app.processEvents()
                        rapid_samples.append((time.perf_counter()-start)*1000)
                    report['rows'].append(dict(theme=theme,context=context,points=count,input=stats(samples),
                        paint=stats(paints), dispatch_and_drain=stats(stalls),commit_ms=commit,
                        cpu_seconds=time.process_time()-start_cpu,wall_seconds=time.perf_counter()-start_wall,
                        working_set_start=start_memory,working_set_end=memory(),
                        committed_points=committed_points, rapid_cycle=stats(rapid_samples),
                        path_cache=rendering._object_path.cache_info()._asdict()))
                    save()
                    print(json.dumps(report['rows'][-1]),flush=True)
                    if manager:
                        manager.close()
                    board.close()
                    board.deleteLater()
                    app.processEvents()
    if args.profile:
        profiler.disable()
        profiler.dump_stats(args.profile)
    save()


if __name__ == '__main__':
    main()
