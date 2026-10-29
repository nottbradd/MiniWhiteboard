"""Public settings path, native conflicts, rollback and persisted custom chords."""
import ctypes
from ctypes import wintypes
from dataclasses import replace
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import QSettings, Qt, QEvent
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from tests.qt_case import APP, QtCase
from tests.fake_platform import fake_platform
from tests.test_platform import FakeCarbon
from mini_whiteboard.app import WhiteboardApplication
from mini_whiteboard.hotkey_config import (ACTIONS, Chord, HotkeyConfig, compatibility,
                                         defaults, recorded_chord)
from mini_whiteboard.hotkey_settings import HotkeySettings
from mini_whiteboard.platform.base import CREATE_HOTKEY, CAPTURE_HOTKEY, HIDE_HOTKEY
from mini_whiteboard.platform.windows import native
from mini_whiteboard.platform.macos.hotkeys import MacHotkeys, CARBON_KEYS
from mini_whiteboard.shortcuts import ShortcutPolicy
from mini_whiteboard.snapping import SnapPreferences


CUSTOM = HotkeyConfig(Chord({'ctrl', 'shift'}, 'F8'), Chord({'alt', 'meta'}, 'J'),
                      Chord({'ctrl', 'alt'}, 'K'))


class ConfigurationTests(QtCase):
    def test_roundtrip_duplicate_and_unsupported_validation(self):
        self.assertEqual(HotkeyConfig.from_json(CUSTOM.to_json()), CUSTOM)
        for config in (replace(CUSTOM, capture=CUSTOM.create),
                       replace(CUSTOM, create=Chord({'shift'}, 'A')),
                       replace(CUSTOM, create=Chord({'ctrl'}, 'Control')),
                       replace(CUSTOM, create=Chord({'ctrl'}, 'A, B')),
                       replace(CUSTOM, hide=Chord({'hyper'}, 'H'))):
            with self.subTest(config=config), self.assertRaises(ValueError):
                config.validate()

    def test_legacy_migration_and_explicit_choices_survive_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / 'prefs.ini'), QSettings.Format.IniFormat)
            settings.setValue('shortcuts/windows_hide', 'shift')
            settings.setValue('shortcuts/preset', 'alternate')
            prefs = SnapPreferences(settings=settings)
            self.assertEqual(prefs.hotkey_configuration(), defaults(hide='shift'))
            self.assertEqual(prefs.hotkey_configuration(True), defaults(True, 'alternate'))
            prefs.set_hotkey_configuration(CUSTOM)
            again = SnapPreferences(settings=settings)
            self.assertEqual(again.hotkey_configuration(), CUSTOM)
            self.assertEqual(again.hotkey_configuration(True), defaults(True, 'alternate'))
            self.assertEqual(again.windows_hide, 'shift')
            old_defaults = HotkeyConfig(Chord({'shift', 'meta'}, 'W'),
                                       Chord({'shift', 'meta'}, 'Q'), defaults(hide='shift').hide)
            prefs.set_hotkey_configuration(old_defaults)
            self.assertEqual(SnapPreferences(settings=settings).hotkey_configuration(), old_defaults)

    def test_invalid_saved_data_keeps_settings_accessible(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / 'prefs.ini'), QSettings.Format.IniFormat)
            settings.setValue('shortcuts/custom_windows', '{broken')
            self.assertEqual(SnapPreferences(settings=settings).hotkey_configuration(), defaults())

    def test_mac_recorder_maps_command_and_control_separately(self):
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_J,
                         Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
        self.assertEqual(recorded_chord(event, True), Chord({'meta', 'alt'}, 'J'))
        self.assertEqual(recorded_chord(event), Chord({'ctrl', 'alt'}, 'J'))
        modifier = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Control, Qt.KeyboardModifier.ControlModifier)
        with self.assertRaises(ValueError):
            recorded_chord(modifier)

    def test_help_uses_custom_chords_without_rewriting_global_control_on_mac(self):
        policy = ShortcutPolicy(mac=True, configuration=CUSTOM)
        self.assertEqual(policy.global_label('W'), 'Control+Shift+F8')
        self.assertIn('Control+Shift+F8', policy.help_html())
        self.assertIn('Command+Z', policy.help_html())
        self.assertNotIn('release W', policy.help_html())
        self.assertEqual(set(CARBON_KEYS).intersection('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'),
                         set('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'))
        self.assertEqual([CARBON_KEYS[k] for k in 'WSHQ'], [13, 1, 4, 12])


class WindowsConfigurationTests(QtCase):
    def setUp(self):
        super().setUp()
        self.owned, self.conflicts, self.down = {}, set(), set()
        self.clock = 100
        def register(_window, identifier, modifiers, key):
            chord = modifiers & 15, key
            if chord in self.conflicts or chord in self.owned.values():
                return False
            self.owned[identifier] = chord
            return True
        def unregister(_window, identifier):
            self.owned.pop(identifier, None)
            return True
        user = SimpleNamespace(RegisterHotKey=register, UnregisterHotKey=unregister,
                               GetAsyncKeyState=lambda key: 0x8000 if key in self.down else 0)
        self.enterContext(patch.object(native, 'IS_WINDOWS', True))
        self.enterContext(patch.object(native, 'user32', user, create=True))
        self.enterContext(patch.object(native, 'kernel32', SimpleNamespace(GetTickCount=lambda: self.clock), create=True))
        self.enterContext(patch.object(native.C, 'get_last_error', lambda: 1409, create=True))
        self.enterContext(patch.object(native.C, 'WinError', lambda error: OSError('1409: already registered'), create=True))
        self.keys = native.NativeHotkeys(APP)
        self.keys.start()
        self.addCleanup(self.keys.close)

    def message(self, identifier, chord, stamp):
        msg = wintypes.MSG()
        msg.message, msg.wParam, msg.time = native.WM_HOTKEY, identifier, stamp
        msg.lParam = chord.windows_key << 16 | chord.windows_modifiers
        self.keys.nativeEventFilter(b'windows_generic_MSG', ctypes.addressof(msg))

    def test_swap_registration_and_per_action_modifiers_and_keys(self):
        self.keys.apply_configuration(replace(defaults(), create=defaults().capture, capture=defaults().create))
        self.assertEqual(self.owned[CREATE_HOTKEY], (14, ord('Q')))
        self.keys.apply_configuration(CUSTOM)
        self.assertEqual(self.owned, {CREATE_HOTKEY: (6, 0x77), CAPTURE_HOTKEY: (9, ord('J')), HIDE_HOTKEY: (3, ord('K'))})
        self.down = {0xA2, 0xA0, 0x77, ord('J')}
        self.assertEqual(self.keys.sample()[:2], ({CREATE_HOTKEY, CAPTURE_HOTKEY}, {CREATE_HOTKEY}))
        self.down = {0xA4, 0x5C, 0x77, ord('J')}
        self.assertEqual(self.keys.sample()[1], {CAPTURE_HOTKEY})
        self.keys.enable_escape()
        self.assertEqual({v[0] for v in self.owned.values() if v[1] == 27}, {0, 1, 2, 4, 6, 8, 9})

    def test_failed_transaction_restores_owned_chords_and_configuration(self):
        before = dict(self.owned)
        self.conflicts.add((CUSTOM.capture.windows_modifiers, CUSTOM.capture.windows_key))
        with self.assertRaisesRegex(OSError, 'Screenshot / quick capture.*1409'):
            self.keys.apply_configuration(CUSTOM)
        self.assertEqual(self.owned, before)
        self.assertEqual(self.keys.configuration, defaults())
        self.assertEqual(self.keys.registered, set(ACTIONS))

    def test_unrecoverable_rollback_is_reported_not_marked_active(self):
        self.conflicts.update(((9, ord('J')), (14, ord('W'))))
        with self.assertRaisesRegex(OSError, 'Could not restore: Create whiteboard'):
            self.keys.apply_configuration(CUSTOM)
        self.assertNotIn(CREATE_HOTKEY, self.keys.registered)
        self.assertIn(CAPTURE_HOTKEY, self.keys.registered)

    def test_pause_suppresses_events_resume_drains_held_and_stale_callbacks(self):
        events = []
        self.keys.events.create.connect(lambda: events.append('create'))
        self.keys.events.hide_toggle.connect(lambda: events.append('hide'))
        self.keys.pause()
        self.assertFalse(self.owned)
        self.keys.apply_configuration(CUSTOM)
        self.message(CREATE_HOTKEY, CUSTOM.create, 101)
        self.message(HIDE_HOTKEY, CUSTOM.hide, 101)
        self.assertFalse(events)
        self.down = {0x77, 0xA2, 0xA0, ord('K')}
        self.clock = 102
        self.keys.resume()
        self.message(CREATE_HOTKEY, CUSTOM.create, 103)
        self.message(HIDE_HOTKEY, CUSTOM.hide, 103)
        self.assertFalse(events)
        self.down.clear()
        self.keys.hold.poll()
        self.keys.hide_latch.poll()
        self.message(CREATE_HOTKEY, CUSTOM.create, 101)
        self.assertFalse(events)
        self.message(CREATE_HOTKEY, CUSTOM.create, 104)
        self.assertEqual(events, ['create'])

    def test_same_trigger_different_modifiers_filters_only_owned_hold(self):
        config = replace(CUSTOM, capture=Chord({'alt'}, 'F8'))
        self.keys.apply_configuration(config)
        self.keys.hold.blocked = {CAPTURE_HOTKEY}
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_F8, Qt.KeyboardModifier.NoModifier)
        self.assertTrue(self.keys.hold.eventFilter(None, event))
        self.keys.hold.blocked.clear()
        self.assertFalse(self.keys.hold.eventFilter(None, event))

    def test_reserved_escape_subsets_do_not_abort_custom_placement(self):
        self.keys.apply_configuration(replace(CUSTOM, create=Chord({'ctrl', 'alt'}, 'F8')))
        self.conflicts.update(((2, 27), (6, 27)))
        self.keys.hold.active = CREATE_HOTKEY
        messages = []
        self.keys.events.warning.connect(messages.append)
        self.keys.enable_escape()
        self.assertIn((3, 27), self.owned.values())
        self.assertFalse(messages)
        self.keys.disable_escape()
        self.keys.apply_configuration(CUSTOM)
        self.keys.hold.active = CREATE_HOTKEY
        self.keys.enable_escape()
        self.assertTrue(any('tray menu' in message for message in messages))
        self.assertIn(CREATE_HOTKEY, self.keys.registered)

    def controller(self, conflict=False):
        self.keys.close()
        if conflict:
            self.conflicts.add((14, ord('W')))
        platform = fake_platform()
        platform.shortcuts = ShortcutPolicy()
        platform.hotkey_factory = lambda app, preset: native.NativeHotkeys(app)
        with patch.object(WhiteboardApplication, 'notify'):
            c = WhiteboardApplication(APP, SnapPreferences(), platform)
            APP.processEvents()
        c.notify = lambda text: None
        self.addCleanup(c.cleanup)
        c.show_hotkey_settings()
        self.addCleanup(c.hotkey_dialog.deleteLater)
        return c, c.hotkey_dialog

    def test_conflict_recovery_through_dialog_persists_actual_configuration(self):
        c, dialog = self.controller(conflict=True)
        self.assertIn('Unavailable', dialog.rows[CREATE_HOTKEY][3].text())
        self.assertIn('1409', dialog.rows[CREATE_HOTKEY][3].text())
        dialog.load(compatibility(defaults()))
        dialog.apply()
        self.assertTrue(dialog.closed)
        self.assertEqual(c.preferences.hotkey_configuration(), compatibility(defaults()))
        self.assertEqual(c.hotkeys.registered, set(ACTIONS))
        self.assertNotIn('unavailable', c.tray.toolTip())
        self.assertIn(c.hotkeys.configuration.create.label(), c.platform.shortcuts.help_html())

    def test_failed_apply_duplicate_and_cancel_never_save(self):
        c, dialog = self.controller()
        dialog.load(replace(CUSTOM, hide=CUSTOM.create))
        dialog.apply()
        self.assertIn('duplicates', dialog.message.text())
        self.assertFalse(c.preferences.custom_hotkeys)
        self.conflicts.add((9, ord('J')))
        dialog.load(CUSTOM)
        dialog.apply()
        self.assertIn('not saved', dialog.message.text())
        self.assertEqual(c.hotkeys.configuration, defaults())
        self.assertEqual(c.hotkeys.registered, set(ACTIONS))
        dialog.reject()
        self.assertFalse(c.hotkeys.paused)
        self.assertFalse(c.preferences.custom_hotkeys)

    def test_reset_defaults_is_pending_until_apply_and_cancel_restores_custom(self):
        self.keys.apply_configuration(CUSTOM)
        c, dialog = self.controller()
        dialog.load(CUSTOM)
        dialog.apply()
        c.show_hotkey_settings()
        reset = c.hotkey_dialog
        self.addCleanup(reset.deleteLater)
        from PySide6.QtWidgets import QDialogButtonBox
        reset.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.RestoreDefaults).click()
        self.assertEqual(reset.configuration(), defaults())
        self.assertEqual(c.preferences.hotkey_configuration(), CUSTOM)
        reset.reject()
        self.assertEqual(c.hotkeys.configuration, CUSTOM)

    def test_recording_does_not_activate_actions_and_closing_restores_registration(self):
        c, dialog = self.controller()
        events = []
        c.hotkeys.events.create.connect(lambda: events.append('create'))
        c.hotkeys.events.capture.connect(lambda: events.append('capture'))
        c.hotkeys.events.hide_toggle.connect(lambda: events.append('hide'))
        dialog.begin_recording(CREATE_HOTKEY)
        QTest.keyClick(dialog, Qt.Key.Key_F8, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual(dialog.configuration().create, CUSTOM.create)
        self.assertIsNone(dialog.recording)
        self.assertFalse(events)
        dialog.begin_recording(CAPTURE_HOTKEY)
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
        self.assertIsNone(dialog.recording)
        self.assertFalse(dialog.closed)
        dialog.begin_recording(HIDE_HOTKEY)
        dialog.close()
        self.assertTrue(dialog.closed)
        self.assertIsNone(dialog.recording)
        self.assertFalse(c.hotkeys.paused)
        self.assertEqual(c.hotkeys.registered, set(ACTIONS))
        self.assertFalse(c.preferences.custom_hotkeys)


class MacConfigurationTests(QtCase):
    def test_custom_registration_sampling_rollback_and_pause(self):
        keys = MacHotkeys(APP, backend_factory=FakeCarbon)
        self.addCleanup(keys.close)
        keys.start()
        keys.apply_configuration(CUSTOM)
        self.assertEqual(keys.backend.active[CREATE_HOTKEY], (100, (1 << 12) | (1 << 9)))
        self.assertEqual(keys.backend.active[CAPTURE_HOTKEY], (38, (1 << 8) | (1 << 11)))
        captured = []
        keys.backend.sample = lambda bindings: captured.append(bindings) or (set(), set())
        keys.sample()
        self.assertEqual(captured[-1][CAPTURE_HOTKEY], (38, 2304))
        keys.pause()
        self.assertFalse(keys.backend.active)
        keys.resume()
        old = dict(keys.backend.active)
        keys.backend.fail.add(CAPTURE_HOTKEY)
        with self.assertRaisesRegex(OSError, 'Could not restore'):
            keys.apply_configuration(defaults(True))
        self.assertEqual(keys.configuration, CUSTOM)
        self.assertNotIn(CAPTURE_HOTKEY, keys.registered)
        self.assertEqual(keys.backend.active[CREATE_HOTKEY], old[CREATE_HOTKEY])
