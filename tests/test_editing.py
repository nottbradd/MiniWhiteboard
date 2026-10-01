from unittest.mock import patch

from PySide6.QtCore import QPoint, Qt, QEvent
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from tests.test_canvas import CanvasCase
from tests.qt_case import APP
from mini_whiteboard.document import Text, Shape, Stroke


class EditingTests(CanvasCase):
    # Reuse the real board fixture and input helpers, without inheriting tests.
    def test_text_copy_paste_selection_delete_and_click_outside_commit(self):
        self.canvas.begin_editing(Text((30, 40), "original"))
        editor = self.canvas.editor
        QTest.keyClick(editor, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClick(editor, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClick(editor, Qt.Key.Key_End)
        QTest.keyClick(editor, Qt.Key.Key_Return)
        QTest.keyClick(editor, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(editor.toPlainText(), "original\noriginal")
        QTest.keyClick(editor, Qt.Key.Key_Backspace)
        self.assertEqual(editor.toPlainText(), "original\norigina")
        QTest.mouseClick(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(400, 300))
        self.assertIsNone(self.canvas.editor)
        self.assertEqual(self.canvas.document.objects[0].text, "original\norigina")

    def test_shortcut_override_delivers_text_even_with_ancestor_action(self):
        from PySide6.QtGui import QAction
        action = QAction(self.board)
        action.setShortcut("D")
        self.board.addAction(action)
        triggered = []
        action.triggered.connect(lambda: triggered.append(True))
        self.canvas.begin_editing(Text((10, 10)))
        QTest.keyClicks(self.canvas.editor, "D123TSEV")
        self.assertEqual(self.canvas.editor.toPlainText(), "D123TSEV")
        self.assertEqual(triggered, [])

    def test_double_click_existing_text_does_not_leave_a_dot(self):
        obj = Text((50, 50), "editable")
        self.canvas.document.add(obj)
        self.key(Qt.Key.Key_D)
        QTest.mouseClick(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(65, 60))
        QTest.mouseDClick(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(65, 60))
        self.assertIsNotNone(self.canvas.editor)
        self.assertEqual(self.canvas.document.objects, (obj,))
        QTest.keyClick(self.canvas.editor, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClicks(self.canvas.editor, "changed")
        QTest.keyClick(self.canvas.editor, Qt.Key.Key_Escape)
        self.key(Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.canvas.document.objects, (obj,))

    def test_help_does_not_change_canvas_size_or_tool(self):
        size = self.canvas.size()
        self.key(Qt.Key.Key_F1)
        self.assertTrue(self.canvas.help_panel.isVisible())
        self.assertEqual(self.canvas.size(), size)
        self.key(Qt.Key.Key_F1)
        self.assertFalse(self.canvas.help_panel.isVisible())

    def test_minimize_retains_document_and_history_and_stops_feedback(self):
        obj = Stroke(((30, 40), (50, 60)))
        self.canvas.document.add(obj)
        self.canvas.show_feedback("Draw · 2")
        self.canvas.toggle_help()
        self.board.minimize_to_tray()
        self.assertFalse(self.canvas.feedback.delay.isActive())
        self.assertFalse(self.canvas.help_panel.isVisible())
        self.board.restore()
        APP.processEvents()
        self.assertEqual(self.canvas.document.objects, (obj,))
        # The offscreen platform cannot re-activate a hidden native tool window.
        # Actual restored focus + keyboard undo are covered by native_smoke.py.
        self.canvas.document.undo()
        self.assertEqual(self.canvas.document.objects, ())

    def test_inactive_board_ignores_tool_keys(self):
        other = QWidget()
        self.widgets.append(other)
        other.show()
        other.activateWindow()
        other.setFocus()
        APP.processEvents()
        QTest.keyClick(self.canvas, Qt.Key.Key_T)
        self.assertEqual(self.canvas.tool, "Draw")

    def test_cancel_eraser_drag_preserves_objects_and_undo(self):
        obj = Shape("Rectangle", (30, 30), (100, 100))
        self.canvas.document.add(obj)
        self.key(Qt.Key.Key_E)
        QTest.mousePress(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(30, 50))
        self.assertTrue(self.canvas.current_objects[0].erasures)
        self.key(Qt.Key.Key_Escape)
        QTest.mouseRelease(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(100, 50))
        self.assertEqual(self.canvas.document.objects, (obj,))
        self.assertEqual(self.canvas.document.index, 1)

    def test_committed_text_renders_dark_pixels_on_white_paper(self):
        self.canvas.document.add(Text((30, 30), "Visible text", 20))
        self.canvas.update()
        APP.processEvents()
        image = self.board.grab().toImage()
        origin = self.canvas.mapTo(self.board, QPoint(30, 30))
        dark = sum(1 for y in range(origin.y(), origin.y()+40)
                   for x in range(origin.x(), origin.x()+160)
                   if image.pixelColor(x, y).lightness() < 100)
        self.assertGreater(dark, 100)
