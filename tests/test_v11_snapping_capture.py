from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QPoint, QRectF, QSettings, Qt
from PySide6.QtTest import QTest

from tests.qt_case import APP, QtCase
from tests.test_canvas import CanvasCase
from tests.test_tray import FakeNativeHotkeys
from tests.test_v11_editing import sample_image
from mini_whiteboard.app import WhiteboardApplication
from mini_whiteboard.document import Shape, ImageObject
from mini_whiteboard.geometry import Rect
from mini_whiteboard.scene import Scene
from mini_whiteboard.snapping import SnapPreferences, SnapTargets
from mini_whiteboard.transforms import SelectionFrame, resize_transform
from mini_whiteboard import rendering, windows
from mini_whiteboard.placement import PlacementController
from mini_whiteboard.screenshot import ScreenshotController


class SnapTests(CanvasCase):
    def test_defaults_and_settings_roundtrip(self):
        prefs = SnapPreferences()
        self.assertTrue(prefs.smart_guides)
        self.assertFalse(prefs.grid_snap)
        settings = QSettings(str(Path('.test-artifacts/v11-settings.ini').absolute()),QSettings.Format.IniFormat)
        settings.clear()
        prefs = SnapPreferences(settings=settings)
        prefs.set_grid(True)
        prefs.set_smart(False)
        restored = SnapPreferences(settings=settings)
        self.assertTrue(restored.grid_snap)
        self.assertFalse(restored.smart_guides)

    def test_object_edge_alignment_and_guides(self):
        a = Shape('Rectangle',(100,100),(160,160),2)
        b = Shape('Rectangle',(220,110),(280,170),2)
        self.canvas.document.commit((a,b),'Fixture')
        self.canvas.preferences.smart_guides = True
        self.canvas.set_tool('Select')
        self.canvas.set_selection({a.id})
        self.canvas.start = self.canvas.last_sample = (130,130)
        self.canvas.start_gesture('move')
        self.canvas.update_gesture((187,137))
        changed = self.canvas.scene.record(a.id)
        self.assertAlmostEqual(changed.bounds.right(),rendering.bounds(b).left())
        self.assertTrue(self.canvas.guide_lines)
        self.canvas.cancel_interaction()
        self.assertFalse(self.canvas.guide_lines)
        self.assertEqual(self.canvas.document.objects,(a,b))

    def test_board_center_and_edges_snap(self):
        prefs = SnapPreferences()
        targets = SnapTargets([],set(),QRectF(0,0,600,400))
        matrix,guides = targets.move(QRectF(50,50,100,60),197,121,prefs)
        moved = QRectF(50,50,100,60).translated(matrix.tx,matrix.ty)
        self.assertEqual(moved.center().x(),300)
        self.assertEqual(moved.center().y(),200)
        self.assertEqual(len(guides),2)
        matrix,_ = targets.move(QRectF(50,50,100,60),-48,-47,prefs)
        self.assertEqual((matrix.tx,matrix.ty),(-50,-50))

    def test_grid_and_alt_override(self):
        prefs = SnapPreferences()
        prefs.smart_guides = False
        prefs.grid_snap = True
        targets = SnapTargets([],set(),QRectF(0,0,600,400))
        bounds = QRectF(13,17,40,30)
        matrix,guides = targets.move(bounds,8,5,prefs)
        self.assertEqual((bounds.x()+matrix.tx,bounds.y()+matrix.ty),(20,20))
        self.assertFalse(guides)
        matrix,guides = targets.move(bounds,8,5,prefs,disabled=True)
        self.assertEqual((matrix.tx,matrix.ty),(8,5))
        self.assertFalse(guides)

    def test_smart_alignment_wins_over_grid(self):
        prefs = SnapPreferences()
        prefs.grid_snap = True
        scene = Scene()
        scene.sync((Shape('Rectangle',(102,100),(160,160),2),))
        targets = SnapTargets(scene.records.values(),set(),QRectF(0,0,600,400))
        matrix,guides = targets.move(QRectF(20,105,40,30),38,0,prefs)
        self.assertEqual(20+matrix.tx+40,101)
        self.assertTrue(guides)

    def test_resize_snaps_reachable_edge_preserving_ratio_and_anchor(self):
        prefs = SnapPreferences()
        targets = SnapTargets([],set(),QRectF(0,0,300,200))
        frame = SelectionFrame((100,100),100,60)
        handle = 4
        start = frame.handle(handle)
        matrix = resize_transform(frame,handle,start,(298,210),True)
        result,guides = targets.resize(frame,handle,matrix,True,prefs)
        self.assertEqual(result.map(frame.handle(0)),frame.handle(0))
        self.assertAlmostEqual(result.a,result.d)
        # Explicit vertical edge target close to its current transformed handle.
        p = matrix.map(frame.handle(handle))
        target_scene = Scene()
        target_scene.sync((Shape('Rectangle',(p[0]+3,p[1]-20),(p[0]+60,p[1]+30)),))
        targets = SnapTargets(target_scene.records.values(),set(),QRectF(0,0,700,500))
        result,guides = targets.resize(frame,handle,matrix,True,prefs)
        self.assertTrue(guides)
        self.assertAlmostEqual(result.a,result.d)
        self.assertEqual(result.map(frame.handle(0)),frame.handle(0))

    def test_guides_do_not_use_detailed_geometry_per_pointer_sample(self):
        self.canvas.document.add(Shape('Rectangle',(60,70),(160,170)))
        self.canvas.preferences.smart_guides = True
        self.canvas.select_all()
        self.canvas.start = self.canvas.last_sample = (110,120)
        self.canvas.start_gesture('move')
        with patch.object(rendering,'hit_path',side_effect=AssertionError('detailed snapping')):
            for i in range(10):
                self.canvas.update_gesture((115+i,125+i))
        self.assertEqual(self.canvas.document.index,1)
        self.canvas.cancel_interaction()

    def test_canvas_alt_release_bypasses_snap_and_undo_restores_exact_object(self):
        obj = Shape('Rectangle',(101,101),(161,161),2)
        self.canvas.document.add(obj)
        self.canvas.preferences.set_grid(True)
        self.canvas.select_all()
        self.canvas.start = self.canvas.last_sample = (130,130)
        self.canvas.start_gesture('move')
        self.canvas.update_gesture((144,144))
        self.assertEqual(self.canvas.scene.record(obj.id).bounds.left(),110)
        QTest.mouseRelease(self.canvas,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.AltModifier,QPoint(144,144))
        self.assertEqual(self.canvas.document.objects[0].transform.tx,14)
        self.assertEqual(self.canvas.document.index,2)
        self.assertFalse(self.canvas.guide_lines)
        self.canvas.document.undo()
        self.assertEqual(self.canvas.document.objects,(obj,))
        self.canvas.preferences.set_smart(True)
        self.canvas.preferences.set_grid(False)
        self.assertEqual(self.canvas.document.index,1)


class CaptureTests(QtCase):
    def controllers(self):
        hotkeys = FakeNativeHotkeys(APP)
        placement = PlacementController(hotkeys)
        capture = ScreenshotController(hotkeys,placement)
        placement.before_start = capture.cancel
        self.addCleanup(placement.cancel)
        self.addCleanup(capture.cancel)
        return hotkeys,placement,capture

    def test_capture_click_drag_normalizes_then_hides_before_reading_pixels(self):
        _,placement,capture = self.controllers()
        capture.start()
        self.assertTrue(capture.active)
        capture.anchor = (400,300)
        capture.track((100,80))
        self.assertTrue(all(o.outline==Rect(100,80,300,220) for o in capture.overlays))
        captures = []
        capture.captured.connect(lambda r,image:captures.append((r,image)))
        def read(rect):
            self.assertFalse(capture.overlays)
            return sample_image(300,220)
        with patch('mini_whiteboard.windows.capture_rect',side_effect=read):
            capture.finish((100,80))
            APP.processEvents()
        self.assertEqual(captures[0][0],Rect(100,80,300,220))
        self.assertFalse(capture.active)
        self.assertFalse(placement.state.active)

    def test_escape_cancels_and_removes_pending_capture(self):
        hotkeys,_,capture = self.controllers()
        capture.start()
        capture.anchor = (100,100)
        hotkeys.events.cancel.emit()
        self.assertFalse(capture.active)
        capture.start()
        capture.anchor = (100,100)
        capture.finish((500,400))
        capture.cancel()
        with patch('mini_whiteboard.windows.capture_rect') as read:
            APP.processEvents()
            self.assertFalse(read.called)

    def test_switching_workflows_preserves_two_press_placement(self):
        hotkeys,placement,capture = self.controllers()
        capture.start()
        with patch('mini_whiteboard.windows.cursor_position',return_value=(100,100)):
            hotkeys.events.create.emit()
        self.assertFalse(capture.active)
        self.assertEqual(placement.state.anchor,(100,100))
        rects = []
        placement.confirmed.connect(rects.append)
        with patch('mini_whiteboard.windows.cursor_position',return_value=(500,400)):
            hotkeys.events.create.emit()
        self.assertEqual(rects,[Rect(100,100,400,300)])
        placement.start_at((100,100))
        hotkeys.events.capture.emit()
        self.assertFalse(placement.state.active)
        self.assertTrue(capture.active)

    def test_capture_failure_is_reported_and_overlay_is_removed(self):
        _,_,capture = self.controllers()
        messages = []
        capture.message.connect(messages.append)
        capture.start()
        capture.anchor = (100,100)
        with patch('mini_whiteboard.windows.capture_rect',side_effect=OSError('unavailable')):
            capture.finish((500,400))
            APP.processEvents()
        self.assertFalse(capture.active)
        self.assertIn('unavailable',messages[-1])

    def test_screenshot_board_is_locked_image_ready_for_annotation(self):
        with patch('mini_whiteboard.windows.NativeHotkeys',FakeNativeHotkeys):
            controller = WhiteboardApplication(APP)
        try:
            board = controller.create_screenshot_board(Rect(100,100,400,250),sample_image(400,250))
            obj = board.canvas.document.objects[0]
            self.assertIsInstance(obj,ImageObject)
            self.assertTrue(obj.locked)
            self.assertEqual(board.canvas.tool,'Draw')
            self.assertAlmostEqual(rendering.bounds(obj).width()/rendering.bounds(obj).height(),1.6)
            self.assertEqual(board.canvas.preferences,controller.preferences)
        finally:
            controller.cleanup()

    def test_tray_preferences_checkmarks_track_shared_state(self):
        with patch('mini_whiteboard.windows.NativeHotkeys',FakeNativeHotkeys):
            controller = WhiteboardApplication(APP)
        try:
            controller.rebuild_menu()
            submenu = next(a.menu() for a in controller.menu.actions() if a.text()=='Snap & Guides')
            smart,grid = submenu.actions()
            self.assertTrue(smart.isChecked())
            self.assertFalse(grid.isChecked())
            grid.trigger()
            smart.trigger()
            controller.rebuild_menu()
            submenu = next(a.menu() for a in controller.menu.actions() if a.text()=='Snap & Guides')
            self.assertEqual([a.isChecked() for a in submenu.actions()],[False,True])
        finally:
            controller.cleanup()
