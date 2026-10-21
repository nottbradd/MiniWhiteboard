"""Inset, passive overlays, eraser toggles, and bounded interaction work."""
from unittest.mock import patch

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QPainter, QRegion
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from tests.test_canvas import CanvasCase
from tests.qt_case import APP
from mini_whiteboard import rendering, windows
from mini_whiteboard.document import Shape, Stroke, Text
from mini_whiteboard.geometry import Rect
from mini_whiteboard.placement import PreviewOverlay
from mini_whiteboard.settings import BORDER_WIDTH, CANVAS_INSET, TOP_STRIP, RADIUS, SHADOW


class PolishTests(CanvasCase):
    def test_canvas_inset_and_reserved_control_holes(self):
        paper = self.board.paper_rect()
        self.assertEqual((CANVAS_INSET, TOP_STRIP, BORDER_WIDTH), (0, 11, 1))
        self.assertEqual((RADIUS, SHADOW), (12, 8))
        self.assertEqual(self.canvas.x()-paper.left(), 0)
        self.assertEqual(paper.right()-(self.canvas.x()+self.canvas.width()), 0)
        self.assertEqual(self.canvas.y()-paper.top(), 11)
        self.assertEqual(paper.bottom()-(self.canvas.y()+self.canvas.height()), 0)
        self.assertTrue(self.canvas.valid_position((2, 40)))
        for rect in self.canvas.control_rects():
            self.assertFalse(self.canvas.valid_position((rect.center().x(), 2)))
        self.assertFalse(self.canvas.valid_position((0, self.canvas.height()-1)))

    def test_five_toggles_to_default_and_numbers_exit_stroke_mode(self):
        self.key(Qt.Key.Key_E)
        self.key(Qt.Key.Key_4)
        sequence = ((5, "stroke", 64), (5, "circular", 16), (5, "stroke", 16),
                    (1, "circular", 8), (5, "stroke", 8), (4, "circular", 64))
        for key, mode, diameter in sequence:
            self.key(Qt.Key.Key_0+key)
            self.assertEqual((self.canvas.eraser_mode, self.canvas.eraser_diameter), (mode, diameter))
        self.assertEqual(self.canvas.document.index, 0)

    def test_exact_digits_stay_in_transformed_editor(self):
        from mini_whiteboard.transforms import rotation, translation
        self.key(Qt.Key.Key_E)
        self.key(Qt.Key.Key_4)
        self.key(Qt.Key.Key_5)
        obj = Text((0, 0), "", transform=translation(100, 80) @ rotation(15))
        self.canvas.begin_editing(obj)
        APP.processEvents()
        target = QApplication.focusWidget()
        QTest.keyClicks(target, "1234554321")
        self.assertEqual(self.canvas.editor.toPlainText(), "1234554321")
        self.assertEqual((self.canvas.tool, self.canvas.eraser_mode, self.canvas.eraser_key), ("Eraser", "stroke", 4))
        self.assertEqual(self.canvas.document.index, 0)
        QTest.keyClick(target, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.canvas.document.index, 0)
        QTest.keyClick(target, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClick(target, Qt.Key.Key_Escape)
        self.assertEqual(self.canvas.document.objects[0].text, "1234554321")

    def test_cursor_is_complete_at_four_edges_and_four_corners(self):
        self.canvas.set_tool("Eraser")
        self.canvas.set_number(4)
        w, h = self.canvas.width(), self.canvas.height()
        positions = ((w/2, 1), (w/2, h-2), (1, h/2), (w-2, h/2),
                     (3, 3), (w-3, 15), (7, h-7), (w-7, h-7))
        for pos in positions:
            self.canvas.cursor_position = pos
            self.canvas.sync_tool_overlay()
            overlay = self.canvas.tool_overlay
            image = overlay.grab().toImage()
            rect = overlay.visual_rect
            # Four extremities of the ring remain painted even beyond the board.
            # Top-right control cutouts intentionally occlude tool chrome.
            for dx, dy in ((32, 0), (-32, 0), (0, 32), (0, -32)):
                p = QPointF(pos[0]+dx, pos[1]+dy)
                if any(r.adjusted(-2, -2, 2, 2).contains(p) for r in self.canvas.control_rects()):
                    continue
                x, y = round(p.x()-rect.x()), round(p.y()-rect.y())
                self.assertTrue(any(image.pixelColor(xx, yy).alpha() > 100
                                    for xx in range(x-1, x+2) for yy in range(y-1, y+2)), (pos, dx, dy))
            self.assertTrue(self.canvas.hasFocus())
            self.assertTrue(overlay.windowFlags() & Qt.WindowType.WindowTransparentForInput)
        self.board.minimize_to_tray()
        self.assertFalse(self.canvas.tool_overlay.isVisible())

    def test_cursor_mode_changes_immediately_without_document_repaint(self):
        self.canvas.set_tool("Eraser")
        self.canvas.cursor_position = (150, 150)
        self.canvas.sync_tool_overlay()
        normal = self.canvas.tool_overlay.grab().toImage()
        self.canvas.set_number(5)
        self.assertTrue(self.canvas.tool_overlay.whole_stroke)
        self.assertNotEqual(normal, self.canvas.tool_overlay.grab().toImage())
        with patch.object(self.canvas, "update", wraps=self.canvas.update) as repaint:
            QTest.mouseMove(self.canvas, QPoint(180, 150))
            self.assertEqual(repaint.call_count, 0)
        self.canvas.begin_editing(Text((100, 100)))
        self.assertFalse(self.canvas.tool_overlay.isVisible())

    def test_cursor_does_not_paint_over_window_controls(self):
        self.canvas.set_tool("Eraser")
        r = self.canvas.control_rects()[0]
        self.canvas.cursor_position = (r.center().x(), 15)
        self.canvas.set_number(4)
        self.canvas.sync_tool_overlay()
        overlay = self.canvas.tool_overlay
        image = overlay.grab().toImage()
        for y in range(image.height()):
            for x in range(image.width()):
                p = QPointF(x+overlay.visual_rect.x()+.5, y+overlay.visual_rect.y()+.5)
                if r.adjusted(1, 1, -1, -1).contains(p):
                    self.assertEqual(image.pixelColor(x, y).alpha(), 0)

    def test_new_drawing_cannot_reveal_outside_ink_when_board_expands(self):
        self.drag((40, 80), (-40, 80))
        obj = self.canvas.document.objects[0]
        self.assertIsNotNone(obj.clip)
        self.assertGreaterEqual(rendering.bounds(obj).left(), -.001)
        self.assertFalse(rendering.hit_path(obj).contains(QPointF(-2, 80)))
        self.board.resize(1000, 800)
        self.assertEqual(self.canvas.document.objects[0], obj)
        self.assertGreaterEqual(rendering.bounds(obj).left(), -.001)

    def test_brush_outside_viewport_does_not_erase_hidden_content(self):
        h = self.canvas.height()
        obj = Stroke(((100, h-40), (100, h+80)), 8)
        self.canvas.document.add(obj)
        self.canvas.set_tool("Eraser")
        self.canvas.set_number(4)
        self.drag((100, h-10), (100, h+40))
        result = self.canvas.document.objects[0]
        self.assertFalse(rendering.visible_ink(result).contains(QPointF(100, h-10)))
        self.assertTrue(rendering.visible_ink(result).contains(QPointF(100, h+10)))
        self.board.resize(700, 800)
        self.assertTrue(rendering.visible_ink(result).contains(QPointF(100, h+10)))

    def test_broad_phase_hit_tests_only_candidates_and_keeps_topmost(self):
        distant = tuple(Stroke(((1000+i*10, 100), (1000+i*10, 130)), 2) for i in range(500))
        lower = Shape("Rectangle", (20, 20), (80, 80))
        upper = Shape("Ellipse", (25, 25), (75, 75))
        self.canvas.document.commit((lower, upper, *distant), "Fixture")
        self.canvas.sync_scene()
        with patch.object(rendering, "hit_path", wraps=rendering.hit_path) as hit:
            self.assertEqual(self.canvas.hit_test((50, 50)), upper)
            self.assertEqual(hit.call_count, 1)
            self.assertIsNone(self.canvas.hit_test((500, 350)))
            self.assertEqual(hit.call_count, 1)

    def test_eraser_uses_sparse_candidates_and_commits_once(self):
        objects = tuple(Stroke(((100+i*30, 100), (100+i*30, 200)), 3) for i in range(500))
        self.canvas.document.commit(objects, "Fixture")
        self.canvas.set_tool("Eraser")
        self.canvas.sync_scene()
        with patch.object(rendering, "visible_ink", wraps=rendering.visible_ink) as detail:
            QTest.mousePress(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(100, 150))
            self.assertLess(detail.call_count, 6)
        self.assertIs(self.canvas.document.objects, objects)
        self.assertEqual(set(self.canvas.scene.previews), {objects[0].id})
        QTest.mouseRelease(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(100, 160))
        self.assertEqual(self.canvas.document.index, 2)

    def test_transform_previews_only_selected_and_paints_dirty_regions(self):
        objects = tuple(Shape("Rectangle", (20+i*60, 60), (45+i*60, 90)) for i in range(100))
        self.canvas.document.commit(objects, "Fixture")
        self.canvas.set_tool("Select")
        self.canvas.set_selection({objects[0].id})
        APP.processEvents()
        records = self.canvas.scene.records.copy()
        QTest.mousePress(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(32, 75))
        with patch.object(self.canvas.scene, "after", side_effect=AssertionError("per-sample document copy")):
            with patch.object(self.canvas, "update", wraps=self.canvas.update) as repaint:
                QTest.mouseMove(self.canvas, QPoint(52, 85))
                regions = [call.args[0] for call in repaint.call_args_list]
                self.assertTrue(regions)
                self.assertTrue(all(isinstance(r, QRegion) and r.boundingRect().width() < 100 for r in regions))
        self.assertIs(self.canvas.document.objects, objects)
        self.assertEqual(set(self.canvas.scene.previews), {objects[0].id})
        self.assertIs(self.canvas.scene.record(objects[0].id).paint, records[objects[0].id].paint)
        for obj in objects[1:]:
            self.assertIs(self.canvas.scene.record(obj.id), records[obj.id])
        QTest.mouseRelease(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(52, 85))
        self.assertEqual(self.canvas.document.index, 2)
        APP.processEvents()

    def test_marquee_updates_do_not_repaint_document(self):
        objects = (Shape("Rectangle", (50, 50), (100, 100), 10),)
        self.canvas.document.commit(objects, "Fixture")
        self.canvas.set_tool("Select")
        APP.processEvents()
        QTest.mousePress(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(20, 20))
        with patch.object(self.canvas, "update", wraps=self.canvas.update) as repaint:
            QTest.mouseMove(self.canvas, QPoint(120, 120))
            self.assertEqual(repaint.call_count, 0)
        QTest.mouseRelease(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(120, 120))
        self.assertEqual(self.canvas.selected_ids, {objects[0].id})
        self.assertEqual(self.canvas.document.index, 1)

    def test_glass_preview_fills_dirty_interior_and_unchanged_geometry_does_not_repaint(self):
        overlay = PreviewOverlay(windows.Monitor("test", Rect(0, 0, 500, 400), 1))
        self.widgets.append(overlay)
        outline = Rect(20, 20, 340, 170)
        with patch.object(overlay, "update", wraps=overlay.update) as repaint:
            overlay.set_outline(outline)
            overlay.set_outline(outline)
            self.assertEqual(repaint.call_count, 1)
            self.assertTrue(repaint.call_args.args[0].contains(QPoint(100, 100)))
        overlay.show()
        image = overlay.grab().toImage()
        self.assertEqual(image.pixelColor(20, 20).alpha(), 0)
        self.assertEqual(image.pixelColor(100, 100).alpha(), 0)  # transparency-disabled fallback
        self.assertGreater(image.pixelColor(100, 21).alpha(), 0)

    def test_local_mask_geometry_cache_survives_transform_changes(self):
        from dataclasses import replace
        from mini_whiteboard.transforms import Erasure, translation
        obj = Stroke(((20, 100), (200, 100)), 6, erasures=(Erasure((80, 80), (80, 120), 8),))
        original = rendering.remaining_local(obj)
        moved = replace(obj, transform=translation(25, 30))
        self.assertIs(rendering.remaining_local(moved), original)

    def test_far_offscreen_selection_keeps_full_bounds_but_limits_overlay_surface(self):
        obj = Shape("Rectangle", (30, 40), (100000, 100000))
        self.canvas.document.add(obj)
        self.canvas.set_tool("Select")
        self.canvas.set_selection({obj.id})
        self.assertGreater(self.canvas.frame.width, 99000)
        overlay = self.canvas.tool_overlay
        self.assertLess(overlay.width(), self.canvas.width()+100)
        self.assertLess(overlay.height(), self.canvas.height()+100)

    def test_cached_preview_bounds_match_full_geometry_after_affine_transform(self):
        from dataclasses import replace
        from mini_whiteboard.transforms import Affine, Erasure, rotation, translation
        from mini_whiteboard.document import transformed
        from mini_whiteboard.scene import Scene
        objects = (Shape("Arrow", (20, 20), (140, 75), 7),
                   Stroke(((30, 80), (65, 40), (160, 90)), 6), Text((30, 40), "masked", 20))
        objects = tuple(replace(obj, erasures=(Erasure((65, 0), (65, 160), 6),)) for obj in objects)
        scene = Scene()
        scene.sync(objects)
        matrix = translation(45, 20) @ Affine(a=1.7, d=.6) @ rotation(25)
        for obj in objects:
            updated = transformed(obj, matrix)
            scene.preview(obj.id, updated, transform_only=True)
            record = scene.record(obj.id)
            self.assertEqual(record.bounds, rendering.bounds(updated))
            self.assertEqual(record.hit_bounds, rendering.interaction_bounds(updated))
            self.assertIs(record.paint, scene.records[obj.id].paint)
