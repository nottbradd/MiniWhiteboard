"""Display-cache lifetime, bounded work, pixel equivalence and invisible resizing."""
from dataclasses import replace
import math
from unittest.mock import patch

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter
from PySide6.QtTest import QTest

from tests.test_canvas import CanvasCase
from tests.qt_case import APP
from mini_whiteboard import clipboard, images, rendering, windows
from mini_whiteboard.background import ScreenshotBackground
from mini_whiteboard.document import Shape, Stroke, transformed
from mini_whiteboard.scene import Record
from mini_whiteboard.settings import BORDER, BORDER_WIDTH, EDGE_GRIP
from mini_whiteboard.snapping import SnapTargets
from mini_whiteboard.transforms import Affine, translation


class ScreenshotRefinementTests(CanvasCase):
    def fixture(self):
        image = QImage(1920,1080,QImage.Format.Format_RGB32)
        image.fill(QColor('#c5ddf2'))
        painter = QPainter(image)
        painter.fillRect(20,30,300,200,QColor('#286cba'))
        painter.end()
        obj = images.from_image(image,locked=True,transform=Affine(a=.32,d=.32))
        self.canvas.document.add(obj)
        self.canvas.set_screenshot_background(obj)
        APP.processEvents()
        return obj

    def test_cache_is_display_sized_and_reused_during_annotation_edits(self):
        obj = self.fixture()
        cache = self.canvas.background_cache
        self.assertEqual((cache.image.width(),cache.image.height()),(self.canvas.width(),self.canvas.height()))
        raster = cache.image
        original_paint = rendering.paint_object
        def checked(painter, candidate, *args):
            self.assertNotEqual(candidate.id,obj.id,'Background rescaled during drawing')
            return original_paint(painter,candidate,*args)
        with (patch.object(images,'decoded',side_effect=AssertionError('Image decoded during annotation')),
              patch.object(clipboard,'encode',side_effect=AssertionError('Clipboard used during annotation')),
              patch.object(rendering,'paint_object',new=checked)):
            self.drag((70,150),(320,180))
            self.canvas.set_tool('Eraser')
            self.drag((190,145),(190,195))
            self.canvas.select_all()
            self.canvas.nudge(10,1)
            APP.processEvents()
        self.assertIs(cache.image,raster)
        self.assertEqual(cache.builds,1)
        self.assertIs(self.canvas.document.objects[0],obj)

    def test_undo_snapshots_share_exact_image_and_bytes(self):
        obj = self.fixture()
        for i in range(5):
            self.canvas.document.add(Shape('Rectangle',(40+i*30,50),(65+i*30,80)))
        self.canvas.select_all()
        self.canvas.nudge(5,7)
        for edit in self.canvas.document.history[1:]:
            self.assertIs(edit.before[0],obj)
            self.assertIs(edit.after[0],obj)
            self.assertIs(edit.after[0].png,obj.png)
        final = self.canvas.document.objects
        self.canvas.document.undo()
        self.canvas.document.redo()
        self.assertIs(self.canvas.document.objects,final)

    def test_dpi_cache_pixels_match_direct_render_without_double_scaling(self):
        obj = self.fixture()
        record = self.canvas.scene.record(obj.id)
        for dpr in (1,1.25,1.5,2):
            cache = ScreenshotBackground(obj)
            cache.prepare(self.canvas.rect(),dpr,self.canvas.clip_spec,record)
            self.assertEqual(cache.image.width(),math.ceil(self.canvas.width()*dpr))
            self.assertEqual(cache.image.height(),math.ceil(self.canvas.height()*dpr))
            self.assertEqual(cache.image.devicePixelRatio(),dpr)
            direct = QImage(cache.image.size(),cache.image.format())
            direct.setDevicePixelRatio(dpr)
            direct.fill(Qt.GlobalColor.transparent)
            painter = QPainter(direct)
            painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
            painter.setClipPath(rendering.clip_path(self.canvas.clip_spec))
            rendering.paint_object(painter,obj,record.paint)
            painter.end()
            self.assertEqual(cache.image,direct)
            output = QImage(direct.size(),direct.format())
            output.setDevicePixelRatio(dpr)
            output.fill(Qt.GlobalColor.transparent)
            painter = QPainter(output)
            cache.paint(painter,None)
            painter.end()
            self.assertEqual(output,direct)

    def test_cache_regenerates_only_for_viewport_dpi_or_clip_change(self):
        obj = self.fixture()
        cache = self.canvas.background_cache
        record = self.canvas.scene.record(obj.id)
        for _ in range(5):
            cache.prepare(self.canvas.rect(),1,self.canvas.clip_spec,record)
        self.assertEqual(cache.builds,1)
        cache.prepare(self.canvas.rect(),1.5,self.canvas.clip_spec,record)
        self.assertEqual(cache.builds,2)
        cache.prepare(self.canvas.rect().adjusted(0,0,20,20),1.5,self.canvas.clip_spec,record)
        self.assertEqual(cache.builds,3)
        changed = replace(self.canvas.clip_spec,radius=self.canvas.clip_spec.radius+1)
        cache.prepare(self.canvas.rect().adjusted(0,0,20,20),1.5,changed,record)
        self.assertEqual(cache.builds,4)

    def test_unlock_transform_and_undo_switch_rendering_path_correctly(self):
        obj = self.fixture()
        cache = self.canvas.background_cache
        self.canvas.set_locked({obj.id},False)
        current = self.canvas.document.get(obj.id)
        self.assertFalse(cache.matches(current))
        self.assertIn(obj.id,self.canvas.scene.editable_order)
        self.canvas.nudge(25,10)
        moved = self.canvas.document.get(obj.id)
        self.assertEqual(moved.transform,translation(25,10) @ obj.transform)
        self.assertIs(moved.png,obj.png)
        self.canvas.set_locked({obj.id},True)
        self.assertFalse(cache.matches(self.canvas.document.get(obj.id)))
        for _ in range(3):
            self.canvas.document.undo()
        self.canvas.sync_selection()
        self.assertIs(self.canvas.document.get(obj.id),obj)
        self.assertTrue(cache.matches(obj))
        APP.processEvents()
        self.assertEqual(cache.builds,1)

    def test_locked_background_never_enters_editable_query_or_detailed_hit(self):
        obj = self.fixture()
        self.assertNotIn(obj.id,self.canvas.scene.editable_order)
        with patch.object(rendering,'hit_path',side_effect=AssertionError('Detailed background hit')):
            self.assertIsNone(self.canvas.hit_test((200,200)))
            self.canvas.select_all()
            self.canvas.set_tool('Eraser')
            self.drag((160,150),(260,150))
            self.canvas.set_number(5)
            self.drag((160,150),(260,150))
        self.assertEqual(list(self.canvas.scene.query(QRectF(self.canvas.rect()),editable=True)),[])
        self.assertEqual(self.canvas.document.objects,(obj,))
        self.assertEqual(self.canvas.hit_test((200,200),include_locked=True),obj)

    def test_locked_background_is_excluded_from_guides_until_unlocked(self):
        obj = self.fixture()
        viewport = QRectF(self.canvas.rect())
        targets = SnapTargets(self.canvas.scene.records.values(),set(),viewport)
        self.assertEqual(tuple(len(axis) for axis in targets.axes),(3,3))
        self.canvas.set_locked({obj.id},False)
        targets = SnapTargets(self.canvas.scene.records.values(),set(),viewport)
        self.assertEqual(tuple(len(axis) for axis in targets.axes),(6,6))

    def test_drawing_only_invalidates_changed_tail(self):
        self.fixture()
        QTest.mousePress(self.canvas,Qt.MouseButton.LeftButton,pos=QPoint(40,150))
        for x in range(60,500,20):
            QTest.mouseMove(self.canvas,QPoint(x,150+round(20*math.sin(x/40))))
        with patch.object(self.canvas,'update',wraps=self.canvas.update) as repaint:
            QTest.mouseMove(self.canvas,QPoint(520,155))
        self.assertTrue(repaint.call_args_list)
        for call in repaint.call_args_list:
            bounds = call.args[0].boundingRect()
            self.assertLess(bounds.width(),100)
            self.assertGreater(bounds.left(),400)
        QTest.mouseRelease(self.canvas,Qt.MouseButton.LeftButton,pos=QPoint(520,155))

    def test_incremental_drawing_matches_fresh_full_repaint(self):
        self.fixture()
        QTest.mousePress(self.canvas,Qt.MouseButton.LeftButton,pos=QPoint(40,160))
        def paint_frame(target, region=None):
            painter = QPainter(target)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            if region is not None:
                painter.setClipRegion(region)
            painter.fillRect(target.rect(),Qt.GlobalColor.white)
            self.canvas.background_cache.paint(painter,None)
            rendering.paint_object(painter,self.canvas.preview)
            painter.end()
        backing = QImage(self.canvas.size(),QImage.Format.Format_ARGB32_Premultiplied)
        paint_frame(backing)
        for position in ((65,180),(80,130),(170,190),(270,100),(300,260),(150,310)):
            with patch.object(self.canvas,'update',wraps=self.canvas.update) as repaint:
                QTest.mouseMove(self.canvas,QPoint(*position))
            for call in repaint.call_args_list:
                paint_frame(backing,call.args[0])
            expected = QImage(backing.size(),backing.format())
            paint_frame(expected)
            self.assertEqual(backing,expected,position)
        QTest.mouseRelease(self.canvas,Qt.MouseButton.LeftButton,pos=QPoint(150,310))

    def test_cache_retains_object_stacking_and_control_holes(self):
        obj = self.fixture()
        rect = self.canvas.control_rects()[0].intersected(QRectF(self.canvas.rect()))
        point = rect.center().toPoint()
        self.assertEqual(self.canvas.background_cache.image.pixelColor(point).alpha(),0)
        stroke = Stroke(((70,150),(250,150)),10,color='#e04444')
        self.canvas.document.add(stroke)
        self.canvas.update()
        APP.processEvents()
        rendered = self.canvas.grab().toImage()
        self.assertEqual(rendered.pixelColor(170,150).name(),'#e04444')
        self.assertEqual(rendered.pixelColor(170,160).name(),'#c5ddf2')

    def test_only_top_has_a_one_pixel_visible_border(self):
        for screenshot in (False,True):
            if screenshot:
                original = self.fixture()
                obj = replace(original,transform=Affine(a=self.canvas.width()/1920,d=self.canvas.height()/1080))
                self.canvas.document.replace(obj)
                self.canvas.set_screenshot_background(obj)
            image = self.board.grab().toImage()
            paper = self.board.paper_rect()
            x,y = round(paper.center().x()),round(paper.center().y())
            self.assertEqual(image.pixelColor(x,round(paper.top())).name(),BORDER)
            self.assertEqual(image.pixelColor(x,round(paper.top()+BORDER_WIDTH)).name(),'#ffffff')
            for px,py in ((round(paper.left()),y),(round(paper.right()-1),y),(x,round(paper.bottom()-1))):
                self.assertEqual(image.pixelColor(px,py).name(),'#c5ddf2' if screenshot else '#ffffff')

    def test_all_eight_invisible_edge_zones_and_cursors(self):
        self.assertEqual(EDGE_GRIP,7)
        r = self.board.paper_rect()
        left,right,top,bottom = Qt.Edge.LeftEdge,Qt.Edge.RightEdge,Qt.Edge.TopEdge,Qt.Edge.BottomEdge
        points = ((r.left()+6,r.center().y(),left),(r.right()-6,r.center().y(),right),
                  (r.center().x(),r.top()+6,top),(r.center().x(),r.bottom()-6,bottom),
                  (r.left()+6,r.top()+6,left|top),(r.right()-6,r.top()+6,right|top),
                  (r.left()+6,r.bottom()-6,left|bottom),(r.right()-6,r.bottom()-6,right|bottom))
        for x,y,edges in points:
            p = QPointF(x,y)
            self.assertEqual(self.board.edges_at(p),edges)
            self.assertNotEqual(self.board.edge_cursor(edges),Qt.CursorShape.ArrowCursor)
        self.assertFalse(self.board.edges_at(QPointF(r.left()+8,r.center().y())))

    def test_canvas_edge_routes_to_window_resize_and_escape_restores(self):
        pos = QPoint(3,self.canvas.height()//2)
        original = windows.window_rect(self.board)
        with patch('mini_whiteboard.windows.cursor_position',return_value=(300,200)):
            QTest.mouseMove(self.canvas,pos)
            self.assertEqual(self.canvas.cursor().shape(),Qt.CursorShape.SizeHorCursor)
            QTest.mousePress(self.canvas,Qt.MouseButton.LeftButton,pos=pos)
        self.assertEqual(self.board._gesture[0],'resize')
        self.assertIsNone(self.canvas.gesture)
        with patch('mini_whiteboard.windows.cursor_position',return_value=(280,200)):
            QTest.mouseMove(self.board,QPoint(10,200))
        self.assertGreater(windows.window_rect(self.board).width,original.width)
        self.board.cancel_window_gesture()
        self.assertEqual(windows.window_rect(self.board),original)

    def test_handle_priority_and_active_drawing_keep_their_input_at_edges(self):
        obj = Shape('Rectangle',(5,100),(100,180),2)
        self.canvas.document.add(obj)
        self.canvas.set_tool('Select')
        self.canvas.set_selection({obj.id})
        handle = self.canvas.frame.handle(7)
        QTest.mousePress(self.canvas,Qt.MouseButton.LeftButton,pos=QPoint(round(handle[0]),round(handle[1])))
        self.assertEqual(self.canvas.gesture,'resize')
        self.assertIsNone(self.board._gesture)
        self.canvas.cancel_interaction()
        self.canvas.set_tool('Draw')
        self.drag((100,230),(2,230))
        self.assertIsNone(self.board._gesture)
        self.assertEqual(len(self.canvas.document.objects),2)
