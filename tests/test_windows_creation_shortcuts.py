"""Windows creation registration, left/right key sampling and queued messages."""
import ctypes
from ctypes import wintypes
from types import SimpleNamespace
from unittest.mock import patch
from tests.qt_case import APP, QtCase
from mini_whiteboard.platform.windows import native
from mini_whiteboard.platform.base import CREATE_HOTKEY, CAPTURE_HOTKEY, HIDE_HOTKEY
from mini_whiteboard.shortcuts import ShortcutPolicy


class WindowsCreationShortcutTests(QtCase):
    def setUp(self):
        super().setUp()
        self.down, self.calls, self.removals = set(), [], []
        self.conflicts = set()
        self.clock = 100
        def register(hwnd, identifier, modifiers, key):
            self.calls.append((identifier, modifiers, key))
            return identifier not in self.conflicts
        user = SimpleNamespace(RegisterHotKey=register,
            UnregisterHotKey=lambda hwnd, identifier: self.removals.append(identifier) or True,
            GetAsyncKeyState=lambda key: 0x8000 if key in self.down else 0)
        self.enterContext(patch.object(native, 'IS_WINDOWS', True))
        self.enterContext(patch.object(native, 'user32', user, create=True))
        self.enterContext(patch.object(native, 'kernel32', SimpleNamespace(GetTickCount=lambda: self.clock), create=True))
        self.enterContext(patch.object(native.C, 'get_last_error', lambda: 1409, create=True))
        self.enterContext(patch.object(native.C, 'WinError', lambda error: OSError('Already registered'), create=True))
        self.keys = native.NativeHotkeys(APP)
        self.addCleanup(self.keys.close)

    def message(self, key, stamp, modifiers=9):
        msg = wintypes.MSG()
        msg.message = native.WM_HOTKEY
        msg.wParam = CREATE_HOTKEY if key == 'W' else CAPTURE_HOTKEY
        msg.lParam, msg.time = ord(key) << 16 | modifiers, stamp
        for route in (b'windows_generic_MSG', b'windows_dispatcher_MSG'):
            self.keys.nativeEventFilter(route, ctypes.addressof(msg))

    def test_real_bindings_conflict_and_retry_keep_working_shortcuts(self):
        self.conflicts.add(CREATE_HOTKEY)
        with self.assertRaisesRegex(OSError, r'Win\+Alt\+W'):
            self.keys.start()
        self.assertEqual(self.keys.registered, {CAPTURE_HOTKEY, HIDE_HOTKEY})
        self.assertEqual([(mods & 15, vk) for _, mods, vk in self.calls], [(9, 87), (9, 83), (3, 72)])
        self.conflicts.clear()
        self.keys.start()
        self.assertEqual(self.calls[-1], (CREATE_HOTKEY, 9 | native.MOD_NOREPEAT, 87))
        self.assertEqual(len(self.calls), 4)
        self.keys.start()
        self.assertEqual(len(self.calls), 4)
        self.assertFalse(self.removals)

    def test_both_sides_and_every_required_release_with_repeat_drain(self):
        self.keys.start()
        events = []
        self.keys.events.create.connect(lambda: events.append('press'))
        self.keys.events.create_released.connect(lambda: events.append('release'))
        for win in (0x5B, 0x5C):
            for alt in (0xA4, 0xA5):
                for released in (win, alt, 87):
                    with self.subTest(win=win, alt=alt, first=released):
                        self.clock += 10
                        self.down = {win, alt, 87}
                        self.assertEqual(self.keys.sample()[:2], ({CREATE_HOTKEY}, {CREATE_HOTKEY}))
                        self.message('W', self.clock)
                        for _ in range(10):
                            self.keys.hold.activate(CREATE_HOTKEY)
                        self.down.remove(released)
                        self.keys.hold.poll()
                        self.assertEqual(events[-2:], ['press', 'release'])
                        before = list(events)
                        self.down.clear()
                        self.keys.hold.poll()
                        self.message('W', self.clock)  # queued pre-release callback
                        self.assertEqual(events, before)
                        self.assertFalse(self.keys.hold.timer.isActive())

    def test_old_modifiers_and_unsupported_messages_cannot_create(self):
        self.keys.start()
        events = []
        self.keys.events.create.connect(lambda: events.append(True))
        self.down = {0x11, 0xA4, 87}
        self.assertEqual(self.keys.sample()[1], set())
        self.message('W', 200, 3)
        self.assertFalse(events)
        self.assertFalse(self.keys.hold.timer.isActive())

    def test_escape_variants_are_distinct_from_hide_and_are_session_scoped(self):
        self.keys.start()
        self.keys.enable_escape()
        self.assertEqual([mods & 15 for identifier, mods, key in self.calls if key == 27], [0, 1, 8, 9])
        self.assertNotIn(HIDE_HOTKEY, native.ESCAPE_VARIANTS)
        self.keys.disable_escape()
        self.assertEqual(self.keys.registered, {CREATE_HOTKEY, CAPTURE_HOTKEY, HIDE_HOTKEY})

    def test_labels_match_native_bindings_and_mac_is_unchanged(self):
        policy = ShortcutPolicy()
        self.assertIn('Win+Alt+W', policy.help_html())
        self.assertIn('Win+Alt+S', policy.help_html())
        self.assertIn('Ctrl+Alt+H', policy.help_html())
        for preset, label in (('default', 'Control+Option'), ('alternate', 'Command+Option+Shift')):
            policy = ShortcutPolicy(mac=True, preset=preset)
            for key in ('W', 'S', 'H'):
                self.assertEqual(policy.global_label(key), label+'+'+key)
                self.assertIn(label+'+'+key, policy.help_html())
            self.assertNotIn('Win+', policy.help_html())
