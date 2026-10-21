from unittest.mock import patch
from PySide6.QtWidgets import QSystemTrayIcon

from tests.qt_case import APP, QtCase
from mini_whiteboard.app import WhiteboardApplication
from mini_whiteboard.document import Text
from mini_whiteboard.geometry import Rect
from mini_whiteboard.windows import HotkeyEvents, CREATE_HOTKEY, CAPTURE_HOTKEY


class FakeNativeHotkeys:
    def __init__(self, app):
        self.events = HotkeyEvents()
        self.registered = set()

    def start(self):
        self.registered.add(CREATE_HOTKEY)
        self.registered.add(CAPTURE_HOTKEY)

    def enable_escape(self):
        pass

    def disable_escape(self):
        pass

    def close(self):
        self.registered.clear()


class TrayTests(QtCase):
    def test_registry_restore_order_delete_and_cleanup(self):
        with patch("mini_whiteboard.windows.NativeHotkeys", FakeNativeHotkeys):
            controller = WhiteboardApplication(APP)
        try:
            self.assertEqual(controller.boards, [])
            controller.create_board(Rect(50, 50, 400, 300))
            controller.create_board(Rect(100, 100, 400, 300))
            a, b = controller.boards
            a.canvas.document.add(Text((20, 20), "keep me"))
            a.minimize_to_tray()
            b.minimize_to_tray()
            controller.rebuild_menu()
            boards_menu = next(action.menu() for action in controller.menu.actions() if action.text() == "Whiteboards")
            self.assertIn("Whiteboard 1 (minimised)", [action.text() for action in boards_menu.actions()])
            controller.tray_activated(QSystemTrayIcon.ActivationReason.DoubleClick)
            self.assertTrue(b.isVisible())
            self.assertFalse(a.isVisible())
            controller.restore_board(a)
            self.assertEqual(a.canvas.document.objects[0].text, "keep me")
            b.close()
            self.assertEqual(controller.boards, [a])
            a.close()
            self.assertEqual(controller.boards, [])
            self.assertTrue(controller.tray.isVisible())
            self.assertFalse(APP.quitOnLastWindowClosed())
        finally:
            controller.cleanup()
        self.assertEqual(controller.hotkeys.registered, set())
        self.assertFalse(controller.tray.isVisible())

    def test_hotkey_failure_shows_warning_and_can_retry(self):
        with patch("mini_whiteboard.windows.NativeHotkeys", FakeNativeHotkeys), \
             patch.object(FakeNativeHotkeys, "start", side_effect=OSError("in use")), \
             patch.object(WhiteboardApplication, 'notify') as warning:
            controller = WhiteboardApplication(APP)
            APP.processEvents()
            self.assertTrue(warning.called)
            self.assertIn('in use', warning.call_args[0][0])
            controller.rebuild_menu()
            self.assertIn("Retry global shortcut", [a.text() for a in controller.menu.actions()])
        controller.retry_hotkey()
        self.assertIn(CREATE_HOTKEY, controller.hotkeys.registered)
        controller.cleanup()
