"""Text dismissal through the visible proxy view, including queued callbacks."""
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt, QTimer
from PySide6.QtGui import QFocusEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMenu, QPushButton, QWidget

from tests.qt_case import APP
from tests.test_canvas import CanvasCase
from mini_whiteboard.document import Shape, Stroke, Text
from mini_whiteboard.transforms import Affine, Erasure, rotation, translation


class TextDismissalTests(CanvasCase):
    def settle(self):
        APP.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        APP.processEvents()

    def draft(self, text=""):
        self.canvas.set_tool("Text")
        self.canvas.set_selection(set())
        QTest.mouseClick(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(40, 40))
        self.settle()
        self.assertIsNotNone(self.canvas.editor)
        self.canvas.editor.setPlainText(text)
        self.settle()
        return self.canvas.editor, self.canvas.editor_overlay

    def outside(self, point=QPoint(40, 270), drag=False):
        overlay = self.canvas.editor_overlay
        self.assertTrue(overlay.isVisible())
        self.assertFalse(overlay.owns_mouse_event(overlay.viewport(),
                         self.mouse_event(QEvent.Type.MouseButtonPress, point)))
        QTest.mousePress(overlay.viewport(), Qt.MouseButton.LeftButton, pos=point)
        # Hiding the view changes the native release target to the canvas.
        if drag:
            QTest.mouseMove(self.canvas, point + QPoint(90, 20))
        QTest.mouseRelease(self.canvas, Qt.MouseButton.LeftButton,
                           pos=point + (QPoint(90, 20) if drag else QPoint()))
        self.settle()

    @staticmethod
    def mouse_event(kind, point):
        from PySide6.QtGui import QMouseEvent
        return QMouseEvent(kind, point.toPointF(), point.toPointF(),
                           Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                           Qt.KeyboardModifier.NoModifier)

    def test_blank_outside_overlay_click_discards_without_replacement(self):
        editor, overlay = self.draft()
        self.outside()
        self.assertIsNone(self.canvas.editor)
        self.assertIsNone(self.canvas.editor_overlay)
        self.assertEqual(self.canvas.document.objects, ())
        self.assertEqual(self.canvas.document.history, [])
        self.assertEqual(self.canvas.selected_ids, set())
        self.assertEqual(self.canvas.tool, "Text")
        QTest.mouseClick(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(80, 290))
        self.settle()
        self.assertIsNotNone(self.canvas.editor)
        self.assertIsNot(self.canvas.editor, editor)
        self.assertEqual(self.canvas.editing_object.position, (80, 290))

    def test_whitespace_draft_dismissal_keeps_history_and_redo(self):
        from mini_whiteboard.document import Stroke
        obj = Stroke(((20, 20), (30, 30)))
        self.canvas.document.add(obj)
        self.canvas.document.undo()
        history = list(self.canvas.document.history)
        self.draft(" \t\n  ")
        self.outside(drag=True)
        self.assertIsNone(self.canvas.editor)
        self.assertEqual(self.canvas.document.objects, ())
        self.assertEqual(self.canvas.document.history, history)
        self.assertEqual(self.canvas.document.index, 0)
        self.assertTrue(self.canvas.document.redo())
        self.assertEqual(self.canvas.document.objects, (obj,))

    def test_old_editor_signal_cannot_finish_a_new_session(self):
        from mini_whiteboard.document import Text
        old, _ = self.draft()
        # Both objects are still alive until the DeferredDelete event is handled.
        self.canvas.finish_editing()
        self.canvas.begin_editing(Text((70, 80)))
        current = self.canvas.editor
        old.committed.emit()
        old.commit_if_unfocused()
        self.assertIs(self.canvas.editor, current)
        self.settle()

    def test_existing_cleared_text_is_one_exact_undoable_deletion(self):
        obj = Text((40, 50), "original\n wrapped text", color="#f08020", layout_width=105,
                   transform=translation(30, 30) @ rotation(20) @ Affine(a=1.2, d=1.2),
                   erasures=(Erasure((50, 60), (60, 70), 3),))
        first, last = Stroke(((30, 20),)), Shape("Rectangle", (100, 100), (180, 140))
        before = (first, obj, last)
        self.canvas.document.commit(before, "Fixture")
        self.canvas.set_tool("Text")
        self.canvas.begin_editing(obj)
        self.canvas.editor.setPlainText(" \t\n")
        self.outside(QPoint(550, 350))
        self.assertIsNone(self.canvas.editor)
        self.assertEqual(self.canvas.document.objects, (first, last))
        self.assertEqual(self.canvas.document.index, 2)
        self.assertNotIn(obj.id, self.canvas.selected_ids)
        self.canvas.document.undo()
        self.assertEqual(self.canvas.document.objects, before)
        self.canvas.document.redo()
        self.assertEqual(self.canvas.document.objects, (first, last))

    def test_meaningful_outside_click_commits_and_deselects_without_replacement(self):
        editor, _ = self.draft("  words\t\n next  ")
        obj = self.canvas.editing_object
        self.outside()
        self.assertEqual(self.canvas.document.objects[0].text, "  words\t\n next  ")
        self.assertEqual(self.canvas.document.objects[0].id, obj.id)
        self.assertEqual(self.canvas.document.index, 1)
        self.assertIsNone(self.canvas.editor)
        self.assertEqual(self.canvas.selected_ids, set())
        self.assertIsNone(self.canvas.frame)
        QTest.mouseClick(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(40, 270))
        self.settle()
        self.assertEqual(self.canvas.editing_object.position, (40, 270))

    def test_dismissal_over_existing_text_requires_a_separate_click_to_edit(self):
        other = Text((40, 270), "other")
        self.canvas.document.add(other)
        self.draft("first")
        self.outside(QPoint(55, 280))
        self.assertIsNone(self.canvas.editor)
        self.assertEqual(self.canvas.selected_ids, set())
        QTest.mouseClick(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(55, 280))
        self.settle()
        self.assertEqual(self.canvas.editing_object, other)
        self.assertEqual(self.canvas.editor.toPlainText(), "other")
        self.assertEqual(len(self.canvas.document.objects), 2)

    def test_dismissal_press_move_release_never_starts_other_tools(self):
        for tool in ("Draw", "Shape", "Eraser", "Select", "Text"):
            with self.subTest(tool=tool):
                obj = Stroke(((40, 270), (200, 290)), width=10)
                from mini_whiteboard.document import Document
                self.canvas.document = Document()
                self.canvas.document.add(obj)
                self.draft()
                self.canvas.tool = tool  # Audit a tool transition during editing.
                self.outside(drag=True)
                self.assertIsNone(self.canvas.editor)
                self.assertIsNone(self.canvas.gesture)
                self.assertIsNone(self.canvas.preview)
                self.assertFalse(self.canvas.scene.previews)
                self.assertEqual(self.canvas.document.objects, (obj,))
                self.assertEqual(self.canvas.document.index, 1)
                self.assertIsNone(QWidget.mouseGrabber())

    def test_nonempty_draw_dismissal_does_not_draw_a_stray_dot(self):
        self.draft("text")
        self.canvas.tool = "Draw"
        self.outside(drag=True)
        self.assertIsNone(self.canvas.editor)
        self.assertIsNone(self.canvas.gesture)
        self.assertEqual(len(self.canvas.document.objects), 1)
        self.assertIsInstance(self.canvas.document.objects[0], Text)

    def test_nonempty_dismissal_cannot_start_a_transform_handle(self):
        obj = Text((80, 120), "word", size=28, layout_width=120)
        self.canvas.document.add(obj)
        self.canvas.set_tool("Text")
        self.canvas.begin_editing(obj)
        self.settle()
        handle = self.canvas.frame.rotation_handle()
        point = QPoint(round(handle[0]), round(handle[1]))
        self.outside(point, drag=True)
        self.assertEqual(self.canvas.document.objects[0], obj)
        self.assertEqual(self.canvas.document.index, 1)
        self.assertIsNone(self.canvas.editor)
        self.assertIsNone(self.canvas.frame)

    def test_repeated_fast_dismissals_leave_no_editors_or_history(self):
        from mini_whiteboard.text_editor import EditorOverlay
        for _ in range(12):
            self.draft(" \n")
            self.outside()
            self.assertIsNone(self.canvas.editor)
            self.assertEqual(self.canvas.findChildren(EditorOverlay), [])
            self.assertEqual(self.canvas.selected_ids, set())
        self.assertEqual(self.canvas.document.history, [])
        self.assertEqual(self.canvas.document.objects, ())

    def test_double_click_and_immediate_separate_click_do_not_replay_dismissal(self):
        self.draft()
        overlay = self.canvas.editor_overlay
        QTest.mouseDClick(overlay.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(40, 270))
        QTest.mouseRelease(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(40, 270))
        self.settle()
        self.assertIsNone(self.canvas.editor)
        QTest.mouseClick(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(80, 300))
        self.assertIsNotNone(self.canvas.editor)
        self.assertEqual(self.canvas.document.history, [])

    def test_queued_old_signal_and_retired_view_cannot_finish_replacement(self):
        old, overlay = self.draft("first")
        QTimer.singleShot(0, lambda: self.canvas.finish_editing(old))
        old.committed.emit()
        self.canvas.begin_editing(Text((80, 290)))
        new = self.canvas.editor
        # Retired viewport events can already be queued at the time of hiding.
        QTest.mouseClick(overlay.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(30, 270))
        old.committed.emit()
        self.settle()
        self.assertIs(self.canvas.editor, new)
        self.assertEqual([obj.text for obj in self.canvas.document.objects], ["first"])

    def test_native_style_double_click_retargeted_to_canvas_does_not_reopen_text(self):
        from mini_whiteboard.document import Text
        obj = Text((40, 270), 'target under outside click')
        self.canvas.document.add(obj)
        self.draft('commit this')
        overlay = self.canvas.editor_overlay
        QTest.mouseClick(overlay.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(45, 275))
        self.settle()
        self.assertIsNone(self.canvas.editor)
        QTest.mouseDClick(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(45, 275))
        QTest.mouseRelease(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(45, 275))
        self.settle()
        self.assertIsNone(self.canvas.editor)
        self.assertIsNone(self.canvas.gesture)
        self.assertEqual(self.canvas.selected_ids, set())

    def test_controls_and_other_boards_receive_one_click(self):
        self.draft()
        received = []
        self.board.minus.clicked.connect(lambda: received.append("minimize"))
        QTest.mouseClick(self.board.minus, Qt.MouseButton.LeftButton)
        self.settle()
        self.assertEqual(received, ["minimize"])
        self.assertFalse(self.board.isVisible())
        self.assertIsNone(self.canvas.editor)
        self.board.restore()
        self.board.activateWindow()
        self.canvas.setFocus()
        self.settle()
        self.draft("text")
        from mini_whiteboard.board import BoardWindow
        other = BoardWindow("Other test board")
        self.widgets.append(other)
        other.resize(500, 400)
        other.show()
        QTest.mouseClick(other.canvas, Qt.MouseButton.LeftButton, pos=QPoint(40, 50))
        self.settle()
        self.assertIsNone(self.canvas.editor)
        self.assertEqual([obj.text for obj in self.canvas.document.objects], ["text"])
        self.assertEqual(len(other.canvas.document.objects), 1)
        self.assertIsInstance(other.canvas.document.objects[0], Stroke)

    def test_external_widget_click_is_not_swallowed_or_focused_back(self):
        editor, _ = self.draft()
        other = QPushButton("External owned target")
        self.widgets.append(other)
        other.show()
        clicked = []
        other.clicked.connect(lambda: clicked.append(True))
        QTest.mouseClick(other, Qt.MouseButton.LeftButton)
        self.settle()
        self.assertEqual(clicked, [True])
        self.assertIsNone(self.canvas.editor)
        self.assertEqual(self.canvas.document.history, [])

    def test_native_editor_context_menu_retains_session(self):
        editor, _ = self.draft("copy this")
        menu = editor.createStandardContextMenu()
        menu.popup(editor.mapToGlobal(QPoint(10, 10)))
        self.settle()
        self.assertTrue(menu.isVisible())
        self.assertTrue(editor.popup_active())
        APP.sendEvent(editor, QFocusEvent(QEvent.Type.FocusOut, Qt.FocusReason.PopupFocusReason))
        self.settle()
        self.assertIs(self.canvas.editor, editor)
        menu.close()
        self.canvas.editor_overlay.activate_editor()
        self.settle()
        self.assertIs(self.canvas.editor, editor)

    def test_embedded_menu_outside_dismissal_does_not_replay_canvas_gesture(self):
        editor, overlay = self.draft("text")
        self.canvas.tool = "Draw"
        menu = editor.createStandardContextMenu()
        menu.popup(editor.mapToGlobal(QPoint(10, 10)))
        self.settle()
        self.assertTrue(menu.isVisible())
        QTest.mouseClick(overlay.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(550, 350))
        self.settle()
        self.assertFalse(menu.isVisible())
        self.assertIsNone(self.canvas.gesture)
        self.assertEqual(self.canvas.document.objects, ())
        self.assertIs(self.canvas.editor, editor)
        self.assertTrue(editor.hasFocus())

    def test_palette_outside_dismissal_does_not_start_a_canvas_gesture(self):
        self.canvas.set_tool("Draw")
        self.canvas.open_palette()
        palette = self.canvas.palette
        self.settle()
        self.assertTrue(palette.isVisible())
        # A real popup receives the outside press at coordinates beyond its bounds.
        point = QPoint(palette.width()+20, palette.height()+20)
        QTest.mouseClick(palette, Qt.MouseButton.LeftButton, pos=point)
        self.settle()
        self.assertIsNone(self.canvas.gesture)
        self.assertEqual(self.canvas.document.objects, ())
        self.assertIsNone(self.canvas.palette)
        QTest.mouseClick(self.canvas, Qt.MouseButton.LeftButton, pos=QPoint(100, 320))
        self.assertEqual(len(self.canvas.document.objects), 1)

    def test_escape_and_ctrl_enter_drop_only_blank_sessions(self):
        for text in ("", " \t\n", " keep \n whitespace "):
            for key, mod in ((Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier),
                             (Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)):
                from mini_whiteboard.document import Document
                self.canvas.document = Document()
                self.draft(text)
                count = self.canvas.document.index
                editor = self.canvas.editor
                QTest.keyClick(editor, key, mod)
                self.canvas.finish_editing(editor)  # Repeated finish is a no-op.
                self.settle()
                self.assertIsNone(self.canvas.editor)
                self.assertEqual(self.canvas.document.index, count + bool(text.strip()))
                if text.strip():
                    self.assertEqual(self.canvas.document.objects[-1].text, text)

    def test_transformed_panned_view_uses_viewport_hit_coordinates(self):
        obj = Text((10, 10), "tall text line\n"*80, layout_width=95,
                   transform=translation(140, 35) @ rotation(15) @ Affine(a=1.2, d=1.2))
        self.canvas.document.add(obj)
        self.canvas.begin_editing(obj)
        self.settle()
        overlay = self.canvas.editor_overlay
        self.assertNotEqual(overlay.mapToScene(QPoint(0, 0)).toPoint(), QPoint(0, 0))
        caret = overlay.proxy.mapToScene(self.canvas.editor.cursorRect().center().toPointF())
        inside = overlay.mapFromScene(caret)
        QTest.mouseClick(overlay.viewport(), Qt.MouseButton.LeftButton, pos=inside)
        self.settle()
        self.assertIs(self.canvas.editing_object, obj)
        self.assertEqual(self.canvas.document.index, 1)
        self.canvas.tool = "Draw"
        self.outside(QPoint(5, 5))
        self.assertIsNone(self.canvas.editor)
        self.assertEqual(self.canvas.document.objects, (obj,))

    def test_panned_text_dismissal_then_separate_canvas_click(self):
        obj = Text((10, 10), "wrapped line\n"*70, layout_width=95,
                   transform=translation(140, 35) @ rotation(15) @ Affine(a=1.2, d=1.2))
        self.canvas.document.add(obj)
        self.canvas.set_tool("Text")
        self.canvas.begin_editing(obj)
        self.settle()
        view = self.canvas.editor_overlay
        point = QPoint(600, 50)
        self.assertNotEqual(view.mapToScene(point).toPoint(), point)
        self.outside(point)
        self.assertEqual(self.canvas.document.objects, (obj,))
        self.assertIsNone(self.canvas.editor)
        self.assertEqual(self.canvas.selected_ids, set())
        QTest.mouseClick(self.canvas, Qt.MouseButton.LeftButton, pos=point)
        self.settle()
        self.assertEqual(self.canvas.editing_object.position, (600, 50))
        self.assertEqual(self.canvas.editor.toPlainText(), "")

    def test_resize_minimize_restore_and_close_clean_up_blank_sessions(self):
        self.draft(" \n")
        self.board.resize(760, 530)
        self.settle()
        self.assertEqual(self.canvas.editor_overlay.geometry(), self.canvas.rect())
        self.board.minimize_to_tray()
        self.settle()
        self.assertIsNone(self.canvas.editor)
        self.board.restore()
        self.canvas.begin_editing(Text((50, 70)))
        self.board.close()
        self.settle()
        self.assertIsNone(self.canvas.editor_overlay)
        self.assertEqual(self.canvas.document.history, [])
