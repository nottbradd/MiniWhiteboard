"""Alpha coverage, theme controls and passive creation material regressions."""
import math
from unittest.mock import patch
from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath
from PySide6.QtTest import QTest
from tests.qt_case import APP, QtCase
from tests.fake_platform import fake_platform
from mini_whiteboard.alpha_clip import apply_mask, mask_image
from mini_whiteboard.appearance import DisplayPolicy, paint_preview
from mini_whiteboard.board import BoardWindow
from mini_whiteboard.document import Stroke, Text
from mini_whiteboard.geometry import Rect
from mini_whiteboard.placement import PlacementController, PreviewOverlay
from mini_whiteboard.screenshot import ScreenshotController
from mini_whiteboard.settings import CONTROL_GAP, CONTROL_HEIGHT, CONTROL_WIDTH
from mini_whiteboard.snapping import SnapPreferences
from mini_whiteboard.surfaces import SurfaceMenu


class SurfaceEdgeTests(QtCase):
    def board(self):
        board = BoardWindow('Edges', SnapPreferences(), fake_platform())
        self.widgets.append(board)
        board.resize(500, 320)
        board.show()
        APP.processEvents()
        return board

    def image(self, width, height, dpr=1):
        image = QImage(math.ceil(width*dpr), math.ceil(height*dpr), QImage.Format.Format_ARGB32_Premultiplied)
        image.setDevicePixelRatio(dpr)
        image.fill(Qt.GlobalColor.transparent)
        return image

    def test_all_four_corners_have_fractional_alpha_at_common_display_scales(self):
        path = QPainterPath()
        path.addRoundedRect(QRectF(2, 2, 160, 100), 32, 32)
        for dpr in (1, 1.25, 1.5, 1.75, 2):
            mask = mask_image(QSize(math.ceil(164*dpr), math.ceil(104*dpr)), dpr, path)
            image = self.image(164, 104, dpr)
            image.fill(QColor('white'))
            apply_mask(image, mask)
            for x,y in ((2,2),(130,2),(2,70),(130,70)):
                alphas = [image.pixelColor(px,py).alpha()
                          for py in range(math.ceil(y*dpr),math.floor((y+32)*dpr))
                          for px in range(math.ceil(x*dpr),math.floor((x+32)*dpr))]
                self.assertGreater(sum(0<a<255 for a in alphas), 10, (dpr,x,y))
            self.assertEqual(image.pixelColor(round(3*dpr), round(3*dpr)).alpha(), 0)
            self.assertEqual(image.pixelColor(round(80*dpr), round(50*dpr)).alpha(), 255)

    def test_board_canvas_and_temporary_surface_have_no_binary_visual_mask(self):
        board = self.board()
        for theme in ('White', 'Glass'):
            board.canvas.preferences.set_theme(theme)
            menu = SurfaceMenu(board.platform, board.canvas.preferences, board)
            self.widgets.append(menu)
            menu.addAction('A command')
            menu.popup(board.mapToGlobal(QPoint(90,45)))
            APP.processEvents()
            self.assertTrue(board.mask().isEmpty())
            self.assertTrue(board.canvas.mask().isEmpty())
            self.assertTrue(menu.mask().isEmpty())
            self.assertFalse(menu.contains_input(QPointF(1,1)))
            self.assertTrue(menu.contains_input(QPointF(menu.width()/2,menu.height()/2)))
            menu.close()

    def test_complete_button_rectangles_fit_minimum_board_in_both_themes(self):
        board = self.board()
        board.resize(160,100)
        for theme in ('White','Glass'):
            board.canvas.preferences.set_theme(theme)
            path=QPainterPath()
            path.addRoundedRect(board.paper_rect(),board.corner_radius(),board.corner_radius())
            for button in (board.minus,board.remove):
                self.assertEqual((button.width(),button.height()),(CONTROL_WIDTH,CONTROL_HEIGHT))
                rect=QRectF(button.geometry())
                for point in (rect.topLeft(),rect.topRight(),rect.bottomLeft(),rect.bottomRight()):
                    self.assertTrue(path.contains(point),(theme,point))
                self.assertTrue(button.toolTip())
                self.assertTrue(button.accessibleName())
                self.assertEqual(button.focusPolicy(),Qt.FocusPolicy.NoFocus)
            self.assertEqual(board.remove.x()-board.minus.x()-CONTROL_WIDTH,CONTROL_GAP)
            self.assertEqual(board.minus.y(),board.remove.y())

    def test_vector_controls_do_not_change_with_font_and_share_resting_surface(self):
        board=self.board()
        for theme in ('White','Glass'):
            board.canvas.preferences.set_theme(theme)
            QTest.mouseMove(board.canvas,QPoint(100,100));APP.processEvents()
            for button in (board.minus,board.remove):
                # Rasterise the explicit resting state independently of the
                # offscreen platform's process-global synthetic cursor cache.
                button.setAttribute(Qt.WidgetAttribute.WA_UnderMouse,False)
                original=button.grab().toImage()
                font=QFont('Symbol');font.setPointSize(72)
                button.setFont(font)
                self.assertEqual(button.grab().toImage(),original)
                self.assertEqual(button.text(),'')
            self.assertEqual(board.minus.grab().toImage().pixelColor(5,5),
                             board.remove.grab().toImage().pixelColor(5,5))

    def test_close_hover_and_press_use_red_without_changing_resting_dimensions(self):
        board=self.board()
        for theme in ('White','Glass'):
            board.canvas.preferences.set_theme(theme)
            button=board.remove
            QTest.mouseMove(board.canvas,QPoint(100,100));APP.processEvents()
            geometry=button.geometry()
            normal=button.grab().toImage().pixelColor(5,5)
            QTest.mouseMove(button,QPoint(10,10));APP.processEvents()
            hover=button.grab().toImage().pixelColor(5,5)
            QTest.mousePress(button,Qt.MouseButton.LeftButton,pos=QPoint(10,10))
            pressed=button.grab().toImage().pixelColor(5,5)
            self.assertGreater(hover.red()-hover.green(),normal.red()-normal.green())
            self.assertGreater(pressed.red()-pressed.green(),hover.red()-hover.green())
            self.assertEqual(button.geometry(),geometry)
            QTest.mouseRelease(button,Qt.MouseButton.LeftButton,pos=QPoint(-8,-8))
            self.assertTrue(board.isVisible())

    def test_preview_fill_is_lightweight_and_disabled_transparency_has_no_fill(self):
        for policy in (DisplayPolicy(),DisplayPolicy(transparency=False),DisplayPolicy(high_contrast=True)):
            image=self.image(360,220)
            painter=QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            paint_preview(painter,QRectF(10,10,340,200),False,policy)
            painter.end()
            centre=image.pixelColor(180,110).alpha()
            if policy.transparency and not policy.high_contrast:
                self.assertGreater(centre,0)
                self.assertLess(centre,110)
            else:
                self.assertEqual(centre,0)
            self.assertEqual(image.pixelColor(10,10).alpha(),0)
            self.assertGreater(image.pixelColor(180,11).alpha(),0)

    def test_preview_stationary_geometry_skips_material_work_and_removes_old_fill(self):
        platform=fake_platform()
        platform.desktop.display_policy=lambda:DisplayPolicy()
        overlay=PreviewOverlay(platform.desktop.screens[0],platform=platform)
        self.widgets.append(overlay)
        overlay.show()
        rect=Rect(20,20,340,200)
        with patch.object(platform.desktop,'apply_appearance',return_value=False) as apply:
            overlay.set_outline(rect)
            for _ in range(20):overlay.set_outline(rect)
            self.assertEqual(apply.call_count,1)
        APP.processEvents()
        self.assertGreater(overlay.grab().toImage().pixelColor(60,60).alpha(),0)
        overlay.set_outline(Rect(150,100,200,150));APP.processEvents()
        self.assertEqual(overlay.grab().toImage().pixelColor(60,60).alpha(),0)
        overlay.set_outline(None);APP.processEvents()
        self.assertEqual(overlay.grab().toImage().pixelColor(200,150).alpha(),0)

    def test_preview_material_is_released_before_capture_and_coordinates_are_unchanged(self):
        platform=fake_platform()
        live=set()
        def apply(widget):
            live.add(int(widget.winId()))
            return True
        def release(widget):live.discard(int(widget.winId()))
        platform.desktop.apply_appearance=apply
        platform.desktop.release_appearance=release
        keys=platform.create_hotkeys(APP)
        placement=PlacementController(keys,platform=platform)
        screenshot=ScreenshotController(keys,placement)
        self.addCleanup(placement.cancel);self.addCleanup(screenshot.cancel)
        for point in ((650,450),(-300,450),(650,-200),(-300,-200)):
            platform.desktop.cursor=(200,150)
            screenshot.start()
            screenshot.track(point)
            self.assertTrue(live)
            screenshot.finish(point)
            self.assertFalse(live)
            APP.processEvents()
            self.assertEqual(len(platform.capture.requests),1)
            request=platform.capture.requests.pop()
            self.assertEqual(request[0],Rect(min(200,point[0]),min(150,point[1]),abs(point[0]-200),abs(point[1]-150)))
            screenshot.cancel()
            self.assertFalse(screenshot.overlays)
            self.assertFalse(screenshot.tracking.isActive())

    def test_editor_alpha_clip_preserves_real_typing_and_document_undo_separation(self):
        board=self.board();canvas=board.canvas
        canvas.preferences.set_theme('Glass')
        canvas.document.add(Stroke(((60,70),(150,80)),4))
        before=tuple(canvas.document.history)
        canvas.begin_editing(Text((0,canvas.height()-35),'',layout_width=150))
        APP.processEvents()
        self.assertTrue(canvas.editor_overlay.clip_effect.isEnabled())
        QTest.keyClicks(canvas.editor,'A V E 12345')
        self.assertEqual(canvas.editor.toPlainText(),'A V E 12345')
        self.assertEqual(tuple(canvas.document.history),before)
        image=canvas.editor_overlay.grab().toImage()
        self.assertFalse(image.isNull())
        self.assertEqual(image.pixelColor(0,image.height()-1).alpha(),0)
        self.assertTrue(any(image.pixelColor(x,y).alpha() for y in range(image.height()-35,image.height()-3)
                            for x in range(15,120)))
        canvas.finish_editing()
        self.assertEqual(canvas.document.objects[-1].text,'A V E 12345')
        self.assertEqual(len(canvas.document.history),len(before)+1)

    def test_interior_editor_uses_direct_viewport_paint_until_content_reaches_a_boundary(self):
        board=self.board();canvas=board.canvas
        canvas.begin_editing(Text((50,60),'',layout_width=140))
        APP.processEvents()
        overlay=canvas.editor_overlay
        self.assertIs(overlay.viewport().graphicsEffect(),overlay.clip_effect)
        self.assertFalse(overlay.clip_effect.isEnabled())
        canvas.editor.setPlainText('A V E 12345\n' * 45)
        APP.processEvents()
        self.assertTrue(overlay.clip_effect.isEnabled())
        canvas.editor.setPlainText('Short again')
        overlay.horizontalScrollBar().setValue(0)
        overlay.verticalScrollBar().setValue(0)
        overlay.keep_caret_visible();APP.processEvents()
        self.assertFalse(overlay.clip_effect.isEnabled())

    def test_dpr_notification_refreshes_material_without_replacing_an_active_editor(self):
        board=self.board();canvas=board.canvas
        canvas.preferences.set_theme('Glass')
        canvas.begin_editing(Text((60,50),'Retain this session',layout_width=180))
        editor=canvas.editor
        before=(canvas.document.objects,list(canvas.document.history),canvas.clip_spec)
        with patch.object(board.desktop,'apply_appearance',return_value=False) as apply:
            APP.sendEvent(board,QEvent(QEvent.Type.DevicePixelRatioChange))
            self.assertEqual(apply.call_count,1)
        self.assertIs(canvas.editor,editor)
        self.assertEqual(before,(canvas.document.objects,canvas.document.history,canvas.clip_spec))
        self.assertTrue(canvas.mask().isEmpty())
