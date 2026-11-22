"""Run the same native, paced input and idle workload against either checkout."""
import argparse
import json
import math
from pathlib import Path
import statistics
import sys
import time


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('themes', nargs='+')
    args = p.parse_args()
    sys.path.insert(0, str(args.source.resolve()))
    from PySide6.QtCore import QEvent, QEventLoop, QObject, QPointF, QTimer, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication
    from mini_whiteboard.board import BoardWindow
    from mini_whiteboard.geometry import Rect
    from mini_whiteboard.snapping import SnapPreferences

    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    class Paints(QObject):
        n = 0
        def eventFilter(self, watched, event):
            if event.type() == QEvent.Type.Paint:
                self.n += 1
            return False

    def rest(ms):
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    report = {}
    for theme in args.themes:
        prefs = SnapPreferences()
        prefs.set_theme(theme)
        b = BoardWindow('Mini Whiteboard', prefs)
        b.place(Rect(85, 95, 580, 330))
        counter = Paints()
        for widget in (b, b.canvas, b.minus, b.remove):
            widget.installEventFilter(counter)
        rest(600)
        counter.n = 0
        wall, cpu = time.perf_counter(), time.process_time()
        rest(4000)
        duration = time.perf_counter() - wall
        idle = dict(duration_s=duration, process_cpu_s=time.process_time()-cpu, paints=counter.n)
        def send(kind, x, y):
            point = QPointF(x, y)
            btn = Qt.MouseButton.LeftButton
            e = QMouseEvent(kind, point, QPointF(b.canvas.mapToGlobal(point.toPoint())),
                            Qt.MouseButton.NoButton if kind == QEvent.Type.MouseMove else btn,
                            Qt.MouseButton.NoButton if kind == QEvent.Type.MouseButtonRelease else btn,
                            Qt.KeyboardModifier.NoModifier)
            app.sendEvent(b.canvas, e)
        send(QEvent.Type.MouseButtonPress, 45, 110)
        times, intervals = [], []
        count = 0
        last_tick = None
        loop = QEventLoop()
        timer = QTimer()
        timer.setTimerType(Qt.TimerType.PreciseTimer)
        def tick():
            nonlocal count, last_tick
            start = time.perf_counter()
            if last_tick is not None:
                intervals.append((start-last_tick)*1000)
            last_tick = start
            for _ in range(4):
                count += 1
                send(QEvent.Type.MouseMove, 45+abs((count%800)-400), 115+59*math.sin(count*.021))
            # Drain posted paints just as the normal event loop does between input batches.
            app.sendPostedEvents(None, QEvent.Type.UpdateRequest)
            times.append((time.perf_counter()-start)*1000)
            if count == 1200:
                timer.stop()
                loop.quit()
        timer.timeout.connect(tick)
        counter.n = 0
        wall, cpu = time.perf_counter(), time.process_time()
        timer.start(16)
        loop.exec()
        send(QEvent.Type.MouseButtonRelease, 45+abs((count%800)-400), 115+59*math.sin(count*.021))
        app.processEvents()
        assert len(b.canvas.document.objects) == 1 and len(b.canvas.document.objects[0].points) >= 1200
        def p95(samples):
            return sorted(samples)[math.ceil(.95*len(samples))-1]
        report[theme] = dict(native=b.native_glass, idle=idle, drawing=dict(
            samples=count, committed_points=len(b.canvas.document.objects[0].points), paints=counter.n,
            duration_s=time.perf_counter()-wall, process_cpu_s=time.process_time()-cpu,
            batch_median_ms=statistics.median(times), batch_p95_ms=p95(times), interval_p95_ms=p95(intervals)))
        b.close()
        b.deleteLater()
        app.processEvents()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
