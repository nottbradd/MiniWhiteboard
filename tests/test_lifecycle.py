from unittest.mock import patch

from tests.qt_case import APP, QtCase
from mini_whiteboard.board import BoardWindow
from mini_whiteboard.geometry import Rect
from mini_whiteboard.placement import PlacementController
from mini_whiteboard.windows import HotkeyEvents


class FakeHotkeys:
    def __init__(self):
        self.events = HotkeyEvents()
        self.escape = False

    def enable_escape(self):
        self.escape = True

    def disable_escape(self):
        self.escape = False


class LifecycleTests(QtCase):
    def test_preview_cancel_and_confirm_cleanup(self):
        keys = FakeHotkeys()
        placement = PlacementController(keys)
        confirmed = []
        placement.confirmed.connect(confirmed.append)
        with patch("mini_whiteboard.windows.cursor_position", return_value=(50, 50)):
            placement.press()
        self.assertTrue(placement.timer.isActive())
        self.assertTrue(keys.escape)
        self.assertEqual(confirmed, [])
        with patch("mini_whiteboard.windows.cursor_position", return_value=(100, 100)):
            placement.press()
        self.assertTrue(placement.state.active)
        self.assertEqual(placement.state.anchor, (50, 50))
        with patch("mini_whiteboard.windows.cursor_position", return_value=(400, 250)):
            placement.release()
        self.assertEqual(confirmed, [Rect(50, 50, 350, 200)])
        self.assertEqual(placement.overlays, [])
        self.assertFalse(placement.timer.isActive())
        self.assertFalse(keys.escape)
        with patch("mini_whiteboard.windows.cursor_position", return_value=(10, 10)):
            placement.press()
        placement.cancel()
        self.assertFalse(placement.state.active)
        self.assertFalse(placement.timer.isActive())

    def test_escape_registration_failure_leaves_no_preview(self):
        keys = FakeHotkeys()
        placement = PlacementController(keys)
        errors = []
        placement.message.connect(errors.append)
        with patch.object(keys, "enable_escape", side_effect=OSError("busy")):
            placement.press()
        self.assertTrue(errors)
        self.assertFalse(placement.state.active)
        self.assertEqual(placement.overlays, [])

    def test_paper_bounds_and_minimize_restore_same_window(self):
        board = BoardWindow("Whiteboard 1")
        self.widgets.append(board)
        rect = Rect(30, 50, 350, 240)
        board.place(rect)
        APP.processEvents()
        self.assertEqual(board.physical_paper_rect(), rect)
        geometry = board.geometry()
        signals = []
        board.minimized.connect(signals.append)
        board.minimize_to_tray()
        self.assertFalse(board.isVisible())
        board.restore()
        self.assertTrue(board.isVisible())
        self.assertEqual(board.geometry(), geometry)
        self.assertEqual(signals, [board])

    def test_deleting_one_board_does_not_close_other(self):
        a, b = BoardWindow("A"), BoardWindow("B")
        self.widgets.extend([a, b])
        a.show()
        b.show()
        deleted = []
        a.deleted.connect(deleted.append)
        a.close()
        self.assertEqual(deleted, [a])
        self.assertTrue(b.isVisible())
        self.assertFalse(APP.quitOnLastWindowClosed())
