"""Screenshot pixels reach the boundary while small chrome stays out of output."""
from dataclasses import replace
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtTest import QTest
from tests.qt_case import APP, QtCase, wait_until
from tests.fake_platform import fake_platform
from mini_whiteboard.app import WhiteboardApplication
from mini_whiteboard.geometry import Rect
from mini_whiteboard import clipboard, images, rendering
from mini_whiteboard.document import Text
from mini_whiteboard.appearance import DisplayPolicy
from mini_whiteboard.settings import CONTROL_HIT_PADDING


class ScreenshotChromeTests(QtCase):
    def setUp(self):
        super().setUp()
        self.controller = WhiteboardApplication(APP, platform=fake_platform())
        self.addCleanup(self.controller.cleanup)

    def board(self, color='#191b20', size=(480, 260)):
        image = QImage(*size, QImage.Format.Format_RGB32)
        image.fill(QColor(color))
        painter = QPainter(image)
        painter.fillRect(100, 80, 60, 70, QColor('#5a89be'))
        painter.end()
        board = self.controller.create_screenshot_board(Rect(80, 90, *size), image)
        APP.processEvents()
        return board, image

    def test_screenshot_canvas_origin_ratio_and_pixels_under_controls(self):
        for theme in ('White', 'Glass'):
            self.controller.preferences.set_theme(theme)
            board, image = self.board()
            canvas = board.canvas
            canvas.feedback.stop()
            paper = board.paper_rect()
            self.assertEqual(canvas.x(), paper.x())
            self.assertEqual(canvas.y(), paper.y())
            self.assertEqual((canvas.width(), canvas.height()), (480, 260))
            obj = canvas.document.objects[0]
            self.assertEqual(images.decoded(obj.png), image)
            output = clipboard.rendered_image((obj,))
            self.assertEqual(output.copy(2, 2, image.width(), image.height()),
                             image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied))
            self.assertEqual(output.pixelColor(0, 0).alpha(), 0)
            cache = canvas.background_cache
            for p in (QPoint(200, 0), QPoint(0, 120), QPoint(479, 120), QPoint(200, 259),
                      board.remove.geometry().center()-canvas.pos()):
                self.assertEqual(cache.image.pixelColor(p).name(), image.pixelColor(p).name())
            # Cut-outs still protect annotation interaction without punching
            # a white rectangle through the screenshot itself.
            local = board.remove.geometry().center()-canvas.pos()
            self.assertFalse(canvas.valid_position((local.x(), local.y())))
            self.assertEqual(obj.transform.a, obj.transform.d)

    def test_small_capture_enlarges_uniformly_without_letterbox_gutters(self):
        board, image = self.board(size=(80, 160))
        canvas = board.canvas
        obj = canvas.document.objects[0]
        self.assertEqual(canvas.width()/canvas.height(), image.width()/image.height())
        self.assertGreaterEqual(canvas.width(), 160)
        self.assertGreaterEqual(canvas.height(), 100)
        self.assertEqual(obj.transform.a, obj.transform.d)
        self.assertEqual(images.decoded(obj.png), image)

    def test_small_controls_have_disjoint_padding_and_keep_lifecycle(self):
        board, _ = self.board(size=(160, 100))
        before = board.canvas.document.objects
        for button in (board.minus, board.remove):
            self.assertEqual(button.width()-2*CONTROL_HIT_PADDING, 20)
            self.assertEqual(button.height()-2*CONTROL_HIT_PADDING, 20)
            self.assertTrue(button.toolTip() and button.accessibleName())
            self.assertFalse(board.edges_at(QPointF(button.geometry().topLeft())))
        self.assertFalse(board.minus.geometry().intersects(board.remove.geometry()))
        QTest.mouseClick(board.minus, Qt.MouseButton.LeftButton)
        self.assertFalse(board.isVisible())
        self.assertEqual(board.canvas.document.objects, before)
        board.restore()
        QTest.mouseClick(board.remove, Qt.MouseButton.LeftButton)
        self.assertNotIn(board, self.controller.boards)

    def test_feedback_wraps_clicks_through_and_stops_on_hide_in_both_policies(self):
        board, _ = self.board(size=(160, 100))
        bubble = board.canvas.feedback
        for policy in (DisplayPolicy(), DisplayPolicy(transparency=False, motion=False), DisplayPolicy(high_contrast=True)):
            board.display_policy = policy
            bubble.show_message('Locked · right-click to unlock')
            self.assertTrue(board.canvas.rect().contains(bubble.geometry()))
            self.assertLess(bubble.height(), 65)
            self.assertTrue(bubble.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents))
            self.assertEqual(bubble.focusPolicy(), Qt.FocusPolicy.NoFocus)
            self.assertFalse(bubble.grab().isNull())
            bubble.hide()
            self.assertFalse(bubble.delay.isActive())
            self.assertEqual(bubble.fade.state(), bubble.fade.State.Stopped)
        bubble.show_message('Draw · 2 px')
        bubble.delay.setInterval(20)
        bubble.delay.start()
        self.assertTrue(wait_until(lambda: not bubble.isVisible(), 500))
        self.assertFalse(bubble.delay.isActive())

    def test_chrome_cache_is_bounded_and_idle_hover_do_not_resample(self):
        board, _ = self.board()
        board.display_policy = DisplayPolicy()
        button = board.remove
        button.grab()
        sample = button.chrome_sample
        self.assertLessEqual(sample.image.width(), 20*board.devicePixelRatioF()+1)
        builds, original = sample.builds, board.canvas.background_cache.builds
        for _ in range(5):
            button.setDown(not button.isDown())
            button.grab()
        self.assertEqual(sample.builds, builds)
        self.assertEqual(board.canvas.background_cache.builds, original)
        button.setDown(False)

    def test_chrome_samples_canvas_coordinates_after_board_movement(self):
        board, _ = self.board('#f3f5f8')
        board.display_policy = DisplayPolicy()
        for point in (QPoint(100, 120), QPoint(350, 240)):
            board.move(point)
            board.remove.grab()
            sample = board.remove.chrome_sample
            self.assertFalse(sample.dark)
            expected = board.remove.pos()-board.canvas.pos()+QPoint(2, 2)
            self.assertEqual(sample.key[1:3], (expected.x(), expected.y()))

    def test_pointer_routes_move_resize_and_text_in_full_screenshot_canvas(self):
        board, _ = self.board()
        canvas = board.canvas
        obj = Text((80, 100), 'Pointer aligned')
        canvas.document.add(obj)
        canvas.set_tool('Select')
        from tests.test_selection_precision import ink_point
        point = ink_point(obj)
        QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(*point))
        self.assertEqual(canvas.selected_ids, {obj.id})
        QTest.mouseDClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(*point))
        self.assertEqual(canvas.editing_object.id, obj.id)
        # The real editor has a one-pixel frame around the shared text layout.
        self.assertEqual(canvas.editor_overlay.proxy.mapToScene(QPointF(1, 1)).toPoint(), QPoint(*obj.position))
        canvas.finish_editing()
        canvas.set_selection(set())
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(200, 9))
        self.assertEqual(board._gesture[0], 'move')
        QTest.mouseRelease(board, Qt.MouseButton.LeftButton, pos=QPoint(200, 9))
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(2, 100))
        self.assertEqual(board._gesture[0], 'resize')
        QTest.mouseRelease(board, Qt.MouseButton.LeftButton, pos=QPoint(2, 100))
