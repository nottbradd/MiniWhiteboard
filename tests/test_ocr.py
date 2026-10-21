from dataclasses import replace
from pathlib import Path
import sys
from threading import Event
import time
import unittest
from unittest.mock import patch

from tests.qt_case import APP, QtCase
from tests.fake_platform import fake_platform
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from mini_whiteboard.board import BoardWindow
from mini_whiteboard.document import Text
from mini_whiteboard.images import read_bytes, from_image
from mini_whiteboard.ocr import OcrService, Request, Result, run_worker
from mini_whiteboard.ocr_worker import recognize, validate_image
from mini_whiteboard.transforms import Affine, Erasure, rotation

FIXTURES = Path(__file__).parent / 'fixtures' / 'ocr'
EXPECTED = 'MINI WHITEBOARD\nMeeting 42: Ready!\nhttps://example.com/plan'


def fixture(name='clean'):
    return from_image(read_bytes((FIXTURES / (name + '.png')).read_bytes()), locked=True)


def until(predicate, seconds=3):
    deadline = time.monotonic() + seconds
    while not predicate() and time.monotonic() < deadline:
        APP.processEvents()
        QTest.qWait(10)
    return predicate()


class OcrTests(QtCase):
    def board(self, runner):
        self.service = OcrService(runner=runner)
        self.addCleanup(self.service.close)
        board = BoardWindow('OCR', platform=fake_platform())
        board.resize(650, 440)
        board.show()
        self.widgets.append(board)
        canvas = board.canvas
        canvas.ocr_service = self.service
        image = fixture()
        canvas.document.add(image)
        canvas.sync_scene()
        APP.processEvents()
        return board, canvas, image

    def test_result_review_copy_insert_and_exact_undo_without_source_changes(self):
        board, canvas, image = self.board(lambda job: Result(job.identifier, EXPECTED))
        APP.clipboard().setText('unchanged clipboard')
        before = canvas.document.objects
        menu = canvas.make_context_menu((10, 10))
        action = next(a for a in menu.actions() if a.text() == 'Extract Text…')
        action.trigger()
        panel = canvas.ocr_panel
        self.assertTrue(until(lambda: panel.ready))
        self.assertEqual(APP.clipboard().text(), 'unchanged clipboard')
        self.assertEqual(canvas.document.objects, before)
        panel.review.setPlainText(EXPECTED + '\nCorrected by user')
        QTest.mouseClick(panel.copy_button, Qt.MouseButton.LeftButton)
        self.assertEqual(APP.clipboard().text(), panel.review.toPlainText())
        QTest.mouseClick(panel.insert_button, Qt.MouseButton.LeftButton)
        after = canvas.document.objects
        self.assertIs(after[0], image)
        self.assertTrue(after[0].locked)
        self.assertIsInstance(after[1], Text)
        self.assertEqual(after[1].text, EXPECTED + '\nCorrected by user')
        self.assertIsNone(after[1].clip)
        self.assertLess(after[1].position[1], canvas.height())
        self.assertEqual(len(canvas.document.history), 2)
        canvas.document.undo()
        self.assertEqual(canvas.document.objects, before)
        canvas.document.redo()
        self.assertEqual(canvas.document.objects, after)

    def test_hide_cancels_and_late_result_cannot_open_or_copy(self):
        release = Event()
        def runner(job):
            release.wait(2)
            return Result(job.identifier, EXPECTED)
        board, canvas, image = self.board(runner)
        self.addCleanup(release.set)
        APP.clipboard().setText('keep')
        canvas.extract_text(image)
        panel = canvas.ocr_panel
        board.minimize_to_tray()
        release.set()
        self.assertTrue(until(lambda: not self.service.requests))
        self.assertIsNone(canvas.ocr_panel)
        self.assertFalse(board.isVisible())
        self.assertEqual(APP.clipboard().text(), 'keep')
        self.assertEqual(canvas.document.objects, (image,))

    def test_source_replacement_invalidates_even_if_result_is_late(self):
        release = Event()
        def runner(job):
            release.wait(2)
            return Result(job.identifier, 'old source')
        _, canvas, image = self.board(runner)
        self.addCleanup(release.set)
        canvas.extract_text(image)
        canvas.commit_edit((replace(image, transform=Affine(tx=50)),), 'Move image')
        self.assertIsNone(canvas.ocr_panel)
        release.set()
        self.assertTrue(until(lambda: not self.service.requests))
        self.assertEqual(len(canvas.document.objects), 1)

    def test_cancel_error_and_no_text_leave_document_and_clipboard_unchanged(self):
        for result_text, error in (('', ''), ('', 'OCR timed out.')):
            _, canvas, image = self.board(lambda job: Result(job.identifier, result_text, error))
            APP.clipboard().setText('keep')
            canvas.extract_text(image)
            panel = canvas.ocr_panel
            self.assertTrue(until(lambda: panel.ready))
            self.assertFalse(panel.copy_button.isEnabled())
            self.assertFalse(panel.insert_button.isEnabled())
            panel.close()
            self.assertEqual(canvas.document.objects, (image,))
            self.assertEqual(APP.clipboard().text(), 'keep')

    def test_bounded_queue_gui_heartbeat_lazy_start_and_shutdown(self):
        release = Event()
        def runner(job):
            while not release.wait(.01):
                if job.cancelled.is_set():
                    return Result(job.identifier)
            return Result(job.identifier, 'done')
        service = OcrService(runner=runner)
        delivered = []
        service.delivered.connect(delivered.append)
        self.addCleanup(service.close)
        self.assertIsNone(service.pool)
        image = fixture()
        a, b = service.submit(image), service.submit(image)
        with self.assertRaisesRegex(ValueError, 'busy'):
            service.submit(image)
        self.assertIs(service.requests[a].image, image)
        heartbeat = []
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, lambda: heartbeat.append(True))
        self.assertTrue(until(lambda: heartbeat))
        service.cancel(a)
        release.set()
        self.assertTrue(until(lambda: not service.requests))
        self.assertEqual([r.identifier for r in delivered], [b])
        service.close()
        self.assertIsNone(service.pool)
        with self.assertRaisesRegex(ValueError, 'shutting down'):
            service.submit(image)

    def test_input_limits_and_language_fail_before_loading_engine(self):
        with self.assertRaisesRegex(ValueError, '16 million'):
            validate_image(replace(fixture(), pixel_size=(5000, 5000)))
        with self.assertRaisesRegex(ValueError, 'English'):
            recognize(fixture(), 'fr')
        with self.assertRaisesRegex(ValueError, 'dimensions'):
            recognize(replace(fixture(), png=b'corrupt'))


@unittest.skipUnless(sys.platform in ('win32', 'darwin'), 'OCR supports Windows/macOS')
class RealEngineTests(QtCase):
    def test_exact_clean_multiline_punctuation_url_dark_and_transparent(self):
        for name in ('clean', 'dark', 'transparent'):
            with self.subTest(name=name):
                result = run_worker(Request(fixture(name)))
                self.assertEqual(result.error, '')
                self.assertEqual(result.text, EXPECTED)

    def test_display_transform_rectification_and_local_erasure(self):
        image = replace(fixture(), transform=rotation(38) @ Affine(a=.35, d=.35, tx=100))
        self.assertEqual(recognize(image), EXPECTED)
        masked = replace(image, erasures=(Erasure((0, 38), (1100, 38), 40),))
        self.assertEqual(recognize(masked), 'Meeting 42: Ready!\nhttps://example.com/plan')

    def test_timeout_stops_worker_and_next_request_recovers(self):
        result = run_worker(Request(fixture()), timeout=.001)
        self.assertIn('timed out', result.error)
        self.assertEqual(run_worker(Request(fixture())).text, EXPECTED)

    def test_blank_image_returns_no_text(self):
        from PySide6.QtGui import QImage
        image = QImage(400, 180, QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.white)
        result = run_worker(Request(from_image(image)))
        self.assertEqual((result.text, result.error), ('', ''))

    def test_missing_backend_or_english_data_is_an_error(self):
        if sys.platform == 'win32':
            from mini_whiteboard.platform.windows import ocr
            with patch.object(ocr, 'data_path', return_value=FIXTURES / 'missing'):
                with self.assertRaisesRegex(RuntimeError, 'Missing English'):
                    ocr.recognize_image(read_bytes((FIXTURES / 'clean.png').read_bytes()).convertToFormat(
                        __import__('PySide6.QtGui', fromlist=['QImage']).QImage.Format.Format_Grayscale8))
        else:
            from mini_whiteboard.platform.macos import ocr
            with patch.dict(sys.modules, {'Vision': None}):
                with self.assertRaises(ImportError):
                    ocr.recognize_image(None)
