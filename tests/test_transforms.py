"""Selection and affine interaction checks, using real canvas mouse/key events."""
from dataclasses import replace
import math

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtTest import QTest

from tests.test_canvas import CanvasCase
from tests.qt_case import APP
from mini_whiteboard.document import Shape, Stroke, Text, transformed
from mini_whiteboard import rendering
from mini_whiteboard.transforms import (Affine, SelectionFrame, translation, rotation,
                                        around, resize_transform, rotate_transform)


def xy(p):
    return round(p[0]), round(p[1])


class SelectionTests(CanvasCase):
    def add(self, *objects):
        self.canvas.document.commit(objects, "Fixture")
        self.key(Qt.Key.Key_A)

    def click(self, p, shift=False):
        QTest.mouseClick(self.canvas, Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier,
                         QPoint(*p))

    def test_marquee_four_directions_contains_only_complete_objects(self):
        inside = Shape("Rectangle", (50, 50), (100, 100), 4)
        crossing = Stroke(((120, 80), (220, 80)), 8)
        text = Text((55, 120), "ok")
        self.add(inside, crossing, text)
        for start, end in [((30, 30), (190, 180)), ((190, 180), (30, 30)),
                           ((30, 180), (190, 30)), ((190, 30), (30, 180))]:
            with self.subTest(start=start):
                self.canvas.set_selection(set())
                self.drag(start, end)
                self.assertEqual(self.canvas.selected_ids, {inside.id, text.id})
        self.assertEqual(self.canvas.document.index, 1)

    def test_rendered_bounds_include_width_and_boundary_tolerance(self):
        obj = Stroke(((20, 50), (80, 50)), 10)
        self.assertEqual(rendering.bounds(obj), QRectF(15, 45, 70, 10))
        self.assertTrue(rendering.fully_contained(obj, QRectF(15, 45, 70, 10)))
        self.assertTrue(rendering.fully_contained(obj, QRectF(15.005, 45, 69.995, 10)))
        self.assertFalse(rendering.fully_contained(obj, QRectF(16, 45, 69, 10)))

    def test_transformed_and_off_viewport_containment(self):
        obj = transformed(Shape("Rectangle", (0, 0), (100, 30), 8),
                          translation(100, 100) @ rotation(35) @ Affine(a=2, d=.8))
        rect = rendering.bounds(obj)
        self.assertTrue(rendering.fully_contained(obj, rect))
        self.assertFalse(rendering.fully_contained(obj, rect.adjusted(0, 0, -1, 0)))
        outside = Stroke(((40, 50), (900, 50)), 4)
        self.add(outside)
        self.drag((10, 10), (600, 400))
        self.assertEqual(self.canvas.selected_ids, set())

    def test_alias_topmost_shift_click_and_shift_marquee(self):
        a = Shape("Rectangle", (40, 50), (130, 140))
        b = Shape("Ellipse", (60, 70), (150, 160))
        c = Stroke(((230, 70), (260, 90)), 4)
        self.add(a, b, c)
        self.click((90, 100))
        self.assertEqual(self.canvas.selected_ids, {b.id})
        self.key(Qt.Key.Key_V)
        self.assertEqual(self.canvas.selected_ids, {b.id})
        self.assertEqual(self.canvas.tool, "Select")
        self.click((45, 120), shift=True)
        self.assertEqual(self.canvas.selected_ids, {a.id, b.id})
        self.click((90, 100), shift=True)
        self.assertEqual(self.canvas.selected_ids, {a.id})
        self.drag((210, 50), (280, 110), Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual(self.canvas.selected_ids, {a.id, c.id})
        self.click((400, 300))
        self.assertFalse(self.canvas.selected_ids)
        self.assertEqual(self.canvas.document.index, 1)

    def test_shared_interior_move_preserves_spacing_order_and_exact_history(self):
        a = Shape("Rectangle", (30, 50), (90, 120))
        b = Text((220, 100), "text")
        self.add(a, b)
        self.canvas.set_selection({a.id, b.id})
        before = self.canvas.document.objects
        self.drag((160, 100), (200, 150))  # Empty space inside the shared frame.
        after = self.canvas.document.objects
        self.assertEqual([o.id for o in after], [a.id, b.id])
        for original, changed in zip(before, after):
            self.assertEqual(changed.transform, translation(40, 50))
        self.assertEqual(self.canvas.document.index, 2)
        self.key(Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.canvas.document.objects, before)
        self.key(Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.canvas.document.objects, after)

    def test_corner_group_resize_scales_geometry_spacing_and_pen(self):
        a = Stroke(((60, 60), (100, 100)), 6)
        b = Shape("Rectangle", (160, 80), (210, 160), 4)
        self.add(a, b)
        self.canvas.set_selection({a.id, b.id})
        frame = self.canvas.frame
        anchor = frame.handle(0)
        tip = frame.handle(4)
        self.drag(xy(tip), xy((2*tip[0]-anchor[0], 2*tip[1]-anchor[1])))
        for original, changed in zip((a, b), self.canvas.document.objects):
            self.assertAlmostEqual(changed.transform.scale, 2, delta=.015)
            mapped = changed.transform.map(anchor)
            self.assertAlmostEqual(mapped[0], anchor[0])
            self.assertAlmostEqual(mapped[1], anchor[1])
            self.assertEqual(changed.id, original.id)
            self.assertAlmostEqual(rendering.bounds(changed).width()/rendering.bounds(original).width(), 2, delta=.02)
        self.assertEqual(self.canvas.document.index, 2)

    def test_edges_nonuniform_without_text_uniform_with_text_and_shift(self):
        for include_text, shift in [(False, False), (False, True), (True, False)]:
            with self.subTest(text=include_text, shift=shift):
                objects = [Shape("Rectangle", (70, 70), (200, 170))]
                if include_text:
                    objects.append(Text((100, 100), "edit me"))
                self.add(*objects)
                self.canvas.set_selection(o.id for o in objects)
                frame = self.canvas.frame
                start = xy(frame.handle(3))
                self.drag(start, (start[0]+100, start[1]),
                          Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier)
                matrix = self.canvas.document.objects[0].transform
                self.assertGreater(matrix.a, 1)
                self.assertAlmostEqual(matrix.d, matrix.a if include_text or shift else 1)
                self.assertEqual(matrix.map(frame.handle(7)), frame.handle(7))

    def test_rotation_moves_every_object_about_shared_center(self):
        a = Stroke(((100, 100), (170, 130)), 4)
        b = Text((230, 140), "rotate")
        self.add(a, b)
        self.canvas.set_selection({a.id, b.id})
        frame = self.canvas.frame
        start = frame.rotation_handle()
        radius = frame.center[1]-start[1]
        target = (frame.center[0]+radius, frame.center[1])
        self.drag(xy(start), xy(target), Qt.KeyboardModifier.ShiftModifier)
        self.assertAlmostEqual(self.canvas.frame.angle, 90)
        expected = around(frame.center, rotation(90))
        for obj in self.canvas.document.objects:
            for actual, wanted in zip(obj.transform.map((0, 0)), expected.map((0, 0))):
                self.assertAlmostEqual(actual, wanted)
        # The oriented frame remains stable when a second gesture starts.
        angle = self.canvas.frame.angle
        p = xy(self.canvas.frame.center)
        self.drag(p, (p[0]+20, p[1]+20))
        self.assertAlmostEqual(self.canvas.frame.angle, angle)

    def test_transform_cancellation_restores_exact_snapshot_and_frame(self):
        obj = Shape("Rectangle", (80, 90), (200, 190))
        self.add(obj)
        for kind in ("move", "resize", "rotate"):
            with self.subTest(kind=kind):
                self.canvas.set_selection({obj.id})
                frame = self.canvas.frame
                start = frame.center if kind == "move" else frame.handle(4) if kind == "resize" else frame.rotation_handle()
                QTest.mousePress(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(*xy(start)))
                QTest.mouseMove(self.canvas, QPoint(round(start[0]+80), round(start[1]+60)))
                self.assertEqual(self.canvas.gesture, kind)
                self.key(Qt.Key.Key_Escape)
                QTest.mouseRelease(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(280, 250))
                self.assertEqual(self.canvas.document.objects, (obj,))
                self.assertEqual(self.canvas.frame, frame)
                self.assertEqual(self.canvas.document.index, 1)

    def test_multiple_samples_do_not_accumulate_transforms(self):
        obj = Shape("Rectangle", (80, 90), (200, 190))
        self.add(obj)
        self.canvas.set_selection({obj.id})
        QTest.mousePress(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(140, 140))
        for x in (170, 190, 200, 160):
            QTest.mouseMove(self.canvas, QPoint(x, 160))
        QTest.mouseRelease(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(160, 160))
        self.assertEqual(self.canvas.document.objects[0].transform, translation(20, 20))
        self.assertEqual(self.canvas.document.index, 2)

    def test_multidelete_one_action_and_no_selection_noop(self):
        objects = (Stroke(((50, 50), (80, 80))), Text((120, 60), "keep as text"))
        self.add(*objects)
        for key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.canvas.set_selection(o.id for o in objects)
            self.key(key)
            self.assertEqual(self.canvas.document.objects, ())
            self.assertFalse(self.canvas.selected_ids)
            self.assertTrue(self.board.isVisible())
            self.assertEqual(self.canvas.document.index, 2)
            self.key(key)
            self.assertEqual(self.canvas.document.index, 2)
            self.key(Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
            self.assertEqual(self.canvas.document.objects, objects)

    def test_small_shapes_no_mirroring_and_shift_snap(self):
        frame = SelectionFrame((100, 100), 100, 50, 20)
        matrix = resize_transform(frame, 4, frame.handle(4), frame.handle(0))
        resized = frame.transformed(matrix)
        self.assertGreaterEqual(resized.width, 1)
        self.assertGreaterEqual(resized.height, 1)
        self.assertGreater(matrix.a*matrix.d-matrix.b*matrix.c, 0)
        matrix = rotate_transform(frame, frame.rotation_handle(), (180, 155), True)
        angle = frame.transformed(matrix).angle
        self.assertAlmostEqual(angle/15, round(angle/15))

    def test_handle_size_and_hit_target_ignore_object_scale(self):
        frame = SelectionFrame((100, 100), 80, 40)
        for dpr in (1, 1.25, 1.5, 2):
            pts = rendering.handles(frame, dpr)
            self.assertAlmostEqual((pts[1].y()-pts[8].y())*dpr, 24)
            self.assertEqual(rendering.handle_at(frame, (pts[4].x()+8, pts[4].y()), dpr), 4)

    def test_shape_mode_endpoints_follow_object_transform(self):
        obj = transformed(Shape("Arrow", (0, 0), (100, 0)), translation(100, 100) @ rotation(30))
        self.add(obj)
        self.canvas.set_selection({obj.id})
        self.key(Qt.Key.Key_S)
        start = xy(obj.transform.map(obj.b))
        self.drag(start, (250, 180))
        result = self.canvas.document.objects[0]
        self.assertEqual(result.a, obj.a)
        for actual, wanted in zip(result.transform.map(result.b), (250, 180)):
            self.assertAlmostEqual(actual, wanted)
        self.assertIsNone(self.board._gesture)
