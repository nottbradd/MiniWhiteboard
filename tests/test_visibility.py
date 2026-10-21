"""Hide All is a session visibility transaction, separate from document edits."""
from unittest.mock import patch

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from tests.qt_case import APP, QtCase
from tests.fake_platform import fake_platform
from mini_whiteboard.app import WhiteboardApplication
from mini_whiteboard.document import Text, Stroke
from mini_whiteboard.geometry import Rect
from mini_whiteboard.snapping import SnapPreferences
from mini_whiteboard.platform.base import HIDE_HOTKEY, CREATE_HOTKEY, CAPTURE_HOTKEY
from tests.test_platform import FakeCarbon
from mini_whiteboard.platform.macos.hotkeys import MacHotkeys


class VisibilityTests(QtCase):
    def setUp(self):
        super().setUp()
        self.platform = fake_platform()
        self.controller = WhiteboardApplication(APP, SnapPreferences(persist=False), self.platform)
        self.addCleanup(self.controller.cleanup)

    def board(self):
        board = self.controller.create_board(Rect(40, 50, 500, 340))
        APP.processEvents()
        return board

    def test_mixed_membership_new_boards_and_exact_state(self):
        a, b, minimized = self.board(), self.board(), self.board()
        minimized.minimize_to_tray()
        stroke = Stroke(((50, 60), (100, 120)))
        a.canvas.document.add(stroke)
        a.canvas.set_selection({stroke.id})
        before = (a.geometry(), a.canvas.document.objects, list(a.canvas.document.history), a.canvas.frame)
        self.controller.toggle_visibility()
        self.assertEqual(set(self.controller.hidden_batch), {a, b})
        self.assertTrue(all(not board.isVisible() for board in (a, b, minimized)))
        new = self.board()
        with patch.object(self.platform.desktop, 'focus_window', side_effect=AssertionError('focus stolen')):
            self.controller.toggle_visibility()
            APP.processEvents()
        self.assertTrue(a.isVisible() and b.isVisible() and new.isVisible())
        self.assertFalse(minimized.isVisible())
        self.assertEqual(before, (a.geometry(), a.canvas.document.objects, a.canvas.document.history, a.canvas.frame))
        self.assertFalse(a.activation_timer.isActive())
        self.assertFalse(a.canvas.suspended)
        self.assertEqual(self.controller.hidden_batch, [])

    def test_individual_restore_later_minimize_and_deleted_members(self):
        a, b, c = self.board(), self.board(), self.board()
        self.controller.toggle_visibility()
        self.controller.restore_board(a)
        a.minimize_to_tray()
        c.close()
        self.assertEqual(self.controller.hidden_batch, [b])
        self.controller.toggle_visibility()
        self.assertFalse(a.isVisible())
        self.assertTrue(b.isVisible())
        self.assertNotIn(c, self.controller.boards)
        self.controller.toggle_visibility()
        self.assertEqual(self.controller.hidden_batch, [b])

    def test_empty_or_manually_minimized_is_noop(self):
        self.controller.toggle_visibility()
        self.assertEqual(self.controller.hidden_batch, [])
        board = self.board()
        board.minimize_to_tray()
        self.controller.toggle_visibility()
        self.assertEqual(self.controller.hidden_batch, [])
        self.assertFalse(board.isVisible())

    def test_hide_commits_real_editor_but_discards_blank_and_cancels_gestures(self):
        a, b = self.board(), self.board()
        a.canvas.begin_editing(Text((20, 30)))
        a.canvas.editor.setPlainText('saved before hiding')
        b.canvas.begin_editing(Text((20, 30)))
        b.canvas.editor.setPlainText(' \n ')
        self.controller.placement.start_at((10, 10))
        self.controller.toggle_visibility()
        APP.processEvents()
        self.assertEqual(a.canvas.document.objects[0].text, 'saved before hiding')
        self.assertEqual(len(a.canvas.document.history), 1)
        self.assertEqual(b.canvas.document.objects, ())
        self.assertEqual(b.canvas.document.history, [])
        self.assertFalse(self.controller.placement.state.active)
        for board in (a, b):
            self.assertIsNone(board.canvas.editor)
            self.assertIsNone(board.canvas.gesture)
            self.assertFalse(board.activation_timer.isActive())
            self.assertFalse(board.canvas.help_panel.isVisible())
        self.controller.toggle_visibility()
        a.canvas.tool = 'Draw'
        QTest.mousePress(a.canvas, Qt.MouseButton.LeftButton, pos=QPoint(60, 70))
        QTest.mouseMove(a.canvas, QPoint(110, 100))
        self.assertIsNotNone(a.canvas.gesture)
        self.controller.toggle_visibility()
        self.assertIsNone(a.canvas.gesture)
        self.assertEqual(len(a.canvas.document.history), 1)


class DiscreteHotkeyTests(QtCase):
    def test_repeat_modifier_release_and_preset_change_cannot_retoggle(self):
        keys = MacHotkeys(APP, backend_factory=FakeCarbon)
        self.addCleanup(keys.close)
        keys.start()
        toggles = []
        keys.events.hide_toggle.connect(lambda: toggles.append(True))
        keys.backend.down.add(HIDE_HOTKEY)
        for _ in range(5):
            keys.deliver(HIDE_HOTKEY, True)
        keys.backend.modifiers_held = False
        keys.hide_latch.poll()
        keys.set_preset('alternate')
        keys.start()
        keys.deliver(HIDE_HOTKEY, True)
        self.assertEqual(toggles, [True])
        keys.backend.down.clear()
        keys.deliver(HIDE_HOTKEY, False)
        self.assertFalse(keys.hide_latch.timer.isActive())
        self.assertEqual(toggles, [True])
        keys.backend.down.add(HIDE_HOTKEY)
        keys.deliver(HIDE_HOTKEY, True)
        self.assertEqual(toggles, [True, True])

    def test_h_conflict_preserves_w_s_and_retry(self):
        keys = MacHotkeys(APP, backend_factory=FakeCarbon)
        self.addCleanup(keys.close)
        keys._ensure_backend()
        keys.backend.fail.add(HIDE_HOTKEY)
        with self.assertRaisesRegex(OSError, r'Control\+Option\+H'):
            keys.start()
        self.assertEqual(keys.registered, {CREATE_HOTKEY, CAPTURE_HOTKEY})
        keys.backend.fail.clear()
        keys.start()
        self.assertEqual(keys.registered, {CREATE_HOTKEY, CAPTURE_HOTKEY, HIDE_HOTKEY})
