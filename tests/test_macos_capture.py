"""Mocked ScreenCaptureKit protocol checks; these do not verify macOS itself."""
from types import SimpleNamespace
import subprocess
import sys
from unittest.mock import MagicMock, patch
from PySide6.QtGui import QImage, QColor
from tests.qt_case import APP, QtCase
from tests.fake_platform import FakeDesktop
from mini_whiteboard.geometry import Rect
from mini_whiteboard.platform.base import CapturePermissionError
from mini_whiteboard.platform.macos.capture import MacCapture, MacCaptureService


class MacCaptureTests(QtCase):
    def setUp(self):
        super().setUp()
        self.quartz = MagicMock()
        self.quartz.CGPreflightScreenCaptureAccess.return_value = True
        self.quartz.CGRectMake.side_effect = lambda *args: args
        self.sc = MagicMock()
        self.configurations = []
        def config():
            configuration = MagicMock()
            self.configurations.append(configuration)
            return configuration
        self.sc.SCStreamConfiguration.alloc.return_value.init.side_effect = config
        modules = patch.dict("sys.modules", {"Quartz": self.quartz, "ScreenCaptureKit": self.sc})
        modules.start()
        self.addCleanup(modules.stop)
        self.capture = MacCapture(FakeDesktop())
        self.addCleanup(self.capture.cancel)
        self.success, self.failure = [], []

    def test_platform_selection_does_not_construct_qobjects_before_application(self):
        code = """
from PySide6.QtCore import QCoreApplication
from unittest.mock import patch
from mini_whiteboard.platform.macos import create_platform
assert QCoreApplication.instance() is None
with patch('mini_whiteboard.platform.macos.capture.MacCapture', side_effect=AssertionError('early QObject')):
    platform = create_platform()
    platform.capture.cancel()
assert QCoreApplication.instance() is None
"""
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)

    def test_first_capture_use_creates_one_application_owned_dispatcher(self):
        service = MacCaptureService(FakeDesktop())
        self.addCleanup(service.cancel)
        self.assertIsNone(service._capture)
        service.prepare()
        capture = service._capture
        self.assertIs(capture.parent(), APP)
        service.prepare()
        self.assertIs(service._capture, capture)

    def start(self):
        self.capture.capture_region(Rect(-300, 50, 600, 200), self.success.append, self.failure.append, (99,))
        request = self.sc.SCShareableContent.getShareableContentExcludingDesktopWindows_onScreenWindowsOnly_completionHandler_
        content = SimpleNamespace(displays=lambda: [SimpleNamespace(displayID=lambda: 10), SimpleNamespace(displayID=lambda: 20)],
                                  windows=lambda: [SimpleNamespace(windowID=lambda: 99)])
        request.call_args.args[-1](content, None)
        APP.processEvents()
        return [call.args[-1] for call in self.sc.SCScreenshotManager.captureImageWithFilter_configuration_completionHandler_.call_args_list]

    def test_crop_configuration_and_cross_display_composition(self):
        callbacks = self.start()
        self.assertEqual(len(callbacks), 2)
        self.configurations[0].setSourceRect_.assert_called_once_with((0, 50, 300, 200))
        self.configurations[0].setWidth_.assert_called_once_with(600)
        self.configurations[1].setWidth_.assert_called_once_with(300)
        for configuration in self.configurations:
            configuration.setShowsCursor_.assert_called_once_with(False)
            configuration.setCapturesAudio_.assert_called_once_with(False)
        def tile(color):
            image = QImage(30, 20, QImage.Format.Format_RGB32)
            image.fill(QColor(color))
            return image
        with patch("mini_whiteboard.platform.macos.capture.image_from_cgimage", side_effect=tile):
            callbacks[1]("red", None)
            callbacks[0]("blue", None)
            APP.processEvents()
        self.assertFalse(self.failure)
        image = self.success[0]
        self.assertEqual((image.width(), image.height(), image.devicePixelRatio()), (1200, 400, 1))
        self.assertEqual(image.pixelColor(50, 50).name(), "#ff0000")
        self.assertEqual(image.pixelColor(650, 50).name(), "#0000ff")
        self.assertFalse(self.capture.timeout.isActive())

    def test_cancel_ignores_native_completion(self):
        callbacks = self.start()
        self.capture.cancel()
        callbacks[0](None, None)
        APP.processEvents()
        self.assertEqual((self.success, self.failure), ([], []))

    def test_permission_preflight_requests_screen_only_and_reports_denial(self):
        self.quartz.CGPreflightScreenCaptureAccess.return_value = False
        with self.assertRaises(CapturePermissionError):
            self.capture.prepare()
        self.quartz.CGRequestScreenCaptureAccess.assert_called_once_with()

    def test_timeout_fails_once_and_late_result_is_ignored(self):
        callbacks = self.start()
        self.capture.timeout.timeout.emit()
        self.assertEqual(len(self.failure), 1)
        callbacks[0](None, None)
        APP.processEvents()
        self.assertEqual(len(self.failure), 1)
        self.assertFalse(self.success)
