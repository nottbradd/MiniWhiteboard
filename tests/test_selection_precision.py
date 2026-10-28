"""Pointer routing must prefer visible text over neighbouring empty layout space."""
from dataclasses import replace
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from tests.qt_case import APP
from tests.test_canvas import CanvasCase
from mini_whiteboard import rendering
from mini_whiteboard.document import Text, Shape, Document, transformed
from mini_whiteboard.transforms import rotation, translation, Erasure


def ink_point(obj):
    """A real integer pointer position inside shaped ink, away from frame handles."""
    ink = rendering.visible_ink(obj)
    bounds = ink.boundingRect()
    center = bounds.center()
    candidates = ((x, y) for y in range(int(bounds.top())+1, int(bounds.bottom()))
                  for x in range(int(bounds.left())+1, int(bounds.right())))
    return min((p for p in candidates if ink.contains(rendering.point(p))),
               key=lambda p: abs(p[0]-center.x())+abs(p[1]-center.y()))


class SelectionPrecisionTests(CanvasCase):
    def fixture(self, objects):
        self.canvas.cancel_interaction()
        self.canvas.document = Document()
        self.canvas.document.commit(tuple(objects), 'Fixture')
        self.canvas.set_tool('Select')
        self.canvas.set_selection(set())
        self.canvas.update()
        APP.processEvents()

    def test_adjacent_wide_textboxes_click_and_drag_in_both_creation_orders(self):
        left = Text((40, 100), 'Left note', layout_width=550)
        right = Text((245, 100), 'Right note', layout_width=320)
        target = ink_point(right)
        for objects in ((left, right), (right, left)):
            with self.subTest(order=[obj.text for obj in objects]):
                self.fixture(objects)
                QTest.mouseClick(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(*target))
                self.assertEqual(self.canvas.selected_ids, {right.id})
                self.canvas.set_selection(set())
                self.drag(target, (target[0]+40, target[1]+55))
                self.assertEqual(self.canvas.selected_ids, {right.id})
                self.assertEqual(self.canvas.document.get(left.id), left)
                self.assertEqual(self.canvas.document.get(right.id).transform, translation(40, 55))
                self.assertTrue(self.canvas.document.undo())
                self.assertEqual(self.canvas.document.objects, objects)

    def test_other_visible_object_inside_existing_selection_frame_owns_drag(self):
        frame = Shape('Rectangle', (30, 40), (550, 330), 2)
        note = Text((200, 150), 'Target note', layout_width=300)
        self.fixture((frame, note))
        self.canvas.set_selection({frame.id})
        target = ink_point(note)
        self.drag(target, (target[0]+35, target[1]+50))
        self.assertEqual(self.canvas.selected_ids, {note.id})
        self.assertEqual(self.canvas.document.get(frame.id), frame)
        self.assertEqual(self.canvas.document.get(note.id).transform, translation(35, 50))

    def test_multiline_transformed_text_does_not_claim_neighbouring_visible_ink(self):
        left = Text((30, 80), 'Left\nSecond line', layout_width=560)
        right = Text((245, 80), 'Target\nSecond note', layout_width=160)
        matrix = translation(45, 30) @ rotation(9)
        left, right = transformed(left, matrix), transformed(right, matrix)
        self.fixture((right, left))
        target = ink_point(right)
        QTest.mouseClick(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(*target))
        self.assertEqual(self.canvas.selected_ids, {right.id})

    def test_empty_wrapping_width_is_not_a_text_target(self):
        note = Text((40, 100), 'Short', layout_width=550)
        self.fixture((note,))
        QTest.mouseClick(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(400, 110))
        self.assertEqual(self.canvas.selected_ids, set())

    def test_true_overlapping_ink_uses_visible_order_and_excludes_locked_objects(self):
        bottom = Text((90, 110), 'Overlapping text', layout_width=320)
        top = replace(bottom, id='top', color='#e04444')
        target = ink_point(top)
        for objects in ((bottom, top), (top, bottom)):
            self.fixture(objects)
            QTest.mouseClick(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(*target))
            self.assertEqual(self.canvas.selected_ids, {objects[-1].id})
        self.fixture((bottom, replace(top, locked=True)))
        QTest.mouseClick(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(*target))
        self.assertEqual(self.canvas.selected_ids, {bottom.id})

    def test_shift_click_then_marquee_and_double_click_keep_input_rules(self):
        left, right = Text((30, 70), 'Left note', layout_width=550), Text((250, 70), 'Right note')
        self.fixture((right, left))
        for obj in (left, right):
            QTest.mouseClick(self.canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier,
                             QPoint(*ink_point(obj)))
        self.assertEqual(self.canvas.selected_ids, {left.id, right.id})
        self.canvas.set_selection(set())
        QTest.mouseDClick(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(*ink_point(right)))
        self.assertEqual(self.canvas.editing_object.id, right.id)
        QTest.mouseClick(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(*ink_point(left)))
        self.assertIsNone(self.canvas.editor)
        self.assertEqual(self.canvas.selected_ids, set())
        self.assertIsNone(self.canvas.gesture)

    def test_erased_text_does_not_win_over_surviving_neighbour(self):
        note = Text((70, 100), 'Target note', layout_width=320)
        target = ink_point(note)
        erased = replace(note, id='erased', erasures=(Erasure(target, target, 18),))
        self.fixture((note, erased))
        QTest.mouseClick(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(*target))
        self.assertEqual(self.canvas.selected_ids, {note.id})

    def test_thin_border_tolerance_and_empty_closed_shape_remain_easy_to_select(self):
        line = Shape('Line', (100, 100), (300, 100), 1)
        box = Shape('Rectangle', (100, 200), (300, 300), 1)
        self.fixture((line, box))
        for obj, target in ((line, (180, 104)), (box, (180, 245))):
            self.canvas.set_selection(set())
            QTest.mouseClick(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(*target))
            self.assertEqual(self.canvas.selected_ids, {obj.id})
