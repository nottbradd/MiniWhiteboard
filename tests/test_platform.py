from pathlib import Path
import tempfile
from unittest.mock import patch

from PySide6.QtCore import QSettings
from PySide6.QtGui import QImage
from tests.qt_case import APP, QtCase
from tests.fake_platform import fake_platform
from mini_whiteboard.app import WhiteboardApplication
from mini_whiteboard.geometry import Rect
from mini_whiteboard.placement import PlacementController
from mini_whiteboard.screenshot import ScreenshotController
from mini_whiteboard.snapping import SnapPreferences
from mini_whiteboard.platform.base import CapturePermissionError, CREATE_HOTKEY, ESCAPE_HOTKEY, CAPTURE_HOTKEY
from mini_whiteboard.platform.capture_geometry import plan_capture
from mini_whiteboard.platform.macos.hotkeys import MacHotkeys
from mini_whiteboard.platform.macos.runtime import MacInstance


class PlatformTests(QtCase):
    def setUp(self):
        super().setUp()
        self.platform = fake_platform()

    def controllers(self):
        keys = self.platform.create_hotkeys(APP)
        placement = PlacementController(keys, platform=self.platform)
        capture = ScreenshotController(keys, placement)
        self.addCleanup(placement.cancel)
        self.addCleanup(capture.cancel)
        return keys, placement, capture

    def test_retina_placement_uses_points_not_backing_pixels(self):
        keys, placement, _ = self.controllers()
        confirmed = []
        placement.confirmed.connect(confirmed.append)
        keys.events.create.emit()
        self.platform.desktop.cursor = (200, 140)
        keys.events.create_released.emit()
        self.assertEqual(confirmed, [Rect(40, 40, 160, 100)])
        self.assertFalse(placement.timer.isActive())

    def test_preview_on_negative_monitor_uses_local_points(self):
        _, placement, _ = self.controllers()
        placement.start_at((-800, -50))
        local = placement.overlays[1].local_bounds(Rect(-800, -50, 400, 200))
        self.assertEqual((local.x(), local.y(), local.width(), local.height()), (400, 50, 400, 200))

    def test_async_capture_discards_cancelled_and_old_callbacks(self):
        keys, placement, capture = self.controllers()
        images = []
        capture.captured.connect(lambda r, i: images.append(i))
        capture.start()
        capture.anchor = (100, 100)
        capture.finish((500, 400))
        APP.processEvents()
        self.assertTrue(capture.pending)
        self.assertTrue(keys.escape)
        self.assertFalse(capture.overlays)
        old = self.platform.capture.requests[-1]
        placement.start_at((20, 20))
        self.assertTrue(capture.pending)  # The pending capture retains ownership.
        capture.cancel()
        self.assertFalse(capture.pending)
        old[1](QImage(8, 8, QImage.Format.Format_RGB32))
        old[2](OSError("late failure"))
        self.assertEqual(images, [])
        capture.start()
        capture.anchor = (100, 100)
        capture.finish((500, 400))
        APP.processEvents()
        self.platform.capture.requests[-1][1](QImage(8, 8, QImage.Format.Format_RGB32))
        APP.processEvents()
        self.assertEqual(len(images), 1)
        self.assertFalse(capture.active)
        self.assertFalse(keys.escape)

    def test_permission_denial_never_opens_overlay_or_board(self):
        _, _, capture = self.controllers()
        self.platform.capture.denial = CapturePermissionError("denied")
        errors, images = [], []
        capture.permission_required.connect(errors.append)
        capture.captured.connect(lambda *args: images.append(args))
        capture.start()
        self.platform.desktop.cursor = (500, 400)
        capture.release()
        APP.processEvents()
        self.assertEqual(errors, ["denied"])
        self.assertFalse(capture.active)
        self.assertFalse(images)

    def test_retina_screenshot_board_size_and_invalid_image(self):
        controller = WhiteboardApplication(APP, platform=self.platform)
        self.addCleanup(controller.cleanup)
        image = QImage(800, 500, QImage.Format.Format_RGB32)
        image.fill(0xff2277aa)
        board = controller.create_screenshot_board(Rect(100, 100, 400, 250), image)
        self.assertEqual(board.canvas.width(), 400)
        self.assertEqual(board.canvas.height(), 250)
        self.assertEqual(board.canvas.document.objects[0].transform.a, .5)
        with patch.object(controller, "notify"):
            self.assertIsNone(controller.create_screenshot_board(Rect(1, 1, 200, 200), QImage()))
        self.assertEqual(len(controller.boards), 1)

    def test_capture_plan_composes_negative_mixed_scale_displays(self):
        plan = plan_capture(Rect(-300, 50, 600, 200), self.platform.desktop.displays())
        self.assertEqual((plan.width, plan.height, plan.scale), (1200, 400, 2))
        retina, left = plan.pieces
        self.assertEqual(retina.source, Rect(0, 50, 300, 200))
        self.assertEqual(retina.pixels, (600, 400))
        self.assertEqual(retina.target, Rect(600, 0, 600, 400))
        self.assertEqual(left.source, Rect(900, 150, 300, 200))
        self.assertEqual(left.pixels, (300, 200))
        self.assertEqual(left.target, Rect(0, 0, 600, 400))

    def test_capture_plan_rejects_empty_offscreen_invalid_and_oversized(self):
        for rect in (Rect(0, 0, 0, 0), Rect(5000, 5000, 200, 200),
                     Rect(float("nan"), 0, 20, 20), Rect(-10000, -10000, 20000, 20000)):
            with self.assertRaises(ValueError):
                plan_capture(rect, self.platform.desktop.displays())

    def test_preferences_persist_shortcut_preset(self):
        with tempfile.TemporaryDirectory() as temp:
            settings = QSettings(str(Path(temp)/"preferences.ini"), QSettings.Format.IniFormat)
            a = SnapPreferences(settings=settings)
            a.set_shortcut_preset("alternate")
            a.set_grid(True)
            a.set_smart(False)
            b = SnapPreferences(settings=settings)
            self.assertEqual((b.shortcut_preset, b.grid_snap, b.smart_guides), ("alternate", True, False))
            with self.assertRaises(ValueError):
                b.set_shortcut_preset("invalid")

    def test_single_instance_lock_release_and_reacquire(self):
        with tempfile.TemporaryDirectory() as directory:
            first = MacInstance(directory)
            try:
                second = MacInstance(directory)
                self.assertTrue(first.acquired)
                self.assertFalse(second.acquired)
                second.close()
            finally:
                first.close()
            third = MacInstance(directory)
            self.assertTrue(third.acquired)
            third.close()

    def test_mac_labels_menu_and_preset_without_pin(self):
        controller = WhiteboardApplication(APP, platform=self.platform)
        self.addCleanup(controller.cleanup)
        controller.change_shortcut_preset("alternate")
        controller.rebuild_menu()
        self.assertEqual(controller.hotkeys.preset, "alternate")
        help_text = self.platform.shortcuts.help_html()
        self.assertIn("Command+Option+Shift+W", help_text)
        self.assertIn("Command+Shift+Z", help_text)
        self.assertNotIn("Ctrl+", help_text)
        self.assertNotIn("Pinned", [a.text() for a in controller.menu.actions()])
        self.assertEqual(controller.menu.actions()[-1].text(), "Quit Mini Whiteboard")


class FakeCarbon:
    def __init__(self, deliver):
        self.deliver = deliver
        self.active = {}
        self.fail = set()
        self.closed = False
        self.down = set()
        self.modifiers_held = True

    def sample(self, required):
        return self.down.copy(), self.down.copy() if self.modifiers_held else set()

    def clock(self):
        return 0

    def add(self, identifier, key, modifiers):
        if identifier in self.fail:
            raise OSError("conflict")
        if identifier in self.active:
            raise AssertionError("duplicate registration")
        self.active[identifier] = (key, modifiers)
        return identifier

    def discard(self, identifier):
        del self.active[identifier]

    def close(self):
        self.closed = True


class MacHotkeyTests(QtCase):
    def setUp(self):
        super().setUp()
        self.keys = MacHotkeys(APP, backend_factory=FakeCarbon)
        self.keys.start()
        self.addCleanup(self.keys.close)

    def test_release_confirms_once_and_repeat_is_ignored(self):
        platform = fake_platform()
        placement = PlacementController(self.keys, platform=platform)
        self.addCleanup(placement.cancel)
        rectangles = []
        placement.confirmed.connect(rectangles.append)
        self.keys.backend.down.add(CREATE_HOTKEY)
        self.keys.deliver(CREATE_HOTKEY, True)
        platform.desktop.cursor = (540, 340)
        self.keys.deliver(CREATE_HOTKEY, True)
        self.assertEqual(rectangles, [])
        self.keys.deliver(CREATE_HOTKEY, False)
        self.assertEqual(rectangles, [Rect(40, 40, 500, 300)])
        self.keys.deliver(CREATE_HOTKEY, True)
        self.assertFalse(placement.state.active)
        self.keys.backend.down.clear()
        self.keys.hold.poll()
        self.assertFalse(self.keys.hold.timer.isActive())

    def test_presets_registration_retry_and_cleanup(self):
        native = self.keys.backend
        self.keys.start()
        self.assertEqual(native.active[CREATE_HOTKEY], (13, 6144))
        self.keys.set_preset("alternate")
        native.fail.add(CAPTURE_HOTKEY)
        with self.assertRaisesRegex(OSError, "Command\\+Option\\+Shift\\+S"):
            self.keys.start()
        self.assertEqual(self.keys.registered, {CREATE_HOTKEY})
        native.fail.clear()
        self.keys.start()
        self.assertEqual(native.active[CREATE_HOTKEY], (13, 2816))
        self.keys.close()
        self.assertFalse(native.active)
        self.assertTrue(native.closed)

    def test_escape_temporary_registration_and_failure_notification(self):
        native = self.keys.backend
        native.fail.add(ESCAPE_HOTKEY)
        warnings = []
        self.keys.events.warning.connect(warnings.append)
        self.assertFalse(self.keys.enable_escape())
        self.assertIn("menu-bar", warnings[0])
        self.assertNotIn(ESCAPE_HOTKEY, native.active)
        native.fail.clear()
        self.assertTrue(self.keys.enable_escape())
        self.assertEqual(native.active[ESCAPE_HOTKEY], (53, 0))
        self.keys.disable_escape()
        self.assertNotIn(ESCAPE_HOTKEY, native.active)
