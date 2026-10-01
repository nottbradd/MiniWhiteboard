"""Repeatable GUI-thread workload; explicit opt-in, no production timing/logging.

Uses Qt's offscreen backend to compare input processing and raster painting, not
display FPS. Captures actual paint-event dirty areas, not forced full renders.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from mini_whiteboard.board import BoardWindow
from mini_whiteboard.canvas import Canvas
from mini_whiteboard.document import Document, Shape, Stroke, Text
from mini_whiteboard.transforms import Erasure


class MeasuredCanvas(Canvas):
    def __init__(self, parent):
        self.paint_samples = []
        super().__init__(parent)

    def paintEvent(self, event):
        start = perf_counter()
        super().paintEvent(event)
        area = sum(r.width()*r.height() for r in event.region())
        self.paint_samples.append(((perf_counter()-start)*1000, area/(self.width()*self.height())))


def fixture(count):
    objects = []
    for i in range(count):
        x, y = 20+(i % 20)*60, 25+(i//20)*28
        if i % 3 == 0:
            points = tuple((x+j*.35, y+10+7*math.sin(j*.15)) for j in range(120))
            obj = Stroke(points, 3)
        elif i % 3 == 1:
            obj = Shape("Rounded rectangle", (x, y), (x+40, y+22), 2)
        else:
            obj = Text((x, y), "Note", 10)
        if i % 4 == 0:
            obj = replace(obj, erasures=(Erasure((x+20, y-3), (x+20, y+25), 3),))
        objects.append(obj)
    return tuple(objects)


def run(frames):
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    rows = []
    with patch("mini_whiteboard.windows.IS_WINDOWS", False):
        board = BoardWindow("Performance fixture")
        old = board.canvas
        old.hide()
        old.deleteLater()
        canvas = MeasuredCanvas(board)
        board.install_canvas(canvas)
        board.resize(1280, 820)
        board.show()
        board.activateWindow()
        canvas.setFocus()
        app.processEvents()
        for count in (10, 100, 500):
            objects = fixture(count)
            for operation in ("circular_erase", "whole_stroke_erase", "marquee", "move_one",
                              "move_many", "resize", "rotate"):
                canvas.cancel_interaction()
                canvas.document = Document()
                canvas.document.commit(objects, "Fixture")
                canvas.set_selection(set())
                canvas.tool = "Eraser" if "erase" in operation else "Select"
                canvas.eraser_mode = "stroke" if operation == "whole_stroke_erase" else "circular"
                canvas.eraser_key = 2
                if operation in ("move_one", "move_many", "resize", "rotate"):
                    selected = objects[:1] if operation == "move_one" else objects[:min(count, 100)]
                    canvas.set_selection(o.id for o in selected)
                    frame = canvas.frame
                    start = frame.handle(4) if operation == "resize" else frame.rotation_handle() if operation == "rotate" else frame.center
                    kind = "move" if operation.startswith("move") else operation
                else:
                    start = (5, 35) if "erase" in operation else (3, 3)
                    kind = "erase" if "erase" in operation else "marquee"
                canvas.update()
                app.processEvents()
                canvas.start = canvas.last_sample = start
                canvas.start_gesture(kind)
                canvas.resize_handle = 4 if operation == "resize" else 8
                canvas.marquee_add = False
                canvas.paint_samples.clear()
                samples = []
                for i in range(1, frames+1):
                    t = i/frames
                    if operation == "rotate":
                        dx, dy = start[0]-frame.center[0], start[1]-frame.center[1]
                        angle = t*.3
                        pos = (frame.center[0]+dx*math.cos(angle)-dy*math.sin(angle),
                               frame.center[1]+dx*math.sin(angle)+dy*math.cos(angle))
                    elif operation == "marquee":
                        pos = (10+1100*t, 10+600*t)
                    elif "erase" in operation:
                        pos = (5+1150*t, 35)
                    else:
                        pos = (start[0]+t*45, start[1]+t*25)
                    before = perf_counter()
                    canvas.update_gesture(pos)
                    app.processEvents()
                    samples.append((perf_counter()-before)*1000)
                before = perf_counter()
                QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(round(pos[0]), round(pos[1])))
                app.processEvents()
                commit_ms = (perf_counter()-before)*1000
                paints = canvas.paint_samples
                rows.append({"objects": count, "operation": operation, "frames": frames,
                             "median_event_ms": round(statistics.median(samples), 3),
                             "p95_event_ms": round(sorted(samples)[max(0, math.ceil(len(samples)*.95)-1)], 3),
                             "commit_ms": round(commit_ms, 3), "paint_events": len(paints),
                             "mean_paint_ms": round(statistics.mean(p[0] for p in paints), 3) if paints else 0,
                             "mean_canvas_paint_fraction": round(statistics.mean(p[1] for p in paints), 4) if paints else 0})
        board.close()
        board.deleteLater()
        app.processEvents()
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=".test-artifacts/performance.json")
    parser.add_argument("--profile")
    parser.add_argument("--frames", type=int, default=16)
    args = parser.parse_args()
    rows = run(args.frames)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"platform": os.environ["QT_QPA_PLATFORM"], "timings": rows}, indent=2), encoding="utf-8")
    if args.profile:
        profiler = cProfile.Profile()
        profiler.runcall(run, max(6, args.frames//2))
        with Path(args.profile).open("w", encoding="utf-8") as stream:
            pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(40)
    print(json.dumps({"results": str(target), "workloads": len(rows), "500_objects": rows[-7:]}, indent=2))


if __name__ == "__main__":
    main()
