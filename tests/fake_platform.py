"""Controllable platform services with no native global registration or capture."""
from mini_whiteboard.platform.base import (Platform, QtDesktop, QtRuntime, Display,
                                         HotkeyEvents, CREATE_HOTKEY, CAPTURE_HOTKEY, HIDE_HOTKEY)
from mini_whiteboard.geometry import Rect
from mini_whiteboard.shortcuts import ShortcutPolicy
from mini_whiteboard.hotkey_config import ConfigurableHotkeys, defaults
from mini_whiteboard.platform.hold import HoldTracker
from mini_whiteboard.platform.toggle import ToggleLatch


class FakeDesktop(QtDesktop):
    shadow_margin = 0
    paints_shadow = False

    def __init__(self):
        self.cursor = (40, 40)
        self.screens = [Display("Retina", Rect(0, 0, 1200, 800), 2, 10),
                        Display("Left", Rect(-1200, -100, 1200, 800), 1, 20)]

    def cursor_position(self):
        return self.cursor

    def displays(self):
        return self.screens


class FakeHotkeys(ConfigurableHotkeys):
    mac = True
    def __init__(self, app=None, preset="default"):
        self.events = HotkeyEvents()
        self.registered = set()
        self.escape = False
        self.preset = preset
        self.initialize_configuration(defaults(True, preset))
        self.hold = HoldTracker(app, self.events, self.sample)
        self.hide_latch = ToggleLatch(app, self.events.hide_toggle, lambda: False)

    def _register_chord(self, identifier, chord):
        self.registered.add(identifier)

    def _unregister(self, identifier):
        self.registered.discard(identifier)

    def sample(self):
        return set(), set()

    def record_release(self, identifier):
        pass

    def enable_escape(self):
        self.escape = True

    def disable_escape(self):
        self.escape = False

    def set_preset(self, preset):
        self.preset = preset
        self.registered.clear()

    def close(self):
        self.hold.close()
        self.hide_latch.close()
        self.registered.clear()


class FakeCapture:
    def __init__(self):
        self.requests = []
        self.denial = None

    def prepare(self):
        if self.denial:
            raise self.denial

    def capture_region(self, rect, success, failure, excluded=()):
        self.requests.append((rect, success, failure, excluded))

    def cancel(self):
        pass


def fake_platform():
    return Platform("fake", QtRuntime(), FakeDesktop(), FakeCapture(), FakeHotkeys, ShortcutPolicy(mac=True))
