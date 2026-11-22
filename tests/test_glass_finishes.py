from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest

from mini_whiteboard.appearance import DisplayPolicy, FROSTED, LIQUID, THEMES, surface
from mini_whiteboard.board import BoardWindow
from mini_whiteboard.clipboard import rendered_image
from mini_whiteboard.floating_tools import FloatingTools
from mini_whiteboard.images import from_image
from mini_whiteboard.snapping import SnapPreferences
from tests.fake_platform import fake_platform
from tests.qt_case import APP, QtCase, wait_until


class FinishTests(QtCase):
    def test_migration_and_restart_only_write_the_appearance_key(self):
        with TemporaryDirectory() as directory:
            path = str(Path(directory)/'prefs.ini')
            def open_prefs():
                return SnapPreferences(settings=QSettings(path, QSettings.Format.IniFormat))
            prefs = open_prefs()
            self.assertEqual(prefs.theme, 'White')
            prefs.settings.setValue('appearance/theme', 'Glass')
            prefs.settings.setValue('other/value', 87)
            prefs.settings.sync()
            migrated = open_prefs()
            self.assertEqual(migrated.theme, FROSTED)
            self.assertEqual(migrated.settings.value('appearance/theme'), FROSTED)
            for choice in THEMES:
                migrated.set_theme(choice)
                fresh = open_prefs()
                self.assertEqual(fresh.theme, choice)
                self.assertEqual(fresh.settings.value('other/value', type=int), 87)

    def test_live_material_for_old_and_new_boards_survives_runtime_fallback(self):
        platform, prefs = fake_platform(), SnapPreferences()
        boards = []
        with patch.object(platform.desktop, 'display_policy', return_value=DisplayPolicy()) as policy:
            def material(board):
                return board.appearance_theme if board.display_policy.transparency and prefs.theme != 'White' else False
            with patch.object(platform.desktop, 'apply_appearance', side_effect=material):
                for i in range(2):
                    board = BoardWindow(str(i), prefs, platform)
                    self.widgets.append(board)
                    board.show()
                    boards.append(board)
                    prefs.set_theme(LIQUID)
                self.assertTrue(all(b.native_glass == LIQUID for b in boards))
                policy.return_value = DisplayPolicy(transparency=False, motion=False)
                for b in boards:
                    b.refresh_appearance()
                    self.assertFalse(b.native_glass)
                    self.assertEqual(b.appearance_theme, LIQUID)
                policy.return_value = DisplayPolicy()
                for b in boards:
                    b.refresh_appearance()
                    self.assertEqual(b.native_glass, LIQUID)
                    self.assertEqual(b.canvas.document.history, [])

    def test_screenshot_image_clip_and_clipboard_survive_every_finish(self):
        prefs = SnapPreferences()
        board = BoardWindow('Screenshot', prefs, fake_platform(), screenshot=True)
        self.widgets.append(board)
        board.show()
        im = QImage(96, 64, QImage.Format.Format_RGB32)
        im.fill(Qt.GlobalColor.blue)
        obj = from_image(im, locked=True)
        board.canvas.document.add(obj)
        board.canvas.set_screenshot_background(obj)
        clip, pixels = board.canvas.background_clip(), rendered_image((obj,))
        for theme in THEMES:
            prefs.set_theme(theme)
            self.assertFalse(board.native_glass)
            self.assertEqual(board.canvas.background_clip(), clip)
            board.set_capture_suspended(True)
            self.assertTrue(board.minus.isHidden() and board.remove.isHidden())
            self.assertEqual(rendered_image(board.canvas.document.objects), pixels)
            board.set_capture_suspended(False)
            self.assertTrue(board.minus.isVisible() and board.remove.isVisible())

    def test_keyboard_toolbar_options_and_escape(self):
        prefs = SnapPreferences()
        board = BoardWindow('Keys', prefs, fake_platform())
        self.widgets.append(board)
        manager = FloatingTools(APP, prefs)
        self.addCleanup(manager.close)
        manager.add_board(board)
        prefs.set_floating_tools(True)
        board.show()
        board.activateWindow()
        board.canvas.setFocus()
        manager.activate(board)
        self.assertTrue(wait_until(lambda: manager.palette and manager.palette.isVisible(), 600))
        QTest.keyClick(board.canvas, Qt.Key.Key_F6)
        button = manager.palette.buttons['Draw']
        self.assertTrue(wait_until(button.hasFocus, 600))
        QTest.keyClick(button, Qt.Key.Key_Down)
        self.assertTrue(manager.options.isVisible())
        QTest.keyClick(manager.options, Qt.Key.Key_Escape)
        self.assertIsNone(manager.options)
        self.assertTrue(wait_until(board.canvas.hasFocus, 600))

    def test_frosted_fallback_uses_frosted_tint_and_accessibility_is_opaque(self):
        for popup in (False, True):
            self.assertEqual(surface(LIQUID, FROSTED, DisplayPolicy(), popup=popup),
                             surface(FROSTED, FROSTED, DisplayPolicy(), popup=popup))
            for theme in THEMES:
                for policy in (DisplayPolicy(high_contrast=True), DisplayPolicy(transparency=False)):
                    self.assertEqual(surface(theme, LIQUID, policy, popup=popup).alpha(), 255)
