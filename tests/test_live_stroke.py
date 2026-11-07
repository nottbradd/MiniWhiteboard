from dataclasses import replace
import math
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtTest import QTest
from tests.test_canvas import CanvasCase
from mini_whiteboard import rendering
from mini_whiteboard.document import Stroke
from mini_whiteboard.live_stroke import LiveStroke


class LiveStrokeTests(CanvasCase):
    def test_incremental_geometry_and_pixels_equal_immutable_stroke(self):
        for clip in (None,self.canvas.clip_spec):
            for width in (2,6,14):
                source = Stroke(((1,3),),width,clip=clip)
                live = LiveStroke(source)
                for i in range(50):
                    if i:
                        live.append((i*3.3,30+40*math.sin(i*.4)))
                    frozen = live.freeze()
                    self.assertEqual(live.path(),rendering.object_path(frozen))
                    data = live.paint_data()
                    self.assertEqual(data.remaining,rendering.remaining_local(frozen))
                    def image(obj,data):
                        im = QImage(200,150,QImage.Format.Format_ARGB32_Premultiplied)
                        im.fill(Qt.GlobalColor.transparent)
                        p = QPainter(im)
                        p.setRenderHint(QPainter.RenderHint.Antialiasing)
                        rendering.paint_object(p,obj,data)
                        p.end()
                        return im
                    self.assertEqual(image(source,data),image(frozen,rendering.paint_data(frozen)))

    def test_live_versions_never_enter_shared_geometry_caches(self):
        canvas = self.canvas
        QTest.mousePress(canvas,Qt.MouseButton.LeftButton,pos=QPoint(50,100))
        before = rendering._object_path.cache_info().misses
        for i in range(500):
            canvas.update_gesture((50+i,100+30*math.sin(i*.04)))
            canvas.live_stroke.paint_data()
        self.assertEqual(rendering._object_path.cache_info().misses,before)
        expected = tuple(canvas.points)
        QTest.mouseRelease(canvas,Qt.MouseButton.LeftButton,pos=QPoint(549,round(expected[-1][1])))
        obj = canvas.document.objects[-1]
        self.assertEqual(obj.points[:len(expected)],expected)
        self.assertEqual(canvas.document.index,1)
        self.assertIsNone(canvas.live_stroke)
        canvas.undo_redo()
        self.assertEqual(canvas.document.objects,())
        canvas.undo_redo(True)
        self.assertIs(canvas.document.objects[-1],obj)

    def test_cancel_discards_live_geometry_without_history(self):
        canvas = self.canvas
        QTest.mousePress(canvas,Qt.MouseButton.LeftButton,pos=QPoint(50,100))
        canvas.update_gesture((200,140))
        canvas.cancel_interaction()
        self.assertIsNone(canvas.live_stroke)
        self.assertEqual(canvas.points,[])
        self.assertEqual(canvas.document.index,0)
