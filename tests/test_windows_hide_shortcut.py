"""The shipped Windows preference changes only H, including failed retries."""
import ctypes
from ctypes import wintypes
from pathlib import Path
from types import SimpleNamespace
import tempfile
from unittest.mock import patch

from PySide6.QtCore import QSettings
from tests.qt_case import APP, QtCase
from tests.fake_platform import fake_platform
from mini_whiteboard.app import WhiteboardApplication
from mini_whiteboard.platform.base import CREATE_HOTKEY, CAPTURE_HOTKEY, HIDE_HOTKEY
from mini_whiteboard.platform.windows import native
from mini_whiteboard.shortcuts import ShortcutPolicy
from mini_whiteboard.snapping import SnapPreferences


class WindowsHideShortcutTests(QtCase):
    def backend(self):
        self.registrations, self.removals = [], []
        def register(window, identifier, modifiers, key):
            self.registrations.append((identifier,modifiers,key))
            return not (identifier == HIDE_HOTKEY and modifiers & 7 == 3)
        user = SimpleNamespace(RegisterHotKey=register,
            UnregisterHotKey=lambda window,identifier: self.removals.append(identifier) or True,
            GetAsyncKeyState=lambda key: 0x8000 if key == ord('H') else 0)
        self.enterContext(patch.object(native,'IS_WINDOWS',True))
        self.enterContext(patch.object(native,'user32',user,create=True))
        self.enterContext(patch.object(native,'kernel32',SimpleNamespace(GetTickCount=lambda:100),create=True))
        self.enterContext(patch.object(native.C,'get_last_error',lambda:1409,create=True))
        self.enterContext(patch.object(native.C,'WinError',lambda value:OSError('already in use'),create=True))

    def test_saved_choices_validation_and_platform_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory)/'settings.ini')
            prefs = SnapPreferences(settings=QSettings(path,QSettings.Format.IniFormat))
            self.assertEqual(prefs.windows_hide,'default')
            for choice in ('shift','default'):
                prefs.set_windows_hide(choice)
                loaded = SnapPreferences(settings=QSettings(path,QSettings.Format.IniFormat))
                self.assertEqual(loaded.windows_hide,choice)
            with self.assertRaises(ValueError):
                prefs.set_windows_hide('invalid')
        policy = ShortcutPolicy(hide_shortcut='shift')
        self.assertEqual(policy.global_label('W'),'Win+Alt+W')
        self.assertEqual(policy.global_label('H'),'Ctrl+Alt+Shift+H')
        self.assertIn('Ctrl+Alt+Shift+H',policy.help_html())
        self.assertEqual(ShortcutPolicy(mac=True).global_label('H'),'Control+Option+H')
        self.assertEqual(ShortcutPolicy(mac=True,preset='alternate').global_label('H'),'Command+Option+Shift+H')

    def test_conflict_menu_choice_saved_launch_and_retry_preserve_working_bindings(self):
        self.backend()
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory)/'settings.ini')
            prefs = SnapPreferences(settings=QSettings(path,QSettings.Format.IniFormat))
            platform = fake_platform()
            platform.shortcuts = ShortcutPolicy()
            platform.hotkey_factory = lambda app,preset:native.NativeHotkeys(app)
            controller = WhiteboardApplication(APP,prefs,platform)
            self.addCleanup(controller.cleanup)
            warnings = []
            controller.notify = warnings.append
            APP.processEvents()
            self.assertEqual(controller.hotkeys.registered,{CREATE_HOTKEY,CAPTURE_HOTKEY})
            self.assertTrue(any('Hide All shortcut' in warning for warning in warnings))
            before = [entry for entry in self.registrations if entry[0] != HIDE_HOTKEY]
            controller.rebuild_menu()
            menu = next(a.menu() for a in controller.menu.actions() if a.text() == 'Hide All shortcut')
            next(a for a in menu.actions() if a.text() == 'Ctrl+Alt+Shift+H').trigger()
            self.assertEqual(controller.hotkeys.registered,{CREATE_HOTKEY,CAPTURE_HOTKEY,HIDE_HOTKEY})
            self.assertEqual(prefs.windows_hide,'shift')
            self.assertEqual(self.registrations[-1],(HIDE_HOTKEY,7|native.MOD_NOREPEAT,ord('H')))
            controller.retry_hotkey()
            self.assertEqual(before,[entry for entry in self.registrations if entry[0] != HIDE_HOTKEY])
            controller.change_hide_shortcut('default')
            self.assertEqual(self.removals,[HIDE_HOTKEY])
            self.assertEqual(controller.hotkeys.registered,{CREATE_HOTKEY,CAPTURE_HOTKEY})
            self.assertEqual(before,[entry for entry in self.registrations if entry[0] != HIDE_HOTKEY])
            controller.change_hide_shortcut('shift')
            controller.cleanup()
            loaded = SnapPreferences(settings=QSettings(path,QSettings.Format.IniFormat))
            fresh = WhiteboardApplication(APP,loaded,platform)
            self.addCleanup(fresh.cleanup)
            self.assertEqual(fresh.hotkeys.hide_shortcut,'shift')
            self.assertIn(HIDE_HOTKEY,fresh.hotkeys.registered)

    def test_changing_binding_while_held_and_stale_native_messages_cannot_retoggle(self):
        self.backend()
        keys = native.NativeHotkeys(APP,'shift')
        self.addCleanup(keys.close)
        keys.start()
        events = []
        keys.events.hide_toggle.connect(lambda:events.append(True))
        keys.hide_latch.activate()
        keys.set_hide_shortcut('default')
        keys.set_hide_shortcut('shift')
        keys.start()
        keys.hide_latch.activate()
        self.assertEqual(events,[True])
        self.assertTrue(keys.hide_latch.held)
        self.assertTrue(keys.hide_latch.timer.isActive())
        keys.hide_latch.is_down = lambda:False
        keys.hide_latch.poll()
        self.assertFalse(keys.hide_latch.timer.isActive())
        msg = wintypes.MSG()
        msg.message, msg.wParam, msg.time = native.WM_HOTKEY,HIDE_HOTKEY,101
        msg.lParam = ord('H') << 16 | 3
        keys.nativeEventFilter(b'windows_generic_MSG',ctypes.addressof(msg))
        self.assertEqual(events,[True])
        msg.lParam = ord('H') << 16 | 7
        keys.nativeEventFilter(b'windows_generic_MSG',ctypes.addressof(msg))
        keys.nativeEventFilter(b'windows_dispatcher_MSG',ctypes.addressof(msg))
        self.assertEqual(events,[True,True])
