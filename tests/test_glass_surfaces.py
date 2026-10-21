"""Presentation geometry and typography stay separate from immutable artwork."""
from dataclasses import replace
from unittest.mock import patch
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QFont, QPainterPath
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel
from tests.qt_case import APP, QtCase
from tests.fake_platform import fake_platform
from mini_whiteboard.appearance import corner_radius, interface_font
from mini_whiteboard.board import BoardWindow
from mini_whiteboard.document import Text, Stroke
from mini_whiteboard import clipboard, rendering
from mini_whiteboard.shortcuts import ShortcutPolicy
from mini_whiteboard.snapping import SnapPreferences
from mini_whiteboard.surfaces import SurfaceMenu
from mini_whiteboard.transforms import Erasure, rotation, translation


class GlassSurfaceTests(QtCase):
    def board(self):
        prefs = SnapPreferences()
        platform = fake_platform()
        platform.shortcuts = ShortcutPolicy()
        board = BoardWindow('Surface',prefs,platform)
        self.widgets.append(board)
        board.resize(640,440)
        board.show()
        APP.processEvents()
        return board

    def test_theme_curvature_preserves_creation_clip_masks_text_and_history(self):
        board = self.board()
        canvas = board.canvas
        original_clip = canvas.clip_spec
        obj = Text((40,50),'Unicode 世界\nhttps://example.com/'+'wrap-'*40,
                   layout_width=210,clip=original_clip,erasures=(Erasure((70,80),(120,80),4),),
                   transform=translation(45,20) @ rotation(15))
        canvas.document.add(obj)
        before = canvas.document.objects,list(canvas.document.history),canvas.document.index
        pixels = clipboard.rendered_image(canvas.document.objects)
        board.canvas.preferences.set_theme('Glass')
        self.assertEqual(canvas.clip_spec.radius,32)
        self.assertEqual(original_clip.radius,12)
        self.assertIs(canvas.document.objects[0],obj)
        board.canvas.preferences.set_theme('White')
        self.assertEqual(before,(canvas.document.objects,canvas.document.history,canvas.document.index))
        self.assertEqual(pixels,clipboard.rendered_image(canvas.document.objects))

    def test_ui_font_roles_leave_document_and_editor_metrics_regular(self):
        board = self.board()
        text = 'Words wrap without changing layout.\n世界 · café 😀'
        before = rendering.text_document(text,14,210)
        font = before.defaultFont().toString()
        size = before.size()
        ink = rendering.text_ink(text,14,210)
        self.assertEqual(interface_font('heading').weight(),QFont.Weight.Bold)
        self.assertEqual(interface_font('action').weight(),QFont.Weight.Medium)
        self.assertEqual(interface_font('support').weight(),QFont.Weight.Normal)
        board.canvas.preferences.set_theme('Glass')
        board.canvas.begin_editing(Text((20,30),text,layout_width=210))
        self.assertEqual(board.canvas.editor.document().defaultFont().weight(),QFont.Weight.Normal)
        after = rendering.text_document(text,14,210)
        self.assertEqual((font,size,ink),(after.defaultFont().toString(),after.size(),rendering.text_ink(text,14,210)))

    def test_small_glass_board_clips_corners_and_keeps_control_centres_inside(self):
        board = self.board()
        board.canvas.preferences.set_theme('Glass')
        board.resize(160,100)
        path = QPainterPath()
        path.addRoundedRect(board.paper_rect(),board.corner_radius(),board.corner_radius())
        self.assertFalse(path.contains(board.paper_rect().topLeft()+QPointF(1,1)))
        for button in (board.minus,board.remove):
            self.assertTrue(path.contains(QPointF(button.geometry().center())))
        self.assertTrue(board.canvas.valid_position((80,40)))
        self.assertFalse(board.canvas.valid_position((0,board.canvas.height()-1)))
        self.assertLessEqual(corner_radius(board.paper_rect(),'Glass'),50)

    def test_menu_keyboard_navigation_and_material_cleanup(self):
        board = self.board()
        menu = SurfaceMenu(board.platform,board.canvas.preferences,board)
        self.widgets.append(menu)
        menu.add_heading('Appearance')
        called = []
        menu.addAction('White',lambda:called.append('White'))
        menu.addAction('Glass',lambda:called.append('Glass'))
        menu.popup(board.mapToGlobal(QPoint(300,50)))
        APP.processEvents()
        heading = menu.findChild(QLabel)
        self.assertEqual(heading.font().weight(),QFont.Weight.Bold)
        self.assertGreater(menu.height(),80)
        QTest.keyClick(menu,Qt.Key.Key_Down)
        QTest.keyClick(menu,Qt.Key.Key_Return)
        self.assertEqual(called,['White'])
        self.assertFalse(menu.isVisible())
        self.assertIsNone(getattr(menu,'_backdrop',None))

    def test_hide_closes_all_transient_surfaces_without_editor_shortcut_changes(self):
        board = self.board()
        canvas = board.canvas
        canvas.open_palette()
        palette = canvas.palette
        canvas.help_panel.show()
        canvas.context_menu = canvas.make_context_menu((150,140))
        canvas.context_menu.popup(board.mapToGlobal(QPoint(250,140)))
        context = canvas.context_menu
        board.prepare_hide()
        board.hide()
        for widget in (palette,canvas.help_panel,context):
            self.assertFalse(widget.isVisible())
            self.assertIsNone(getattr(widget,'_backdrop',None))
        self.assertFalse(canvas.feedback.delay.isActive())
        self.assertEqual(canvas.document.history,[])

    def test_transparent_popup_corners_dismiss_without_replaying_the_press(self):
        board = self.board()
        canvas = board.canvas
        canvas.set_tool('Text')
        canvas.open_palette()
        palette = canvas.palette
        QTest.mouseClick(palette,Qt.MouseButton.LeftButton,pos=QPoint(1,1))
        self.assertFalse(palette.isVisible())
        self.assertIsNone(canvas.editor)
        menu = canvas.make_context_menu((200,150))
        self.widgets.append(menu)
        menu.popup(board.mapToGlobal(QPoint(220,150)))
        APP.processEvents()
        QTest.mouseClick(menu,Qt.MouseButton.LeftButton,pos=QPoint(1,1))
        self.assertFalse(menu.isVisible())
        self.assertIsNone(canvas.editor)
        self.assertIsNone(canvas.gesture)
        self.assertEqual(canvas.document.history,[])
