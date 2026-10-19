from dataclasses import replace
import math

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction
from PySide6.QtTest import QTest

from tests.test_canvas import CanvasCase
from tests.qt_case import APP
from mini_whiteboard.document import Text, Shape, transformed
from mini_whiteboard.transforms import Affine, Erasure, rotation, translation
from mini_whiteboard import rendering


class TransformedEditingTests(CanvasCase):
    def text_object(self):
        return transformed(Text((10, 10), "editable", 20),
                           translation(120, 100) @ rotation(25) @ Affine(a=1.5, d=1.5))

    def test_actual_focus_target_types_tool_keys_with_ancestor_shortcuts(self):
        obj = self.text_object()
        self.canvas.document.add(obj)
        self.canvas.begin_editing(obj)
        APP.processEvents()
        self.assertIsNotNone(self.canvas.editor)
        self.assertTrue(self.canvas.editor.hasFocus())
        target = APP.focusWidget()
        self.assertIsNotNone(target)
        triggered = []
        for key in ("A", "V", "E", "1", "2", "3", "4", "5"):
            action = QAction(self.board)
            action.setShortcut(key)
            action.triggered.connect(lambda: triggered.append(True))
            self.board.addAction(action)
        QTest.keyClick(target, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClicks(target, "A V E 12345")
        self.assertEqual(self.canvas.editor.toPlainText(), "A V E 12345")
        self.assertEqual(self.canvas.tool, "Draw")
        self.assertEqual(triggered, [])
        self.assertEqual(self.canvas.document.index, 1)
        QTest.keyClick(target, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.canvas.document.objects, (obj,))
        QTest.keyClick(target, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClick(target, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
        self.assertIsNone(self.canvas.editor)
        self.assertEqual(self.canvas.document.objects[0].text, "A V E 12345")
        self.assertEqual(self.canvas.document.objects[0].transform, obj.transform)
        self.key(Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.canvas.document.objects, (obj,))

    def test_delete_and_backspace_edit_text_without_deleting_objects(self):
        obj = self.text_object()
        self.canvas.document.add(obj)
        self.canvas.begin_editing(obj)
        APP.processEvents()
        target = APP.focusWidget()
        QTest.keyClick(target, Qt.Key.Key_Backspace)
        self.assertEqual(self.canvas.editor.toPlainText(), "editabl")
        QTest.keyClick(target, Qt.Key.Key_Home)
        QTest.keyClick(target, Qt.Key.Key_Delete)
        self.assertEqual(self.canvas.editor.toPlainText(), "ditabl")
        self.assertEqual(self.canvas.document.objects, (obj,))

    def test_font_presets_set_effective_size_for_all_selected_text(self):
        a, b = self.text_object(), transformed(Text((20, 20), "second"), translation(300, 60) @ Affine(a=2, d=2))
        shape = Shape("Rectangle", (50, 50), (100, 100))
        self.canvas.document.commit((a, b, shape), "Fixture")
        self.canvas.set_selection({a.id, b.id, shape.id})
        self.key(Qt.Key.Key_T)
        for key, size in ((1, 14), (2, 20), (3, 28)):
            before = self.canvas.document.objects
            self.key(Qt.Key.Key_0+key)
            for obj in self.canvas.document.objects[:2]:
                self.assertAlmostEqual(obj.size*obj.transform.scale, size)
            self.assertEqual(self.canvas.document.objects[2], shape)
            self.key(Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
            self.assertEqual(self.canvas.document.objects, before)

    def test_mask_stays_visible_during_rotated_edit_and_after_commit(self):
        mask = Erasure((55, 0), (55, 150), 9)
        obj = Text((10, 10), "MMMMM", 28, erasures=(mask,),
                   transform=translation(120, 90) @ rotation(20) @ Affine(a=1.2, d=1.2))
        self.canvas.document.add(obj)
        self.canvas.begin_editing(obj)
        APP.processEvents()
        image = self.canvas.grab().toImage()
        dpr = image.devicePixelRatio()
        for local_y in range(16, 45):
            p = obj.transform.map((55, local_y))
            self.assertGreater(image.pixelColor(round(p[0]*dpr), round(p[1]*dpr)).lightness(), 220)
        QTest.keyClicks(APP.focusWidget(), " A V E 12345")
        QTest.keyClick(APP.focusWidget(), Qt.Key.Key_Escape)
        self.assertIsNone(self.canvas.editor)
        updated = self.canvas.document.objects[0]
        self.assertEqual(updated.erasures, obj.erasures)
        self.assertEqual(updated.transform, obj.transform)
        for local_y in range(16, 45):
            self.assertIsNone(rendering.hit_test([updated], obj.transform.map((55, local_y))))

    def test_overlay_inside_click_and_outside_click_use_correct_coordinates(self):
        obj = self.text_object()
        self.canvas.document.add(obj)
        self.canvas.begin_editing(obj)
        APP.processEvents()
        overlay = self.canvas.editor_overlay
        inside = overlay.proxy.mapToScene(20, 15).toPoint()
        QTest.mouseClick(overlay.viewport(), Qt.MouseButton.LeftButton, pos=inside)
        APP.processEvents()
        self.assertIsNotNone(self.canvas.editor)
        QTest.mouseClick(overlay.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
        APP.processEvents()
        self.assertIsNone(self.canvas.editor)
        self.assertTrue(self.canvas.hasFocus())
        self.assertEqual(self.canvas.document.objects[0], obj)

    def test_glyph_bounds_cover_multiline_text_and_exclude_document_margin(self):
        a = Text((20, 20), "Text\nsecond line", 20)
        single = Text((20, 20), "Text", 20)
        self.assertGreater(rendering.bounds(a).height(), rendering.bounds(single).height())
        self.assertGreater(rendering.bounds(a).left(), a.position[0])
        self.assertTrue(rendering.text_bounds(a).contains(rendering.bounds(a)))
