"""Bounded material presentation and readable responsive temporary surfaces."""
from types import SimpleNamespace
from unittest.mock import patch
import time

from PySide6.QtCore import QAbstractAnimation, QPoint, QRect, Qt
from PySide6.QtTest import QTest
from tests.qt_case import APP, QtCase
from tests.fake_platform import fake_platform
from mini_whiteboard.appearance import ANIMATION_MS, DisplayPolicy
from mini_whiteboard.board import BoardWindow
from mini_whiteboard.document import Text
from mini_whiteboard.shortcuts import ShortcutPolicy
from mini_whiteboard.snapping import SnapPreferences
from mini_whiteboard.surfaces import SurfaceMenu


class PresentationTests(QtCase):
    def board(self, *, motion=True):
        platform = fake_platform()
        platform.shortcuts = ShortcutPolicy(hide_shortcut='shift')
        platform.desktop.display_policy = lambda: DisplayPolicy(motion=motion)
        prefs = SnapPreferences()
        prefs.set_theme('Glass')
        board = BoardWindow('Presentation', prefs, platform)
        self.widgets.append(board)
        board.resize(640, 440)
        return board

    def test_creation_restore_and_popups_follow_motion_without_changing_artwork(self):
        board = self.board()
        text = Text((30,40), 'Regular text stays fixed', layout_width=220)
        board.canvas.document.add(text)
        before = board.geometry(), board.canvas.document.objects, list(board.canvas.document.history)
        board.show()
        self.assertEqual(board.emphasis.animation.state(), QAbstractAnimation.State.Running)
        self.assertEqual(board.emphasis.value, 1)
        QTest.qWait(180)
        self.assertFalse(board.emphasis.deadline.isActive())
        board.prepare_hide()
        board.hide()
        board.restore(activate=False)
        self.assertEqual(board.emphasis.animation.state(), QAbstractAnimation.State.Running)
        self.assertEqual(board.emphasis.value, 1)
        menu = SurfaceMenu(board.platform, board.canvas.preferences, board)
        self.widgets.append(menu)
        menu.addAction('Action')
        menu.popup(board.mapToGlobal(QPoint(100,80)))
        self.assertTrue(menu.emphasis.deadline.isActive())
        menu.hide()
        self.assertFalse(menu.emphasis.deadline.isActive())
        QTest.qWait(180)
        self.assertEqual(before, (board.geometry(), board.canvas.document.objects, board.canvas.document.history))
        self.assertEqual(board.windowOpacity(), 1)
        self.assertFalse(board.activation_timer.isActive())

    def test_repeated_triggers_keep_the_original_deadline_and_load_does_not_extend_it(self):
        board = self.board()
        board.show()
        QTest.qWait(35)
        elapsed = board.emphasis.clock.elapsed()
        for _ in range(8):
            board.emphasis.start()
        self.assertGreaterEqual(board.emphasis.clock.elapsed(), elapsed)
        self.assertLessEqual(board.emphasis.deadline.remainingTime(), ANIMATION_MS-elapsed+2)
        time.sleep(.16)  # Simulate a busy GUI thread beyond the presentation budget.
        APP.processEvents()
        self.assertEqual(board.emphasis.animation.state(), QAbstractAnimation.State.Stopped)
        self.assertFalse(board.emphasis.deadline.isActive())
        self.assertEqual(board.emphasis.value, 0)

    def test_queued_creation_activation_preserves_an_immediately_started_editor(self):
        board = self.board(motion=False)
        board.show()
        board.activation_timer.start(0)
        board.canvas.begin_editing(Text((25,35),'Typed immediately'))
        editor = board.canvas.editor
        APP.processEvents()
        self.assertIs(board.canvas.editor,editor)
        self.assertTrue(editor.hasFocus())
        QTest.keyClicks(editor,' A V E 12345')
        self.assertEqual(editor.toPlainText(),'Typed immediately A V E 12345')
        self.assertEqual(board.canvas.tool,'Draw')
        self.assertEqual(board.canvas.document.history,[])

    def test_reduced_motion_and_obsolete_lifetimes_leave_no_presentation_timer(self):
        board = self.board(motion=False)
        board.show()
        self.assertFalse(board.emphasis.deadline.isActive())
        board.canvas.open_palette()
        palette = board.canvas.palette
        self.assertFalse(palette.emphasis.deadline.isActive())
        palette.close()
        board.desktop.display_policy = lambda: DisplayPolicy(motion=True)
        for _ in range(5):
            board.hide()
            board.show()
            board.canvas.open_palette()
            popup = board.canvas.palette
            self.assertTrue(popup.emphasis.deadline.isActive())
            board.canvas.preferences.set_theme('White')
            self.assertFalse(popup.isVisible())
            self.assertFalse(popup.emphasis.deadline.isActive())
            board.canvas.preferences.set_theme('Glass')
            board.prepare_hide()
            board.hide()
            self.assertFalse(board.emphasis.deadline.isActive())
        board.close()
        APP.processEvents()
        self.assertFalse(board.activation_timer.isActive())

    def test_help_reflows_with_readable_fonts_and_the_selected_global_shortcut(self):
        board = self.board(motion=False)
        board.show()
        panel = board.canvas.help_panel
        fonts = [label.font().toString() for label in panel.sections]
        for width,height,columns in ((1440,900,2),(800,500,1),(1152,650,2),(640,480,1)):
            screen = SimpleNamespace(availableGeometry=lambda:QRect(0,0,width,height))
            with patch.object(board,'screen',return_value=screen):
                panel.fit_reference()
                panel.show()
                APP.processEvents()
                self.assertEqual(panel.columns, columns)
                self.assertLessEqual(panel.height(),height-24)
                self.assertLessEqual(panel.width(),width-24)
                self.assertEqual(fonts, [label.font().toString() for label in panel.sections])
                self.assertTrue(all(label.height() >= label.heightForWidth(label.width()) for label in panel.sections))
                self.assertIn('Ctrl+Alt+Shift+H',' '.join(label.text() for label in panel.sections))
                if columns == 1:
                    self.assertGreater(panel.scroll.verticalScrollBar().maximum(),0)
                panel.hide()
        self.assertEqual(board.canvas.document.history, [])

    def test_checked_appearance_and_keyboard_focus_keep_native_actions(self):
        board = self.board(motion=False)
        board.show()
        menu = SurfaceMenu(board.platform, board.canvas.preferences, board)
        self.widgets.append(menu)
        menu.add_heading('Appearance')
        white, glass = menu.addAction('White'), menu.addAction('Glass')
        for action in (white,glass):
            action.setCheckable(True)
        glass.setChecked(True)
        menu.popup(board.mapToGlobal(QPoint(120,100)))
        APP.processEvents()
        self.assertGreaterEqual(menu.actionGeometry(glass).height(),38)
        self.assertGreaterEqual(menu.width(),220)
        menu.setActiveAction(glass)
        self.assertTrue(glass.isChecked())
        self.assertEqual(menu.activeAction(),glass)
        pixels = menu.grab().toImage()
        row = menu.actionGeometry(glass)
        blue = sum(pixels.pixelColor(x,y).blue()-pixels.pixelColor(x,y).red()>70
                   for x in range(row.right()-28,row.right()) for y in range(row.top(),row.bottom()))
        self.assertGreater(blue,12)  # Observable blue tick, not only the boolean action state.
        QTest.keyClick(menu,Qt.Key.Key_Up)
        self.assertEqual(menu.activeAction(),white)
        QTest.keyClick(menu,Qt.Key.Key_Escape)
        self.assertFalse(menu.isVisible())
        self.assertFalse(menu.emphasis.deadline.isActive())
