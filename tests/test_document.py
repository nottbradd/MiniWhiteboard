from dataclasses import replace
import unittest

from mini_whiteboard.document import Document, Shape, Stroke, Text, moved
from mini_whiteboard.geometry import constrained_end


class DocumentTests(unittest.TestCase):
    def test_actual_state_restored_including_order_and_ids(self):
        doc = Document()
        a, b = Stroke(((1, 2),)), Text((10, 20), "Today is day 123")
        doc.add(a)
        doc.add(b)
        doc.replace(moved(b, 40, 60), "Move")
        self.assertEqual(doc.get(b.id).transform.map(b.position), (50, 80))
        doc.undo()
        self.assertEqual(doc.objects, (a, b))
        doc.redo()
        doc.delete([a.id, b.id], "Erase")
        self.assertEqual(doc.objects, ())
        doc.undo()
        self.assertEqual([x.id for x in doc.objects], [a.id, b.id])

    def test_new_edit_discards_redo_and_noops_do_not_create_history(self):
        doc = Document()
        a = Shape("Rectangle", (0, 0), (100, 100))
        doc.add(a)
        self.assertFalse(doc.replace(a))
        self.assertEqual(len(doc.history), 1)
        doc.undo()
        doc.add(Text((1, 2), "replacement"))
        self.assertFalse(doc.redo())
        self.assertEqual(len(doc.objects), 1)

    def test_committed_text_and_font_changes(self):
        doc = Document()
        obj = Text((30, 40), "before")
        doc.add(obj)
        doc.replace(replace(obj, text="after\nmultiline"), "Edit text")
        doc.replace(replace(doc.get(obj.id), size=28), "Font size")
        doc.undo()
        self.assertEqual(doc.get(obj.id).size, 14)
        doc.undo()
        self.assertEqual(doc.get(obj.id), obj)

    def test_constraints(self):
        for kind in ["Rectangle", "Ellipse", "Triangle", "Diamond", "Rounded rectangle"]:
            self.assertEqual(constrained_end((0, 0), (-30, 50), kind, True), (-50, 50))
        x, y = constrained_end((0, 0), (100, 20), "Arrow", True)
        self.assertAlmostEqual(y, 0)
        self.assertGreater(x, 100)
