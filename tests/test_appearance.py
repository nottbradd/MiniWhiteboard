from pathlib import Path
import tempfile
from unittest.mock import patch, MagicMock
from types import SimpleNamespace
import sys

from tests.qt_case import APP, QtCase, wait_until
from tests.fake_platform import fake_platform
from PySide6.QtCore import QSettings, QAbstractAnimation
from PySide6.QtTest import QTest
from mini_whiteboard.appearance import DisplayPolicy, surface
from mini_whiteboard.board import BoardWindow
from mini_whiteboard.document import Text
from mini_whiteboard.images import from_image
from PySide6.QtGui import QImage
from mini_whiteboard.snapping import SnapPreferences
from mini_whiteboard.clipboard import rendered_image


class AppearanceTests(QtCase):
    def test_windows_frost_uses_the_screen_origin_for_a_friendly_monitor_name(self):
        from PySide6.QtCore import QRect
        from mini_whiteboard.platform.windows import appearance
        screen = SimpleNamespace(name=lambda: '24G2W1G3-', geometry=lambda: QRect(-1920, 80, 1536, 864))
        with (patch.object(appearance.native, 'IS_WINDOWS', True),
              patch.object(appearance.sys, 'getwindowsversion', create=True,
                           return_value=SimpleNamespace(build=26300)),
              patch.object(appearance, 'backdrop_display', return_value=True) as display):
            self.assertTrue(appearance.capable(DisplayPolicy(),screen))
            display.assert_called_once_with((-1920,80))
            display.reset_mock()
            self.assertFalse(appearance.capable(DisplayPolicy(transparency=False),screen))
            self.assertFalse(appearance.capable(DisplayPolicy(high_contrast=True),screen))
            display.assert_not_called()

    def test_windows_frost_matches_the_adapter_attached_to_each_monitor(self):
        from mini_whiteboard.geometry import Rect
        from mini_whiteboard.platform.windows import appearance

        monitors = [SimpleNamespace(name='DISPLAY-A', rect=Rect(0, 0, 1920, 1080)),
                    SimpleNamespace(name='DISPLAY-B', rect=Rect(-2560, 80, 2560, 1440))]
        adapters = [('DISPLAY-A', 'Hyper-V Video', 5), ('DISPLAY-B', 'NVIDIA', 1)]

        def enabled(flag):
            flag._obj.value = True
            return 0

        def enumerate_display(_name, index, info, _flags):
            if index == len(adapters):
                return False
            info._obj.name, info._obj.description, info._obj.flags = adapters[index]
            return True

        def bind(_library, method, *_args):
            return {'DwmIsCompositionEnabled': enabled, 'EnumDisplayDevicesW': enumerate_display}[method]

        query = appearance.backdrop_display
        query.cache_clear()
        self.addCleanup(query.cache_clear)
        with (patch.object(appearance.native, 'monitors', return_value=monitors),
              patch.object(appearance.native, 'user32', create=True,
                           new=SimpleNamespace(GetSystemMetrics=lambda _: 0)),
              patch.object(appearance.native, 'bind', create=True, side_effect=bind),
              patch.object(appearance.C, 'WinDLL', create=True)):
            self.assertTrue(query((-2560, 80)))
            self.assertFalse(query((0, 0)))
            self.assertFalse(query((40, 20)))
            self.assertFalse(query())

    def test_mac_accessibility_fallback_recovers_when_transparency_is_reenabled(self):
        from mini_whiteboard.platform.macos.desktop import MacDesktop
        callbacks = {}
        class Centre:
            def addObserverForName_object_queue_usingBlock_(self, name, obj, queue, callback):
                token = object()
                callbacks[token] = callback
                return token
            def removeObserver_(self, token):
                callbacks.pop(token)
            def publish(self):
                for callback in tuple(callbacks.values()):
                    callback(None)
        centre = Centre()
        workspace = MagicMock()
        workspace.notificationCenter.return_value = centre
        workspace.accessibilityDisplayShouldIncreaseContrast.return_value = False
        workspace.accessibilityDisplayShouldReduceMotion.return_value = True
        workspace.accessibilityDisplayShouldReduceTransparency.return_value = True
        appkit = SimpleNamespace(NSWorkspace=SimpleNamespace(sharedWorkspace=lambda: workspace),
            NSWorkspaceAccessibilityDisplayOptionsDidChangeNotification='policy',
            NSVisualEffectView=MagicMock(), NSVisualEffectMaterialPopover=1,
            NSVisualEffectBlendingModeBehindWindow=0, NSVisualEffectStateActive=1,
            NSAppearance=MagicMock(), NSAppearanceNameAqua='Aqua', NSViewWidthSizable=2,
            NSViewHeightSizable=4, NSWindowBelow=-1, NSFloatingWindowLevel=3,
            NSColor=MagicMock(), NSWindowCollectionBehaviorManaged=0)
        foundation = SimpleNamespace(NSOperationQueue=SimpleNamespace(mainQueue=lambda: None))
        prefs = SnapPreferences()
        prefs.set_theme('Glass')
        board = BoardWindow('Policy recovery', prefs, fake_platform())
        self.widgets.append(board)
        board.show()
        with patch.dict(sys.modules, {'AppKit': appkit, 'Foundation': foundation}), \
             patch('mini_whiteboard.platform.macos.desktop.native_window', return_value=MagicMock()):
            board.desktop = MacDesktop()
            board.refresh_appearance()
            self.assertFalse(board.native_glass)
            self.assertEqual(len(callbacks), 1)
            workspace.accessibilityDisplayShouldReduceTransparency.return_value = False
            centre.publish()
            self.assertTrue(board.native_glass)
            self.assertEqual(len(callbacks), 1)
            workspace.accessibilityDisplayShouldReduceTransparency.return_value = True
            centre.publish()
            self.assertFalse(board.native_glass)
            self.assertEqual(len(callbacks), 1)
            board.close()
            self.assertEqual(callbacks, {})

    def test_native_effect_failure_uses_readable_solid_without_changing_document(self):
        prefs = SnapPreferences()
        board = BoardWindow('Fallback', prefs)
        self.widgets.append(board)
        board.show()
        obj = Text((20, 30), 'unchanged')
        board.canvas.document.add(obj)
        before = (board.canvas.document.objects, list(board.canvas.document.history), board.geometry())
        with patch('mini_whiteboard.platform.windows.appearance.capable', return_value=True), \
             patch('mini_whiteboard.platform.windows.appearance.BackdropHost', side_effect=OSError('DWM unavailable')):
            prefs.set_theme('Glass')
            self.assertFalse(board.native_glass)
            self.assertEqual(surface('Glass', board.native_glass, board.display_policy).alpha(), 255)
        self.assertEqual(before, (board.canvas.document.objects, board.canvas.document.history, board.geometry()))

    def test_persisted_theme_existing_and_new_boards_preserve_content(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory)/'settings.ini'), QSettings.Format.IniFormat)
            prefs = SnapPreferences(settings=settings)
            self.assertEqual(prefs.theme, 'White')
            platform = fake_platform()
            board = BoardWindow('Existing', prefs, platform)
            self.widgets.append(board)
            board.show()
            pixels = QImage(80, 60, QImage.Format.Format_RGB32)
            pixels.fill('#2878d0')
            image = from_image(pixels)
            board.canvas.document.add(image)
            original = board.canvas.document.objects
            original_history = list(board.canvas.document.history)
            copied_before = rendered_image(original)
            prefs.set_theme('Glass')
            APP.processEvents()
            self.assertEqual(board.canvas.document.objects, original)
            self.assertIs(board.canvas.document.objects[0], image)
            self.assertEqual(board.canvas.document.history, original_history)
            self.assertEqual(rendered_image(original), copied_before)
            fresh = SnapPreferences(settings=QSettings(str(Path(directory)/'settings.ini'), QSettings.Format.IniFormat))
            self.assertEqual(fresh.theme, 'Frosted Glass')
            other = BoardWindow('New', fresh, platform)
            self.widgets.append(other)
            other.show()
            self.assertFalse(other.native_glass)  # Readable solid adapter fallback.
            self.assertEqual(other.windowOpacity(), 1)

    def test_accessibility_native_failure_and_alpha_policy(self):
        self.assertEqual(surface('White', True, DisplayPolicy()).alpha(), 255)
        self.assertLess(surface('Glass', True, DisplayPolicy()).alpha(), 255)
        self.assertEqual(surface('Glass', False, DisplayPolicy()).alpha(), 255)
        self.assertEqual(surface('Glass', True, DisplayPolicy(high_contrast=True)).name(), '#ffffff')
        self.assertEqual(surface('Glass', True, DisplayPolicy(transparency=False)).alpha(), 255)
        from mini_whiteboard.platform.windows import appearance
        with patch.object(appearance.native, 'IS_WINDOWS', False):
            self.assertFalse(appearance.capable(DisplayPolicy()))

    def test_animations_interrupt_and_finish_without_document_or_geometry_changes(self):
        platform = fake_platform()
        prefs = SnapPreferences()
        board = BoardWindow('Motion', prefs, platform)
        self.widgets.append(board)
        board.resize(600, 380)
        board.show()
        board.display_policy = DisplayPolicy(motion=True)
        stopped_at=[]
        def record_stop(state, _previous):
            if state==QAbstractAnimation.State.Stopped and board.emphasis.clock.isValid():
                stopped_at.append(board.emphasis.clock.elapsed())
        board.emphasis.animation.stateChanged.connect(record_stop)
        before = board.geometry()
        with patch.object(board, 'update') as repaint:
            board.emphasis.changed(.5)
            region = repaint.call_args[0][0]
            paper = board.paper_rect().toAlignedRect()
            self.assertTrue(region.contains(paper.bottomLeft() + (paper.bottomRight()-paper.bottomLeft())/2))
            self.assertFalse(region.contains(paper.center()))
        board.emphasis.start()
        board.refresh_appearance()
        self.assertEqual(board.emphasis.animation.state(), QAbstractAnimation.State.Stopped)
        self.assertFalse(board.emphasis.deadline.isActive())
        for _ in range(10):
            board.emphasis.start()
            self.assertEqual(board.emphasis.animation.state(), QAbstractAnimation.State.Running)
            board.prepare_hide()
            board.hide()
            self.assertEqual(board.emphasis.animation.state(), QAbstractAnimation.State.Stopped)
            self.assertFalse(board.emphasis.deadline.isActive())
            board.restore(activate=False)
            prefs.set_theme('Glass' if prefs.theme == 'White' else 'White')
        stopped_at.clear()
        # Record the transition itself. qWait can finish after unrelated queued
        # painting even when the animation stopped on time. The observation
        # watchdog is separate from the unchanged 180 ms presentation limit.
        self.assertTrue(wait_until(lambda: bool(stopped_at),500),
                        f'Presentation exceeded 180 ms: frame={board.emphasis.animation.currentTime()}; '
                        f'deadline={board.emphasis.deadline.remainingTime()}; elapsed={board.emphasis.clock.elapsed()}')
        self.assertLessEqual(stopped_at[-1],180,'Actual presentation stop exceeded 180 ms')
        self.assertEqual(board.emphasis.animation.state(), QAbstractAnimation.State.Stopped,
                         f'frame={board.emphasis.animation.currentTime()} ms; '
                         f'deadline={board.emphasis.deadline.remainingTime()} ms; '
                         f'elapsed={board.emphasis.clock.elapsed()} ms')
        self.assertFalse(board.emphasis.deadline.isActive())
        self.assertEqual(board.geometry(), before)
        self.assertEqual(board.canvas.document.history, [])
        self.assertEqual(board.windowOpacity(), 1)
        board.display_policy = DisplayPolicy(motion=False)
        board.emphasis.start()
        self.assertEqual(board.emphasis.animation.state(), QAbstractAnimation.State.Stopped)
        board.canvas.feedback.show_message('feedback')
        board.canvas.feedback.finish_delay()
        self.assertFalse(board.canvas.feedback.isVisible())
