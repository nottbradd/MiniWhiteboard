"""Geometric and rendered-pixel checks for object-local swept erasure."""
from dataclasses import replace

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtTest import QTest

from tests.test_canvas import CanvasCase
from tests.qt_case import APP
from mini_whiteboard.document import Shape, Stroke, Text, transformed
from mini_whiteboard import rendering
from mini_whiteboard.transforms import Affine, Erasure, translation, rotation


def render(objects):
    image = QImage(500, 400, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    for obj in objects:
        rendering.paint_object(painter, obj)
    painter.end()
    return image


class ErasingTests(CanvasCase):
    def setup_eraser(self, *objects):
        self.canvas.document.commit(objects, "Fixture")
        self.key(Qt.Key.Key_E)

    def test_partial_stroke_cut_retains_both_fragments_and_original_identity(self):
        obj = Stroke(((40, 100), (240, 100)), 6)
        self.setup_eraser(obj)
        self.drag((140, 70), (140, 130))
        result = self.canvas.document.objects[0]
        self.assertEqual(result.id, obj.id)
        self.assertEqual(result.points, obj.points)
        self.assertTrue(result.erasures)
        ink = rendering.visible_ink(result)
        self.assertTrue(ink.contains(QPointF(60, 100)))
        self.assertTrue(ink.contains(QPointF(220, 100)))
        self.assertFalse(ink.contains(QPointF(140, 100)))
        self.assertIsNone(rendering.hit_test([result], (140, 100)))
        self.assertEqual(self.canvas.document.index, 2)
        self.key(Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.canvas.document.objects, (obj,))
        self.key(Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.canvas.document.objects, (result,))

    def test_pixels_outside_brush_are_unchanged_and_new_content_is_visible(self):
        obj = Stroke(((40, 100), (240, 100)), 8)
        self.setup_eraser(obj)
        before = render([obj])
        self.drag((140, 70), (140, 130))
        result = self.canvas.document.objects[0]
        after = render([result])
        for y in range(80, 121):
            for x in list(range(20, 130))+list(range(150, 260)):
                self.assertEqual(before.pixel(x, y), after.pixel(x, y))
        self.assertGreater(after.pixelColor(140, 100).lightness(), 240)
        fresh = Stroke(((140, 80), (140, 120)), 4)
        self.canvas.document.add(fresh)
        self.assertFalse(fresh.erasures)
        self.assertLess(render(self.canvas.document.objects).pixelColor(140, 100).lightness(), 100)

    def test_fast_sweep_erases_all_overlapping_objects_between_samples(self):
        objects = tuple(Stroke(((x, 60), (x, 150)), 2) for x in range(60, 260, 5))
        overlapping = Shape("Rectangle", (100, 60), (220, 150), 4)
        self.setup_eraser(*objects, overlapping)
        self.drag((20, 100), (300, 100))
        self.assertEqual(len(self.canvas.document.objects), len(objects)+1)
        for obj in self.canvas.document.objects:
            self.assertTrue(obj.erasures)
            self.assertFalse(rendering.visible_ink(obj).contains(QPointF(rendering.bounds(obj).center().x(), 100)))
        self.assertEqual(self.canvas.document.index, 2)

    def test_text_shape_outline_and_filled_arrowhead_partial_erase(self):
        for obj in (Text((60, 60), "MMMM", 28),
                    Shape("Rectangle", (50, 50), (190, 130), 8),
                    Shape("Arrow", (50, 80), (190, 80), 6)):
            with self.subTest(kind=type(obj).__name__):
                self.canvas.document = type(self.canvas.document)()
                self.setup_eraser(obj)
                r = rendering.bounds(obj)
                x = r.center().x() if not isinstance(obj, Shape) or obj.kind != "Arrow" else 180
                self.drag((round(x), round(r.top()-15)), (round(x), round(r.bottom()+15)))
                result = self.canvas.document.objects[0]
                self.assertIs(type(result), type(obj))
                self.assertTrue(result.erasures)
                self.assertFalse(rendering.visible_ink(result).intersects(rendering.swept_brush((x, r.top()), (x, r.bottom()), 10)))
                self.assertFalse(rendering.visible_ink(result).isEmpty())

    def test_erase_transformed_object_and_transform_mask_with_it(self):
        original = Stroke(((10, 10), (110, 10)), 10)
        matrix = translation(100, 100) @ rotation(35) @ Affine(a=2, d=.8)
        obj = transformed(original, matrix)
        self.setup_eraser(obj)
        center = matrix.map((60, 10))
        QTest.mouseClick(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(round(center[0]), round(center[1])))
        result = self.canvas.document.objects[0]
        self.assertFalse(rendering.hit_path(result).contains(QPointF(*center)))
        future = translation(25, 30) @ rotation(-20) @ Affine(a=.75, d=1.2)
        moved = transformed(result, future)
        self.assertEqual(moved.erasures, result.erasures)
        self.assertFalse(rendering.hit_path(moved).contains(QPointF(*future.map(center))))
        surviving = future.map(matrix.map((20, 10)))
        self.assertTrue(rendering.visible_ink(moved).contains(QPointF(*surviving)))

    def test_whole_stroke_removes_all_fragments_and_ignores_text_and_shapes(self):
        stroke = Stroke(((40, 100), (240, 100)), 6)
        shape = Shape("Rectangle", (35, 80), (250, 140), 6)
        text = Text((40, 90), "text")
        self.setup_eraser(stroke, shape, text)
        self.drag((140, 60), (140, 160))
        partial = self.canvas.document.objects
        self.key(Qt.Key.Key_5)
        self.drag((60, 85), (60, 125))
        self.assertIsNone(self.canvas.document.get(stroke.id))
        self.assertEqual(self.canvas.document.objects, partial[1:])
        self.key(Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.canvas.document.objects, partial)

    def test_whole_stroke_does_not_hit_already_erased_gap(self):
        obj = Stroke(((40, 100), (240, 100)), 4)
        self.setup_eraser(obj)
        self.key(Qt.Key.Key_4)
        self.drag((140, 80), (140, 120))
        partial = self.canvas.document.objects
        self.key(Qt.Key.Key_1)
        self.key(Qt.Key.Key_5)
        QTest.mouseClick(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(140, 100))
        self.assertEqual(self.canvas.document.objects, partial)
        self.assertEqual(self.canvas.document.index, 2)
        self.drag((20, 100), (260, 100))
        self.assertFalse(self.canvas.document.objects)

    def test_fully_erased_objects_removed_and_undo_restores_everything(self):
        objects = (Stroke(((90, 90),), 4), Shape("Ellipse", (85, 85), (95, 95)))
        self.setup_eraser(*objects)
        self.key(Qt.Key.Key_4)
        QTest.mouseClick(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(90, 90))
        self.assertEqual(self.canvas.document.objects, ())
        self.key(Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.canvas.document.objects, objects)

    def test_modes_sizes_cursor_and_per_board_memory(self):
        self.key(Qt.Key.Key_E)
        self.assertEqual((self.canvas.eraser_mode, self.canvas.eraser_diameter), ("circular", 16))
        for key, diameter in ((1, 8), (2, 16), (3, 32), (4, 64)):
            self.key(Qt.Key.Key_5)
            self.assertEqual(self.canvas.eraser_mode, "stroke")
            self.key(Qt.Key.Key_0+key)
            self.assertEqual((self.canvas.eraser_mode, self.canvas.eraser_diameter), ("circular", diameter))
        self.key(Qt.Key.Key_5)
        self.key(Qt.Key.Key_D)
        self.key(Qt.Key.Key_E)
        self.assertEqual((self.canvas.eraser_mode, self.canvas.eraser_diameter), ("stroke", 64))
        from mini_whiteboard.board import BoardWindow
        other = BoardWindow("Other")
        self.widgets.append(other)
        self.assertEqual((other.canvas.eraser_mode, other.canvas.eraser_diameter), ("circular", 16))
        QTest.mouseMove(self.canvas, QPoint(150, 120))
        self.assertIsNotNone(self.canvas.cursor_position)
        self.key(Qt.Key.Key_A)
        self.assertIsNone(self.canvas.cursor_position)

    def test_escape_restores_partial_and_whole_stroke_gestures(self):
        original = Stroke(((40, 100), (240, 100)), 8)
        mask = Erasure((100, 80), (100, 120), 8)
        obj = replace(original, erasures=(mask,))
        self.setup_eraser(obj)
        for key in (2, 5):
            self.key(Qt.Key.Key_0+key)
            QTest.mousePress(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(160, 100))
            QTest.mouseMove(self.canvas, QPoint(230, 100))
            self.assertNotEqual(self.canvas.current_objects, (obj,))
            self.key(Qt.Key.Key_Escape)
            QTest.mouseRelease(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(240, 100))
            self.assertEqual(self.canvas.document.objects, (obj,))
            self.assertEqual(self.canvas.document.index, 1)

    def test_marquee_uses_surviving_bounds_after_edge_erasure(self):
        obj = Stroke(((40, 100), (240, 100)), 4)
        self.setup_eraser(obj)
        self.key(Qt.Key.Key_4)
        self.drag((230, 70), (300, 130))
        result = self.canvas.document.objects[0]
        self.assertLess(rendering.bounds(result).right(), rendering.bounds(obj).right())
        self.assertTrue(rendering.fully_contained(result, rendering.bounds(result)))
        self.assertFalse(rendering.fully_contained(obj, rendering.bounds(result)))

    def test_eraser_double_click_does_not_open_text_editor(self):
        obj = Text((50, 50), "erase this text", 28)
        self.setup_eraser(obj)
        QTest.mouseDClick(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(80, 70))
        QTest.mouseRelease(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(80, 70))
        self.assertIsNone(self.canvas.editor)
        self.assertTrue(self.canvas.document.objects[0].erasures)
