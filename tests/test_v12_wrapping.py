"""One local layout width drives editor, glyphs, history and editable transfer."""
from dataclasses import replace
import json
from unittest.mock import patch
from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtTest import QTest
from tests.qt_case import APP
from tests.test_canvas import CanvasCase
from mini_whiteboard import clipboard, rendering
from mini_whiteboard.document import Text, transformed
from mini_whiteboard.settings import TEXT_DEFAULT_WIDTH, TEXT_MIN_WIDTH, TEXT_MARGIN
from mini_whiteboard.transforms import Affine, Erasure, rotation, translation


def lines(document):
    document.documentLayout().documentSize()
    block, result = document.begin(), []
    while block.isValid():
        layout = block.layout()
        result.append(tuple((layout.lineAt(i).textStart(), layout.lineAt(i).textLength(),
                             layout.lineAt(i).width()) for i in range(layout.lineCount())))
        block = block.next()
    return tuple(result)


class TextWrappingTests(CanvasCase):
    def test_text_hit_tolerance_work_is_bounded_by_box_not_glyph_count(self):
        obj = Text((20, 20), 'many wrapped glyph contours '*25, layout_width=160,
                   erasures=(Erasure((35, 20), (35, 800), 7),))
        original = rendering.stroked
        def checked(path, width):
            self.assertLess(path.elementCount(), 20, 'Hit tolerance expanded every glyph')
            return original(path, width)
        with patch.object(rendering, 'stroked', new=checked):
            hit = rendering.hit_path(obj)
        self.assertFalse(hit.contains(rendering.point((35, 40))))
        self.assertGreater(hit.boundingRect().height(), 200)

    def test_editor_and_committed_layout_match_for_words_urls_and_newlines(self):
        for text in ('one two three four five six '*12, 'https://example.com/'+'a'*200,
                     'First paragraph wraps with words '*6+'\nSecond\n\nlast'):
            for size in (14, 20, 28):
                with self.subTest(text=text[:20], size=size):
                    obj = Text((30, 40), text, size, layout_width=180)
                    self.canvas.begin_editing(obj)
                    APP.processEvents()
                    doc = rendering.text_document(text, size, obj.layout_width)
                    expected = lines(doc)
                    self.assertEqual(lines(self.canvas.editor.document()), expected)
                    self.assertGreater(sum(map(len, expected)), text.count('\n')+1)
                    self.canvas.finish_editing()
                    saved = self.canvas.document.get(obj.id)
                    self.assertEqual(saved.text, text)
                    self.canvas.begin_editing(saved)
                    APP.processEvents()
                    self.assertEqual(lines(self.canvas.editor.document()), expected)
                    self.canvas.finish_editing()

    def test_new_width_uses_right_margin_and_edge_minimum(self):
        self.canvas.set_tool('Text')
        for x in (40, self.canvas.width()-10):
            QTest.mouseClick(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(x, 160))
            self.assertEqual(self.canvas.editing_object.layout_width,
                             max(TEXT_MIN_WIDTH, self.canvas.width()-x-TEXT_MARGIN))
            self.canvas.finish_editing()

    def test_caret_stays_visible_for_tall_text_without_canvas_resizing(self):
        size = self.board.size()
        obj = Text((60, 60), '', layout_width=130)
        self.canvas.begin_editing(obj)
        text = ('long content and URL '+'x'*70+'\n')*15
        self.canvas.editor.insertPlainText(text)
        APP.processEvents()
        editor, overlay = self.canvas.editor, self.canvas.editor_overlay
        self.assertGreater(editor.height(), self.canvas.height())
        caret = overlay.proxy.mapRectToScene(QRectF(editor.cursorRect())).center()
        self.assertTrue(overlay.viewport().rect().contains(overlay.mapFromScene(caret)))
        self.assertEqual(self.board.size(), size)
        self.canvas.finish_editing()
        self.assertEqual(self.canvas.document.get(obj.id).text, text)

    def test_layout_cache_bounds_and_glyph_geometry_include_width(self):
        text = 'narrow wrapping must have several painted lines '*6
        wide = Text((20, 30), text, layout_width=500)
        narrow = replace(wide, layout_width=130)
        self.assertGreater(rendering.bounds(narrow).height(), rendering.bounds(wide).height())
        self.assertIsNot(rendering.text_document(text, 14, 500), rendering.text_document(text, 14, 130))
        self.assertLessEqual(rendering.bounds(narrow).right(), narrow.position[0]+narrow.layout_width)
        ink = rendering.local_ink(narrow)
        self.assertGreater(ink.boundingRect().height(), 50)

    def test_move_rotate_scale_preserve_local_line_breaks_and_masks(self):
        obj = Text((20, 20), 'text wraps at a stored width '*8, layout_width=160,
                   erasures=(Erasure((35, 20), (35, 400), 7),))
        matrix = translation(130, 80) @ rotation(27) @ Affine(a=1.5, d=1.5)
        updated = transformed(obj, matrix)
        self.assertEqual(updated.layout_width, obj.layout_width)
        self.assertEqual(updated.erasures, obj.erasures)
        self.assertEqual(lines(rendering.text_document(updated.text, updated.size, updated.layout_width)),
                         lines(rendering.text_document(obj.text, obj.size, obj.layout_width)))
        self.assertEqual(rendering.visible_ink(updated), rendering.qt_transform(matrix).map(rendering.remaining_local(obj)))
        for y in range(20, 180, 10):
            self.assertIsNone(rendering.hit_test([updated], matrix.map((35, y))))

    def test_wrapped_duplicate_clipboard_and_exact_history(self):
        obj = Text((20, 20), 'transfer wrapping '*20, layout_width=177)
        self.canvas.document.add(obj)
        self.canvas.set_selection({obj.id})
        self.canvas.duplicate_selection()
        duplicate = self.canvas.document.objects[-1]
        self.assertEqual(duplicate.layout_width, 177)
        self.assertNotEqual(duplicate.id, obj.id)
        final = self.canvas.document.objects
        self.canvas.document.undo()
        self.assertEqual(self.canvas.document.objects, (obj,))
        self.canvas.document.redo()
        self.assertIs(self.canvas.document.objects, final)
        payload = clipboard.encode(final, 'board')
        decoded, _, _ = clipboard.decode(payload)
        self.assertEqual(decoded, final)

    def test_legacy_clipboard_defaults_and_invalid_widths_rejected(self):
        payload = json.loads(clipboard.encode((Text((10, 10), 'old clipboard'),), 'b'))
        del payload['objects'][0]['layout_width']
        decoded, _, _ = clipboard.decode(json.dumps(payload).encode())
        self.assertEqual(decoded[0].layout_width, TEXT_DEFAULT_WIDTH)
        for value in (None, True, '160', 0, -1, 23, 100001, float('inf'), float('nan')):
            with self.subTest(value=value):
                payload['objects'][0]['layout_width'] = value
                with self.assertRaises(ValueError):
                    clipboard.decode(json.dumps(payload).encode())

    def test_window_resize_preserves_committed_text_width_and_content(self):
        obj = Text((30, 40), 'full retained text '*100, layout_width=190)
        self.canvas.document.add(obj)
        before, history = self.canvas.document.objects, self.canvas.document.index
        self.board.resize(300, 180)
        APP.processEvents()
        self.assertIs(self.canvas.document.objects, before)
        self.assertEqual(self.canvas.document.index, history)
        self.assertEqual(self.canvas.document.get(obj.id), obj)

    def test_wrapped_editor_owns_tool_keys_clipboard_and_undo(self):
        self.canvas.begin_editing(Text((30, 30), '', layout_width=90))
        editor = self.canvas.editor
        QTest.keyClicks(editor, 'A V E 12345 '*6)
        QTest.keyClick(editor, Qt.Key.Key_Return)
        QTest.keyClicks(editor, 'last')
        self.assertEqual(editor.toPlainText(), 'A V E 12345 '*6+'\nlast')
        QTest.keyClick(editor, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.canvas.document.index, 0)
        QTest.keyClick(editor, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClick(editor, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
        self.assertIsNone(self.canvas.editor)
        self.assertEqual(self.canvas.document.index, 1)
