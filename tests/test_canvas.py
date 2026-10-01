from dataclasses import replace

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from tests.qt_case import APP, QtCase
from mini_whiteboard.board import BoardWindow
from mini_whiteboard.document import Shape, Stroke, Text
from mini_whiteboard import rendering
from mini_whiteboard.transforms import resize_transform


class CanvasCase(QtCase):
    def setUp(self):
        super().setUp()
        self.board = BoardWindow("Test")
        self.widgets.append(self.board)
        self.board.resize(700, 500)
        self.board.show()
        self.board.activateWindow()
        self.canvas = self.board.canvas
        # These regressions assert raw transform geometry; snapping has its own suite.
        self.canvas.preferences.smart_guides = False
        self.canvas.setFocus()
        APP.processEvents()

    def key(self, key, modifier=Qt.KeyboardModifier.NoModifier):
        QTest.keyClick(self.canvas, key, modifier)
        APP.processEvents()

    def drag(self, start, end, modifier=Qt.KeyboardModifier.NoModifier):
        QTest.mousePress(self.canvas, Qt.MouseButton.LeftButton, modifier, QPoint(*start))
        QTest.mouseMove(self.canvas, QPoint(*end))
        QTest.mouseRelease(self.canvas, Qt.MouseButton.LeftButton, modifier, QPoint(*end))
        APP.processEvents()


class CanvasTests(CanvasCase):
    def test_typing_tool_letters_numbers_and_editor_undo(self):
        self.key(Qt.Key.Key_T)
        QTest.mouseClick(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(30, 40))
        editor = self.canvas.editor
        QTest.keyClicks(editor, "Today is day 123")
        self.assertEqual(editor.toPlainText(), "Today is day 123")
        self.assertEqual(self.canvas.tool, "Text")
        self.assertEqual(self.canvas.font_key, 1)
        self.assertEqual(self.canvas.document.index, 0)
        QTest.keyClick(editor, Qt.Key.Key_Return)
        QTest.keyClicks(editor, "TDSVE 1234567")
        self.assertEqual(editor.toPlainText(), "Today is day 123\nTDSVE 1234567")
        QTest.keyClick(editor, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.canvas.document.index, 0)
        QTest.keyClick(editor, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClick(editor, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
        self.assertIsNone(self.canvas.editor)
        self.assertEqual(self.canvas.document.objects[0].text, "Today is day 123\nTDSVE 1234567")
        self.assertEqual(self.canvas.document.index, 1)
        self.key(Qt.Key.Key_3)
        self.assertEqual(self.canvas.document.objects[0].size, 28)
        self.key(Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.canvas.document.objects[0].size, 14)

    def test_empty_text_removed_and_escape_commits_nonempty(self):
        self.canvas.begin_editing(Text((10, 10)))
        QTest.keyClick(self.canvas.editor, Qt.Key.Key_Escape)
        self.assertEqual(self.canvas.document.objects, ())
        self.canvas.begin_editing(Text((10, 10)))
        QTest.keyClicks(self.canvas.editor, "hello")
        QTest.keyClick(self.canvas.editor, Qt.Key.Key_Escape)
        self.assertEqual(self.canvas.document.objects[0].text, "hello")

    def test_draw_dot_thickness_and_one_action_per_drag(self):
        QTest.mouseClick(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(40, 50))
        first = self.canvas.document.objects[0]
        self.assertIsInstance(first, Stroke)
        self.assertEqual(len(first.points), 1)
        self.key(Qt.Key.Key_5)
        self.drag((100, 100), (200, 180))
        self.assertEqual(len(self.canvas.document.history), 2)
        self.assertEqual(first.width, 2)
        self.assertEqual(self.canvas.document.objects[1].width, 14)

    def test_all_shapes_remain_objects_and_shift_constraints(self):
        self.key(Qt.Key.Key_S)
        for number in range(1, 8):
            self.canvas.selected_id = None
            self.key(Qt.Key.Key_0+number)
            self.drag((30, 40), (100, 160), Qt.KeyboardModifier.ShiftModifier)
            self.assertIsInstance(self.canvas.document.objects[-1], Shape)
        self.assertEqual(len(self.canvas.document.objects), 7)
        obj = self.canvas.document.objects[0]
        self.assertEqual(abs(obj.b[0]-obj.a[0]), abs(obj.b[1]-obj.a[1]))

    def test_select_topmost_move_and_resize_undo(self):
        a = Shape("Rectangle", (10, 10), (100, 100))
        b = Shape("Ellipse", (20, 20), (110, 110))
        self.canvas.document.add(a)
        self.canvas.document.add(b)
        self.key(Qt.Key.Key_V)
        self.drag((50, 50), (100, 90))
        self.assertEqual(self.canvas.selected_id, b.id)
        self.assertEqual(self.canvas.document.get(b.id).transform.map(b.a), (70, 60))
        self.key(Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.canvas.document.get(b.id), b)
        frame = self.canvas.frame
        self.drag((111, 111), (161, 181))
        resized = rendering.bounds(self.canvas.document.get(b.id))
        self.assertAlmostEqual(resized.width(), resized.height())
        self.assertGreater(resized.width(), frame.width)
        self.key(Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.canvas.document.get(b.id), b)

    def test_eraser_sweeps_between_samples_and_groups_undo(self):
        a = Stroke(((70, 20), (70, 100)))
        b = Stroke(((120, 20), (120, 100)))
        self.canvas.document.add(a)
        self.canvas.document.add(b)
        self.key(Qt.Key.Key_E)
        self.key(Qt.Key.Key_5)
        self.drag((20, 50), (180, 50))
        self.assertEqual(self.canvas.document.objects, ())
        self.assertEqual(len(self.canvas.document.history), 3)
        self.key(Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.canvas.document.objects, (a, b))

    def test_resize_window_does_not_transform_or_discard_document(self):
        obj = Text((500, 300), "outside small viewport")
        self.canvas.document.add(obj)
        self.board.resize(180, 120)
        self.board.resize(700, 500)
        self.assertEqual(self.canvas.document.objects, (obj,))

    def test_cancel_gesture_leaves_no_history(self):
        self.key(Qt.Key.Key_S)
        QTest.mousePress(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
        QTest.mouseMove(self.canvas, QPoint(100, 100))
        self.key(Qt.Key.Key_Escape)
        QTest.mouseRelease(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(100, 100))
        self.assertEqual(self.canvas.document.objects, ())
        self.assertEqual(self.canvas.document.index, 0)

    def test_text_has_shared_handles_and_thin_stroke_hit(self):
        self.assertEqual(len(rendering.handles(rendering.selection_frame([Text((10, 10), "test")]))), 9)
        stroke = Stroke(((10, 10), (100, 10)), 2)
        self.assertEqual(rendering.hit_test([stroke], (50, 14)), stroke)
        shape = Shape("Diamond", (0, 0), (100, 50))
        frame = rendering.selection_frame([shape])
        resized = frame.transformed(resize_transform(frame, 4, frame.handle(4), (200, 180), True))
        self.assertAlmostEqual(resized.width/resized.height, frame.width/frame.height)
