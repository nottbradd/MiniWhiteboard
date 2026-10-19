"""Hold ownership and cleanup, independent of physical desktop input."""
from unittest.mock import patch
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QImage, QKeyEvent
from tests.qt_case import APP, QtCase
from tests.fake_platform import fake_platform
from tests.test_platform import FakeCarbon
from mini_whiteboard.geometry import Rect
from mini_whiteboard.placement import PlacementController
from mini_whiteboard.screenshot import ScreenshotController
from mini_whiteboard.platform.base import CREATE_HOTKEY as W, CAPTURE_HOTKEY as S, CapturePermissionError
from mini_whiteboard.platform.hold import HoldTracker
from mini_whiteboard.platform.macos.hotkeys import MacHotkeys


class HoldGestureTests(QtCase):
    def setUp(self):
        super().setUp()
        self.platform = fake_platform()
        self.keys = self.platform.create_hotkeys(APP)
        self.placement = PlacementController(self.keys, platform=self.platform)
        self.capture = ScreenshotController(self.keys, self.placement)
        self.down, self.complete = set(), set()
        self.tracker = HoldTracker(APP, self.keys.events, lambda: (self.down.copy(), self.complete.copy()))
        self.rects, self.images, self.messages = [], [], []
        self.placement.confirmed.connect(self.rects.append)
        self.capture.captured.connect(lambda r, i: self.images.append((r, i)))
        self.capture.message.connect(self.messages.append)
        self.addCleanup(self.placement.cancel)
        self.addCleanup(self.capture.cancel)
        self.addCleanup(self.tracker.close)

    def begin(self, identifier=W, point=(-400, -200)):
        self.platform.desktop.cursor = point
        self.down.add(identifier)
        self.complete.add(identifier)
        self.tracker.activate(identifier)

    def release(self, identifier=W, point=(100, 200), modifier_first=False):
        self.platform.desktop.cursor = point
        self.complete.discard(identifier)
        if not modifier_first:
            self.down.discard(identifier)
        self.tracker.poll()

    def assert_idle(self):
        self.assertFalse(self.placement.state.active)
        self.assertFalse(self.placement.overlays or self.capture.overlays)
        self.assertFalse(self.placement.timer.isActive() or self.capture.tracking.isActive())
        self.assertIsNone(self.placement.session.owner)
        self.assertFalse(self.keys.escape)

    def test_help_teaches_hold_release_for_both_shortcuts(self):
        from mini_whiteboard.shortcuts import ShortcutPolicy
        for policy in (ShortcutPolicy(), ShortcutPolicy(True), ShortcutPolicy(True, 'alternate')):
            text = policy.help_html()
            self.assertNotIn('press again', text)
            self.assertNotIn('click, drag, release', text)
            for trigger in ('W', 'S'):
                instruction = next(line for line in text.splitlines() if line.startswith(policy.global_label(trigger)))
                self.assertIn('hold', instruction)
                self.assertIn('release', instruction)

    def test_initial_press_tracks_without_completing(self):
        self.begin()
        self.assertEqual(self.rects, [])
        self.platform.desktop.cursor = (100, 200)
        self.placement.track()
        self.assertTrue(all(o.outline == Rect(-400, -200, 500, 400) for o in self.placement.overlays))
        self.assertTrue(all(o.windowFlags() & Qt.WindowType.WindowTransparentForInput
                            for o in self.placement.overlays))
        self.release()
        self.assertEqual(self.rects, [Rect(-400, -200, 500, 400)])
        self.assert_idle()
        self.assertFalse(self.tracker.timer.isActive())

    def test_long_repeat_and_duplicate_release_produce_one_result(self):
        self.begin()
        for _ in range(100):
            self.tracker.activate(W)
            self.keys.events.create.emit()  # Also defend the shared controller.
        self.assertEqual(self.rects, [])
        self.release()
        self.tracker.release(W)
        self.keys.events.create_released.emit()
        self.assertEqual(len(self.rects), 1)
        self.assert_idle()

    def test_each_modifier_first_release_blocks_remaining_trigger(self):
        for modifier in ('control', 'option', 'shift', 'command'):
            with self.subTest(modifier=modifier):
                before = len(self.rects)
                self.begin()
                self.release(modifier_first=True)
                self.assertEqual(len(self.rects), before+1)
                self.assertIn(W, self.tracker.blocked)
                self.tracker.activate(W)
                self.assertFalse(self.placement.state.active)
                self.down.clear()
                self.tracker.poll()
                self.assertFalse(self.tracker.timer.isActive())

    def test_cancel_while_held_requires_fresh_activation(self):
        self.begin()
        self.keys.events.cancel.emit()
        for _ in range(30):
            self.tracker.activate(W)
        self.assert_idle()
        self.release()
        self.assertEqual(self.rects, [])
        self.begin()
        self.release()
        self.assertEqual(len(self.rects), 1)

    def test_competing_shortcut_never_replaces_owner(self):
        self.begin()
        self.begin(S)
        self.keys.events.capture.emit()
        self.assertFalse(self.capture.active)
        self.assertEqual(self.placement.session.owner, 'board')
        self.release()
        self.tracker.release(S)
        self.assertEqual(len(self.rects), 1)
        self.down.clear()
        self.complete.clear()
        self.tracker.poll()
        self.assert_idle()

    def test_too_small_release_cancels_and_next_gesture_works(self):
        self.begin(point=(40, 40))
        self.release(point=(50, 50))
        self.assertEqual(self.rects, [])
        self.assert_idle()
        self.begin()
        self.release()
        self.assertEqual(len(self.rects), 1)

    def test_unmatched_releases_and_rapid_gestures(self):
        self.tracker.release(W)
        self.keys.events.capture_released.emit()
        for _ in range(15):
            self.begin()
            self.release()
        self.assertEqual(len(self.rects), 15)
        self.assert_idle()

    def test_remaining_s_does_not_become_shape_tool(self):
        self.begin(S)
        self.release(S, modifier_first=True)
        for kind in (QEvent.Type.KeyPress, QEvent.Type.ShortcutOverride):
            event = QKeyEvent(kind, Qt.Key.Key_S, Qt.KeyboardModifier.NoModifier, 's', True)
            self.assertTrue(self.tracker.eventFilter(None, event))
        self.down.clear()
        self.tracker.poll()
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_S, Qt.KeyboardModifier.NoModifier)
        self.assertFalse(self.tracker.eventFilter(None, event))

    def test_native_sample_error_cancels_and_drains_before_retry(self):
        self.begin()
        with patch.object(self.tracker, 'sample', side_effect=OSError('unavailable')):
            self.tracker.poll()
        self.assert_idle()
        self.tracker.activate(W)
        self.assertFalse(self.placement.state.active)
        self.release()
        self.begin()
        self.release()
        self.assertEqual(len(self.rects), 1)

    def test_escape_with_modifiers_is_detected_during_hold_only(self):
        self.begin()
        with patch.object(self.tracker, 'sample', return_value=(self.down.copy(), self.complete.copy(), True)):
            self.tracker.poll()
        self.assert_idle()
        self.release()
        self.assertFalse(self.rects)

    def test_all_four_release_directions(self):
        for end in ((-700, -600), (-300, -600), (-700, -200), (-300, -200)):
            self.begin(point=(-500, -400))
            self.release(point=end)
            self.assertEqual((self.rects[-1].width, self.rects[-1].height), (200, 200))
            self.assert_idle()

    def test_preview_exception_cleans_partial_windows(self):
        with patch.object(self.platform.desktop, 'configure_overlay', side_effect=ValueError('display changed')):
            self.begin()
        self.assert_idle()
        self.release()
        self.begin()
        self.release()
        self.assertEqual(len(self.rects), 1)

    def start_capture(self):
        self.begin(S, (100, 100))
        self.assertFalse(self.platform.capture.requests)
        self.release(S, (500, 400))
        APP.processEvents()
        return self.platform.capture.requests[-1]

    def test_capture_release_is_passive_and_pending_retains_ownership(self):
        request = self.start_capture()
        self.assertTrue(self.capture.pending)
        self.assertFalse(self.capture.overlays or self.capture.tracking.isActive())
        self.begin()
        self.release()
        self.assertFalse(self.rects)
        request[1](QImage(20, 20, QImage.Format.Format_RGB32))
        self.assertFalse(self.images)  # Even synchronous service completion is queued.
        APP.processEvents()
        self.assertEqual(len(self.images), 1)
        self.assert_idle()

    def test_cancel_and_late_queued_success_cannot_create(self):
        request = self.start_capture()
        request[1](QImage(20, 20, QImage.Format.Format_RGB32))
        self.capture.cancel()
        APP.processEvents()
        request[2](OSError('late'))
        APP.processEvents()
        self.assertFalse(self.images or self.messages)
        self.assert_idle()

    def test_capture_timeout_and_late_callback_are_single_failure(self):
        request = self.start_capture()
        self.capture.timeout.timeout.emit()
        request[1](QImage(20, 20, QImage.Format.Format_RGB32))
        APP.processEvents()
        self.assertEqual(len(self.messages), 1)
        self.assertFalse(self.images)
        self.assert_idle()
        self.assertFalse(self.capture.timeout.isActive())

    def test_permission_prompt_only_after_release_and_cleanup(self):
        self.platform.capture.denial = CapturePermissionError('permission')
        errors = []
        self.capture.permission_required.connect(lambda e: (self.assert_idle(), errors.append(e)))
        self.begin(S, (100, 100))
        self.assertFalse(errors)
        self.release(S, (500, 400))
        APP.processEvents()
        self.assertEqual(errors, ['permission'])
        self.assertFalse(self.platform.capture.requests)

    def test_capture_tiny_region_cancels_and_tracks_no_mouse_grab(self):
        self.begin(S, (100, 100))
        self.release(S, (102, 102))
        self.assert_idle()
        self.assertFalse(self.platform.capture.requests)


class MacHoldTests(QtCase):
    def test_modifier_first_and_stale_native_events_in_both_presets(self):
        for preset in ('default', 'alternate'):
            with self.subTest(preset=preset):
                keys = MacHotkeys(APP, preset, FakeCarbon)
                keys.start()
                try:
                    events = []
                    keys.events.create.connect(lambda: events.append('press'))
                    keys.events.create_released.connect(lambda: events.append('release'))
                    keys.backend.down.add(W)
                    keys.deliver(W, True, 10)
                    keys.backend.modifiers_held = False
                    keys.hold.poll()
                    keys.deliver(W, True, 11)
                    keys.deliver(W, False, 11)
                    self.assertEqual(events, ['press', 'release'])
                    keys.backend.down.clear()
                    keys.hold.poll()
                    keys.backend.modifiers_held = True
                    keys.backend.down.add(W)
                    keys.deliver(W, True, 12)
                    keys.deliver(W, False, 11)  # Old release cannot finish a new hold.
                    self.assertEqual(events[-1], 'press')
                    keys.deliver(W, False, 13)
                    self.assertEqual(events, ['press', 'release', 'press', 'release'])
                finally:
                    keys.close()
